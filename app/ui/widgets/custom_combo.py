"""
Custom PromptBeast ComboBox widget.
Enforces dark popup view and disables accidental mouse wheel cycling so scrolling the page works smoothly.
"""
from PySide6.QtWidgets import QComboBox, QListView
from PySide6.QtCore import Qt


class PBComboBox(QComboBox):
    """
    QComboBox that:
    1. Disables mouse wheel item cycling (propagates wheel events to parent scroll containers).
    2. Automatically uses dark styled QListView for popup items.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setView(QListView())
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event):
        # Ignore wheel event so parent QScrollArea can scroll smoothly
        event.ignore()
