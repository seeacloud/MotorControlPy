"""JMC 伺服电机控制系统 - 入口"""

import sys
import logging
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from ui.main_window import MainWindow


def resource_path(relative_path: str) -> Path:
    """返回源码运行或冻结发布后的资源路径。"""
    if getattr(sys, "frozen", False):
        base_path = Path(sys.executable).resolve().parent
    else:
        base_path = Path(__file__).resolve().parent
    return base_path / relative_path


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main():
    setup_logging()

    app = QApplication(sys.argv)
    app.setApplicationName("JMC 伺服电机控制系统")
    app.setWindowIcon(QIcon(str(resource_path("ui/app_icon.ico"))))
    app.setQuitOnLastWindowClosed(False)

    # 全局异常处理
    def exception_hook(exc_type, exc_value, exc_tb):
        logging.error("未捕获异常", exc_info=(exc_type, exc_value, exc_tb))
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = exception_hook

    window = MainWindow()
    window.hide()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
