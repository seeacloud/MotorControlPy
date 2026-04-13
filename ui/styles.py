"""应用样式表 + 自定义控件 — Airbnb UI Style"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen


# === Airbnb 颜色常量 ===
RAUSCH_RED = "#ff385c"
RAUSCH_DARK = "#e00b41"
TEXT_PRIMARY = "#222222"
TEXT_SECONDARY = "#6a6a6a"
TEXT_DISABLED = "#929292"
SURFACE_BG = "#ffffff"
SURFACE_SECONDARY = "#f2f2f2"
BORDER = "#c1c1c1"
BORDER_LIGHT = "#dddddd"
GREEN = "#008a05"
ORANGE = "#c77800"
GRAY = "#929292"

STYLESHEET = """
* {
    font-family:  'Microsoft YaHei';
}
QMainWindow {
    background-color: #ffffff;
}

QLabel#title {
    font-size: 28px; font-weight: 700; margin-bottom: 4px;
    color: #222222; letter-spacing: -0.44px;
}
QLabel#pos-display {
    font-size: 28px; font-weight: 600; color: #222222;
}
QLabel#cur-point {
    font-size: 18px; font-weight: 600; color: #222222;
}
QLabel#udp-msg {
    font-size: 14px; color: #6a6a6a;
}
QLabel#status {
    font-size: 16px; font-weight: 500; color: #222222;
}

QPushButton[class="pill"] {
    border: 1px solid #222222; border-radius: 8px; color: #222222;
    background-color: #ffffff; padding: 10px 16px; font-size: 14px;
    font-weight: 500; min-height: 20px;
}
QPushButton[class="pill"]:hover {
    background-color: #f2f2f2;
}
QPushButton[class="pill"]:pressed {
    background-color: #dddddd; color: #222222;
}

QPushButton[class="pill-stop"] {
    border: 2px solid #ff385c; border-radius: 8px; color: #ff385c;
    background-color: #ffffff; padding: 10px 16px; font-size: 14px;
    font-weight: 600; min-height: 20px;
}
QPushButton[class="pill-stop"]:hover {
    background-color: #fff0f3; color: #e00b41;
}
QPushButton[class="pill-stop"]:pressed {
    background-color: #ffe0e6;
}

QPushButton[class="blue-btn"] {
    background-color: #222222; color: #ffffff; border: none; border-radius: 8px;
    padding: 10px 24px; font-size: 14px; font-weight: 500; min-height: 20px;
}
QPushButton[class="blue-btn"]:hover {
    background-color: #ff385c;
}

QPushButton[class="jog-btn"] {
    border: 1px solid #c1c1c1; border-radius: 8px; background-color: #f2f2f2;
    color: #222222; padding: 6px 10px; font-size: 14px; font-weight: 500; min-width: 40px;
}
QPushButton[class="jog-btn"]:hover {
    background-color: #e8e8e8;
}
QPushButton[class="jog-btn"]:pressed {
    background-color: #dddddd;
}

QPushButton[class="point-action"] {
    border: 1px solid #c1c1c1; border-radius: 8px; background-color: #f2f2f2;
    color: #222222; padding: 6px 12px; font-size: 13px; font-weight: 500;
}
QPushButton[class="point-action"]:hover {
    background-color: #e8e8e8;
}

QPushButton[class="point-delete"] {
    border: none; background-color: transparent; color: #929292;
    font-size: 14px; padding: 2px 6px;
}
QPushButton[class="point-delete"]:hover { color: #ff385c; }
QPushButton:focus {
    outline: none;
}

QComboBox {
    padding: 6px 12px; border: 1px solid #c1c1c1; border-radius: 8px;
    background-color: #ffffff; min-height: 20px; color: #222222;
    font-size: 14px;
}

QLineEdit {
    padding: 8px 12px; border: 1px solid #c1c1c1; border-radius: 8px;
    background-color: #ffffff; font-size: 16px; font-weight: 600;
    color: #222222;
}
QLineEdit:focus {
    border: 2px solid #222222;
}

QScrollArea { border: none; background-color: #ffffff; }

QListWidget {
    border: 1px solid #dddddd; border-radius: 20px; background: #ffffff;
    font-size: 14px; color: #222222;
}
QListWidget:focus { outline: none; }
QListWidget::item { padding: 8px 8px; }
QListWidget::item:focus { outline: none; }
QListWidget::item:selected {
    background-color: #f2f2f2; color: #222222;
}
"""


def get_stylesheet() -> str:
    return STYLESHEET


class ToggleSwitch(QWidget):
    """iOS风格开关控件"""
    toggled = pyqtSignal(bool)

    def __init__(self, label: str = "", checked: bool = False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self._label = label
        self._track_w = 44
        self._track_h = 24
        self._knob_r = 10
        self.setFixedHeight(28)
        self.setMinimumWidth(self._track_w + 8 + len(label) * 14)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        self._checked = checked
        self.update()
        self.toggled.emit(self._checked)

    def mousePressEvent(self, event):
        self._checked = not self._checked
        self.update()
        self.toggled.emit(self._checked)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 标签
        if self._label:
            p.setPen(QColor("#333"))
            p.drawText(0, 0, 100, self.height(), Qt.AlignmentFlag.AlignVCenter, self._label)

        x_off = len(self._label) * 9 + 8 if self._label else 0

        # 轨道
        track_rect = QRect(x_off, (self.height() - self._track_h) // 2,
                           self._track_w, self._track_h)
        track_color = QColor(TEXT_PRIMARY) if self._checked else QColor("#dddddd")
        p.setBrush(QBrush(track_color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(track_rect, self._track_h // 2, self._track_h // 2)

        # 旋钮
        knob_x = x_off + self._track_w - self._knob_r * 2 - 2 if self._checked else x_off + 2
        knob_y = (self.height() - self._knob_r * 2) // 2
        p.setBrush(QBrush(QColor("white")))
        p.setPen(QPen(QColor("#ccc"), 0.5))
        p.drawEllipse(knob_x, knob_y, self._knob_r * 2, self._knob_r * 2)
        p.end()
