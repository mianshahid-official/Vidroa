"""
Preset Editor dialog for creating and managing visual styles and subjects.
"""
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QMessageBox,
)
from app.presets.loader import PresetManager
from app.models.presets import VisualStylePreset, SubjectPreset


class PresetEditorDialog(QDialog):
    """Allows viewing system presets and creating custom visual styles / subjects."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preset Manager & Visual Style Editor")
        self.setMinimumWidth(720)
        self.setMinimumHeight(520)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)

        tabs = QTabWidget()

        # TAB 1: Visual Styles
        styles_tab = QWidget()
        s_layout = QHBoxLayout(styles_tab)
        s_splitter = QSplitter(Qt.Horizontal)

        # Left List
        left_w = QWidget()
        lw_layout = QVBoxLayout(left_w)
        lw_layout.setContentsMargins(0, 0, 0, 0)
        lw_layout.addWidget(QLabel("Visual Styles:"))

        self.styles_list = QListWidget()
        self.styles_list.currentItemChanged.connect(self._on_style_selected)
        lw_layout.addWidget(self.styles_list)

        self.new_style_btn = QPushButton("+ New Custom Style")
        self.new_style_btn.clicked.connect(self._on_new_style)
        lw_layout.addWidget(self.new_style_btn)

        s_splitter.addWidget(left_w)

        # Right Editor
        right_w = QWidget()
        rw_layout = QVBoxLayout(right_w)
        rw_layout.setContentsMargins(0, 0, 0, 0)

        rw_layout.addWidget(QLabel("Style Name:"))
        self.style_name_input = QLineEdit()
        rw_layout.addWidget(self.style_name_input)

        rw_layout.addWidget(QLabel("Short Description (User Facing):"))
        self.style_desc_input = QLineEdit()
        rw_layout.addWidget(self.style_desc_input)

        rw_layout.addWidget(QLabel("Hidden System Instructions (Injected into Cloud AI):"))
        self.style_sys_edit = QPlainTextEdit()
        rw_layout.addWidget(self.style_sys_edit)

        self.save_style_btn = QPushButton("Save Visual Style")
        self.save_style_btn.setStyleSheet("background-color: #4F46E5; color: #FFFFFF; font-weight: 600;")
        self.save_style_btn.clicked.connect(self._on_save_style)
        rw_layout.addWidget(self.save_style_btn)

        s_splitter.addWidget(right_w)
        s_splitter.setSizes([260, 440])
        s_layout.addWidget(s_splitter)

        tabs.addTab(styles_tab, "Visual Styles")

        layout.addWidget(tabs)

        # Close Button
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_layout.addWidget(close_btn)
        layout.addLayout(close_layout)

        self._populate_styles()

    def _populate_styles(self):
        self.styles_list.clear()
        styles = PresetManager.get_all_styles()
        for s in styles:
            item = QListWidgetItem(f"{s.name} {'(Custom)' if s.is_custom else ''}")
            item.setData(Qt.UserRole, s.id)
            self.styles_list.addItem(item)

        if self.styles_list.count() > 0:
            self.styles_list.setCurrentRow(0)

    def _on_style_selected(self, current: Optional[QListWidgetItem]):
        if not current:
            return
        style_id = current.data(Qt.UserRole)
        preset = PresetManager.get_style_by_id(style_id)
        if preset:
            self.style_name_input.setText(preset.name)
            self.style_desc_input.setText(preset.description)
            self.style_sys_edit.setPlainText(preset.system_instructions)
            self.style_name_input.setReadOnly(not preset.is_custom)
            self.save_style_btn.setEnabled(preset.is_custom)

    def _on_new_style(self):
        self.styles_list.clearSelection()
        self.style_name_input.setText("New Custom Style")
        self.style_name_input.setReadOnly(False)
        self.style_desc_input.setText("Custom visual style description.")
        self.style_sys_edit.setPlainText("Custom system instructions for image prompt generation...")
        self.save_style_btn.setEnabled(True)

    def _on_save_style(self):
        name = self.style_name_input.text().strip()
        desc = self.style_desc_input.text().strip()
        instructions = self.style_sys_edit.toPlainText().strip()

        if not name or not instructions:
            QMessageBox.warning(self, "Incomplete Style", "Please enter both a style name and system instructions.")
            return

        style_id = "custom_" + name.lower().replace(" ", "_").replace("-", "_")
        preset = VisualStylePreset(
            id=style_id,
            name=name,
            description=desc,
            system_instructions=instructions,
            is_custom=True
        )
        PresetManager.save_custom_style(preset)
        self._populate_styles()
        QMessageBox.information(self, "Saved", f"Visual style '{name}' saved successfully.")
