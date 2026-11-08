"""
Scene Sync Panel for PromptBeast Studio Pro.
- Auto-loads the voiceover audio generated in Step 1 (no manual selection needed).
- Shows "Generate Images with Gemini" button that opens Chrome acc1 with Gemini Bulk Canvas.
- Auto-watches the project images folder for new downloads (every 3s).
- AI Auto-Place: maps all images across the narration timeline.
"""

import os
import re
import shutil
import zipfile
import time
from pathlib import Path
from typing import List, Optional, Union

from PySide6.QtCore import Qt, Signal, QUrl, QTimer
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
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
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from app.models.scene import VisualScene
from app.models.timeline import NarrationData, WordTimestamp
from app.core.timestamp_parser import TimestampParser


def natural_sort_key(p: Union[Path, str]):
    """Natural sorting key: puts numbered filenames in numerical order (001, 002, 010)."""
    name = Path(p).name
    nums = re.findall(r"\d+", name)
    return (0, int(nums[0]), name.lower()) if nums else (1, 0, name.lower())


class SceneSyncPanel(QWidget):
    """Studio panel: auto-loads audio, shows Gemini image generation, AI-paces images."""

    sync_completed = Signal(list, str, object)   # scenes, audio_path, narration
    navigate_to_deliverables = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.audio_path: Optional[str] = None
        self.images_folder: Optional[str] = None
        self.image_files: List[str] = []
        self.thumbnail_image_path: Optional[str] = None
        self.narration: Optional[NarrationData] = None
        self.scenes: List[VisualScene] = []
        self._project_dir: Optional[Path] = None
        self._prompts_path: Optional[Path] = None

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
    # UI BUILD
    # =========================================================================

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(12)

        # ── Row: Audio (left) + Images (right) ───────────────────────────────
        inputs_row = QHBoxLayout()
        inputs_row.setSpacing(12)

        # ── Left: Audio (auto-loaded, read-only display) ──────────────────────
        audio_box = QFrame()
        audio_box.setStyleSheet("""
            QFrame {
                background-color: #0E131B;
                border: 1px solid #1F2836;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        ab_layout = QVBoxLayout(audio_box)
        ab_layout.setContentsMargins(10, 8, 10, 8)
        ab_layout.setSpacing(8)

        a_hdr = QHBoxLayout()
        a_title = QLabel("🎵 1. Voiceover Audio Track")
        a_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #38BDF8;")
        self.audio_dur_lbl = QLabel("Duration: --:--")
        self.audio_dur_lbl.setStyleSheet("font-size: 11px; color: #94A3B8;")
        self.status_badge = QLabel("• 0 Images Synced")
        self.status_badge.setStyleSheet("""
            font-size: 11px;
            font-weight: 600;
            color: #34D399;
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid #10B981;
            border-radius: 6px;
            padding: 2px 8px;
        """)
        a_hdr.addWidget(a_title)
        a_hdr.addStretch()
        a_hdr.addWidget(self.audio_dur_lbl)
        a_hdr.addSpacing(6)
        a_hdr.addWidget(self.status_badge)
        ab_layout.addLayout(a_hdr)

        a_sel_row = QHBoxLayout()
        self.audio_path_edit = QLineEdit()
        self.audio_path_edit.setPlaceholderText("Auto-loaded from Step 1 (Kokoro voiceover)...")
        self.audio_path_edit.setReadOnly(True)
        self.audio_path_edit.setStyleSheet(
            "background: #111827; color: #4ade80; border: 1px solid #1F2836; "
            "border-radius: 4px; padding: 4px 8px; font-size: 11px;"
        )
        # Fallback browse (kept hidden by default, revealed if auto-load fails)
        self.browse_audio_btn = QPushButton("Browse")
        self.browse_audio_btn.setCursor(Qt.PointingHandCursor)
        self.browse_audio_btn.setFixedWidth(65)
        self.browse_audio_btn.setStyleSheet(
            "background:#1e293b; color:#94a3b8; border:1px solid #334155; "
            "border-radius:4px; font-size:10px;"
        )
        self.browse_audio_btn.clicked.connect(self._on_browse_audio)

        self.view_json_btn = QPushButton("📄 JSON")
        self.view_json_btn.setToolTip("View or export standardized word timestamps JSON")
        self.view_json_btn.setCursor(Qt.PointingHandCursor)
        self.view_json_btn.setFixedWidth(55)
        self.view_json_btn.setStyleSheet(
            "background:#1e293b; color:#38bdf8; border:1px solid #334155; "
            "border-radius:4px; font-size:10px; font-weight:600;"
        )
        self.view_json_btn.clicked.connect(self._on_view_timestamps_json)

        a_sel_row.addWidget(self.audio_path_edit, 1)
        a_sel_row.addWidget(self.browse_audio_btn)
        a_sel_row.addWidget(self.view_json_btn)
        ab_layout.addLayout(a_sel_row)

        # Mini-player
        play_row = QHBoxLayout()
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setFixedWidth(70)
        self.play_btn.clicked.connect(self._toggle_play)
        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.sliderMoved.connect(self._on_slider_moved)
        play_row.addWidget(self.play_btn)
        play_row.addWidget(self.seek_slider, 1)
        ab_layout.addLayout(play_row)

        inputs_row.addWidget(audio_box, 1)

        # ── Right: Gemini Image Generation ────────────────────────────────────
        img_box = QFrame()
        img_box.setStyleSheet("""
            QFrame {
                background-color: #0E131B;
                border: 1px solid #1F2836;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        ib_layout = QVBoxLayout(img_box)
        ib_layout.setContentsMargins(10, 8, 10, 8)
        ib_layout.setSpacing(8)

        i_hdr = QHBoxLayout()
        i_title = QLabel("🤖 2. Generate Images with Gemini")
        i_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #A6FF00;")
        self.img_count_badge = QLabel("0 images ready")
        self.img_count_badge.setStyleSheet("font-size: 11px; font-weight: 600; color: #94A3B8;")
        i_hdr.addWidget(i_title)
        i_hdr.addStretch()
        i_hdr.addWidget(self.img_count_badge)
        ib_layout.addLayout(i_hdr)

        # Primary CTA: Generate Images button + Multi-Account Hub
        gen_btn_row = QHBoxLayout()
        gen_btn_row.setSpacing(8)

        self.generate_images_btn = QPushButton(
            "🚀  Generate Images — Open Gemini with Connected Account"
        )
        self.generate_images_btn.setFixedHeight(36)
        self.generate_images_btn.setCursor(Qt.PointingHandCursor)
        self.generate_images_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #7C3AED, stop:1 #4F46E5);
                color: #FFFFFF;
                font-size: 12px;
                font-weight: 800;
                border: none;
                border-radius: 6px;
                padding: 0 14px;
                letter-spacing: 0.3px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #8B5CF6, stop:1 #6366F1);
            }
            QPushButton:disabled {
                background: #1e293b;
                color: #4B5563;
            }
        """)
        self.generate_images_btn.clicked.connect(self._on_generate_images)
        gen_btn_row.addWidget(self.generate_images_btn, 1)

        self.multi_acc_btn = QPushButton("👥 Multi-Account Hub")
        self.multi_acc_btn.setToolTip("Generate images across multiple Google accounts (acc1..acc6) in 100-prompt batches")
        self.multi_acc_btn.setFixedHeight(36)
        self.multi_acc_btn.setCursor(Qt.PointingHandCursor)
        self.multi_acc_btn.setStyleSheet("""
            QPushButton {
                background: #1E293B;
                color: #A78BFA;
                font-size: 11px;
                font-weight: 700;
                border: 1px solid #4F46E5;
                border-radius: 6px;
                padding: 0 10px;
            }
            QPushButton:hover {
                background: #312E81;
                color: #FFFFFF;
            }
        """)
        self.multi_acc_btn.clicked.connect(self._open_multi_account_hub)
        gen_btn_row.addWidget(self.multi_acc_btn)
        ib_layout.addLayout(gen_btn_row)

        # Folder path + secondary controls row
        folder_row = QHBoxLayout()
        self.img_folder_edit = QLineEdit()
        self.img_folder_edit.setPlaceholderText("Project images folder (auto-selected)...")
        self.img_folder_edit.setReadOnly(True)
        self.img_folder_edit.setStyleSheet(
            "background: #111827; color: #94a3b8; border: 1px solid #1F2836; "
            "border-radius: 4px; padding: 4px 8px; font-size: 10px;"
        )
        self.import_downloads_btn = QPushButton("📥 Unpack ZIP / Scan Images")
        self.import_downloads_btn.setToolTip(
            "Auto-extract ZIP archives in project images folder, scan images, or import from Downloads"
        )
        self.import_downloads_btn.setCursor(Qt.PointingHandCursor)
        self.import_downloads_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #334155; color: #fff; }
        """)
        self.import_downloads_btn.clicked.connect(self._on_import_downloads)
        folder_row.addWidget(self.img_folder_edit, 1)
        folder_row.addWidget(self.import_downloads_btn)
        ib_layout.addLayout(folder_row)

        # Watcher status line
        self.folder_status_lbl = QLabel(
            "🟡 Waiting for images… (auto-refreshes every 3s after Gemini generates)"
        )
        self.folder_status_lbl.setStyleSheet("font-size: 11px; color: #64748B; margin-top: 2px;")
        self.folder_status_lbl.setWordWrap(True)
        ib_layout.addWidget(self.folder_status_lbl)

        inputs_row.addWidget(img_box, 1)
        main_layout.addLayout(inputs_row)

        # ── Action Bar ────────────────────────────────────────────────────────
        # Hidden compatibility handles for ASR Engine & Transcribe
        self.whisper_mode_combo = QComboBox()
        self.whisper_mode_combo.addItem("💻 Local Faster-Whisper (Offline)", "local")
        self.whisper_mode_combo.addItem("⚡ Groq Whisper Cloud (v3-turbo)", "groq")
        self.whisper_mode_combo.setVisible(False)
        self.transcribe_btn = QPushButton("🎙️ 1. Transcribe Subtitles")
        self.transcribe_btn.setVisible(False)
        self.transcribe_btn.clicked.connect(self._on_transcribe_audio)

        action_bar = QFrame()
        action_bar.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0B0E14, stop:1 #131A24);
                border: 1px solid #1F2836;
                border-radius: 8px;
                padding: 6px 12px;
            }
        """)
        act_layout = QHBoxLayout(action_bar)
        act_layout.setContentsMargins(10, 6, 10, 6)
        act_layout.setSpacing(12)

        self.auto_pace_btn = QPushButton("⚡ AI Auto-Place & Pace Images Across Timeline")
        self.auto_pace_btn.setFixedHeight(38)
        self.auto_pace_btn.setCursor(Qt.PointingHandCursor)
        self.auto_pace_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:0.5 #34D399, stop:1 #A6FF00);
                color: #080D0B;
                font-size: 13px;
                font-weight: 800;
                letter-spacing: 0.4px;
                border: none;
                border-radius: 6px;
                padding: 0 20px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #34D399, stop:1 #B8FF24);
            }
            QPushButton:disabled {
                background: #1e293b;
                color: #4B5563;
            }
        """)
        self.auto_pace_btn.clicked.connect(self._on_ai_auto_pace)
        act_layout.addWidget(self.auto_pace_btn, 1)

        self.pace_status_hint = QLabel("• Auto-maps scene visuals to narration timestamps")
        self.pace_status_hint.setStyleSheet("font-size: 11px; color: #94A3B8; font-weight: 500;")
        act_layout.addWidget(self.pace_status_hint)

        main_layout.addWidget(action_bar)

        # Progress bar
        self.sync_progress = QProgressBar()
        self.sync_progress.setFixedHeight(6)
        self.sync_progress.setTextVisible(False)
        self.sync_progress.setStyleSheet(
            "QProgressBar { background: #141B26; border: none; border-radius: 3px; } "
            "QProgressBar::chunk { background: #A6FF00; border-radius: 3px; }"
        )
        self.sync_progress.hide()
        main_layout.addWidget(self.sync_progress)

        # Scene timeline table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["Scene #", "Thumbnail", "Image Filename", "Start Time", "End Time", "Duration"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(60)
        self.table.verticalHeader().hide()
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #0B0E14;
                border: 1px solid #1F2836;
                border-radius: 6px;
                color: #F8FAFC;
                gridline-color: #1A2332;
            }
            QHeaderView::section {
                background-color: #0E131B;
                color: #94A3B8;
                font-weight: 700;
                font-size: 11px;
                border: none;
                border-bottom: 1px solid #1F2836;
                padding: 6px;
            }
        """)
        main_layout.addWidget(self.table, 1)

        # Bottom nav
        bottom_nav_row = QHBoxLayout()
        bottom_nav_row.setContentsMargins(0, 4, 0, 0)

        self.summary_sync_lbl = QLabel("Audio auto-loaded from Step 1. Generate images, then click AI Auto-Place.")
        self.summary_sync_lbl.setStyleSheet("font-size: 12px; color: #94A3B8; font-weight: 500;")
        bottom_nav_row.addWidget(self.summary_sync_lbl)
        bottom_nav_row.addStretch()

        self.next_step_btn = QPushButton("➔ Next Step: Proceed to Deliverables (Render Final Video)")
        self.next_step_btn.setFixedHeight(38)
        self.next_step_btn.setCursor(Qt.PointingHandCursor)
        self.next_step_btn.setStyleSheet("""
            QPushButton {
                background-color: #141821;
                color: #A6FF00;
                font-size: 13px;
                font-weight: 700;
                border: 1px solid #A6FF00;
                border-radius: 6px;
                padding: 0 18px;
            }
            QPushButton:hover { background-color: rgba(166,255,0,0.12); }
        """)
        self.next_step_btn.clicked.connect(self._on_proceed_to_deliverables)
        bottom_nav_row.addWidget(self.next_step_btn)

        main_layout.addLayout(bottom_nav_row)

    # =========================================================================
    # PUBLIC SETTERS — called by MainWindow
    # =========================================================================

    def set_audio_path(self, path: str):
        """Auto-load audio from project state (called by MainWindow)."""
        if path and Path(path).exists():
            self.audio_path = str(Path(path).resolve())
            self.audio_path_edit.setText(f"✅ {Path(path).name}")
            self.audio_path_edit.setStyleSheet(
                "background: #0b1a0e; color: #4ade80; border: 1px solid #166534; "
                "border-radius: 4px; padding: 4px 8px; font-size: 11px;"
            )
            self._player.setSource(QUrl.fromLocalFile(self.audio_path))
            self._update_audio_duration_label()

            # Auto-check for existing timestamps beside audio
            try:
                from app.core.audio_alignment_engine import AudioAlignmentEngine
                from app.models.timeline import NarrationData
                ap = Path(self.audio_path)
                align_eng = AudioAlignmentEngine()
                candidates = [
                    ap.parent / "narration_timestamps.json",
                    ap.with_suffix(".json"),
                ]
                for cand in candidates:
                    if cand.exists():
                        loaded_narr = NarrationData.from_standard_json(cand)
                        align_eng.validate_alignment(loaded_narr, audio_path=ap)
                        self.narration = loaded_narr
                        status_str = "Verified" if loaded_narr.is_verified else ("Degraded" if loaded_narr.is_degraded else "Loaded")
                        self.status_badge.setText(f"• {len(loaded_narr.words)} Words ({status_str})")
                        self.summary_sync_lbl.setText(
                            f"✅ Audio & Timestamps Auto-Loaded ({len(loaded_narr.words)} words, {loaded_narr.duration_seconds:.1f}s) • {loaded_narr.alignment_status}"
                        )
                        break
            except Exception as e:
                print(f"[SceneSync] Notice auto-loading timestamps: {e}")
        else:
            # Try to auto-find the most recently modified narration.wav across all projects
            self._auto_find_audio()

    def _auto_find_audio(self):
        """Scan project dir and workspace directories for the most recent voiceover audio."""
        try:
            from app.config.settings import SettingsManager
            settings = SettingsManager.load_settings()
            search_roots = []
            if self._project_dir and Path(self._project_dir).exists():
                search_roots.append(Path(self._project_dir))
            if settings.workspace_directory:
                search_roots.append(Path(settings.workspace_directory))
            search_roots.append(Path("projects"))

            candidates = []
            for root in search_roots:
                if not root.exists():
                    continue
                for name in ("narration.wav", "narration.mp3", "voiceover.wav", "voiceover.mp3"):
                    direct = root / name
                    if direct.is_file():
                        candidates.append(direct)
                    sub = root / "audio" / name
                    if sub.is_file():
                        candidates.append(sub)
                for f in root.glob("*/*narration*.*"):
                    if f.is_file() and f.suffix.lower() in (".wav", ".mp3"):
                        candidates.append(f)
                for f in root.glob("*/*/*narration*.*"):
                    if f.is_file() and f.suffix.lower() in (".wav", ".mp3"):
                        candidates.append(f)

            if not candidates:
                return

            best = max(set(candidates), key=lambda p: p.stat().st_mtime)
            self.set_audio_path(str(best))
            print(f"[SceneSync] Auto-found audio: {best}")
        except Exception as e:
            print(f"[SceneSync] Auto-find audio notice: {e}")

    def _auto_find_project(self):
        """Auto-resolve the most recent project directory if not explicitly set."""
        if self._project_dir and self._project_dir.exists():
            return
        try:
            from app.config.settings import SettingsManager
            settings = SettingsManager.load_settings()
            roots = [Path(settings.workspace_directory), Path("projects")]
            dirs = []
            for r in roots:
                if r.exists():
                    for d in r.iterdir():
                        if d.is_dir() and d.name not in ("temp", "__pycache__", "projects"):
                            dirs.append(d)
            if dirs:
                best_dir = max(dirs, key=lambda d: d.stat().st_mtime)
                self.set_project(best_dir)
                print(f"[SceneSync] Auto-found active project: {best_dir}")
        except Exception as e:
            print(f"[SceneSync] Auto-find project notice: {e}")

    def set_images_folder(self, folder: str):
        """Set the project images folder (always updates display even if empty)."""
        if folder:
            p = Path(folder)
            p.mkdir(parents=True, exist_ok=True)
            self.images_folder = str(p.resolve())
            self.img_folder_edit.setText(str(p.resolve()))
            self._scan_images()
            # Start watching for new images
            if not self._watch_timer.isActive():
                self._watch_timer.start()

    def set_project(self, project_dir: Path):
        """Called by MainWindow when project is loaded or generation completes."""
        self._project_dir = Path(project_dir)

        # Auto-set images folder
        img_dir = self._project_dir / "images"
        img_dir.mkdir(parents=True, exist_ok=True)
        self.set_images_folder(str(img_dir))

        # Look for prompts file
        for name in ("prompts_only.txt", "prompts.txt", "image_prompts.txt"):
            p = self._project_dir / name
            if p.exists():
                self._prompts_path = p
                break

        # Update generate button tooltip with prompt count
        self._refresh_generate_btn_label()

    def _refresh_generate_btn_label(self):
        """Update generate button to show prompt count."""
        count = 0
        if self._prompts_path and self._prompts_path.exists():
            try:
                text = self._prompts_path.read_text(encoding="utf-8")
                # Count non-empty lines as prompt count
                count = sum(1 for ln in text.splitlines() if ln.strip())
            except Exception:
                pass

        if count > 100:
            self.generate_images_btn.setText(
                f"🚀  Generate {count} Images — Multi-Account Hub (acc1..acc6)"
            )
        elif count > 0:
            self.generate_images_btn.setText(
                f"🚀  Generate {count} Images — Open Gemini with Connected Account (acc1)"
            )
        else:
            self.generate_images_btn.setText(
                "🚀  Generate Images — Open Gemini with Connected Account (acc1)"
            )

    # =========================================================================
    # GEMINI IMAGE GENERATION
    # =========================================================================

    def _open_multi_account_hub(self):
        """Open the multi-account batch generation dialog for splitting prompts across Google accounts."""
        if not self.images_folder and not self._project_dir:
            self._auto_find_project()

        if self.images_folder:
            img_dir = Path(self.images_folder)
        elif self._project_dir:
            img_dir = self._project_dir / "images"
            img_dir.mkdir(parents=True, exist_ok=True)
            self.set_images_folder(str(img_dir))
        else:
            QMessageBox.warning(
                self,
                "No Project Loaded",
                "Please complete Step 1 (Script → Voiceover → Generate Prompts) first.",
            )
            return

        prompts_list = []
        if self._prompts_path and self._prompts_path.exists():
            try:
                txt = self._prompts_path.read_text(encoding="utf-8")
                prompts_list = [ln.strip() for ln in txt.splitlines() if ln.strip()]
            except Exception:
                pass

        if not prompts_list and self.scenes:
            prompts_list = [s.image_prompt for s in self.scenes if getattr(s, "image_prompt", None)]

        if not prompts_list:
            QMessageBox.warning(
                self,
                "No Prompts Available",
                "No generated prompts were found. Please generate storyboard prompts first.",
            )
            return

        from app.ui.dialogs.multi_account_dialog import MultiAccountGenerationDialog
        dlg = MultiAccountGenerationDialog(
            prompts=prompts_list,
            project_dir=Path(self._project_dir) if self._project_dir else img_dir.parent,
            images_dir=img_dir,
            batch_size=100,
            parent=self,
        )
        self._watch_timer.start()
        self.folder_status_lbl.setText(
            "🟢 Watching for new images… (auto-refreshes every 3s across all account folders)"
        )
        self.folder_status_lbl.setStyleSheet("font-size: 11px; color: #4ade80; margin-top: 2px;")
        dlg.exec()

    def _on_generate_images(self):
        """Open Chrome with acc1 profile + Gemini Bulk Canvas, or Multi-Account Hub if > 100 prompts."""
        from app.core.browser_profiles_manager import BrowserProfilesManager

        # Auto-find project if not yet set
        if not self.images_folder and not self._project_dir:
            self._auto_find_project()

        # Check prompt count to see if multi-account is needed
        prompts_count = 0
        if self._prompts_path and self._prompts_path.exists():
            try:
                txt = self._prompts_path.read_text(encoding="utf-8")
                prompts_count = sum(1 for ln in txt.splitlines() if ln.strip())
            except Exception:
                pass
        elif self.scenes:
            prompts_count = len(self.scenes)

        if prompts_count > 100:
            self._open_multi_account_hub()
            return

        # Ensure images folder exists and is configured as Chrome download dir
        if self.images_folder:
            img_dir = Path(self.images_folder)
        elif self._project_dir:
            img_dir = self._project_dir / "images"
            img_dir.mkdir(parents=True, exist_ok=True)
            self.set_images_folder(str(img_dir))
        else:
            QMessageBox.warning(
                self,
                "No Project Loaded",
                "Please complete Step 1 (Script → Voiceover → Generate Prompts) first.",
            )
            return

        # Copy clean single-line prompts directly to clipboard for 1-click paste into Gemini
        from app.core.export import StoryboardExporter
        copied_prompts = False
        clean_payload = ""

        # Prioritize prompts_only.txt if available
        candidates = [
            self._project_dir / "prompts_only.txt",
            Path("prompts_only.txt"),
            self._prompts_path if self._prompts_path else None
        ]
        target_path = next((p for p in candidates if p and p.exists()), None)

        if target_path and target_path.exists():
            try:
                raw_txt = target_path.read_text(encoding="utf-8")
                # Collapse all prompts strictly to 1 single clean line per scene
                if "IMAGE 00" in raw_txt or "NARRATION:" in raw_txt:
                    # Parse image_prompts.txt format if only detailed file is present
                    lines = []
                    for block in raw_txt.split("---"):
                        if "PROMPT:" in block:
                            p_part = block.split("PROMPT:", 1)[1].strip()
                            clean_line = StoryboardExporter.clean_prompt_single_line(p_part)
                            if clean_line:
                                lines.append(clean_line)
                    clean_payload = "\n".join(lines)
                else:
                    lines = [StoryboardExporter.clean_prompt_single_line(ln) for ln in raw_txt.splitlines() if ln.strip()]
                    clean_payload = "\n".join(lines)

                if clean_payload.strip():
                    QApplication.clipboard().setText(clean_payload.strip())
                    verified = QApplication.clipboard().text()
                    if verified.strip() == clean_payload.strip():
                        copied_prompts = True
                    else:
                        print("[SceneSync] Warning: Windows clipboard verification failed.")
            except Exception as ex:
                print(f"[SceneSync] Notice copying prompts from file: {ex}")

        # Fallback to in-memory scenes if files were missing or empty
        if not clean_payload.strip() and self.scenes:
            try:
                lines = [
                    StoryboardExporter.clean_prompt_single_line(s.prompt)
                    for s in self.scenes if getattr(s, "prompt", None)
                ]
                clean_payload = "\n".join(lines)
                if clean_payload.strip():
                    QApplication.clipboard().setText(clean_payload.strip())
                    verified = QApplication.clipboard().text()
                    if verified.strip() == clean_payload.strip():
                        copied_prompts = True
            except Exception as ex:
                print(f"[SceneSync] Notice copying prompts from scenes: {ex}")

        # Set Chrome acc1 download dir to project images folder
        BrowserProfilesManager.configure_download_dir("acc1", img_dir)

        # Open Chrome with guaranteed clipboard copy
        ok, msg = BrowserProfilesManager.open_browser_profile("acc1", download_dir=img_dir, prompts_text=clean_payload)

        if not ok:
            QMessageBox.critical(self, "Chrome Not Found", msg)
            return

        # Show instructions dialog with the prompts
        self._show_gemini_instructions(copied_prompts)

        # Start watching for new images
        self._watch_timer.start()
        self.folder_status_lbl.setText(
            "🟢 Watching for new images… (auto-refreshes every 3s as Gemini generates)"
        )
        self.folder_status_lbl.setStyleSheet("font-size: 11px; color: #4ade80; margin-top: 2px;")

    def _show_gemini_instructions(self, copied_prompts: bool = False):
        """Show a non-blocking info dialog with the prompts and workflow instructions."""
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Gemini Image Generation Started")
        dlg.setIcon(QMessageBox.Information)

        prompts_preview = ""
        prompt_count = 0
        if self._prompts_path and self._prompts_path.exists():
            try:
                text = self._prompts_path.read_text(encoding="utf-8")
                lines = [ln for ln in text.splitlines() if ln.strip()]
                prompt_count = len(lines)
                prompts_preview = f"\n\nPrompts file: {self._prompts_path}\n({prompt_count} prompts ready)"
            except Exception:
                pass

        clipboard_notice = "📋 Prompts copied to your clipboard! Just press Ctrl+V in Gemini.\n\n" if copied_prompts else ""

        dlg.setText(
            "✅ Chrome opened with your connected Gemini account (acc1).\n\n"
            + clipboard_notice +
            "📋 How to generate images:\n"
            "1. In Chrome, go to Gemini Bulk Canvas (already opened)\n"
            "2. Press Ctrl+V to paste your prompts\n"
            "3. Click Generate — images will auto-download directly to your project's images folder\n"
            "4. Return to PromptBeast — images appear here automatically!"
            + prompts_preview
        )

        open_btn = dlg.addButton("📋 Open Prompts File", QMessageBox.ActionRole)
        dlg.addButton("Got it!", QMessageBox.AcceptRole)

        dlg.exec()

        if dlg.clickedButton() == open_btn and self._prompts_path:
            import subprocess
            try:
                subprocess.Popen(["notepad.exe", str(self._prompts_path)])
            except Exception:
                pass

    def _on_watch_tick(self):
        """Poll images folder every 3s; auto-extract new ZIPs and update badge if images appear."""
        if not self.images_folder or not Path(self.images_folder).exists():
            return
        target_p = Path(self.images_folder)
        # Check for any new zip files in images folder or subfolders
        if any(target_p.glob("*.zip")):
            self._auto_extract_zip_files(target_p)
        exts = (".jpg", ".jpeg", ".png", ".webp")
        count = sum(1 for f in target_p.iterdir() if f.suffix.lower() in exts)
        for sdir in [p for p in target_p.iterdir() if p.is_dir() and not p.name.startswith(".")]:
            if any(sdir.glob("*.zip")):
                self._auto_extract_zip_files(sdir)
            count += sum(1 for f in sdir.iterdir() if f.suffix.lower() in exts)

        if count != self._last_image_count:
            self._last_image_count = count
            self._scan_images()
            if count > 0:
                self.folder_status_lbl.setText(
                    f"✅ {count} images detected — click 'AI Auto-Place' to sync!"
                )
                self.folder_status_lbl.setStyleSheet(
                    "font-size: 11px; color: #4ade80; margin-top: 2px;"
                )

    def _auto_extract_zip_files(self, target_dir: Path) -> int:
        """Automatically extracts any .zip files containing generated images directly into target_dir."""
        if not target_dir.exists():
            return 0

        total_extracted = 0
        for zip_p in list(target_dir.glob("*.zip")):
            try:
                extracted = 0
                with zipfile.ZipFile(zip_p, "r") as zf:
                    for member in zf.infolist():
                        if member.is_dir():
                            continue
                        fname = Path(member.filename).name
                        if fname.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                            dest_file = target_dir / fname
                            # Prevent overwriting if file with same name exists from another batch/zip
                            if dest_file.exists():
                                dest_file = target_dir / f"{zip_p.stem}_{fname}"
                            with zf.open(member) as s_f, open(dest_file, "wb") as d_f:
                                shutil.copyfileobj(s_f, d_f)
                            extracted += 1
                if extracted > 0:
                    marker = zip_p.with_suffix(".zip.extracted")
                    if marker.exists():
                        marker.unlink()
                    zip_p.rename(marker)
                    total_extracted += extracted
                    print(f"[SceneSync] Auto-extracted {extracted} images from {zip_p.name} into {target_dir.name}")
            except Exception as e:
                print(f"[SceneSync] ZIP auto-extract notice for {zip_p.name}: {e}")
        return total_extracted

    def _on_import_downloads(self):
        """
        Scan project images folder first for ZIP archives or image files.
        If empty, checks user Downloads folder as a fallback, or lets the user select a ZIP archive.
        """
        if not self.images_folder and not self._project_dir:
            self._auto_find_project()

        if not self.images_folder and self._project_dir:
            img_dir = self._project_dir / "images"
            img_dir.mkdir(parents=True, exist_ok=True)
            self.set_images_folder(str(img_dir))

        if not self.images_folder:
            QMessageBox.warning(self, "No Project Folder", "Please complete Step 1 (Plan Storyboard) first.")
            return

        dest_dir = Path(self.images_folder)
        dest_dir.mkdir(parents=True, exist_ok=True)
        exts = (".png", ".jpg", ".jpeg", ".webp")

        # -------------------------------------------------------------
        # 1. Check Project Images Folder & Project Directory FIRST for ZIP files
        # -------------------------------------------------------------
        extracted_from_project = self._auto_extract_zip_files(dest_dir)

        # Check subfolders (e.g. acc1, acc2, batch1)
        for sdir in [p for p in dest_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]:
            extracted_from_project += self._auto_extract_zip_files(sdir)

        # Also check project root for any accidentally dropped ZIP
        if self._project_dir and Path(self._project_dir).exists():
            for p_zip in list(Path(self._project_dir).glob("*.zip")):
                try:
                    shutil.move(str(p_zip), str(dest_dir / p_zip.name))
                    extracted_from_project += self._auto_extract_zip_files(dest_dir)
                except Exception:
                    pass

        self._scan_images()

        if extracted_from_project > 0:
            QMessageBox.information(
                self,
                "ZIP Unpacked Successfully",
                f"Extracted {extracted_from_project} images from ZIP archive(s) directly in your project folder!\n\n"
                f"Total images ready: {len(self.image_files)}\nFolder: {dest_dir}"
            )
            return

        # -------------------------------------------------------------
        # 2. If project images folder already has images, notify and finish
        # -------------------------------------------------------------
        if len(self.image_files) > 0:
            QMessageBox.information(
                self,
                "Images Detected",
                f"Found {len(self.image_files)} images ready in project folder:\n{dest_dir}\n\n"
                "Click 'AI Auto-Place' to map them across the audio timeline."
            )
            return

        # -------------------------------------------------------------
        # 3. Fallback: Check Downloads folder for recent Gemini downloads
        # -------------------------------------------------------------
        downloads_dir = Path.home() / "Downloads"
        copied = 0
        if downloads_dir.exists():
            now = time.time()
            recent_images = []
            recent_zips = []
            for f in downloads_dir.iterdir():
                if f.is_file():
                    suf = f.suffix.lower()
                    try:
                        if now - f.stat().st_mtime < 48 * 3600:
                            if suf in exts:
                                recent_images.append((f.stat().st_mtime, f))
                            elif suf == ".zip":
                                recent_zips.append((f.stat().st_mtime, f))
                    except Exception:
                        pass

            # Extract any recent image zip files from Downloads
            recent_zips.sort(key=lambda x: x[0], reverse=True)
            for _, zip_p in recent_zips:
                try:
                    with zipfile.ZipFile(zip_p, "r") as zf:
                        has_imgs = any(Path(m.filename).name.lower().endswith(exts) for m in zf.infolist())
                        if has_imgs:
                            for member in zf.infolist():
                                if member.is_dir():
                                    continue
                                fn = Path(member.filename).name
                                if fn.lower().endswith(exts):
                                    dest_f = dest_dir / fn
                                    if dest_f.exists():
                                        dest_f = dest_dir / f"{zip_p.stem}_{fn}"
                                    with zf.open(member) as s_f, open(dest_f, "wb") as d_f:
                                        shutil.copyfileobj(s_f, d_f)
                                    copied += 1
                except Exception as ze:
                    print(f"[SceneSync] Error extracting zip from Downloads: {ze}")

            # Copy individual recent image files from Downloads
            recent_images.sort(key=lambda x: x[0])
            for _, src in recent_images:
                try:
                    shutil.copy2(src, dest_dir / src.name)
                    copied += 1
                except Exception:
                    pass

        if copied > 0:
            self._scan_images()
            QMessageBox.information(
                self, "Import Complete", f"Imported {copied} images from Downloads into:\n{dest_dir}"
            )
            return

        # -------------------------------------------------------------
        # 4. If nothing in project or Downloads, offer manual ZIP file picker
        # -------------------------------------------------------------
        ret = QMessageBox.question(
            self,
            "No Images or ZIP Found",
            f"No images or ZIP files were found in your project images folder:\n{dest_dir}\n"
            f"(or in Downloads).\n\n"
            "Would you like to browse and select a ZIP archive or image folder?",
            QMessageBox.Yes | QMessageBox.No
        )
        if ret == QMessageBox.Yes:
            f, _ = QFileDialog.getOpenFileName(
                self, "Select Image ZIP Archive", "", "ZIP Archives (*.zip);;Image Files (*.jpg *.png *.webp);;All Files (*.*)"
            )
            if f:
                sel_p = Path(f)
                if sel_p.suffix.lower() == ".zip":
                    shutil.copy2(sel_p, dest_dir / sel_p.name)
                    self._auto_extract_zip_files(dest_dir)
                elif sel_p.suffix.lower() in exts:
                    shutil.copy2(sel_p, dest_dir / sel_p.name)
                self._scan_images()
                QMessageBox.information(
                    self, "Images Loaded", f"Loaded {len(self.image_files)} images into project folder!"
                )

    def _on_browse_audio(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Select Voiceover Audio", "", "Audio Files (*.wav *.mp3 *.m4a *.aac *.flac)"
        )
        if f:
            self.set_audio_path(f)

    def _on_browse_images_folder(self):
        f = QFileDialog.getExistingDirectory(self, "Select Generated Images Folder")
        if f:
            self.set_images_folder(f)

    def _scan_images(self):
        if not self.images_folder or not Path(self.images_folder).exists():
            return

        target_path = Path(self.images_folder)

        # Auto-extract any zip files in the images folder first
        self._auto_extract_zip_files(target_path)

        exts = (".jpg", ".jpeg", ".png", ".webp")
        all_files = []

        # 1. Direct image files in images folder
        direct_files = [p for p in target_path.iterdir() if p.is_file() and p.suffix.lower() in exts]
        all_files.extend(sorted(direct_files, key=natural_sort_key))

        # 2. Subfolders (e.g. acc1, acc2, acc3, batch1, batch2) in natural sorted order
        subdirs = [p for p in target_path.iterdir() if p.is_dir() and not p.name.startswith(".")]
        for sdir in sorted(subdirs, key=natural_sort_key):
            self._auto_extract_zip_files(sdir)
            sub_files = [p for p in sdir.iterdir() if p.is_file() and p.suffix.lower() in exts]
            all_files.extend(sorted(sub_files, key=natural_sort_key))

        self.image_files = [str(p.resolve()) for p in all_files]
        count = len(self.image_files)
        self._last_image_count = count

        if count > 0:
            if any("thumb" in Path(f).name.lower() for f in self.image_files):
                thumb_cand = [f for f in self.image_files if "thumb" in Path(f).name.lower()][0]
                self.thumbnail_image_path = thumb_cand
                story_cnt = count - 1
                self.img_count_badge.setText(f"{count} images (1 Thumb + {story_cnt} Scenes)")
            elif count > 1:
                self.thumbnail_image_path = self.image_files[0]
                story_cnt = count - 1
                self.img_count_badge.setText(f"{count} images (1 Thumb [01] + {story_cnt} Scenes [02..{count:02d}])")
            else:
                self.thumbnail_image_path = None
                self.img_count_badge.setText(f"{count} images ready")
            self.img_count_badge.setStyleSheet("font-size: 11px; font-weight: 700; color: #A6FF00;")
            self.folder_status_lbl.setText(
                f"✅ {count} images in {Path(self.images_folder).name} — ready to sync!"
            )
            self.folder_status_lbl.setStyleSheet("font-size: 11px; color: #4ade80; margin-top: 2px;")
            self.summary_sync_lbl.setText(
                f"Ready: {count} images detected. Click 'AI Auto-Place' to map them across the audio."
            )
        else:
            self.thumbnail_image_path = None
            self.img_count_badge.setText("0 images ready")
            self.img_count_badge.setStyleSheet("font-size: 11px; font-weight: 600; color: #94A3B8;")
            self.folder_status_lbl.setText(
                "🟡 No images yet — click 'Generate Images' to open Gemini, or 'Unpack ZIP / Scan Images'."
            )

    def _toggle_play(self):
        if not self.audio_path:
            return
        if self._player.playbackState() == QMediaPlayer.PlayingState:
            self._player.pause()
            self.play_btn.setText("▶ Play")
        else:
            self._player.play()
            self.play_btn.setText("⏸ Pause")

    def _on_player_pos_changed(self, pos_ms: int):
        dur_ms = self._player.duration()
        if dur_ms > 0:
            self.seek_slider.setValue(int((pos_ms / dur_ms) * 1000))
        cur_sec = pos_ms / 1000.0
        tot_sec = dur_ms / 1000.0
        self.audio_dur_lbl.setText(
            f"{int(cur_sec//60):02d}:{int(cur_sec%60):02d} / {int(tot_sec//60):02d}:{int(tot_sec%60):02d}"
        )

    def _on_player_dur_changed(self, dur_ms: int):
        tot_sec = dur_ms / 1000.0
        self.audio_dur_lbl.setText(f"00:00 / {int(tot_sec//60):02d}:{int(tot_sec%60):02d}")

    def _on_slider_moved(self, val: int):
        dur_ms = self._player.duration()
        if dur_ms > 0:
            self._player.setPosition(int((val / 1000.0) * dur_ms))

    def _update_audio_duration_label(self):
        try:
            import soundfile as sf
            info = sf.info(self.audio_path)
            tot_sec = info.duration
            self.audio_dur_lbl.setText(
                f"Duration: {int(tot_sec//60):02d}:{int(tot_sec%60):02d} ({tot_sec:.1f}s)"
            )
        except Exception:
            pass

    # =========================================================================
    # TRANSCRIPTION
    # =========================================================================

    def _on_transcribe_audio(self):
        if not self.audio_path or not Path(self.audio_path).exists():
            QMessageBox.warning(
                self, "No Audio", "Audio not loaded. Complete Step 1 (voiceover synthesis) first."
            )
            return

        self.transcribe_btn.setEnabled(False)
        self.transcribe_btn.setText("Transcribing...")
        self.sync_progress.show()
        self.sync_progress.setRange(0, 0)

        mode = self.whisper_mode_combo.currentData() or "local"

        def _do_transcribe():
            try:
                from app.core.audio_alignment_engine import AudioAlignmentEngine
                align_eng = AudioAlignmentEngine()
                engine_type = "groq-whisper" if mode == "groq" else "faster-whisper"
                narration = align_eng.align_uploaded_audio(self.audio_path, engine=engine_type)
                return narration, None
            except Exception as e:
                try:
                    if mode == "groq":
                        from app.ai.groq_whisper import GroqWhisperEngine
                        narration = GroqWhisperEngine().transcribe(self.audio_path)
                    else:
                        from app.ai.whisper_local import LocalWhisperEngine
                        narration = LocalWhisperEngine().transcribe(self.audio_path)
                    return narration, None
                except Exception as fb_err:
                    return None, f"{e} (Fallback failed: {fb_err})"

        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(_do_transcribe)

        def _check_finished():
            if future.done():
                self.sync_progress.hide()
                self.transcribe_btn.setEnabled(True)
                self.transcribe_btn.setText("🎙️ 1. Transcribe Subtitles")
                narration, err = future.result()
                if err:
                    QMessageBox.warning(self, "Transcription Error", f"Transcription failed: {err}")
                elif narration:
                    self.narration = narration
                    status_str = "Verified" if getattr(narration, "is_verified", False) else (
                        "Degraded" if getattr(narration, "is_degraded", False) else "Completed"
                    )
                    self.summary_sync_lbl.setText(
                        f"✅ Transcribed & Aligned {len(narration.words)} words ({narration.duration_seconds:.1f}s) • {getattr(narration, 'alignment_status', 'COMPLETED')}"
                    )
                    self.status_badge.setText(f"• {len(narration.words)} Words ({status_str})")
            else:
                QTimer.singleShot(200, _check_finished)

        QTimer.singleShot(200, _check_finished)

    def _on_view_timestamps_json(self):
        """Views or opens the standardized narration timestamps JSON."""
        candidates = []
        if self.audio_path:
            ap = Path(self.audio_path)
            candidates.extend([ap.parent / "narration_timestamps.json", ap.with_suffix(".json")])
        if self._project_dir:
            candidates.append(self._project_dir / "narration_timestamps.json")

        found_json = None
        for c in candidates:
            if c.exists():
                found_json = c
                break

        if not found_json:
            if self.narration:
                # Prompt user to save standardized JSON
                save_path, _ = QFileDialog.getSaveFileName(
                    self, "Save Word Timestamps JSON", "narration_timestamps.json", "JSON Files (*.json)"
                )
                if save_path:
                    with open(save_path, "w", encoding="utf-8") as f:
                        f.write(self.narration.to_standard_json(indent=2))
                    QMessageBox.information(self, "Timestamps Saved", f"Saved to:\n{save_path}")
            else:
                QMessageBox.information(self, "No Timestamps", "No word timestamps currently loaded or generated.")
            return

        # Show JSON info
        try:
            import subprocess
            if os.name == "nt":
                os.startfile(str(found_json))
            else:
                subprocess.Popen(["xdg-open", str(found_json)])
        except Exception:
            QMessageBox.information(
                self, "Narration Timestamps JSON",
                f"Standardized JSON path:\n{found_json}\n\nContains {len(self.narration.words) if self.narration else 0} words."
            )

    # =========================================================================
    # AI IMAGE PACING
    # =========================================================================

    def _on_ai_auto_pace(self):
        if not self.image_files:
            # Try one last scan before giving up
            self._scan_images()
        if not self.image_files:
            QMessageBox.warning(
                self,
                "No Images Yet",
                "No images found in the project images folder.\n\n"
                "Click '🚀 Generate Images' to open Gemini with your connected account, "
                "generate the images there, and they'll appear here automatically.",
            )
            return

        if not self.audio_path or not Path(self.audio_path).exists():
            QMessageBox.warning(
                self,
                "No Audio",
                "Voiceover audio not loaded. Please complete Step 1 first.",
            )
            return

        total_images = len(self.image_files)

        # Determine audio duration
        duration = 60.0
        if self.narration and self.narration.duration_seconds > 0:
            duration = self.narration.duration_seconds
        elif self.audio_path and Path(self.audio_path).exists():
            try:
                import soundfile as sf
                info = sf.info(self.audio_path)
                duration = info.duration
            except Exception:
                pass

        existing_scenes = self.scenes or []
        scenes: List[VisualScene] = []

        # -----------------------------------------------------------------
        # Separate Thumbnail (Image 1) and Video Scenes (Image 2..N)
        # -----------------------------------------------------------------
        if any("thumb" in Path(f).name.lower() for f in self.image_files):
            thumb_cand = [f for f in self.image_files if "thumb" in Path(f).name.lower()][0]
            self.thumbnail_image_path = thumb_cand
            video_images = [f for f in self.image_files if f != thumb_cand]
        elif len(self.image_files) > 1:
            # Batch generation contract: Image 01 is always YouTube Thumbnail; story starts from Image 02
            self.thumbnail_image_path = self.image_files[0]
            video_images = self.image_files[1:]
        else:
            self.thumbnail_image_path = None
            video_images = self.image_files

        # Overlay thumbnail title typography if thumbnail image is present
        if self.thumbnail_image_path and Path(self.thumbnail_image_path).exists():
            try:
                from app.core.thumbnail_generator import ThumbnailGenerator
                hl_text = ""
                win = self.window()
                proj = getattr(win, "project", None)
                if proj and hasattr(proj, "state") and getattr(proj.state, "thumbnail_headline", ""):
                    hl_text = proj.state.thumbnail_headline
                elif proj and hasattr(proj, "state") and getattr(proj.state, "analysis", None):
                    hl_text = getattr(proj.state.analysis, "thumbnail_headline", "") or ""

                if not hl_text and self._project_dir:
                    sb_file = self._project_dir / "story_bible.txt"
                    if sb_file.exists():
                        for ln in sb_file.read_text(encoding="utf-8").splitlines():
                            if "VIRAL THUMBNAIL TEXT:" in ln:
                                hl_text = ln.split("VIRAL THUMBNAIL TEXT:", 1)[1].strip()
                                break

                if hl_text:
                    out_thumb = Path(self.thumbnail_image_path).parent / "thumbnail_rendered.jpg"
                    rendered_p = ThumbnailGenerator.overlay_headline_on_image(
                        image_path=self.thumbnail_image_path,
                        headline_text=hl_text,
                        output_path=str(out_thumb)
                    )
                    self.thumbnail_image_path = rendered_p
            except Exception as e:
                print(f"[Thumbnail] Notice rendering title overlay: {e}")

        total_video_images = len(video_images)
        if total_video_images == 0:
            video_images = self.image_files
            total_video_images = len(video_images)

        time_per_image = duration / float(max(1, total_video_images))

        for idx, img_path in enumerate(video_images):
            if idx < len(existing_scenes) and existing_scenes[idx].visual_subject:
                sc = existing_scenes[idx].model_copy(deep=True)
                sc.image_path = img_path
            else:
                start_t = round(idx * time_per_image, 2)
                end_t = (
                    round((idx + 1) * time_per_image, 2)
                    if idx < total_video_images - 1
                    else round(duration, 2)
                )
                sc = VisualScene(
                    scene_id=f"{idx+1:03d}",
                    start=start_t,
                    end=end_t,
                    duration=round(end_t - start_t, 2),
                    visual_subject=f"Scene {idx+1}: {Path(img_path).stem}",
                    narration_excerpt=f"Visual Beat {idx+1}",
                    image_path=img_path,
                    prompt=f"Scene {idx+1} matching {Path(img_path).name}",
                )
            scenes.append(sc)

        self.scenes = scenes
        self._populate_table()
        badge_thumb = " + 1 Thumbnail" if self.thumbnail_image_path else ""
        self.status_badge.setText(f"🟢 {len(scenes)} Scenes Synced{badge_thumb}")
        self.summary_sync_lbl.setText(
            f"✅ Paced {len(scenes)} video scenes across {duration:.1f}s "
            f"({time_per_image:.1f}s/image avg){badge_thumb}. Proceed to Deliverables!"
        )
        self.sync_completed.emit(self.scenes, self.audio_path, self.narration)

    def _populate_table(self):
        total_scenes = len(self.scenes)
        has_thumb = bool(self.thumbnail_image_path and Path(self.thumbnail_image_path).exists())
        row_offset = 1 if has_thumb else 0
        self.table.setRowCount(total_scenes + row_offset)

        if has_thumb:
            # Row 0: Dedicated YouTube Thumbnail cover
            it_num = QTableWidgetItem("🎯 THUMB")
            it_num.setTextAlignment(Qt.AlignCenter)
            it_num.setForeground(QColor("#F59E0B"))
            self.table.setItem(0, 0, it_num)

            thumb_lbl = QLabel()
            thumb_lbl.setFixedSize(50, 45)
            thumb_lbl.setAlignment(Qt.AlignCenter)
            pix = QPixmap(self.thumbnail_image_path)
            if not pix.isNull():
                thumb_lbl.setPixmap(pix.scaled(50, 45, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.table.setCellWidget(0, 1, thumb_lbl)

            fname = f"{Path(self.thumbnail_image_path).name} (YouTube Thumbnail Cover)"
            it_name = QTableWidgetItem(fname)
            it_name.setForeground(QColor("#FBBF24"))
            self.table.setItem(0, 2, it_name)

            it_st = QTableWidgetItem("Cover")
            it_st.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(0, 3, it_st)

            it_et = QTableWidgetItem("Cover")
            it_et.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(0, 4, it_et)

            it_dur = QTableWidgetItem("Standalone")
            it_dur.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(0, 5, it_dur)

        for s_idx, sc in enumerate(self.scenes):
            row = s_idx + row_offset
            it_num = QTableWidgetItem(f"#{sc.scene_id}")
            it_num.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, it_num)

            thumb_lbl = QLabel()
            thumb_lbl.setFixedSize(50, 45)
            thumb_lbl.setAlignment(Qt.AlignCenter)
            if sc.image_path and Path(sc.image_path).exists():
                pix = QPixmap(sc.image_path)
                if not pix.isNull():
                    thumb_lbl.setPixmap(pix.scaled(50, 45, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.table.setCellWidget(row, 1, thumb_lbl)

            fname = Path(sc.image_path).name if sc.image_path else "N/A"
            self.table.setItem(row, 2, QTableWidgetItem(fname))

            it_st = QTableWidgetItem(f"{sc.start:.2f}s")
            it_st.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, it_st)

            it_et = QTableWidgetItem(f"{sc.end:.2f}s")
            it_et.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, it_et)

            it_dur = QTableWidgetItem(f"{sc.duration:.2f}s")
            it_dur.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 5, it_dur)

    def _on_proceed_to_deliverables(self):
        self.navigate_to_deliverables.emit()
