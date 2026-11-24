"""
Scene Sync — All-In-One One-Pager Video Production Studio for PromptBeast Pro.
Allows direct input of:
1. Voiceover Audio (speech.mp3 / voiceover.wav)
2. Word Timestamps JSON (speech.json / timestamps.json)
3. Visual Storyboard (.txt, .json, or pasted text)
4. Images Folder (001.png, 002.png, etc.)
5. Subtitles configuration (Yes/No toggle + Style Presets: Hormozi, Cinematic Gold, Neon, MrBeast, Minimalist, etc.)
6. Single-click Video Rendering with progress bar, video player, and output folder revealer.
Features pure glassmorphism design with Electric Lime accents and responsive layouts.
"""

import os
import re
import shutil
import zipfile
import subprocess
from pathlib import Path
from typing import List, Optional, Union, Dict, Any

from PySide6.QtCore import Qt, Signal, QUrl, QTimer, QThread
from PySide6.QtGui import QPixmap, QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QFrame,
    QFileDialog,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSlider,
    QComboBox,
    QMessageBox,
    QTextEdit,
    QPlainTextEdit,
    QDialog,
    QScrollArea,
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from app.models.scene import VisualScene
from app.models.timeline import NarrationData, WordTimestamp
from app.models.video_config import (
    VideoRenderSettings,
    SubtitleConfig,
    SubtitlePreset,
    AspectRatio,
    MotionPreset,
    VideoOverlay,
)
from app.core.asset_manager import AssetManager
from app.core.video_renderer import VideoRenderWorker, VideoRenderer
from app.core.subtitle_engine import SubtitleEngine
from app.core.narration_workflow import (
    import_script_json,
    parse_visual_breakdown_text,
    align_visuals_with_timestamps,
)


def natural_sort_key(p: Union[Path, str]) -> list:
    """Natural sorting key: puts numbered filenames in numerical order (001, 002, 010, 100)."""
    name = Path(p).name
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", name)]


class PasteStoryboardDialog(QDialog):
    """Sleek glassmorphism dialog for pasting or viewing raw storyboard scenes."""

    def __init__(self, current_text: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Visual Storyboard — Script & Scene Breakdown")
        self.resize(750, 520)
        self.setStyleSheet("""
            QDialog {
                background-color: #080D0B;
                border: 1px solid rgba(163, 255, 18, 0.25);
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        hdr = QLabel("📋 Visual Storyboard Editor")
        hdr.setStyleSheet("font-size: 15px; font-weight: 800; color: #A3FF12; letter-spacing: 0.5px;")
        layout.addWidget(hdr)

        desc = QLabel(
            "Paste your storyboard text below. Supports standard formats like:\n"
            "• Visual 1 Words: <narration> Visual: <visual description>\n"
            "• Scene 1: Words: ... Visual: ...\n"
            "• Plain numbered paragraphs"
        )
        desc.setStyleSheet("font-size: 11px; color: #94A3B8; line-height: 1.4;")
        layout.addWidget(desc)

        self.editor = QPlainTextEdit()
        self.editor.setPlainText(current_text)
        self.editor.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0D1510;
                color: #F0F5F0;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 10px;
                font-family: Consolas, monospace;
                font-size: 11px;
                line-height: 1.4;
            }
        """)
        layout.addWidget(self.editor, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedHeight(34)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #162019;
                color: #94A3B8;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                padding: 0 16px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #202D24; color: #fff; }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        self.apply_btn = QPushButton("✓ Apply Storyboard")
        self.apply_btn.setFixedHeight(34)
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #A3FF12;
                color: #080D0B;
                border: none;
                border-radius: 6px;
                padding: 0 20px;
                font-weight: 800;
            }
            QPushButton:hover { background-color: #B8FF24; }
        """)
        self.apply_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.apply_btn)

        layout.addLayout(btn_row)

    def get_text(self) -> str:
        return self.editor.toPlainText().strip()


class SceneSyncPanel(QWidget):
    """
    All-in-one One-Pager Studio Panel:
    Accepts:
    1. Voiceover Audio file
    2. Word Timestamps JSON file
    3. Storyboard file / text
    4. Images folder
    5. Subtitles toggle + Subtitles style preset
    And renders the final video directly in one click.
    """

    sync_completed = Signal(list, str, object)   # scenes, audio_path, narration
    navigate_to_deliverables = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.audio_path: Optional[str] = None
        self.json_path: Optional[str] = None
        self.storyboard_path: Optional[str] = None
        self.storyboard_text: str = ""
        self.images_folder: Optional[str] = None
        self.image_files: List[str] = []
        self.thumbnail_image_path: Optional[str] = None
        self.narration: Optional[NarrationData] = None
        self.scenes: List[VisualScene] = []
        self._project_dir: Optional[Path] = None
        self._prompts_path: Optional[Path] = None

        # Rendering state
        self._worker: Optional[VideoRenderWorker] = None
        self._output_video_path: Optional[str] = None
        self.settings = VideoRenderSettings(
            aspect_ratio=AspectRatio.LANDSCAPE_16_9,
            fps=30,
            motion_preset=MotionPreset.STATIC,
            video_overlay=VideoOverlay.NONE
        )

        # Audio playback
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._player.positionChanged.connect(self._on_player_pos_changed)
        self._player.durationChanged.connect(self._on_player_dur_changed)

        # File-watch timer: auto-detect new images dropped in folder
        self._watch_timer = QTimer(self)
        self._watch_timer.setInterval(3000)   # every 3 seconds
        self._watch_timer.timeout.connect(self._on_watch_tick)
        self._last_image_count = 0

        self._init_ui()

    # =========================================================================
    # UI BUILD (Glassmorphism One-Pager)
    # =========================================================================

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Smooth Scroll Area wrapping the entire one-pager
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #080D0B;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(163, 255, 18, 0.25);
                border-radius: 4px;
                min-height: 24px;
            }
            QScrollBar::handle:vertical:hover {
                background: #A3FF12;
            }
        """)

        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(20, 16, 20, 20)
        main_layout.setSpacing(14)

        # ── 1. Top Glass Header Banner ────────────────────────────────────────
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: rgba(20, 32, 24, 0.72);
                border: 1px solid rgba(163, 255, 18, 0.22);
                border-radius: 12px;
                padding: 12px 16px;
            }
        """)
        hf_layout = QHBoxLayout(header_frame)
        hf_layout.setContentsMargins(12, 8, 12, 8)

        titles_box = QVBoxLayout()
        titles_box.setSpacing(3)

        title_lbl = QLabel("⚡ Scene Sync — One-Click Video Production Studio")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #F0F5F0; letter-spacing: 0.4px;")
        desc_lbl = QLabel(
            "Load your voiceover audio, word timestamps JSON, visual storyboard, and images. "
            "Configure subtitles and render your complete video in one click."
        )
        desc_lbl.setStyleSheet("font-size: 11px; color: #94A3B8;")

        titles_box.addWidget(title_lbl)
        titles_box.addWidget(desc_lbl)
        hf_layout.addLayout(titles_box, 1)

        self.status_badge = QLabel("🟢 Ready to Sync & Render")
        self.status_badge.setStyleSheet("""
            font-size: 11px;
            font-weight: 700;
            color: #A3FF12;
            background: rgba(163, 255, 18, 0.12);
            border: 1px solid rgba(163, 255, 18, 0.4);
            border-radius: 8px;
            padding: 6px 12px;
        """)
        hf_layout.addWidget(self.status_badge)
        main_layout.addWidget(header_frame)

        # ── 2. The 4 Main Input Cards (2x2 Grid) ─────────────────────────────
        inputs_grid = QGridLayout()
        inputs_grid.setSpacing(12)

        # ── Card 1: Voiceover Audio Track ─────────────────────────────────────
        self.card_audio = QFrame()
        self.card_audio.setStyleSheet("""
            QFrame {
                background: rgba(15, 23, 42, 0.65);
                border: 1px solid rgba(56, 189, 248, 0.25);
                border-radius: 10px;
                padding: 10px;
            }
        """)
        ca_layout = QVBoxLayout(self.card_audio)
        ca_layout.setContentsMargins(10, 8, 10, 8)
        ca_layout.setSpacing(8)

        ca_hdr = QHBoxLayout()
        ca_title = QLabel("🎙️ 1. Voiceover Audio")
        ca_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #38BDF8;")
        self.audio_dur_lbl = QLabel("Duration: --:--")
        self.audio_dur_lbl.setStyleSheet("font-size: 11px; color: #94A3B8;")
        ca_hdr.addWidget(ca_title)
        ca_hdr.addStretch()
        ca_hdr.addWidget(self.audio_dur_lbl)
        ca_layout.addLayout(ca_hdr)

        ca_row = QHBoxLayout()
        ca_row.setSpacing(6)
        self.audio_path_edit = QLineEdit()
        self.audio_path_edit.setPlaceholderText("Select speech.mp3 / voiceover.wav...")
        self.audio_path_edit.setReadOnly(True)
        self.audio_path_edit.setStyleSheet("""
            background: #0B1118; color: #38BDF8; border: 1px solid #1E293B;
            border-radius: 6px; padding: 6px 10px; font-size: 11px; font-weight: 600;
        """)
        self.browse_audio_btn = QPushButton("📁 Browse Audio...")
        self.browse_audio_btn.setFixedHeight(30)
        self.browse_audio_btn.setCursor(Qt.PointingHandCursor)
        self.browse_audio_btn.setStyleSheet("""
            QPushButton {
                background-color: #1E293B; color: #38BDF8; border: 1px solid #0284C7;
                border-radius: 6px; padding: 0 12px; font-size: 11px; font-weight: 600;
            }
            QPushButton:hover { background-color: #0284C7; color: #fff; }
        """)
        self.browse_audio_btn.clicked.connect(self._on_browse_audio)
        ca_row.addWidget(self.audio_path_edit, 1)
        ca_row.addWidget(self.browse_audio_btn)
        ca_layout.addLayout(ca_row)

        # Mini player
        play_row = QHBoxLayout()
        play_row.setSpacing(8)
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setFixedHeight(26)
        self.play_btn.setFixedWidth(68)
        self.play_btn.setStyleSheet("""
            QPushButton {
                background: rgba(56, 189, 248, 0.15); color: #38BDF8; border: 1px solid rgba(56, 189, 248, 0.4);
                border-radius: 4px; font-size: 10px; font-weight: 700;
            }
            QPushButton:hover { background: #38BDF8; color: #080D0B; }
        """)
        self.play_btn.clicked.connect(self._toggle_play)
        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setStyleSheet("""
            QSlider::groove:horizontal { height: 4px; background: #1E293B; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #38BDF8; border-radius: 2px; }
            QSlider::handle:horizontal { width: 10px; margin: -3px 0; background: #38BDF8; border-radius: 5px; }
        """)
        self.seek_slider.sliderMoved.connect(self._on_slider_moved)
        play_row.addWidget(self.play_btn)
        play_row.addWidget(self.seek_slider, 1)
        ca_layout.addLayout(play_row)

        inputs_grid.addWidget(self.card_audio, 0, 0)

        # ── Card 2: Word Timestamps JSON ──────────────────────────────────────
        self.card_json = QFrame()
        self.card_json.setStyleSheet("""
            QFrame {
                background: rgba(15, 23, 42, 0.65);
                border: 1px solid rgba(52, 211, 153, 0.25);
                border-radius: 10px;
                padding: 10px;
            }
        """)
        cj_layout = QVBoxLayout(self.card_json)
        cj_layout.setContentsMargins(10, 8, 10, 8)
        cj_layout.setSpacing(8)

        cj_hdr = QHBoxLayout()
        cj_title = QLabel("⏱️ 2. Word Timestamps JSON")
        cj_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #34D399;")
        self.json_status_lbl = QLabel("No JSON loaded")
        self.json_status_lbl.setStyleSheet("font-size: 11px; color: #94A3B8;")
        cj_hdr.addWidget(cj_title)
        cj_hdr.addStretch()
        cj_hdr.addWidget(self.json_status_lbl)
        cj_layout.addLayout(cj_hdr)

        cj_row = QHBoxLayout()
        cj_row.setSpacing(6)
        self.json_path_edit = QLineEdit()
        self.json_path_edit.setPlaceholderText("Select speech.json (ElevenLabs / Whisper word timestamps)...")
        self.json_path_edit.setReadOnly(True)
        self.json_path_edit.setStyleSheet("""
            background: #0B1118; color: #34D399; border: 1px solid #1E293B;
            border-radius: 6px; padding: 6px 10px; font-size: 11px; font-weight: 600;
        """)
        self.browse_json_btn = QPushButton("📄 Import JSON...")
        self.browse_json_btn.setFixedHeight(30)
        self.browse_json_btn.setCursor(Qt.PointingHandCursor)
        self.browse_json_btn.setStyleSheet("""
            QPushButton {
                background-color: #1E293B; color: #34D399; border: 1px solid #059669;
                border-radius: 6px; padding: 0 12px; font-size: 11px; font-weight: 600;
            }
            QPushButton:hover { background-color: #059669; color: #fff; }
        """)
        self.browse_json_btn.clicked.connect(self._on_browse_json)
        cj_row.addWidget(self.json_path_edit, 1)
        cj_row.addWidget(self.browse_json_btn)
        cj_layout.addLayout(cj_row)

        cj_sub = QLabel("• Word-level timestamps provide 100% word-perfect karaoke subtitles and scene synchronization.")
        cj_sub.setStyleSheet("font-size: 10px; color: #64748B;")
        cj_sub.setWordWrap(True)
        cj_layout.addWidget(cj_sub)

        inputs_grid.addWidget(self.card_json, 0, 1)

        # ── Card 3: Visual Storyboard ─────────────────────────────────────────
        self.card_storyboard = QFrame()
        self.card_storyboard.setStyleSheet("""
            QFrame {
                background: rgba(15, 23, 42, 0.65);
                border: 1px solid rgba(251, 191, 36, 0.25);
                border-radius: 10px;
                padding: 10px;
            }
        """)
        cs_layout = QVBoxLayout(self.card_storyboard)
        cs_layout.setContentsMargins(10, 8, 10, 8)
        cs_layout.setSpacing(8)

        cs_hdr = QHBoxLayout()
        cs_title = QLabel("📋 3. Visual Storyboard")
        cs_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #FBBF24;")
        self.storyboard_status_lbl = QLabel("0 scenes")
        self.storyboard_status_lbl.setStyleSheet("font-size: 11px; color: #94A3B8;")
        cs_hdr.addWidget(cs_title)
        cs_hdr.addStretch()
        cs_hdr.addWidget(self.storyboard_status_lbl)
        cs_layout.addLayout(cs_hdr)

        cs_row = QHBoxLayout()
        cs_row.setSpacing(6)
        self.storyboard_path_edit = QLineEdit()
        self.storyboard_path_edit.setPlaceholderText("Select storyboard text/JSON file or paste script...")
        self.storyboard_path_edit.setReadOnly(True)
        self.storyboard_path_edit.setStyleSheet("""
            background: #0B1118; color: #FBBF24; border: 1px solid #1E293B;
            border-radius: 6px; padding: 6px 10px; font-size: 11px; font-weight: 600;
        """)
        self.browse_storyboard_btn = QPushButton("📑 Load File...")
        self.browse_storyboard_btn.setFixedHeight(30)
        self.browse_storyboard_btn.setCursor(Qt.PointingHandCursor)
        self.browse_storyboard_btn.setStyleSheet("""
            QPushButton {
                background-color: #1E293B; color: #FBBF24; border: 1px solid #D97706;
                border-radius: 6px; padding: 0 10px; font-size: 11px; font-weight: 600;
            }
            QPushButton:hover { background-color: #D97706; color: #080D0B; }
        """)
        self.browse_storyboard_btn.clicked.connect(self._on_browse_storyboard)

        self.paste_storyboard_btn = QPushButton("✏️ Paste / View")
        self.paste_storyboard_btn.setFixedHeight(30)
        self.paste_storyboard_btn.setCursor(Qt.PointingHandCursor)
        self.paste_storyboard_btn.setStyleSheet("""
            QPushButton {
                background-color: #1E293B; color: #F3F1EC; border: 1px solid #4B5563;
                border-radius: 6px; padding: 0 10px; font-size: 11px; font-weight: 600;
            }
            QPushButton:hover { background-color: #374151; }
        """)
        self.paste_storyboard_btn.clicked.connect(self._on_paste_storyboard)

        cs_row.addWidget(self.storyboard_path_edit, 1)
        cs_row.addWidget(self.browse_storyboard_btn)
        cs_row.addWidget(self.paste_storyboard_btn)
        cs_layout.addLayout(cs_row)

        cs_sub = QLabel("• Auto-extracts visual beats and narration lines (e.g. Visual 1 Words: ... Visual: ...)")
        cs_sub.setStyleSheet("font-size: 10px; color: #64748B;")
        cs_sub.setWordWrap(True)
        cs_layout.addWidget(cs_sub)

        inputs_grid.addWidget(self.card_storyboard, 1, 0)

        # ── Card 4: Generated Images Folder ───────────────────────────────────
        self.card_images = QFrame()
        self.card_images.setStyleSheet("""
            QFrame {
                background: rgba(15, 23, 42, 0.65);
                border: 1px solid rgba(167, 139, 250, 0.25);
                border-radius: 10px;
                padding: 10px;
            }
        """)
        ci_layout = QVBoxLayout(self.card_images)
        ci_layout.setContentsMargins(10, 8, 10, 8)
        ci_layout.setSpacing(8)

        ci_hdr = QHBoxLayout()
        ci_title = QLabel("🖼️ 4. Images Folder")
        ci_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #A78BFA;")
        self.img_count_badge = QLabel("0 images ready")
        self.img_count_badge.setStyleSheet("font-size: 11px; color: #94A3B8;")
        ci_hdr.addWidget(ci_title)
        ci_hdr.addStretch()
        ci_hdr.addWidget(self.img_count_badge)
        ci_layout.addLayout(ci_hdr)

        ci_row = QHBoxLayout()
        ci_row.setSpacing(6)
        self.img_folder_edit = QLineEdit()
        self.img_folder_edit.setPlaceholderText("Select folder containing 001.png, 002.png...")
        self.img_folder_edit.setReadOnly(True)
        self.img_folder_edit.setStyleSheet("""
            background: #0B1118; color: #A78BFA; border: 1px solid #1E293B;
            border-radius: 6px; padding: 6px 10px; font-size: 11px; font-weight: 600;
        """)
        self.browse_images_btn = QPushButton("📁 Select Folder...")
        self.browse_images_btn.setFixedHeight(30)
        self.browse_images_btn.setCursor(Qt.PointingHandCursor)
        self.browse_images_btn.setStyleSheet("""
            QPushButton {
                background-color: #1E293B; color: #A78BFA; border: 1px solid #7C3AED;
                border-radius: 6px; padding: 0 10px; font-size: 11px; font-weight: 600;
            }
            QPushButton:hover { background-color: #7C3AED; color: #fff; }
        """)
        self.browse_images_btn.clicked.connect(self._on_browse_images_folder)

        self.unpack_zip_btn = QPushButton("📥 Unpack ZIP / Scan")
        self.unpack_zip_btn.setFixedHeight(30)
        self.unpack_zip_btn.setCursor(Qt.PointingHandCursor)
        self.unpack_zip_btn.setStyleSheet("""
            QPushButton {
                background-color: #1E293B; color: #E2E8F0; border: 1px solid #4B5563;
                border-radius: 6px; padding: 0 10px; font-size: 11px; font-weight: 600;
            }
            QPushButton:hover { background-color: #374151; }
        """)
        self.unpack_zip_btn.clicked.connect(self._on_import_downloads)

        ci_row.addWidget(self.img_folder_edit, 1)
        ci_row.addWidget(self.browse_images_btn)
        ci_row.addWidget(self.unpack_zip_btn)
        ci_layout.addLayout(ci_row)

        ci_sub = QLabel("• Direct 1-to-1 sequential mapping: 001.png -> Scene #001, 002.png -> Scene #002.")
        ci_sub.setStyleSheet("font-size: 10px; color: #64748B;")
        ci_sub.setWordWrap(True)
        ci_layout.addWidget(ci_sub)

        inputs_grid.addWidget(self.card_images, 1, 1)
        main_layout.addLayout(inputs_grid)

        # ── 3. Subtitles & Typography Configuration Glass Card ───────────────
        sub_card = QFrame()
        sub_card.setStyleSheet("""
            QFrame {
                background: rgba(18, 28, 22, 0.72);
                border: 1px solid rgba(163, 255, 18, 0.18);
                border-radius: 12px;
                padding: 12px;
            }
        """)
        sc_layout = QVBoxLayout(sub_card)
        sc_layout.setContentsMargins(12, 10, 12, 10)
        sc_layout.setSpacing(10)

        sc_top = QHBoxLayout()
        sc_lbl = QLabel("✨ Subtitles & Karaoke Typography Studio")
        sc_lbl.setStyleSheet("font-size: 13px; font-weight: 800; color: #A3FF12;")
        sc_top.addWidget(sc_lbl)
        sc_top.addStretch()

        # Modern Subtitles YES / NO Toggle Switch
        self.subtitle_toggle_btn = QPushButton("🟢 Subtitles: YES")
        self.subtitle_toggle_btn.setCheckable(True)
        self.subtitle_toggle_btn.setChecked(True)
        self.subtitle_toggle_btn.setFixedHeight(30)
        self.subtitle_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.subtitle_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(16, 185, 129, 0.2);
                color: #34D399;
                border: 1px solid #10B981;
                border-radius: 6px;
                padding: 0 14px;
                font-weight: 800;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(16, 185, 129, 0.35);
            }
        """)
        self.subtitle_toggle_btn.clicked.connect(self._toggle_subtitles)
        sc_top.addWidget(self.subtitle_toggle_btn)
        sc_layout.addLayout(sc_top)

        # Subtitle Controls Row
        self.sub_controls_row = QHBoxLayout()
        self.sub_controls_row.setSpacing(12)

        lbl_preset = QLabel("Subtitle Style Preset:")
        lbl_preset.setStyleSheet("font-size: 11px; font-weight: 700; color: #cbd5e1;")
        self.sub_preset_combo = QComboBox()
        self.sub_preset_combo.setFixedHeight(32)
        self.sub_preset_combo.addItem("🔥 Hormozi Karaoke (Bold Yellow Pop · Black Outline)", SubtitlePreset.HORMOZI_KARAOKE)
        self.sub_preset_combo.addItem("🎬 Cinematic Gold (Warm Gold Amber · Elegant)", SubtitlePreset.CINEMATIC_GOLD)
        self.sub_preset_combo.addItem("⚡ Neon Cyberpunk (Cyan & Mint Electric Glow)", SubtitlePreset.NEON_CYBERPUNK)
        self.sub_preset_combo.addItem("💥 MrBeast Bold (Punchy Red & Yellow Impact)", SubtitlePreset.MRBEAST_BOLD)
        self.sub_preset_combo.addItem("✨ Minimalist Clean (Pure White Modern Sans)", SubtitlePreset.MINIMALIST_CLEAN)
        self.sub_preset_combo.addItem("⬛ Boxed Dark (Translucent Dark Badge)", SubtitlePreset.BOXED_DARK)
        self.sub_preset_combo.addItem("🔮 TikTok Pop (Vivid Pastel Pink Pop)", SubtitlePreset.TIKTOK_POP)
        self.sub_preset_combo.setStyleSheet("""
            QComboBox {
                background: #0B1118; color: #F0F5F0; border: 1px solid #1E293B;
                border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: 600;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background: #0F172A; color: #F8FAFC; selection-background-color: #0284C7;
                border: 1px solid #334155; border-radius: 6px;
            }
        """)
        self.sub_preset_combo.currentIndexChanged.connect(self._on_subtitle_preset_changed)
        self.sub_controls_row.addWidget(lbl_preset)
        self.sub_controls_row.addWidget(self.sub_preset_combo, 1)

        lbl_size = QLabel("Font Size:")
        lbl_size.setStyleSheet("font-size: 11px; font-weight: 700; color: #cbd5e1;")
        self.sub_size_combo = QComboBox()
        self.sub_size_combo.setFixedHeight(32)
        self.sub_size_combo.addItem("Medium (44px)", 44)
        self.sub_size_combo.addItem("Large (54px)", 54)
        self.sub_size_combo.addItem("Extra Large (64px)", 64)
        self.sub_size_combo.setCurrentIndex(1)
        self.sub_size_combo.setStyleSheet(self.sub_preset_combo.styleSheet())
        self.sub_size_combo.currentIndexChanged.connect(self._on_subtitle_size_changed)
        self.sub_controls_row.addWidget(lbl_size)
        self.sub_controls_row.addWidget(self.sub_size_combo)

        sc_layout.addLayout(self.sub_controls_row)

        # Live Subtitle Styled Preview Card
        self.sub_preview_lbl = QLabel(
            "SIXTY PEOPLE WERE LOCKED INSIDE THIS MALL"
        )
        self.sub_preview_lbl.setFixedHeight(44)
        self.sub_preview_lbl.setAlignment(Qt.AlignCenter)
        self.sub_preview_lbl.setStyleSheet("""
            background: #080C12;
            color: #FFD700;
            font-family: Impact;
            font-size: 20px;
            font-weight: 900;
            letter-spacing: 1px;
            border: 1px solid rgba(255, 215, 0, 0.35);
            border-radius: 8px;
        """)
        sc_layout.addWidget(self.sub_preview_lbl)
        main_layout.addWidget(sub_card)

        # ── 4. Hero Execution: Big Render CTA + Progress + Status ─────────────
        hero_render_card = QFrame()
        hero_render_card.setStyleSheet("""
            QFrame {
                background: rgba(14, 26, 18, 0.88);
                border: 1px solid rgba(163, 255, 18, 0.4);
                border-radius: 12px;
                padding: 14px;
            }
        """)
        hr_layout = QVBoxLayout(hero_render_card)
        hr_layout.setContentsMargins(14, 12, 14, 12)
        hr_layout.setSpacing(10)

        # Big Hero Render Button (Electric Lime CTA)
        self.render_btn = QPushButton("🚀  RENDER FINAL VIDEO (ONE-CLICK)")
        self.render_btn.setFixedHeight(48)
        self.render_btn.setCursor(Qt.PointingHandCursor)
        self.render_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #A3FF12, stop:0.5 #34D399, stop:1 #10B981);
                color: #061109;
                font-size: 14px;
                font-weight: 900;
                letter-spacing: 0.8px;
                border-radius: 8px;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #B8FF24, stop:0.5 #4ADE80, stop:1 #059669);
            }
            QPushButton:disabled {
                background: #1B291F;
                color: #4B5563;
                border: 1px solid rgba(255, 255, 255, 0.06);
            }
        """)
        self.render_btn.clicked.connect(self._on_start_one_click_render)
        hr_layout.addWidget(self.render_btn)

        # Progress bar
        self.render_progress = QProgressBar()
        self.render_progress.setFixedHeight(8)
        self.render_progress.setRange(0, 100)
        self.render_progress.setValue(0)
        self.render_progress.setTextVisible(False)
        self.render_progress.setStyleSheet("""
            QProgressBar {
                background-color: #0B1118;
                border-radius: 4px;
                border: 1px solid #1E293B;
            }
            QProgressBar::chunk {
                background-color: #A3FF12;
                border-radius: 3px;
            }
        """)
        hr_layout.addWidget(self.render_progress)

        # Render status + actions row
        status_action_row = QHBoxLayout()
        self.render_status_lbl = QLabel("Ready to render. Provide audio and images, then click Render Final Video.")
        self.render_status_lbl.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: 500;")
        status_action_row.addWidget(self.render_status_lbl, 1)

        self.play_video_btn = QPushButton("▶️ Play Video")
        self.play_video_btn.setFixedHeight(32)
        self.play_video_btn.setCursor(Qt.PointingHandCursor)
        self.play_video_btn.setStyleSheet("""
            QPushButton {
                background-color: #A3FF12; color: #080D0B; font-weight: 800; font-size: 11px;
                border-radius: 6px; padding: 0 16px; border: none;
            }
            QPushButton:hover { background-color: #B8FF24; }
        """)
        self.play_video_btn.clicked.connect(self._on_play_rendered_video)
        self.play_video_btn.setVisible(False)
        status_action_row.addWidget(self.play_video_btn)

        self.open_folder_btn = QPushButton("📂 Open Output Folder")
        self.open_folder_btn.setFixedHeight(32)
        self.open_folder_btn.setCursor(Qt.PointingHandCursor)
        self.open_folder_btn.setStyleSheet("""
            QPushButton {
                background-color: #1E293B; color: #F0F5F0; font-weight: 700; font-size: 11px;
                border-radius: 6px; padding: 0 14px; border: 1px solid #334155;
            }
            QPushButton:hover { background-color: #334155; color: #fff; }
        """)
        self.open_folder_btn.clicked.connect(self._on_open_output_folder)
        self.open_folder_btn.setVisible(False)
        status_action_row.addWidget(self.open_folder_btn)

        hr_layout.addLayout(status_action_row)
        main_layout.addWidget(hero_render_card)

        # ── 5. Synchronized Timeline Scenes Table ─────────────────────────────
        table_card = QFrame()
        table_card.setStyleSheet("""
            QFrame {
                background: rgba(15, 23, 42, 0.65);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
                padding: 10px;
            }
        """)
        tc_layout = QVBoxLayout(table_card)
        tc_layout.setContentsMargins(10, 8, 10, 8)
        tc_layout.setSpacing(8)

        tc_hdr = QHBoxLayout()
        tc_title = QLabel("🎞️ Synchronized Scenes & Visual Beats")
        tc_title.setStyleSheet("font-size: 12px; font-weight: 800; color: #E2E8F0;")
        self.scenes_summary_lbl = QLabel("0 Scenes Synced")
        self.scenes_summary_lbl.setStyleSheet("font-size: 11px; color: #94A3B8; font-weight: 600;")
        tc_hdr.addWidget(tc_title)
        tc_hdr.addStretch()
        tc_hdr.addWidget(self.scenes_summary_lbl)
        tc_layout.addLayout(tc_hdr)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["Scene #", "Preview", "Image Filename", "Start Time", "End Time", "Duration", "Narration Excerpt"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(54)
        self.table.verticalHeader().hide()
        self.table.setMinimumHeight(240)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #080D0B;
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 8px;
                color: #F8FAFC;
                gridline-color: #162019;
            }
            QHeaderView::section {
                background-color: #0E1611;
                color: #94A3B8;
                font-weight: 700;
                font-size: 11px;
                border: none;
                border-bottom: 1px solid rgba(163, 255, 18, 0.15);
                padding: 6px;
            }
        """)
        tc_layout.addWidget(self.table)
        main_layout.addWidget(table_card)

        scroll.setWidget(container)
        root_layout.addWidget(scroll)

        # Apply initial subtitle styling
        self._on_subtitle_preset_changed()

    # =========================================================================
    # PUBLIC API & BACKWARD COMPATIBILITY
    # =========================================================================

    def set_project(self, project_dir: Path):
        """Called by MainWindow when project is loaded or generation completes."""
        self._project_dir = Path(project_dir)
        img_dir = self._project_dir / "images"
        img_dir.mkdir(parents=True, exist_ok=True)
        self.set_images_folder(str(img_dir))

        for name in ("prompts_only.txt", "prompts.txt", "image_prompts.txt"):
            p = self._project_dir / name
            if p.exists():
                self._prompts_path = p
                break

    def set_audio_path(self, path: str):
        """Auto-load audio from project state."""
        if path and Path(path).exists():
            self.audio_path = str(Path(path).resolve())
            self.audio_path_edit.setText(Path(path).name)
            self._player.setSource(QUrl.fromLocalFile(self.audio_path))
            self._update_audio_duration_label()

            # Auto-check companion speech.json in same dir
            p = Path(self.audio_path)
            for cname in (f"{p.stem}.json", "speech.json", "narration_timestamps.json", "timestamps.json"):
                cand = p.parent / cname
                if cand.exists():
                    self.load_json_file(str(cand.resolve()))
                    break
        else:
            self._auto_find_audio()

    def set_images_folder(self, folder: str):
        """Set images folder and auto-scan."""
        if folder:
            p = Path(folder)
            p.mkdir(parents=True, exist_ok=True)
            self.images_folder = str(p.resolve())
            self.img_folder_edit.setText(str(p.resolve()))
            self._scan_images()
            if not self._watch_timer.isActive():
                self._watch_timer.start()

    # =========================================================================
    # ASSET BROWSING & LOADING
    # =========================================================================

    def _on_browse_audio(self):
        start_dir = "audio and files" if Path("audio and files").exists() else "."
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Voiceover Audio File",
            start_dir,
            "Audio Files (*.mp3 *.wav *.m4a *.aac *.flac *.ogg);;All Files (*.*)"
        )
        if file_path:
            self.set_audio_path(file_path)
            self._auto_sync_pipeline()

    def _on_browse_json(self):
        start_dir = "audio and files" if Path("audio and files").exists() else "."
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Word Timestamps JSON",
            start_dir,
            "JSON Files (*.json);;All Files (*.*)"
        )
        if file_path:
            self.load_json_file(file_path)
            self._auto_sync_pipeline()

    def load_json_file(self, path: str):
        """Loads and parses speech.json or timestamps.json."""
        res = import_script_json(path)
        if not res.success:
            QMessageBox.critical(self, "JSON Import Error", res.message)
            return

        self.json_path = str(Path(path).resolve())
        self.json_path_edit.setText(Path(path).name)
        self.narration = res.narration

        words_cnt = len(res.narration.words) if res.narration and res.narration.words else 0
        dur_s = res.narration.duration_seconds if res.narration else 0.0
        self.json_status_lbl.setText(f"✅ {words_cnt} words ({dur_s:.1f}s)")
        self.json_status_lbl.setStyleSheet("font-size: 11px; color: #34D399; font-weight: 700;")

        # Auto-detect audio if not yet selected
        if not self.audio_path:
            parent_d = Path(path).parent
            for ext in (".mp3", ".wav", ".m4a"):
                cand = parent_d / f"{Path(path).stem}{ext}"
                if cand.exists():
                    self.set_audio_path(str(cand.resolve()))
                    break
                scand = parent_d / f"speech{ext}"
                if scand.exists():
                    self.set_audio_path(str(scand.resolve()))
                    break

    def _on_browse_storyboard(self):
        start_dir = "audio and files" if Path("audio and files").exists() else "."
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Storyboard File",
            start_dir,
            "Storyboard Files (*.txt *.json);;All Files (*.*)"
        )
        if file_path:
            self.load_storyboard_file(file_path)
            self._auto_sync_pipeline()

    def load_storyboard_file(self, path: str):
        """Loads storyboard from text file or JSON."""
        p = Path(path)
        try:
            content = p.read_text(encoding="utf-8")
            self.storyboard_path = str(p.resolve())
            self.storyboard_text = content
            self.storyboard_path_edit.setText(p.name)

            items = parse_visual_breakdown_text(content)
            if items:
                self._apply_parsed_storyboard_items(items)
        except Exception as e:
            QMessageBox.warning(self, "Storyboard Read Notice", f"Could not read storyboard file:\n{e}")

    def _on_paste_storyboard(self):
        dlg = PasteStoryboardDialog(self.storyboard_text, self)
        if dlg.exec() == QDialog.Accepted:
            txt = dlg.get_text()
            if txt:
                self.storyboard_text = txt
                self.storyboard_path_edit.setText("Custom Pasted Storyboard")
                items = parse_visual_breakdown_text(txt)
                if items:
                    self._apply_parsed_storyboard_items(items)
                    self._auto_sync_pipeline()

    def _apply_parsed_storyboard_items(self, items: List[Dict[str, str]]):
        """Aligns parsed visual items with narration or paces them evenly."""
        total_audio_dur = self.narration.duration_seconds if self.narration else None
        if not total_audio_dur and self.audio_path:
            total_audio_dur = self._probe_audio_duration()

        self.scenes = align_visuals_with_timestamps(
            visual_items=items,
            narration=self.narration,
            total_audio_duration=total_audio_dur
        )
        self.storyboard_status_lbl.setText(f"✅ {len(self.scenes)} scenes loaded")
        self.storyboard_status_lbl.setStyleSheet("font-size: 11px; color: #FBBF24; font-weight: 700;")

    def _on_browse_images_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Generated Images Folder")
        if folder:
            self.set_images_folder(folder)
            self._auto_sync_pipeline()

    def _scan_images(self):
        """Scans image files in images_folder and natural-sorts them."""
        if not self.images_folder or not Path(self.images_folder).exists():
            return
        p = Path(self.images_folder)
        exts = {".png", ".jpg", ".jpeg", ".webp"}
        files = [str(f.resolve()) for f in p.iterdir() if f.is_file() and f.suffix.lower() in exts]
        files.sort(key=natural_sort_key)
        self.image_files = files

        cnt = len(files)
        self.img_count_badge.setText(f"{cnt} images ready")
        self.img_count_badge.setStyleSheet(
            "font-size: 11px; color: #A78BFA; font-weight: 700;" if cnt > 0 else "font-size: 11px; color: #94A3B8;"
        )

    # =========================================================================
    # PIPELINE AUTOMATION & DIRECT 1-TO-1 SYNC
    # =========================================================================

    def _auto_sync_pipeline(self):
        """Synchronizes scenes, timestamps, and images directly 1-to-1."""
        if not self.image_files and self.images_folder:
            self._scan_images()

        # If storyboard scenes don't exist yet, construct them from images or audio
        if not self.scenes and self.image_files:
            dur = self._probe_audio_duration()
            time_per_image = dur / float(max(1, len(self.image_files)))
            auto_scenes = []
            for idx, img_path in enumerate(self.image_files):
                st = round(idx * time_per_image, 2)
                et = round((idx + 1) * time_per_image, 2) if idx < len(self.image_files) - 1 else round(dur, 2)
                auto_scenes.append(VisualScene(
                    scene_id=f"{idx+1:03d}",
                    start=st,
                    end=et,
                    duration=round(et - st, 2),
                    visual_subject=Path(img_path).stem,
                    narration_excerpt=f"Visual Beat #{idx+1}",
                    image_path=img_path
                ))
            self.scenes = auto_scenes

        # Direct 1-to-1 sequential binding
        if self.scenes and self.images_folder:
            self.scenes, bound = AssetManager.auto_bind_images_to_scenes(self.scenes, self.images_folder)

        self._populate_table()
        self.sync_completed.emit(self.scenes, self.audio_path or "", self.narration)

    def _populate_table(self):
        """Fills table with scenes, thumbnails, start/end timestamps, and narration excerpts."""
        total_scenes = len(self.scenes)
        self.table.setRowCount(total_scenes)
        self.scenes_summary_lbl.setText(f"🟢 {total_scenes} Scenes Synchronized (1-to-1)")

        for s_idx, sc in enumerate(self.scenes):
            it_num = QTableWidgetItem(f"#{sc.scene_id}")
            it_num.setTextAlignment(Qt.AlignCenter)
            it_num.setForeground(QColor("#A3FF12"))
            self.table.setItem(s_idx, 0, it_num)

            thumb_lbl = QLabel()
            thumb_lbl.setFixedSize(50, 42)
            thumb_lbl.setAlignment(Qt.AlignCenter)
            if sc.image_path and Path(sc.image_path).exists():
                pix = QPixmap(sc.image_path)
                if not pix.isNull():
                    thumb_lbl.setPixmap(pix.scaled(50, 42, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.table.setCellWidget(s_idx, 1, thumb_lbl)

            fname = Path(sc.image_path).name if sc.image_path else "Not Bound"
            it_fn = QTableWidgetItem(fname)
            it_fn.setForeground(QColor("#E2E8F0"))
            self.table.setItem(s_idx, 2, it_fn)

            it_st = QTableWidgetItem(f"{sc.start:.2f}s")
            it_st.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(s_idx, 3, it_st)

            it_et = QTableWidgetItem(f"{sc.end:.2f}s")
            it_et.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(s_idx, 4, it_et)

            it_dur = QTableWidgetItem(f"{sc.duration:.2f}s")
            it_dur.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(s_idx, 5, it_dur)

            it_words = QTableWidgetItem(sc.narration_excerpt or sc.visual_subject or "")
            it_words.setForeground(QColor("#94A3B8"))
            self.table.setItem(s_idx, 6, it_words)

    # =========================================================================
    # SUBTITLES CONFIGURATION & PRESETS
    # =========================================================================

    def _toggle_subtitles(self):
        is_on = self.subtitle_toggle_btn.isChecked()
        if is_on:
            self.subtitle_toggle_btn.setText("🟢 Subtitles: YES")
            self.subtitle_toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(16, 185, 129, 0.2);
                    color: #34D399;
                    border: 1px solid #10B981;
                    border-radius: 6px;
                    padding: 0 14px;
                    font-weight: 800;
                    font-size: 11px;
                }
            """)
            self.sub_preset_combo.setEnabled(True)
            self.sub_size_combo.setEnabled(True)
            self.sub_preview_lbl.setVisible(True)
            self._on_subtitle_preset_changed()
        else:
            self.subtitle_toggle_btn.setText("⚪ Subtitles: NO")
            self.subtitle_toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(75, 85, 99, 0.2);
                    color: #94A3B8;
                    border: 1px solid #4B5563;
                    border-radius: 6px;
                    padding: 0 14px;
                    font-weight: 800;
                    font-size: 11px;
                }
            """)
            self.sub_preset_combo.setEnabled(False)
            self.sub_size_combo.setEnabled(False)
            self.sub_preview_lbl.setVisible(False)
            self.settings.subtitle_config.preset = SubtitlePreset.NONE

    def _on_subtitle_preset_changed(self):
        preset = self.sub_preset_combo.currentData()
        if not preset or not self.subtitle_toggle_btn.isChecked():
            self.settings.subtitle_config.preset = SubtitlePreset.NONE
            return

        cfg = self.settings.subtitle_config
        cfg.preset = preset
        size = self.sub_size_combo.currentData() or 54
        cfg.font_size = size

        if preset == SubtitlePreset.HORMOZI_KARAOKE:
            cfg.font_name = "Impact"
            cfg.primary_color_hex = "#FFFFFF"
            cfg.highlight_color_hex = "#FFD700"
            cfg.outline_color_hex = "#000000"
            cfg.outline_width = 4
            cfg.is_karaoke = True
            self.sub_preview_lbl.setStyleSheet("""
                background: #080C12; color: #FFD700; font-family: Impact; font-size: 20px; font-weight: 900;
                letter-spacing: 1px; border: 1px solid rgba(255, 215, 0, 0.4); border-radius: 8px;
            """)
        elif preset == SubtitlePreset.CINEMATIC_GOLD:
            cfg.font_name = "Montserrat"
            cfg.primary_color_hex = "#F8FAFC"
            cfg.highlight_color_hex = "#F59E0B"
            cfg.outline_color_hex = "#0F172A"
            cfg.outline_width = 2
            cfg.is_karaoke = True
            self.sub_preview_lbl.setStyleSheet("""
                background: #080C12; color: #F59E0B; font-family: 'Segoe UI', Montserrat; font-size: 18px; font-weight: 800;
                letter-spacing: 0.5px; border: 1px solid rgba(245, 158, 11, 0.4); border-radius: 8px;
            """)
        elif preset == SubtitlePreset.NEON_CYBERPUNK:
            cfg.font_name = "Impact"
            cfg.primary_color_hex = "#10B981"
            cfg.highlight_color_hex = "#06B6D4"
            cfg.outline_color_hex = "#020617"
            cfg.outline_width = 3
            cfg.is_karaoke = True
            self.sub_preview_lbl.setStyleSheet("""
                background: #080C12; color: #06B6D4; font-family: Impact; font-size: 20px; font-weight: 900;
                letter-spacing: 1px; border: 1px solid rgba(6, 182, 212, 0.4); border-radius: 8px;
            """)
        elif preset == SubtitlePreset.MRBEAST_BOLD:
            cfg.font_name = "Impact"
            cfg.primary_color_hex = "#FACC15"
            cfg.highlight_color_hex = "#EF4444"
            cfg.outline_color_hex = "#000000"
            cfg.outline_width = 5
            cfg.is_karaoke = True
            self.sub_preview_lbl.setStyleSheet("""
                background: #080C12; color: #EF4444; font-family: Impact; font-size: 22px; font-weight: 900;
                letter-spacing: 1px; border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 8px;
            """)
        elif preset == SubtitlePreset.MINIMALIST_CLEAN:
            cfg.font_name = "Segoe UI"
            cfg.primary_color_hex = "#FFFFFF"
            cfg.highlight_color_hex = "#CBD5E1"
            cfg.outline_color_hex = "#1E293B"
            cfg.outline_width = 1
            cfg.is_karaoke = False
            self.sub_preview_lbl.setStyleSheet("""
                background: #080C12; color: #FFFFFF; font-family: 'Segoe UI'; font-size: 17px; font-weight: 600;
                letter-spacing: 0.3px; border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 8px;
            """)
        elif preset == SubtitlePreset.BOXED_DARK:
            cfg.font_name = "Segoe UI"
            cfg.primary_color_hex = "#FFFFFF"
            cfg.highlight_color_hex = "#FBBF24"
            cfg.outline_color_hex = "#000000"
            cfg.outline_width = 2
            cfg.is_karaoke = True
            self.sub_preview_lbl.setStyleSheet("""
                background: rgba(0,0,0,0.8); color: #FBBF24; font-family: 'Segoe UI'; font-size: 18px; font-weight: 700;
                border: 1px solid rgba(251, 191, 36, 0.4); border-radius: 8px;
            """)
        elif preset == SubtitlePreset.TIKTOK_POP:
            cfg.font_name = "Montserrat"
            cfg.primary_color_hex = "#FFFFFF"
            cfg.highlight_color_hex = "#F472B6"
            cfg.outline_color_hex = "#581C87"
            cfg.outline_width = 3
            cfg.is_karaoke = True
            self.sub_preview_lbl.setStyleSheet("""
                background: #080C12; color: #F472B6; font-family: Impact; font-size: 20px; font-weight: 900;
                border: 1px solid rgba(244, 114, 182, 0.4); border-radius: 8px;
            """)

    def _on_subtitle_size_changed(self):
        size = self.sub_size_combo.currentData()
        if size:
            self.settings.subtitle_config.font_size = size

    # =========================================================================
    # SINGLE-CLICK VIDEO RENDERING
    # =========================================================================

    def _on_start_one_click_render(self):
        """Main action CTA: Validates assets, configures subtitles, and compiles video."""
        if not self.audio_path or not Path(self.audio_path).exists():
            QMessageBox.warning(self, "Missing Audio", "Please select or import a voiceover audio file (.mp3 / .wav).")
            return

        if not self.image_files and not any(sc.image_path for sc in self.scenes):
            QMessageBox.warning(self, "Missing Images", "Please select an images folder containing your visual scenes.")
            return

        if not self.scenes:
            self._auto_sync_pipeline()

        if not self.scenes:
            QMessageBox.warning(self, "No Storyboard Scenes", "Could not synchronize scenes. Please provide a storyboard.")
            return

        # Synchronize narration for subtitles
        if (not self.narration or not self.narration.words) and self.scenes:
            self.narration = SubtitleEngine.synthesize_narration_from_scenes(self.scenes)

        # Output file destination
        out_dir = Path(self._project_dir) if self._project_dir else Path("projects/output")
        renders_dir = out_dir / "renders"
        renders_dir.mkdir(parents=True, exist_ok=True)

        is_sub = self.subtitle_toggle_btn.isChecked()
        p_name = Path(self._project_dir).name if self._project_dir else "Rendered_Video"
        suffix = "_subtitles.mp4" if is_sub else "_clean.mp4"
        output_file = str((renders_dir / f"{p_name}{suffix}").resolve())
        self._output_video_path = output_file

        self.render_btn.setEnabled(False)
        self.render_progress.setValue(5)
        self.render_status_lbl.setText("Compiling video with FFmpeg...")
        self.render_status_lbl.setStyleSheet("color: #38BDF8; font-size: 11px;")
        self.play_video_btn.setVisible(False)
        self.open_folder_btn.setVisible(False)

        self._worker = VideoRenderWorker(
            scenes=self.scenes,
            audio_path=self.audio_path,
            output_video_path=output_file,
            settings=self.settings,
            narration=self.narration,
            parent=self
        )
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    def _on_worker_progress(self, pct: float, msg: str):
        self.render_progress.setValue(int(pct))
        self.render_status_lbl.setText(msg)

    def _on_worker_finished(self, out_path: str):
        self._output_video_path = out_path
        self.render_progress.setValue(100)
        self.render_btn.setEnabled(True)
        fname = Path(out_path).name
        self.render_status_lbl.setText(f"✅ Video render complete: {fname}")
        self.render_status_lbl.setStyleSheet("color: #A3FF12; font-size: 11px; font-weight: 700;")
        self.play_video_btn.setVisible(True)
        self.open_folder_btn.setVisible(True)
        QMessageBox.information(self, "Render Complete", f"Your final video has been produced successfully:\n{out_path}")

    def _on_worker_error(self, err: str):
        self.render_btn.setEnabled(True)
        self.render_progress.setValue(0)
        self.render_status_lbl.setText(f"❌ Render error: {err[:80]}")
        self.render_status_lbl.setStyleSheet("color: #EF4444; font-size: 11px; font-weight: 700;")
        QMessageBox.critical(self, "Video Render Error", f"Video compilation failed:\n{err}")

    def _on_play_rendered_video(self):
        if self._output_video_path and Path(self._output_video_path).exists():
            if os.name == "nt":
                os.startfile(self._output_video_path)
            else:
                subprocess.Popen(["xdg-open", self._output_video_path])

    def _on_open_output_folder(self):
        if self._output_video_path:
            p = Path(self._output_video_path).parent
            if p.exists():
                if os.name == "nt":
                    subprocess.Popen(f'explorer /select,"{Path(self._output_video_path).resolve()}"')
                else:
                    subprocess.Popen(["xdg-open", str(p)])

    # =========================================================================
    # AUDIO CONTROLS & HELPERS
    # =========================================================================

    def _probe_audio_duration(self) -> float:
        """Determines audio duration via ffprobe or QMediaPlayer."""
        if self.narration and self.narration.duration_seconds > 0:
            return self.narration.duration_seconds
        if self.audio_path and Path(self.audio_path).exists():
            try:
                cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", self.audio_path]
                res = subprocess.run(cmd, capture_output=True, text=True)
                dur = float(res.stdout.strip())
                if dur > 0:
                    return dur
            except Exception:
                pass
        return 60.0

    def _update_audio_duration_label(self):
        dur = self._probe_audio_duration()
        mins = int(dur // 60)
        secs = int(dur % 60)
        self.audio_dur_lbl.setText(f"Duration: {mins:02d}:{secs:02d} ({dur:.1f}s)")

    def _toggle_play(self):
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
            self.play_btn.setText("▶ Play")
        else:
            self._player.play()
            self.play_btn.setText("⏸ Pause")

    def _on_player_pos_changed(self, pos: int):
        dur = self._player.duration()
        if dur > 0:
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(int(pos * 1000 / dur))
            self.seek_slider.blockSignals(False)

    def _on_player_dur_changed(self, dur: int):
        self._update_audio_duration_label()

    def _on_slider_moved(self, val: int):
        dur = self._player.duration()
        if dur > 0:
            self._player.setPosition(int(val * dur / 1000))

    def _on_watch_tick(self):
        """Auto-refreshes when new images are downloaded."""
        if self.images_folder and Path(self.images_folder).exists():
            cnt = len([f for f in Path(self.images_folder).iterdir() if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}])
            if cnt != self._last_image_count:
                self._last_image_count = cnt
                self._scan_images()
                self._auto_sync_pipeline()

    def _auto_find_audio(self):
        """Auto-detects speech.mp3 / voiceover.wav in audio and files or project dir."""
        candidates = [
            Path("audio and files/speech.mp3"),
            Path("audio and files/narration.mp3"),
            Path("audio and files/voiceover.wav"),
        ]
        for c in candidates:
            if c.exists():
                self.set_audio_path(str(c.resolve()))
                return

    def _on_import_downloads(self):
        """Unpacks ZIP files sequentially into images folder using temp folder renaming."""
        if not self.images_folder:
            self._on_browse_images_folder()
            return
        img_dir = Path(self.images_folder)
        from app.core.asset_manager import AssetManager
        
        # If no zips in images folder, copy any from Downloads
        if not list(img_dir.glob("*.zip")):
            dl = Path.home() / "Downloads"
            if dl.exists():
                for z in dl.glob("*.zip"):
                    try:
                        import shutil
                        shutil.copy2(z, img_dir / z.name)
                    except Exception:
                        pass

        unpacked = AssetManager.extract_and_sequentially_rename_zips(img_dir)
        self._scan_images()
        self._auto_sync_pipeline()
        QMessageBox.information(self, "Unpack Completed", f"Scanned and extracted {unpacked} image(s) sequentially. Total images: {len(self.image_files)}")
