"""Material Design 风格的应用主题与自定义控件。"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QSize
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen


# Material 3 色彩令牌，针对工业控制界面提高了状态色对比度。
PRIMARY = "#1a73e8"
PRIMARY_DARK = "#0b57d0"
PRIMARY_CONTAINER = "#d3e3fd"
TEXT_PRIMARY = "#3c4043"
TEXT_SECONDARY = "#5f6368"
TEXT_DISABLED = "#9aa0a6"
SURFACE_BG = "#f8fafd"
SURFACE = "#ffffff"
SURFACE_CONTAINER = "#eef2f6"
OUTLINE = "#747775"
OUTLINE_VARIANT = "#c4c7c5"
GREEN = "#188038"
ORANGE = "#b06000"
ERROR = "#b3261e"
GRAY = TEXT_SECONDARY


STYLESHEET = """
* {
    font-family: "Microsoft YaHei UI", "Segoe UI";
    font-size: 14px;
    color: #3c4043;
    letter-spacing: 0px;
}

QMainWindow, QWidget#workspace {
    background-color: #f8fafd;
}

QWidget[class="toggle"] {
    font-size: 12px;
}

QLabel#title {
    color: #3c4043;
    font-size: 26px;
    font-weight: 400;
    padding: 0px;
}

QLabel#status {
    color: #5f6368;
    font-size: 14px;
    font-weight: 400;
}

QFrame#telemetry {
    background-color: #ffffff;
    border: 1px solid #c4c7c5;
    border-radius: 8px;
}

QLabel#data-label {
    color: #5f6368;
    font-size: 12px;
    font-weight: 400;
}

QLabel#pos-display {
    color: #0b57d0;
    font-size: 34px;
    font-weight: 400;
}

QLabel#cur-point {
    color: #3c4043;
    font-size: 18px;
    font-weight: 400;
}

QLabel#udp-msg {
    color: #3c4043;
    font-size: 16px;
    font-weight: 400;
}

QLabel#section-title {
    color: #3c4043;
    font-size: 16px;
    font-weight: 400;
}

QToolButton#section-toggle {
    min-height: 24px;
    padding: 6px 8px;
    color: #3c4043;
    background-color: #ffffff;
    border: 1px solid #bdc1c6;
    border-radius: 6px;
    font-size: 16px;
    font-weight: 400;
    text-align: left;
}
QToolButton#section-toggle:hover {
    color: #3c4043;
    background-color: #e8f0fe;
}
QToolButton#section-toggle:focus {
    border-color: #0b57d0;
}
QToolButton#section-toggle:pressed {
    background-color: #d3e3fd;
}

QLabel#field-label {
    color: #5f6368;
    font-size: 12px;
    font-weight: 400;
}

QFrame#divider {
    min-height: 1px;
    max-height: 1px;
    border: none;
    background-color: #c4c7c5;
}

QPushButton {
    min-height: 24px;
    padding: 9px 16px;
    border: 1px solid #bdc1c6;
    border-radius: 6px;
    background-color: #ffffff;
    color: #3c4043;
    font-size: 14px;
    font-weight: 400;
}

QPushButton[class="primary"] {
    color: #ffffff;
    background-color: #1a73e8;
    border-color: #1a73e8;
}
QPushButton[class="primary"]:hover {
    background-color: #1765cc;
    border-color: #1765cc;
}
QPushButton[class="primary"]:pressed,
QPushButton[class="primary"]:focus {
    background-color: #0b57d0;
    border-color: #0b57d0;
}

QPushButton[class="tonal"] {
    color: #0b57d0;
    background-color: #d3e3fd;
    border-color: #d3e3fd;
}
QPushButton[class="tonal"]:hover {
    background-color: #c2d7f5;
}
QPushButton[class="tonal"]:pressed,
QPushButton[class="tonal"]:focus {
    background-color: #a8c7fa;
    border-color: #0b57d0;
}

QPushButton[class="outlined"] {
    color: #3c4043;
    background-color: #ffffff;
    border-color: #747775;
}
QPushButton[class="outlined"]:hover {
    color: #0b57d0;
    background-color: #f1f6ff;
    border-color: #0b57d0;
}
QPushButton[class="outlined"]:pressed,
QPushButton[class="outlined"]:focus {
    background-color: #d3e3fd;
    border: 2px solid #0b57d0;
}

QPushButton[class="danger"] {
    color: #ffffff;
    background-color: #b3261e;
    border-color: #b3261e;
}
QPushButton[class="danger"]:hover {
    background-color: #8c1d18;
    border-color: #8c1d18;
}
QPushButton[class="danger"]:pressed,
QPushButton[class="danger"]:focus {
    background-color: #711511;
    border-color: #711511;
}

QPushButton[class="step"] {
    min-width: 40px;
    min-height: 22px;
    padding: 6px 9px;
    color: #3c4043;
    background-color: #e8eaed;
    border-color: #e8eaed;
    font-weight: 400;
}
QPushButton[class="step"]:hover {
    color: #0b57d0;
    background-color: #d3e3fd;
}
QPushButton[class="step"]:pressed,
QPushButton[class="step"]:focus {
    background-color: #a8c7fa;
    border-color: #0b57d0;
}

QPushButton[class="parameter-step"] {
    min-width: 32px;
    max-width: 34px;
    min-height: 28px;
    max-height: 30px;
    padding: 0px;
    color: #3c4043;
    background-color: #e8eaed;
    border-color: #e8eaed;
    border-radius: 5px;
    font-size: 12px;
    font-weight: 400;
}
QPushButton[class="parameter-step"]:hover {
    color: #0b57d0;
    background-color: #d3e3fd;
}
QPushButton[class="parameter-step"]:pressed,
QPushButton[class="parameter-step"]:focus {
    background-color: #a8c7fa;
    border-color: #0b57d0;
}

QPushButton[class="primary-small"] {
    min-height: 18px;
    padding: 5px 12px;
    color: #ffffff;
    background-color: #1a73e8;
    border-color: #1a73e8;
    font-size: 13px;
}
QPushButton[class="primary-small"]:hover {
    background-color: #1765cc;
}
QPushButton[class="primary-small"]:pressed,
QPushButton[class="primary-small"]:focus {
    background-color: #0b57d0;
    border-color: #0b57d0;
}

QPushButton[class="text"] {
    min-height: 18px;
    padding: 6px 10px;
    color: #0b57d0;
    background-color: transparent;
    border-color: transparent;
}
QPushButton[class="text"]:hover {
    background-color: #d3e3fd;
}
QPushButton[class="text"]:focus {
    border-color: #0b57d0;
}

QPushButton[class="danger-text"] {
    min-height: 18px;
    padding: 6px 10px;
    color: #b3261e;
    background-color: transparent;
    border-color: transparent;
}
QPushButton[class="danger-text"]:hover {
    background-color: #f9dedc;
}
QPushButton[class="danger-text"]:focus {
    border-color: #b3261e;
}

QPushButton[class="primary"],
QPushButton[class="tonal"],
QPushButton[class="outlined"],
QPushButton[class="step"],
QPushButton[class="parameter-step"],
QPushButton[class="primary-small"],
QPushButton[class="text"],
QPushButton[class="danger-text"] {
    color: #3c4043;
    background-color: #ffffff;
    border: 1px solid #bdc1c6;
}

QPushButton[class="primary"]:hover,
QPushButton[class="tonal"]:hover,
QPushButton[class="outlined"]:hover,
QPushButton[class="step"]:hover,
QPushButton[class="parameter-step"]:hover,
QPushButton[class="primary-small"]:hover,
QPushButton[class="text"]:hover,
QPushButton[class="danger-text"]:hover,
QPushButton:hover {
    color: #3c4043;
    background-color: #e8f0fe;
    border: 1px solid #bdc1c6;
}

QPushButton[class="primary"]:pressed,
QPushButton[class="tonal"]:pressed,
QPushButton[class="outlined"]:pressed,
QPushButton[class="step"]:pressed,
QPushButton[class="parameter-step"]:pressed,
QPushButton[class="primary-small"]:pressed,
QPushButton[class="text"]:pressed,
QPushButton[class="danger-text"]:pressed {
    color: #3c4043;
    background-color: #d3e3fd;
    border: 1px solid #0b57d0;
}

QPushButton[class="primary"]:focus,
QPushButton[class="tonal"]:focus,
QPushButton[class="outlined"]:focus,
QPushButton[class="step"]:focus,
QPushButton[class="parameter-step"]:focus,
QPushButton[class="primary-small"]:focus,
QPushButton[class="text"]:focus,
QPushButton[class="danger-text"]:focus {
    color: #3c4043;
    background-color: #ffffff;
    border: 1px solid #0b57d0;
}

QPushButton[class="danger"] {
    color: #ffffff;
    background-color: #b3261e;
    border: 1px solid #b3261e;
}
QPushButton[class="danger"]:hover {
    color: #ffffff;
    background-color: #8c1d18;
    border: 1px solid #8c1d18;
}
QPushButton[class="danger"]:pressed,
QPushButton[class="danger"]:focus {
    color: #ffffff;
    background-color: #711511;
    border: 1px solid #711511;
}

QPushButton:disabled {
    color: #9aa0a6;
    background-color: #e8eaed;
    border-color: #e8eaed;
}

QLineEdit {
    min-height: 24px;
    padding: 7px 11px;
    color: #3c4043;
    background-color: #ffffff;
    border: 1px solid #747775;
    border-radius: 6px;
    selection-background-color: #a8c7fa;
    font-size: 15px;
    font-weight: 400;
}
QLineEdit:hover {
    border-color: #5f6368;
}
QLineEdit:focus {
    padding: 6px 10px;
    border: 2px solid #1a73e8;
}
QLineEdit:disabled {
    color: #9aa0a6;
    background-color: #eef2f6;
    border-color: #c4c7c5;
}

QListWidget {
    color: #3c4043;
    background-color: #ffffff;
    border: 1px solid #c4c7c5;
    border-radius: 8px;
    outline: none;
}
QListWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #e1e3e1;
}
QListWidget::item:hover {
    background-color: #f1f6ff;
}
QListWidget::item:selected {
    color: #0b57d0;
    background-color: #d3e3fd;
}

QScrollBar:vertical {
    width: 10px;
    margin: 4px 2px;
    background: transparent;
}
QScrollBar::handle:vertical {
    min-height: 32px;
    background: #c4c7c5;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #9aa0a6;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    height: 0px;
    background: transparent;
}

QMenu {
    padding: 6px;
    color: #3c4043;
    background-color: #ffffff;
    border: 1px solid #c4c7c5;
    border-radius: 6px;
}
QMenu::item {
    padding: 8px 20px;
    border-radius: 4px;
}
QMenu::item:selected {
    color: #0b57d0;
    background-color: #d3e3fd;
}

QToolTip {
    padding: 5px 8px;
    color: #ffffff;
    background-color: #3c4043;
    border: none;
    border-radius: 4px;
}
"""


def get_stylesheet() -> str:
    return STYLESHEET


class ToggleSwitch(QWidget):
    """支持鼠标和键盘操作的 Material 风格开关。"""

    toggled = pyqtSignal(bool)

    def __init__(self, label: str = "", checked: bool = False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self._label = label.strip()
        self._track_w = 36
        self._track_h = 20
        self._knob_d = 16
        self.setProperty("class", "toggle")
        compact_font = self.font()
        compact_font.setPixelSize(12)
        self.setFont(compact_font)
        self.setFixedHeight(26)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(self._label)
        self.setMinimumWidth(self.sizeHint().width())

    def sizeHint(self) -> QSize:
        label_width = self.fontMetrics().horizontalAdvance(self._label)
        gap = 6 if self._label else 0
        return QSize(label_width + gap + self._track_w, 26)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        checked = bool(checked)
        if self._checked == checked:
            return
        self._checked = checked
        self.update()
        self.toggled.emit(self._checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.setChecked(not self._checked)
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        label_width = painter.fontMetrics().horizontalAdvance(self._label)
        if self._label:
            painter.setPen(QColor(TEXT_PRIMARY))
            painter.drawText(
                QRect(0, 0, label_width, self.height()),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                self._label,
            )

        track_x = label_width + (6 if self._label else 0)
        track_y = (self.height() - self._track_h) // 2
        track_rect = QRect(track_x, track_y, self._track_w, self._track_h)

        if self.hasFocus():
            focus_rect = track_rect.adjusted(-3, -3, 3, 3)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#a8c7fa"), 2))
            painter.drawRoundedRect(focus_rect, 16, 16)

        track_color = QColor(PRIMARY) if self._checked else QColor(OUTLINE)
        painter.setBrush(QBrush(track_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(track_rect, self._track_h // 2, self._track_h // 2)

        knob_x = (
            track_x + self._track_w - self._knob_d - 3
            if self._checked
            else track_x + 3
        )
        knob_y = (self.height() - self._knob_d) // 2
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawEllipse(knob_x, knob_y, self._knob_d, self._knob_d)
        painter.end()
