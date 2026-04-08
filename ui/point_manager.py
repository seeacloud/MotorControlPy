"""点位列表管理器 - 通过config.json持久化"""

from PyQt6.QtCore import QObject, pyqtSignal
from config import AppConfig


class PointManager(QObject):
    """管理命名点位列表，保存到config.json的points字段。"""

    points_changed = pyqtSignal()

    def __init__(self, cfg: AppConfig, parent=None):
        super().__init__(parent)
        self._cfg = cfg
        self._points: list[dict] = list(cfg.points)

    @property
    def count(self) -> int:
        return len(self._points)

    def get_all(self) -> list[dict]:
        return list(self._points)

    def get(self, index: int) -> dict | None:
        if 0 <= index < len(self._points):
            return self._points[index]
        return None

    def add(self, position_mm: float):
        name = self._next_name()
        self._points.append({"name": name, "position_mm": round(position_mm, 1)})
        self._save_and_notify()

    def remove(self, index: int):
        if 0 <= index < len(self._points):
            self._points.pop(index)
            self._save_and_notify()

    def clear(self):
        self._points.clear()
        self._save_and_notify()

    def update_position(self, index: int, position_mm: float):
        if 0 <= index < len(self._points):
            self._points[index]["position_mm"] = round(position_mm, 1)
            self._save_and_notify()

    def _save_and_notify(self):
        self._cfg.points = self._points
        self.points_changed.emit()

    def _next_name(self) -> str:
        num = len(self._points) + 1
        return f"P-{num:02d}"
