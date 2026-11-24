"""
Project recovery dialog for unfinished / interrupted jobs.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
)


class RecoveryDialog(QDialog):
    """Prompts the user when an unfinished generation job is detected on startup."""

    def __init__(self, project_name: str, stage: str, progress_pct: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Unfinished Project Generation Detected")
        self.setMinimumWidth(480)
        self.action = "open" # 'resume', 'open', 'discard'

        self._setup_ui(project_name, stage, progress_pct)

    def _setup_ui(self, project_name: str, stage: str, progress_pct: float):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        title = QLabel("⚠️ Interrupted Generation Found")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #F59E0B;")
        layout.addWidget(title)

        info_box = QGroupBox("Project State")
        ib_layout = QVBoxLayout(info_box)
        ib_layout.addWidget(QLabel(f"Project Name: <b>{project_name}</b>"))
        ib_layout.addWidget(QLabel(f"Last Active Stage: <b>{stage}</b> ({progress_pct:.0f}% completed)"))
        ib_layout.addWidget(QLabel("Intermediate scenes have been preserved on disk."))
        layout.addWidget(info_box)

        msg = QLabel("How would you like to proceed?")
        msg.setStyleSheet("color: #CBD5E1;")
        layout.addWidget(msg)

        # Buttons
        btn_layout = QHBoxLayout()

        resume_btn = QPushButton("Resume Generation")
        resume_btn.setStyleSheet("background-color: #4F46E5; border: 1px solid #6366F1; color: #FFFFFF; font-weight: 600;")
        resume_btn.clicked.connect(self._on_resume)
        btn_layout.addWidget(resume_btn)

        open_btn = QPushButton("Open Project As-Is")
        open_btn.clicked.connect(self._on_open)
        btn_layout.addWidget(open_btn)

        discard_btn = QPushButton("Discard")
        discard_btn.setStyleSheet("background-color: #450A0A; border: 1px solid #7F1D1D; color: #FCA5A5;")
        discard_btn.clicked.connect(self._on_discard)
        btn_layout.addWidget(discard_btn)

        layout.addLayout(btn_layout)

    def _on_resume(self):
        self.action = "resume"
        self.accept()

    def _on_open(self):
        self.action = "open"
        self.accept()

    def _on_discard(self):
        self.action = "discard"
        self.accept()
