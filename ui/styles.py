"""应用样式表 + 自定义控件"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QPropertyAnimation, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen


STYLESHEET = """
QMainWindow {
    background-color: #FFFFFF;
}

QPushButton.pill {
    border: 1px solid #2196F3;
    border-radius: 20px;
    color: #2196F3;
    background-color: white;
    padding: 10px 8px;
    font-size: 13px;
    min-height: 20px;
}
QPushButton.pill:hover {
    background-color: #E3F2FD;
}
QPushButton.pill:pressed {
    background-color: #BBDEFB;
}

QPushButton.pill-stop {
    border: 1px solid #F44336;
    border-radius: 20px;
    color: #F44336;
    background-color: white;
    padding: 10px 8px;
    font-size: 13px;
    min-height: 20px;
}
QPushButton.pill-stop:hover {
    background-color: #FFEBEE;
}

QPushButton.blue-btn {
    background-color: #2196F3;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 10px 24px;
    font-size: 14px;
    min-height: 20px;
}
QPushButton.blue-btn:hover {
    background-color: #1976D2;
}

QPushButton.blue-btn-large {
    background-color: #2196F3;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 14px 32px;
    font-size: 16px;
    min-height: 30px;
}
QPushButton.blue-btn-large:hover {
    background-color: #1976D2;
}

QPushButton.jog-btn {
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    background-color: #FAFAFA;
    color: #333;
    padding: 6px 10px;
    font-size: 13px;
    min-width: 40px;
}
QPushButton.jog-btn:hover {
    background-color: #EEEEEE;
}
QPushButton.jog-btn:pressed {
    background-color: #E0E0E0;
}

QPushButton.point-action {
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    background-color: #FAFAFA;
    color: #666;
    padding: 4px 10px;
    font-size: 12px;
}
QPushButton.point-action:hover {
    background-color: #EEEEEE;
}

QPushButton.point-delete {
    border: none;
    background-color: transparent;
    color: #999;
    font-size: 14px;
    padding: 2px 6px;
}
QPushButton.point-delete:hover {
    color: #F44336;
}

QComboBox {
    padding: 6px 12px;
    border: 1px solid #E0E0E0;
    border-radius: 6px;
    background-color: #FAFAFA;
    min-height: 20px;
}

QLineEdit {
    padding: 8px 12px;
    border: 1px solid #E0E0E0;
    border-radius: 6px;
    background-color: white;
    font-size: 16px;
    font-weight: bold;
}

QScrollArea {
    border: none;
    background-color: white;
}
"""


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
        track_color = QColor("#2196F3") if self._checked else QColor("#E0E0E0")
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
