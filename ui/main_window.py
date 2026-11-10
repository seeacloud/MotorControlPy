"""主窗口 - 单页面伺服电机控制面板"""

import logging
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QScrollArea, QFrame, QListWidget,
    QListWidgetItem, QAbstractItemView, QMessageBox, QMenu, QStyle,
    QSystemTrayIcon, QSizePolicy, QToolButton,
)
from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtGui import QShortcut, QKeySequence

from config import AppConfig
from protocol.modbus_client import ModbusClient
from protocol.register_map import OperationMode
from core.motor_controller import MotorController, DeviceState
from core.polling_service import PollingService
from core.udp_service import UdpService
from ui.point_manager import PointManager
from ui.styles import ToggleSwitch, get_stylesheet
from version import APP_VERSION

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, False)
        self.setWindowTitle(f"伺服电机控制面板 V{APP_VERSION}")
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
        self._motor_disabled_after_arrival = False  # 到达点位后是否已停止使能
        self._pending_move_mm: float | None = None  # 等待重新使能后执行的移动目标
        self._parameter_inputs: dict[str, QLineEdit] = {}
        self._parameter_labels: dict[str, QLabel] = {}
        self._parameter_specs = {
            "move_speed": ("运行速度", self._cfg.move_speed, 1.0, 50.0, False),
            "homing_speed": ("回零速度", self._cfg.homing_speed, 1.0, 100000.0, True),
            "move_accel": ("加速度", self._cfg.move_accel, 0.1, 6553.5, False),
            "move_decel": ("减速度", self._cfg.move_decel, 0.1, 6553.5, False),
        }

        self._init_ui()
        self._apply_theme()
        self._init_tray()
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

    @property
    def start_minimized(self) -> bool:
        """返回是否应在启动时隐藏到系统托盘。"""
        return self._cfg.toggle_start_minimized

    def _init_tray(self):
        """创建系统托盘图标和快捷菜单。"""
        icon = self.windowIcon()
        if icon.isNull():
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
            self.setWindowIcon(icon)

        self._tray_icon = QSystemTrayIcon(icon, self)
        self._tray_icon.setToolTip(f"伺服电机控制系统 V{APP_VERSION}")

        self._tray_menu = QMenu(self)
        show_action = self._tray_menu.addAction("显示主窗口")
        show_action.triggered.connect(self._restore_from_tray)
        self._tray_menu.addSeparator()
        quit_action = self._tray_menu.addAction("退出")
        quit_action.triggered.connect(self.close)

        self._tray_icon.setContextMenu(self._tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._restore_from_tray()

    def _restore_from_tray(self):
        """恢复主窗口并将其置于前台。"""
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized():
            QTimer.singleShot(0, self.hide)

    def _init_ui(self):
        central = QWidget()
        central.setObjectName("workspace")
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(24)

        # === 左侧主面板 ===
        left = QVBoxLayout()
        left.setSpacing(16)

        # 标题
        title = QLabel("伺服电机控制面板")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        left.addWidget(title)

        # 状态行: 回零状态 | 串口状态
        status_row = QHBoxLayout()
        status_row.setSpacing(24)
        self._homing_status_label = QLabel("回零: 未完成")
        self._homing_status_label.setObjectName("status")
        self._serial_status_label = QLabel("串口: 未连接")
        self._serial_status_label.setObjectName("status")
        status_row.addWidget(self._homing_status_label)
        status_row.addWidget(self._serial_status_label)
        status_row.addStretch()
        left.addLayout(status_row)

        # 紧凑开关单行排列，保留更多纵向空间。
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(8)
        self._auto_init_toggle = ToggleSwitch("自动回零", self._cfg.toggle_auto_init)
        self._broadcast_toggle = ToggleSwitch("发送实时位置", self._cfg.toggle_broadcast)
        self._start_minimized_toggle = ToggleSwitch(
            "启动时最小化", self._cfg.toggle_start_minimized
        )
        self._disable_on_arrival_toggle = ToggleSwitch(
            "到位后停止使能", self._cfg.toggle_disable_on_arrival
        )
        toggle_row.addWidget(self._auto_init_toggle)
        toggle_row.addWidget(self._broadcast_toggle)
        toggle_row.addWidget(self._start_minimized_toggle)
        toggle_row.addWidget(self._disable_on_arrival_toggle)
        toggle_row.addStretch()
        left.addLayout(toggle_row)

        # 关键运行数据
        telemetry = QFrame()
        telemetry.setObjectName("telemetry")
        info_row = QHBoxLayout(telemetry)
        info_row.setContentsMargins(20, 12, 20, 12)
        info_row.setSpacing(20)

        position_group = QVBoxLayout()
        position_group.setSpacing(2)
        position_caption = QLabel("实时位置")
        position_caption.setObjectName("data-label")
        self._pos_display = QLabel("0 mm")
        self._pos_display.setObjectName("pos-display")
        position_group.addWidget(position_caption)
        position_group.addWidget(self._pos_display)
        info_row.addLayout(position_group, 2)

        current_group = QVBoxLayout()
        current_group.setSpacing(2)
        current_caption = QLabel("当前点位")
        current_caption.setObjectName("data-label")
        self._cur_pt_label = QLabel("--")
        self._cur_pt_label.setObjectName("cur-point")
        current_group.addWidget(current_caption)
        current_group.addWidget(self._cur_pt_label)
        info_row.addLayout(current_group, 1)

        udp_group = QVBoxLayout()
        udp_group.setSpacing(2)
        udp_caption = QLabel("UDP 消息")
        udp_caption.setObjectName("data-label")
        self._udp_label = QLabel("--")
        self._udp_label.setObjectName("udp-msg")
        udp_group.addWidget(udp_caption)
        udp_group.addWidget(self._udp_label)
        info_row.addLayout(udp_group, 1)
        left.addWidget(telemetry)

        # 控制按钮
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        for column in range(3):
            grid.setColumnStretch(column, 1)
        btn_defs = [
            ("上一个", "outlined", 0, 0), ("下一个", "outlined", 0, 1), ("起点", "outlined", 0, 2),
            ("CCW100", "tonal", 1, 0), ("CW100", "tonal", 1, 1), ("停止", "danger", 1, 2),
            ("CCW回零", "tonal", 2, 0), ("CW回零", "tonal", 2, 1),
        ]
        self._ctrl_btns = {}
        for text, cls, r, c in btn_defs:
            btn = QPushButton(text)
            btn.setProperty("class", cls)
            row_span = 2 if text == "停止" else 1
            vertical_policy = (
                QSizePolicy.Policy.Expanding
                if text == "停止"
                else QSizePolicy.Policy.Fixed
            )
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, vertical_policy)
            grid.addWidget(btn, r, c, row_span, 1)
            self._ctrl_btns[text] = btn
        left.addLayout(grid)

        # Jog控制行: -100 -10 -1 [输入框] +1 +10 +100
        jog_row = QHBoxLayout()
        jog_row.setSpacing(8)
        for delta in [-100, -10, -1]:
            btn = QPushButton(str(delta))
            btn.setProperty("class", "step")
            btn.clicked.connect(lambda _, d=delta: self._jog_adjust(d))
            jog_row.addWidget(btn)
        self._jog_input = QLineEdit()
        self._jog_input.setPlaceholderText("请输入目标位置")
        self._jog_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        jog_row.addWidget(self._jog_input, 1)
        for delta in [1, 10, 100]:
            btn = QPushButton(f"+{delta}")
            btn.setProperty("class", "step")
            btn.clicked.connect(lambda _, d=delta: self._jog_adjust(d))
            jog_row.addWidget(btn)
        left.addLayout(jog_row)

        # 底部行: 添加点位 | 启动 | 自动巡航
        pt_row = QHBoxLayout()
        pt_row.setSpacing(12)
        self._add_pt_btn = QPushButton("添加点位")
        self._go_btn = QPushButton("启动")
        self._cruise_btn = QPushButton("自动巡航")
        self._add_pt_btn.setProperty("class", "outlined")
        self._go_btn.setProperty("class", "primary")
        self._cruise_btn.setProperty("class", "tonal")
        for button in [self._add_pt_btn, self._go_btn, self._cruise_btn]:
            pt_row.addWidget(button)
        left.addLayout(pt_row)
        left.addStretch()

        # === 右侧点位列表 ===
        right = QVBoxLayout()
        right.setSpacing(12)
        pt_title = QLabel("点位列表")
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
        self._edit_btn.setProperty("class", "text")
        self._save_btn.setProperty("class", "primary-small")
        self._del_sel_btn.setProperty("class", "danger-text")
        for button in [self._edit_btn, self._save_btn, self._del_sel_btn]:
            edit_btn_row1.addWidget(button)
        right.addLayout(edit_btn_row1)

        # 设为起点/清空列表
        edit_btn_row2 = QHBoxLayout()
        edit_btn_row2.setSpacing(8)
        self._set_start_btn = QPushButton("设为起点")
        self._clear_pt_btn = QPushButton("清空列表")
        self._set_start_btn.setProperty("class", "text")
        self._clear_pt_btn.setProperty("class", "danger-text")
        for button in [self._set_start_btn, self._clear_pt_btn]:
            edit_btn_row2.addWidget(button)
        right.addLayout(edit_btn_row2)

        # 编辑Jog
        edit_jog_row = QHBoxLayout()
        edit_jog_row.setSpacing(4)
        for delta in [-100, -10, -1, 1, 10, 100]:
            btn = QPushButton(f"+{delta}" if delta > 0 else str(delta))
            btn.setProperty("class", "step")
            btn.clicked.connect(lambda _, d=delta: self._edit_jog_adjust(d))
            edit_jog_row.addWidget(btn)
        right.addLayout(edit_jog_row)

        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFrameShape(QFrame.Shape.HLine)
        right.addWidget(divider)

        self._parameter_toggle = QToolButton()
        self._parameter_toggle.setObjectName("section-toggle")
        self._parameter_toggle.setText("运动参数")
        self._parameter_toggle.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self._parameter_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self._parameter_toggle.setCheckable(True)
        self._parameter_toggle.setChecked(False)
        self._parameter_toggle.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._parameter_toggle.setToolTip("展开运动参数")
        self._parameter_toggle.toggled.connect(self._set_parameter_panel_expanded)
        right.addWidget(self._parameter_toggle)

        self._parameter_panel = QWidget()
        parameter_panel_layout = QVBoxLayout(self._parameter_panel)
        parameter_panel_layout.setContentsMargins(0, 0, 0, 0)
        parameter_panel_layout.setSpacing(8)

        parameter_grid = QGridLayout()
        parameter_grid.setHorizontalSpacing(4)
        parameter_grid.setVerticalSpacing(6)
        parameter_grid.setColumnStretch(0, 1)
        for row, key in enumerate(self._parameter_specs):
            self._add_parameter_row(parameter_grid, row, key)
        parameter_panel_layout.addLayout(parameter_grid)

        self._parameter_save_btn = QPushButton("保存运动参数")
        self._parameter_save_btn.setProperty("class", "primary-small")
        self._parameter_save_btn.clicked.connect(self._save_parameters)
        parameter_panel_layout.addWidget(self._parameter_save_btn)
        self._parameter_panel.setVisible(False)
        right.addWidget(self._parameter_panel)

        root.addLayout(left, 3)
        root.addLayout(right, 1)
        self._refresh_point_list()

    def _set_parameter_panel_expanded(self, expanded: bool):
        """展开或折叠运动参数面板，并将高度归还给点位列表。"""
        self._parameter_panel.setVisible(expanded)
        self._parameter_toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self._parameter_toggle.setToolTip(
            "收起运动参数" if expanded else "展开运动参数"
        )

    def _add_parameter_row(self, grid: QGridLayout, row: int, key: str):
        """创建一行可步进调节的运动参数控件。"""
        label_text, value, _minimum, _maximum, _integer = self._parameter_specs[key]
        label = QLabel(self._parameter_label_text(key, value))
        label.setObjectName("field-label")
        self._parameter_labels[key] = label
        grid.addWidget(label, row, 0)

        for column, delta in ((1, -10), (2, -1)):
            button = QPushButton(str(delta))
            button.setProperty("class", "parameter-step")
            button.setFixedSize(34, 30)
            button.clicked.connect(
                lambda _, parameter=key, amount=delta: self._adjust_parameter(parameter, amount)
            )
            grid.addWidget(button, row, column)

        input_widget = QLineEdit(self._format_parameter_value(key, value))
        input_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        input_widget.setFixedWidth(72)
        if key in ("move_speed", "homing_speed"):
            input_widget.setToolTip("输入单位：转/秒 (r/s)")
            input_widget.textChanged.connect(
                lambda text, parameter=key: self._update_speed_parameter_label(
                    parameter, text
                )
            )
        self._parameter_inputs[key] = input_widget
        grid.addWidget(input_widget, row, 3)

        for column, delta in ((4, 1), (5, 10)):
            button = QPushButton(f"+{delta}")
            button.setProperty("class", "parameter-step")
            button.setFixedSize(34, 30)
            button.clicked.connect(
                lambda _, parameter=key, amount=delta: self._adjust_parameter(parameter, amount)
            )
            grid.addWidget(button, row, column)

    def _connect_signals(self):
        self._client.connected.connect(self._on_connection_changed)
        self._client.error.connect(lambda msg: logger.error(msg))
        self._polling.position_updated.connect(self._on_position)
        self._polling.status_updated.connect(self._on_status)
        self._polling.error_updated.connect(self._on_error)
        self._controller.state_changed.connect(self._on_state_changed)
        self._controller.command_done.connect(self._on_command_done)
        self._udp.message_received.connect(self._on_udp_msg)

        self._ctrl_btns["上一个"].clicked.connect(self._go_prev_point)
        self._ctrl_btns["下一个"].clicked.connect(self._go_next_point)
        self._ctrl_btns["起点"].clicked.connect(self._go_start_point)
        self._ctrl_btns["停止"].clicked.connect(self._stop_motion)
        self._ctrl_btns["CCW100"].clicked.connect(lambda: self._relative_move(100))
        self._ctrl_btns["CW100"].clicked.connect(lambda: self._relative_move(-100))
        self._ctrl_btns["CCW回零"].clicked.connect(self._homing_ccw)
        self._ctrl_btns["CW回零"].clicked.connect(self._homing_cw)

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
        self._start_minimized_toggle.toggled.connect(self._on_toggle_start_minimized)
        self._disable_on_arrival_toggle.toggled.connect(
            self._on_toggle_disable_on_arrival
        )
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
            self._serial_status_label.setStyleSheet("font-size: 14px; color: #188038; font-weight: 400;")
            self._polling.start(self._cfg.fast_poll_ms, self._cfg.slow_poll_ms)
            if self._auto_init_toggle.isChecked():
                QTimer.singleShot(self._cfg.auto_init_delay_ms, self._auto_init)
            else:
                self._homing_state = "已完成"
                self._update_homing_label()
        else:
            self._serial_status_label.setText("串口: 未连接")
            self._serial_status_label.setStyleSheet("font-size: 14px; color: #b3261e; font-weight: 400;")
            self._polling.stop()

    def _auto_init(self):
        """自动初始化: 清除电机残留状态 → 故障复位 → 使能 → 回零"""
        if not self._is_connected:
            return
        # 1) 清除控制字，让电机回到未就绪状态
        self._controller._control_word = 0x0000
        self._client.write_raw(0x6040, 0x0000)
        # 2) 故障复位(bit7上升沿)，防止残留故障阻止使能
        QTimer.singleShot(200, lambda: self._client.write_raw(0x6040, 0x0080))
        QTimer.singleShot(400, lambda: self._client.write_raw(0x6040, 0x0000))
        # 3) 重置内部标志，然后执行使能序列
        self._auto_homing_done = False
        QTimer.singleShot(600, self._controller.enable)

    # === 轮询数据 ===

    def _on_position(self, ts: float, pulse: int):
        self._current_pos_pulse = pulse
        mm = pulse / self._cfg.pulse_per_mm
        self._pos_display.setText(f"{mm:.0f} mm")
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
            # 根据开关决定是否在到位2秒后停止使能，留出充分的定位时间。
            if self._disable_on_arrival_toggle.isChecked():
                QTimer.singleShot(2000, self._disable_after_arrival)
            # 自动巡航: 到达后去下一个
            if self._auto_cruise_running:
                QTimer.singleShot(300, self._cruise_next)

    def _disable_after_arrival(self):
        """到达点位2秒后停止电机使能，减少发热和噪音。"""
        if not self._disable_on_arrival_toggle.isChecked():
            return
        if self._target_pos_mm is not None:
            return  # 已经有新的移动指令，不再停止使能
        if self._auto_cruise_running:
            return  # 自动巡航中不停止使能
        self._controller.disable()
        self._motor_disabled_after_arrival = True
        logger.info("到达点位，已停止电机使能")

    def _on_state_changed(self, state: int):
        pass

    def _on_error(self, error_word: int):
        """处理错误寄存器"""
        if error_word == 0:
            return
        from protocol.register_map import ERROR_BITS
        errors = [desc for bit, desc in ERROR_BITS.items() if error_word & (1 << bit)]
        error_str = ", ".join(errors) if errors else f"未知错误(0x{error_word:04X})"
        logger.error(f"电机故障: {error_str} (error_word=0x{error_word:04X})")
        self._homing_status_label.setText(f"故障: {error_str}")
        self._homing_status_label.setStyleSheet("font-size: 14px; color: #b3261e; font-weight: 400;")

    def _on_command_done(self, cmd: str, success: bool, msg: str):
        logger.info(f"命令完成: {cmd}, 成功={success}, 消息={msg}")
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
            logger.info("回零完成，准备切换到位置模式并去起点")
            # 回零完成后，重新走使能序列，确保控制字干净
            self._controller._control_word = 0x0000
            self._client.write_raw(0x6040, 0x0000)
            QTimer.singleShot(200, lambda: self._client.write_raw(0x6040, 0x0006))
            QTimer.singleShot(400, lambda: self._client.write_raw(0x6040, 0x0007))
            QTimer.singleShot(600, lambda: self._client.write_raw(0x6040, 0x000F))
            QTimer.singleShot(700, lambda: self._controller.set_mode(OperationMode.POSITION))
            QTimer.singleShot(800, self._after_homing_enable)

    def _after_homing_enable(self):
        """回零完成后重新使能完毕，更新内部状态并去起点"""
        self._controller._control_word = 0x000F
        self._controller._state = DeviceState.ENABLED
        logger.info("使能恢复完成，去起点")
        QTimer.singleShot(300, self._go_start_point)

    def _on_udp_msg(self, msg: str):
        self._udp_label.setText(msg)
        stripped = msg.strip()
        navigation_commands = {
            "l": self._go_prev_point,
            "r": self._go_next_point,
            "h": self._go_start_point,
        }
        handler = navigation_commands.get(stripped.lower())
        if handler:
            handler()
            return

        # 数字指令按点位序号移动，例如 "1" 对应第一个点位。
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
        # 如果电机因到达点位而停止使能，先重新使能再移动
        if self._motor_disabled_after_arrival:
            self._pending_move_mm = mm
            self._motor_disabled_after_arrival = False
            logger.info(f"电机未使能，先重新使能，目标={mm}mm")
            # 完整CiA 402使能序列
            self._controller._control_word = 0x0000
            self._client.write_raw(0x6040, 0x0000)
            QTimer.singleShot(100, lambda: self._client.write_raw(0x6040, 0x0006))
            QTimer.singleShot(200, lambda: self._client.write_raw(0x6040, 0x0007))
            QTimer.singleShot(300, lambda: self._client.write_raw(0x6040, 0x000F))
            QTimer.singleShot(400, self._execute_pending_move)
            return
        self._do_move(mm)

    def _execute_pending_move(self):
        """重新使能完成后，执行挂起的移动指令"""
        if self._pending_move_mm is None:
            return
        mm = self._pending_move_mm
        self._pending_move_mm = None
        self._controller._control_word = 0x000F
        self._controller._state = DeviceState.ENABLED
        logger.info(f"重新使能完成，执行移动到 {mm}mm")
        self._do_move(mm)

    def _do_move(self, mm: float):
        """实际执行位置移动"""
        pulse = int(mm * self._cfg.pulse_per_mm)
        logger.info(f"移动到 {mm}mm (pulse={pulse}), 速度={self._cfg.move_speed}, 当前模式={self._controller.current_mode}")
        # 保持使能(0x000F)，清除 bit4 和暂停位，确保后续上升沿有效
        self._controller._control_word = 0x000F & ~(1 << 4) & ~(1 << 8)
        self._client.write_raw(0x6040, self._controller._control_word & 0xFFFF)
        # 仅在非位置模式时切换，避免中断正在执行的运动
        if self._controller.current_mode != OperationMode.POSITION:
            self._controller.set_mode(OperationMode.POSITION)
        QTimer.singleShot(200, lambda: self._controller.start_position_move(
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
            self._cur_pt_label.setText(pt["name"])
            self._refresh_point_list()

    def _homing_cw(self):
        self._auto_cruise_running = False
        self._target_pos_mm = None
        self._pending_move_mm = None
        self._motor_disabled_after_arrival = False
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
        self._pending_move_mm = None
        self._motor_disabled_after_arrival = False
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
        self._motor_disabled_after_arrival = False  # 停止时清除标志
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

    def _format_parameter_value(self, key: str, value: float) -> str:
        """按参数类型格式化输入框中的数值。"""
        integer = self._parameter_specs[key][4]
        return str(int(round(value))) if integer else f"{value:.1f}"

    def _parameter_label_text(self, key: str, value: float | None = None) -> str:
        """为速度参数附加实时换算后的每分钟转速。"""
        label_text = self._parameter_specs[key][0]
        if key not in ("move_speed", "homing_speed"):
            return label_text
        if value is None:
            return f"{label_text} (-- 转/分)"
        rpm = round(float(value) * 60)
        return f"{label_text} ({rpm} 转/分)"

    def _update_speed_parameter_label(self, key: str, text: str):
        """输入或步进调节速度时，同步更新 rpm 显示。"""
        try:
            value = float(text)
        except ValueError:
            value = None
        self._parameter_labels[key].setText(
            self._parameter_label_text(key, value)
        )

    def _normalize_parameter_value(self, key: str, value: float) -> float | int:
        """将参数限制在驱动器可接受范围内。"""
        _label, _default, minimum, maximum, integer = self._parameter_specs[key]
        value = max(minimum, min(maximum, value))
        return int(round(value)) if integer else round(value, 1)

    def _adjust_parameter(self, key: str, delta: float):
        """按指定步长调节运动参数。"""
        input_widget = self._parameter_inputs[key]
        try:
            value = float(input_widget.text()) + delta
        except ValueError:
            value = float(getattr(self._cfg, key)) + delta
        value = self._normalize_parameter_value(key, value)
        input_widget.setText(self._format_parameter_value(key, value))

    def _save_parameters(self):
        """校验并保存全部运动参数到 config.json。"""
        values = {}
        for key, input_widget in self._parameter_inputs.items():
            try:
                value = float(input_widget.text())
            except ValueError:
                input_widget.setFocus()
                self._parameter_save_btn.setText("输入有误")
                QTimer.singleShot(
                    1500,
                    lambda: self._parameter_save_btn.setText("保存运动参数"),
                )
                return
            values[key] = self._normalize_parameter_value(key, value)
            input_widget.setText(self._format_parameter_value(key, values[key]))

        self._cfg.move_speed = values["move_speed"]
        self._cfg.homing_speed = values["homing_speed"]
        self._cfg.move_accel = values["move_accel"]
        self._cfg.move_decel = values["move_decel"]
        self._parameter_save_btn.setText("已保存")
        QTimer.singleShot(
            1500,
            lambda: self._parameter_save_btn.setText("保存运动参数"),
        )

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
        colors = {"已完成": "#188038", "回零进行中": "#b06000", "未完成": "#5f6368"}
        color = colors.get(self._homing_state, "#5f6368")
        self._homing_status_label.setText(f"回零: {self._homing_state}")
        self._homing_status_label.setStyleSheet(f"font-size: 14px; color: {color}; font-weight: 400;")

    def _apply_theme(self):
        """应用浅色主题"""
        self.setStyleSheet(get_stylesheet())

    def _on_toggle_auto_init(self, checked: bool):
        self._cfg.toggle_auto_init = checked

    def _on_toggle_broadcast(self, checked: bool):
        self._cfg.toggle_broadcast = checked

    def _on_toggle_start_minimized(self, checked: bool):
        self._cfg.toggle_start_minimized = checked

    def _on_toggle_disable_on_arrival(self, checked: bool):
        self._cfg.toggle_disable_on_arrival = checked

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
                dot.setStyleSheet("color: #1a73e8; font-size: 14px;")
                dot.setFixedWidth(16)
                h.addWidget(dot)

            if is_editing:
                name_lbl = QLabel(f"{pt['name']}:")
                name_lbl.setStyleSheet("color: #3c4043; font-weight: 400;")
                h.addWidget(name_lbl)
                edit_input = QLineEdit(str(int(pt['position_mm'])))
                edit_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
                edit_input.setFixedWidth(80)
                h.addWidget(edit_input)
                self._active_edit_input = edit_input
            else:
                label = QLabel(f"{pt['name']}: {pt['position_mm']:.0f} mm")
                if is_current:
                    label.setStyleSheet("color: #0b57d0; font-weight: 400;")
                h.addWidget(label)

            h.addStretch()
            go_btn = QPushButton("Go")
            go_btn.setFixedSize(44, 28)
            go_btn.setProperty("class", "primary-small")
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
            self._cur_pt_label.setText(pt["name"])

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
        self._tray_icon.hide()
        # 清除控制字，确保电机回到干净状态
        self._controller._control_word = 0x0000
        self._client.write_raw(0x6040, 0x0000)
        if self._controller.is_enabled:
            self._controller.disable()
        self._client.shutdown()
        event.accept()
        QApplication.instance().quit()

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
