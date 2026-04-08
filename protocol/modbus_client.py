"""线程安全的 Modbus-RTU 通信客户端"""

import logging
from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot, QMutex, QWaitCondition
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException

from protocol.register_map import RegisterDef, REGISTERS, encode_value, decode_value
from protocol.data_types import split_32bit, combine_32bit

logger = logging.getLogger(__name__)


class ModbusWorker(QObject):
    """在 QThread 中运行的 Modbus 工作线程，独占串口连接。"""

    response_ready = pyqtSignal(str, bool, object)  # (request_id, success, data_or_error)
    connection_changed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._client: ModbusSerialClient | None = None
        self._slave_id = 1
        self._word_order = 0

    @pyqtSlot(str, int, int, int)
    def connect_device(self, port: str, baudrate: int, slave_id: int, timeout_ms: int):
        try:
            self._slave_id = slave_id
            self._client = ModbusSerialClient(
                port=port,
                baudrate=baudrate,
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=timeout_ms / 1000.0,
            )
            if self._client.connect():
                # 读取字序设置
                result = self._client.read_holding_registers(
                    0x6000, count=1, device_id=self._slave_id
                )
                if not result.isError():
                    self._word_order = result.registers[0]
                logger.info(f"已连接 {port}, 从站={slave_id}, 字序={self._word_order}")
                self.connection_changed.emit(True)
            else:
                self.error_occurred.emit(f"无法打开串口 {port}")
                self.connection_changed.emit(False)
        except Exception as e:
            logger.error(f"连接失败: {e}")
            self.error_occurred.emit(str(e))
            self.connection_changed.emit(False)

    @pyqtSlot()
    def disconnect_device(self):
        if self._client:
            self._client.close()
            self._client = None
            logger.info("已断开连接")
        self.connection_changed.emit(False)

    @pyqtSlot(str, int, int)
    def read_registers(self, request_id: str, address: int, count: int):
        if not self._client:
            self.response_ready.emit(request_id, False, "未连接")
            return
        try:
            result = self._client.read_holding_registers(
                address, count=count, device_id=self._slave_id
            )
            if result.isError():
                self.response_ready.emit(request_id, False, str(result))
            else:
                self.response_ready.emit(request_id, True, result.registers)
        except Exception as e:
            logger.error(f"读取寄存器 0x{address:04X} 失败: {e}")
            self.response_ready.emit(request_id, False, str(e))

    @pyqtSlot(str, int, int)
    def write_register(self, request_id: str, address: int, value: int):
        """写单个16位寄存器 (功能码 0x06)"""
        if not self._client:
            self.response_ready.emit(request_id, False, "未连接")
            return
        try:
            result = self._client.write_register(
                address, value, device_id=self._slave_id
            )
            if result.isError():
                self.response_ready.emit(request_id, False, str(result))
            else:
                self.response_ready.emit(request_id, True, None)
        except Exception as e:
            logger.error(f"写寄存器 0x{address:04X} 失败: {e}")
            self.response_ready.emit(request_id, False, str(e))

    @pyqtSlot(str, int, list)
    def write_registers(self, request_id: str, address: int, values: list):
        """写多个寄存器 (功能码 0x10)"""
        if not self._client:
            self.response_ready.emit(request_id, False, "未连接")
            return
        try:
            result = self._client.write_registers(
                address, values, device_id=self._slave_id
            )
            if result.isError():
                self.response_ready.emit(request_id, False, str(result))
            else:
                self.response_ready.emit(request_id, True, None)
        except Exception as e:
            logger.error(f"写多寄存器 0x{address:04X} 失败: {e}")
            self.response_ready.emit(request_id, False, str(e))

    @property
    def word_order(self) -> int:
        return self._word_order


class ModbusClient(QObject):
    """线程安全的 Modbus 客户端门面，供 UI 和业务层使用。"""

    connected = pyqtSignal(bool)
    error = pyqtSignal(str)
    response = pyqtSignal(str, bool, object)  # (request_id, success, data)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = QThread()
        self._worker = ModbusWorker()
        self._worker.moveToThread(self._thread)

        # 转发信号
        self._worker.connection_changed.connect(self.connected)
        self._worker.error_occurred.connect(self.error)
        self._worker.response_ready.connect(self.response)

        self._thread.start()
        self._is_connected = False
        self.connected.connect(self._on_connection_changed)
        self._request_counter = 0

    def _on_connection_changed(self, state: bool):
        self._is_connected = state

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def word_order(self) -> int:
        return self._worker.word_order

    def _next_request_id(self, prefix: str = "") -> str:
        self._request_counter += 1
        return f"{prefix}_{self._request_counter}"

    def connect_device(self, port: str, baudrate: int, slave_id: int, timeout_ms: int = 500):
        from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
        QMetaObject.invokeMethod(
            self._worker, "connect_device", Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, port), Q_ARG(int, baudrate),
            Q_ARG(int, slave_id), Q_ARG(int, timeout_ms),
        )

    def disconnect_device(self):
        from PyQt6.QtCore import QMetaObject, Qt
        QMetaObject.invokeMethod(
            self._worker, "disconnect_device", Qt.ConnectionType.QueuedConnection,
        )

    def read_reg(self, name: str) -> str:
        """读取命名寄存器，返回 request_id"""
        reg = REGISTERS[name]
        rid = self._next_request_id(f"read_{name}")
        from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
        QMetaObject.invokeMethod(
            self._worker, "read_registers", Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, rid), Q_ARG(int, reg.address), Q_ARG(int, reg.reg_count),
        )
        return rid

    def write_reg(self, name: str, actual_value: float) -> str:
        """写入命名寄存器(自动处理缩放和32位拆分)，返回 request_id"""
        reg = REGISTERS[name]
        reg_value = encode_value(reg, actual_value)
        rid = self._next_request_id(f"write_{name}")

        from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
        if reg.is_32bit:
            words = split_32bit(reg_value, reg.is_signed, self.word_order)
            QMetaObject.invokeMethod(
                self._worker, "write_registers", Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, rid), Q_ARG(int, reg.address), Q_ARG(list, words),
            )
        else:
            value = reg_value & 0xFFFF
            QMetaObject.invokeMethod(
                self._worker, "write_register", Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, rid), Q_ARG(int, reg.address), Q_ARG(int, value),
            )
        return rid

    def read_raw(self, address: int, count: int) -> str:
        """读取任意地址寄存器"""
        rid = self._next_request_id(f"raw_read_{address:04X}")
        from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
        QMetaObject.invokeMethod(
            self._worker, "read_registers", Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, rid), Q_ARG(int, address), Q_ARG(int, count),
        )
        return rid

    def write_raw(self, address: int, value: int) -> str:
        """写入任意16位寄存器"""
        rid = self._next_request_id(f"raw_write_{address:04X}")
        from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
        QMetaObject.invokeMethod(
            self._worker, "write_register", Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, rid), Q_ARG(int, address), Q_ARG(int, value),
        )
        return rid

    def write_raw_multi(self, address: int, values: list[int]) -> str:
        """写入多个寄存器"""
        rid = self._next_request_id(f"raw_writem_{address:04X}")
        from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
        QMetaObject.invokeMethod(
            self._worker, "write_registers", Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, rid), Q_ARG(int, address), Q_ARG(list, values),
        )
        return rid

    def decode_response(self, name: str, registers: list[int]) -> float:
        """解码寄存器响应为实际值"""
        reg = REGISTERS[name]
        if reg.is_32bit:
            raw = combine_32bit(registers, reg.is_signed, self.word_order)
        else:
            raw = registers[0]
            if reg.is_signed and raw > 0x7FFF:
                raw -= 0x10000
        return decode_value(reg, raw)

    def shutdown(self):
        """关闭工作线程"""
        if self._is_connected:
            self.disconnect_device()
        self._thread.quit()
        self._thread.wait(3000)
