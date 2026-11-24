"""
Video Rendering and Export Panel.
Configures Ken Burns motion, aspect ratio, overlays, and orchestrates final MP4 generation.
Fully scrollable and responsive.
"""
import os
import sys
import subprocess
from pathlib import Path
from typing import Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSlider, QProgressBar, QGroupBox, QFileDialog,
    QMessageBox, QFrame, QSplitter, QScrollArea, QListView,
    QCheckBox, QLineEdit
)
from PySide6.QtCore import Qt, Signal

from app.models.video_config import (
    VideoRenderSettings,
    AspectRatio,
    MotionPreset,
    VideoOverlay,
    SubtitleConfig,
    SubtitlePreset,
    TransitionStyle
)
from app.models.scene import VisualScene
from app.models.timeline import NarrationData
from app.core.video_renderer import VideoRenderWorker, VideoRenderer
from app.core.timestamp_parser import TimestampParser
from app.core.thumbnail_generator import ThumbnailGenerator
from app.core.mobile_share_server import MobileShareServer, get_local_ip
from app.ui.widgets.custom_combo import PBComboBox
from app.ui.widgets.subtitle_editor import SubtitleEditor
from backend.pipeline.stage1_story_intelligence import is_valid_thumbnail_headline, extract_smart_fallback_headline


class RenderPanel(QWidget):
    """Orchestrates final video compilation, motion effects, subtitle burning, and export."""

    render_completed = Signal(str)  # output_video_path

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.settings = VideoRenderSettings()
        self.scenes: List[VisualScene] = []
        self.audio_path: Optional[str] = None
        self.narration: Optional[NarrationData] = None
        self._worker: Optional[VideoRenderWorker] = None
        self._output_video_path: Optional[str] = None

        self._setup_ui()

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Header Bar (Fixed slim height)
        hdr_bar = QFrame()
        hdr_bar.setFixedHeight(38)
        hdr_bar.setStyleSheet("background-color: #161616; border-bottom: 1px solid #282828; padding: 2px 10px;")
        hdr = QHBoxLayout(hdr_bar)
        hdr.setContentsMargins(6, 2, 6, 2)

        header_lbl = QLabel("<span style='color: #FF4B4B; font-weight: 800;'>04</span> &nbsp; <b style='color: #F5F5F5;'>FINAL RENDER STUDIO</b>")
        header_lbl.setStyleSheet("font-size: 13px; letter-spacing: 0.5px;")
        hdr.addWidget(header_lbl)
        hdr.addStretch()

        self.btn_manage_images = QPushButton("🖼️ Manage / Sync Images")
        self.btn_manage_images.setFixedHeight(26)
        self.btn_manage_images.setCursor(Qt.PointingHandCursor)
        self.btn_manage_images.setStyleSheet("""
            QPushButton {
                background-color: #222222;
                color: #D1D5DB;
                border: 1px solid #333333;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 10px;
                margin-right: 8px;
            }
            QPushButton:hover {
                background-color: #2A2A2A;
                border-color: #E53935;
                color: #FFFFFF;
            }
        """)
        self.btn_manage_images.clicked.connect(self._on_jump_to_images)
        hdr.addWidget(self.btn_manage_images)

        ffmpeg_ok = VideoRenderer.is_ffmpeg_available()
        ffmpeg_lbl = QLabel("✓ FFmpeg Ready" if ffmpeg_ok else "✗ FFmpeg Missing")
        ffmpeg_lbl.setStyleSheet("color: #FF4B4B; font-size: 11px; font-weight: bold;" if ffmpeg_ok else "color: #EF5350; font-size: 11px; font-weight: bold;")
        hdr.addWidget(ffmpeg_lbl)
        root_layout.addWidget(hdr_bar)

        # Splitter: Left = Video Motion & Render Summary, Right = Subtitle & Karaoke Studio
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # =====================================================================
        # LEFT PANE: Video Canvas, Camera Motion & Render Execution
        # =====================================================================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(8)

        # Video Settings Group
        vid_group = QGroupBox("Canvas and Camera Motion")
        vid_layout = QVBoxLayout(vid_group)
        vid_layout.setContentsMargins(10, 12, 10, 10)
        vid_layout.setSpacing(8)

        # Aspect Ratio
        r1 = QHBoxLayout()
        ar_lbl = QLabel("Aspect Ratio:")
        ar_lbl.setFixedWidth(95)
        self.ar_combo = PBComboBox()
        self.ar_combo.addItem("16:9 Landscape (YouTube / Desktop)", AspectRatio.LANDSCAPE_16_9)
        self.ar_combo.addItem("9:16 Vertical (TikTok / Shorts / Reels)", AspectRatio.VERTICAL_9_16)
        self.ar_combo.addItem("1:1 Square (Instagram / Social)", AspectRatio.SQUARE_1_1)
        self.ar_combo.currentIndexChanged.connect(self._on_settings_changed)
        r1.addWidget(ar_lbl)
        r1.addWidget(self.ar_combo)
        vid_layout.addLayout(r1)

        # Ken Burns Motion Toggle & Motion Presets
        r_motion_toggle = QHBoxLayout()
        self.chk_enable_ken_burns = QCheckBox("Enable Camera Motion / Ken Burns (Uncheck for shake-free still prints)")
        self.chk_enable_ken_burns.setChecked(False)  # Default OFF: shake-free static video preserves worn/torn paper edges
        self.chk_enable_ken_burns.setStyleSheet("color: #F5F5F5; font-size: 11px; font-weight: 700;")
        self.chk_enable_ken_burns.toggled.connect(self._on_motion_toggled)
        r_motion_toggle.addWidget(self.chk_enable_ken_burns)
        vid_layout.addLayout(r_motion_toggle)

        r2 = QHBoxLayout()
        m_lbl = QLabel("Motion Style:")
        m_lbl.setFixedWidth(95)
        self.motion_combo = PBComboBox()
        self.motion_combo.addItem("Static Still (No Movement / Shake-Free)", MotionPreset.STATIC)
        self.motion_combo.addItem("Subtle Alternating Ken Burns (Zoom In / Out)", MotionPreset.SUBTLE_ALTERNATING)
        self.motion_combo.addItem("Smooth Zoom In", MotionPreset.ZOOM_IN)
        self.motion_combo.addItem("Smooth Zoom Out", MotionPreset.ZOOM_OUT)
        self.motion_combo.addItem("Pan Left to Right", MotionPreset.PAN_LEFT_RIGHT)
        self.motion_combo.addItem("Pan Right to Left", MotionPreset.PAN_RIGHT_LEFT)
        self.motion_combo.setEnabled(False)  # Disabled when toggle is off
        self.motion_combo.currentIndexChanged.connect(self._on_settings_changed)
        r2.addWidget(m_lbl)
        r2.addWidget(self.motion_combo)
        vid_layout.addLayout(r2)

        # Zoom slider & Overlay
        r3 = QHBoxLayout()
        z_lbl = QLabel("Zoom Factor:")
        z_lbl.setFixedWidth(95)
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(5, 30)
        self.zoom_slider.setValue(15)
        self.zoom_val_lbl = QLabel("1.15x")
        self.zoom_val_lbl.setFixedWidth(38)
        self.zoom_slider.valueChanged.connect(lambda v: self.zoom_val_lbl.setText(f"{1.0 + v/100:.2f}x"))
        self.zoom_slider.valueChanged.connect(self._on_settings_changed)

        r3.addWidget(z_lbl)
        r3.addWidget(self.zoom_slider)
        r3.addWidget(self.zoom_val_lbl)
        vid_layout.addLayout(r3)

        r4 = QHBoxLayout()
        ov_lbl = QLabel("Visual Overlay:")
        ov_lbl.setFixedWidth(95)
        self.overlay_combo = PBComboBox()
        self.overlay_combo.addItem("Subtle Vignette", VideoOverlay.SUBTLE_VIGNETTE)
        self.overlay_combo.addItem("Letterbox (2.35:1 Cinematic)", VideoOverlay.LETTERBOX_CINEMATIC)
        self.overlay_combo.addItem("None (Clean)", VideoOverlay.NONE)
        self.overlay_combo.currentIndexChanged.connect(self._on_settings_changed)
        r4.addWidget(ov_lbl)
        r4.addWidget(self.overlay_combo)
        vid_layout.addLayout(r4)

        # Scene Transitions
        r5 = QHBoxLayout()
        tr_lbl = QLabel("Transitions:")
        tr_lbl.setFixedWidth(95)
        self.transition_combo = PBComboBox()
        self.transition_combo.addItem("🎲 Random Transitions (Dynamic Mix)", TransitionStyle.RANDOM)
        self.transition_combo.addItem("🎬 Cinematic Dip to Black", TransitionStyle.DIP_TO_BLACK)
        self.transition_combo.addItem("🌫️ Soft Dissolve / Crossfade", TransitionStyle.CROSSFADE)
        self.transition_combo.addItem("⚡ Direct Cut (No Transition)", TransitionStyle.CUT)
        self.transition_combo.currentIndexChanged.connect(self._on_settings_changed)
        r5.addWidget(tr_lbl)
        r5.addWidget(self.transition_combo)
        vid_layout.addLayout(r5)

        left_layout.addWidget(vid_group)

        # Render Summary and Execution Group
        summary_group = QGroupBox("Render Summary and Execution")
        summary_layout = QVBoxLayout(summary_group)
        summary_layout.setContentsMargins(12, 14, 12, 12)
        summary_layout.setSpacing(10)

        self.summary_text = QLabel("Preparing project assets...")
        self.summary_text.setStyleSheet("color: #cbd5e1; font-size: 12px; line-height: 1.4;")
        self.summary_text.setWordWrap(True)
        summary_layout.addWidget(self.summary_text)

        # Voiceover Audio Selection Row
        audio_row = QHBoxLayout()
        self.choose_audio_btn = QPushButton("🎙️ Choose Voiceover Audio...")
        self.choose_audio_btn.setFixedHeight(32)
        self.choose_audio_btn.setStyleSheet("""
            QPushButton {
                background-color: #222222;
                color: #F5F5F5;
                border: 1px solid #333333;
                border-radius: 6px;
                font-weight: 700;
                font-size: 11px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background-color: #292929;
                border-color: #E53935;
                color: #FFFFFF;
            }
        """)
        self.choose_audio_btn.clicked.connect(self._on_choose_audio_clicked)
        audio_row.addWidget(self.choose_audio_btn)

        self.audio_status_lbl = QLabel("No audio selected")
        self.audio_status_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        audio_row.addWidget(self.audio_status_lbl, 1)
        summary_layout.addLayout(audio_row)

        # Big Hero Render Button (FrameForge Red CTA)
        self.render_btn = QPushButton("🎬 PRODUCE CINEMATIC VIDEO")
        self.render_btn.setFixedHeight(46)
        self.render_btn.setCursor(Qt.PointingHandCursor)
        self.render_btn.setStyleSheet("""
            QPushButton {
                background-color: #E53935;
                color: #FFFFFF;
                font-weight: 800;
                font-size: 13px;
                letter-spacing: 0.5px;
                border-radius: 8px;
                border: 1px solid #FF4B4B;
            }
            QPushButton:hover {
                background-color: #FF4B4B;
                border-color: #FF7070;
            }
            QPushButton:pressed {
                background-color: #B71C1C;
            }
            QPushButton:disabled {
                background-color: #1F1F1F;
                color: #555555;
                border: 1px solid #282828;
            }
        """)
        self.render_btn.clicked.connect(self._on_start_render)
        summary_layout.addWidget(self.render_btn)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #181818;
                border-radius: 4px;
                border: 1px solid #282828;
            }
            QProgressBar::chunk {
                background-color: #E53935;
                border-radius: 3px;
            }
        """)
        summary_layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel("Ready to render.")
        self.status_lbl.setStyleSheet("color: #9AA4B2; font-size: 11px;")
        summary_layout.addWidget(self.status_lbl)

        # Prompts copy helper button
        btn_prompts_row = QHBoxLayout()
        self.copy_all_batch_prompts_btn = QPushButton("📋 Copy All Image Prompts")
        self.copy_all_batch_prompts_btn.setFixedHeight(28)
        self.copy_all_batch_prompts_btn.setStyleSheet("""
            QPushButton {
                background-color: #222222; color: #F5F5F5; font-size: 11px; font-weight: 700;
                border: 1px solid #333333; border-radius: 4px; padding: 0 12px;
            }
            QPushButton:hover { background-color: #292929; border-color: #E53935; color: #FFFFFF; }
        """)
        self.copy_all_batch_prompts_btn.clicked.connect(self._copy_all_batch_prompts)
        btn_prompts_row.addWidget(self.copy_all_batch_prompts_btn)
        btn_prompts_row.addStretch()
        summary_layout.addLayout(btn_prompts_row)

        # Post-render actions
        self.post_render_box = QHBoxLayout()

        self.open_vid_btn = QPushButton("▶️ Play Video")
        self.open_vid_btn.setFixedHeight(30)
        self.open_vid_btn.setStyleSheet("background-color: #E53935; color: #FFFFFF; font-weight: 700; border-radius: 4px; border: 1px solid #FF4B4B;")
        self.open_vid_btn.clicked.connect(self._on_play_video)
        self.open_vid_btn.setVisible(False)
        self.post_render_box.addWidget(self.open_vid_btn)

        self.open_folder_btn = QPushButton("📂 Open Folder")
        self.open_folder_btn.setFixedHeight(30)
        self.open_folder_btn.setStyleSheet("background-color: #222222; color: #F5F5F5; border-radius: 4px; border: 1px solid #333333;")
        self.open_folder_btn.clicked.connect(self._on_open_folder)
        self.open_folder_btn.setVisible(False)
        self.post_render_box.addWidget(self.open_folder_btn)

        self.qr_share_btn = QPushButton("📱 Phone Share (QR)")
        self.qr_share_btn.setFixedHeight(30)
        self.qr_share_btn.setStyleSheet("background-color: #222222; color: #4CAF50; border-radius: 4px; border: 1px solid #388E3C; font-weight: 600;")
        self.qr_share_btn.clicked.connect(self._on_qr_share)
        self.qr_share_btn.setVisible(False)
        self.post_render_box.addWidget(self.qr_share_btn)

        summary_layout.addLayout(self.post_render_box)
        left_layout.addWidget(summary_group)
        left_layout.addStretch()

        splitter.addWidget(left_widget)

        # =====================================================================
        # RIGHT PANE: Subtitle and Karaoke Styling Studio
        # =====================================================================
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(10)

        # Subtitle Editor Sub-widget
        self.sub_editor = SubtitleEditor()
        self.sub_editor.config_changed.connect(self._on_sub_config_changed)
        right_layout.addWidget(self.sub_editor)
        right_layout.addStretch()

        splitter.addWidget(right_widget)

        splitter.setSizes([540, 660])
        root_layout.addWidget(splitter, 1)

    def _on_jump_to_images(self):
        win = self.window()
        if win and hasattr(win, "_on_sidebar_nav_changed"):
            win._on_sidebar_nav_changed("images")

    def _on_choose_audio_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Voiceover Audio File",
            "",
            "Audio Files (*.mp3 *.wav *.m4a *.flac *.ogg *.aac);;All Files (*.*)"
        )
        if file_path:
            self.set_audio_file(file_path)

    def set_audio_file(self, file_path: str):
        p = Path(file_path)
        if not p.exists():
            return
        self.audio_path = str(p.resolve())

        # Auto-detect companion speech.json, narration_timestamps.json or timestamps.json in same dir
        loaded_narration = None
        candidates = [
            p.with_suffix(".json"),
            p.parent / "narration_timestamps.json",
            p.parent / "speech.json",
            p.parent / "timestamps.json",
            p.parent / "words.json"
        ]
        for c_path in candidates:
            if c_path.exists():
                try:
                    loaded_narration = TimestampParser.load_from_json(str(c_path))
                    break
                except Exception as ex:
                    print(f"Notice auto-detecting timestamps from {c_path}: {ex}")

        if loaded_narration:
            self.narration = loaded_narration
            self.audio_status_lbl.setText(f"✓ {p.name} ({loaded_narration.duration_seconds:.1f}s, {len(loaded_narration.words)} words)")
            self.audio_status_lbl.setStyleSheet("color: #FF4B4B; font-size: 11px; font-weight: bold;")
        elif self.narration and self.narration.words:
            self.audio_status_lbl.setText(f"✓ {p.name} ({self.narration.duration_seconds:.1f}s, {len(self.narration.words)} words)")
            self.audio_status_lbl.setStyleSheet("color: #FF4B4B; font-size: 11px; font-weight: bold;")
        else:
            win = self.window()
            if hasattr(win, "project") and win.project and getattr(win.project.state, "narration", None):
                self.narration = win.project.state.narration
                self.audio_status_lbl.setText(f"✓ {p.name} ({self.narration.duration_seconds:.1f}s, {len(self.narration.words)} words)")
                self.audio_status_lbl.setStyleSheet("color: #FF4B4B; font-size: 11px; font-weight: bold;")
            else:
                self.audio_status_lbl.setText(f"✓ {p.name} (Audio Loaded)")
                self.audio_status_lbl.setStyleSheet("color: #FF4B4B; font-size: 11px; font-weight: bold;")

        # Sync with main project state
        win = self.window()
        if hasattr(win, "project") and win.project:
            win.project.state.audio_file_path = self.audio_path
            if self.narration:
                win.project.state.narration = self.narration

        self._update_summary()

    def load_project_data(
        self,
        scenes: List[VisualScene],
        audio_path: Optional[str] = None,
        narration: Optional[NarrationData] = None
    ):
        self.scenes = scenes
        if narration:
            self.narration = narration
        if audio_path and Path(audio_path).exists():
            self.set_audio_file(audio_path)
        if not self.narration:
            win = self.window()
            if hasattr(win, "project") and win.project and getattr(win.project.state, "narration", None):
                self.narration = win.project.state.narration

        win = self.window()
        th_head = getattr(win.project.state, "thumbnail_headline", "") if (win and hasattr(win, "project") and win.project) else ""
        th_prompt = getattr(win.project.state, "thumbnail_prompt", "") if (win and hasattr(win, "project") and win.project) else ""

        if th_head:
            self.set_thumbnail_headline(th_head)
        elif hasattr(self, "thumb_headline_edit") and not self.thumb_headline_edit.text():
            hl = self._auto_extract_story_headline()
            if hl:
                self.set_thumbnail_headline(hl)

        if th_prompt:
            self.set_thumbnail_prompt(th_prompt)

        if hasattr(self, "thumb_widget"):
            self.thumb_widget.setVisible(True)
        self._update_summary()

    def _update_summary(self):
        total_scenes = len(self.scenes)
        matched_images = sum(1 for s in self.scenes if s.image_path and Path(s.image_path).exists())
        total_dur = sum(s.duration for s in self.scenes)
        if self.narration and self.narration.duration_seconds > 0:
            total_dur = max(total_dur, self.narration.duration_seconds)

        audio_status = "✅ Audio Loaded" if (self.audio_path and Path(self.audio_path).exists()) else "⚠️ No Audio"

        # Defensive Subtitle Preset String
        sub_cfg = getattr(self.settings, "subtitle_config", None)
        sub_preset = getattr(sub_cfg, "preset", SubtitlePreset.NONE) if sub_cfg else SubtitlePreset.NONE
        sub_preset_val = getattr(sub_preset, "value", str(sub_preset))
        sub_status = f"✅ Subtitles ({sub_preset_val})" if sub_preset != SubtitlePreset.NONE else "🚫 Subtitles Disabled"

        # Defensive Aspect Ratio Resolution
        ar = getattr(self.settings, "aspect_ratio", AspectRatio.LANDSCAPE_16_9)
        if isinstance(ar, AspectRatio):
            ar_val = ar.value
            ar_dims = ar.dimensions
        elif isinstance(ar, str):
            ar_val = ar
            if "9:16" in ar or "vertical" in ar.lower():
                ar_dims = (1080, 1920)
            elif "1:1" in ar or "square" in ar.lower():
                ar_dims = (1080, 1080)
            else:
                ar_dims = (1920, 1080)
        elif hasattr(ar, "dimensions"):
            ar_val = getattr(ar, "value", str(ar))
            ar_dims = ar.dimensions
        else:
            ar_val = "16:9"
            ar_dims = (1920, 1080)

        # Defensive Motion Preset String
        mp = getattr(self.settings, "motion_preset", MotionPreset.SUBTLE_ALTERNATING)
        mp_val = getattr(mp, "value", str(mp))

        text = (
            f"<b>Storyboard:</b> {total_scenes} scenes ({total_dur:.1f}s total duration)<br>"
            f"<b>Images:</b> {matched_images}/{total_scenes} bound (placeholders used for remaining)<br>"
            f"<b>Voiceover:</b> {audio_status}<br>"
            f"<b>Aspect Ratio:</b> {ar_val} ({ar_dims[0]}x{ar_dims[1]})<br>"
            f"<b>Subtitles:</b> {sub_status}<br>"
            f"<b>Motion:</b> {mp_val} ({self.settings.motion_intensity:.2f}x zoom)"
        )
        self.summary_text.setText(text)

    def _on_motion_toggled(self, checked: bool):
        self.motion_combo.setEnabled(checked)
        self.zoom_slider.setEnabled(checked)
        self._on_settings_changed()

    def _auto_extract_story_headline(self) -> str:
        win = self.window()
        # 1. Use Groq AI generated thumbnail headline if present and valid
        if win and hasattr(win, "project") and getattr(win.project, "state", None):
            th_head = getattr(win.project.state, "thumbnail_headline", None)
            if th_head and is_valid_thumbnail_headline(th_head):
                return th_head.strip().upper()

        story_text = ""
        if win:
            if hasattr(win, "story_text_edit"):
                story_text = win.story_text_edit.toPlainText().strip()
            if not story_text and hasattr(win, "project") and getattr(win.project, "state", None):
                story_text = getattr(win.project.state, "story_raw_text", "").strip()

        if story_text:
            lines = [l.strip() for l in story_text.splitlines() if l.strip()]
            for l in lines:
                if l.startswith("#"):
                    cand = l.lstrip("#").strip().upper()
                    if is_valid_thumbnail_headline(cand):
                        return cand
                if l.lower().startswith("title:"):
                    cand = l.split(":", 1)[1].strip().upper()
                    if is_valid_thumbnail_headline(cand):
                        return cand

            # Smart non-stopword keyword extraction (NEVER takes raw sentence fragments like 'HOW DID A')
            fallback = extract_smart_fallback_headline(story_text)
            if is_valid_thumbnail_headline(fallback):
                return fallback

        if win and hasattr(win, "proj_name_input"):
            p_name = win.proj_name_input.text().strip().replace("_", " ")
            if p_name and p_name.lower() not in ("untitled project", "new project"):
                if is_valid_thumbnail_headline(p_name):
                    return p_name.upper()

        return "FORGOTTEN CONQUEST"

    def _on_settings_changed(self):
        self.settings.aspect_ratio = self.ar_combo.currentData() or AspectRatio.LANDSCAPE_16_9
        if not hasattr(self, "chk_enable_ken_burns") or not self.chk_enable_ken_burns.isChecked():
            self.settings.motion_preset = MotionPreset.STATIC
        else:
            self.settings.motion_preset = self.motion_combo.currentData() or MotionPreset.SUBTLE_ALTERNATING
        self.settings.motion_intensity = round(1.0 + self.zoom_slider.value() / 100.0, 2)
        self.settings.video_overlay = self.overlay_combo.currentData() or VideoOverlay.SUBTLE_VIGNETTE
        if hasattr(self, "transition_combo"):
            self.settings.transition_style = self.transition_combo.currentData() or TransitionStyle.RANDOM
        self._update_summary()

    def _on_sub_config_changed(self, cfg: SubtitleConfig):
        self.settings.subtitle_config = cfg
        self._update_summary()

    def _on_start_render(self):
        # If scenes list is empty (e.g. fresh launch or project re-opened), auto-generate scenes from images
        if not self.scenes:
            win = self.window()
            img_panel = getattr(win, "tab3_images", None)
            folder_to_use = None
            if img_panel and getattr(img_panel, "images_folder", None) and Path(img_panel.images_folder).exists():
                folder_to_use = img_panel.images_folder
            else:
                folder_to_use = QFileDialog.getExistingDirectory(self, "Select Generated Images Folder")
                if folder_to_use and img_panel:
                    img_panel.images_folder = folder_to_use
                    img_panel.folder_path_lbl.setText(f"📁 Folder: {Path(folder_to_use).name}")

            if folder_to_use and Path(folder_to_use).exists():
                img_exts = (".png", ".jpg", ".jpeg", ".webp")
                raw_files = [f for f in Path(folder_to_use).iterdir() if f.suffix.lower() in img_exts]
                from app.core.asset_manager import natural_sort_key
                img_files = sorted([str(f.resolve()) for f in raw_files], key=lambda x: natural_sort_key(Path(x)))

                if img_files:
                    total_dur = 60.0
                    if self.narration and self.narration.duration_seconds > 0:
                        total_dur = self.narration.duration_seconds
                    elif self.audio_path and Path(self.audio_path).exists():
                        try:
                            probe_res = subprocess.run(
                                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(Path(self.audio_path).resolve())],
                                capture_output=True, text=True
                            )
                            total_dur = float(probe_res.stdout.strip())
                        except Exception:
                            total_dur = float(len(img_files) * 5.0)

                    story_img_files = img_files

                    dur_each = round(total_dur / len(story_img_files), 2) if story_img_files else 5.0
                    dur_each = max(0.5, dur_each)
                    auto_scenes = []
                    cur_t = 0.0
                    for idx, img_path in enumerate(story_img_files):
                        end_t = round(cur_t + dur_each, 2)
                        auto_scenes.append(VisualScene(
                            scene_id=f"{idx+1:03d}",
                            start=cur_t,
                            end=end_t,
                            duration=round(end_t - cur_t, 2),
                            visual_subject=Path(img_path).stem,
                            image_path=img_path
                        ))
                        cur_t = end_t
                    self.scenes = auto_scenes
                    if img_panel:
                        img_panel.load_scenes(auto_scenes, folder_to_use)
                    if hasattr(win, "project") and win.project:
                        win.project.state.scenes = auto_scenes
                    self._update_summary()

        if not self.scenes:
            QMessageBox.warning(self, "No Images or Storyboard", "Please select an image folder or generate a storyboard first.")
            return

        # Enforce human checkpoint: A scene does not render until its clip is approved (or its image fallback is approved)
        unapproved = []
        for sc in self.scenes:
            if getattr(sc, "is_video", False) and not getattr(sc, "is_video_fallback_to_image", False):
                if not getattr(sc, "video_approved", False) and not getattr(sc, "is_approved", False):
                    unapproved.append(f"Scene #{sc.scene_id} (Video clip)")
            else:
                if not getattr(sc, "is_approved", False) and not getattr(sc, "image_path", None):
                    unapproved.append(f"Scene #{sc.scene_id} (Image fallback/still)")

        if unapproved:
            msg = (
                f"The following {len(unapproved)} scene(s) have not been approved at the checkpoint:\n"
                + "\n".join(unapproved[:5])
                + ("\n..." if len(unapproved) > 5 else "")
                + "\n\nA scene does not render until its clip is approved (or its image fallback is approved)."
            )
            reply = QMessageBox.question(
                self,
                "Unapproved Scenes at Checkpoint",
                f"{msg}\n\nDo you want to approve all scenes now and proceed with rendering?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                for sc in self.scenes:
                    sc.is_approved = True
                    sc.video_approved = True
            else:
                return

        if not self.audio_path or not Path(self.audio_path).exists():
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select Voiceover Audio File (e.g. speech.mp3 / voiceover.wav)",
                "",
                "Audio Files (*.mp3 *.wav *.m4a *.flac *.ogg *.aac);;All Files (*.*)"
            )
            if file_path and Path(file_path).exists():
                self.set_audio_file(file_path)
            else:
                QMessageBox.warning(self, "No Voiceover Audio", "Please select a voiceover audio file to render the video.")
                return

        win = self.window()
        project = getattr(win, "project", None)
        out_dir = Path(project.project_dir) if project and getattr(project, "project_dir", None) else Path.cwd() / "projects" / "output"
        renders_dir = out_dir / "renders"
        renders_dir.mkdir(parents=True, exist_ok=True)

        # Always synchronize latest subtitle config directly from subtitle editor widget
        if hasattr(self, "sub_editor") and hasattr(self.sub_editor, "config"):
            self.settings.subtitle_config = self.sub_editor.config

        # Defensive: guarantee narration exists for subtitle burning
        if not self.narration or not self.narration.words:
            if project and getattr(project.state, "narration", None):
                self.narration = project.state.narration

        if (not self.narration or not self.narration.words) and self.scenes:
            from app.core.subtitle_engine import SubtitleEngine
            self.narration = SubtitleEngine.synthesize_narration_from_scenes(self.scenes)

        # Name file clearly with project name and subtitle status
        sub_cfg = getattr(self.settings, "subtitle_config", None)
        has_subtitles = sub_cfg and getattr(sub_cfg, "preset", SubtitlePreset.NONE) != SubtitlePreset.NONE
        proj_name = getattr(project, "name", "project") if project else "project"
        suffix = "_subtitles.mp4" if has_subtitles else "_nosubtitles.mp4"
        output_file = str((renders_dir / f"{proj_name}{suffix}").resolve())

        # Authoritatively verify/re-bind scene images if an images directory is available
        img_dir_cand = None
        if project and getattr(project, "project_dir", None):
            p_img = Path(project.project_dir) / "images"
            if p_img.exists():
                img_dir_cand = str(p_img.resolve())
        elif hasattr(self, "images_folder") and self.images_folder and Path(self.images_folder).exists():
            img_dir_cand = str(Path(self.images_folder).resolve())

        if img_dir_cand:
            from app.core.asset_manager import AssetManager
            self.scenes, _ = AssetManager.auto_bind_images_to_scenes(self.scenes, img_dir_cand)

        self.render_btn.setEnabled(False)
        self.progress_bar.setValue(5)
        self.status_lbl.setText("Starting FFmpeg video compilation...")
        self.status_lbl.setStyleSheet("color: #F5F5F5; font-size: 11px;")
        self.open_vid_btn.setVisible(False)
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
        self.progress_bar.setValue(int(pct))
        self.status_lbl.setText(msg)

    def _on_worker_finished(self, out_path: str):
        self._output_video_path = out_path
        self.render_btn.setEnabled(True)
        self.progress_bar.setValue(100)
        self.status_lbl.setText(f"✓ RENDER COMPLETE! Saved to {Path(out_path).name}")
        self.status_lbl.setStyleSheet("color: #FF4B4B; font-size: 12px; font-weight: bold;")

        # Keep a copy as final_video.mp4 for convenience
        try:
            import shutil
            final_copy = Path(out_path).parent / "final_video.mp4"
            if Path(out_path).resolve() != final_copy.resolve():
                shutil.copy2(out_path, final_copy)
        except Exception:
            pass

        self.open_vid_btn.setVisible(True)
        self.open_folder_btn.setVisible(True)
        self.qr_share_btn.setVisible(True)
        self.render_completed.emit(out_path)

    def set_thumbnail_headline(self, text: str):
        if hasattr(self, "thumb_headline_edit") and text:
            clean = text.strip().upper()
            if is_valid_thumbnail_headline(clean):
                self.thumb_headline_edit.setText(clean)
                cur_p = self.get_thumbnail_prompt()
                if not cur_p or clean not in cur_p:
                    win = self.window()
                    sid = getattr(win.project.state, "style_preset_id", "3d_red_blue_stickman") if (win and hasattr(win, "project") and win.project) else "3d_red_blue_stickman"
                    from app.core.thumbnail_prompt_builder import build_viral_thumbnail_prompt
                    new_p = build_viral_thumbnail_prompt(headline=clean, style_id=sid)
                    self.set_thumbnail_prompt(new_p)
                    if win and hasattr(win, "project") and win.project:
                        win.project.state.thumbnail_headline = clean
                        win.project.state.thumbnail_prompt = new_p

    def get_thumbnail_prompt(self) -> str:
        if not hasattr(self, "thumb_prompt_edit"):
            return ""
        if hasattr(self.thumb_prompt_edit, "toPlainText"):
            return self.thumb_prompt_edit.toPlainText().strip()
        return self.thumb_prompt_edit.text().strip()

    def set_thumbnail_prompt(self, prompt: str):
        if hasattr(self, "thumb_prompt_edit") and prompt:
            if hasattr(self.thumb_prompt_edit, "setPlainText"):
                self.thumb_prompt_edit.setPlainText(prompt.strip())
            else:
                self.thumb_prompt_edit.setText(prompt.strip())

    def _on_thumb_headline_edited(self, text: str):
        clean = text.strip().upper()
        if clean:
            win = self.window()
            sid = getattr(win.project.state, "style_preset_id", "3d_red_blue_stickman") if (win and hasattr(win, "project") and win.project) else "3d_red_blue_stickman"
            from app.core.thumbnail_prompt_builder import build_viral_thumbnail_prompt
            new_p = build_viral_thumbnail_prompt(headline=clean, style_id=sid)
            self.set_thumbnail_prompt(new_p)
            if win and hasattr(win, "project") and win.project:
                win.project.state.thumbnail_headline = clean
                win.project.state.thumbnail_prompt = new_p

    def _on_thumb_prompt_edited(self, text: Optional[str] = None):
        txt = self.get_thumbnail_prompt()
        win = self.window()
        if win and hasattr(win, "project") and win.project:
            win.project.state.thumbnail_prompt = txt

    def _copy_thumbnail_prompt(self):
        txt = self.get_thumbnail_prompt()
        if txt:
            QApplication.clipboard().setText(txt)
            self.copy_thumb_prompt_btn.setText("✓ Copied!")
            QTimer.singleShot(2000, lambda: self.copy_thumb_prompt_btn.setText("📋 Copy Thumb Prompt"))

    def _copy_all_batch_prompts(self):
        win = self.window()
        scenes = self.scenes
        if not scenes and win and hasattr(win, "project") and win.project and getattr(win.project.state, "scenes", None):
            scenes = win.project.state.scenes
        if not scenes:
            QMessageBox.warning(self, "No Scenes", "No storyboard scenes available to copy.")
            return
        from app.core.export import StoryboardExporter, copy_to_system_clipboard
        payload = StoryboardExporter.export_to_prompts_only(scenes)
        copy_to_system_clipboard(payload)
        if hasattr(self, "copy_all_batch_prompts_btn"):
            self.copy_all_batch_prompts_btn.setText("✓ All Prompts Copied!")
            QTimer.singleShot(2500, lambda: self.copy_all_batch_prompts_btn.setText("📋 Copy All Prompts"))

    def _on_generate_thumbnail(self):
        if not self._output_video_path or not Path(self._output_video_path).exists():
            return
        out_vid = Path(self._output_video_path)
        thumb_out = out_vid.parent / f"{out_vid.stem}_THUMBNAIL.jpg"

        # 1. Look for dedicated thumbnail image from scene sync panel (Image 1)
        bg_img = None
        win = self.window()
        if hasattr(win, "scene_sync_panel") and getattr(win.scene_sync_panel, "thumbnail_image_path", None):
            cand = win.scene_sync_panel.thumbnail_image_path
            if cand and Path(cand).exists():
                bg_img = str(Path(cand).resolve())

        # 2. Look for dedicated thumbnail files (e.g. thumbnail.png, thumb.jpg, 000.jpg, 000_thumbnail.png, 001.png)
        project = getattr(win, "project", None)
        candidate_dirs = [out_vid.parent]
        if project and getattr(project, "project_dir", None):
            candidate_dirs.append(Path(project.project_dir))
            candidate_dirs.append(Path(project.project_dir) / "images")

        thumb_names = ["000_thumbnail", "thumbnail", "thumb", "000", "cover", "thumb_gemini", "000_thumb"]
        for cdir in candidate_dirs:
            if cdir.exists():
                for ext in [".png", ".jpg", ".jpeg", ".webp"]:
                    for tname in thumb_names:
                        cfile = cdir / f"{tname}{ext}"
                        if cfile.exists():
                            bg_img = str(cfile.resolve())
                            break
                    if bg_img:
                        break
            if bg_img:
                break

        # Fallback: find best background image from generated scenes
        if not bg_img:
            for sc in self.scenes:
                if sc.image_path and Path(sc.image_path).exists():
                    bg_img = sc.image_path
                    break
        if not bg_img:
            bg_img = str(out_vid.parent / "001.jpg")

        # Extract clean headline from Groq AI or script text (never generic Untitled_Project or questions like 'HOW DID A')
        custom_txt = self.thumb_headline_edit.text().strip() if hasattr(self, "thumb_headline_edit") else ""
        if custom_txt and is_valid_thumbnail_headline(custom_txt):
            title_text = custom_txt.upper()
        else:
            title_text = self._auto_extract_story_headline()

        res = ThumbnailGenerator.generate_thumbnail(
            background_image_path=bg_img,
            headline_text=title_text,
            output_path=str(thumb_out)
        )
        if sys.platform == "win32":
            os.startfile(res)
        QMessageBox.information(self, "Thumbnail Created", f"Viral YouTube thumbnail created successfully:\n{res}")

    def _on_qr_share(self):
        if not self._output_video_path or not Path(self._output_video_path).exists():
            return
        try:
            from app.ui.dialogs.qr_code_dialog import QRCodeDialog
            url, _ = MobileShareServer.start(self._output_video_path)
            dlg = QRCodeDialog(url, Path(self._output_video_path).name, self)
            dlg.exec()
        except Exception as e:
            print(f"[RenderPanel] QR share dialog error: {e}")
            url, _ = MobileShareServer.start(self._output_video_path)
            QMessageBox.information(self, "Mobile Wi-Fi Share Active", f"Open in your phone's browser:\n\n{url}")

    def _on_worker_error(self, err: str):
        self.render_btn.setEnabled(True)
        self.status_lbl.setText(f"❌ Render failed: {err}")
        self.status_lbl.setStyleSheet("color: #f87171; font-size: 11px;")
        QMessageBox.critical(self, "Video Rendering Error", f"Video rendering encountered an error:\n{err}")

    def _on_play_video(self):
        if self._output_video_path and Path(self._output_video_path).exists():
            if sys.platform == "win32":
                os.startfile(self._output_video_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", self._output_video_path])
            else:
                subprocess.Popen(["xdg-open", self._output_video_path])

    def _on_open_folder(self):
        if self._output_video_path and Path(self._output_video_path).exists():
            folder = str(Path(self._output_video_path).parent)
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
