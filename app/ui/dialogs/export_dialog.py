"""
Export dialog with real-time text/JSON tabbed preview and multi-format save.
"""
import json
from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QPlainTextEdit,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QApplication,
)
from app.models.scene import VisualScene
from app.models.timeline import NarrationData
from app.core.export import StoryboardExporter


class ExportDialog(QDialog):
    """Multi-format export dialog with real-time code/text preview."""

    def __init__(
        self,
        scenes: List[VisualScene],
        narration: Optional[NarrationData] = None,
        parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Export Storyboard & Image Prompts")
        self.setMinimumWidth(760)
        self.setMinimumHeight(540)

        self.scenes = scenes
        self.narration = narration
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)

        self.tabs = QTabWidget()

        # Generate exported texts
        self.txt_content = StoryboardExporter.export_to_text(self.scenes)
        self.timeline_json_content = json.dumps(
            StoryboardExporter.export_to_timeline_json(self.scenes, self.narration),
            indent=2
        )
        self.prompts_json_content = json.dumps(
            StoryboardExporter.export_to_image_prompts_json(self.scenes),
            indent=2
        )
        self.csv_content = StoryboardExporter.export_to_csv(self.scenes)
        self.prompts_only_content = StoryboardExporter.export_to_prompts_only(self.scenes)

        # Tab 1: prompts_only.txt (One Prompt Per Line, Clean)
        self.prompts_only_edit = QPlainTextEdit(self.prompts_only_content)
        self.prompts_only_edit.setReadOnly(True)
        self.tabs.addTab(self.prompts_only_edit, "prompts_only.txt (1 Line Each)")

        # Tab 2: image_prompts.txt
        self.txt_edit = QPlainTextEdit(self.txt_content)
        self.txt_edit.setReadOnly(True)
        self.tabs.addTab(self.txt_edit, "image_prompts.txt (Detailed)")

        # Tab 2: timeline.json
        self.timeline_edit = QPlainTextEdit(self.timeline_json_content)
        self.timeline_edit.setReadOnly(True)
        self.tabs.addTab(self.timeline_edit, "timeline.json")

        # Tab 3: image_prompts.json
        self.prompts_edit = QPlainTextEdit(self.prompts_json_content)
        self.prompts_edit.setReadOnly(True)
        self.tabs.addTab(self.prompts_edit, "image_prompts.json")

        # Tab 4: timeline.csv
        self.csv_edit = QPlainTextEdit(self.csv_content)
        self.csv_edit.setReadOnly(True)
        self.tabs.addTab(self.csv_edit, "timeline.csv")

        layout.addWidget(self.tabs)

        # Actions
        btn_layout = QHBoxLayout()

        self.copy_btn = QPushButton("📋 Copy Current View to Clipboard")
        self.copy_btn.clicked.connect(self._on_copy_clipboard)
        btn_layout.addWidget(self.copy_btn)

        btn_layout.addStretch()

        self.export_all_btn = QPushButton("📁 Export All Files to Folder...")
        self.export_all_btn.setStyleSheet("background-color: #4F46E5; border: 1px solid #6366F1; color: #FFFFFF; font-weight: 600;")
        self.export_all_btn.clicked.connect(self._on_export_all)
        btn_layout.addWidget(self.export_all_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)

    def _on_copy_clipboard(self):
        idx = self.tabs.currentIndex()
        if idx == 0:
            text = self.prompts_only_content
        elif idx == 1:
            text = self.txt_content
        elif idx == 2:
            text = self.timeline_json_content
        elif idx == 3:
            text = self.prompts_json_content
        else:
            text = self.csv_content

        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copied", "Content copied to clipboard.")

    def _on_export_all(self):
        target_dir = QFileDialog.getExistingDirectory(self, "Select Export Directory")
        if target_dir:
            try:
                saved = StoryboardExporter.save_all_exports(target_dir, self.scenes, self.narration)
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Successfully exported 5 production files to:\n{target_dir}\n\n- prompts_only.txt (clean 1 per line)\n- image_prompts.txt (detailed)\n- timeline.json\n- image_prompts.json\n- timeline.csv"
                )
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Error writing export files: {str(e)}")
