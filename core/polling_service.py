"""双速率轮询服务 - 驱动实时数据流"""

import time
import logging
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from protocol.modbus_client import ModbusClient
from protocol.data_types import combine_32bit

logger = logging.getLogger(__name__)


class PollingService(QObject):
    """周期性读取伺服驱动器状态和运动数据。

    快速轮询(100ms): 位置 + 速度 -> 波形显示
    慢速轮询(500ms): 状态字 + 错误寄存器 -> 状态监控
    """

    position_updated = pyqtSignal(float, int)    # (timestamp, position)
    speed_updated = pyqtSignal(float, int)       # (timestamp, speed)
    status_updated = pyqtSignal(int)             # raw status word
    error_updated = pyqtSignal(int)              # raw error register
    mode_updated = pyqtSignal(int)               # current mode

    def __init__(self, client: ModbusClient, parent=None):
        super().__init__(parent)
        self._client = client
        self._running = False

        self._fast_timer = QTimer(self)
        self._fast_timer.timeout.connect(self._fast_poll)
        self._slow_timer = QTimer(self)
        self._slow_timer.timeout.connect(self._slow_poll)

        self._client.response.connect(self._on_response)

        # 待处理的请求ID
        self._fast_rid: str | None = None
        self._slow_rid: str | None = None

    def start(self, fast_ms: int = 100, slow_ms: int = 500):
        self._running = True
        self._fast_timer.start(fast_ms)
        self._slow_timer.start(slow_ms)
        logger.info(f"轮询已启动: 快速={fast_ms}ms, 慢速={slow_ms}ms")

    def stop(self):
        self._running = False
        self._fast_timer.stop()
        self._slow_timer.stop()
        self._fast_rid = None
        self._slow_rid = None
        logger.info("轮询已停止")

    @property
    def is_running(self) -> bool:
        return self._running

    def _fast_poll(self):
        """快速轮询: 批量读取位置(0x6064, 2reg) + 速度(0x606C, 2reg)
        地址间隔: 0x606C - 0x6064 = 8, 加上速度的2个 = 共10个寄存器"""
        if self._fast_rid is not None:
            return  # 上一次还没返回，跳过
        self._fast_rid = self._client.read_raw(0x6064, 10)

    def _slow_poll(self):
        """慢速轮询: 读取状态字(0x6041, 1reg)"""
        if self._slow_rid is not None:
            return
        self._slow_rid = self._client.read_raw(0x6041, 1)
        # 同时读错误寄存器和模式
        self._error_rid = self._client.read_raw(0x1001, 1)
        self._mode_rid = self._client.read_raw(0x6061, 1)

    def _on_response(self, request_id: str, success: bool, data):
        if not self._running:
            return

        ts = time.time()

        if request_id == self._fast_rid:
            self._fast_rid = None
            if success and isinstance(data, list) and len(data) >= 10:
                word_order = self._client.word_order
                position = combine_32bit(data[0:2], signed=True, word_order=word_order)
                speed = combine_32bit(data[8:10], signed=True, word_order=word_order)
                self.position_updated.emit(ts, position)
                self.speed_updated.emit(ts, speed)

        elif request_id == self._slow_rid:
            self._slow_rid = None
            if success and isinstance(data, list) and len(data) >= 1:
                self.status_updated.emit(data[0])

        elif hasattr(self, '_error_rid') and request_id == self._error_rid:
            self._error_rid = None
            if success and isinstance(data, list) and len(data) >= 1:
                self.error_updated.emit(data[0])

        elif hasattr(self, '_mode_rid') and request_id == self._mode_rid:
            self._mode_rid = None
            if success and isinstance(data, list) and len(data) >= 1:
                val = data[0]
                if val > 0x7FFF:
                    val -= 0x10000
                self.mode_updated.emit(val)
