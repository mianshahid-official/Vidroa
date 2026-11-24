"""
PromptBeast Desktop Application Entry Point.
"""
import sys
import os
import traceback
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QIcon, QFont
from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow
from app.presets.loader import PresetManager


def global_exception_handler(exctype, value, tb):
    """Global exception handler to prevent silent application crashes and log tracebacks."""
    err_msg = "".join(traceback.format_exception(exctype, value, tb))
    print(f"\n[CRITICAL UNCAUGHT EXCEPTION]\n{err_msg}", file=sys.stderr)
    try:
        with open(BASE_DIR / "crash.log", "a", encoding="utf-8") as f:
            f.write(f"\n--- Crash Log: {exctype.__name__} ---\n{err_msg}\n")
    except Exception:
        pass


def main():
    sys.excepthook = global_exception_handler

    # Configure High-DPI attributes
    QCoreApplication.setApplicationName("PromptBeast")
    QCoreApplication.setOrganizationName("PromptBeast Studio")
    QCoreApplication.setOrganizationDomain("promptbeast.ai")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    # Never terminate when a modal QMessageBox, file dialog, or preview window closes
    app.setQuitOnLastWindowClosed(True)

    # Set default modern font
    font = QFont("Segoe UI", 10)
    font.setStyleHint(QFont.SansSerif)
    app.setFont(font)

    # Initialize Presets
    PresetManager.initialize()

    # Launch Main Window
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
