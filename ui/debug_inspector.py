"""Qt Widget Inspector / 调试面板 — F12 唤出"""

from PyQt6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator,
    QTableWidget, QTableWidgetItem, QPlainTextEdit,
    QPushButton, QLineEdit, QLabel, QApplication, QHeaderView,
)
from PyQt6.QtCore import Qt, QObject, QEvent, QPoint, pyqtSignal, QRect
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QCursor

try:
    from PyQt6 import sip
except ImportError:
    import sip  # type: ignore

from ui.styles import get_stylesheet

# === Inspector 自有深色主题（不受 App 样式影响）===
INSPECTOR_STYLE = """
DebugInspector, DebugInspector * {
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    color: #d4d4d4;
    background-color: #1e1e1e;
}
DebugInspector QTreeWidget {
    background-color: #252526;
    border: 1px solid #3c3c3c;
    color: #d4d4d4;
}
DebugInspector QTreeWidget::item:selected {
    background-color: #094771;
    color: #ffffff;
}
DebugInspector QTreeWidget::item:hover {
    background-color: #2a2d2e;
}
DebugInspector QTableWidget {
    background-color: #252526;
    border: 1px solid #3c3c3c;
    color: #d4d4d4;
    gridline-color: #3c3c3c;
}
DebugInspector QTableWidget::item {
    padding: 2px 4px;
}
DebugInspector QTableWidget::item:selected {
    background-color: #094771;
}
DebugInspector QHeaderView::section {
    background-color: #333333;
    color: #d4d4d4;
    border: 1px solid #3c3c3c;
    padding: 3px 6px;
    font-weight: 600;
}
DebugInspector QPlainTextEdit {
    background-color: #1e1e1e;
    border: 1px solid #3c3c3c;
    color: #ce9178;
    selection-background-color: #264f78;
}
DebugInspector QPushButton {
    background-color: #0e639c;
    color: #ffffff;
    border: none;
    border-radius: 3px;
    padding: 4px 10px;
    font-weight: 500;
    min-height: 18px;
}
DebugInspector QPushButton:hover {
    background-color: #1177bb;
}
DebugInspector QPushButton:pressed {
    background-color: #094771;
}
DebugInspector QPushButton[class="pick-active"] {
    background-color: #cc6633;
}
DebugInspector QLineEdit {
    background-color: #3c3c3c;
    border: 1px solid #555555;
    border-radius: 3px;
    color: #d4d4d4;
    padding: 3px 6px;
}
DebugInspector QLineEdit:focus {
    border: 1px solid #0e639c;
}
DebugInspector QLabel {
    background-color: transparent;
    color: #d4d4d4;
}
DebugInspector QSplitter::handle {
    background-color: #3c3c3c;
}
"""


# ─────────────────────────────────────────────
# 1. 高亮叠加层
# ─────────────────────────────────────────────
class HighlightOverlay(QWidget):
    """在目标 widget 上方绘制半透明红色高亮框"""

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._color = QColor("#ff385c")

    def highlight(self, widget: QWidget):
        """移动到 widget 的全局坐标并显示"""
        if widget is None or sip.isdeleted(widget):
            self.hide()
            return
        pos = widget.mapToGlobal(QPoint(0, 0))
        pad = 2
        self.setGeometry(
            pos.x() - pad, pos.y() - pad,
            widget.width() + pad * 2, widget.height() + pad * 2,
        )
        self.show()
        self.raise_()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 半透明填充
        fill = QColor(self._color)
        fill.setAlpha(40)
        p.setBrush(QBrush(fill))
        # 边框
        border = QColor(self._color)
        border.setAlpha(200)
        p.setPen(QPen(border, 2))
        p.drawRect(self.rect().adjusted(1, 1, -1, -1))
        p.end()


# ─────────────────────────────────────────────
# 2. Widget 选取事件过滤器
# ─────────────────────────────────────────────
class WidgetPickerFilter(QObject):
    """全局事件过滤器：点击任意 widget 选中它，吃掉点击事件"""

    widget_picked = pyqtSignal(object)  # QWidget
    widget_hovered = pyqtSignal(object)

    def __init__(self, inspector_dock: QWidget, parent=None):
        super().__init__(parent)
        self._inspector = inspector_dock
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    def activate(self):
        app = QApplication.instance()
        if app and not self._active:
            app.installEventFilter(self)
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.CrossCursor))
            self._active = True

    def deactivate(self):
        app = QApplication.instance()
        if app and self._active:
            app.removeEventFilter(self)
            QApplication.restoreOverrideCursor()
            self._active = False

    def _is_inspector_widget(self, widget):
        """判断 widget 是否属于 inspector dock"""
        w = widget
        while w is not None:
            if w is self._inspector:
                return True
            w = w.parentWidget()
        return False

    def eventFilter(self, obj, event):
        if not self._active:
            return False

        if event.type() == QEvent.Type.MouseMove:
            widget = QApplication.widgetAt(QCursor.pos())
            if widget and not self._is_inspector_widget(widget):
                self.widget_hovered.emit(widget)
            return False

        if event.type() == QEvent.Type.MouseButtonPress:
            widget = QApplication.widgetAt(QCursor.pos())
            if widget and not self._is_inspector_widget(widget):
                self.widget_picked.emit(widget)
                self.deactivate()
                return True  # 吃掉点击，防止触发按钮
            elif widget and self._is_inspector_widget(widget):
                return False  # 点击 inspector 自身，放行

        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.deactivate()
                self.widget_hovered.emit(None)
                return True

        return False


# ─────────────────────────────────────────────
# 3. 主调试面板
# ─────────────────────────────────────────────
class DebugInspector(QDockWidget):
    """Qt Widget Inspector — 显示 widget 树、属性、QSS 编辑"""

    def __init__(self, parent: QWidget):
        super().__init__("Debug Inspector", parent)
        self.setObjectName("DebugInspector")
        self.setMinimumWidth(420)
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.setStyleSheet(INSPECTOR_STYLE)

        self._widget_map: dict[int, QWidget] = {}
        self._selected_widget: QWidget | None = None

        # 高亮和选取
        self._overlay = HighlightOverlay()
        self._picker = WidgetPickerFilter(self, parent=self)
        self._picker.widget_picked.connect(self._on_widget_picked)
        self._picker.widget_hovered.connect(self._on_widget_hovered)

        self._init_ui()
        self.refresh_tree()

    def _init_ui(self):
        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # === 工具栏 ===
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self.refresh_tree)
        toolbar.addWidget(self._refresh_btn)

        self._pick_btn = QPushButton("Pick Widget")
        self._pick_btn.clicked.connect(self._toggle_pick_mode)
        toolbar.addWidget(self._pick_btn)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search widgets...")
        self._search_input.textChanged.connect(self._filter_tree)
        toolbar.addWidget(self._search_input, 1)

        root.addLayout(toolbar)

        # === 主分割器 ===
        main_splitter = QSplitter(Qt.Orientation.Vertical)

        # -- Widget 树 --
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Widget Hierarchy"])
        self._tree.setIndentation(16)
        self._tree.currentItemChanged.connect(self._on_tree_selection)
        main_splitter.addWidget(self._tree)

        # -- 右侧：属性 + QSS 编辑 --
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        # 属性表
        self._prop_table = QTableWidget(0, 2)
        self._prop_table.setHorizontalHeaderLabels(["Property", "Value"])
        self._prop_table.horizontalHeader().setStretchLastSection(True)
        self._prop_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._prop_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._prop_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._prop_table.verticalHeader().setVisible(False)
        right_splitter.addWidget(self._prop_table)

        # QSS 编辑器
        qss_panel = QWidget()
        qss_layout = QVBoxLayout(qss_panel)
        qss_layout.setContentsMargins(0, 0, 0, 0)
        qss_layout.setSpacing(4)

        qss_label = QLabel("QSS Editor")
        qss_label.setStyleSheet("font-weight: 600; padding: 2px;")
        qss_layout.addWidget(qss_label)

        self._qss_editor = QPlainTextEdit()
        self._qss_editor.setPlaceholderText("Enter QSS here...")
        self._qss_editor.setMinimumHeight(80)
        qss_layout.addWidget(self._qss_editor)

        qss_btns = QHBoxLayout()
        qss_btns.setSpacing(4)

        btn_load = QPushButton("Load Current")
        btn_load.clicked.connect(self._qss_load_current)
        qss_btns.addWidget(btn_load)

        btn_apply_app = QPushButton("Apply to App")
        btn_apply_app.clicked.connect(self._qss_apply_to_app)
        qss_btns.addWidget(btn_apply_app)

        btn_apply_sel = QPushButton("Apply to Selected")
        btn_apply_sel.clicked.connect(self._qss_apply_to_selected)
        qss_btns.addWidget(btn_apply_sel)

        btn_reset = QPushButton("Reset")
        btn_reset.clicked.connect(self._qss_reset)
        qss_btns.addWidget(btn_reset)

        qss_layout.addLayout(qss_btns)
        right_splitter.addWidget(qss_panel)

        main_splitter.addWidget(right_splitter)

        # 分割比例：树占 40%，属性+QSS 占 60%
        main_splitter.setSizes([300, 400])
        right_splitter.setSizes([250, 200])

        root.addWidget(main_splitter, 1)
        self.setWidget(container)

    # ─── Widget 树 ───

    def refresh_tree(self):
        """重建 widget 树"""
        self._tree.clear()
        self._widget_map.clear()
        root_widget = self.parent()
        if root_widget:
            root_item = self._build_tree_item(root_widget)
            self._tree.addTopLevelItem(root_item)
            self._expand_levels(root_item, 2)

    def _build_tree_item(self, widget: QWidget) -> QTreeWidgetItem:
        """递归构建 widget 树节点"""
        class_name = type(widget).__name__
        obj_name = widget.objectName()
        label = f"{class_name} [{obj_name}]" if obj_name else class_name

        item = QTreeWidgetItem([label])
        wid = id(widget)
        item.setData(0, Qt.ItemDataRole.UserRole, wid)
        self._widget_map[wid] = widget

        # 递归子 widget，跳过 inspector 自身
        children = widget.findChildren(
            QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly
        )
        for child in children:
            if child is self or self._is_descendant_of(child, self):
                continue
            child_item = self._build_tree_item(child)
            item.addChild(child_item)

        return item

    def _is_descendant_of(self, widget: QWidget, ancestor: QWidget) -> bool:
        """判断 widget 是否为 ancestor 的后代"""
        w = widget
        while w is not None:
            if w is ancestor:
                return True
            w = w.parentWidget()
        return False

    def _expand_levels(self, item: QTreeWidgetItem, levels: int):
        """展开树的前 N 层"""
        if levels <= 0:
            return
        item.setExpanded(True)
        for i in range(item.childCount()):
            self._expand_levels(item.child(i), levels - 1)

    # ─── 树选中 ───

    def _on_tree_selection(self, current, previous):
        if current is None:
            self._selected_widget = None
            self._overlay.hide()
            return
        wid = current.data(0, Qt.ItemDataRole.UserRole)
        widget = self._widget_map.get(wid)
        if widget and not sip.isdeleted(widget):
            self._selected_widget = widget
            self._show_properties(widget)
            self._overlay.highlight(widget)
        else:
            self._selected_widget = None
            self._overlay.hide()

    # ─── 属性面板 ───

    def _show_properties(self, widget: QWidget):
        """显示 widget 的属性"""
        props = []

        props.append(("class", type(widget).__name__))
        props.append(("objectName", widget.objectName() or "(empty)"))

        # geometry
        g = widget.geometry()
        props.append(("geometry", f"{g.x()}, {g.y()}, {g.width()} x {g.height()}"))

        # 全局坐标
        gp = widget.mapToGlobal(QPoint(0, 0))
        props.append(("globalPos", f"{gp.x()}, {gp.y()}"))

        # sizeHint
        sh = widget.sizeHint()
        props.append(("sizeHint", f"{sh.width()} x {sh.height()}"))

        # min/max size
        props.append(("minimumSize", f"{widget.minimumWidth()} x {widget.minimumHeight()}"))
        props.append(("maximumSize", f"{widget.maximumWidth()} x {widget.maximumHeight()}"))

        # sizePolicy
        sp = widget.sizePolicy()
        props.append(("sizePolicy", f"H:{sp.horizontalPolicy().name}  V:{sp.verticalPolicy().name}"))

        props.append(("visible", str(widget.isVisible())))
        props.append(("enabled", str(widget.isEnabled())))

        # 本地 stylesheet
        ss = widget.styleSheet()
        props.append(("styleSheet", ss[:200] if ss else "(none)"))

        # font
        props.append(("font", widget.font().toString()))

        # toolTip
        props.append(("toolTip", widget.toolTip() or "(none)"))

        # layout
        layout = widget.layout()
        if layout:
            layout_info = type(layout).__name__
            layout_info += f"  spacing={layout.spacing()}"
            m = layout.contentsMargins()
            layout_info += f"  margins=({m.left()},{m.top()},{m.right()},{m.bottom()})"
            props.append(("layout", layout_info))
        else:
            props.append(("layout", "None"))

        # children count
        children = widget.findChildren(
            QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly
        )
        props.append(("children", str(len(children))))

        # Qt dynamic property "class" (本项目使用 QPushButton[class="pill"] 选择器)
        cls_prop = widget.property("class")
        if cls_prop:
            props.append(('property("class")', str(cls_prop)))

        # text (QLabel, QPushButton, QLineEdit)
        if hasattr(widget, "text"):
            try:
                txt = widget.text()
                if txt:
                    props.append(("text", txt[:100]))
            except Exception:
                pass

        # 填充表格
        self._prop_table.setRowCount(len(props))
        for row, (key, val) in enumerate(props):
            key_item = QTableWidgetItem(key)
            key_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            val_item = QTableWidgetItem(str(val))
            val_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._prop_table.setItem(row, 0, key_item)
            self._prop_table.setItem(row, 1, val_item)

    # ─── Pick 模式 ───

    def _toggle_pick_mode(self):
        if self._picker.active:
            self._picker.deactivate()
            self._pick_btn.setProperty("class", "")
            self._overlay.hide()
        else:
            self._picker.activate()
            self._pick_btn.setProperty("class", "pick-active")
        self._pick_btn.style().unpolish(self._pick_btn)
        self._pick_btn.style().polish(self._pick_btn)

    def _on_widget_picked(self, widget):
        """点击选取了一个 widget"""
        self._pick_btn.setProperty("class", "")
        self._pick_btn.style().unpolish(self._pick_btn)
        self._pick_btn.style().polish(self._pick_btn)

        self._selected_widget = widget
        self._show_properties(widget)
        self._overlay.highlight(widget)
        self._select_widget_in_tree(widget)

    def _on_widget_hovered(self, widget):
        """hover 预览高亮"""
        if widget and not sip.isdeleted(widget):
            self._overlay.highlight(widget)
        else:
            self._overlay.hide()

    def _select_widget_in_tree(self, widget: QWidget):
        """在树中定位并选中对应 widget"""
        wid = id(widget)
        it = QTreeWidgetItemIterator(self._tree)
        while it.value():
            item = it.value()
            if item.data(0, Qt.ItemDataRole.UserRole) == wid:
                self._tree.setCurrentItem(item)
                self._tree.scrollToItem(item)
                return
            it += 1

    # ─── 搜索过滤 ───

    def _filter_tree(self, text: str):
        """根据搜索文本过滤 widget 树"""
        text = text.strip().lower()
        if not text:
            # 显示全部
            it = QTreeWidgetItemIterator(self._tree)
            while it.value():
                it.value().setHidden(False)
                it += 1
            return

        # 先全部隐藏
        it = QTreeWidgetItemIterator(self._tree)
        while it.value():
            it.value().setHidden(True)
            it += 1

        # 匹配项及其祖先显示
        it = QTreeWidgetItemIterator(self._tree)
        while it.value():
            item = it.value()
            if text in item.text(0).lower():
                item.setHidden(False)
                # 展开并显示所有祖先
                parent = item.parent()
                while parent:
                    parent.setHidden(False)
                    parent.setExpanded(True)
                    parent = parent.parent()
            it += 1

    # ─── QSS 编辑器 ───

    def _qss_load_current(self):
        """加载当前样式表到编辑器"""
        if self._selected_widget and not sip.isdeleted(self._selected_widget):
            ss = self._selected_widget.styleSheet()
            if ss:
                self._qss_editor.setPlainText(ss)
                return
        # 无选中或无本地样式，加载全局样式
        self._qss_editor.setPlainText(get_stylesheet())

    def _qss_apply_to_app(self):
        """应用编辑器中的 QSS 到整个 App"""
        main_win = self.parent()
        if main_win:
            main_win.setStyleSheet(self._qss_editor.toPlainText())

    def _qss_apply_to_selected(self):
        """应用 QSS 到选中的 widget"""
        if self._selected_widget and not sip.isdeleted(self._selected_widget):
            self._selected_widget.setStyleSheet(self._qss_editor.toPlainText())

    def _qss_reset(self):
        """重置为原始样式"""
        main_win = self.parent()
        if main_win:
            main_win.setStyleSheet(get_stylesheet())
        self._qss_editor.setPlainText(get_stylesheet())

    # ─── 生命周期 ───

    def closeEvent(self, event):
        """关闭时清理"""
        if self._picker.active:
            self._picker.deactivate()
        self._overlay.hide()
        super().closeEvent(event)
