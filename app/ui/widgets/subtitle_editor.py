"""
Subtitle Styling & Dynamic Karaoke Customizer Widget.
Features 10 industry-standard creator presets, full color/font customization, and live preview.
"""
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QCheckBox, QColorDialog, QGroupBox,
    QFrame, QButtonGroup, QGridLayout, QListView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from app.models.video_config import SubtitleConfig, SubtitlePreset


from app.ui.widgets.custom_combo import PBComboBox


class SubtitleEditor(QWidget):
    """Interactive subtitle style customizer with 10 presets and live visual preview."""

    config_changed = Signal(object)  # SubtitleConfig

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config = SubtitleConfig()
        self._setup_ui()
        self._apply_preset(SubtitlePreset.HORMOZI_KARAOKE)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        # Header
        header_lbl = QLabel("🔤 Subtitle and Karaoke Styling")
        header_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #f59e0b;")
        layout.addWidget(header_lbl)

        # Preset Selector Grid (2 rows x 5 columns + None)
        preset_group = QGroupBox("10 Subtitle Style Presets")
        preset_layout = QGridLayout(preset_group)
        preset_layout.setContentsMargins(6, 10, 6, 8)
        preset_layout.setSpacing(5)

        self.preset_btn_group = QButtonGroup(self)

        presets = [
            # Row 0
            (SubtitlePreset.HORMOZI_KARAOKE, "🔥 Hormozi", "Bold active word highlight (Impact, Yellow Pop)", 0, 0),
            (SubtitlePreset.CINEMATIC_GOLD, "🎬 Cinematic", "Warm gold highlight, clean soft shadow", 0, 1),
            (SubtitlePreset.NEON_CYBERPUNK, "⚡ Neon Cyber", "Electric cyan/lime glow, navy outline", 0, 2),
            (SubtitlePreset.MRBEAST_BOLD, "💥 MrBeast", "Punchy red & yellow, heavy black stroke", 0, 3),
            (SubtitlePreset.MINIMALIST_CLEAN, "✨ Minimal", "Pure white, clean modern sans", 0, 4),
            # Row 1
            (SubtitlePreset.BOXED_DARK, "⬛ Boxed", "Semi-transparent backdrop box", 1, 0),
            (SubtitlePreset.TIKTOK_POP, "🔮 TikTok Pop", "Pastel pink highlight, bold rounded font", 1, 1),
            (SubtitlePreset.DOCUMENTARY_TOP, "📜 Top Header", "Upper-third gold documentary header", 1, 2),
            (SubtitlePreset.RETRO_SYNTHWAVE, "🚀 Synthwave", "Hot magenta & neon cyan gradient vibe", 1, 3),
            (SubtitlePreset.CLEAN_STORYTELLER, "📖 Storyteller", "Warm cream base, amber highlight", 1, 4),
            (SubtitlePreset.NONE, "🚫 None", "Disable burned-in subtitles", 1, 5),
        ]

        for i, (val, name, tip, row, col) in enumerate(presets):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setToolTip(tip)
            btn.setFixedHeight(26)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(27, 41, 31, 0.68);
                    color: #B1BDB3;
                    border: 1px solid rgba(163, 255, 18, 0.12);
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: 600;
                    padding: 0 4px;
                }
                QPushButton:checked {
                    background-color: #A3FF12;
                    color: #080D0B;
                    border: 1px solid #A3FF12;
                    font-weight: 800;
                }
                QPushButton:hover:!checked {
                    background-color: rgba(40, 57, 43, 0.78);
                    color: #F0F5F0;
                    border-color: rgba(163, 255, 18, 0.35);
                }
            """)
            btn.clicked.connect(lambda _, p=val: self._apply_preset(p))
            self.preset_btn_group.addButton(btn, i)
            preset_layout.addWidget(btn, row, col)
            if val == SubtitlePreset.HORMOZI_KARAOKE:
                btn.setChecked(True)

        layout.addWidget(preset_group)

        # Customization Options Group
        opts_group = QGroupBox("Typography and Colors")
        opts_layout = QVBoxLayout(opts_group)
        opts_layout.setContentsMargins(8, 10, 8, 8)
        opts_layout.setSpacing(6)

        # Row 1: Font & Size
        r1 = QHBoxLayout()
        f_lbl = QLabel("Font:")
        f_lbl.setFixedWidth(36)
        self.font_combo = PBComboBox()
        self.font_combo.addItems(["Impact", "Arial", "Montserrat", "Segoe UI", "Tahoma", "Verdana", "Trebuchet MS", "Georgia"])
        self.font_combo.currentTextChanged.connect(self._on_font_changed)

        s_lbl = QLabel("Size:")
        s_lbl.setFixedWidth(32)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(20, 120)
        self.size_spin.setValue(58)
        self.size_spin.valueChanged.connect(self._on_size_changed)

        r1.addWidget(f_lbl)
        r1.addWidget(self.font_combo)
        r1.addSpacing(8)
        r1.addWidget(s_lbl)
        r1.addWidget(self.size_spin)
        opts_layout.addLayout(r1)

        # Row 2: Colors (Primary Base, Karaoke Highlight, Outline/Shadow)
        r2 = QHBoxLayout()
        self.pri_color_btn = QPushButton("Base Color")
        self.pri_color_btn.setFixedHeight(26)
        self.pri_color_btn.clicked.connect(self._pick_primary_color)
        r2.addWidget(self.pri_color_btn)

        self.hl_color_btn = QPushButton("Karaoke Color")
        self.hl_color_btn.setFixedHeight(26)
        self.hl_color_btn.clicked.connect(self._pick_highlight_color)
        r2.addWidget(self.hl_color_btn)

        self.out_color_btn = QPushButton("Outline Color")
        self.out_color_btn.setFixedHeight(26)
        self.out_color_btn.clicked.connect(self._pick_outline_color)
        r2.addWidget(self.out_color_btn)

        opts_layout.addLayout(r2)

        # Row 3: Karaoke toggle & Vertical margin
        r3 = QHBoxLayout()
        self.karaoke_cb = QCheckBox("Word Karaoke Highlight")
        self.karaoke_cb.setChecked(True)
        self.karaoke_cb.toggled.connect(self._on_karaoke_toggled)

        m_lbl = QLabel("V-Margin:")
        m_lbl.setFixedWidth(55)
        self.margin_spin = QSpinBox()
        self.margin_spin.setRange(10, 300)
        self.margin_spin.setValue(45)
        self.margin_spin.valueChanged.connect(self._on_margin_changed)

        r3.addWidget(self.karaoke_cb)
        r3.addStretch()
        r3.addWidget(m_lbl)
        r3.addWidget(self.margin_spin)
        opts_layout.addLayout(r3)

        layout.addWidget(opts_group)

        # Live Visual Preview Box
        prev_group = QGroupBox("Live Subtitle Preview")
        prev_layout = QVBoxLayout(prev_group)
        prev_layout.setContentsMargins(6, 8, 6, 6)

        self.preview_frame = QFrame()
        self.preview_frame.setFixedHeight(75)
        self.preview_frame.setStyleSheet("background-color: rgba(13, 21, 16, 0.9); border: 1px solid rgba(163, 255, 18, 0.2); border-radius: 6px;")

        pf_layout = QVBoxLayout(self.preview_frame)
        pf_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pf_layout.setContentsMargins(4, 4, 4, 4)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setTextFormat(Qt.TextFormat.RichText)
        pf_layout.addWidget(self.preview_label)

        prev_layout.addWidget(self.preview_frame)
        layout.addWidget(prev_group)

        self._update_color_buttons()
        self._update_preview()

    def _apply_preset(self, preset: SubtitlePreset):
        self.config.preset = preset
        if preset == SubtitlePreset.HORMOZI_KARAOKE:
            self.config.font_name = "Impact"
            self.config.font_size = 58
            self.config.primary_color_hex = "#FFFFFF"
            self.config.highlight_color_hex = "#FFD700"
            self.config.outline_color_hex = "#000000"
            self.config.outline_width = 4
            self.config.alignment = 2
            self.config.margin_v = 45
            self.config.is_karaoke = True
        elif preset == SubtitlePreset.CINEMATIC_GOLD:
            self.config.font_name = "Montserrat"
            self.config.font_size = 52
            self.config.primary_color_hex = "#F8FAFC"
            self.config.highlight_color_hex = "#F59E0B"
            self.config.outline_color_hex = "#0F172A"
            self.config.outline_width = 2
            self.config.alignment = 2
            self.config.margin_v = 40
            self.config.is_karaoke = True
        elif preset == SubtitlePreset.NEON_CYBERPUNK:
            self.config.font_name = "Impact"
            self.config.font_size = 56
            self.config.primary_color_hex = "#10B981"
            self.config.highlight_color_hex = "#06B6D4"
            self.config.outline_color_hex = "#020617"
            self.config.outline_width = 3
            self.config.alignment = 2
            self.config.margin_v = 45
            self.config.is_karaoke = True
        elif preset == SubtitlePreset.MRBEAST_BOLD:
            self.config.font_name = "Impact"
            self.config.font_size = 64
            self.config.primary_color_hex = "#FACC15"
            self.config.highlight_color_hex = "#EF4444"
            self.config.outline_color_hex = "#000000"
            self.config.outline_width = 5
            self.config.alignment = 2
            self.config.margin_v = 50
            self.config.is_karaoke = True
        elif preset == SubtitlePreset.MINIMALIST_CLEAN:
            self.config.font_name = "Segoe UI"
            self.config.font_size = 46
            self.config.primary_color_hex = "#FFFFFF"
            self.config.highlight_color_hex = "#CBD5E1"
            self.config.outline_color_hex = "#1E293B"
            self.config.outline_width = 1
            self.config.alignment = 2
            self.config.margin_v = 35
            self.config.is_karaoke = False
        elif preset == SubtitlePreset.BOXED_DARK:
            self.config.font_name = "Segoe UI"
            self.config.font_size = 48
            self.config.primary_color_hex = "#FFFFFF"
            self.config.highlight_color_hex = "#FBBF24"
            self.config.outline_color_hex = "#000000"
            self.config.outline_width = 2
            self.config.alignment = 2
            self.config.margin_v = 40
            self.config.is_karaoke = True
        elif preset == SubtitlePreset.TIKTOK_POP:
            self.config.font_name = "Montserrat"
            self.config.font_size = 56
            self.config.primary_color_hex = "#FFFFFF"
            self.config.highlight_color_hex = "#F472B6"
            self.config.outline_color_hex = "#581C87"
            self.config.outline_width = 3
            self.config.alignment = 2
            self.config.margin_v = 45
            self.config.is_karaoke = True
        elif preset == SubtitlePreset.DOCUMENTARY_TOP:
            self.config.font_name = "Georgia"
            self.config.font_size = 50
            self.config.primary_color_hex = "#FDE047"
            self.config.highlight_color_hex = "#FFFFFF"
            self.config.outline_color_hex = "#000000"
            self.config.outline_width = 3
            self.config.alignment = 8
            self.config.margin_v = 50
            self.config.is_karaoke = False
        elif preset == SubtitlePreset.RETRO_SYNTHWAVE:
            self.config.font_name = "Impact"
            self.config.font_size = 56
            self.config.primary_color_hex = "#06B6D4"
            self.config.highlight_color_hex = "#EC4899"
            self.config.outline_color_hex = "#3B0764"
            self.config.outline_width = 3
            self.config.alignment = 2
            self.config.margin_v = 45
            self.config.is_karaoke = True
        elif preset == SubtitlePreset.CLEAN_STORYTELLER:
            self.config.font_name = "Tahoma"
            self.config.font_size = 50
            self.config.primary_color_hex = "#FEF08A"
            self.config.highlight_color_hex = "#F59E0B"
            self.config.outline_color_hex = "#1E293B"
            self.config.outline_width = 2
            self.config.alignment = 2
            self.config.margin_v = 40
            self.config.is_karaoke = True

        idx = self.font_combo.findText(self.config.font_name)
        if idx >= 0:
            self.font_combo.setCurrentIndex(idx)
        self.size_spin.setValue(self.config.font_size)
        self.karaoke_cb.setChecked(self.config.is_karaoke)
        self.margin_spin.setValue(self.config.margin_v)

        self._update_color_buttons()
        self._update_preview()
        self.config_changed.emit(self.config)

    def _update_color_buttons(self):
        pri = self.config.primary_color_hex
        hl = self.config.highlight_color_hex
        out = self.config.outline_color_hex

        self.pri_color_btn.setText(f"⚪ Base: {pri}")
        self.pri_color_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #161f36;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-left: 6px solid {pri};
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 6px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: #1e293b;
                border-color: #6366f1;
            }}
        """)

        self.hl_color_btn.setText(f"🟡 Active: {hl}")
        self.hl_color_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #161f36;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-left: 6px solid {hl};
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 6px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: #1e293b;
                border-color: #6366f1;
            }}
        """)

        self.out_color_btn.setText(f"⚫ Border: {out}")
        self.out_color_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #161f36;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-left: 6px solid {out};
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 6px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: #1e293b;
                border-color: #6366f1;
            }}
        """)

    def _update_preview(self):
        if self.config.preset == SubtitlePreset.NONE:
            self.preview_label.setText("<span style='color: #64748b; font-size: 13px;'>[Subtitles Disabled]</span>")
            return

        font = self.config.font_name
        size = min(26, max(14, int(self.config.font_size * 0.42)))
        pri = self.config.primary_color_hex
        hl = self.config.highlight_color_hex
        out = self.config.outline_color_hex

        if self.config.is_karaoke:
            text_html = (
                f"<div style='font-family: {font}; font-size: {size}px; font-weight: bold; text-shadow: 2px 2px 3px {out}; text-align: center;'>"
                f"<span style='color: {pri};'>EVERY </span>"
                f"<span style='color: {hl}; text-decoration: underline;'>SINGLE </span>"
                f"<span style='color: {pri};'>DETAIL COUNTS</span>"
                f"</div>"
            )
        else:
            text_html = (
                f"<div style='font-family: {font}; font-size: {size}px; font-weight: bold; color: {pri}; text-shadow: 2px 2px 3px {out}; text-align: center;'>"
                f"EVERY SINGLE DETAIL COUNTS"
                f"</div>"
            )

        self.preview_label.setText(text_html)

    def _pick_primary_color(self):
        color = QColorDialog.getColor(QColor(self.config.primary_color_hex), self, "Choose Base Subtitle Color")
        if color.isValid():
            self.config.primary_color_hex = color.name()
            self._update_color_buttons()
            self._update_preview()
            self.config_changed.emit(self.config)

    def _pick_highlight_color(self):
        color = QColorDialog.getColor(QColor(self.config.highlight_color_hex), self, "Choose Karaoke Active Color")
        if color.isValid():
            self.config.highlight_color_hex = color.name()
            self._update_color_buttons()
            self._update_preview()
            self.config_changed.emit(self.config)

    def _pick_outline_color(self):
        color = QColorDialog.getColor(QColor(self.config.outline_color_hex), self, "Choose Outline/Shadow Color")
        if color.isValid():
            self.config.outline_color_hex = color.name()
            self._update_color_buttons()
            self._update_preview()
            self.config_changed.emit(self.config)

    def _on_font_changed(self, font_name: str):
        self.config.font_name = font_name
        self._update_preview()
        self.config_changed.emit(self.config)

    def _on_size_changed(self, size: int):
        self.config.font_size = size
        self._update_preview()
        self.config_changed.emit(self.config)

    def _on_karaoke_toggled(self, checked: bool):
        self.config.is_karaoke = checked
        self._update_preview()
        self.config_changed.emit(self.config)

    def _on_margin_changed(self, margin: int):
        self.config.margin_v = margin
        self.config_changed.emit(self.config)

    def get_config(self) -> SubtitleConfig:
        return self.config

    def set_config(self, cfg: SubtitleConfig):
        self.config = cfg
        self._apply_preset(cfg.preset)
