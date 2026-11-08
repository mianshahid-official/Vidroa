"""
Master Application Window for PromptBeast Production Studio.
Unified 4-Step Pipeline:
1. 🎙️ Story Narration + Local Neural TTS Voiceover (Kokoro & Piper)
2. 🎨 AI Storyboard + 3-Pane Bulk Prompts Studio
3. 🖼️ Image Assets Ingestion + Scene Auto-Binding
4. 🎬 Subtitle Styling, Ken Burns Motion + Native FFmpeg Video Render
"""
import os
import json
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QRadioButton,
    QButtonGroup,
    QGroupBox,
    QFileDialog,
    QMessageBox,
    QScrollArea,
    QListWidget,
    QListWidgetItem,
    QFrame,
    QStatusBar,
    QPlainTextEdit,
    QTabWidget,
    QApplication,
    QListView,
)

from app.ui.widgets.custom_combo import PBComboBox
from app.config.constants import (
    APP_NAME,
    APP_DISPLAY_NAME,
    APP_VERSION,
    DEFAULT_MIN_DURATION,
    DEFAULT_PREFERRED_DURATION,
    DEFAULT_MAX_DURATION,
)
from app.config.settings import SettingsManager
from app.models.project import StoryProject, ProjectConfig, ProjectState, ImageCountMode, TimingMode
from app.models.scene import VisualScene
from app.models.timeline import NarrationData
from app.models.job import JobStage, JobStatus, ProgressInfo
from app.presets.loader import PresetManager
from app.core.story_loader import StoryLoader
from app.core.timestamp_parser import TimestampParser
from app.core.timeline_engine import TimelineEngine
from app.core.validation import TimelineValidator
from app.core.project_manager import ProjectManager
from app.core.export import StoryboardExporter
from app.core.video_renderer import VideoRenderer
from app.ai.api_client import CloudAPIClient, ConnectionCheckWorker
from app.ai.job_worker import CloudJobWorker, SceneRegenerateWorker
from app.ai.schemas import JobCreateRequest, SceneRegenerateRequest

from app.ui.theme import DARK_THEME_QSS
from app.ui.widgets.scene_editor import SceneEditorWidget
from app.ui.widgets.progress_panel import ProgressPanelWidget
from app.ui.widgets.status_banner import StatusBannerWidget
from app.ui.widgets.audio_transcription_panel import AudioTranscriptionPanel
from app.ui.widgets.image_asset_panel import ImageAssetPanel
from app.ui.widgets.render_panel import RenderPanel
from app.ui.dialogs.settings_dialog import SettingsDialog
from app.ui.dialogs.preset_editor_dialog import PresetEditorDialog
from app.ui.dialogs.export_dialog import ExportDialog
from app.ui.dialogs.recovery_dialog import RecoveryDialog
from app.ui.dialogs.project_history_dialog import ProjectHistoryDialog
from app.ui.dialogs.style_preview_dialog import StylePreviewDialog


class MainWindow(QMainWindow):
    """Main application window for PromptBeast Production Studio."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_DISPLAY_NAME} - Complete AI Video Production Studio")
        self.setMinimumSize(1024, 600)
        self.resize(1440, 840)

        # Initialize presets & settings
        PresetManager.initialize()
        self.settings = SettingsManager.load_settings()

        # Active Project
        self.project = StoryProject(
            name="Untitled_Project",
            config=ProjectConfig(),
            state=ProjectState()
        )

        # Workers
        self.active_job_worker: Optional[CloudJobWorker] = None
        self.active_regen_worker: Optional[SceneRegenerateWorker] = None
        self._cloud_worker: Optional[ConnectionCheckWorker] = None

        # Build UI
        self._setup_menus()
        self._setup_top_cloud_bar()
        self._setup_main_tabs()
        self._setup_status_bar()

        # Populate presets
        self._populate_subject_combo()
        self._populate_style_combo()

        # Apply dark theme
        self.setStyleSheet(DARK_THEME_QSS)

        # Initial check for connection in background
        QTimer.singleShot(400, self._check_cloud_connection)

        # Check for crash recovery / unfinished projects
        QTimer.singleShot(800, self._check_project_recovery)

    # =========================================================================
    # MENUS & TOP CLOUD BAR
    # =========================================================================

    def _setup_menus(self):
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("&File")

        new_act = QAction("&New Project", self)
        new_act.setShortcut(QKeySequence.StandardKey.New)
        new_act.triggered.connect(self._on_new_project)
        file_menu.addAction(new_act)

        open_act = QAction("&Open Project...", self)
        open_act.setShortcut(QKeySequence.StandardKey.Open)
        open_act.triggered.connect(self._on_open_project)
        file_menu.addAction(open_act)

        history_act = QAction("📁 &Projects History & Workspace...", self)
        history_act.setShortcut(QKeySequence("Ctrl+H"))
        history_act.triggered.connect(self._on_open_project_history)
        file_menu.addAction(history_act)

        save_act = QAction("&Save Project", self)
        save_act.setShortcut(QKeySequence.StandardKey.Save)
        save_act.triggered.connect(self._on_save_project)
        file_menu.addAction(save_act)

        save_as_act = QAction("Save Project &As...", self)
        save_as_act.triggered.connect(self._on_save_project_as)
        file_menu.addAction(save_as_act)

        file_menu.addSeparator()

        export_act = QAction("&Export Prompts and JSON...", self)
        export_act.setShortcut(QKeySequence("Ctrl+E"))
        export_act.triggered.connect(self._on_export_dialog)
        file_menu.addAction(export_act)

        file_menu.addSeparator()

        exit_act = QAction("E&xit", self)
        exit_act.setShortcut(QKeySequence.StandardKey.Quit)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        # Edit Menu
        edit_menu = menubar.addMenu("&Edit")
        split_act = QAction("&Split Selected Scene", self)
        split_act.setShortcut(QKeySequence("Ctrl+K"))
        split_act.triggered.connect(lambda: self.scene_editor._on_split_clicked())
        edit_menu.addAction(split_act)

        merge_act = QAction("&Merge With Next", self)
        merge_act.setShortcut(QKeySequence("Ctrl+M"))
        merge_act.triggered.connect(lambda: self.scene_editor._on_merge_clicked())
        edit_menu.addAction(merge_act)

        regen_act = QAction("&Regenerate Scene Prompt", self)
        regen_act.setShortcut(QKeySequence("Ctrl+R"))
        regen_act.triggered.connect(lambda: self.scene_editor._on_regenerate_clicked())
        edit_menu.addAction(regen_act)

        # Presets Menu
        presets_menu = menubar.addMenu("&Presets")
        preset_mgr_act = QAction("&Preset and Visual Style Manager...", self)
        preset_mgr_act.triggered.connect(self._on_open_preset_editor)
        presets_menu.addAction(preset_mgr_act)

        # Cloud Menu
        cloud_menu = menubar.addMenu("&AI Engine")
        test_conn_act = QAction("&Test Groq AI Connection", self)
        test_conn_act.triggered.connect(self._check_cloud_connection)
        cloud_menu.addAction(test_conn_act)

        settings_act = QAction("&Settings...", self)
        settings_act.setShortcut(QKeySequence.StandardKey.Preferences)
        settings_act.triggered.connect(self._on_open_settings)
        cloud_menu.addAction(settings_act)

    def _setup_top_cloud_bar(self):
        """Top banner showing the active Modal.run link and quick status."""
        self.top_bar_widget = QFrame()
        self.top_bar_widget.setStyleSheet("background-color: #0b1120; border-bottom: 1px solid #1e293b; padding: 4px 10px;")
        tb_layout = QHBoxLayout(self.top_bar_widget)
        tb_layout.setContentsMargins(6, 2, 6, 2)
        tb_layout.setSpacing(10)

        app_title = QLabel("<b>PromptBeast Studio</b>")
        app_title.setStyleSheet("color: #38bdf8; font-size: 13px;")
        tb_layout.addWidget(app_title)

        tb_layout.addSpacing(12)

        # Modal URL display
        self.modal_url_lbl = QLabel("⚡ Engine: Groq Multi-Key AI & Whisper (11 Keys Active)")
        self.modal_url_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: bold;")
        self.modal_url_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        tb_layout.addWidget(self.modal_url_lbl)

        tb_layout.addStretch()

        self.cloud_status_lbl = QLabel("⏳ Checking Groq...")
        self.cloud_status_lbl.setStyleSheet("color: #fbbf24; font-size: 11px; font-weight: bold;")
        tb_layout.addWidget(self.cloud_status_lbl)

        history_top_btn = QPushButton("📁 Projects & History")
        history_top_btn.setFixedHeight(22)
        history_top_btn.setStyleSheet("background-color: #1e3a8a; color: #93c5fd; font-size: 10px; font-weight: bold; border-radius: 4px; padding: 0 8px; border: 1px solid #2563eb;")
        history_top_btn.clicked.connect(self._on_open_project_history)
        tb_layout.addWidget(history_top_btn)

        quick_settings_btn = QPushButton("⚙️ AI Settings")
        quick_settings_btn.setFixedHeight(22)
        quick_settings_btn.setStyleSheet("background-color: #1e293b; color: #cbd5e1; font-size: 10px; border-radius: 4px; padding: 0 8px;")
        quick_settings_btn.clicked.connect(self._on_open_settings)
        tb_layout.addWidget(quick_settings_btn)

    # =========================================================================
    # MAIN WORKFLOW TABS
    # =========================================================================

    def _setup_main_tabs(self):
        central_container = QWidget()
        cc_layout = QVBoxLayout(central_container)
        cc_layout.setContentsMargins(0, 0, 0, 0)
        cc_layout.setSpacing(0)

        cc_layout.addWidget(self.top_bar_widget)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #1e293b;
                background-color: #0b0f19;
                border-radius: 0;
            }
            QTabBar::tab {
                background: #0f172a;
                color: #94a3b8;
                border: 1px solid #1e293b;
                border-bottom: none;
                padding: 8px 20px;
                font-weight: 600;
                font-size: 12px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 3px;
            }
            QTabBar::tab:selected {
                background: #1e293b;
                color: #38bdf8;
                border-bottom: 2px solid #38bdf8;
            }
            QTabBar::tab:hover:!selected {
                background: #1e293b;
                color: #f1f5f9;
            }
        """)

        # Tab 1: Story + Voiceover
        self.tab1_story_tts = self._create_tab1_story_tts()
        self.tabs.addTab(self.tab1_story_tts, "🎙️ 1. Story & Narration Audio")

        # Tab 2: Prompts + Storyboard (3-Pane Studio)
        self.tab2_prompts = self._create_tab2_prompts()
        self.tabs.addTab(self.tab2_prompts, "🎨 2. Prompts + Storyboard")

        # Tab 3: Images + Assets
        self.tab3_images = ImageAssetPanel()
        self.tab3_images.images_updated.connect(self._on_images_updated)
        self.tabs.addTab(self.tab3_images, "🖼️ 3. Images + Assets")

        # Tab 4: Subtitles + Video Render
        self.tab4_render = RenderPanel()
        self.tab4_render.render_completed.connect(self._on_render_completed)
        self.tabs.addTab(self.tab4_render, "🎬 4. Subtitles + Video Render")

        cc_layout.addWidget(self.tabs)
        self.setCentralWidget(central_container)

    # -------------------------------------------------------------------------
    # TAB 1: STORY + VOICEOVER
    # -------------------------------------------------------------------------

    def _create_tab1_story_tts(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Story Script Editor
        left_box = QGroupBox("Story Narration Script")
        left_layout = QVBoxLayout(left_box)
        left_layout.setSpacing(8)
        left_layout.setContentsMargins(10, 12, 10, 10)

        # Project Name Row
        pn_box = QHBoxLayout()
        pn_lbl = QLabel("Project Name:")
        pn_lbl.setFixedWidth(85)
        self.proj_name_input = QLineEdit("Untitled_Project")
        self.proj_name_input.textChanged.connect(self._on_project_name_changed)
        pn_box.addWidget(pn_lbl)
        pn_box.addWidget(self.proj_name_input)
        left_layout.addLayout(pn_box)

        # Story Load File Toolbar
        file_row = QHBoxLayout()
        self.browse_story_btn = QPushButton("📄 Load Story File (.txt, .md)")
        self.browse_story_btn.setFixedHeight(28)
        self.browse_story_btn.clicked.connect(self._on_browse_story)
        file_row.addWidget(self.browse_story_btn)

        self.history_proj_btn = QPushButton("📁 Projects & History...")
        self.history_proj_btn.setFixedHeight(28)
        self.history_proj_btn.setStyleSheet("background-color: #1e3a8a; border: 1px solid #3b82f6; color: #ffffff; font-weight: 600; padding: 0 12px; border-radius: 4px;")
        self.history_proj_btn.clicked.connect(self._on_open_project_history)
        file_row.addWidget(self.history_proj_btn)

        file_row.addStretch()
        self.story_stats_lbl = QLabel("0 words | 0 characters")
        self.story_stats_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        file_row.addWidget(self.story_stats_lbl)
        left_layout.addLayout(file_row)

        # Story Text Editor
        self.story_text_edit = QPlainTextEdit()
        self.story_text_edit.setPlaceholderText("Type or paste your story narration script here, or click 'Load Story File' above...")
        self.story_text_edit.setStyleSheet("font-size: 13px; line-height: 1.5; font-family: 'Segoe UI', sans-serif;")
        self.story_text_edit.textChanged.connect(self._on_story_text_edited)
        left_layout.addWidget(self.story_text_edit)

        # Timestamps import row
        ts_box = QHBoxLayout()
        self.ts_path_lbl = QLabel("Word Timestamps: Auto-generated on Voiceover")
        self.ts_path_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        ts_box.addWidget(self.ts_path_lbl)
        ts_box.addStretch()
        self.browse_ts_btn = QPushButton("Import JSON...")
        self.browse_ts_btn.setFixedHeight(22)
        self.browse_ts_btn.setStyleSheet("font-size: 10px;")
        self.browse_ts_btn.clicked.connect(self._on_browse_timestamps)
        ts_box.addWidget(self.browse_ts_btn)
        left_layout.addLayout(ts_box)

        splitter.addWidget(left_box)

        # Right: Audio Narration & Whisper Transcription Panel
        self.audio_panel = AudioTranscriptionPanel()
        self.audio_panel.story_text_provider = lambda: self.story_text_edit.toPlainText().strip()
        self.audio_panel.audio_ready.connect(self._on_audio_ready)
        splitter.addWidget(self.audio_panel)

        splitter.setSizes([600, 600])
        layout.addWidget(splitter)
        return widget

    # -------------------------------------------------------------------------
    # TAB 2: PROMPTS + STORYBOARD (3-PANE STUDIO)
    # -------------------------------------------------------------------------

    def _create_tab2_prompts(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 3-Pane Splitter: Left = Config & Generate, Center = Prompts List, Right = Scene Editor
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # =====================================================================
        # PANE 1: Style Presets & Generation Rules (Left)
        # =====================================================================
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setMinimumWidth(300)
        left_scroll.setMaximumWidth(360)

        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(4, 4, 4, 4)
        left_layout.setSpacing(8)

        # Subject Selection
        subj_group = QGroupBox("Subject / Domain")
        subj_layout = QVBoxLayout(subj_group)
        subj_layout.setContentsMargins(8, 10, 8, 8)
        self.subject_combo = PBComboBox()
        self.subject_combo.currentIndexChanged.connect(self._on_subject_changed)
        subj_layout.addWidget(self.subject_combo)

        self.custom_subject_edit = QPlainTextEdit()
        self.custom_subject_edit.setPlaceholderText("Enter custom subject instructions...")
        self.custom_subject_edit.setMaximumHeight(40)
        self.custom_subject_edit.setVisible(False)
        subj_layout.addWidget(self.custom_subject_edit)
        left_layout.addWidget(subj_group)

        # Visual Style Preset
        style_group = QGroupBox("Visual Style Preset")
        style_layout = QVBoxLayout(style_group)
        style_layout.setContentsMargins(8, 10, 8, 8)
        
        style_row = QHBoxLayout()
        self.style_combo = PBComboBox()
        self.style_combo.currentIndexChanged.connect(self._on_style_changed)
        style_row.addWidget(self.style_combo, 1)

        self.preview_style_btn = QPushButton("👁️ Preview Style")
        self.preview_style_btn.setFixedHeight(28)
        self.preview_style_btn.setStyleSheet("""
            QPushButton {
                background-color: #0f172a;
                color: #38bdf8;
                font-weight: 700;
                font-size: 11px;
                border: 1px solid #0284c7;
                border-radius: 4px;
                padding: 0 10px;
            }
            QPushButton:hover {
                background-color: #0284c7;
                color: #ffffff;
            }
        """)
        self.preview_style_btn.clicked.connect(self._on_open_style_preview)
        style_row.addWidget(self.preview_style_btn)
        style_layout.addLayout(style_row)

        # Style Preview Card
        self.style_preview_card = QFrame()
        self.style_preview_card.setStyleSheet("background-color: #0b0f19; border: 1px solid #1e293b; border-radius: 6px; padding: 4px;")
        sp_layout = QVBoxLayout(self.style_preview_card)
        sp_layout.setContentsMargins(4, 4, 4, 4)
        sp_layout.setSpacing(2)
        self.style_preview_name = QLabel("Century-Old Photograph")
        self.style_preview_name.setStyleSheet("font-weight: 700; color: #38bdf8; font-size: 11px;")
        sp_layout.addWidget(self.style_preview_name)
        self.style_preview_desc = QLabel("Archival photographic appearance with aged physical emulsion.")
        self.style_preview_desc.setStyleSheet("color: #94a3b8; font-size: 10px;")
        self.style_preview_desc.setWordWrap(True)
        sp_layout.addWidget(self.style_preview_desc)
        style_layout.addWidget(self.style_preview_card)

        self.custom_style_edit = QPlainTextEdit()
        self.custom_style_edit.setPlaceholderText("Enter custom style instructions...")
        self.custom_style_edit.setMaximumHeight(40)
        self.custom_style_edit.setVisible(False)
        style_layout.addWidget(self.custom_style_edit)
        left_layout.addWidget(style_group)

        # Timing & Image Count
        timing_group = QGroupBox("Timing & Image Count Rules")
        tg_layout = QVBoxLayout(timing_group)
        tg_layout.setContentsMargins(8, 10, 8, 8)
        tg_layout.setSpacing(6)

        count_mode_layout = QHBoxLayout()
        self.count_auto_radio = QRadioButton("Auto")
        self.count_auto_radio.setChecked(True)
        self.count_exact_radio = QRadioButton("Exact:")
        self.count_group = QButtonGroup()
        self.count_group.addButton(self.count_auto_radio)
        self.count_group.addButton(self.count_exact_radio)
        self.count_auto_radio.toggled.connect(self._on_count_mode_toggled)

        self.target_count_spin = QSpinBox()
        self.target_count_spin.setRange(3, 300)
        self.target_count_spin.setValue(20)
        self.target_count_spin.setEnabled(False)

        count_mode_layout.addWidget(self.count_auto_radio)
        count_mode_layout.addWidget(self.count_exact_radio)
        count_mode_layout.addWidget(self.target_count_spin)
        tg_layout.addLayout(count_mode_layout)

        tg_layout.addWidget(QLabel("Timing Mode:"))
        self.timing_combo = PBComboBox()
        self.timing_combo.addItems(["AI Decides (Semantic Boundaries)", "Target Duration", "Fixed Duration Intervals"])
        tg_layout.addWidget(self.timing_combo)

        dur_row = QHBoxLayout()
        dur_row.addWidget(QLabel("Min:"))
        self.min_dur_spin = QDoubleSpinBox()
        self.min_dur_spin.setRange(0.5, 30.0)
        self.min_dur_spin.setValue(3.0)
        dur_row.addWidget(self.min_dur_spin)

        dur_row.addWidget(QLabel("Pref:"))
        self.pref_dur_spin = QDoubleSpinBox()
        self.pref_dur_spin.setRange(1.0, 60.0)
        self.pref_dur_spin.setValue(5.0)
        dur_row.addWidget(self.pref_dur_spin)

        dur_row.addWidget(QLabel("Max:"))
        self.max_dur_spin = QDoubleSpinBox()
        self.max_dur_spin.setRange(2.0, 120.0)
        self.max_dur_spin.setValue(8.0)
        dur_row.addWidget(self.max_dur_spin)
        tg_layout.addLayout(dur_row)

        left_layout.addWidget(timing_group)

        # Start Generation Button
        self.start_gen_btn = QPushButton("🚀 GENERATE STORYBOARD + PROMPTS")
        self.start_gen_btn.setFixedHeight(42)
        self.start_gen_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #6366f1);
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 6px;
                border: 1px solid #818cf8;
            }
            QPushButton:hover {
                background: #4338ca;
            }
            QPushButton:disabled {
                background: #334155;
                color: #64748b;
                border-color: #475569;
            }
        """)
        self.start_gen_btn.clicked.connect(self._on_start_generation)
        left_layout.addWidget(self.start_gen_btn)

        # Progress Panel
        self.progress_panel = ProgressPanelWidget()
        self.progress_panel.cancel_requested.connect(self._on_cancel_generation)
        left_layout.addWidget(self.progress_panel)

        left_layout.addStretch()
        left_scroll.setWidget(left_container)
        splitter.addWidget(left_scroll)

        # =====================================================================
        # PANE 2: Full-Height Prompts List (Center)
        # =====================================================================
        center_container = QWidget()
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(2, 2, 2, 2)
        center_layout.setSpacing(6)

        # Top Bar
        top_bar = QFrame()
        top_bar.setStyleSheet("background-color: #0f172a; border: 1px solid #1e293b; border-radius: 6px; padding: 4px 6px;")
        tb_layout = QHBoxLayout(top_bar)
        tb_layout.setContentsMargins(4, 2, 4, 2)
        tb_layout.setSpacing(6)

        self.scene_search_input = QLineEdit()
        self.scene_search_input.setPlaceholderText("Filter prompts...")
        self.scene_search_input.textChanged.connect(self._on_scene_search_changed)
        tb_layout.addWidget(self.scene_search_input)

        self.scene_count_badge = QLabel("0 Prompts")
        self.scene_count_badge.setStyleSheet("background-color: #1e293b; color: #38bdf8; border-radius: 4px; padding: 2px 6px; font-weight: 700; font-size: 11px;")
        tb_layout.addWidget(self.scene_count_badge)

        self.add_scene_btn = QPushButton("➕ Add Scene")
        self.add_scene_btn.setFixedHeight(26)
        self.add_scene_btn.setStyleSheet("background-color: #065f46; color: white; font-weight: bold; border-radius: 4px; padding: 0 8px;")
        self.add_scene_btn.clicked.connect(self._on_add_manual_scene)
        tb_layout.addWidget(self.add_scene_btn)

        self.quick_copy_btn = QPushButton("📋 Copy All")
        self.quick_copy_btn.setFixedHeight(26)
        self.quick_copy_btn.clicked.connect(self._on_quick_copy_all)
        tb_layout.addWidget(self.quick_copy_btn)

        self.quick_export_btn = QPushButton("📁 Export")
        self.quick_export_btn.setFixedHeight(26)
        self.quick_export_btn.setStyleSheet("background-color: #312e81; color: white; font-weight: bold; border-radius: 4px; padding: 0 8px;")
        self.quick_export_btn.clicked.connect(self._on_export_dialog)
        tb_layout.addWidget(self.quick_export_btn)

        center_layout.addWidget(top_bar)

        # Prompts List (Full height)
        self.scenes_list = QListWidget()
        self.scenes_list.setStyleSheet("""
            QListWidget {
                background-color: #0b0f19;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item {
                background-color: #111827;
                border: 1px solid #1e293b;
                border-radius: 6px;
                margin-bottom: 6px;
                padding: 8px;
                color: #e2e8f0;
            }
            QListWidget::item:selected {
                background-color: #1e293b;
                border: 1px solid #38bdf8;
                color: #38bdf8;
            }
            QListWidget::item:hover:!selected {
                background-color: #1a2234;
            }
        """)
        self.scenes_list.currentItemChanged.connect(self._on_scene_list_item_selected)
        self.scenes_list.itemClicked.connect(self._on_scene_list_item_selected)
        center_layout.addWidget(self.scenes_list)

        splitter.addWidget(center_container)

        # =====================================================================
        # PANE 3: Selected Scene Inspector & Editor (Right)
        # =====================================================================
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(2, 2, 2, 2)
        right_layout.setSpacing(6)

        self.scene_editor = SceneEditorWidget()
        self.scene_editor.scene_updated.connect(self._on_scene_edited)
        self.scene_editor.regenerate_requested.connect(self._on_regenerate_single_scene)
        self.scene_editor.split_requested.connect(self._on_split_scene)
        self.scene_editor.merge_requested.connect(self._on_merge_scene)
        self.scene_editor.delete_requested.connect(self._on_delete_scene)
        self.scene_editor.create_scene_requested.connect(self._on_add_manual_scene)
        right_layout.addWidget(self.scene_editor)

        splitter.addWidget(right_container)

        # Proportions: Left=320px, Center=460px, Right=460px
        splitter.setSizes([320, 460, 460])
        layout.addWidget(splitter)
        return widget

    def _setup_status_bar(self):
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        self.status_banner = StatusBannerWidget()
        status_bar.addPermanentWidget(self.status_banner)

    # =========================================================================
    # EVENT HANDLERS & SYNC
    # =========================================================================

    def _on_story_text_edited(self):
        text = self.story_text_edit.toPlainText()
        self.project.state.story_raw_text = text
        if hasattr(self, "audio_panel"):
            self.audio_panel.set_story_text(text)
        w_count = len(text.split())
        c_count = len(text)
        self.story_stats_lbl.setText(f"{w_count} words | {c_count} chars")

    def _on_audio_ready(self, audio_path: str, narration: NarrationData, story_text: str = ""):
        if audio_path:
            self.project.state.audio_file_path = audio_path
        if narration:
            self.project.state.narration = narration
        if story_text and not self.story_text_edit.toPlainText().strip():
            self.story_text_edit.setPlainText(story_text)
        self.project.state.story_raw_text = self.story_text_edit.toPlainText().strip()

        if narration:
            self.ts_path_lbl.setText(f"✅ Narration Audio ({narration.duration_seconds:.1f}s, {len(narration.words)} words)")
            self.ts_path_lbl.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: bold;")

        if not self.project.project_dir:
            proj_name = self.proj_name_input.text().strip() or "Untitled_Project"
            proj = ProjectManager.create_project(proj_name, self.settings.workspace_directory, add_unique_id=True)
            self.project.project_dir = proj.project_dir
            self.project.name = proj.name
            self.proj_name_input.setText(proj.name)

        try:
            self._sync_project_config()
            ProjectManager.save_project(self.project)
            SettingsManager.add_recent_project(self.project.project_dir)
        except Exception as e:
            print(f"Notice saving project on audio ready: {e}")

        self.tab4_render.load_project_data(
            scenes=self.project.state.scenes,
            audio_path=self.project.state.audio_file_path,
            narration=self.project.state.narration
        )
        self.tabs.setCurrentIndex(1)
        self.statusBar().showMessage(f"Narration loaded ({narration.duration_seconds:.1f}s). Ready for storyboard generation.", 5000)

    def _on_voiceover_generated(self, audio_path: str, narration: NarrationData):
        self.project.state.story_raw_text = self.story_text_edit.toPlainText().strip()
        self.project.state.audio_file_path = audio_path
        self.project.state.narration = narration
        self.ts_path_lbl.setText(f"✅ Voiceover Narration ({narration.duration_seconds:.1f}s, {len(narration.words)} words)")
        self.ts_path_lbl.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: bold;")

        # Save project to disk immediately
        if self.project.project_dir:
            try:
                self._sync_project_config()
                ProjectManager.save_project(self.project)
            except Exception as e:
                print(f"Notice auto-saving project: {e}")

        # Update render panel
        self.tab4_render.load_project_data(
            scenes=self.project.state.scenes,
            audio_path=audio_path,
            narration=narration
        )

        # Automatically advance to Tab 2: Prompts + Storyboard
        self.tabs.setCurrentIndex(1)
        self.statusBar().showMessage(f"Voiceover generated & saved to {self.project.name}. Ready for prompts generation.", 5000)

    def _on_images_updated(self, updated_scenes: List[VisualScene]):
        self.project.state.scenes = updated_scenes
        self.tab4_render.load_project_data(
            scenes=updated_scenes,
            audio_path=self.project.state.audio_file_path,
            narration=self.project.state.narration
        )

    def _on_render_completed(self, output_video_path: str):
        self.project.state.final_video_path = output_video_path

    # =========================================================================
    # PRESETS & SETTINGS
    # =========================================================================

    def _populate_subject_combo(self):
        self.subject_combo.clear()
        subjects = PresetManager.get_all_subjects()
        for s in subjects:
            self.subject_combo.addItem(s.name, s.id)
        idx = self.subject_combo.findData(self.settings.default_subject_id)
        if idx >= 0:
            self.subject_combo.setCurrentIndex(idx)

    def _populate_style_combo(self):
        self.style_combo.clear()
        styles = PresetManager.get_all_styles()

        # Curated top viral & user-requested styles
        priority_styles = [
            ("2d_stick_figure", "✏️ 2D Stick Figure Animation"),
            ("historical_painting", "🏛️ Old History Painting"),
            ("2d_cartoon", "🎨 2D Vector & Cartoon (Kurzgesagt)"),
            ("3d_realistic", "✨ 3D CGI & Stylized Render"),
            ("photorealistic", "📸 Photorealistic DSLR (8K)"),
            ("midjourney_hyper_realism", "🔥 Midjourney Viral Hyper-Realism (UE5)"),
            ("studio_ghibli_anime", "🌸 Studio Ghibli Anime (Lofi Viral)"),
            ("isometric_3d", "📐 Isometric 3D Explainer (Vox)"),
            ("dark_fantasy_gothic", "🗡️ Dark Fantasy Gothic (Elden)"),
            ("retro_pop_art", "💥 Retro Comic Book & Pop Art"),
            ("clay_stop_motion", "🧱 Claymation & Stop Motion"),
            ("century_old_photograph", "📜 Century-Old Photograph (Archival)"),
            ("watercolor", "📖 Watercolor Storybook"),
            ("cinematic_realism", "🎬 Cinematic Documentary Realism"),
        ]

        added_ids = set()
        for s_id, custom_label in priority_styles:
            preset = PresetManager.get_style_by_id(s_id)
            if preset:
                self.style_combo.addItem(custom_label, preset.id)
                added_ids.add(preset.id)

        # Add remaining presets
        for s in sorted(styles, key=lambda x: x.name):
            if s.id not in added_ids and s.id != "custom":
                self.style_combo.addItem(s.name, s.id)

        custom_p = PresetManager.get_style_by_id("custom")
        if custom_p:
            self.style_combo.addItem("⚙️ Custom Visual Style...", "custom")

        idx = self.style_combo.findData(self.settings.default_visual_style_id)
        if idx >= 0:
            self.style_combo.setCurrentIndex(idx)
        else:
            self.style_combo.setCurrentIndex(0)

    def _on_open_style_preview(self):
        current_id = self.style_combo.currentData() or "midjourney_hyper_realism"
        dlg = StylePreviewDialog(current_id, self)
        if dlg.exec():
            selected = dlg.selected_style_id
            if selected:
                idx = self.style_combo.findData(selected)
                if idx >= 0:
                    self.style_combo.setCurrentIndex(idx)

    def _on_subject_changed(self, index: int):
        subject_id = self.subject_combo.currentData()
        self.custom_subject_edit.setVisible(subject_id == "custom")
        self.project.config.subject_id = subject_id or "history"

    def _on_style_changed(self, index: int):
        style_id = self.style_combo.currentData()
        self.custom_style_edit.setVisible(style_id == "custom")
        self.project.config.visual_style_id = style_id or "century_old_photograph"

        preset = PresetManager.get_style_by_id(style_id)
        if preset:
            self.style_preview_name.setText(preset.name)
            self.style_preview_desc.setText(preset.description)

    def _on_count_mode_toggled(self, checked: bool):
        is_exact = self.count_exact_radio.isChecked()
        self.target_count_spin.setEnabled(is_exact)
        self.project.config.image_count_mode = ImageCountMode.EXACT if is_exact else ImageCountMode.AUTOMATIC

    # =========================================================================
    # PROJECT LIFECYCLE
    # =========================================================================

    def _on_project_name_changed(self, text: str):
        self.project.name = text.strip() or "Untitled_Project"

    def _on_new_project(self):
        self.project = StoryProject(
            name="Untitled_Project",
            config=ProjectConfig(),
            state=ProjectState()
        )
        self.proj_name_input.setText("Untitled_Project")
        self.story_text_edit.setPlainText("")
        self.story_stats_lbl.setText("0 words | 0 characters")
        self.ts_path_lbl.setText("Word Timestamps: Auto-generated on Voiceover")
        self._refresh_scenes_ui([])
        self.tab3_images.load_scenes([])
        self.tab4_render.load_project_data([])
        self.scene_editor.load_scene(None)
        QMessageBox.information(self, "New Project", "Created new blank project.")

    def _apply_project_to_ui(self, proj: StoryProject, auto_switch_tab: bool = True):
        """Applies a loaded StoryProject completely to all tabs and UI components."""
        self.project = proj
        self.proj_name_input.setText(proj.name)

        # 1. Populate Story & TTS in Tab 1
        raw_story = proj.state.story_raw_text or ""
        self.story_text_edit.setPlainText(raw_story)
        if hasattr(self, "audio_panel"):
            self.audio_panel.set_story_text(raw_story)
        words = len(raw_story.split()) if raw_story else 0
        chars = len(raw_story)
        self.story_stats_lbl.setText(f"{words} words | {chars} characters")

        # 2. Populate Voiceover Narration & Timestamps
        if proj.state.audio_file_path and Path(proj.state.audio_file_path).exists() and proj.state.narration:
            if hasattr(self, "audio_panel"):
                self.audio_panel.load_audio_narration(proj.state.audio_file_path, proj.state.narration)
            self.ts_path_lbl.setText(f"✅ Voiceover Narration ({proj.state.narration.duration_seconds:.1f}s, {len(proj.state.narration.words)} words)")
            self.ts_path_lbl.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: bold;")
        elif proj.state.narration:
            self.ts_path_lbl.setText(f"✅ Timestamps loaded ({proj.state.narration.duration_seconds:.1f}s, {len(proj.state.narration.words)} words)")
            self.ts_path_lbl.setStyleSheet("color: #4ade80; font-size: 11px;")
        else:
            self.ts_path_lbl.setText("Word Timestamps: Auto-generated on Voiceover")
            self.ts_path_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")

        # 3. Populate Preset & Config settings
        s_idx = self.subject_combo.findData(proj.config.subject_id)
        if s_idx >= 0:
            self.subject_combo.setCurrentIndex(s_idx)
        if proj.config.custom_subject:
            self.custom_subject_edit.setPlainText(proj.config.custom_subject)

        v_idx = self.style_combo.findData(proj.config.visual_style_id)
        if v_idx >= 0:
            self.style_combo.setCurrentIndex(v_idx)
        if proj.config.custom_style:
            self.custom_style_edit.setPlainText(proj.config.custom_style)

        if proj.config.image_count_mode == ImageCountMode.EXACT:
            self.count_exact_radio.setChecked(True)
            self.target_count_spin.setValue(proj.config.target_image_count)
        else:
            self.count_auto_radio.setChecked(True)

        if proj.config.timing_mode == TimingMode.TARGET:
            self.timing_combo.setCurrentIndex(1)
        elif proj.config.timing_mode == TimingMode.FIXED:
            self.timing_combo.setCurrentIndex(2)
        else:
            self.timing_combo.setCurrentIndex(0)

        self.min_dur_spin.setValue(proj.config.min_duration)
        self.pref_dur_spin.setValue(proj.config.preferred_duration)
        self.max_dur_spin.setValue(proj.config.max_duration)

        # 4. Populate Scenes in Tab 2, Tab 3, Tab 4
        self._refresh_scenes_ui(proj.state.scenes)
        self.tab3_images.load_scenes(proj.state.scenes, proj.state.images_folder_path)
        self.tab4_render.load_project_data(
            scenes=proj.state.scenes,
            audio_path=proj.state.audio_file_path,
            narration=proj.state.narration
        )

        # 5. Auto-switch to the most appropriate tab
        if auto_switch_tab:
            if proj.state.scenes and len(proj.state.scenes) > 0:
                self.tabs.setCurrentIndex(1)  # Tab 2: Storyboard
            elif proj.state.audio_file_path and proj.state.narration:
                self.tabs.setCurrentIndex(1)  # Tab 2: Ready for Storyboard generation
            else:
                self.tabs.setCurrentIndex(0)  # Tab 1: Story

        if proj.project_dir:
            SettingsManager.add_recent_project(proj.project_dir)

    def _on_open_project_history(self):
        """Opens the Project History & Workspace browser dialog."""
        dlg = ProjectHistoryDialog(self.settings.workspace_directory, self)
        if dlg.exec() and dlg.selected_project_dir:
            try:
                proj = ProjectManager.load_project(dlg.selected_project_dir)
                self._apply_project_to_ui(proj, auto_switch_tab=True)
                QMessageBox.information(
                    self,
                    "Project Loaded",
                    f"Loaded project '{proj.name}' successfully!\n"
                    f"• Story text: {len(proj.state.story_raw_text or '')} chars\n"
                    f"• Scenes: {len(proj.state.scenes)}\n"
                    f"• Voiceover: {'Ready' if proj.state.audio_file_path else 'Not generated yet'}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Open Failed", f"Could not load project: {str(e)}")

    def _on_open_project(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Open Project Directory", self.settings.workspace_directory)
        if not dir_path:
            return

        try:
            proj = ProjectManager.load_project(dir_path)
            self._apply_project_to_ui(proj, auto_switch_tab=True)
            QMessageBox.information(self, "Project Loaded", f"Loaded project '{proj.name}' ({len(proj.state.scenes)} scenes).")
        except Exception as e:
            QMessageBox.critical(self, "Open Failed", f"Could not load project: {str(e)}")

    def _on_audio_ready(self, audio_path: str, narration: NarrationData, story_text: str = ""):
        if audio_path:
            self.project.state.audio_file_path = audio_path
        if narration:
            self.project.state.narration = narration
        if story_text and not self.story_text_edit.toPlainText().strip():
            self.story_text_edit.setPlainText(story_text)
        self.project.state.story_raw_text = self.story_text_edit.toPlainText().strip()

        if narration:
            self.ts_path_lbl.setText(f"✅ Narration Audio ({narration.duration_seconds:.1f}s, {len(narration.words)} words)")
            self.ts_path_lbl.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: bold;")

        if not self.project.project_dir:
            proj_name = self.proj_name_input.text().strip() or "Untitled_Project"
            proj = ProjectManager.create_project(proj_name, self.settings.workspace_directory, add_unique_id=True)
            self.project.project_dir = proj.project_dir
            self.project.name = proj.name
            self.proj_name_input.setText(proj.name)

        try:
            self._sync_project_config()
            ProjectManager.save_project(self.project)
            SettingsManager.add_recent_project(self.project.project_dir)
        except Exception as e:
            print(f"Notice saving project on audio ready: {e}")

        self.tab4_render.load_project_data(
            scenes=self.project.state.scenes,
            audio_path=self.project.state.audio_file_path,
            narration=self.project.state.narration
        )
        self.tabs.setCurrentIndex(1)
        self.statusBar().showMessage(f"Narration loaded ({narration.duration_seconds:.1f}s). Ready for storyboard generation.", 5000)

    def _on_voiceover_generated(self, audio_path: str, narration: NarrationData):
        """Called immediately when voiceover synthesis finishes."""
        self.project.state.audio_file_path = audio_path
        self.project.state.narration = narration
        self.project.state.story_raw_text = self.story_text_edit.toPlainText().strip()

        # Update labels
        self.ts_path_lbl.setText(f"✅ Voiceover Narration ({narration.duration_seconds:.1f}s, {len(narration.words)} words)")
        self.ts_path_lbl.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: bold;")

        # Automatically create and save project directory
        if not self.project.project_dir:
            proj_name = self.proj_name_input.text().strip() or "Untitled_Project"
            proj = ProjectManager.create_project(proj_name, self.settings.workspace_directory, add_unique_id=True)
            self.project.project_dir = proj.project_dir
            self.project.name = proj.name
            self.proj_name_input.setText(proj.name)

        try:
            self._sync_project_config()
            ProjectManager.save_project(self.project)
            SettingsManager.add_recent_project(self.project.project_dir)
        except Exception as e:
            print(f"Notice saving project on voiceover generation: {e}")

        # Auto-advance directly to Tab 2 for Storyboard generation
        self.tabs.setCurrentIndex(1)

    def _on_save_project(self):
        if not self.project.project_dir:
            self._on_save_project_as()
            return

        try:
            self._sync_project_config()
            ProjectManager.save_project(self.project)
            QMessageBox.information(self, "Saved", f"Project '{self.project.name}' saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", f"Could not save project: {str(e)}")

    def _on_save_project_as(self):
        parent_dir = QFileDialog.getExistingDirectory(self, "Select Parent Directory for Project", self.settings.workspace_directory)
        if not parent_dir:
            return

        name = self.proj_name_input.text().strip() or "Untitled_Project"
        proj_dir = Path(parent_dir) / name
        self.project.name = name
        self.project.project_dir = str(proj_dir.resolve())

        self._on_save_project()

    def _sync_project_config(self):
        self.project.state.story_raw_text = self.story_text_edit.toPlainText().strip()
        self.project.config.subject_id = self.subject_combo.currentData() or "history"
        self.project.config.custom_subject = self.custom_subject_edit.toPlainText().strip() or None
        self.project.config.visual_style_id = self.style_combo.currentData() or "century_old_photograph"
        self.project.config.custom_style = self.custom_style_edit.toPlainText().strip() or None
        self.project.config.image_count_mode = ImageCountMode.EXACT if self.count_exact_radio.isChecked() else ImageCountMode.AUTOMATIC
        self.project.config.target_image_count = self.target_count_spin.value()

        t_idx = self.timing_combo.currentIndex()
        if t_idx == 1:
            self.project.config.timing_mode = TimingMode.TARGET
        elif t_idx == 2:
            self.project.config.timing_mode = TimingMode.FIXED
        else:
            self.project.config.timing_mode = TimingMode.AI_DECIDES

        self.project.config.min_duration = self.min_dur_spin.value()
        self.project.config.preferred_duration = self.pref_dur_spin.value()
        self.project.config.max_duration = self.max_dur_spin.value()

    # =========================================================================
    # FILE LOADERS
    # =========================================================================

    def _on_browse_story(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Story Narration File",
            "",
            "Text Files (*.txt *.md *.text *.markdown);;All Files (*.*)"
        )
        if not file_path:
            return

        try:
            raw_text, meta = StoryLoader.load_from_file(file_path)
            self.project.state.story_raw_text = raw_text
            self.project.state.story_file_path = file_path
            self.story_text_edit.setPlainText(raw_text)
            self.story_stats_lbl.setText(f"{meta['word_count']} words | {meta['character_count']} chars (Est: {meta['estimated_spoken_duration_seconds']}s)")
        except Exception as e:
            QMessageBox.critical(self, "Story Load Error", str(e))

    def _on_browse_timestamps(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Word-Level Timestamp JSON File",
            "",
            "JSON Files (*.json);;All Files (*.*)"
        )
        if not file_path:
            return

        try:
            narration_data = TimestampParser.load_from_json(file_path)
            self.project.state.narration = narration_data
            self.project.state.timestamps_file_path = file_path
            self.ts_path_lbl.setText(f"✅ Imported: {Path(file_path).name} ({narration_data.duration_seconds:.1f}s)")
            self.ts_path_lbl.setStyleSheet("color: #4ade80; font-size: 11px;")
        except Exception as e:
            QMessageBox.critical(self, "Timestamp Load Error", str(e))

    # =========================================================================
    # AI GENERATION PIPELINE
    # =========================================================================

    def _on_start_generation(self):
        story_text = self.story_text_edit.toPlainText().strip()
        if not story_text:
            QMessageBox.warning(self, "Missing Story", "Please enter or load a story script in Tab 1 first.")
            self.tabs.setCurrentIndex(0)
            return

        self._sync_project_config()

        if not self.project.state.narration:
            estimated = TimestampParser.estimate_from_text(story_text)
            self.project.state.narration = estimated

        req = JobCreateRequest(
            project_name=self.project.name,
            story_text=story_text,
            narration=self.project.state.narration,
            subject_id=self.project.config.subject_id,
            custom_subject=self.project.config.custom_subject,
            visual_style_id=self.project.config.visual_style_id,
            custom_style=self.project.config.custom_style,
            image_count_mode=self.project.config.image_count_mode,
            target_image_count=self.project.config.target_image_count,
            timing_mode=self.project.config.timing_mode,
            min_duration=self.project.config.min_duration,
            preferred_duration=self.project.config.preferred_duration,
            max_duration=self.project.config.max_duration,
            batch_size=self.settings.default_batch_size,
            model_name=self.settings.default_model
        )

        self.start_gen_btn.setEnabled(False)
        self.progress_panel.set_running_state(True)

        self.active_job_worker = CloudJobWorker(
            base_url=self.settings.modal_api_url,
            request=req,
            api_key=self.settings.api_key,
            auth_token=self.settings.auth_token
        )
        self.active_job_worker.progress_updated.connect(self._on_job_progress_updated)
        self.active_job_worker.scenes_streamed.connect(self._on_job_scenes_streamed)
        self.active_job_worker.analysis_ready.connect(self._on_job_analysis_ready)
        self.active_job_worker.job_completed.connect(self._on_job_completed)
        self.active_job_worker.job_failed.connect(self._on_job_failed)
        self.active_job_worker.job_cancelled.connect(self._on_job_cancelled)
        self.active_job_worker.start()

    def _on_job_progress_updated(self, progress: ProgressInfo):
        self.progress_panel.update_progress(progress)
        if self.active_job_worker and self.active_job_worker.job_id:
            ProjectManager.mark_job_in_progress(
                self.project,
                self.active_job_worker.job_id,
                progress.stage.value,
                progress.progress_percentage
            )

    def _on_job_scenes_streamed(self, scenes: List[VisualScene]):
        self.project.state.scenes = scenes
        self._refresh_scenes_ui(scenes)
        self.tab3_images.load_scenes(scenes)
        self.tab4_render.load_project_data(
            scenes=scenes,
            audio_path=self.project.state.audio_file_path,
            narration=self.project.state.narration
        )

    def _on_job_analysis_ready(self, analysis):
        self.project.state.analysis = analysis

    def _on_job_completed(self, resp):
        self.start_gen_btn.setEnabled(True)
        self.progress_panel.set_running_state(False)
        if resp.scenes:
            self.project.state.scenes = resp.scenes
            self._refresh_scenes_ui(resp.scenes, select_first=True)
            self.tab3_images.load_scenes(resp.scenes)
            self.tab4_render.load_project_data(
                scenes=resp.scenes,
                audio_path=self.project.state.audio_file_path,
                narration=self.project.state.narration
            )

        ProjectManager.clear_job_in_progress(self.project)
        QMessageBox.information(
            self,
            "Generation Complete",
            f"Successfully generated and validated {len(resp.scenes)} storyboard scenes!\n\nYou can now copy prompts, generate your images, and proceed to Tab 3."
        )

    def _on_job_failed(self, user_msg: str, tech_details: str):
        self.start_gen_btn.setEnabled(True)
        self.progress_panel.set_running_state(False)
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("Generation Error")
        msg_box.setText(user_msg)
        if tech_details:
            msg_box.setDetailedText(tech_details)
        msg_box.exec()

    def _on_cancel_generation(self):
        if self.active_job_worker:
            self.active_job_worker.cancel()
            self.progress_panel.mark_cancelled()

    def _on_job_cancelled(self):
        self.start_gen_btn.setEnabled(True)
        self.progress_panel.set_running_state(False)
        ProjectManager.clear_job_in_progress(self.project)
        QMessageBox.information(self, "Cancelled", "Cloud generation job was cancelled.")

    # =========================================================================
    # SCENE LIST & PROMPT INSPECTOR
    # =========================================================================

    def _refresh_scenes_ui(self, scenes: List[VisualScene], select_first: bool = False):
        self.scene_count_badge.setText(f"{len(scenes)} Prompts")
        self.scenes_list.blockSignals(True)
        self.scenes_list.clear()
        filter_text = self.scene_search_input.text().strip().lower()

        for sc in scenes:
            if filter_text and filter_text not in sc.narration_excerpt.lower() and filter_text not in sc.visual_subject.lower() and filter_text not in sc.prompt.lower():
                continue

            item = QListWidgetItem()
            edit_mark = " [EDITED]" if sc.is_manually_edited else ""
            prompt_preview = (sc.prompt[:75] + "...") if len(sc.prompt) > 75 else sc.prompt
            item.setText(
                f"Image #{sc.scene_id} [{sc.start:.1f}s - {sc.end:.1f}s | {sc.duration:.1f}s]{edit_mark}\n"
                f"  Subject: {sc.visual_subject}\n"
                f"  Prompt: {prompt_preview}"
            )
            item.setData(Qt.ItemDataRole.UserRole, sc.scene_id)
            self.scenes_list.addItem(item)

        self.scenes_list.blockSignals(False)

        if select_first and scenes:
            self.scenes_list.setCurrentRow(0)
            self.scene_editor.load_scene(scenes[0])

    def _on_scene_list_item_selected(self, current: Optional[QListWidgetItem]):
        if not current:
            return
        scene_id = current.data(Qt.ItemDataRole.UserRole)
        sc = next((s for s in self.project.state.scenes if s.scene_id == scene_id), None)
        if sc:
            self.scene_editor.load_scene(sc)

    def _on_scene_search_changed(self, text: str):
        self._refresh_scenes_ui(self.project.state.scenes)

    def _on_quick_copy_all(self):
        if not self.project.state.scenes:
            QMessageBox.warning(self, "No Prompts", "No generated prompts to copy.")
            return

        all_text = StoryboardExporter.export_to_text(self.project.state.scenes)
        QApplication.clipboard().setText(all_text)
        QMessageBox.information(self, "Copied", f"Copied {len(self.project.state.scenes)} image prompts to clipboard.")

    def _select_scene_by_id(self, scene_id: str):
        for i in range(self.scenes_list.count()):
            item = self.scenes_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == scene_id:
                self.scenes_list.setCurrentRow(i)
                break
        sc = next((s for s in self.project.state.scenes if s.scene_id == scene_id), None)
        if sc:
            self.scene_editor.load_scene(sc)

    def _on_scene_edited(self, updated_scene: VisualScene):
        idx = next((i for i, s in enumerate(self.project.state.scenes) if s.scene_id == updated_scene.scene_id), None)
        if idx is not None:
            self.project.state.scenes[idx] = updated_scene
            healed = TimelineEngine.heal_gaps_and_overlaps(self.project.state.scenes)
            self.project.state.scenes = healed
            self._refresh_scenes_ui(healed)
            self.tab3_images.load_scenes(healed)
            self.tab4_render.load_project_data(healed, self.project.state.audio_file_path, self.project.state.narration)
            self._select_scene_by_id(updated_scene.scene_id)

    def _on_regenerate_single_scene(self, scene_id: str):
        sc = next((s for s in self.project.state.scenes if s.scene_id == scene_id), None)
        if not sc:
            return

        req = SceneRegenerateRequest(
            scene=sc,
            story_summary=self.project.state.analysis.story_summary if self.project.state.analysis else "",
            subject_id=self.project.config.subject_id,
            custom_subject=self.project.config.custom_subject,
            visual_style_id=self.project.config.visual_style_id,
            custom_style=self.project.config.custom_style,
            continuity=self.project.state.analysis.continuity if self.project.state.analysis else None,
            model_name=self.settings.default_model
        )

        self.scene_editor.setEnabled(False)
        self.active_regen_worker = SceneRegenerateWorker(
            base_url=self.settings.modal_api_url,
            request=req,
            api_key=self.settings.api_key,
            auth_token=self.settings.auth_token
        )
        self.active_regen_worker.regenerate_completed.connect(self._on_single_scene_regenerated)
        self.active_regen_worker.regenerate_failed.connect(self._on_single_scene_regen_failed)
        self.active_regen_worker.start()

    def _on_single_scene_regenerated(self, resp):
        self.scene_editor.setEnabled(True)
        idx = next((i for i, s in enumerate(self.project.state.scenes) if s.scene_id == resp.scene_id), None)
        if idx is not None:
            sc = self.project.state.scenes[idx]
            sc.prompt = resp.prompt
            sc.visual_subject = resp.visual_subject
            sc.is_validated = True
            self.scene_editor.load_scene(sc)
            self._refresh_scenes_ui(self.project.state.scenes)
            QMessageBox.information(self, "Regeneration Complete", f"Scene #{resp.scene_id} regenerated successfully.")

    def _on_single_scene_regen_failed(self, msg: str, tech: str):
        self.scene_editor.setEnabled(True)
        QMessageBox.critical(self, "Regeneration Failed", f"{msg}\n\n{tech}")

    def _on_split_scene(self, scene_id: str, split_time: float):
        try:
            updated_list = TimelineEngine.split_scene(
                self.project.state.scenes,
                scene_id,
                split_time,
                self.project.state.narration
            )
            self.project.state.scenes = updated_list
            self._refresh_scenes_ui(updated_list, select_first=False)
            self.tab3_images.load_scenes(updated_list)
            self.tab4_render.load_project_data(updated_list, self.project.state.audio_file_path, self.project.state.narration)
            self._select_scene_by_id(scene_id)
            QMessageBox.information(self, "Scene Split", f"Scene #{scene_id} split into two scenes at {split_time:.2f}s.")
        except Exception as e:
            QMessageBox.critical(self, "Split Failed", str(e))

    def _on_merge_scene(self, scene_id: str):
        scenes = self.project.state.scenes
        idx = next((i for i, s in enumerate(scenes) if s.scene_id == scene_id), None)
        if idx is None or idx >= len(scenes) - 1:
            QMessageBox.warning(self, "Merge Not Possible", "No subsequent scene available to merge with.")
            return

        next_id = scenes[idx + 1].scene_id
        try:
            updated_list = TimelineEngine.merge_scenes(
                scenes,
                scene_id,
                next_id,
                self.project.state.narration
            )
            self.project.state.scenes = updated_list
            self._refresh_scenes_ui(updated_list)
            self.tab3_images.load_scenes(updated_list)
            self.tab4_render.load_project_data(updated_list, self.project.state.audio_file_path, self.project.state.narration)
            self._select_scene_by_id(scene_id)
            QMessageBox.information(self, "Scene Merged", f"Merged Scene #{scene_id} and #{next_id}.")
        except Exception as e:
            QMessageBox.critical(self, "Merge Failed", str(e))

    def _on_delete_scene(self, scene_id: str):
        try:
            updated_list = TimelineEngine.delete_scene(
                self.project.state.scenes,
                scene_id,
                self.project.state.narration
            )
            self.project.state.scenes = updated_list
            self._refresh_scenes_ui(updated_list, select_first=True)
            self.tab3_images.load_scenes(updated_list)
            self.tab4_render.load_project_data(updated_list, self.project.state.audio_file_path, self.project.state.narration)
            if not updated_list:
                self.scene_editor.load_scene(None)
        except Exception as e:
            QMessageBox.critical(self, "Delete Failed", str(e))

    def _on_add_manual_scene(self):
        scenes = self.project.state.scenes
        new_id = str(len(scenes) + 1)
        start_time = scenes[-1].end if scenes else 0.0
        end_time = round(start_time + 5.0, 2)
        new_scene = VisualScene(
            scene_id=new_id,
            start=round(start_time, 2),
            end=end_time,
            duration=5.0,
            narration_excerpt=f"Scene {new_id} narration excerpt...",
            visual_subject=f"Key Subject for Scene #{new_id}",
            framing_suggestion="Eye-level medium shot, cinematic lighting",
            prompt=f"A cinematic studio-quality visualization of Scene #{new_id}, highly detailed, volumetric lighting, photorealistic, 8k resolution.",
            is_manually_edited=True
        )
        scenes.append(new_scene)
        self.project.state.scenes = scenes
        self._refresh_scenes_ui(scenes)
        self.tab3_images.load_scenes(scenes)
        self.tab4_render.load_project_data(scenes, self.project.state.audio_file_path, self.project.state.narration)
        self._select_scene_by_id(new_id)

    # =========================================================================
    # CLOUD CONNECTION & RECOVERY
    # =========================================================================

    def _check_cloud_connection(self):
        self.modal_url_lbl.setText("⚡ Engine: Groq Multi-Key AI & Whisper (11 Keys Active)")
        self.cloud_status_lbl.setText("⏳ Checking Groq...")
        self.cloud_status_lbl.setStyleSheet("color: #38bdf8; font-size: 11px;")

        if self._cloud_worker and self._cloud_worker.isRunning():
            return

        self._cloud_worker = ConnectionCheckWorker(
            "groq",
            self.settings.api_key,
            self.settings.auth_token,
            timeout=15.0,
            parent=self
        )
        self._cloud_worker.result_ready.connect(self._on_cloud_check_finished)
        self._cloud_worker.start()

    def _on_cloud_check_finished(self, resp):
        if resp.connected:
            model = resp.backend_info.model if resp.backend_info else "qwen/qwen3.8-27b"
            gpu = resp.backend_info.gpu if resp.backend_info else "Groq LPU Array"
            self.status_banner.set_connected(
                model,
                gpu,
                resp.latency_ms
            )
            self.cloud_status_lbl.setText(f"✅ Groq Ready ({resp.latency_ms:.0f}ms)")
            self.cloud_status_lbl.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: bold;")
        else:
            self.status_banner.set_offline(resp.message)
            self.cloud_status_lbl.setText("⚠️ Groq Offline")
            self.cloud_status_lbl.setStyleSheet("color: #f87171; font-size: 11px;")

    def _check_project_recovery(self):
        unfinished = ProjectManager.check_for_unfinished_jobs(self.settings.workspace_directory)
        if unfinished:
            name, proj_dir, info = unfinished[0]
            dlg = RecoveryDialog(name, info.get("stage", "Unknown"), float(info.get("progress", 0.0)), self)
            if dlg.exec():
                if dlg.action in ("resume", "open"):
                    try:
                        proj = ProjectManager.load_project(proj_dir)
                        self._apply_project_to_ui(proj, auto_switch_tab=True)
                        if dlg.action == "resume":
                            if proj.state.story_raw_text:
                                self._on_start_generation()
                            else:
                                QMessageBox.information(self, "Story Required", "Please enter or check the story script in Tab 1, then click Generate Storyboard.")
                    except Exception as e:
                        QMessageBox.warning(self, "Recovery Notice", f"Could not load project: {str(e)}")
                elif dlg.action == "discard":
                    ProjectManager.clear_job_in_progress(proj_dir)

    def _on_open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self.settings = SettingsManager.load_settings()
            self._check_cloud_connection()

    def _on_open_preset_editor(self):
        dlg = PresetEditorDialog(self)
        if dlg.exec():
            self._populate_subject_combo()
            self._populate_style_combo()

    def _on_export_dialog(self):
        if not self.project.state.scenes:
            QMessageBox.warning(self, "No Scenes", "There are no generated scenes to export yet.")
            return

        dlg = ExportDialog(self.project.state.scenes, self.project.state.narration, self)
        dlg.exec()