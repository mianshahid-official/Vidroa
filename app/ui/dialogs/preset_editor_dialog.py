"""
Preset Editor & Visual Style Manager for PromptBeast.
Allows creating, customizing, and deleting custom visual styles with live preview thumbnails.
"""
from pathlib import Path
from typing import Optional
import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QMessageBox,
    QFileDialog,
    QComboBox,
    QFrame,
    QSizePolicy,
)
from app.presets.loader import PresetManager
from app.models.presets import VisualStylePreset


class PresetEditorDialog(QDialog):
    """Studio Visual Style Manager: Create, Edit, Duplicate, and Delete Visual Art Styles."""

    styles_updated = Signal()

    def __init__(self, parent=None, initial_style_id: Optional[str] = None):
        super().__init__(parent)
        self.setWindowTitle("Visual Art Style Studio Manager")
        self.setMinimumWidth(860)
        self.setMinimumHeight(620)
        self._initial_style_id = initial_style_id
        self._selected_preview_path: Optional[str] = None
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #080C12;
                color: #E2E8F0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }
            QLabel {
                color: #CBD5E1;
            }
            QLineEdit, QPlainTextEdit, QComboBox {
                background-color: #0E1622;
                color: #F8FAFC;
                border: 1px solid rgba(163, 255, 18, 0.22);
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
                border-color: #A3FF12;
            }
            QListWidget {
                background-color: #0A0F18;
                border: 1px solid #1E293B;
                border-radius: 8px;
                padding: 4px;
                color: #E2E8F0;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-radius: 6px;
                margin-bottom: 2px;
            }
            QListWidget::item:selected {
                background-color: rgba(16, 185, 129, 0.25);
                border: 1px solid #10B981;
                color: #A3FF12;
                font-weight: 600;
            }
            QListWidget::item:hover:!selected {
                background-color: rgba(255, 255, 255, 0.05);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header Title
        hdr_box = QHBoxLayout()
        title_lbl = QLabel("🎨 Visual Art Style Studio Manager")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: 800; color: #F8FAFC;")
        hdr_box.addWidget(title_lbl)

        hdr_sub = QLabel("Create, customize, and manage AI prompt styling templates")
        hdr_sub.setStyleSheet("font-size: 11px; color: #64748B; margin-left: 10px;")
        hdr_box.addWidget(hdr_sub)
        hdr_box.addStretch()

        self.new_style_btn = QPushButton("➕ Create New Custom Style")
        self.new_style_btn.setCursor(Qt.PointingHandCursor)
        self.new_style_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #059669);
                color: #FFFFFF;
                font-weight: 700;
                font-size: 11px;
                border: 1px solid #34D399;
                border-radius: 6px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #A3FF12, stop:1 #10B981);
                color: #081009;
                border-color: #A3FF12;
            }
        """)
        self.new_style_btn.clicked.connect(self._on_new_style)
        hdr_box.addWidget(self.new_style_btn)

        layout.addLayout(hdr_box)

        # Main Splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #1E293B;
                width: 2px;
            }
        """)

        # LEFT PANEL: Style List
        left_w = QWidget()
        lw_layout = QVBoxLayout(left_w)
        lw_layout.setContentsMargins(0, 0, 8, 0)
        lw_layout.setSpacing(8)

        list_lbl = QLabel("AVAILABLE ART STYLES:")
        list_lbl.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748B; letter-spacing: 0.5px;")
        lw_layout.addWidget(list_lbl)

        self.styles_list = QListWidget()
        self.styles_list.currentItemChanged.connect(self._on_style_selected)
        lw_layout.addWidget(self.styles_list)

        # Quick action: Duplicate as Custom
        self.duplicate_btn = QPushButton("📋 Duplicate as Custom Style")
        self.duplicate_btn.setCursor(Qt.PointingHandCursor)
        self.duplicate_btn.setStyleSheet("""
            QPushButton {
                background-color: #111A24;
                color: #CBD5E1;
                border: 1px solid #1E293B;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #1E293B;
                color: #A3FF12;
                border-color: #34D399;
            }
        """)
        self.duplicate_btn.clicked.connect(self._on_duplicate_style)
        lw_layout.addWidget(self.duplicate_btn)

        splitter.addWidget(left_w)

        # RIGHT PANEL: Style Form
        right_w = QWidget()
        rw_layout = QVBoxLayout(right_w)
        rw_layout.setContentsMargins(8, 0, 0, 0)
        rw_layout.setSpacing(8)

        # State banner: Built-in or Custom
        self.badge_banner = QLabel("Built-in System Preset (Protected)")
        self.badge_banner.setStyleSheet("""
            background-color: rgba(59, 130, 246, 0.15);
            color: #60A5FA;
            border: 1px solid rgba(59, 130, 246, 0.3);
            border-radius: 6px;
            padding: 5px 10px;
            font-size: 11px;
            font-weight: 600;
        """)
        rw_layout.addWidget(self.badge_banner)

        # Row 1: Name and Category
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        name_box = QVBoxLayout()
        name_box.addWidget(QLabel("Style Name:"))
        self.style_name_input = QLineEdit()
        self.style_name_input.setPlaceholderText("e.g. Cinematic Cyberpunk 2099")
        name_box.addWidget(self.style_name_input)
        row1.addLayout(name_box, 3)

        cat_box = QVBoxLayout()
        cat_box.addWidget(QLabel("Category:"))
        self.style_cat_combo = QComboBox()
        self.style_cat_combo.setEditable(True)
        self.style_cat_combo.addItems([
            "Historical & Archival",
            "3D Animation",
            "Archival Monochrome",
            "Cinematic & Film",
            "Papercraft & Cutout",
            "Editorial Collage",
            "Painting & Fine Art",
            "Custom",
        ])
        cat_box.addWidget(self.style_cat_combo)
        row1.addLayout(cat_box, 2)

        rw_layout.addLayout(row1)

        # Row 2: Short Description
        rw_layout.addWidget(QLabel("User-Facing Description (UI Cards):"))
        self.style_desc_input = QLineEdit()
        self.style_desc_input.setPlaceholderText("Brief summary describing the visual tone, palette, and texture...")
        rw_layout.addWidget(self.style_desc_input)

        # Row 3: Preview Thumbnail Image Box
        thumb_box = QHBoxLayout()
        thumb_box.setSpacing(10)

        # Image preview label
        self.thumb_preview = QLabel("No Image")
        self.thumb_preview.setFixedSize(110, 68)
        self.thumb_preview.setAlignment(Qt.AlignCenter)
        self.thumb_preview.setStyleSheet("""
            background-color: #0B0E14;
            border: 1px solid rgba(163, 255, 18, 0.2);
            border-radius: 6px;
            color: #64748B;
            font-size: 10px;
        """)
        thumb_box.addWidget(self.thumb_preview)

        thumb_ctrls = QVBoxLayout()
        thumb_ctrls.addWidget(QLabel("Card Thumbnail Preview (16:9 recommended):"))

        btn_row = QHBoxLayout()
        self.choose_img_btn = QPushButton("📂 Choose Thumbnail Image...")
        self.choose_img_btn.setCursor(Qt.PointingHandCursor)
        self.choose_img_btn.setStyleSheet("""
            QPushButton {
                background-color: #111A24;
                color: #CBD5E1;
                border: 1px solid #1E293B;
                border-radius: 5px;
                padding: 4px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                border-color: #34D399;
                color: #A3FF12;
            }
        """)
        self.choose_img_btn.clicked.connect(self._on_choose_image)
        btn_row.addWidget(self.choose_img_btn)

        self.clear_img_btn = QPushButton("✕ Clear Image")
        self.clear_img_btn.setCursor(Qt.PointingHandCursor)
        self.clear_img_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #94A3B8;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 5px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                color: #F87171;
                border-color: #EF4444;
            }
        """)
        self.clear_img_btn.clicked.connect(self._on_clear_image)
        btn_row.addWidget(self.clear_img_btn)
        btn_row.addStretch()

        thumb_ctrls.addLayout(btn_row)
        thumb_box.addLayout(thumb_ctrls)
        rw_layout.addLayout(thumb_box)

        # Row 4: AI System Instructions
        instr_hdr = QHBoxLayout()
        instr_lbl = QLabel("AI System Prompt Instructions (Injected into Groq LLM):")
        instr_lbl.setStyleSheet("font-weight: 600; color: #F1F5F9;")
        instr_hdr.addWidget(instr_lbl)
        instr_hdr.addStretch()

        self.insert_template_btn = QPushButton("⚡ Insert Template Guide")
        self.insert_template_btn.setCursor(Qt.PointingHandCursor)
        self.insert_template_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #34D399;
                border: 1px solid rgba(52, 211, 153, 0.3);
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 10px;
            }
            QPushButton:hover {
                color: #A3FF12;
                border-color: #A3FF12;
            }
        """)
        self.insert_template_btn.clicked.connect(self._on_insert_template)
        instr_hdr.addWidget(self.insert_template_btn)
        rw_layout.addLayout(instr_hdr)

        self.style_sys_edit = QPlainTextEdit()
        self.style_sys_edit.setPlaceholderText(
            "Enter comprehensive instructions defining:\n"
            "- Visual world & aesthetic\n"
            "- Human subjects representation (anatomy, clothing)\n"
            "- Lighting, shadows, and camera lens\n"
            "- Palette, textures, and material realism\n"
            "- Negative constraints (what to strictly avoid)"
        )
        rw_layout.addWidget(self.style_sys_edit, 1)

        # Action Buttons Row
        act_row = QHBoxLayout()
        act_row.setSpacing(10)

        self.delete_btn = QPushButton("🗑 Delete Custom Style")
        self.delete_btn.setCursor(Qt.PointingHandCursor)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.15);
                color: #F87171;
                border: 1px solid rgba(239, 68, 68, 0.4);
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #EF4444;
                color: #FFFFFF;
                border-color: #DC2626;
            }
            QPushButton:disabled {
                background-color: rgba(255, 255, 255, 0.03);
                color: #475569;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
        """)
        self.delete_btn.clicked.connect(self._on_delete_style)
        act_row.addWidget(self.delete_btn)

        act_row.addStretch()

        self.save_style_btn = QPushButton("💾 Save Visual Style")
        self.save_style_btn.setCursor(Qt.PointingHandCursor)
        self.save_style_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #059669);
                color: #FFFFFF;
                font-weight: 700;
                font-size: 12px;
                border: 1px solid #34D399;
                border-radius: 6px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #A3FF12, stop:1 #10B981);
                color: #081009;
                border-color: #A3FF12;
            }
            QPushButton:disabled {
                background-color: rgba(255, 255, 255, 0.04);
                color: #475569;
                border: 1px solid rgba(255, 255, 255, 0.06);
            }
        """)
        self.save_style_btn.clicked.connect(self._on_save_style)
        act_row.addWidget(self.save_style_btn)

        rw_layout.addLayout(act_row)

        splitter.addWidget(right_w)
        splitter.setSizes([260, 580])
        layout.addWidget(splitter, 1)

        # Bottom Bar: Close
        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #1E293B;
                color: #E2E8F0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 18px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #FFFFFF;
            }
        """)
        close_btn.clicked.connect(self.accept)
        bottom_bar.addWidget(close_btn)

        layout.addLayout(bottom_bar)

        self._populate_styles()

    def _populate_styles(self, select_id: Optional[str] = None):
        self.styles_list.clear()
        styles = PresetManager.get_all_styles()

        target_row = 0
        for idx, s in enumerate(styles):
            tag = "[Custom]" if s.is_custom else "[Built-in]"
            item = QListWidgetItem(f"{s.name}  {tag}")
            item.setData(Qt.UserRole, s.id)
            if s.is_custom:
                item.setForeground(Qt.green)
            self.styles_list.addItem(item)
            if select_id and s.id == select_id:
                target_row = idx
            elif not select_id and self._initial_style_id and s.id == self._initial_style_id:
                target_row = idx

        if self.styles_list.count() > 0:
            self.styles_list.setCurrentRow(target_row)

    def _on_style_selected(self, current: Optional[QListWidgetItem]):
        if not current:
            return
        style_id = current.data(Qt.UserRole)
        preset = PresetManager.get_style_by_id(style_id)
        if not preset:
            return

        self._selected_preview_path = None
        self.style_name_input.setText(preset.name)

        # Set category
        idx = self.style_cat_combo.findText(preset.category)
        if idx >= 0:
            self.style_cat_combo.setCurrentIndex(idx)
        else:
            self.style_cat_combo.setEditText(preset.category)

        self.style_desc_input.setText(preset.description)
        self.style_sys_edit.setPlainText(preset.system_instructions)

        # Check if custom
        is_custom = preset.is_custom

        if is_custom:
            self.badge_banner.setText("✨ User-Created Custom Style (Editable & Deletable)")
            self.badge_banner.setStyleSheet("""
                background-color: rgba(16, 185, 129, 0.15);
                color: #34D399;
                border: 1px solid rgba(16, 185, 129, 0.35);
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: 600;
            """)
            self.style_name_input.setReadOnly(False)
            self.style_desc_input.setReadOnly(False)
            self.style_sys_edit.setReadOnly(False)
            self.save_style_btn.setEnabled(True)
            self.save_style_btn.setText("💾 Update Visual Style")
            self.delete_btn.setEnabled(True)
            self.choose_img_btn.setEnabled(True)
            self.clear_img_btn.setEnabled(True)
        else:
            self.badge_banner.setText("🔒 Official Built-in Style (Protected System Preset)")
            self.badge_banner.setStyleSheet("""
                background-color: rgba(59, 130, 246, 0.15);
                color: #60A5FA;
                border: 1px solid rgba(59, 130, 246, 0.3);
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: 600;
            """)
            self.style_name_input.setReadOnly(True)
            self.style_desc_input.setReadOnly(True)
            self.style_sys_edit.setReadOnly(True)
            self.save_style_btn.setEnabled(False)
            self.save_style_btn.setText("🔒 Protected (Use Duplicate to Edit)")
            self.delete_btn.setEnabled(False)
            self.choose_img_btn.setEnabled(False)
            self.clear_img_btn.setEnabled(False)

        # Load preview image
        self._update_thumbnail_preview(preset.id)

    def _update_thumbnail_preview(self, style_id: str, custom_file_path: Optional[str] = None):
        if custom_file_path and Path(custom_file_path).exists():
            pm = QPixmap(custom_file_path)
            if not pm.isNull():
                self.thumb_preview.setPixmap(pm.scaled(110, 68, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                return

        # Check existing style preview directory
        previews_dir = Path(__file__).resolve().parent.parent.parent.parent / "assets" / "style_previews"
        for ext in (".png", ".jpg", ".jpeg"):
            cand = previews_dir / f"{style_id}{ext}"
            if cand.exists():
                pm = QPixmap(str(cand))
                if not pm.isNull():
                    self.thumb_preview.setPixmap(pm.scaled(110, 68, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    return

        # Fallback
        self.thumb_preview.setPixmap(QPixmap())
        self.thumb_preview.setText("🎨 No Preview")

    def _on_choose_image(self):
        fpath, _ = QFileDialog.getOpenFileName(
            self,
            "Select Style Preview Thumbnail",
            "",
            "Image Files (*.png *.jpg *.jpeg *.webp);;All Files (*.*)"
        )
        if fpath:
            self._selected_preview_path = fpath
            pm = QPixmap(fpath)
            if not pm.isNull():
                self.thumb_preview.setPixmap(pm.scaled(110, 68, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _on_clear_image(self):
        self._selected_preview_path = ""
        self.thumb_preview.setPixmap(QPixmap())
        self.thumb_preview.setText("🎨 No Preview")

    def _on_new_style(self):
        self.styles_list.clearSelection()
        self._selected_preview_path = None
        self.badge_banner.setText("✨ Creating New Custom Art Style")
        self.badge_banner.setStyleSheet("""
            background-color: rgba(163, 255, 18, 0.15);
            color: #A3FF12;
            border: 1px solid rgba(163, 255, 18, 0.4);
            border-radius: 6px;
            padding: 5px 10px;
            font-size: 11px;
            font-weight: 700;
        """)

        self.style_name_input.setText("New Art Style")
        self.style_name_input.setReadOnly(False)
        self.style_name_input.selectAll()
        self.style_name_input.setFocus()

        self.style_cat_combo.setEditText("Custom")
        self.style_desc_input.setText("Vibrant custom aesthetic for YouTube storytelling...")
        self.style_desc_input.setReadOnly(False)

        self._on_insert_template()
        self.style_sys_edit.setReadOnly(False)

        self.thumb_preview.setPixmap(QPixmap())
        self.thumb_preview.setText("🎨 No Preview")

        self.save_style_btn.setEnabled(True)
        self.save_style_btn.setText("💾 Save Visual Style")
        self.delete_btn.setEnabled(False)
        self.choose_img_btn.setEnabled(True)
        self.clear_img_btn.setEnabled(True)

    def _on_duplicate_style(self):
        curr = self.styles_list.currentItem()
        if not curr:
            return
        style_id = curr.data(Qt.UserRole)
        preset = PresetManager.get_style_by_id(style_id)
        if not preset:
            return

        self._on_new_style()
        self.style_name_input.setText(f"{preset.name} (Custom Copy)")
        self.style_cat_combo.setEditText(preset.category)
        self.style_desc_input.setText(f"Customized variation of {preset.name}")
        self.style_sys_edit.setPlainText(preset.system_instructions)

        # Copy over preview image reference if built-in has one
        previews_dir = Path(__file__).resolve().parent.parent.parent.parent / "assets" / "style_previews"
        for ext in (".png", ".jpg"):
            cand = previews_dir / f"{style_id}{ext}"
            if cand.exists():
                self._selected_preview_path = str(cand)
                self._update_thumbnail_preview(style_id, str(cand))
                break

    def _on_insert_template(self):
        template = (
            "Visual Aesthetic: Define the overarching cinematic and artistic identity.\n\n"
            "Human Subjects: Depict human characters with natural proportions, expressive facial features, "
            "and period-authentic clothing and textures.\n\n"
            "Environment & Architecture: Detailed, textured backgrounds respecting the story setting facts.\n\n"
            "Lighting & Atmosphere: Dynamic cinematic lighting with natural depth and contrast.\n\n"
            "Camera & Framing: Adapt shot composition (wide, medium, close-up) naturally based on narration beats.\n\n"
            "STRICTLY AVOID: Blurry artifacts, modern anachronisms, cartoonish distortions, or conflicting styles."
        )
        self.style_sys_edit.setPlainText(template)

    def _on_save_style(self):
        name = self.style_name_input.text().strip()
        cat = self.style_cat_combo.currentText().strip() or "Custom"
        desc = self.style_desc_input.text().strip()
        instructions = self.style_sys_edit.toPlainText().strip()

        if not name or not instructions:
            QMessageBox.warning(self, "Incomplete Style", "Please enter both a Style Name and System Instructions.")
            return

        # Generate or retain clean style ID
        curr = self.styles_list.currentItem()
        if curr and curr.data(Qt.UserRole) and not PresetManager.is_builtin_style(curr.data(Qt.UserRole)):
            style_id = curr.data(Qt.UserRole)
        else:
            clean_token = re.sub(r"[^a-zA-Z0-9]+", "_", name.lower()).strip("_")
            style_id = f"custom_{clean_token}"

        preset = VisualStylePreset(
            id=style_id,
            name=name,
            category=cat,
            description=desc or f"Custom {name} visual art style.",
            system_instructions=instructions,
            is_custom=True
        )

        PresetManager.save_custom_style(preset, preview_image_path=self._selected_preview_path)
        self._populate_styles(select_id=style_id)
        self.styles_updated.emit()

        QMessageBox.information(
            self,
            "Visual Style Saved",
            f"Visual art style '{name}' saved successfully!\nIt is now active and selectable in the Studio."
        )

    def _on_delete_style(self):
        curr = self.styles_list.currentItem()
        if not curr:
            return
        style_id = curr.data(Qt.UserRole)
        if PresetManager.is_builtin_style(style_id):
            QMessageBox.warning(self, "Protected Preset", "Official built-in system styles cannot be deleted.")
            return

        preset = PresetManager.get_style_by_id(style_id)
        name = preset.name if preset else style_id

        reply = QMessageBox.question(
            self,
            "Delete Custom Style",
            f"Are you sure you want to permanently delete custom style:\n\n'{name}'?\n\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            PresetManager.delete_custom_style(style_id)
            self._populate_styles()
            self.styles_updated.emit()
            QMessageBox.information(self, "Deleted", f"Custom style '{name}' has been deleted.")
