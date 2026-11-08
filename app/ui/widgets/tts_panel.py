"""
TTS Voiceover Panel with Native Local Models (Kokoro & Piper) and Instant Voice Preview.
"""
from pathlib import Path
from typing import Optional, List, Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSlider, QProgressBar, QGroupBox, QFrame,
    QMessageBox, QScrollArea, QListView
)
from PySide6.QtCore import Qt, Signal, QThread, QObject, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from app.models.video_config import TTSConfig, TTSVoice, TTSEngineType
from app.models.timeline import NarrationData
from app.core.tts_engine import TTSEngine


from app.ui.widgets.custom_combo import PBComboBox


class TTSWorker(QThread):
    progress = Signal(float, str)
    finished = Signal(str, object)  # (audio_path, NarrationData)
    error = Signal(str)

    def __init__(
        self,
        text: str,
        output_audio_path: str,
        config: TTSConfig,
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        self.text = text
        self.output_audio_path = output_audio_path
        self.config = config

    def run(self):
        try:
            def cb(pct: float, msg: str):
                self.progress.emit(pct, msg)

            audio_path, narration = TTSEngine.synthesize_speech_sync(
                text=self.text,
                output_audio_path=self.output_audio_path,
                config=self.config,
                progress_callback=cb
            )
            self.finished.emit(audio_path, narration)
        except Exception as e:
            self.error.emit(str(e))


class VoicePreviewWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, voice_id: str, engine: TTSEngineType, out_path: str, parent=None):
        super().__init__(parent)
        self.voice_id = voice_id
        self.engine = engine
        self.out_path = out_path

    def run(self):
        try:
            res = TTSEngine.synthesize_preview_sync(self.voice_id, self.engine, self.out_path)
            self.finished.emit(res)
        except Exception as e:
            self.error.emit(str(e))


class TTSPanel(QWidget):
    """Local neural voiceover panel with Kokoro and Piper."""

    voiceover_generated = Signal(str, object)  # (audio_path, NarrationData)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_audio_path: Optional[str] = None
        self._current_narration: Optional[NarrationData] = None
        self._worker: Optional[TTSWorker] = None
        self._preview_worker: Optional[VoicePreviewWorker] = None
        self.story_text_provider = None
        self._story_text: str = ""

        # Media Player setup
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._player.positionChanged.connect(self._on_player_position_changed)
        self._player.durationChanged.connect(self._on_player_duration_changed)

        self._setup_ui()
        self._populate_languages()
        self._on_filter_changed()

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        # Outer ScrollArea to ensure it never gets cut off on smaller screens
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Header Info Card
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #0f172a; border: 1px solid #1e293b; border-radius: 6px; padding: 6px;")
        hf_layout = QVBoxLayout(header_frame)
        hf_layout.setSpacing(2)
        hf_layout.setContentsMargins(8, 6, 8, 6)

        header_lbl = QLabel("🎙️ Local Neural Voiceover Engine")
        header_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #38bdf8;")
        desc_lbl = QLabel("Synthesize studio-grade voiceover locally using Kokoro TTS (Ultra-Realistic) or Piper TTS (Fast Offline).")
        desc_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        desc_lbl.setWordWrap(True)

        hf_layout.addWidget(header_lbl)
        hf_layout.addWidget(desc_lbl)
        main_layout.addWidget(header_frame)

        # Main Settings Group
        settings_group = QGroupBox("Voice and Language Configuration")
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setSpacing(8)
        settings_layout.setContentsMargins(10, 12, 10, 10)

        # Row 1: Engine Selector
        r1 = QHBoxLayout()
        eng_lbl = QLabel("TTS Engine:")
        eng_lbl.setFixedWidth(95)
        self.engine_combo = PBComboBox()
        self.engine_combo.addItem("Kokoro TTS (Ultra-Realistic Neural)", TTSEngineType.KOKORO)
        self.engine_combo.addItem("Piper TTS (Fast Offline Neural)", TTSEngineType.PIPER)
        self.engine_combo.currentIndexChanged.connect(self._on_filter_changed)

        r1.addWidget(eng_lbl)
        r1.addWidget(self.engine_combo)
        settings_layout.addLayout(r1)

        # Row 2: Language Filter
        r2 = QHBoxLayout()
        lang_lbl = QLabel("Language:")
        lang_lbl.setFixedWidth(95)
        self.lang_combo = PBComboBox()
        self.lang_combo.currentIndexChanged.connect(self._on_filter_changed)

        r2.addWidget(lang_lbl)
        r2.addWidget(self.lang_combo)
        settings_layout.addLayout(r2)

        # Row 3: Voice Dropdown + Preview Button
        r3 = QHBoxLayout()
        voice_lbl = QLabel("Narrator Voice:")
        voice_lbl.setFixedWidth(95)
        self.voice_combo = PBComboBox()
        self.voice_combo.currentIndexChanged.connect(self._on_voice_selected)

        self.preview_voice_btn = QPushButton("🔊 Preview Voice")
        self.preview_voice_btn.setFixedHeight(30)
        self.preview_voice_btn.setStyleSheet("""
            QPushButton {
                background-color: #312e81;
                border: 1px solid #4f46e5;
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
                border-radius: 4px;
                padding: 0 10px;
            }
            QPushButton:hover {
                background-color: #3730a3;
            }
        """)
        self.preview_voice_btn.clicked.connect(self._on_preview_voice_clicked)

        r3.addWidget(voice_lbl)
        r3.addWidget(self.voice_combo)
        r3.addWidget(self.preview_voice_btn)
        settings_layout.addLayout(r3)

        # Voice Description Tag
        self.voice_desc_lbl = QLabel("")
        self.voice_desc_lbl.setStyleSheet("color: #60a5fa; font-size: 11px; font-style: italic; margin-left: 98px;")
        self.voice_desc_lbl.setWordWrap(True)
        settings_layout.addWidget(self.voice_desc_lbl)

        # Row 4: Speed Rate & Pitch
        sliders_box = QHBoxLayout()

        # Speed
        r_lbl = QLabel("Speed Rate:")
        r_lbl.setFixedWidth(75)
        self.rate_slider = QSlider(Qt.Orientation.Horizontal)
        self.rate_slider.setRange(-40, 40)
        self.rate_slider.setValue(0)
        self.rate_val_lbl = QLabel("0%")
        self.rate_val_lbl.setFixedWidth(34)
        self.rate_slider.valueChanged.connect(lambda v: self.rate_val_lbl.setText(f"{v:+d}%"))

        sliders_box.addWidget(r_lbl)
        sliders_box.addWidget(self.rate_slider)
        sliders_box.addWidget(self.rate_val_lbl)
        sliders_box.addSpacing(12)

        # Pitch
        p_lbl = QLabel("Pitch:")
        p_lbl.setFixedWidth(40)
        self.pitch_slider = QSlider(Qt.Orientation.Horizontal)
        self.pitch_slider.setRange(-20, 20)
        self.pitch_slider.setValue(0)
        self.pitch_val_lbl = QLabel("0Hz")
        self.pitch_val_lbl.setFixedWidth(34)
        self.pitch_slider.valueChanged.connect(lambda v: self.pitch_val_lbl.setText(f"{v:+d}Hz"))

        sliders_box.addWidget(p_lbl)
        sliders_box.addWidget(self.pitch_slider)
        sliders_box.addWidget(self.pitch_val_lbl)

        settings_layout.addLayout(sliders_box)
        main_layout.addWidget(settings_group)

        # Action Button
        self.gen_btn = QPushButton("🎙️ Generate Voiceover Audio")
        self.gen_btn.setFixedHeight(44)
        self.gen_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #38bdf8);
                color: white;
                font-weight: bold;
                font-size: 13px;
                border-radius: 6px;
                border: 1px solid #60a5fa;
            }
            QPushButton:hover {
                background: #1d4ed8;
            }
            QPushButton:disabled {
                background: #334155;
                color: #64748b;
                border: 1px solid #475569;
            }
        """)
        self.gen_btn.clicked.connect(self._on_generate_clicked)
        main_layout.addWidget(self.gen_btn)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #38bdf8;
                border-radius: 4px;
            }
        """)
        main_layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel("Ready to synthesize voiceover.")
        self.status_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        main_layout.addWidget(self.status_lbl)

        # Audio Player Preview Card
        self.player_frame = QFrame()
        self.player_frame.setStyleSheet("background-color: #0b0f19; border: 1px solid #1e293b; border-radius: 6px; padding: 6px;")
        self.player_frame.setVisible(False)

        pf_layout = QVBoxLayout(self.player_frame)
        pf_layout.setSpacing(4)

        player_hdr = QHBoxLayout()
        player_title = QLabel("▶️ Audio Playback Preview")
        player_title.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: bold;")
        player_hdr.addWidget(player_title)
        player_hdr.addStretch()

        self.audio_time_lbl = QLabel("0:00 / 0:00")
        self.audio_time_lbl.setStyleSheet("color: #94a3b8; font-size: 10px;")
        player_hdr.addWidget(self.audio_time_lbl)
        pf_layout.addLayout(player_hdr)

        controls_row = QHBoxLayout()
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setFixedSize(65, 26)
        self.play_btn.setStyleSheet("background-color: #059669; color: white; font-weight: bold; border-radius: 4px; font-size: 11px;")
        self.play_btn.clicked.connect(self._toggle_playback)
        controls_row.addWidget(self.play_btn)

        self.audio_slider = QSlider(Qt.Orientation.Horizontal)
        self.audio_slider.setRange(0, 100)
        self.audio_slider.sliderMoved.connect(self._on_seek_audio)
        controls_row.addWidget(self.audio_slider)
        pf_layout.addLayout(controls_row)

        main_layout.addWidget(self.player_frame)
        main_layout.addStretch()

        scroll.setWidget(container)
        root_layout.addWidget(scroll)

    def _populate_languages(self):
        self.lang_combo.blockSignals(True)
        self.lang_combo.clear()
        for code, name in TTSEngine.get_languages():
            self.lang_combo.addItem(name, code)
        self.lang_combo.blockSignals(False)

    def _on_filter_changed(self):
        engine = self.engine_combo.currentData() or TTSEngineType.KOKORO
        locale = self.lang_combo.currentData() or "all"

        voices = TTSEngine.get_voices(locale=locale, engine=engine)

        self.voice_combo.blockSignals(True)
        self.voice_combo.clear()

        if not voices:
            voices = TTSEngine.get_voices(locale=None, engine=engine)

        for v in voices:
            disp = f"{v.name} ({v.gender}) - {v.locale}"
            self.voice_combo.addItem(disp, v.voice_id)

        self.voice_combo.blockSignals(False)
        self._on_voice_selected()

    def _on_voice_selected(self):
        voice_id = self.voice_combo.currentData()
        if not voice_id:
            self.voice_desc_lbl.setText("")
            return

        for v in TTSEngine.get_voices():
            if v.voice_id == voice_id:
                self.voice_desc_lbl.setText(f"ℹ️ {v.description or v.language_name}")
                return

    def _on_preview_voice_clicked(self):
        voice_id = self.voice_combo.currentData()
        engine = self.engine_combo.currentData() or TTSEngineType.KOKORO
        if not voice_id:
            return

        temp_preview = Path.cwd() / "projects" / "temp" / "voice_preview.wav"
        temp_preview.parent.mkdir(parents=True, exist_ok=True)

        self.preview_voice_btn.setEnabled(False)
        self.status_lbl.setText("🔊 Generating voice sample...")
        self.status_lbl.setStyleSheet("color: #38bdf8; font-size: 11px;")

        self._preview_worker = VoicePreviewWorker(voice_id, engine, str(temp_preview), self)
        self._preview_worker.finished.connect(self._on_preview_finished)
        self._preview_worker.error.connect(self._on_preview_error)
        self._preview_worker.start()

    def _on_preview_finished(self, preview_path: str):
        self.preview_voice_btn.setEnabled(True)
        self.status_lbl.setText("▶ Playing voice preview...")
        self.status_lbl.setStyleSheet("color: #4ade80; font-size: 11px;")

        self._player.setSource(QUrl.fromLocalFile(preview_path))
        self.player_frame.setVisible(True)
        self._player.play()
        self.play_btn.setText("⏸ Pause")

    def _on_preview_error(self, err: str):
        self.preview_voice_btn.setEnabled(True)
        self.status_lbl.setText(f"❌ Preview error: {err}")
        self.status_lbl.setStyleSheet("color: #f87171; font-size: 11px;")

    def get_config(self) -> TTSConfig:
        voice_id = self.voice_combo.currentData() or "kokoro:af"
        engine = self.engine_combo.currentData() or TTSEngineType.KOKORO
        locale = self.lang_combo.currentData() or "en-US"
        return TTSConfig(
            engine=engine,
            voice_id=voice_id,
            language_locale=locale,
            rate_percentage=self.rate_slider.value(),
            pitch_percentage=self.pitch_slider.value()
        )

    def set_config(self, cfg: TTSConfig):
        e_idx = self.engine_combo.findData(cfg.engine)
        if e_idx >= 0:
            self.engine_combo.setCurrentIndex(e_idx)
        l_idx = self.lang_combo.findData(cfg.language_locale)
        if l_idx >= 0:
            self.lang_combo.setCurrentIndex(l_idx)
        self._on_filter_changed()
        v_idx = self.voice_combo.findData(cfg.voice_id)
        if v_idx >= 0:
            self.voice_combo.setCurrentIndex(v_idx)
        self.rate_slider.setValue(cfg.rate_percentage)
        self.pitch_slider.setValue(cfg.pitch_percentage)

    def set_story_text(self, text: str):
        """Sets story script text explicitly."""
        self._story_text = text

    def load_audio_narration(self, audio_path: str, narration: Optional[NarrationData] = None):
        """Loads existing voiceover audio and timestamp data into the player."""
        if not audio_path or not os.path.exists(audio_path):
            return
        self._current_audio_path = audio_path
        self._current_narration = narration
        self._player.setSource(QUrl.fromLocalFile(audio_path))
        self.player_frame.setVisible(True)
        self.play_btn.setText("▶ Play")
        dur_str = f"{narration.duration_seconds:.1f}s" if narration else ""
        words_str = f"{len(narration.words)} words, " if narration and narration.words else ""
        self.status_lbl.setText(f"✅ Voiceover loaded ({words_str}{dur_str})")
        self.status_lbl.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: bold;")

    def _on_generate_clicked(self):
        story_text = ""
        if self.story_text_provider:
            try:
                story_text = self.story_text_provider()
            except Exception:
                story_text = ""

        if not story_text and hasattr(self, "_story_text") and self._story_text:
            story_text = self._story_text

        win = self.window()
        if not story_text:
            if hasattr(win, "story_text_edit") and win.story_text_edit:
                story_text = win.story_text_edit.toPlainText().strip()
            elif hasattr(win, "project") and hasattr(win.project, "state"):
                story_text = win.project.state.story_raw_text.strip()

        if not story_text or not story_text.strip():
            QMessageBox.warning(
                self,
                "No Story Script",
                "Please enter or paste your story script in the 'Story Narration Script' editor on the left first."
            )
            return

        story_text = story_text.strip()

        # Ensure active project folder exists
        from app.core.project_manager import ProjectManager
        proj = getattr(win, "project", None)
        workspace_dir = getattr(win, "settings", None).workspace_directory if hasattr(win, "settings") and getattr(win, "settings") else "projects"
        proj_title = win.proj_name_input.text().strip() if hasattr(win, "proj_name_input") and win.proj_name_input.text().strip() else "Story_Project"

        if not proj or not proj.project_dir or not Path(proj.project_dir).exists():
            proj = ProjectManager.create_project(proj_title, workspace_dir, add_unique_id=True)
            if hasattr(win, "project"):
                win.project = proj
            if hasattr(win, "proj_name_input"):
                win.proj_name_input.setText(proj.name)

        proj_dir = Path(proj.project_dir)
        proj_dir.mkdir(parents=True, exist_ok=True)
        out_audio = str((proj_dir / "narration.wav").resolve())

        self.gen_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(10)
        self.status_lbl.setText("Generating local neural voiceover...")
        self.status_lbl.setStyleSheet("color: #38bdf8; font-size: 11px;")

        self._worker = TTSWorker(
            text=story_text,
            output_audio_path=out_audio,
            config=self.get_config(),
            parent=self
        )
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    def _on_worker_progress(self, pct: float, msg: str):
        self.progress_bar.setValue(int(pct))
        self.status_lbl.setText(msg)

    def _on_worker_finished(self, audio_path: str, narration: NarrationData):
        self._current_audio_path = audio_path
        self._current_narration = narration
        self.gen_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_lbl.setText(f"✅ Voiceover generated: {len(narration.words)} words ({narration.duration_seconds:.1f}s)")
        self.status_lbl.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: bold;")

        # Load audio into player
        self._player.setSource(QUrl.fromLocalFile(audio_path))
        self.player_frame.setVisible(True)
        self.play_btn.setText("▶ Play")

        self.voiceover_generated.emit(audio_path, narration)

    def _on_worker_error(self, err_msg: str):
        self.gen_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_lbl.setText(f"❌ Voiceover failed: {err_msg}")
        self.status_lbl.setStyleSheet("color: #f87171; font-size: 11px;")
        QMessageBox.critical(self, "Voiceover Generation Error", f"Failed to synthesize voiceover:\n{err_msg}")

    # =========================================================================
    # AUDIO PLAYER CONTROLS
    # =========================================================================

    def _toggle_playback(self):
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
            self.play_btn.setText("▶ Play")
        else:
            self._player.play()
            self.play_btn.setText("⏸ Pause")

    def _on_player_position_changed(self, pos_ms: int):
        dur_ms = self._player.duration()
        if dur_ms > 0:
            pct = int((pos_ms / dur_ms) * 100)
            self.audio_slider.blockSignals(True)
            self.audio_slider.setValue(pct)
            self.audio_slider.blockSignals(False)

            cur_sec = pos_ms / 1000.0
            tot_sec = dur_ms / 1000.0
            self.audio_time_lbl.setText(f"{int(cur_sec//60)}:{int(cur_sec%60):02d} / {int(tot_sec//60)}:{int(tot_sec%60):02d}")

    def _on_player_duration_changed(self, dur_ms: int):
        tot_sec = dur_ms / 1000.0
        self.audio_time_lbl.setText(f"0:00 / {int(tot_sec//60)}:{int(tot_sec%60):02d}")

    def _on_seek_audio(self, pct: int):
        dur_ms = self._player.duration()
        if dur_ms > 0:
            target_pos = int((pct / 100.0) * dur_ms)
            self._player.setPosition(target_pos)
