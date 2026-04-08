"""JMC伺服电机控制器 - 状态机与控制字管理"""

import logging
from enum import IntEnum
from PyQt6.QtCore import QObject, pyqtSignal

from protocol.modbus_client import ModbusClient
from protocol.register_map import OperationMode

logger = logging.getLogger(__name__)


class DeviceState(IntEnum):
    DISCONNECTED = 0
    NOT_READY = 1
    READY = 2
    SWITCHED_ON = 3
    ENABLED = 4
    FAULT = 5
    QUICK_STOP = 6


class MotorController(QObject):
    """封装JMC伺服驱动器的状态机和高级控制操作。"""

    state_changed = pyqtSignal(int)       # DeviceState
    mode_changed = pyqtSignal(int)        # OperationMode
    command_done = pyqtSignal(str, bool, str)  # (command_name, success, message)

    def __init__(self, client: ModbusClient, parent=None):
        super().__init__(parent)
        self._client = client
        self._control_word = 0x0000
        self._state = DeviceState.DISCONNECTED
        self._current_mode = 0
        self._pending_commands: dict[str, str] = {}  # request_id -> command_name

        self._client.response.connect(self._on_response)
        self._client.connected.connect(self._on_connection)

    @property
    def state(self) -> DeviceState:
        return self._state

    @property
    def current_mode(self) -> int:
        return self._current_mode

    @property
    def is_enabled(self) -> bool:
        return self._state == DeviceState.ENABLED

    # === 状态机控制 ===

    def enable(self):
        """执行上电使能序列: 0x0001 -> 0x0003 -> 0x000F"""
        self._write_control_word(0x0001, "enable_step1")

    def _continue_enable(self, step: str):
        if step == "enable_step1":
            self._write_control_word(0x0003, "enable_step2")
        elif step == "enable_step2":
            self._write_control_word(0x000F, "enable_step3")
        elif step == "enable_step3":
            self._control_word = 0x000F
            self._state = DeviceState.ENABLED
            self.state_changed.emit(self._state)
            self.command_done.emit("enable", True, "电机已使能")

    def disable(self):
        """禁用电机"""
        self._write_control_word(0x0000, "disable")

    def emergency_stop(self):
        """紧急停止 - 直接写0"""
        self._control_word = 0x0000
        rid = self._client.write_raw(0x6040, 0x0000)
        self._pending_commands[rid] = "emergency_stop"

    def fault_reset(self):
        """故障复位 - bit7上升沿"""
        self._set_bit(7, True, "fault_reset_set")

    # === 模式控制 ===

    def set_mode(self, mode: OperationMode):
        """设置操作模式"""
        rid = self._client.write_reg("operation_mode", mode)
        self._pending_commands[rid] = f"set_mode_{mode}"
        self._current_mode = mode

    # === 位置模式 ===

    def start_position_move(self, target: int, speed: float, accel: float,
                            decel: float, absolute: bool = True):
        """启动位置运动"""
        # 写入参数
        self._client.write_reg("target_position", target)
        self._client.write_reg("target_speed", speed)
        self._client.write_reg("acceleration", accel)
        self._client.write_reg("deceleration", decel)

        # 设置绝对/相对位
        if absolute:
            self._control_word &= ~(1 << 6)  # bit6=0 绝对
        else:
            self._control_word |= (1 << 6)   # bit6=1 相对

        # bit4上升沿触发
        cw = self._control_word & ~(1 << 4)
        rid1 = self._client.write_raw(0x6040, cw & 0xFFFF)
        cw |= (1 << 4)
        self._control_word = cw
        rid2 = self._client.write_raw(0x6040, cw & 0xFFFF)
        self._pending_commands[rid2] = "position_start"

    # === 速度模式 ===

    def start_speed_move(self, speed: float, accel: float, decel: float):
        """启动速度运动"""
        self._client.write_reg("target_speed", speed)
        self._client.write_reg("acceleration", accel)
        self._client.write_reg("deceleration", decel)
        self._write_control_word(0x000F, "speed_start")

    def stop_speed(self):
        """速度模式暂停"""
        self._write_control_word(0x010F, "speed_stop")

    # === 回零模式 ===

    def start_homing(self, method: int, speed: int, accel: float,
                     offset: int = 0, offset_speed: int = 0):
        """启动回零运动"""
        self._client.write_reg("homing_method", method)
        self._client.write_reg("homing_speed", speed)
        self._client.write_reg("homing_accel", accel)
        if offset:
            self._client.write_reg("home_offset", offset)
        if offset_speed:
            self._client.write_reg("homing_offset_speed", offset_speed)

        # bit4上升沿触发
        cw = self._control_word & ~(1 << 4)
        self._client.write_raw(0x6040, cw & 0xFFFF)
        cw |= (1 << 4)
        self._control_word = cw
        rid = self._client.write_raw(0x6040, cw & 0xFFFF)
        self._pending_commands[rid] = "homing_start"

    # === 暂停/恢复 ===

    def pause(self):
        """暂停运动 - bit8置1"""
        self._set_bit(8, True, "pause")

    def resume(self):
        """恢复运动 - bit8清0"""
        self._set_bit(8, False, "resume")

    # === 内部方法 ===

    def _write_control_word(self, value: int, cmd_name: str):
        rid = self._client.write_raw(0x6040, value & 0xFFFF)
        self._pending_commands[rid] = cmd_name

    def _set_bit(self, bit: int, value: bool, cmd_name: str):
        if value:
            self._control_word |= (1 << bit)
        else:
            self._control_word &= ~(1 << bit)
        self._write_control_word(self._control_word, cmd_name)

    def _on_response(self, request_id: str, success: bool, data):
        cmd = self._pending_commands.pop(request_id, None)
        if cmd is None:
            return

        if not success:
            logger.error(f"命令 {cmd} 失败: {data}")
            self.command_done.emit(cmd, False, str(data))
            return

        # 使能序列自动推进
        if cmd.startswith("enable_step"):
            self._continue_enable(cmd)
        elif cmd == "disable":
            self._control_word = 0x0000
            self._state = DeviceState.READY
            self.state_changed.emit(self._state)
            self.command_done.emit("disable", True, "电机已禁用")
        elif cmd == "emergency_stop":
            self._state = DeviceState.NOT_READY
            self.state_changed.emit(self._state)
            self.command_done.emit("emergency_stop", True, "紧急停止")
        elif cmd.startswith("set_mode_"):
            mode = int(cmd.split("_")[-1])
            self.mode_changed.emit(mode)
            self.command_done.emit("set_mode", True, f"模式已切换")
        elif cmd == "fault_reset_set":
            # 复位后清除bit7
            self._set_bit(7, False, "fault_reset_clear")
        elif cmd == "fault_reset_clear":
            self.command_done.emit("fault_reset", True, "故障已复位")
        else:
            self.command_done.emit(cmd, True, "")

    def _on_connection(self, connected: bool):
        if connected:
            self._state = DeviceState.NOT_READY
        else:
            self._state = DeviceState.DISCONNECTED
            self._control_word = 0x0000
        self.state_changed.emit(self._state)

    def update_state_from_status(self, status_word: int):
        """根据状态字更新设备状态(由轮询服务调用)"""
        if status_word & (1 << 3):  # bit3 故障
            self._state = DeviceState.FAULT
        elif status_word & (1 << 2):  # bit2 操作使能
            self._state = DeviceState.ENABLED
        elif status_word & (1 << 1):  # bit1 初始化完成
            self._state = DeviceState.READY
        else:
            self._state = DeviceState.NOT_READY
        self.state_changed.emit(self._state)
