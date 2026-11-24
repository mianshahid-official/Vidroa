"""
Sleek, minimal real-time progress bar widget for PromptBeast.
Displays active step description and percentage directly on a slim modern progress bar.
"""
from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QFrame,
)
from app.models.job import JobStage, JobStatus, ProgressInfo


class ProgressPanelWidget(QWidget):
    """Sleek, minimal progress bar displaying the active step and cancellation control."""

    cancel_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(4)

        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: #0b0f19;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 4px 8px;
            }
        """)
        c_lay = QVBoxLayout(container)
        c_lay.setContentsMargins(4, 4, 4, 4)
        c_lay.setSpacing(4)

        # Header Row: Active step message on left, percentage on right
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.msg_lbl = QLabel("Ready to plan storyboard.")
        self.msg_lbl.setWordWrap(True)
        self.msg_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 600;")
        top_row.addWidget(self.msg_lbl, 1)

        self.pct_lbl = QLabel("0%")
        self.pct_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-family: monospace; font-weight: 700;")
        top_row.addWidget(self.pct_lbl)

        c_lay.addLayout(top_row)

        # Bottom Row: Slim progress bar + inline cancel button
        bar_row = QHBoxLayout()
        bar_row.setSpacing(8)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border-radius: 3px;
                border: 1px solid #334155;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:0.5 #38bdf8, stop:1 #818cf8);
                border-radius: 2px;
            }
        """)
        bar_row.addWidget(self.progress_bar, 1)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedHeight(22)
        self.cancel_btn.setFixedWidth(64)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #450a0a;
                border: 1px solid #7f1d1d;
                color: #fca5a5;
                font-size: 10px;
                font-weight: 600;
                border-radius: 3px;
            }
            QPushButton:hover:enabled {
                background-color: #7f1d1d;
            }
            QPushButton:disabled {
                background-color: #1e293b;
                border-color: #334155;
                color: #64748b;
            }
        """)
        self.cancel_btn.clicked.connect(self.cancel_requested.emit)
        self.cancel_btn.setEnabled(False)
        bar_row.addWidget(self.cancel_btn)

        c_lay.addLayout(bar_row)
        layout.addWidget(container)

    def update_progress(self, info: ProgressInfo):
        pct = max(0, min(100, int(info.progress_percentage)))
        self.progress_bar.setValue(pct)
        self.pct_lbl.setText(f"{pct}%")
        self.msg_lbl.setText(info.message or "In progress...")

        # Enable/Disable cancel button
        self.cancel_btn.setEnabled(info.status == JobStatus.RUNNING)

    def set_running_state(self, running: bool):
        self.cancel_btn.setEnabled(running)
        if not running:
            self.cancel_btn.setText("Cancel")

    def mark_cancelled(self):
        self.msg_lbl.setText("Generation cancelled by user.")
        self.msg_lbl.setStyleSheet("color: #f87171; font-size: 11px; font-weight: 600;")
        self.cancel_btn.setEnabled(False)
