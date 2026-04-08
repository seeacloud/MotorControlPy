"""数据记录与CSV导出"""

import csv
import time
from collections import deque
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal

from config import RECORDER_BUFFER_SIZE


class DataRecorder(QObject):
    """缓存时间戳数据并支持CSV导出。"""

    buffer_updated = pyqtSignal(int)  # 当前缓冲区大小

    def __init__(self, max_size: int = RECORDER_BUFFER_SIZE, parent=None):
        super().__init__(parent)
        self._buffer: deque[tuple] = deque(maxlen=max_size)
        self._recording = False

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def count(self) -> int:
        return len(self._buffer)

    def start(self):
        self._recording = True

    def stop(self):
        self._recording = False

    def clear(self):
        self._buffer.clear()
        self.buffer_updated.emit(0)

    def add_sample(self, timestamp: float, position: int, speed: int, status: int = 0):
        if not self._recording:
            return
        self._buffer.append((timestamp, position, speed, status))
        self.buffer_updated.emit(len(self._buffer))

    def export_csv(self, filepath: str) -> int:
        """导出为CSV文件，返回导出的记录数。"""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        count = 0
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["时间戳", "时间(s)", "位置(pulse)", "速度(rps/min)", "状态字"])

            if self._buffer:
                t0 = self._buffer[0][0]
                for ts, pos, spd, status in self._buffer:
                    writer.writerow([
                        f"{ts:.3f}",
                        f"{ts - t0:.3f}",
                        pos,
                        spd,
                        f"0x{status:04X}",
                    ])
                    count += 1

        return count
