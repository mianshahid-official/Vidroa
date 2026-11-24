"""
Audio Narration & Whisper Transcription Panel for PromptBeast.
Allows loading an audio file, importing pre-generated timestamps JSON, or transcribing
audio directly using Groq Whisper or Local Faster-Whisper to extract word-level timestamps.
"""
import json
from pathlib import Path
from typing import Optional, List

from PySide6.QtCore import Qt, Signal, QThread, QObject, QUrl
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QProgressBar, QGroupBox, QFrame,
    QMessageBox, QScrollArea, QFileDialog, QSlider, QSizePolicy
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from app.models.timeline import NarrationData, WordTimestamp
from app.ai.groq_engine import GroqEngine


class TranscriptionWorker(QThread):
    progress = Signal(float, str)
    finished = Signal(str, object, str)  # (audio_path, NarrationData, transcript_text)
    error = Signal(str)

    def __init__(
        self,
        audio_path: str,
        engine_type: str = "groq",  # "groq" or "local"
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        self.audio_path = audio_path
        self.engine_type = engine_type

    def run(self):
        try:
            self.progress.emit(20.0, "Initializing transcription engine...")
            groq_eng = GroqEngine()

            if self.engine_type == "local":
                self.progress.emit(40.0, "Transcribing with Local Faster-Whisper (CPU)...")
                narration = groq_eng.transcribe_audio_local(self.audio_path)
            else:
                self.progress.emit(40.0, "Transcribing with Groq Whisper (Ultra-Fast)...")
                narration = groq_eng.transcribe_audio_groq(self.audio_path)

            self.progress.emit(90.0, "Formatting word-level timestamp boundaries...")
            full_text = " ".join(w.word for w in narration.words)

            self.progress.emit(100.0, "Transcription & timestamp alignment complete!")
            self.finished.emit(self.audio_path, narration, full_text)
        except Exception as e:
            self.error.emit(str(e))


class AudioTranscriptionPanel(QWidget):
    """
    Panel for loading voiceover audio and extracting word-level timestamps via Whisper.
    Replaces TTSPanel in Tab 1 for audio-first workflows.
    """

    audio_ready = Signal(str, object, str)  # (audio_path, NarrationData, story_text)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_audio_path: Optional[str] = None
        self._current_narration: Optional[NarrationData] = None
        self._worker: Optional[TranscriptionWorker] = None

        # Media Player
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._player.positionChanged.connect(self._on_player_position_changed)
        self._player.durationChanged.connect(self._on_player_duration_changed)

        self._setup_ui()

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(8)

        card_frame = QFrame()
        card_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(14, 22, 17, 0.95);
                border: 1px solid rgba(163, 255, 18, 0.22);
                border-radius: 8px;
                padding: 10px;
            }
        """)
        main_layout = QVBoxLayout(card_frame)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # 1. Row: Audio Selection & Status
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        self.browse_audio_btn = QPushButton("📂 Select Voiceover Audio (.wav, .mp3, .m4a)")
        self.browse_audio_btn.setFixedHeight(32)
        self.browse_audio_btn.setCursor(Qt.PointingHandCursor)
        self.browse_audio_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(27, 41, 31, 0.85);
                color: #F0F5F0;
                border: 1px solid rgba(163, 255, 18, 0.35);
                border-radius: 6px;
                padding: 0 14px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(40, 60, 45, 0.95);
                border-color: #A3FF12;
                color: #A3FF12;
            }
        """)
        self.browse_audio_btn.clicked.connect(self._on_browse_audio)
        row1.addWidget(self.browse_audio_btn)

        self.audio_status_lbl = QLabel("No audio loaded")
        self.audio_status_lbl.setStyleSheet("color: #89978D; font-size: 11px; font-weight: 600;")
        row1.addWidget(self.audio_status_lbl)

        row1.addStretch()

        self.import_json_btn = QPushButton("📄 Import Timestamps JSON")
        self.import_json_btn.setFixedHeight(28)
        self.import_json_btn.setCursor(Qt.PointingHandCursor)
        self.import_json_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(20, 30, 24, 0.7);
                color: #B1BDB3;
                border: 1px solid rgba(163, 255, 18, 0.18);
                border-radius: 5px;
                padding: 0 10px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: rgba(30, 48, 35, 0.85);
                color: #A3FF12;
                border-color: #A3FF12;
            }
        """)
        self.import_json_btn.clicked.connect(self._on_import_timestamps_json)
        row1.addWidget(self.import_json_btn)

        main_layout.addLayout(row1)

        # 2. Row: Media Player UI
        self.player_frame = QFrame()
        self.player_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(10, 16, 12, 0.90);
                border: 1px solid rgba(163, 255, 18, 0.14);
                border-radius: 6px;
                padding: 4px;
            }
        """)
        pf_layout = QHBoxLayout(self.player_frame)
        pf_layout.setContentsMargins(8, 2, 8, 2)
        pf_layout.setSpacing(8)

        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setFixedSize(65, 26)
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: #081009;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
                border: 1px solid #34D399;
            }
            QPushButton:hover {
                background-color: #A3FF12;
                color: #081009;
            }
            QPushButton:disabled {
                background-color: rgba(27, 41, 31, 0.5);
                color: #667269;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
        """)
        self.play_btn.clicked.connect(self._toggle_playback)
        self.play_btn.setEnabled(False)
        pf_layout.addWidget(self.play_btn)

        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #111B14;
                height: 6px;
                border-radius: 3px;
                border: 1px solid rgba(163, 255, 18, 0.15);
            }
            QSlider::sub-page:horizontal {
                background: #10B981;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #A3FF12;
                width: 14px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 7px;
            }
        """)
        self.seek_slider.sliderMoved.connect(self._on_seek)
        pf_layout.addWidget(self.seek_slider)

        self.time_lbl = QLabel("00:00 / 00:00")
        self.time_lbl.setStyleSheet("color: #B1BDB3; font-family: monospace; font-size: 11px;")
        pf_layout.addWidget(self.time_lbl)

        main_layout.addWidget(self.player_frame)

        # 3. Row: Whisper Engine & Transcribe Button
        row3 = QHBoxLayout()
        row3.setSpacing(8)

        w_lbl = QLabel("Whisper Engine:")
        w_lbl.setStyleSheet("color: #C0CDC2; font-size: 11px; font-weight: 600;")
        row3.addWidget(w_lbl)

        self.engine_combo = QComboBox()
        self.engine_combo.addItem("⚡ Groq Whisper-Large-V3 (Cloud ~2s)", "groq")
        self.engine_combo.addItem("💻 Faster-Whisper (100% Offline Local)", "local")
        self.engine_combo.setFixedHeight(28)
        self.engine_combo.setStyleSheet("""
            QComboBox {
                background-color: rgba(20, 32, 24, 0.85);
                color: #F0F5F0;
                border: 1px solid rgba(163, 255, 18, 0.25);
                border-radius: 5px;
                padding: 2px 8px;
                font-size: 11px;
            }
            QComboBox:hover {
                border-color: #A3FF12;
            }
        """)
        row3.addWidget(self.engine_combo)

        self.transcribe_btn = QPushButton("⚡ Transcribe & Align Words")
        self.transcribe_btn.setFixedHeight(28)
        self.transcribe_btn.setCursor(Qt.PointingHandCursor)
        self.transcribe_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #059669);
                color: #FFFFFF;
                font-weight: 700;
                font-size: 11px;
                border-radius: 5px;
                border: 1px solid #34D399;
                padding: 0 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #A3FF12, stop:1 #10B981);
                color: #081009;
                border-color: #A3FF12;
            }
            QPushButton:disabled {
                background-color: rgba(27, 41, 31, 0.5);
                color: #667269;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
        """)
        self.transcribe_btn.setEnabled(False)
        self.transcribe_btn.clicked.connect(self._on_start_transcription)
        row3.addWidget(self.transcribe_btn)

        row3.addStretch()
        main_layout.addLayout(row3)

        # 4. Progress bar & Status
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: rgba(13, 21, 16, 0.9);
                border: 1px solid rgba(163, 255, 18, 0.2);
                border-radius: 3px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #A3FF12;
                border-radius: 2px;
            }
        """)
        main_layout.addWidget(self.progress_bar)

        self.ts_status_lbl = QLabel("Waiting for audio file...")
        self.ts_status_lbl.setStyleSheet("color: #89978D; font-size: 10px;")
        main_layout.addWidget(self.ts_status_lbl)

        root_layout.addWidget(card_frame)

    # =========================================================================
    # AUDIO FILE HANDLING
    # =========================================================================

    def _on_browse_audio(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Voiceover Audio File",
            "",
            "Audio Files (*.wav *.mp3 *.m4a *.flac *.ogg *.aac);;All Files (*.*)"
        )
        if file_path:
            self.load_audio(file_path)


    def load_audio_narration(self, file_path: str, narration: Optional[NarrationData] = None):
        self.load_audio(file_path, narration)

    def set_story_text(self, text: str):
        pass

    def load_audio(self, file_path: str, narration: Optional[NarrationData] = None):
        p = Path(file_path)
        if not p.exists():
            return

        self._current_audio_path = str(p.resolve())
        self.audio_status_lbl.setText(f"✅ {p.name}")
        self.audio_status_lbl.setStyleSheet("color: #4ade80; font-size: 12px; font-weight: bold;")

        # Setup Player
        self._player.setSource(QUrl.fromLocalFile(self._current_audio_path))
        self.play_btn.setEnabled(True)
        self.transcribe_btn.setEnabled(True)

        full_text = ""
        # Auto-detect companion speech.json or timestamps.json if present
        if not narration:
            candidates = [
                p.with_suffix(".json"),
                p.parent / "speech.json",
                p.parent / "timestamps.json",
                p.parent / "words.json"
            ]
            for c_path in candidates:
                if c_path.exists():
                    try:
                        from app.core.timestamp_parser import TimestampParser
                        narration = TimestampParser.load_from_json(str(c_path))
                        if narration and narration.words:
                            full_text = " ".join(w.word for w in narration.words)
                        break
                    except Exception as ex:
                        print(f"Notice auto-loading companion timestamp {c_path}: {ex}")

        if narration:
            self._current_narration = narration
            self.ts_status_lbl.setText(
                f"✅ Timestamps Loaded ({narration.duration_seconds:.1f}s, {len(narration.words)} words)"
            )
            self.ts_status_lbl.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: bold;")
            self.audio_ready.emit(self._current_audio_path, narration, full_text)
        else:
            self.ts_status_lbl.setText("✅ Audio loaded. Ready for video rendering.")
            self.ts_status_lbl.setStyleSheet("color: #34D399; font-size: 11px;")
            self.audio_ready.emit(self._current_audio_path, None, "")

    def _on_import_timestamps_json(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Word Timestamps JSON",
            "",
            "JSON Files (*.json);;All Files (*.*)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            words_data = data.get("words", [])
            word_objs = [
                WordTimestamp(
                    word=w.get("word", ""),
                    start=float(w.get("start", 0.0)),
                    end=float(w.get("end", 0.0))
                )
                for w in words_data if w.get("word")
            ]
            dur = float(data.get("duration_seconds", word_objs[-1].end if word_objs else 0.0))
            narration = NarrationData(duration_seconds=dur, words=word_objs)

            self._current_narration = narration
            self.ts_status_lbl.setText(f"✅ Imported: {Path(file_path).name} ({dur:.1f}s, {len(word_objs)} words)")
            self.ts_status_lbl.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: bold;")

            full_text = " ".join(w.word for w in word_objs)
            if self._current_audio_path:
                self.audio_ready.emit(self._current_audio_path, narration, full_text)
            else:
                self.audio_ready.emit("", narration, full_text)
        except Exception as e:
            QMessageBox.critical(self, "Invalid Timestamps JSON", f"Failed to parse timestamp file: {e}")

    # =========================================================================
    # WHISPER TRANSCRIPTION
    # =========================================================================

    def _on_start_transcription(self):
        if not self._current_audio_path:
            QMessageBox.warning(self, "No Audio", "Please select an audio file first.")
            return

        engine_type = self.engine_combo.currentData() or "groq"

        self.transcribe_btn.setEnabled(False)
        self.browse_audio_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(10)
        self.ts_status_lbl.setText("Starting Whisper transcription...")
        self.ts_status_lbl.setStyleSheet("color: #fbbf24; font-size: 11px;")

        self._worker = TranscriptionWorker(self._current_audio_path, engine_type=engine_type)
        self._worker.progress.connect(self._on_transcribe_progress)
        self._worker.finished.connect(self._on_transcribe_finished)
        self._worker.error.connect(self._on_transcribe_error)
        self._worker.start()

    def _on_transcribe_progress(self, pct: float, msg: str):
        self.progress_bar.setValue(int(pct))
        self.ts_status_lbl.setText(msg)

    def _on_transcribe_finished(self, audio_path: str, narration: NarrationData, text: str):
        self.transcribe_btn.setEnabled(True)
        self.browse_audio_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

        self._current_narration = narration
        self.ts_status_lbl.setText(
            f"✅ Transcribed Successfully ({narration.duration_seconds:.1f}s, {len(narration.words)} words)"
        )
        self.ts_status_lbl.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: bold;")

        self.audio_ready.emit(audio_path, narration, text)

    def _on_transcribe_error(self, err: str):
        self.transcribe_btn.setEnabled(True)
        self.browse_audio_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.ts_status_lbl.setText(f"❌ Transcription error: {err}")
        self.ts_status_lbl.setStyleSheet("color: #f87171; font-size: 11px;")
        QMessageBox.critical(self, "Transcription Error", f"Whisper transcription failed:\n{err}")

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

    def _on_seek(self, position: int):
        self._player.setPosition(position)

    def _on_player_position_changed(self, position: int):
        self.seek_slider.setValue(position)
        self._update_time_label()

    def _on_player_duration_changed(self, duration: int):
        self.seek_slider.setRange(0, duration)
        self._update_time_label()

    def _update_time_label(self):
        pos_s = self._player.position() // 1000
        dur_s = self._player.duration() // 1000
        pos_str = f"{pos_s // 60:02d}:{pos_s % 60:02d}"
        dur_str = f"{dur_s // 60:02d}:{dur_s % 60:02d}"
        self.time_lbl.setText(f"{pos_str} / {dur_str}")
