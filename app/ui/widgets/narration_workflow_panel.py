"""
Production Narration-Aware Studio Workflow Panel for PromptBeast.
Implements Steps 1 to 5:
- Step 1: Import Script JSON & Audio File
- Step 2: Narration and Visual Ideas Input
- Step 3: Story Intelligence & Dynamic Bibles Extraction
- Step 4: Visual Style Selection & Target Settings
- Step 5: Groq Image Prompt Generation & Expansion
"""
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QLineEdit,
    QFileDialog,
    QMessageBox,
    QFrame,
    QTabWidget,
    QProgressBar,
    QSpinBox,
    QComboBox,
    QGroupBox,
    QSizePolicy,
    QDialog,
    QDialogButtonBox,
    QApplication,
)

from app.models.scene import VisualScene
from app.models.timeline import NarrationData
from app.core.narration_workflow import (
    import_script_json,
    parse_visual_breakdown_text,
    align_visuals_with_timestamps,
    parse_custom_bible_text,
)
from app.core.bible_manager import BibleManager
from app.ai.narration_worker import BatchPromptGenerationWorker
from app.ui.widgets.style_thumbnail_matrix import StyleThumbnailMatrix
from app.presets.loader import PresetManager


STYLE_PROMPT_MAP = {
    "zombie_survival": "01_zombie_survival_ai_prompt.txt",
    "whatif_flat_vector": "02_whatif_flat_vector_ai_prompt.txt",
    "century_old_photograph": "03_century_old_photograph_ai_prompt.txt",
    "3d_red_blue_stickman": "05_3d_red_blue_stickman_ai_prompt.txt",
    "antique_engraving": "06_antique_engraving_ai_prompt.txt",
    "authentic_archival_photography": "07_authentic_archival_photography_ai_prompt.txt",
    "historical_maps": "08_historical_maps_ai_prompt.txt",
}

STYLE_FEATURE_HIGHLIGHTS = {
    "zombie_survival": "🔒 Zombie Survival Directives: Locked Hero 'YOU' (Backwards Red Cap #D63A2A, Charcoal Hoodie #333333, Pure White T-Shirt #FFFFFF, Brown Crossbody Strap #4A2E1B) | Locked Horde (Uniform Olive-Green #8A9A66 Skin, White Eyes with Dot Pupils, Sharp Jagged Teeth, Tattered Brown Jacket #5C4033) | Thick Black #1A1A1A Outlines | Zero Blood/Gore.",
    "whatif_flat_vector": "🔒 What-If Flat Vector Directives: Minimalist Black Stick Figure | Strictly Locked Vibrant Bright RED Hoodie (#FF0000) across all scenes | Exactly Uniform Limb Thickness | Midnight Navy Night-World (#12182E) with Warm Golden Light Pools (#F59E0B) | Zero Gradients.",
    "century_old_photograph": "📜 Century-Old Photograph Directives: Authentic Damaged Archival Print | Faded Warm Sepia, Aged Albumen, or Silver Gelatin Monochrome | 9 Dynamic Archival Treatments (Map Overlays, Diptych Splits, Engraving Splits, Leporello Folders, Silver Bleeding, Fold Creases, Document Archives, Split-Screen Trio, Textured Blur) | STRICTLY ZERO Modern RGB Colors.",
    "3d_red_blue_stickman": "⚔️ 3D Red & Blue Stickman Directives: Strict Faction Separation | Attacking Forces = 100% Solid Bright Red 3D Stick Figures | Defending Forces = 100% Solid Blue 3D Stick Figures | No Color Mixing on Tasks | Featureless Smooth Spherical Heads | Rounded 3D Block Geometry | Zero Realistic Anatomy.",
    "antique_engraving": "✒️ Antique Engraving Directives: 18th/19th-Century Copperplate & Steel Engraving | Fine Black-Ink Cross-Hatching & Stippling on Aged Cream Paper | Black Ink Only | STRICTLY NO Color, NO Sepia Wash, NO Photographic Look, NO Torn Edges | Stills Held Completely Still.",
    "authentic_archival_photography": "📷 Authentic Archival Photography Directives: Genuine Period Photograph | Silver Gelatin or Albumen Print | Warm Sepia / Antique Monochrome | Realistic Grain, Dust Spots, Hairline Scratches, Vignette | Fills Full Frame | STRICTLY NO Torn Edges & NO Paper Borders | Stills Held Completely Still.",
    "historical_maps": "🗺️ Historical Maps Directives: Aged Parchment Period Cartography | Hand-Drawn Coastlines, Borders & Compass Rose | Strictly Period-Accurate Place Names & Frontiers | Narratively Relevant Geography | ZERO Modern Map Looks, ZERO Satellite Look | Stills Held Completely Still (Never Pan/Zoom Across Map).",
}


class PromptViewerDialog(QDialog):
    """Dialog showing the complete Master AI Prompt with copy functionality."""
    def __init__(self, style_name: str, prompt_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"PromptBeast Master AI Prompt — {style_name}")
        self.resize(840, 620)
        self.setStyleSheet("background-color: #0A0E17; color: #E2E8F0;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)

        hdr = QLabel(f"📋 Master AI Prompt for External LLM — {style_name}")
        hdr.setStyleSheet("font-size: 14px; font-weight: 700; color: #10B981;")
        lay.addWidget(hdr)

        desc = QLabel(
            "Instructions: Copy this complete prompt and send it to ChatGPT, Claude, or Gemini. "
            "The AI will acknowledge that it is ready, ask for your story script, and return your "
            "visual storyboard in PromptBeast's exact synchronized format. When you ask for bibles, "
            "it will provide the complete production bibles matching this visual style."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #94A3B8; font-size: 11px; line-height: 1.4;")
        lay.addWidget(desc)

        txt = QPlainTextEdit()
        txt.setPlainText(prompt_text)
        txt.setReadOnly(True)
        txt.setStyleSheet("""
            QPlainTextEdit {
                background-color: #05080E;
                color: #CBD5E1;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                border: 1px solid #1E293B;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        lay.addWidget(txt)

        btn_row = QHBoxLayout()
        btn_copy = QPushButton("📋 Copy Entire Prompt to Clipboard")
        btn_copy.setFixedHeight(36)
        btn_copy.setCursor(Qt.PointingHandCursor)
        btn_copy.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: #05080E;
                font-weight: 700;
                font-size: 12px;
                border-radius: 6px;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: #34D399;
            }
        """)
        btn_close = QPushButton("Close")
        btn_close.setFixedHeight(36)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #1E293B;
                color: #94A3B8;
                font-size: 12px;
                border-radius: 6px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #FFFFFF;
            }
        """)

        def _do_copy():
            from app.core.export import copy_to_system_clipboard
            copy_to_system_clipboard(prompt_text)
            btn_copy.setText("✓ Copied to Clipboard!")
            btn_copy.setStyleSheet("background-color: #3B82F6; color: #FFFFFF; font-weight: 700; border-radius: 6px; padding: 0 20px;")

        btn_copy.clicked.connect(_do_copy)
        btn_close.clicked.connect(self.accept)

        btn_row.addWidget(btn_copy)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        lay.addLayout(btn_row)


class NarrationWorkflowPanel(QWidget):
    """Unified Single-Page Narration Workflow Studio."""

    # Signals
    story_script_imported = Signal(str, object)   # (story_text, narration_data)
    visual_scenes_aligned = Signal(list)          # (List[VisualScene])
    bibles_updated = Signal(dict)                 # (extracted bibles dict)
    prompts_generated = Signal(list)              # (List[VisualScene])
    style_selected = Signal(str)                  # (style_id)
    navigate_requested = Signal(str)              # page key e.g. "studio", "scene_sync", "deliverables"
    proceed_to_studio_requested = Signal()        # Dedicated signal to proceed to studio with full pipeline sync

    def __init__(self, parent=None):
        super().__init__(parent)
        self.story_text: str = ""
        self.narration: Optional[NarrationData] = None
        self.scenes: List[VisualScene] = []
        self.bibles: Dict[str, Any] = {}
        self.loaded_bibles: Dict[str, Dict[str, Any]] = {}
        self.json_path: Optional[str] = None
        self.audio_path: Optional[str] = None

        self._auto_sync_timer = QTimer(self)
        self._auto_sync_timer.setSingleShot(True)
        self._auto_sync_timer.setInterval(300)
        self._auto_sync_timer.timeout.connect(self._auto_sync_storyboard)

        self._prompt_worker: Optional[BatchPromptGenerationWorker] = None

        self._init_ui()

    def _auto_load_default_assets(self):
        """No auto-preloading of speech/bibles. All steps start clean."""
        pass

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 14)
        main_layout.setSpacing(14)

        # ---------------------------------------------------------------------
        # STEP 1: IMPORT SCRIPT JSON & AUDIO
        # ---------------------------------------------------------------------
        step1_box, s1_lay = self._create_card("🎙️ STEP 1: Import Script JSON & Audio File")
        s1_lay.setSpacing(8)

        # File actions row
        f_row = QHBoxLayout()
        f_row.setSpacing(10)

        self.btn_browse_json = QPushButton("📁 Import Script JSON (speech.json)...")
        self.btn_browse_json.setFixedHeight(36)
        self.btn_browse_json.setCursor(Qt.PointingHandCursor)
        self.btn_browse_json.setStyleSheet("""
            QPushButton {
                background-color: #222222;
                color: #F5F5F5;
                font-weight: 700;
                font-size: 12px;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background-color: #292929;
                border-color: #E53935;
                color: #FFFFFF;
            }
        """)
        self.btn_browse_json.clicked.connect(self._on_browse_json)
        f_row.addWidget(self.btn_browse_json)

        self.btn_browse_audio = QPushButton("🎵 Select Audio File (speech.mp3)...")
        self.btn_browse_audio.setFixedHeight(36)
        self.btn_browse_audio.setCursor(Qt.PointingHandCursor)
        self.btn_browse_audio.setStyleSheet("""
            QPushButton {
                background-color: #222222;
                color: #F5F5F5;
                font-weight: 700;
                font-size: 12px;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background-color: #292929;
                border-color: #E53935;
                color: #FFFFFF;
            }
        """)
        self.btn_browse_audio.clicked.connect(self._on_browse_audio)
        f_row.addWidget(self.btn_browse_audio)

        f_row.addStretch()
        s1_lay.addLayout(f_row)

        # Status row
        status_row = QHBoxLayout()
        self.lbl_json_status = QLabel("JSON: No script file loaded.")
        self.lbl_json_status.setStyleSheet("color: #707070; font-size: 11px; background: transparent; border: none;")
        status_row.addWidget(self.lbl_json_status)

        status_row.addStretch()

        self.lbl_audio_status = QLabel("Audio: No audio file attached.")
        self.lbl_audio_status.setStyleSheet("color: #707070; font-size: 11px; background: transparent; border: none;")
        status_row.addWidget(self.lbl_audio_status)
        s1_lay.addLayout(status_row)

        main_layout.addWidget(step1_box)

        # ---------------------------------------------------------------------
        # STEP 2: NARRATION & VISUAL IDEAS INPUT
        # ---------------------------------------------------------------------
        step2_box, s2_lay = self._create_card("📝 STEP 2: Narration & Visual Ideas Breakdown")
        s2_lay.setSpacing(8)

        s2_desc = QLabel("Paste script narration lines, corresponding visual ideas (e.g. Visual 1 Words: ... Visual: ...), scene descriptions, or creative instructions:")
        s2_desc.setStyleSheet("color: #A0A0A0; font-size: 11px; background: transparent; border: none;")
        s2_lay.addWidget(s2_desc)

        self.txt_visual_ideas = QPlainTextEdit()
        self.txt_visual_ideas.setMinimumHeight(140)
        self.txt_visual_ideas.setMaximumHeight(260)
        self.txt_visual_ideas.setPlaceholderText(
            "Visual 1 Words: ... Visual: ...\n\nVisual 2 Words: ... Visual: ...\n\nVisual 3 Words: ... Visual: ..."
        )
        self.txt_visual_ideas.setStyleSheet("""
            QPlainTextEdit {
                background-color: #141414;
                color: #F5F5F5;
                font-family: 'Consolas', 'Segoe UI', monospace;
                font-size: 12px;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 8px;
            }
            QPlainTextEdit:focus {
                border: 1px solid #E53935;
                background-color: #181818;
            }
        """)
        self.txt_visual_ideas.textChanged.connect(self._on_visual_ideas_text_changed)
        s2_lay.addWidget(self.txt_visual_ideas)

        # Alignment Action Row (Automatic live sync on paste, manual file loader retained)
        align_row = QHBoxLayout()
        self.btn_load_storyboard = QPushButton("📑 Load Storyboard File...")
        self.btn_load_storyboard.setFixedHeight(34)
        self.btn_load_storyboard.setCursor(Qt.PointingHandCursor)
        self.btn_load_storyboard.setStyleSheet("""
            QPushButton {
                background-color: #222222;
                color: #F5F5F5;
                font-weight: 700;
                font-size: 12px;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 0 14px;
            }
            QPushButton:hover {
                background-color: #292929;
                border-color: #E53935;
                color: #FFFFFF;
            }
        """)
        self.btn_load_storyboard.clicked.connect(self._on_load_storyboard_dialog)
        align_row.addWidget(self.btn_load_storyboard)

        # Hidden for backward compatibility; auto-sync handles parsing live
        self.btn_align_visuals = QPushButton("⚡ Parse & Synchronize")
        self.btn_align_visuals.setVisible(False)
        self.btn_align_visuals.clicked.connect(self._on_align_visuals)

        self.lbl_align_stats = QLabel("0 visual beats aligned.")
        self.lbl_align_stats.setStyleSheet("color: #A0A0A0; font-size: 11px; font-weight: 600; margin-left: 10px; background: transparent; border: none;")
        align_row.addWidget(self.lbl_align_stats)

        align_row.addStretch()
        s2_lay.addLayout(align_row)

        main_layout.addWidget(step2_box)

        # ---------------------------------------------------------------------
        # STEP 3: USER-PROVIDED PRODUCTION BIBLES (FLEXIBLE BULK / SINGLE)
        # ---------------------------------------------------------------------
        step3_box, s3_lay = self._create_card("📖 STEP 3: User Production Bibles & Context (Flexible Bulk / Single)")
        s3_lay.setSpacing(8)

        b_hdr = QHBoxLayout()
        b_hdr.setSpacing(10)

        self.btn_load_bibles = QPushButton("📁 Load Bible File / Folder...")
        self.btn_load_bibles.setFixedHeight(34)
        self.btn_load_bibles.setCursor(Qt.PointingHandCursor)
        self.btn_load_bibles.setStyleSheet("""
            QPushButton {
                background-color: #222222;
                color: #F5F5F5;
                font-weight: 700;
                font-size: 12px;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 0 14px;
            }
            QPushButton:hover {
                background-color: #292929;
                border-color: #E53935;
                color: #FFFFFF;
            }
        """)
        self.btn_load_bibles.clicked.connect(self._on_load_bibles_dialog)
        b_hdr.addWidget(self.btn_load_bibles)

        self.btn_paste_bibles = QPushButton("📋 Paste Custom Bible")
        self.btn_paste_bibles.setFixedHeight(34)
        self.btn_paste_bibles.setCursor(Qt.PointingHandCursor)
        self.btn_paste_bibles.setStyleSheet("""
            QPushButton {
                background-color: rgba(229, 57, 53, 0.16);
                color: #FF4B4B;
                font-weight: 700;
                font-size: 12px;
                border: 1px solid #E53935;
                border-radius: 6px;
                padding: 0 14px;
            }
            QPushButton:hover {
                background-color: #E53935;
                color: #FFFFFF;
                border-color: #FF7070;
            }
        """)
        self.btn_paste_bibles.clicked.connect(self._on_paste_custom_bibles)
        b_hdr.addWidget(self.btn_paste_bibles)

        b_hdr.addStretch()

        self.btn_save_bibles = QPushButton("💾 Save Edited Bibles")
        self.btn_save_bibles.setFixedHeight(32)
        self.btn_save_bibles.setStyleSheet("""
            QPushButton {
                background-color: #222222;
                color: #F5F5F5;
                font-size: 12px;
                font-weight: 600;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 0 14px;
            }
            QPushButton:hover {
                background-color: #292929;
                border-color: #E53935;
                color: #FFFFFF;
            }
        """)
        self.btn_save_bibles.clicked.connect(self._on_save_bibles_clicked)
        b_hdr.addWidget(self.btn_save_bibles)
        s3_lay.addLayout(b_hdr)

        # Status row for bibles
        b_status_row = QHBoxLayout()
        self.lbl_bible_status = QLabel("No bibles loaded. Click 'Load Bible File / Folder' or 'Paste Custom Bible'.")
        self.lbl_bible_status.setStyleSheet("color: #707070; font-size: 11px; background: transparent; border: none;")
        b_status_row.addWidget(self.lbl_bible_status)
        b_status_row.addStretch()
        s3_lay.addLayout(b_status_row)

        # Tabbed Bible Editors (all start completely empty so placeholder is visible)
        self.bible_tabs = QTabWidget()
        self.bible_tabs.setFixedHeight(180)
        self.bible_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #282828;
                background: #141414;
                border-radius: 6px;
            }
            QTabBar::tab {
                background: #1A1A1A;
                color: #A0A0A0;
                padding: 5px 14px;
                font-size: 11px;
                font-weight: 600;
                border: 1px solid #282828;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #242424;
                color: #FFFFFF;
                border-color: #E53935;
                border-bottom: 2px solid #E53935;
            }
            QTabBar::tab:hover:!selected {
                background: #202020;
                color: #F5F5F5;
            }
        """)

        self.txt_story_bible = QPlainTextEdit()
        self.txt_story_bible.setPlaceholderText("Story Logline, Genre & Tone, Narrative Arc, Timeline Events...")
        self.bible_tabs.addTab(self.txt_story_bible, "Story Bible")

        self.txt_char_bible = QPlainTextEdit()
        self.txt_char_bible.setPlaceholderText("Characters, Appearances, Clothing, Age, Consistency Rules...")
        self.bible_tabs.addTab(self.txt_char_bible, "Character Bible")

        self.txt_env_bible = QPlainTextEdit()
        self.txt_env_bible.setPlaceholderText("Locations, Architecture, Atmospheric Lighting, Decay Progression...")
        self.bible_tabs.addTab(self.txt_env_bible, "Environment Bible")

        self.txt_objects_bible = QPlainTextEdit()
        self.txt_objects_bible.setPlaceholderText("Key Objects, Tools, Weapons, Survival Props, Significance...")
        self.bible_tabs.addTab(self.txt_objects_bible, "Key Objects & Props")

        self.txt_style_bible = QPlainTextEdit()
        self.txt_style_bible.setPlaceholderText("Color Palette, Lighting Rules, Camera Guidelines, Continuity Motifs...")
        self.bible_tabs.addTab(self.txt_style_bible, "Style & Cinematography")

        for txt_widget in (self.txt_story_bible, self.txt_char_bible, self.txt_env_bible, self.txt_objects_bible, self.txt_style_bible):
            txt_widget.setStyleSheet("""
                QPlainTextEdit {
                    background-color: #141414;
                    color: #F5F5F5;
                    font-family: 'Consolas', monospace;
                    font-size: 11px;
                    border: none;
                    padding: 8px;
                }
                QPlainTextEdit:focus {
                    background-color: #181818;
                }
            """)

        s3_lay.addWidget(self.bible_tabs)
        main_layout.addWidget(step3_box)

        # ---------------------------------------------------------------------
        # STEP 4: VISUAL STYLE PRESETS
        # ---------------------------------------------------------------------
        step4_box, s4_lay = self._create_card("🎨 STEP 4: Visual Art Style Presets")
        s4_lay.setSpacing(10)

        # Visual Style Matrix (Only the 4 curated cards)
        self.style_matrix = StyleThumbnailMatrix(self)
        self.style_matrix.style_selected.connect(self._on_style_selected)
        s4_lay.addWidget(self.style_matrix)

        main_layout.addWidget(step4_box)

        # ---------------------------------------------------------------------
        # STEP 5: REVIEW STORYBOARD & PROCEED TO STUDIO
        # ---------------------------------------------------------------------
        step5_box, s5_lay = self._create_card("➔ STEP 5: Review Storyboard & Proceed to Studio")

        s5_desc = QLabel(
            "Your visual breakdown and style directives are configured. "
            "Proceed to Stage 02 (Studio) to review your storyboard scenes and approve prompt expansion."
        )
        s5_desc.setStyleSheet("color: #A0A0A0; font-size: 11px; background: transparent; border: none;")
        s5_lay.addWidget(s5_desc)

        self.btn_next_studio = QPushButton("➔ Next: Review & Approve in Studio")
        self.btn_next_studio.setFixedHeight(46)
        self.btn_next_studio.setCursor(Qt.PointingHandCursor)
        self.btn_next_studio.setStyleSheet("""
            QPushButton {
                background-color: #E53935;
                color: #FFFFFF;
                font-weight: 800;
                font-size: 14px;
                border-radius: 8px;
                border: 1px solid #FF4B4B;
                padding: 0 24px;
            }
            QPushButton:hover {
                background-color: #FF4B4B;
                border-color: #FF7070;
            }
            QPushButton:pressed {
                background-color: #B71C1C;
            }
        """)
        self.btn_next_studio.clicked.connect(self._on_proceed_to_studio)
        s5_lay.addWidget(self.btn_next_studio)

        main_layout.addWidget(step5_box)

    def _create_card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("workflowStepCard")
        card.setStyleSheet("""
            QFrame#workflowStepCard {
                background-color: #161616;
                border: 1px solid #282828;
                border-radius: 8px;
            }
            QLabel {
                background: transparent;
                background-color: transparent;
                border: none;
                outline: none;
            }
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(10)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("color: #F5F5F5; font-size: 13px; font-weight: 700; border: none; background: transparent;")
        lay.addWidget(t_lbl)
        return card, lay

    # =========================================================================
    # STEP 1 ACTIONS: SCRIPT JSON & AUDIO IMPORT
    # =========================================================================

    def _on_browse_json(self):
        start_dir = str(Path("audio and files").resolve()) if Path("audio and files").exists() else "."
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Script / Speech JSON File",
            start_dir,
            "JSON Files (*.json);;All Files (*.*)"
        )
        if not path:
            return
        self.load_json_file(path)

    def load_json_file(self, path: str):
        res = import_script_json(path)
        if not res.success:
            QMessageBox.critical(self, "JSON Import Error", res.message)
            return

        self.json_path = path
        self.story_text = res.story_text
        self.narration = res.narration

        dur_text = f"{res.narration.duration_seconds:.1f}s" if res.narration else "N/A"
        word_count = len(res.narration.words) if res.narration and res.narration.words else len(res.story_text.split())
        self.lbl_json_status.setText(f"✅ JSON: {Path(path).name} ({word_count} words · {dur_text})")
        self.lbl_json_status.setStyleSheet("color: #4CAF50; font-size: 11px; font-weight: 600; background: transparent; border: none;")

        # Auto-detect audio file in the same directory
        parent_dir = Path(path).parent
        for ext in [".mp3", ".wav", ".m4a"]:
            cand = parent_dir / f"{Path(path).stem}{ext}"
            if cand.exists():
                self.set_audio_file(str(cand))
                break
            # Or general speech.mp3
            speech_cand = parent_dir / f"speech{ext}"
            if speech_cand.exists():
                self.set_audio_file(str(speech_cand))
                break

        self.story_script_imported.emit(self.story_text, self.narration)

        # Re-synchronize storyboard if visual ideas were already pasted
        if self.txt_visual_ideas.toPlainText().strip():
            self._auto_sync_storyboard()

    def _on_browse_audio(self):
        start_dir = str(Path("audio and files").resolve()) if Path("audio and files").exists() else "."
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Voiceover Audio File",
            start_dir,
            "Audio Files (*.mp3 *.wav *.m4a *.aac);;All Files (*.*)"
        )
        if path:
            self.set_audio_file(path)

    def set_audio_file(self, path: str):
        p = Path(path)
        if p.exists():
            self.audio_path = str(p.resolve())
            self.lbl_audio_status.setText(f"✅ Audio: {p.name}")
            self.lbl_audio_status.setStyleSheet("color: #4CAF50; font-size: 11px; font-weight: 600; background: transparent; border: none;")

            # Auto-catch matching JSON file in the same directory if not already loaded
            if not self.json_path or not Path(self.json_path).exists():
                parent_dir = p.parent
                candidates = [
                    parent_dir / f"{p.stem}.json",
                    parent_dir / "speech.json",
                    parent_dir / "narration.json",
                    parent_dir / "transcript.json"
                ]
                for cand in candidates:
                    if cand.exists() and cand.is_file():
                        self.load_json_file(str(cand.resolve()))
                        break

    # =========================================================================
    # STEP 2 ACTIONS: PARSE & ALIGN VISUAL IDEAS
    # =========================================================================

    def _on_visual_ideas_text_changed(self):
        """Debounced auto-synchronization trigger the moment text is pasted or edited."""
        if hasattr(self, "_auto_sync_timer"):
            self._auto_sync_timer.start(300)

    def _auto_sync_storyboard(self):
        """Automatically parses and aligns storyboard scenes the moment text is pasted."""
        raw_text = self.txt_visual_ideas.toPlainText().strip()
        if not raw_text:
            self.scenes = []
            self.lbl_align_stats.setText("0 visual beats aligned.")
            self.lbl_align_stats.setStyleSheet("color: #A0A0A0; font-size: 11px; font-weight: 600; margin-left: 10px; background: transparent; border: none;")
            return

        items = parse_visual_breakdown_text(raw_text)
        if not items:
            self.lbl_align_stats.setText("0 visual beats aligned.")
            self.lbl_align_stats.setStyleSheet("color: #A0A0A0; font-size: 11px; font-weight: 600; margin-left: 10px; background: transparent; border: none;")
            return

        # Auto-discover narration if missing
        if not self.narration:
            cands = []
            if hasattr(self, "json_path") and self.json_path and Path(self.json_path).exists():
                cands.append(Path(self.json_path))
            if hasattr(self, "audio_path") and self.audio_path:
                cands.append(Path(self.audio_path).parent / "speech.json")
                cands.append(Path(self.audio_path).parent / "narration_timestamps.json")
            for c in cands:
                if c.exists():
                    res = import_script_json(str(c))
                    if res.success and res.narration:
                        self.narration = res.narration
                        self.json_path = str(c)
                        break

        total_audio_dur = self.narration.duration_seconds if self.narration else None
        try:
            self.scenes = align_visuals_with_timestamps(
                visual_items=items,
                narration=self.narration,
                total_audio_duration=total_audio_dur
            )
        except Exception as e:
            print(f"[WorkflowPanel] Alignment fallback: {e}")
            self.scenes = align_visuals_with_timestamps(
                visual_items=items,
                narration=None,
                total_audio_duration=total_audio_dur
            )

        self.lbl_align_stats.setText(f"✓ {len(self.scenes)} Visual Beats Aligned & Synchronized")
        self.lbl_align_stats.setStyleSheet("color: #FF4B4B; font-size: 11px; font-weight: 700; margin-left: 10px; background: transparent; border: none;")

        self.visual_scenes_aligned.emit(self.scenes)

    def _on_align_visuals(self):
        """Manual alignment trigger for backward compatibility."""
        self._auto_sync_storyboard()

    def _on_load_storyboard_dialog(self):
        """Allows 1-click loading of a storyboard file (.txt or .json) into Step 2."""
        start_dir = str(Path("audio and files").resolve()) if Path("audio and files").exists() else "."
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Storyboard File",
            start_dir,
            "Storyboard Files (*.txt *.json);;All Files (*.*)"
        )
        if not path:
            return

        # Auto-discover speech.json in the same directory if narration is not loaded
        if not self.narration:
            parent_dir = Path(path).parent
            for sc in [parent_dir / "speech.json", parent_dir / "narration_timestamps.json"]:
                if sc.exists():
                    self.load_json_file(str(sc))
                    break

        try:
            content = Path(path).read_text(encoding="utf-8")
        except Exception:
            try:
                content = Path(path).read_text(encoding="latin-1")
            except Exception as e:
                QMessageBox.critical(self, "Read Error", f"Could not read storyboard file:\n{e}")
                return

        self.txt_visual_ideas.setPlainText(content)
        self._on_align_visuals()

    # =========================================================================
    # STEP 3 ACTIONS: USER PRODUCTION BIBLES (FLEXIBLE BULK / SINGLE)
    # =========================================================================

    def _display_bibles_in_tabs(self, bibles: Dict[str, Any]):
        """Populates the 5 workspace tabs cleanly with non-empty JSON or empty string."""
        chars = bibles.get("characters", [])
        envs = bibles.get("environments", [])
        props = bibles.get("key_objects", [])
        story_b = bibles.get("story_bible", {})
        style_b = bibles.get("visual_style_bible", {})

        has_story = bool(story_b and any(v for v in story_b.values() if v))
        has_style = bool(style_b and any(v for v in style_b.values() if v))

        self.txt_story_bible.setPlainText(json.dumps(story_b, indent=2) if has_story else "")
        self.txt_char_bible.setPlainText(json.dumps(chars, indent=2) if chars else "")
        self.txt_env_bible.setPlainText(json.dumps(envs, indent=2) if envs else "")
        self.txt_objects_bible.setPlainText(json.dumps(props, indent=2) if props else "")
        self.txt_style_bible.setPlainText(json.dumps(style_b, indent=2) if has_style else "")

    def load_bibles_from_path(self, path: str) -> bool:
        """Loads single or bulk bibles from a file or folder path using BibleManager."""
        loaded = BibleManager.load_bibles_from_path(path)
        if not loaded:
            return False

        first_bible = list(loaded.values())[0] if loaded else {}
        self.bibles = first_bible
        self._display_bibles_in_tabs(self.bibles)

        chars = self.bibles.get("characters", [])
        envs = self.bibles.get("environments", [])
        props = self.bibles.get("key_objects", [])
        self.lbl_bible_status.setText(
            f"✅ Loaded Bibles ({len(chars)} characters, {len(envs)} locations, {len(props)} props)"
        )
        self.lbl_bible_status.setStyleSheet("color: #4CAF50; font-size: 11px; font-weight: 600; background: transparent; border: none;")
        self.bibles_updated.emit(self.bibles)
        return True

    def _on_load_bibles_dialog(self):
        """Prompts user to select a Bible file or a folder containing multiple bibles."""
        start_dir = str(Path("audio and files").resolve()) if Path("audio and files").exists() else "."
        choice = QMessageBox.question(
            self,
            "Load Production Bibles",
            "Click 'Yes' to select a single Bible file (e.g. Bibles.txt, .json, .md),\n"
            "or 'No' to select a folder containing multiple Bible files.",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.Yes
        )
        if choice == QMessageBox.Cancel:
            return
        elif choice == QMessageBox.Yes:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Select Production Bible File",
                start_dir,
                "Bible Files (*.txt *.json *.md);;All Files (*.*)"
            )
        else:
            path = QFileDialog.getExistingDirectory(
                self,
                "Select Folder Containing Production Bibles",
                start_dir
            )

        if not path:
            return

        success = self.load_bibles_from_path(path)
        if not success:
            QMessageBox.warning(self, "Load Warning", f"No valid bibles could be extracted from:\n{path}")

    def _on_save_bibles_clicked(self):
        try:
            story_txt = self.txt_story_bible.toPlainText().strip()
            char_txt = self.txt_char_bible.toPlainText().strip()
            env_txt = self.txt_env_bible.toPlainText().strip()
            props_txt = self.txt_objects_bible.toPlainText().strip()
            style_txt = self.txt_style_bible.toPlainText().strip()

            if story_txt:
                self.bibles["story_bible"] = json.loads(story_txt) if (story_txt.startswith("{") or story_txt.startswith("[")) else {"notes": story_txt}
            if char_txt:
                self.bibles["characters"] = json.loads(char_txt) if (char_txt.startswith("{") or char_txt.startswith("[")) else [{"raw": char_txt}]
            if env_txt:
                self.bibles["environments"] = json.loads(env_txt) if (env_txt.startswith("{") or env_txt.startswith("[")) else [{"raw": env_txt}]
            if props_txt:
                self.bibles["key_objects"] = json.loads(props_txt) if (props_txt.startswith("{") or props_txt.startswith("[")) else [{"raw": props_txt}]
            if style_txt:
                self.bibles["visual_style_bible"] = json.loads(style_txt) if (style_txt.startswith("{") or style_txt.startswith("[")) else {"notes": style_txt}

            self.lbl_bible_status.setText("✅ Saved edited bibles!")
            self.lbl_bible_status.setStyleSheet("color: #4CAF50; font-size: 11px; font-weight: 600; background: transparent; border: none;")
            self.bibles_updated.emit(self.bibles)
        except Exception as e:
            QMessageBox.warning(self, "Format Warning", f"Could not save edited bibles:\n{e}")

    def _on_paste_custom_bibles(self):
        """Opens a dialog for the user to paste human-readable or structured production bibles."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Paste Custom Production Bibles (Character, Environment, Props, Style)")
        dlg.resize(750, 550)
        dlg.setStyleSheet("""
            QDialog {
                background-color: #101010;
                color: #F5F5F5;
            }
            QPlainTextEdit {
                background-color: #141414;
                color: #F5F5F5;
                font-family: 'Consolas', monospace;
                font-size: 12px;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 8px;
            }
            QPushButton {
                background-color: #222222;
                color: #F5F5F5;
                font-weight: 700;
                font-size: 12px;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #292929;
                border-color: #E53935;
                color: #FFFFFF;
            }
        """)
        d_lay = QVBoxLayout(dlg)
        d_lay.setSpacing(10)

        lbl = QLabel(
            "Paste your formatted Production Bibles below (CHARACTER BIBLE, ENVIRONMENT BIBLE, "
            "OBJECT AND PROP BIBLE, CINEMATIC STYLE BIBLE):",
            dlg
        )
        lbl.setStyleSheet("color: #A0A0A0; font-size: 12px; background: transparent; border: none;")
        d_lay.addWidget(lbl)

        txt_input = QPlainTextEdit(dlg)
        txt_input.setPlaceholderText(
            "1. CHARACTER BIBLE\nCHARACTER 1: ...\n\n2. ENVIRONMENT BIBLE\nLOCATION 1: ...\n\n3. OBJECT AND PROP BIBLE\n..."
        )
        d_lay.addWidget(txt_input)

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_cancel = QPushButton("Cancel", dlg)
        btn_cancel.clicked.connect(dlg.reject)
        btn_box.addWidget(btn_cancel)

        btn_apply = QPushButton("Apply Bibles", dlg)
        btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #E53935;
                color: #FFFFFF;
                font-weight: 700;
                border: 1px solid #FF4B4B;
                border-radius: 6px;
                padding: 6px 18px;
            }
            QPushButton:hover {
                background-color: #FF4B4B;
            }
        """)
        btn_apply.clicked.connect(dlg.accept)
        btn_box.addWidget(btn_apply)

        d_lay.addLayout(btn_box)

        if dlg.exec() == QDialog.Accepted:
            raw_text = txt_input.toPlainText().strip()
            if not raw_text:
                return

            parsed = BibleManager.parse_single_bible_text(raw_text)
            self.bibles = parsed
            self._display_bibles_in_tabs(self.bibles)

            chars = self.bibles.get("characters", [])
            envs = self.bibles.get("environments", [])
            props = self.bibles.get("key_objects", [])
            self.lbl_bible_status.setText(
                f"✅ Bibles Applied: {len(chars)} characters · {len(envs)} locations · {len(props)} props"
            )
            self.lbl_bible_status.setStyleSheet("color: #4CAF50; font-size: 11px; font-weight: 600; background: transparent; border: none;")
            self.bibles_updated.emit(self.bibles)

    # =========================================================================
    # STEP 5 ACTIONS: BATCH PROMPT GENERATION
    # =========================================================================

    def _on_start_prompt_generation(self):
        if not self.scenes:
            self._on_align_visuals()

        if not self.scenes:
            QMessageBox.warning(self, "No Scenes", "Please align visual ideas with timestamps before generating prompts.")
            return

        style_id = self.style_matrix.current_style_id()
        aspect_ratio = "16:9"
        model = "qwen/qwen3.8-27b"
        batch_size = 4

        # If bibles not yet extracted, construct a dynamic base
        if not self.bibles:
            self.bibles = {
                "story_bible": {"logline": self.story_text[:160]},
                "characters": [{"name": "Protagonist", "physical_description": "Survivor", "clothing_and_gear": "Standard survival gear"}],
                "environments": [{"name": "Primary Setting", "architectural_style": "Story environment"}],
                "visual_style_bible": {"color_palette": "Consistent with selected style"}
            }

        self.btn_generate_prompts.setEnabled(False)
        self.btn_stop_prompts.setEnabled(True)
        self.progress_bar.setValue(0)
        self.lbl_progress_status.setText("Starting Groq prompt expansion worker...")

        self._prompt_worker = BatchPromptGenerationWorker(
            scenes=self.scenes,
            bibles=self.bibles,
            story_context=self.story_text or "Story Narrative",
            visual_style_id=style_id,
            aspect_ratio=aspect_ratio,
            model=model,
            batch_size=batch_size,
            force_regenerate=False,
            parent=self
        )
        self._prompt_worker.progress_updated.connect(self._on_prompt_progress)
        self._prompt_worker.generation_finished.connect(self._on_prompt_generation_finished)
        self._prompt_worker.generation_failed.connect(self._on_prompt_generation_failed)
        self._prompt_worker.start()

    def _on_stop_prompt_generation(self):
        if self._prompt_worker:
            self._prompt_worker.cancel()
            self.lbl_progress_status.setText("Generation stopped by user.")
            self.btn_generate_prompts.setEnabled(True)
            self.btn_stop_prompts.setEnabled(False)

    def _on_prompt_progress(self, current: int, total: int, status_msg: str):
        pct = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(pct)
        self.lbl_progress_status.setText(status_msg)

    def _on_prompt_generation_finished(self, updated_scenes: List[VisualScene]):
        self.scenes = updated_scenes
        self.btn_generate_prompts.setEnabled(True)
        self.btn_stop_prompts.setEnabled(False)
        self.progress_bar.setValue(100)
        self.lbl_progress_status.setText(f"✅ Generated {len(updated_scenes)} detailed image prompts matching selected style!")
        self.lbl_progress_status.setStyleSheet("color: #34D399; font-size: 11px; font-weight: 600;")
        self.prompts_generated.emit(self.scenes)

    def _on_prompt_generation_failed(self, error_msg: str):
        self.btn_generate_prompts.setEnabled(True)
        self.btn_stop_prompts.setEnabled(False)
        self.lbl_progress_status.setText(f"❌ Generation error: {error_msg[:60]}")
        self.lbl_progress_status.setStyleSheet("color: #EF4444; font-size: 11px;")
        QMessageBox.critical(self, "Prompt Generation Error", f"Prompt generation error:\n{error_msg}")

    def _on_proceed_to_studio(self):
        """Validates alignment, synchronizes state, and navigates to Studio page for approval."""
        raw_ideas = self.txt_visual_ideas.toPlainText().strip()
        has_dummy_durations = bool(self.scenes and len(self.scenes) > 1 and all(abs(s.duration - 3.5) < 0.01 for s in self.scenes[:min(5, len(self.scenes))]))
        if raw_ideas and (not self.scenes or (self.narration and has_dummy_durations)):
            self._auto_sync_storyboard()

        style_id = self.style_matrix.current_style_id()
        self.style_selected.emit(style_id)

        if not self.bibles:
            style_preset = PresetManager.get_style_by_id(style_id)
            style_name = style_preset.name if style_preset else style_id.replace("_", " ").title()
            self.bibles = {
                "story_bible": {"logline": (self.story_text or "Production Story")[:200]},
                "characters": [{"name": "Protagonist", "physical_description": "Survivor", "clothing_and_gear": "Standard gear"}],
                "environments": [{"name": "Setting", "architectural_style": "Story environment"}],
                "visual_style_bible": {"color_palette": f"Consistent with {style_name}"}
            }
            self.bibles_updated.emit(self.bibles)

        if self.scenes:
            self.visual_scenes_aligned.emit(self.scenes)

        self.navigate_requested.emit("studio")

    def _get_prompt_path_for_style(self, style_id: str) -> Optional[Path]:
        """Resolves the dedicated Master AI Prompt file for a given style ID."""
        prompts_dir = Path(__file__).resolve().parent.parent.parent.parent / "config" / "ai_prompts"
        norm_id = style_id.lower().strip()
        filename = STYLE_PROMPT_MAP.get(norm_id, "01_zombie_survival_ai_prompt.txt")
        target_path = prompts_dir / filename
        if target_path.exists():
            return target_path
        return None

    def _on_style_selected(self, style_id: str):
        """Updates feature highlights banner and button text when user selects a visual style."""
        norm_id = style_id.lower().strip()
        features_text = STYLE_FEATURE_HIGHLIGHTS.get(
            norm_id,
            f"Active Style: {style_id}. Visual directives and constraints loaded from configuration."
        )
        if hasattr(self, "lbl_style_feature_banner"):
            self.lbl_style_feature_banner.setText(features_text)

        style_preset = PresetManager.get_style_by_id(norm_id)
        style_name = style_preset.name if style_preset else norm_id.replace("_", " ").title()

        if hasattr(self, "btn_copy_style_prompt"):
            self.btn_copy_style_prompt.setText(f"📋 Copy Master AI Prompt ({style_name})")
        if hasattr(self, "lbl_prompt_copy_status"):
            self.lbl_prompt_copy_status.setText("")

        self.style_selected.emit(norm_id)

    def _on_copy_style_prompt(self):
        """Copies the dedicated Master AI Prompt for the active style to the system clipboard."""
        style_id = self.style_matrix.current_style_id()
        p = self._get_prompt_path_for_style(style_id)
        style_preset = PresetManager.get_style_by_id(style_id)
        style_name = style_preset.name if style_preset else style_id.replace("_", " ").title()

        if p and p.exists():
            try:
                content = p.read_text(encoding="utf-8")
                from app.core.export import copy_to_system_clipboard
                copy_to_system_clipboard(content)
                if hasattr(self, "lbl_prompt_copy_status"):
                    self.lbl_prompt_copy_status.setText(f"✓ Copied {style_name} prompt to clipboard! Paste into ChatGPT/Claude.")
                    self.lbl_prompt_copy_status.setStyleSheet("color: #10B981; font-size: 11px; font-weight: 600;")
            except Exception as e:
                QMessageBox.warning(self, "Copy Error", f"Could not read prompt file:\n{e}")
        else:
            QMessageBox.warning(self, "Prompt Not Found", f"Prompt file for style '{style_name}' was not found at:\n{p}")

    def _on_view_style_prompt(self):
        """Opens a viewer dialog allowing inspection and full copy of the active style's Master AI Prompt."""
        style_id = self.style_matrix.current_style_id()
        p = self._get_prompt_path_for_style(style_id)
        style_preset = PresetManager.get_style_by_id(style_id)
        style_name = style_preset.name if style_preset else style_id.replace("_", " ").title()

        if p and p.exists():
            try:
                content = p.read_text(encoding="utf-8")
                dialog = PromptViewerDialog(style_name=style_name, prompt_text=content, parent=self)
                dialog.exec()
            except Exception as e:
                QMessageBox.warning(self, "Viewer Error", f"Could not open prompt viewer:\n{e}")
        else:
            QMessageBox.warning(self, "Prompt Not Found", f"Prompt file for style '{style_name}' was not found at:\n{p}")
