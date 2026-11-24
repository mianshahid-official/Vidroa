"""
Prompt Grid and Prompt Card Matrix widget for PromptBeast Studio.
Renders generated scenes as a responsive grid of visual prompt cards matching
the modern production dashboard specification.
"""
import re
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
        self.dur_lbl.setStyleSheet("color: #FF4B4B; font-weight: bold;")
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

        # Full Clean AI Generation Prompt
        layout.addWidget(QLabel("AI Image Generation Prompt:"))
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
            self.dur_lbl.setStyleSheet("color: #FF5252; font-weight: bold;")
        else:
            self.dur_lbl.setStyleSheet("color: #FF4B4B; font-weight: bold;")

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
    retry_requested = Signal(object)   # VisualScene

    def __init__(self, scene: VisualScene, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.setObjectName("PromptCard")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self._build_card(layout)

    def update_scene(self, scene: VisualScene):
        """Refreshes the card in-place with new scene prompt data."""
        self.scene = scene
        layout = self.layout()
        if layout:
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    while item.layout().count():
                        sub = item.layout().takeAt(0)
                        if sub.widget():
                            sub.widget().deleteLater()
            self._build_card(layout)
        else:
            self._setup_ui()

    def _build_card(self, layout):
        is_error = getattr(self.scene, "generation_status", "") == "error"

        if is_error:
            self.setStyleSheet("""
                QFrame#PromptCard {
                    background-color: rgba(36, 12, 12, 0.95);
                    border: 1px solid #EF4444;
                    border-radius: 8px;
                    padding: 10px;
                }
                QFrame#PromptCard:hover {
                    border: 1px solid #F87171;
                    background-color: rgba(50, 16, 16, 0.95);
                }
            """)
        else:
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

        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # 1. Card Header: Scene Tag, Timecode, Duration Badge
        hdr = QHBoxLayout()
        hdr.setSpacing(6)

        num_lbl = QLabel(f"#{self.scene.scene_id}")
        num_lbl.setStyleSheet(f"""
            background-color: {"rgba(239, 68, 68, 0.2)" if is_error else "rgba(229, 57, 53, 0.15)"};
            color: {"#F87171" if is_error else "#FF4B4B"};
            font-size: 11px;
            font-weight: 800;
            padding: 2px 6px;
            border-radius: 4px;
            border: 1px solid {"rgba(239, 68, 68, 0.4)" if is_error else "rgba(229, 57, 53, 0.30)"};
        """)
        hdr.addWidget(num_lbl)

        tc_lbl = QLabel(f"{self._format_time(self.scene.start)} - {self._format_time(self.scene.end)}")
        tc_lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; font-family: 'Consolas', monospace;")
        hdr.addWidget(tc_lbl)

        hdr.addStretch()

        if is_error:
            err_badge = QLabel("⚠️ RETRY NEEDED")
            err_badge.setStyleSheet("background-color: #EF4444; color: #FFFFFF; font-size: 9px; font-weight: 800; padding: 2px 6px; border-radius: 3px;")
            hdr.addWidget(err_badge)

        # Modality badge
        mod = getattr(self.scene, "visual_modality", "cinematic_scene") or "cinematic_scene"
        mod_colors = {
            "infographic_chart": ("#FF6B6B", "#1F1515", "CHART"),
            "blueprint_schematic": ("#FF5252", "#1F1515", "BLUEPRINT"),
            "historical_document": ("#E53935", "#1F1515", "DOCUMENT"),
            "tactical_map": ("#FF7070", "#1F1515", "MAP"),
            "data_counter": ("#EF4444", "#1F1515", "DATA"),
            "cinematic_scene": ("#E53935", "#1F1515", "CINEMATIC")
        }
        fg, bg, label_txt = mod_colors.get(mod, ("#E53935", "#1F1515", "SCENE"))
        mod_lbl = QLabel(label_txt)
        mod_lbl.setStyleSheet(f"background-color: {bg}; color: {fg}; font-size: 9px; font-weight: 800; padding: 2px 6px; border-radius: 3px; border: 1px solid {fg};")
        hdr.addWidget(mod_lbl)

        # Duration Pill (Dynamic AI pacing)
        dur_lbl = QLabel(f"{self.scene.duration:.2f}s")
        dur_lbl.setStyleSheet("""
            background-color: rgba(229, 57, 53, 0.12);
            color: #FF4B4B;
            font-size: 10px;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 3px;
            border: 1px solid rgba(229, 57, 53, 0.25);
        """)
        hdr.addWidget(dur_lbl)
        layout.addLayout(hdr)

        # 2. Visual Subject & Tags
        title_box = QHBoxLayout()
        title_box.setSpacing(4)
        full_subj = getattr(self.scene, "visual_idea", "") or self.scene.visual_subject or f"Scene {self.scene.scene_id}"
        subj_lbl = QLabel(full_subj)
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
        prompt_content = (self.scene.prompt or "").strip()

        if is_error:
            self.prompt_box.setPlainText(
                f"[Prompt Generation Skipped / Rate Limited]\n"
                f"Subject: {full_subj}\n\n"
                f"Click '🔄 Retry Prompt' below to generate this single scene prompt via Groq."
            )
            self.prompt_box.setStyleSheet("""
                QTextEdit {
                    background-color: #1A0A0A;
                    color: #F87171;
                    border: 1px dashed #EF4444;
                    border-radius: 4px;
                    padding: 6px;
                    font-family: 'Consolas', 'JetBrains Mono', monospace;
                    font-size: 10px;
                    font-style: italic;
                    line-height: 1.3;
                }
            """)
        elif prompt_content:
            prompt_content = re.sub(r"^/imagine\s+prompt:\s*", "", prompt_content, flags=re.IGNORECASE)
            prompt_content = re.sub(r"^/imagine\s*", "", prompt_content, flags=re.IGNORECASE)
            prompt_content = re.sub(r"--ar\s+\d+:\d+", "", prompt_content, flags=re.IGNORECASE)
            prompt_content = re.sub(r"--style\s+\w+", "", prompt_content, flags=re.IGNORECASE)
            prompt_content = " ".join(prompt_content.split())
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
            self.prompt_box.setPlainText(prompt_content)
        else:
            full_idea = getattr(self.scene, "visual_idea", "") or self.scene.visual_subject or "Planned visual scene."
            prompt_content = f"[Planned Visual Shot - Awaiting Batch Prompt Gen]\n{full_idea}"
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

        if is_error:
            self.retry_btn = QPushButton("🔄 Retry Prompt")
            self.retry_btn.setFixedHeight(26)
            self.retry_btn.setStyleSheet("""
                QPushButton {
                    background-color: #DC2626;
                    color: #FFFFFF;
                    font-weight: 800;
                    font-size: 11px;
                    border-radius: 4px;
                    border: none;
                    padding: 0 12px;
                }
                QPushButton:hover {
                    background-color: #EF4444;
                }
                QPushButton:disabled {
                    background-color: #7F1D1D;
                    color: #D1D5DB;
                }
            """)
            self.retry_btn.clicked.connect(self._on_retry_clicked)
            footer.addWidget(self.retry_btn)
        else:
            self.copy_btn = QPushButton("📋 Copy")
            self.copy_btn.setFixedHeight(26)
            self.copy_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLOR_GLASS_SURFACE_2};
                    color: #FF4B4B;
                    border: 1px solid rgba(229, 57, 53, 0.35);
                    border-radius: 4px;
                    padding: 0 10px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: rgba(229, 57, 53, 0.15);
                    border-color: #E53935;
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

            if getattr(self.scene, "is_video", False) and getattr(self.scene, "video_candidates", None):
                self.reroll_btn = QPushButton("🎲 Re-roll")
                self.reroll_btn.setFixedHeight(26)
                self.reroll_btn.setToolTip("Swap in the next downloaded candidate video clip")
                self.reroll_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {COLOR_GLASS_SURFACE_2};
                        color: #00D2FF;
                        border: 1px solid rgba(0, 210, 255, 0.4);
                        border-radius: 4px;
                        padding: 0 8px;
                        font-size: 11px;
                        font-weight: 600;
                    }}
                    QPushButton:hover {{
                        background-color: rgba(0, 210, 255, 0.15);
                        border-color: #00D2FF;
                    }}
                """)
                self.reroll_btn.clicked.connect(self._on_reroll_video)
                footer.addWidget(self.reroll_btn)

            is_app = getattr(self.scene, "is_approved", False) or getattr(self.scene, "video_approved", False)
            btn_txt = "★ Approved" if is_app else ("✓ Approve Video" if getattr(self.scene, "is_video", False) else "✓ Approve")
            self.card_approve_btn = QPushButton(btn_txt)
            self.card_approve_btn.setFixedHeight(26)
            self.card_approve_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {"rgba(229, 57, 53, 0.20)" if is_app else COLOR_GLASS_SURFACE_2};
                    color: {"#FF4B4B" if is_app else COLOR_TEXT_SECONDARY};
                    border: 1px solid {"#E53935" if is_app else COLOR_BORDER_SUBTLE};
                    border-radius: 4px;
                    padding: 0 8px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    border-color: #FF4B4B;
                    color: #FFFFFF;
                }}
            """)
            self.card_approve_btn.clicked.connect(self._toggle_approved)
            footer.addWidget(self.card_approve_btn)

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

    def _on_retry_clicked(self):
        if hasattr(self, "retry_btn"):
            self.retry_btn.setEnabled(False)
            self.retry_btn.setText("⏳ Retrying...")
        self.retry_requested.emit(self.scene)

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
            self.copy_btn.setText("✓ Copied!")
            self.copy_btn.setStyleSheet("background-color: #222222; color: #FF4B4B; border: 1px solid #E53935; font-weight: bold; border-radius: 4px; padding: 0 10px; font-size: 11px;")
            QTimer.singleShot(1500, self._reset_copy_btn)

    def _reset_copy_btn(self):
        self.copy_btn.setText("📋 Copy")
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #222222;
                color: #F5F5F5;
                border: 1px solid #333333;
                border-radius: 4px;
                padding: 0 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #292929;
                border-color: #E53935;
                color: #FFFFFF;
            }
        """)

    def _on_edit_clicked(self):
        dlg = SceneEditDialog(self.scene, self)
        if dlg.exec():
            # Update display
            self.edit_requested.emit(self.scene)

    def _on_reroll_video(self):
        from app.core.video_worker import VideoWorker
        swapped = VideoWorker.re_roll_candidate(self.scene)
        if swapped:
            self.scene.is_approved = False
            self.scene.video_approved = False
            if hasattr(self, "card_approve_btn"):
                self.card_approve_btn.setText("✓ Approve Video")
                self.card_approve_btn.setStyleSheet(f"background-color: {COLOR_GLASS_SURFACE_2}; color: {COLOR_TEXT_SECONDARY}; border: 1px solid {COLOR_BORDER_SUBTLE}; border-radius: 4px; padding: 0 8px; font-size: 11px; font-weight: 600;")
            fname = Path(self.scene.video_path).name if self.scene.video_path else ""
            self.prompt_box.setPlainText(f"[B-Roll Video Clip] {self.scene.video_shot_description or self.scene.visual_subject}\nActive candidate: {fname}")
            self.edit_requested.emit(self.scene)

    def _toggle_approved(self):
        curr = getattr(self.scene, "is_approved", False) or getattr(self.scene, "video_approved", False)
        new_val = not curr
        self.scene.is_approved = new_val
        self.scene.video_approved = new_val
        is_vid = getattr(self.scene, "is_video", False)
        if self.scene.is_approved:
            self.scene.generation_status = "approved"
            self.card_approve_btn.setText("★ Approved")
            self.card_approve_btn.setStyleSheet("background-color: rgba(229, 57, 53, 0.20); color: #FF4B4B; border: 1px solid #E53935; border-radius: 4px; padding: 0 8px; font-size: 11px; font-weight: 700;")
        else:
            self.scene.generation_status = "generated" if not is_vid else "video_ready"
            self.card_approve_btn.setText("✓ Approve Video" if is_vid else "✓ Approve")
            self.card_approve_btn.setStyleSheet(f"background-color: {COLOR_GLASS_SURFACE_2}; color: {COLOR_TEXT_SECONDARY}; border: 1px solid {COLOR_BORDER_SUBTLE}; border-radius: 4px; padding: 0 8px; font-size: 11px; font-weight: 600;")
        self.edit_requested.emit(self.scene)


class PromptGridWidget(QWidget):
    """The complete responsive Grid Matrix of generated visual scene prompt cards."""

    scene_updated = Signal(object)
    delete_requested = Signal(str)
    add_scene_requested = Signal()
    export_requested = Signal()
    open_file_requested = Signal()
    approve_requested = Signal()
    retry_scene_requested = Signal(object)  # VisualScene

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
        self.count_badge.setStyleSheet("""
            background-color: rgba(229, 57, 53, 0.12);
            color: #FF4B4B;
            font-size: 11px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 6px;
            border: 1px solid rgba(229, 57, 53, 0.30);
        """)
        top_bar.addWidget(self.count_badge)

        self.pacing_badge = QLabel("Pacing: Dynamic AI Beats")
        self.pacing_badge.setStyleSheet("""
            background-color: #1A1A1A;
            color: #CCCCCC;
            font-size: 11px;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 6px;
            border: 1px solid #333333;
        """)
        top_bar.addWidget(self.pacing_badge)

        self.approve_btn = QPushButton("✓ Approve & Generate All Prompts")
        self.approve_btn.setFixedHeight(30)
        self.approve_btn.setStyleSheet("""
            QPushButton {
                background-color: #E53935;
                color: #FFFFFF;
                font-weight: 800;
                font-size: 11px;
                border-radius: 6px;
                border: none;
                padding: 0 14px;
            }
            QPushButton:hover {
                background-color: #FF4B4B;
            }
        """)
        self.approve_btn.clicked.connect(lambda: self.approve_requested.emit())
        self.approve_btn.setVisible(False)
        top_bar.addWidget(self.approve_btn)

        self.batch_combo = QComboBox()
        self.batch_combo.setFixedHeight(30)
        self.batch_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLOR_GLASS_SURFACE_2};
                color: #FFFFFF;
                border: 1px solid #333333;
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
        self.copy_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #E53935;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 0 14px;
                font-size: 11px;
                font-weight: 800;
            }
            QPushButton:hover {
                background-color: #FF4B4B;
            }
        """)
        self.copy_all_btn.clicked.connect(self._on_copy_all)
        top_bar.addWidget(self.copy_all_btn)

        self.export_btn = QPushButton("📁 Export...")
        self.export_btn.setFixedHeight(30)
        self.export_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_GLASS_SURFACE_2};
                color: #E0E0E0;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 0 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLOR_HOVER_SURFACE};
                border-color: #E53935;
                color: #FFFFFF;
            }}
        """)
        self.export_btn.clicked.connect(lambda: self.export_requested.emit())
        top_bar.addWidget(self.export_btn)

        self.open_file_btn = QPushButton("📄 Open Prompts File")
        self.open_file_btn.setFixedHeight(30)
        self.open_file_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_GLASS_SURFACE_2};
                color: #E2E8F0;
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: 6px;
                padding: 0 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLOR_HOVER_SURFACE};
                border-color: {COLOR_BRAND_PRIMARY};
                color: #FFFFFF;
            }}
        """)
        self.open_file_btn.clicked.connect(lambda: self.open_file_requested.emit())
        top_bar.addWidget(self.open_file_btn)

        self.add_btn = QPushButton("➕ Add Scene")
        self.add_btn.setFixedHeight(30)
        self.add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_GLASS_SURFACE_2};
                color: #FF4B4B;
                border: 1px solid rgba(229, 57, 53, 0.35);
                border-radius: 6px;
                padding: 0 12px;
                font-size: 11px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: rgba(229, 57, 53, 0.15);
                border-color: #E53935;
                color: #FFFFFF;
            }}
        """)
        self.add_btn.clicked.connect(lambda: self.add_scene_requested.emit())
        top_bar.addWidget(self.add_btn)

        root.addLayout(top_bar)

        # 1.5 Realtime Progress Panel (Visible during prompt generation / Groq requests)
        self.live_progress_panel = QFrame()
        self.live_progress_panel.setStyleSheet("""
            QFrame {
                background-color: #141414;
                border: 1px solid rgba(229, 57, 53, 0.35);
                border-radius: 8px;
                padding: 8px 12px;
            }
        """)
        lp_layout = QVBoxLayout(self.live_progress_panel)
        lp_layout.setContentsMargins(10, 6, 10, 6)
        lp_layout.setSpacing(6)

        lp_top_row = QHBoxLayout()
        self.spinner_lbl = QLabel("◐")
        self.spinner_lbl.setStyleSheet("color: #E53935; font-size: 16px; font-weight: 800;")
        lp_top_row.addWidget(self.spinner_lbl)

        self.progress_msg_lbl = QLabel("⚡ Sending requests to Groq API... Generating prompts...")
        self.progress_msg_lbl.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 12px; font-weight: 700;")
        lp_top_row.addWidget(self.progress_msg_lbl, 1)

        self.progress_pct_lbl = QLabel("0%")
        self.progress_pct_lbl.setStyleSheet("color: #FF4B4B; font-size: 12px; font-weight: 800; font-family: monospace;")
        lp_top_row.addWidget(self.progress_pct_lbl)
        lp_layout.addLayout(lp_top_row)

        self.live_progress_bar = QProgressBar()
        self.live_progress_bar.setFixedHeight(8)
        self.live_progress_bar.setRange(0, 100)
        self.live_progress_bar.setValue(0)
        self.live_progress_bar.setTextVisible(False)
        self.live_progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #181818;
                border: 1px solid #282828;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: #E53935;
                border-radius: 3px;
            }
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
            background-color: #141414;
            color: #A0A0A0;
            font-size: 13px;
            border: 1px dashed #333333;
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

    def load_scenes(self, scenes: List[VisualScene], force: bool = False):
        """Populates the grid with prompt cards for all scenes."""
        scenes = scenes or []
        needs_rebuild = force or not hasattr(self, "scenes") or len(self._card_widgets) != len(scenes)
        if not needs_rebuild:
            # Check if prompt content has been generated or updated
            for card, sc in zip(self._card_widgets, scenes):
                card_text = card.prompt_box.toPlainText().strip()
                sc_prompt = (sc.prompt or "").strip()
                if card_text.startswith("[Planned Visual Shot") and sc_prompt and not sc_prompt.startswith("[Planned Visual Shot"):
                    needs_rebuild = True
                    break
                if not card_text.startswith("[Planned Visual Shot") and sc_prompt and card_text != sc_prompt:
                    needs_rebuild = True
                    break
        if not needs_rebuild:
            return
        self.scenes = scenes
        self._update_batch_combo()
        self._rebuild_grid()

    def _update_batch_combo(self):
        if not hasattr(self, "batch_combo"):
            return
        # Bulk single-batch mode: hide batch dropdown and keep clean single Copy All Prompts
        self.batch_combo.clear()
        self.batch_combo.setVisible(False)
        self.copy_all_btn.setText("📋 Copy All Prompts")

    def _rebuild_grid(self):
        # Clear existing items cleanly without promoting to desktop windows
        while self.grid_layout.count() > 0:
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
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
        # Studio approval is unified in the top banner (MainWindow.plan_approval_banner); keep toolbar button hidden
        self.approve_btn.setVisible(False)

        if count == 0:
            self.empty_label = QLabel(
                f"⚡ <b style='color: #FF4B4B;'>Ready to Generate Visual Storyboard</b><br><br>"
                f"<span style='color: {COLOR_TEXT_SECONDARY};'>Paste or load your story script in Production, select your Visual Style Preset, "
                f"then click <b style='color: #FF4B4B;'>'Plan Storyboard & Audio'</b>.<br>"
                "All generated visual scene prompts will appear here in this responsive cinematic prompt card matrix.</span>"
            )
            self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.empty_label.setStyleSheet(f"""
                background-color: {COLOR_GLASS_SURFACE};
                color: {COLOR_TEXT_PRIMARY};
                font-size: 13px;
                border: 1px dashed rgba(229, 57, 53, 0.35);
                border-radius: 8px;
                padding: 40px 20px;
            """)
            self.grid_layout.addWidget(self.empty_label, 0, 0, 1, 3)
            return

        cols = 3  # Responsive 3 cards per row

        for i, sc in enumerate(self.scenes):
            card = PromptCardWidget(sc, parent=self.grid_container)
            card.edit_requested.connect(self._on_card_edited)
            card.delete_requested.connect(self._on_card_deleted)
            card.retry_requested.connect(lambda sc_item: self.retry_scene_requested.emit(sc_item))
            row = i // cols
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

    def update_single_scene(self, updated_scene: VisualScene):
        """Updates a single card in-place when its retry completes or prompt changes."""
        for card in self._card_widgets:
            if card.scene.scene_id == updated_scene.scene_id:
                card.update_scene(updated_scene)
                break

    def _on_copy_all(self):
        if not self.scenes:
            QMessageBox.information(self, "No Scenes", "There are no prompts to copy.")
            return

        from app.core.export import StoryboardExporter, copy_to_system_clipboard
        full_text = StoryboardExporter.export_to_prompts_only(self.scenes)
        copy_to_system_clipboard(full_text)

        copied_cnt = len(self.scenes)
        self.copy_all_btn.setText(f"✓ Copied {copied_cnt} Prompts!")
        self.copy_all_btn.setStyleSheet("background-color: #222222; color: #FF4B4B; border: 1px solid #E53935; font-weight: bold; border-radius: 6px; padding: 0 12px; font-size: 11px;")
        QTimer.singleShot(2500, lambda: self.copy_all_btn.setText("📋 Copy All Prompts"))

