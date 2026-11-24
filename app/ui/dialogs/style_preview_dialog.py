"""
Interactive Style Preview Dialog for PromptBeast.
Displays visual artwork samples, camera framing specs, lighting details, and prompt examples
for all available visual styles.
"""
from pathlib import Path
from typing import Optional, Dict, List

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTextEdit, QComboBox, QApplication, QMessageBox, QScrollArea, QWidget
)

from app.presets.loader import PresetManager
from app.models.presets import VisualStylePreset

ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "style_previews"


class StylePreviewDialog(QDialog):
    """Visual gallery dialog for previewing and selecting image styles."""

    def __init__(self, initial_style_id: str = "century_old_photograph", parent=None):
        super().__init__(parent)
        self.setWindowTitle("PromptBeast Visual Style Gallery & Prompt Previewer")
        self.setMinimumSize(780, 680)
        self.resize(840, 720)

        self.all_styles: List[VisualStylePreset] = PresetManager.get_all_styles()
        self.style_map = {s.id: s for s in self.all_styles}
        self.current_style_id = initial_style_id if initial_style_id in self.style_map else (self.all_styles[0].id if self.all_styles else "")
        self.selected_style_id = self.current_style_id

        self._setup_ui()
        self._load_style(self.current_style_id)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Top Navigation Bar: Style Selector + Prev/Next
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        lbl = QLabel("<b>Select Style:</b>")
        lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
        top_bar.addWidget(lbl)

        self.style_selector = QComboBox()
        self.style_selector.setStyleSheet("""
            QComboBox {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 13px;
                font-weight: 600;
            }
        """)
        for s in self.all_styles:
            self.style_selector.addItem(f"{s.name} ({s.category or 'Style'})", s.id)
        self.style_selector.currentIndexChanged.connect(self._on_selector_changed)
        top_bar.addWidget(self.style_selector, 1)

        self.prev_btn = QPushButton("◀ Prev")
        self.prev_btn.setFixedSize(70, 32)
        self.prev_btn.setStyleSheet("background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155; border-radius: 6px;")
        self.prev_btn.clicked.connect(self._on_prev)
        top_bar.addWidget(self.prev_btn)

        self.next_btn = QPushButton("Next ▶")
        self.next_btn.setFixedSize(70, 32)
        self.next_btn.setStyleSheet("background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155; border-radius: 6px;")
        self.next_btn.clicked.connect(self._on_next)
        top_bar.addWidget(self.next_btn)

        layout.addLayout(top_bar)

        # Scrollable Content Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: #0b0f19; border: 1px solid #1e293b; border-radius: 8px;")

        content_widget = QWidget()
        c_layout = QVBoxLayout(content_widget)
        c_layout.setContentsMargins(16, 16, 16, 16)
        c_layout.setSpacing(14)

        # 1. Visual Preview Banner
        self.image_preview_lbl = QLabel()
        self.image_preview_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview_lbl.setMinimumHeight(320)
        self.image_preview_lbl.setStyleSheet("""
            background-color: #020617;
            border: 1px solid #1e293b;
            border-radius: 8px;
            padding: 8px;
        """)
        c_layout.addWidget(self.image_preview_lbl)

        # 2. Style Description & System Instructions Box
        desc_box = QFrame()
        desc_box.setStyleSheet("background-color: #0f172a; border: 1px solid #1e293b; border-radius: 6px; padding: 10px;")
        db_layout = QVBoxLayout(desc_box)
        db_layout.setSpacing(6)

        self.title_lbl = QLabel("")
        self.title_lbl.setStyleSheet("color: #38bdf8; font-size: 15px; font-weight: bold;")
        db_layout.addWidget(self.title_lbl)

        self.desc_lbl = QLabel("")
        self.desc_lbl.setStyleSheet("color: #cbd5e1; font-size: 12px; line-height: 1.4;")
        self.desc_lbl.setWordWrap(True)
        db_layout.addWidget(self.desc_lbl)

        c_layout.addWidget(desc_box)

        # 3. Master Prompt Template Preview
        prompt_box = QFrame()
        prompt_box.setStyleSheet("background-color: #0f172a; border: 1px solid #1e293b; border-radius: 6px; padding: 10px;")
        pb_layout = QVBoxLayout(prompt_box)
        pb_layout.setSpacing(6)

        prompt_hdr = QHBoxLayout()
        p_title = QLabel("<b>AI Image Prompt Blueprint (System Instructions):</b>")
        p_title.setStyleSheet("color: #a855f7; font-size: 11px;")
        prompt_hdr.addWidget(p_title)
        prompt_hdr.addStretch()

        self.copy_btn = QPushButton("Copy Instructions")
        self.copy_btn.setFixedHeight(26)
        self.copy_btn.setStyleSheet("background-color: #1e293b; color: #38bdf8; font-size: 10px; font-weight: bold; border-radius: 4px; padding: 0 10px;")
        self.copy_btn.clicked.connect(self._on_copy_prompt)
        prompt_hdr.addWidget(self.copy_btn)
        pb_layout.addLayout(prompt_hdr)

        self.prompt_text = QTextEdit()
        self.prompt_text.setReadOnly(True)
        self.prompt_text.setFixedHeight(85)
        self.prompt_text.setStyleSheet("""
            background-color: #020617;
            color: #94a3b8;
            font-family: 'Consolas', monospace;
            font-size: 11px;
            border: 1px solid #334155;
            border-radius: 4px;
            padding: 6px;
        """)
        pb_layout.addWidget(self.prompt_text)

        c_layout.addWidget(prompt_box)

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        # Bottom Action Buttons
        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()

        cancel_btn = QPushButton("Close")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet("background-color: #1e293b; color: #94a3b8; font-weight: 600; border-radius: 6px; padding: 0 16px;")
        cancel_btn.clicked.connect(self.reject)
        bottom_bar.addWidget(cancel_btn)

        self.apply_btn = QPushButton("Select & Apply This Style")
        self.apply_btn.setFixedHeight(36)
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-size: 12px;
                font-weight: bold;
                border-radius: 6px;
                border: 1px solid #38bdf8;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)
        self.apply_btn.clicked.connect(self._on_apply)
        bottom_bar.addWidget(self.apply_btn)

        layout.addLayout(bottom_bar)

    def _load_style(self, style_id: str):
        preset = self.style_map.get(style_id)
        if not preset:
            return

        self.current_style_id = style_id

        # Update selector combo box without triggering signal loop
        self.style_selector.blockSignals(True)
        idx = self.style_selector.findData(style_id)
        if idx >= 0:
            self.style_selector.setCurrentIndex(idx)
        self.style_selector.blockSignals(False)

        self.title_lbl.setText(f"{preset.name}  <span style='color: #64748b; font-size: 11px;'>[{preset.category or 'Visual Style'}]</span>")
        self.desc_lbl.setText(preset.description or "No description provided.")
        self.prompt_text.setPlainText(preset.system_instructions or "")

        # Load Preview Graphic
        preview_path = None
        # Check direct style_id and common aliases
        candidate_ids = [style_id]
        aliases = {
            "vintage_photograph": "century_old_photograph",
            "vintage_photo": "century_old_photograph",
            "stick_figure": "3d_red_blue_stickman",
            "stickman": "3d_red_blue_stickman",
            "red_blue_stickman_3d": "3d_red_blue_stickman",
            "black_white_historical_photography": "bw_vintage_historical_photography",
            "bw_historical_photography": "bw_vintage_historical_photography",
            "quilling": "paper_quilling",
            "paper_quill": "paper_quilling",
            "paper_quilling_illustration": "paper_quilling",
            "collage": "mixed_media_collage",
            "mixed_media": "mixed_media_collage",
            "mixed_media_collage_illustration": "mixed_media_collage",
            "cutout": "paper_cutout",
            "paper_cut": "paper_cutout",
            "paper_cutout_illustration": "paper_cutout",
        }
        if style_id in aliases:
            candidate_ids.append(aliases[style_id])
        if style_id.startswith("custom"):
            candidate_ids.append("custom")

        for cid in candidate_ids:
            for ext in [".png", ".jpg", ".jpeg", ".webp"]:
                cand = ASSETS_DIR / f"{cid}{ext}"
                if cand.exists():
                    preview_path = cand
                    break
            if preview_path:
                break

        # Fallback if not found
        if not preview_path or not preview_path.exists():
            for fallback in ["century_old_photograph.png", "vintage_photograph.png", "3d_red_blue_stickman.png", "bw_vintage_historical_photography.png"]:
                fb = ASSETS_DIR / fallback
                if fb.exists():
                    preview_path = fb
                    break

        if preview_path and preview_path.exists():
            pix = QPixmap(str(preview_path))
            scaled = pix.scaled(620, 350, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.image_preview_lbl.setPixmap(scaled)
            self.image_preview_lbl.setText("")
        else:
            scene_sim = (
                f"<div style='text-align: left; padding: 20px; line-height: 1.6;'>"
                f"<div style='color: #38bdf8; font-size: 16px; font-weight: bold; margin-bottom: 8px;'>Full Scene Visual Archetype: {preset.name}</div>"
                f"<div style='color: #94a3b8; font-size: 12px; margin-bottom: 14px;'>{preset.description}</div>"
                f"<div style='background-color: #0b1120; border: 1px solid #1e293b; border-radius: 6px; padding: 12px; margin-top: 6px;'>"
                f"<div style='color: #f1f5f9; font-weight: 600; font-size: 12px; margin-bottom: 4px;'>Atmospheric Cinematic Frame:</div>"
                f"<div style='color: #cbd5e1; font-size: 11px;'>Full wide environmental composition featuring atmospheric lighting, volumetric depth of field, and authentic period textures. All narrative characters, architectural backgrounds, and lighting color grading are locked into this unified aesthetic.</div>"
                f"</div>"
                f"</div>"
            )
            self.image_preview_lbl.setText(scene_sim)
            self.image_preview_lbl.setStyleSheet("background-color: #020617; border: 1px solid #1e293b; border-radius: 8px;")

    def _on_selector_changed(self, idx: int):
        s_id = self.style_selector.itemData(idx)
        if s_id:
            self._load_style(s_id)

    def _on_prev(self):
        cur_idx = self.style_selector.currentIndex()
        if cur_idx > 0:
            self.style_selector.setCurrentIndex(cur_idx - 1)
        else:
            self.style_selector.setCurrentIndex(self.style_selector.count() - 1)

    def _on_next(self):
        cur_idx = self.style_selector.currentIndex()
        if cur_idx < self.style_selector.count() - 1:
            self.style_selector.setCurrentIndex(cur_idx + 1)
        else:
            self.style_selector.setCurrentIndex(0)

    def _on_copy_prompt(self):
        text = self.prompt_text.toPlainText().strip()
        if text:
            QApplication.clipboard().setText(text)
            self.copy_btn.setText("Copied!")
            self.copy_btn.setStyleSheet("background-color: #065f46; color: #34d399; font-size: 10px; font-weight: bold; border-radius: 4px; padding: 0 10px;")

    def _on_apply(self):
        self.selected_style_id = self.current_style_id
        self.accept()

