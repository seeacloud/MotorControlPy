"""多段位置运动执行器"""

import logging
from dataclasses import dataclass
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from core.motor_controller import MotorController

logger = logging.getLogger(__name__)


@dataclass
class SegmentDef:
    target_position: int
    speed: float        # rps
    acceleration: float  # rps/s²
    deceleration: float  # rps/s²
    dwell_ms: int = 0   # 停留时间(毫秒)
    absolute: bool = True


class SegmentMotionExecutor(QObject):
    """按顺序执行多段位置运动。"""

    segment_started = pyqtSignal(int)     # 段索引
    segment_completed = pyqtSignal(int)
    all_completed = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, controller: MotorController, parent=None):
        super().__init__(parent)
        self._controller = controller
        self._segments: list[SegmentDef] = []
        self._current_index = -1
        self._running = False

        self._dwell_timer = QTimer(self)
        self._dwell_timer.setSingleShot(True)
        self._dwell_timer.timeout.connect(self._on_dwell_done)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def total_segments(self) -> int:
        return len(self._segments)

    def load_segments(self, segments: list[SegmentDef]):
        self._segments = list(segments)
        self._current_index = -1

    def start(self):
        if not self._segments:
            self.error_occurred.emit("没有运动段")
            return
        self._running = True
        self._current_index = -1
        self._start_next()

    def stop(self):
        self._running = False
        self._dwell_timer.stop()
        self._controller.pause()

    def _start_next(self):
        self._current_index += 1
        if self._current_index >= len(self._segments):
            self._running = False
            self.all_completed.emit()
            return

        seg = self._segments[self._current_index]
        self.segment_started.emit(self._current_index)
        self._controller.start_position_move(
            target=seg.target_position,
            speed=seg.speed,
            accel=seg.acceleration,
            decel=seg.deceleration,
            absolute=seg.absolute,
        )

    def on_motion_complete(self):
        """由外部(轮询服务检测到位完成)调用"""
        if not self._running:
            return

        self.segment_completed.emit(self._current_index)
        seg = self._segments[self._current_index]

        if seg.dwell_ms > 0:
            self._dwell_timer.start(seg.dwell_ms)
        else:
            self._start_next()

    def _on_dwell_done(self):
        if self._running:
            self._start_next()
