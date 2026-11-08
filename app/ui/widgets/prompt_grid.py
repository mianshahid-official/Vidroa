"""
Prompt Grid and Prompt Card Matrix widget for PromptBeast Studio.
Renders generated scenes as a responsive grid of visual prompt cards matching
the modern production dashboard specification.
"""
from typing import List, Optional
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTextEdit, QLineEdit, QScrollArea, QGridLayout,
    QApplication, QDialog, QDoubleSpinBox, QMessageBox, QDialogButtonBox,
    QComboBox, QProgressBar
)
from app.models.scene import VisualScene
from app.ui.theme import (
    COLOR_BRAND_PRIMARY,
    COLOR_BRAND_EMERALD,
    COLOR_BRAND_MINT,
    COLOR_BG_MAIN,
    COLOR_BG_SECONDARY,
    COLOR_GLASS_SURFACE,
    COLOR_GLASS_SURFACE_2,
    COLOR_HOVER_SURFACE,
    COLOR_BORDER_SUBTLE,
    COLOR_BORDER_GREEN,
    COLOR_BORDER_ACTIVE,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_STATUS_SUCCESS,
    COLOR_STATUS_WARNING,
    COLOR_STATUS_ERROR,
)


class SceneEditDialog(QDialog):
    """Clean dialog to edit a single visual scene prompt, timings, and narration."""

    def __init__(self, scene: VisualScene, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.setWindowTitle(f"✏️ Edit Scene #{scene.scene_id}")
        self.setMinimumWidth(560)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLOR_BG_SECONDARY};
                color: {COLOR_TEXT_PRIMARY};
            }}
            QLabel {{
                color: {COLOR_TEXT_MUTED};
                font-size: 11px;
                font-weight: 600;
            }}
            QLineEdit, QTextEdit, QDoubleSpinBox {{
                background-color: {COLOR_BG_MAIN};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_BORDER_GREEN};
                border-radius: 4px;
                padding: 6px;
                font-size: 12px;
            }}
            QLineEdit:focus, QTextEdit:focus, QDoubleSpinBox:focus {{
                border: 1px solid {COLOR_BRAND_PRIMARY};
            }}
        """)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Timings row
        t_row = QHBoxLayout()
        t_row.addWidget(QLabel("Start (s):"))
        self.start_spin = QDoubleSpinBox()
        self.start_spin.setRange(0.0, 9999.0)
        self.start_spin.setDecimals(2)
        self.start_spin.setValue(self.scene.start)
        t_row.addWidget(self.start_spin)

        t_row.addWidget(QLabel("End (s):"))
        self.end_spin = QDoubleSpinBox()
        self.end_spin.setRange(0.0, 9999.0)
        self.end_spin.setDecimals(2)
        self.end_spin.setValue(self.scene.end)
        t_row.addWidget(self.end_spin)

        t_row.addWidget(QLabel("Duration:"))
        self.dur_lbl = QLabel(f"{self.scene.duration:.2f}s")
        self.dur_lbl.setStyleSheet("color: #34d399; font-weight: bold;")
        t_row.addWidget(self.dur_lbl)
        layout.addLayout(t_row)

        self.start_spin.valueChanged.connect(self._recalc_dur)
        self.end_spin.valueChanged.connect(self._recalc_dur)

        # Visual Subject
        layout.addWidget(QLabel("Visual Subject / Title:"))
        self.subj_input = QLineEdit(self.scene.visual_subject)
        layout.addWidget(self.subj_input)

        # Spoken Narration
        layout.addWidget(QLabel("Spoken Narration Excerpt:"))
        self.narr_edit = QTextEdit()
        self.narr_edit.setFixedHeight(60)
        self.narr_edit.setPlainText(self.scene.narration_excerpt)
        layout.addWidget(self.narr_edit)

        # Full Midjourney Prompt
        layout.addWidget(QLabel("AI Image Generation Prompt (/imagine prompt: ...):"))
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setFixedHeight(120)
        self.prompt_edit.setStyleSheet("font-family: 'Consolas', monospace; font-size: 11px;")
        self.prompt_edit.setPlainText(self.scene.prompt)
        layout.addWidget(self.prompt_edit)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _recalc_dur(self):
        d = max(0.0, self.end_spin.value() - self.start_spin.value())
        self.dur_lbl.setText(f"{d:.2f}s")
        if d > 6.05:
            self.dur_lbl.setStyleSheet("color: #f87171; font-weight: bold;")
        else:
            self.dur_lbl.setStyleSheet("color: #34d399; font-weight: bold;")

    def _save(self):
        s = self.start_spin.value()
        e = self.end_spin.value()
        if e < s:
            QMessageBox.warning(self, "Invalid Timings", "End time cannot precede start time.")
            return

        self.scene.start = s
        self.scene.end = e
        self.scene.duration = round(e - s, 2)
        self.scene.visual_subject = self.subj_input.text().strip()
        self.scene.narration_excerpt = self.narr_edit.toPlainText().strip()
        self.scene.prompt = self.prompt_edit.toPlainText().strip()
        self.scene.is_manually_edited = True
        self.accept()


class PromptCardWidget(QFrame):
    """An individual visual scene card displaying timecode, narration, prompt, and quick actions."""

    copy_requested = Signal(str)      # prompt text
    edit_requested = Signal(object)   # VisualScene
    delete_requested = Signal(str)    # scene_id

    def __init__(self, scene: VisualScene, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.setObjectName("PromptCard")
        self.setStyleSheet(f"""
            QFrame#PromptCard {{
                background-color: {COLOR_GLASS_SURFACE};
                border: 1px solid {COLOR_BORDER_GREEN};
                border-radius: 8px;
                padding: 10px;
            }}
            QFrame#PromptCard:hover {{
                border: 1px solid {COLOR_BORDER_ACTIVE};
                background-color: {COLOR_HOVER_SURFACE};
            }}
        """)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # 1. Card Header: Scene Tag, Timecode, Duration Badge
        hdr = QHBoxLayout()
        hdr.setSpacing(6)

        num_lbl = QLabel(f"#{self.scene.scene_id}")
        num_lbl.setStyleSheet(f"""
            background-color: rgba(163, 255, 18, 0.12);
            color: {COLOR_BRAND_PRIMARY};
            font-size: 11px;
            font-weight: 800;
            padding: 2px 6px;
            border-radius: 4px;
            border: 1px solid rgba(163, 255, 18, 0.25);
        """)
        hdr.addWidget(num_lbl)

        tc_lbl = QLabel(f"{self._format_time(self.scene.start)} - {self._format_time(self.scene.end)}")
        tc_lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; font-family: 'Consolas', monospace;")
        hdr.addWidget(tc_lbl)

        hdr.addStretch()

        # Modality badge
        mod = getattr(self.scene, "visual_modality", "cinematic_scene") or "cinematic_scene"
        mod_colors = {
            "infographic_chart": ("#38BDF8", "#11161D", "CHART"),
            "blueprint_schematic": ("#06b6d4", "#11161D", "BLUEPRINT"),
            "historical_document": ("#d97706", "#11161D", "DOCUMENT"),
            "tactical_map": ("#A3FF12", "#11161D", "MAP"),
            "data_counter": ("#ec4899", "#11161D", "DATA"),
            "cinematic_scene": ("#34D399", "#11161D", "CINEMATIC")
        }
        fg, bg, label_txt = mod_colors.get(mod, ("#34D399", "#11161D", "SCENE"))
        mod_lbl = QLabel(label_txt)
        mod_lbl.setStyleSheet(f"background-color: {bg}; color: {fg}; font-size: 9px; font-weight: 800; padding: 2px 6px; border-radius: 3px; border: 1px solid {fg};")
        hdr.addWidget(mod_lbl)

        # Duration Pill (Dynamic AI pacing)
        dur_lbl = QLabel(f"{self.scene.duration:.2f}s")
        dur_lbl.setStyleSheet(f"""
            background-color: rgba(16, 185, 129, 0.12);
            color: {COLOR_BRAND_MINT};
            font-size: 10px;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 3px;
            border: 1px solid rgba(16, 185, 129, 0.25);
        """)
        hdr.addWidget(dur_lbl)
        layout.addLayout(hdr)

        # 2. Visual Subject & Tags
        title_box = QHBoxLayout()
        title_box.setSpacing(4)
        subj_lbl = QLabel(self.scene.visual_subject or f"Scene {self.scene.scene_id}")
        subj_lbl.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-weight: 700; font-size: 12px;")
        subj_lbl.setWordWrap(True)
        title_box.addWidget(subj_lbl, 1)

        if self.scene.continuity_tags:
            for tag in self.scene.continuity_tags[:2]:
                t_badge = QLabel(tag)
                t_badge.setStyleSheet(f"background-color: {COLOR_GLASS_SURFACE_2}; color: {COLOR_BRAND_MINT}; font-size: 9px; padding: 1px 4px; border-radius: 3px; border: 1px solid {COLOR_BORDER_SUBTLE};")
                title_box.addWidget(t_badge)
        layout.addLayout(title_box)

        # 3. Spoken Narration Excerpt
        narr = self.scene.narration_excerpt.strip()
        if narr:
            narr_lbl = QLabel(f'"{narr}"')
            narr_lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-style: italic; font-size: 11px; line-height: 1.3;")
            narr_lbl.setWordWrap(True)
            narr_lbl.setMaximumHeight(40)
            layout.addWidget(narr_lbl)

        # 4. Monospace Prompt Block (Selectable & Clear Preview)
        self.prompt_box = QTextEdit()
        self.prompt_box.setReadOnly(True)
        self.prompt_box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.prompt_box.setFixedHeight(84)
        prompt_content = self.scene.prompt.strip()
        if prompt_content:
            if not prompt_content.startswith("/imagine"):
                prompt_content = f"/imagine prompt: {prompt_content}"
            self.prompt_box.setStyleSheet(f"""
                QTextEdit {{
                    background-color: {COLOR_BG_MAIN};
                    color: {COLOR_TEXT_PRIMARY};
                    border: 1px solid {COLOR_BORDER_GREEN};
                    border-radius: 4px;
                    padding: 4px;
                    font-family: 'Consolas', 'JetBrains Mono', monospace;
                    font-size: 10px;
                    line-height: 1.3;
                }}
            """)
        else:
            prompt_content = f"[Planned Visual Shot - Awaiting Batch Prompt Gen]\n{self.scene.visual_subject}"
            self.prompt_box.setStyleSheet(f"""
                QTextEdit {{
                    background-color: {COLOR_BG_MAIN};
                    color: {COLOR_TEXT_MUTED};
                    border: 1px dashed {COLOR_BORDER_GREEN};
                    border-radius: 4px;
                    padding: 6px;
                    font-family: 'Consolas', 'JetBrains Mono', monospace;
                    font-size: 10px;
                    font-style: italic;
                    line-height: 1.3;
                }}
            """)
        self.prompt_box.setPlainText(prompt_content)
        layout.addWidget(self.prompt_box)

        # 5. Card Footer Actions
        footer = QHBoxLayout()
        footer.setSpacing(6)

        self.copy_btn = QPushButton("📋 Copy")
        self.copy_btn.setFixedHeight(26)
        self.copy_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_GLASS_SURFACE_2};
                color: {COLOR_BRAND_PRIMARY};
                border: 1px solid {COLOR_BORDER_GREEN};
                border-radius: 4px;
                padding: 0 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: rgba(163, 255, 18, 0.15);
            }}
        """)
        self.copy_btn.clicked.connect(self._on_copy_clicked)
        footer.addWidget(self.copy_btn)

        self.edit_btn = QPushButton("✏️ Edit")
        self.edit_btn.setFixedHeight(26)
        self.edit_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_GLASS_SURFACE_2};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: 4px;
                padding: 0 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLOR_HOVER_SURFACE};
                border-color: {COLOR_BORDER_GREEN};
            }}
        """)
        self.edit_btn.clicked.connect(self._on_edit_clicked)
        footer.addWidget(self.edit_btn)

        footer.addStretch()

        del_btn = QPushButton("🗑️")
        del_btn.setFixedSize(26, 26)
        del_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_GLASS_SURFACE_2};
                color: {COLOR_TEXT_MUTED};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                color: {COLOR_STATUS_ERROR};
                border-color: rgba(255, 100, 124, 0.4);
            }}
        """)
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self.scene.scene_id))
        footer.addWidget(del_btn)

        layout.addLayout(footer)

    def _format_time(self, seconds: float) -> str:
        mins = int(seconds // 60)
        secs = seconds % 60
        return f"{mins:02d}:{secs:05.2f}"

    def _on_copy_clicked(self):
        text = self.prompt_box.toPlainText().strip()
        if not text or text.startswith("[Planned Visual Shot"):
            text = self.scene.visual_subject or f"Scene {self.scene.scene_id}"
        if text:
            QApplication.clipboard().setText(text)
            self.copy_btn.setText("✅ Copied!")
            self.copy_btn.setStyleSheet("background-color: #064e3b; color: #34d399; font-weight: bold; border-radius: 4px; padding: 0 10px; font-size: 11px;")
            QTimer.singleShot(1500, self._reset_copy_btn)

    def _reset_copy_btn(self):
        self.copy_btn.setText("📋 Copy")
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 0 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #0369a1;
                color: #ffffff;
            }
        """)

    def _on_edit_clicked(self):
        dlg = SceneEditDialog(self.scene, self)
        if dlg.exec():
            # Update display
            self.edit_requested.emit(self.scene)


class PromptGridWidget(QWidget):
    """The complete responsive Grid Matrix of generated visual scene prompt cards."""

    scene_updated = Signal(object)
    delete_requested = Signal(str)
    add_scene_requested = Signal()
    export_requested = Signal()
    approve_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scenes: List[VisualScene] = []
        self._card_widgets: List[PromptCardWidget] = []
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        # 1. Top Filter & Action Bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filter prompts or scenes...")
        self.search_input.setFixedHeight(30)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLOR_GLASS_SURFACE_2};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_BORDER_GREEN};
                border-radius: 6px;
                padding: 0 10px;
                font-size: 11px;
            }}
            QLineEdit:focus {{
                border: 1px solid {COLOR_BRAND_PRIMARY};
            }}
        """)
        self.search_input.textChanged.connect(self._apply_filter)
        top_bar.addWidget(self.search_input, 1)

        self.count_badge = QLabel("0 Scenes Planned")
        self.count_badge.setStyleSheet(f"""
            background-color: rgba(163, 255, 18, 0.12);
            color: {COLOR_BRAND_PRIMARY};
            font-size: 11px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 6px;
            border: 1px solid rgba(163, 255, 18, 0.25);
        """)
        top_bar.addWidget(self.count_badge)

        self.pacing_badge = QLabel("Pacing: Dynamic AI Beats")
        self.pacing_badge.setStyleSheet(f"""
            background-color: rgba(16, 185, 129, 0.12);
            color: {COLOR_BRAND_MINT};
            font-size: 11px;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 6px;
            border: 1px solid rgba(16, 185, 129, 0.25);
        """)
        top_bar.addWidget(self.pacing_badge)

        self.approve_btn = QPushButton("✓ Approve & Generate All Prompts")
        self.approve_btn.setFixedHeight(30)
        self.approve_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_BRAND_PRIMARY};
                color: #080D0B;
                font-weight: 800;
                font-size: 11px;
                border-radius: 6px;
                border: none;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                background-color: #B8FF24;
            }}
        """)
        self.approve_btn.clicked.connect(lambda: self.approve_requested.emit())
        self.approve_btn.setVisible(False)
        top_bar.addWidget(self.approve_btn)

        self.batch_combo = QComboBox()
        self.batch_combo.setFixedHeight(30)
        self.batch_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLOR_GLASS_SURFACE_2};
                color: {COLOR_BRAND_PRIMARY};
                border: 1px solid {COLOR_BORDER_GREEN};
                border-radius: 6px;
                padding: 0 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background-color: {COLOR_BG_SECONDARY};
                color: {COLOR_TEXT_PRIMARY};
                selection-background-color: {COLOR_HOVER_SURFACE};
            }}
        """)
        self.batch_combo.setVisible(False)
        top_bar.addWidget(self.batch_combo)

        self.copy_all_btn = QPushButton("📋 Copy All Prompts")
        self.copy_all_btn.setFixedHeight(30)
        self.copy_all_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_BRAND_PRIMARY};
                color: #080D0B;
                border: none;
                border-radius: 6px;
                padding: 0 14px;
                font-size: 11px;
                font-weight: 800;
            }}
            QPushButton:hover {{
                background-color: #B8FF24;
            }}
        """)
        self.copy_all_btn.clicked.connect(self._on_copy_all)
        top_bar.addWidget(self.copy_all_btn)

        self.export_btn = QPushButton("📁 Export...")
        self.export_btn.setFixedHeight(30)
        self.export_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_GLASS_SURFACE_2};
                color: {COLOR_BRAND_MINT};
                border: 1px solid {COLOR_BORDER_GREEN};
                border-radius: 6px;
                padding: 0 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLOR_HOVER_SURFACE};
                border-color: {COLOR_BRAND_PRIMARY};
            }}
        """)
        self.export_btn.clicked.connect(lambda: self.export_requested.emit())
        top_bar.addWidget(self.export_btn)

        self.add_btn = QPushButton("➕ Add Scene")
        self.add_btn.setFixedHeight(30)
        self.add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_GLASS_SURFACE_2};
                color: {COLOR_BRAND_EMERALD};
                border: 1px solid rgba(16, 185, 129, 0.3);
                border-radius: 6px;
                padding: 0 12px;
                font-size: 11px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: rgba(16, 185, 129, 0.2);
                border-color: {COLOR_BRAND_EMERALD};
            }}
        """)
        self.add_btn.clicked.connect(lambda: self.add_scene_requested.emit())
        top_bar.addWidget(self.add_btn)

        root.addLayout(top_bar)

        # 1.5 Realtime Progress Panel (Visible during prompt generation / Groq requests)
        self.live_progress_panel = QFrame()
        self.live_progress_panel.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(18, 30, 22, 0.95);
                border: 1px solid rgba(163, 255, 18, 0.35);
                border-radius: 8px;
                padding: 8px 12px;
            }}
        """)
        lp_layout = QVBoxLayout(self.live_progress_panel)
        lp_layout.setContentsMargins(10, 6, 10, 6)
        lp_layout.setSpacing(6)

        lp_top_row = QHBoxLayout()
        self.spinner_lbl = QLabel("◐")
        self.spinner_lbl.setStyleSheet(f"color: {COLOR_BRAND_PRIMARY}; font-size: 16px; font-weight: 800;")
        lp_top_row.addWidget(self.spinner_lbl)

        self.progress_msg_lbl = QLabel("⚡ Sending requests to Groq API... Generating prompts...")
        self.progress_msg_lbl.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 12px; font-weight: 700;")
        lp_top_row.addWidget(self.progress_msg_lbl, 1)

        self.progress_pct_lbl = QLabel("0%")
        self.progress_pct_lbl.setStyleSheet(f"color: {COLOR_BRAND_PRIMARY}; font-size: 12px; font-weight: 800; font-family: monospace;")
        lp_top_row.addWidget(self.progress_pct_lbl)
        lp_layout.addLayout(lp_top_row)

        self.live_progress_bar = QProgressBar()
        self.live_progress_bar.setFixedHeight(8)
        self.live_progress_bar.setRange(0, 100)
        self.live_progress_bar.setValue(0)
        self.live_progress_bar.setTextVisible(False)
        self.live_progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(13, 21, 16, 0.9);
                border: 1px solid rgba(163, 255, 18, 0.2);
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #A3FF12);
                border-radius: 3px;
            }}
        """)
        lp_layout.addWidget(self.live_progress_bar)

        self.live_progress_panel.setVisible(False)
        root.addWidget(self.live_progress_panel)

        self._spinner_frames = ["◐", "◓", "◑", "◒"]
        self._spinner_idx = 0
        self._spinner_timer = QTimer(self)
        self._spinner_timer.setInterval(180)
        self._spinner_timer.timeout.connect(self._rotate_spinner)

        # 2. Scrollable Grid Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("background-color: transparent;")

        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(0, 4, 0, 4)
        self.grid_layout.setSpacing(10)

        # Empty State Placeholder
        self.empty_label = QLabel(
            "⚡ <b>Ready to Generate Visual Storyboard</b><br><br>"
            "<span style='color: #64748b;'>Paste or load your story script above, select your Visual Style Preset and Subject Domain, "
            "then click <b>'GENERATE STORYBOARD + PROMPTS'</b>.<br>"
            "All generated image prompts will appear here in this responsive prompt card matrix.</span>"
        )
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("""
            background-color: #080c14;
            color: #38bdf8;
            font-size: 13px;
            border: 1px dashed #1e293b;
            border-radius: 8px;
            padding: 40px 20px;
        """)
        self.grid_layout.addWidget(self.empty_label, 0, 0, 1, 3)

        self.scroll_area.setWidget(self.grid_container)
        self.scroll_area.setMinimumHeight(450)
        root.addWidget(self.scroll_area)

    def _rotate_spinner(self):
        self._spinner_idx = (self._spinner_idx + 1) % len(self._spinner_frames)
        self.spinner_lbl.setText(self._spinner_frames[self._spinner_idx])

    def show_progress(self, message: str, percentage: float = 0.0):
        self.progress_msg_lbl.setText(message)
        pct = max(0, min(100, int(percentage)))
        self.progress_pct_lbl.setText(f"{pct}%")
        self.live_progress_bar.setValue(pct)
        self.live_progress_panel.setVisible(True)
        if not self._spinner_timer.isActive():
            self._spinner_timer.start()

    def update_progress(self, message: str, percentage: float):
        if message:
            self.progress_msg_lbl.setText(message)
        pct = max(0, min(100, int(percentage)))
        self.progress_pct_lbl.setText(f"{pct}%")
        self.live_progress_bar.setValue(pct)
        if not self.live_progress_panel.isVisible():
            self.live_progress_panel.setVisible(True)
        if not self._spinner_timer.isActive():
            self._spinner_timer.start()

    def hide_progress(self):
        self._spinner_timer.stop()
        self.live_progress_panel.setVisible(False)

    def load_scenes(self, scenes: List[VisualScene]):
        """Populates the grid with prompt cards for all scenes."""
        self.scenes = scenes or []
        self._update_batch_combo()
        self._rebuild_grid()

    def _update_batch_combo(self):
        if not hasattr(self, "batch_combo"):
            return
        total = len(self.scenes)
        self.batch_combo.clear()
        if total > 100:
            self.batch_combo.addItem(f"All Prompts (1–{total})", (0, total))
            batch_size = 100
            for b_idx in range(0, total, batch_size):
                acc_num = (b_idx // batch_size) + 1
                start_n = b_idx + 1
                end_n = min(b_idx + batch_size, total)
                self.batch_combo.addItem(f"Acc {acc_num} ({start_n}–{end_n})", (b_idx, end_n))
            self.batch_combo.setVisible(True)
            self.copy_all_btn.setText("📋 Copy Prompts")
        else:
            self.batch_combo.setVisible(False)
            self.copy_all_btn.setText("📋 Copy All Prompts")

    def _rebuild_grid(self):
        # Clear existing items cleanly
        while self.grid_layout.count() > 0:
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        self._card_widgets.clear()
        count = len(self.scenes)
        self.count_badge.setText(f"{count} Scenes Planned (100% Validated)")

        # Show approve button if there are planned scenes awaiting prompt generation
        has_unprompted = any(
            not (s.prompt and s.prompt.strip()) or
            "[Planned Visual Shot" in (s.prompt or "") or
            "Awaiting Batch Prompt Gen" in (s.prompt or "")
            for s in self.scenes
        )
        self.approve_btn.setVisible(count > 0 and has_unprompted)

        if count == 0:
            self.empty_label = QLabel(
                f"⚡ <b style='color: {COLOR_BRAND_PRIMARY};'>Ready to Generate Visual Storyboard</b><br><br>"
                f"<span style='color: {COLOR_TEXT_SECONDARY};'>Paste or load your story script in Production, select your Visual Style Preset, "
                f"then click <b style='color: {COLOR_BRAND_PRIMARY};'>'Plan Storyboard & Audio'</b>.<br>"
                "All generated visual scene prompts will appear here in this responsive green glass prompt card matrix.</span>"
            )
            self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.empty_label.setStyleSheet(f"""
                background-color: {COLOR_GLASS_SURFACE};
                color: {COLOR_BRAND_MINT};
                font-size: 13px;
                border: 1px dashed {COLOR_BORDER_GREEN};
                border-radius: 8px;
                padding: 40px 20px;
            """)
            self.grid_layout.addWidget(self.empty_label, 0, 0, 1, 3)
            return

        cols = 3  # Responsive 3 cards per row
        start_row = 0

        # Dedicated YouTube Thumbnail Banner at the top of the Studio Matrix
        win = self.window()
        proj = getattr(win, "project", None)
        th_head = getattr(proj.state, "thumbnail_headline", "") if proj and hasattr(proj, "state") else ""
        th_prompt = getattr(proj.state, "thumbnail_prompt", "") if proj and hasattr(proj, "state") else ""

        if th_head and (not th_prompt or th_head not in th_prompt):
            try:
                from app.core.thumbnail_prompt_builder import build_viral_thumbnail_prompt
                sid = getattr(proj.state, "style_preset_id", "3d_red_blue_stickman") if proj and hasattr(proj, "state") else "3d_red_blue_stickman"
                th_prompt = build_viral_thumbnail_prompt(headline=th_head, style_id=sid)
                if proj and hasattr(proj, "state"):
                    proj.state.thumbnail_prompt = th_prompt
            except Exception as e:
                print(f"[Studio] Notice generating thumbnail prompt: {e}")

        if th_head or th_prompt:
            th_frame = QFrame()
            th_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {COLOR_GLASS_SURFACE};
                    border: 1px solid {COLOR_BORDER_GREEN};
                    border-radius: 8px;
                    padding: 8px 12px;
                    margin-bottom: 6px;
                }}
            """)
            th_lay = QHBoxLayout(th_frame)
            th_lay.setContentsMargins(8, 6, 8, 6)
            th_lay.setSpacing(10)

            t_icon = QLabel("🎯 <b>YOUTUBE THUMBNAIL</b>")
            t_icon.setStyleSheet(f"color: {COLOR_BRAND_PRIMARY}; font-size: 11px; font-weight: 800;")
            th_lay.addWidget(t_icon)

            if th_head:
                h_lbl = QLabel(f"<b>TEXT:</b> <span style='color: {COLOR_TEXT_PRIMARY};'>{th_head}</span>")
                h_lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px;")
                th_lay.addWidget(h_lbl)

            th_lay.addStretch()

            if th_prompt:
                btn_copy_th = QPushButton("📋 Copy Thumbnail Prompt")
                btn_copy_th.setFixedHeight(26)
                btn_copy_th.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {COLOR_GLASS_SURFACE_2}; color: {COLOR_BRAND_PRIMARY}; font-size: 10px; font-weight: 700;
                        border: 1px solid {COLOR_BORDER_GREEN}; border-radius: 4px; padding: 0 10px;
                    }}
                    QPushButton:hover {{ background-color: rgba(163, 255, 18, 0.15); }}
                """)
                def _do_copy():
                    QApplication.clipboard().setText(th_prompt)
                    btn_copy_th.setText("✓ Copied!")
                    QTimer.singleShot(2000, lambda: btn_copy_th.setText("📋 Copy Thumbnail Prompt"))
                btn_copy_th.clicked.connect(_do_copy)
                th_lay.addWidget(btn_copy_th)

            self.grid_layout.addWidget(th_frame, 0, 0, 1, cols)
            start_row = 1

        for i, sc in enumerate(self.scenes):
            card = PromptCardWidget(sc)
            card.edit_requested.connect(self._on_card_edited)
            card.delete_requested.connect(self._on_card_deleted)
            row = start_row + (i // cols)
            col = i % cols
            self.grid_layout.addWidget(card, row, col)
            self._card_widgets.append(card)

        # Set column stretch
        for c in range(cols):
            self.grid_layout.setColumnStretch(c, 1)

    def _apply_filter(self, text: str):
        q = text.strip().lower()
        visible_count = 0
        for card in self._card_widgets:
            sc = card.scene
            match = (
                not q
                or q in sc.scene_id.lower()
                or q in sc.visual_subject.lower()
                or q in sc.narration_excerpt.lower()
                or q in sc.prompt.lower()
            )
            card.setVisible(match)
            if match:
                visible_count += 1
        self.count_badge.setText(f"{visible_count} of {len(self.scenes)} Scenes")

    def _on_card_edited(self, scene: VisualScene):
        self.scene_updated.emit(scene)

    def _on_card_deleted(self, scene_id: str):
        self.delete_requested.emit(scene_id)

    def _on_copy_all(self):
        if not self.scenes:
            QMessageBox.information(self, "No Scenes", "There are no prompts to copy.")
            return

        target_scenes = self.scenes
        batch_label = "All"
        is_first_batch = True
        if hasattr(self, "batch_combo") and self.batch_combo.isVisible():
            data = self.batch_combo.currentData()
            if data and isinstance(data, (tuple, list)):
                s_idx, e_idx = data
                target_scenes = self.scenes[s_idx:e_idx]
                batch_label = self.batch_combo.currentText().split()[0]
                if s_idx > 0:
                    is_first_batch = False

        win = self.window()
        proj = getattr(win, "project", None)
        th_p = getattr(proj.state, "thumbnail_prompt", "") if proj and hasattr(proj, "state") else ""
        th_h = getattr(proj.state, "thumbnail_headline", "") if proj and hasattr(proj, "state") else ""
        sid = getattr(proj.state, "style_preset_id", "3d_red_blue_stickman") if proj and hasattr(proj, "state") else "3d_red_blue_stickman"

        if not th_h:
            if proj and hasattr(proj, "state") and getattr(proj.state, "analysis", None):
                th_h = getattr(proj.state.analysis, "thumbnail_headline", "")
            if not th_h:
                th_h = "CONSTANTINOPLE FALLS"

        if is_first_batch:
            try:
                from app.core.thumbnail_prompt_builder import build_viral_thumbnail_prompt
                is_stickman = "stickman" in sid.lower() or "3d_red_blue" in sid.lower()
                th_p_is_stickman = "stickman" in th_p.lower() if th_p else False
                if not th_p or (is_stickman != th_p_is_stickman) or (th_h not in th_p):
                    th_p = build_viral_thumbnail_prompt(headline=th_h, style_id=sid)
                    if proj and hasattr(proj, "state"):
                        proj.state.thumbnail_headline = th_h
                        proj.state.thumbnail_prompt = th_p
            except Exception as e:
                print(f"[Studio] Notice generating thumbnail prompt for batch: {e}")

        lines = []
        from app.core.export import StoryboardExporter

        # YouTube Thumbnail is ALWAYS placed at #1 (Batch Image 01)
        if is_first_batch and th_p:
            clean_th = StoryboardExporter.clean_prompt_single_line(th_p)
            if clean_th:
                lines.append(clean_th)

        for s in target_scenes:
            raw_p = s.prompt.strip() if s.prompt else (s.visual_subject or "")
            # Clean out any unprompted placeholder text before copying
            raw_p = re.sub(r"\[Planned Visual Shot\s*[—-]\s*Awaiting Batch Prompt Gen\]\s*", "", raw_p, flags=re.IGNORECASE).strip()
            if not raw_p:
                raw_p = s.visual_subject or s.narration_excerpt or ""
            clean_p = StoryboardExporter.clean_prompt_single_line(raw_p)
            if clean_p:
                lines.append(clean_p)

        full_text = "\n".join(lines)
        QApplication.clipboard().setText(full_text)

        # Explicit verification: confirm Windows clipboard matches expected payload
        verified = QApplication.clipboard().text()
        if verified != full_text:
            QMessageBox.critical(
                self,
                "Clipboard Copy Error",
                "Windows clipboard verification failed. Could not copy prompts."
            )
            return

        copied_cnt = len(lines)
        self.copy_all_btn.setText(f"✅ Copied {copied_cnt} Prompts ({batch_label})!")
        self.copy_all_btn.setStyleSheet("background-color: #064e3b; color: #34d399; font-weight: bold; border-radius: 6px; padding: 0 12px; font-size: 11px;")
        QTimer.singleShot(2500, lambda: self.copy_all_btn.setText("📋 Copy Prompts" if len(self.scenes) > 100 else "📋 Copy All Prompts"))

