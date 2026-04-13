"""主窗口 - 单页面伺服电机控制面板"""

import logging
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QScrollArea, QFrame, QListWidget,
    QListWidgetItem, QAbstractItemView, QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QShortcut, QKeySequence

from config import AppConfig
from protocol.modbus_client import ModbusClient
from protocol.register_map import OperationMode
from core.motor_controller import MotorController, DeviceState
from core.polling_service import PollingService
from core.udp_service import UdpService
from ui.point_manager import PointManager
from ui.styles import ToggleSwitch, get_stylesheet

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("伺服电机控制面板")
        self.setMinimumSize(960, 680)

        self._cfg = AppConfig()

        # 核心组件
        self._client = ModbusClient(self)
        self._controller = MotorController(self._client, self)
        self._polling = PollingService(self._client, self)
        self._udp = UdpService(self._cfg.udp_listen_port, self._cfg.udp_send_port, self)
        self._point_mgr = PointManager(self._cfg, parent=self)

        # 状态
        self._is_connected = False
        self._homing_state = "未完成"  # 未完成/回零进行中/已完成
        self._current_point_index = -1
        self._current_pos_pulse = 0
        self._target_pos_mm: float | None = None
        self._auto_cruise_running = False
        self._editing_point_index = -1
        self._active_edit_input = None
        self._auto_homing_done = False

        self._init_ui()
        self._apply_theme()
        self._connect_signals()
        self._udp.start()

        # UDP位置广播定时器 (30Hz)
        self._udp_pos_timer = QTimer(self)
        self._udp_pos_timer.timeout.connect(self._send_udp_position)
        self._udp_pos_timer.start(33)  # ~30fps

        # 自动连接
        QTimer.singleShot(500, self._auto_connect)

        # F12 调试面板
        self._debug_inspector = None
        QShortcut(QKeySequence(Qt.Key.Key_F12), self).activated.connect(
            self._toggle_debug_inspector
        )

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(24, 16, 24, 12)
        root.setSpacing(24)

        # === 左侧主面板 ===
        left = QVBoxLayout()
        left.setSpacing(14)

        # 标题
        title = QLabel("伺服电机控制面板")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left.addWidget(title)

        # 状态行: 回零状态 | 串口状态 | toggles
        status_toggle_row = QHBoxLayout()
        status_toggle_row.setSpacing(24)
        self._homing_status_label = QLabel("回零: 未完成")
        self._homing_status_label.setObjectName("status")
        self._serial_status_label = QLabel("串口: 未连接")
        self._serial_status_label.setObjectName("status")
        status_toggle_row.addWidget(self._homing_status_label)
        status_toggle_row.addWidget(self._serial_status_label)
        self._auto_init_toggle = ToggleSwitch("自动初始化    ", self._cfg.toggle_auto_init)
        self._broadcast_toggle = ToggleSwitch("发送实时位置    ", self._cfg.toggle_broadcast)
        status_toggle_row.addWidget(self._auto_init_toggle)
        status_toggle_row.addWidget(self._broadcast_toggle)
        status_toggle_row.addStretch()
        left.addLayout(status_toggle_row)

        # 信息行: 实时位置 | 当前点位 | UDP Msg
        info_row = QHBoxLayout()
        info_row.setSpacing(24)
        self._pos_display = QLabel("位置: 0 mm")
        self._pos_display.setObjectName("pos-display")
        self._cur_pt_label = QLabel("当前点位: --")
        self._cur_pt_label.setObjectName("cur-point")
        self._udp_label = QLabel("UDP Msg: --")
        self._udp_label.setObjectName("udp-msg")
        info_row.addWidget(self._pos_display)
        info_row.addWidget(self._cur_pt_label)
        info_row.addWidget(self._udp_label)
        info_row.addStretch()
        left.addLayout(info_row)

        # 控制按钮
        grid = QGridLayout()
        grid.setSpacing(30)
        btn_defs = [
            ("上一个", "pill", 0, 0), ("下一个", "pill", 0, 1), ("起点", "pill", 0, 2),
            ("CCW100", "pill", 1, 0), ("CW100", "pill", 1, 1), ("停止", "pill-stop", 1, 2),
        ]
        self._ctrl_btns = {}
        for text, cls, r, c in btn_defs:
            btn = QPushButton(text)
            btn.setProperty("class", cls)
            grid.addWidget(btn, r, c)
            self._ctrl_btns[text] = btn
        left.addLayout(grid)

        # Jog控制行: -100 -10 -1 [输入框] +1 +10 +100
        jog_row = QHBoxLayout()
        jog_row.setSpacing(5)
        for delta in [-100, -10, -1]:
            btn = QPushButton(str(delta))
            btn.setProperty("class", "jog-btn")
            btn.clicked.connect(lambda _, d=delta: self._jog_adjust(d))
            jog_row.addWidget(btn)
        self._jog_input = QLineEdit()
        self._jog_input.setPlaceholderText("请输入目标位置")
        self._jog_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        jog_row.addWidget(self._jog_input, 1)
        for delta in [1, 10, 100]:
            btn = QPushButton(f"+{delta}")
            btn.setProperty("class", "jog-btn")
            btn.clicked.connect(lambda _, d=delta: self._jog_adjust(d))
            jog_row.addWidget(btn)
        left.addLayout(jog_row)

        # 底部行: 添加点位 | 启动 | 自动巡航
        pt_row = QHBoxLayout()
        pt_row.setSpacing(30)
        self._add_pt_btn = QPushButton("添加点位")
        self._go_btn = QPushButton("启动")
        self._cruise_btn = QPushButton("自动巡航")
        for b in [self._add_pt_btn, self._go_btn, self._cruise_btn]:
            b.setProperty("class", "pill")
            pt_row.addWidget(b)
        left.addLayout(pt_row)
        left.addStretch()

        # === 右侧点位列表 ===
        right = QVBoxLayout()
        right.setSpacing(15)
        pt_title = QLabel("点位列表:")
        pt_title.setObjectName("cur-point")
        right.addWidget(pt_title)


        self._point_list = QListWidget()
        self._point_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._point_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._point_list.model().rowsMoved.connect(self._on_points_reordered)
        self._point_list.currentRowChanged.connect(self._on_list_row_changed)
        right.addWidget(self._point_list, 1)

        # 编辑/保存/删除
        edit_btn_row1 = QHBoxLayout()
        edit_btn_row1.setSpacing(8)
        self._edit_btn = QPushButton("编辑")
        self._save_btn = QPushButton("保存")
        self._del_sel_btn = QPushButton("删除")
        for b in [self._edit_btn, self._save_btn, self._del_sel_btn]:
            b.setProperty("class", "point-action")
            edit_btn_row1.addWidget(b)
        right.addLayout(edit_btn_row1)

        # 设为起点/清空列表
        edit_btn_row2 = QHBoxLayout()
        edit_btn_row2.setSpacing(8)
        self._set_start_btn = QPushButton("设为起点")
        self._clear_pt_btn = QPushButton("清空列表")
        for b in [self._set_start_btn, self._clear_pt_btn]:
            b.setProperty("class", "point-action")
            edit_btn_row2.addWidget(b)
        right.addLayout(edit_btn_row2)

        # 编辑Jog
        edit_jog_row = QHBoxLayout()
        edit_jog_row.setSpacing(4)
        for delta in [-100, -10, -1, 1, 10, 100]:
            btn = QPushButton(f"+{delta}" if delta > 0 else str(delta))
            btn.setProperty("class", "jog-btn")
            btn.clicked.connect(lambda _, d=delta: self._edit_jog_adjust(d))
            edit_jog_row.addWidget(btn)
        right.addLayout(edit_jog_row)

        root.addLayout(left, 3)
        root.addLayout(right, 1)
        self._refresh_point_list()

    def _connect_signals(self):
        self._client.connected.connect(self._on_connection_changed)
        self._client.error.connect(lambda msg: logger.error(msg))
        self._polling.position_updated.connect(self._on_position)
        self._polling.status_updated.connect(self._on_status)
        self._controller.state_changed.connect(self._on_state_changed)
        self._controller.command_done.connect(self._on_command_done)
        self._udp.message_received.connect(self._on_udp_msg)

        self._ctrl_btns["上一个"].clicked.connect(self._go_prev_point)
        self._ctrl_btns["下一个"].clicked.connect(self._go_next_point)
        self._ctrl_btns["起点"].clicked.connect(self._go_start_point)
        self._ctrl_btns["停止"].clicked.connect(self._stop_motion)
        self._ctrl_btns["CCW100"].clicked.connect(lambda: self._relative_move(100))
        self._ctrl_btns["CW100"].clicked.connect(lambda: self._relative_move(-100))

        self._go_btn.clicked.connect(self._jog_execute)
        self._cruise_btn.clicked.connect(self._toggle_auto_cruise)
        self._add_pt_btn.clicked.connect(self._add_current_point)
        self._clear_pt_btn.clicked.connect(self._confirm_clear_points)
        self._edit_btn.clicked.connect(self._start_edit)
        self._save_btn.clicked.connect(self._save_edit)
        self._del_sel_btn.clicked.connect(self._delete_selected_point)
        self._set_start_btn.clicked.connect(self._set_as_start_point)
        self._auto_init_toggle.toggled.connect(self._on_toggle_auto_init)
        self._broadcast_toggle.toggled.connect(self._on_toggle_broadcast)
        self._point_mgr.points_changed.connect(self._refresh_point_list)

    # === 连接 ===

    def _auto_connect(self):
        self._client.connect_device(
            self._cfg.serial_port, self._cfg.serial_baudrate,
            self._cfg.serial_slave_id, int(self._cfg.serial_timeout * 1000),
        )

    def _on_connection_changed(self, connected: bool):
        self._is_connected = connected
        if connected:
            self._serial_status_label.setText("串口: 已连接")
            self._serial_status_label.setStyleSheet("font-size: 16px; color: #008a05; font-weight: 600;")
            self._polling.start(self._cfg.fast_poll_ms, self._cfg.slow_poll_ms)
            if self._auto_init_toggle.isChecked():
                QTimer.singleShot(self._cfg.auto_init_delay_ms, self._auto_init)
            else:
                self._homing_state = "已完成"
                self._update_homing_label()
        else:
            self._serial_status_label.setText("串口: 未连接")
            self._serial_status_label.setStyleSheet("font-size: 16px; color: #ff385c; font-weight: 600;")
            self._polling.stop()

    def _auto_init(self):
        if self._is_connected:
            self._controller.enable()

    # === 轮询数据 ===

    def _on_position(self, ts: float, pulse: int):
        self._current_pos_pulse = pulse
        mm = pulse / self._cfg.pulse_per_mm
        self._pos_display.setText(f"位置: {mm:.1f} mm")
        # 距离到达检测
        self._check_arrival(mm)

    def _check_arrival(self, current_mm: float):
        if self._target_pos_mm is None:
            return
        if abs(current_mm - self._target_pos_mm) <= self._cfg.dist_tolerance:
            arrived_target = self._target_pos_mm
            self._target_pos_mm = None  # 清除，防止重复触发
            # 发送UDP点位通知
            if self._current_point_index >= 0:
                self._udp.send_point_arrival(self._current_point_index)
            # 自动巡航: 到达后去下一个
            if self._auto_cruise_running:
                QTimer.singleShot(300, self._cruise_next)

    def _on_state_changed(self, state: int):
        pass

    def _on_command_done(self, cmd: str, success: bool, msg: str):
        if cmd == "enable" and success and not self._auto_homing_done:
            self._auto_homing_done = True
            self._homing_state = "回零进行中"
            self._update_homing_label()
            self._controller.set_mode(OperationMode.HOMING)
            QTimer.singleShot(200, self._start_auto_homing)
        elif cmd == "homing_start" and success:
            self._homing_check_timer = QTimer(self)
            self._homing_check_timer.timeout.connect(self._poll_homing_status)
            self._homing_check_timer.start(500)

    def _start_auto_homing(self):
        self._controller.start_homing(
            method=self._cfg.homing_method_ccw,
            speed=self._cfg.homing_speed,
            accel=self._cfg.homing_accel,
            offset=self._cfg.homing_offset,
        )

    def _poll_homing_status(self):
        """定时读状态字检测回零完成"""
        self._homing_poll_rid = self._client.read_raw(0x6041, 1)

    def _on_status(self, status_word: int):
        self._controller.update_state_from_status(status_word)
        # 也用轮询的状态字检测回零完成(bit12)
        if self._homing_state == "回零进行中" and (status_word & (1 << 12)):
            if hasattr(self, '_homing_check_timer'):
                self._homing_check_timer.stop()
                del self._homing_check_timer
            self._homing_state = "已完成"
            self._update_homing_label()
            QTimer.singleShot(500, self._go_start_point)

    def _on_udp_msg(self, msg: str):
        self._udp_label.setText(f"UDP Msg: {msg}")
        # UDP收到数字指令，移动到对应点位
        stripped = msg.strip()
        if stripped.isdigit():
            idx = int(stripped) - 1  # "1"->index 0, "2"->index 1
            if 0 <= idx < self._point_mgr.count:
                self._goto_point(idx)

    def _send_udp_position(self):
        """30Hz定时发送实时位置 - 仅在移动中发送"""
        if self._broadcast_toggle.isChecked() and self._is_connected and self._target_pos_mm is not None:
            mm = self._current_pos_pulse / self._cfg.pulse_per_mm
            self._udp.send_position(mm)

    # === 控制按钮 ===

    def _move_to_mm(self, mm: float):
        self._target_pos_mm = mm
        pulse = int(mm * self._cfg.pulse_per_mm)
        # 确保控制字干净(清除暂停等状态)
        self._controller._control_word = 0x000F
        self._client.write_raw(0x6040, 0x000F)
        self._controller.set_mode(OperationMode.POSITION)
        QTimer.singleShot(150, lambda: self._controller.start_position_move(
            target=pulse, speed=self._cfg.move_speed,
            accel=self._cfg.move_accel, decel=self._cfg.move_decel, absolute=True,
        ))

    def _relative_move(self, delta_mm: float):
        current_mm = self._current_pos_pulse / self._cfg.pulse_per_mm
        self._move_to_mm(current_mm + delta_mm)

    def _go_prev_point(self):
        if self._point_mgr.count == 0: return
        self._current_point_index = max(0, self._current_point_index - 1)
        self._goto_point(self._current_point_index)

    def _go_next_point(self):
        if self._point_mgr.count == 0: return
        self._current_point_index = min(self._point_mgr.count - 1, self._current_point_index + 1)
        self._goto_point(self._current_point_index)

    def _go_start_point(self):
        if self._point_mgr.count == 0: return
        idx = min(self._cfg.start_point, self._point_mgr.count - 1)
        self._goto_point(idx)

    def _goto_point(self, index: int):
        pt = self._point_mgr.get(index)
        if pt:
            self._current_point_index = index
            self._move_to_mm(pt["position_mm"])
            self._cur_pt_label.setText(f"当前点位: {pt['name']}")
            self._refresh_point_list()

    def _homing_cw(self):
        self._auto_cruise_running = False
        self._target_pos_mm = None
        self._homing_state = "回零进行中"
        self._update_homing_label()
        # 先恢复控制字到使能状态，再切模式
        self._controller._control_word = 0x000F
        self._client.write_raw(0x6040, 0x000F)
        self._controller.set_mode(OperationMode.HOMING)
        QTimer.singleShot(300, lambda: self._controller.start_homing(
            method=self._cfg.homing_method_cw,
            speed=self._cfg.homing_speed, accel=self._cfg.homing_accel,
            offset=self._cfg.homing_offset,
        ))

    def _homing_ccw(self):
        self._auto_cruise_running = False
        self._target_pos_mm = None
        self._homing_state = "回零进行中"
        self._update_homing_label()
        self._controller._control_word = 0x000F
        self._client.write_raw(0x6040, 0x000F)
        self._controller.set_mode(OperationMode.HOMING)
        QTimer.singleShot(300, lambda: self._controller.start_homing(
            method=self._cfg.homing_method_ccw,
            speed=self._cfg.homing_speed, accel=self._cfg.homing_accel,
            offset=self._cfg.homing_offset,
        ))

    def _stop_motion(self):
        self._auto_cruise_running = False
        self._target_pos_mm = None
        self._controller.pause()  # 暂停运动，保持使能

    def _toggle_auto_cruise(self):
        if self._auto_cruise_running:
            self._auto_cruise_running = False
            self._target_pos_mm = None
            self._controller.pause()
            return
        if self._point_mgr.count == 0: return
        self._auto_cruise_running = True
        self._current_point_index = 0
        self._goto_point(0)

    def _cruise_next(self):
        if not self._auto_cruise_running or self._point_mgr.count == 0:
            return
        next_idx = (self._current_point_index + 1) % self._point_mgr.count
        self._goto_point(next_idx)

    # === Jog ===

    def _jog_adjust(self, delta: int):
        try:
            val = float(self._jog_input.text()) + delta
        except ValueError:
            val = delta
        self._jog_input.setText(str(int(val)))

    def _jog_execute(self):
        try:
            mm = float(self._jog_input.text())
        except ValueError:
            return
        self._move_to_mm(mm)

    # === 点位管理 ===

    def _add_current_point(self):
        mm = self._current_pos_pulse / self._cfg.pulse_per_mm
        self._point_mgr.add(mm)

    def _delete_selected_point(self):
        if 0 <= self._current_point_index < self._point_mgr.count:
            self._point_mgr.remove(self._current_point_index)
            # 重新编号
            self._renumber_points()
            self._current_point_index = min(self._current_point_index, self._point_mgr.count - 1)
            self._editing_point_index = -1

    def _renumber_points(self):
        """删除后重新排列序号 P-01, P-02, ..."""
        for i, pt in enumerate(self._point_mgr.get_all()):
            pt["name"] = f"P-{i+1:02d}"
        self._point_mgr._save_and_notify()

    def _start_edit(self):
        """将当前选中点位设为编辑状态，数值变为可输入"""
        if self._current_point_index >= 0:
            self._editing_point_index = self._current_point_index
            self._active_edit_input = None
            self._refresh_point_list()

    def _save_edit(self):
        """保存编辑中的数值到点位，退出编辑状态"""
        if self._editing_point_index >= 0 and self._active_edit_input:
            try:
                new_val = float(self._active_edit_input.text())
                self._point_mgr.update_position(self._editing_point_index, new_val)
            except ValueError:
                pass
        self._editing_point_index = -1
        self._active_edit_input = None
        self._refresh_point_list()

    def _set_as_start_point(self):
        if self._current_point_index >= 0:
            self._cfg.start_point = self._current_point_index
            self._refresh_point_list()

    def _confirm_clear_points(self):
        ret = QMessageBox.question(
            self, "确认", "确定要清除全部点位吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret == QMessageBox.StandardButton.Yes:
            self._point_mgr.clear()

    def _update_homing_label(self):
        """根据回零状态更新标签文字和颜色"""
        colors = {"已完成": "#008a05", "回零进行中": "#c77800", "未完成": "#929292"}
        color = colors.get(self._homing_state, "#929292")
        self._homing_status_label.setText(f"回零: {self._homing_state}")
        self._homing_status_label.setStyleSheet(f"font-size: 16px; color: {color}; font-weight: 600;")

    def _apply_theme(self):
        """应用浅色主题"""
        self.setStyleSheet(get_stylesheet())

    def _on_toggle_auto_init(self, checked: bool):
        self._cfg.toggle_auto_init = checked

    def _on_toggle_broadcast(self, checked: bool):
        self._cfg.toggle_broadcast = checked

    def _edit_jog_adjust(self, delta: int):
        """编辑状态下，jog按钮调整输入框中的数值"""
        if self._editing_point_index < 0 or not self._active_edit_input:
            return
        try:
            val = float(self._active_edit_input.text()) + delta
        except ValueError:
            val = delta
        self._active_edit_input.setText(str(int(val)))

    def _refresh_point_list(self):
        self._point_list.blockSignals(True)
        self._point_list.clear()
        start_idx = self._cfg.start_point
        self._active_edit_input = None

        for i, pt in enumerate(self._point_mgr.get_all()):
            is_editing = (i == self._editing_point_index)
            is_current = (i == self._current_point_index)

            # 构建行widget
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(4, 2, 4, 2)
            h.setSpacing(6)

            # 起点红点
            if i == start_idx:
                dot = QLabel("\u25cf")
                dot.setStyleSheet("color: #ff385c; font-size: 14px;")
                dot.setFixedWidth(16)
                h.addWidget(dot)

            if is_editing:
                name_lbl = QLabel(f"{pt['name']}:")
                name_lbl.setStyleSheet("color: #222222; font-weight: 600;")
                h.addWidget(name_lbl)
                edit_input = QLineEdit(str(int(pt['position_mm'])))
                edit_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
                edit_input.setFixedWidth(80)
                h.addWidget(edit_input)
                self._active_edit_input = edit_input
            else:
                label = QLabel(f"{pt['name']}: {pt['position_mm']:.0f} mm")
                if is_current:
                    label.setStyleSheet("color: #222222; font-weight: 600;")
                h.addWidget(label)

            h.addStretch()
            go_btn = QPushButton("Go")
            go_btn.setFixedSize(44, 28)
            go_btn.setProperty("class", "point-action")
            go_btn.clicked.connect(lambda _, idx=i: self._goto_point(idx))
            h.addWidget(go_btn)

            from PyQt6.QtCore import QSize
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 52))
            self._point_list.addItem(item)
            self._point_list.setItemWidget(item, row)

        self._point_list.blockSignals(False)
        if 0 <= self._current_point_index < self._point_list.count():
            self._point_list.setCurrentRow(self._current_point_index)

    def _on_list_row_changed(self, row: int):
        if row < 0 or row >= self._point_mgr.count:
            return
        self._current_point_index = row
        pt = self._point_mgr.get(row)
        if pt:
            self._cur_pt_label.setText(f"当前点位: {pt['name']}")

    def _on_points_reordered(self):
        """拖拽排序后，根据widget中的文本重建数据"""
        new_order = []
        for i in range(self._point_list.count()):
            item = self._point_list.item(i)
            widget = self._point_list.itemWidget(item)
            if not widget:
                continue
            labels = widget.findChildren(QLabel)
            for lbl in labels:
                text = lbl.text()
                if ":" in text and text.startswith("P-"):
                    parts = text.split(":")
                    try:
                        val = float(parts[1])
                        new_order.append({"name": parts[0], "position_mm": val})
                    except (ValueError, IndexError):
                        pass
                    break

        if new_order and len(new_order) == self._point_mgr.count:
            for i, pt in enumerate(new_order):
                pt["name"] = f"P-{i+1:02d}"
            self._point_mgr._points = new_order
            self._point_mgr._save_and_notify()

    # === 关闭 ===

    def closeEvent(self, event):
        self._auto_cruise_running = False
        self._polling.stop()
        self._udp.stop()
        if self._controller.is_enabled:
            self._controller.disable()
        self._client.shutdown()
        event.accept()

    def _toggle_debug_inspector(self):
        """F12 切换调试面板"""
        if self._debug_inspector is None:
            from ui.debug_inspector import DebugInspector
            self._debug_inspector = DebugInspector(self)
            self.addDockWidget(
                Qt.DockWidgetArea.RightDockWidgetArea,
                self._debug_inspector,
            )
        else:
            vis = not self._debug_inspector.isVisible()
            self._debug_inspector.setVisible(vis)
            if vis:
                self._debug_inspector.refresh_tree()
