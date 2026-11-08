"""
Settings dialog for configuring Groq Multi-Key Engine, models, Whisper transcription, and generation defaults.
"""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QDoubleSpinBox,
    QSpinBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QMessageBox,
    QFrame,
)
from app.config.settings import AppSettings, SettingsManager
from app.ai.api_client import ConnectionCheckWorker
from app.ai.groq_engine import get_groq_engine
from app.ui.widgets.custom_combo import PBComboBox


class SettingsDialog(QDialog):
    """Configuration dialog for Groq Multi-Key AI Engine, Whisper, and Storyboard defaults."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PromptBeast Settings")
        self.setMinimumWidth(640)
        self.setMinimumHeight(500)

        self._worker = None
        self.settings = SettingsManager.load_settings()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        tabs = QTabWidget()

        # =====================================================================
        # Tab 1: Groq AI & Whisper Engine
        # =====================================================================
        groq_tab = QWidget()
        g_tab_layout = QVBoxLayout(groq_tab)
        g_tab_layout.setSpacing(12)

        groq_group = QGroupBox("⚡ Groq Multi-Key Acceleration Engine")
        gg_layout = QVBoxLayout(groq_group)
        gg_layout.setSpacing(10)

        # Active Keys Info
        groq = get_groq_engine()
        key_count = len(groq.api_keys)
        info_lbl = QLabel(
            f"<b>Active Key Pool:</b> {key_count} Groq API keys loaded from "
            f"<code>d:/AntiGravity/groq api.txt</code>.<br>"
            "Keys are automatically rotated in round-robin fashion with instant failover on rate limits (429)."
        )
        info_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; line-height: 1.4;")
        info_lbl.setWordWrap(True)
        gg_layout.addWidget(info_lbl)

        # Primary Storyboard Model
        gg_layout.addWidget(QLabel("Primary Storyboard LLM Model:"))
        self.model_combo = PBComboBox()
        self.model_combo.addItems([
            "qwen/qwen3.8-27b",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
        ])
        current_model = self.settings.default_model or "qwen/qwen3.8-27b"
        if current_model in ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]:
            self.model_combo.setCurrentText(current_model)
        else:
            self.model_combo.setCurrentText("qwen/qwen3.8-27b")
        gg_layout.addWidget(self.model_combo)

        # Audio Transcription Engine
        gg_layout.addWidget(QLabel("Default Audio Transcription Engine:"))
        self.whisper_combo = PBComboBox()
        self.whisper_combo.addItem("Groq Whisper Cloud (whisper-large-v3-turbo - Ultra-Fast <2s)", "groq")
        self.whisper_combo.addItem("Local Faster-Whisper (100% Offline CPU/CUDA)", "local")
        gg_layout.addWidget(self.whisper_combo)

        # Test Connection Button
        test_btn_layout = QHBoxLayout()
        self.test_btn = QPushButton("⚡ Test Groq AI Engine Connection")
        self.test_btn.setFixedHeight(34)
        self.test_btn.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                border: 1px solid #38bdf8;
                color: #ffffff;
                font-weight: bold;
                border-radius: 6px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)
        self.test_btn.clicked.connect(self._on_test_connection)
        test_btn_layout.addWidget(self.test_btn)
        test_btn_layout.addStretch()
        gg_layout.addLayout(test_btn_layout)

        self.test_result_lbl = QLabel("")
        self.test_result_lbl.setStyleSheet("font-size: 11px;")
        self.test_result_lbl.setWordWrap(True)
        gg_layout.addWidget(self.test_result_lbl)

        g_tab_layout.addWidget(groq_group)
        g_tab_layout.addStretch()
        tabs.addTab(groq_tab, "⚡ Groq AI & Whisper")

        # =====================================================================
        # Tab 2: Generation Defaults
        # =====================================================================
        gen_tab = QWidget()
        gen_layout = QVBoxLayout(gen_tab)
        gen_layout.setSpacing(12)

        timing_group = QGroupBox("Default Image Timing Constraints (Seconds)")
        tg_layout = QHBoxLayout(timing_group)

        # Min
        min_box = QVBoxLayout()
        min_box.addWidget(QLabel("Min Duration:"))
        self.min_spin = QDoubleSpinBox()
        self.min_spin.setRange(0.5, 30.0)
        self.min_spin.setValue(self.settings.default_min_duration)
        min_box.addWidget(self.min_spin)
        tg_layout.addLayout(min_box)

        # Preferred
        pref_box = QVBoxLayout()
        pref_box.addWidget(QLabel("Preferred:"))
        self.pref_spin = QDoubleSpinBox()
        self.pref_spin.setRange(1.0, 60.0)
        self.pref_spin.setValue(self.settings.default_preferred_duration)
        pref_box.addWidget(self.pref_spin)
        tg_layout.addLayout(pref_box)

        # Max
        max_box = QVBoxLayout()
        max_box.addWidget(QLabel("Max Duration:"))
        self.max_spin = QDoubleSpinBox()
        self.max_spin.setRange(2.0, 120.0)
        self.max_spin.setValue(self.settings.default_max_duration)
        max_box.addWidget(self.max_spin)
        tg_layout.addLayout(max_box)

        gen_layout.addWidget(timing_group)

        batch_group = QGroupBox("Prompt Generation Batching")
        bg_layout = QHBoxLayout(batch_group)
        bg_layout.addWidget(QLabel("Batch Size (Scenes per LLM request):"))
        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(1, 30)
        self.batch_spin.setValue(self.settings.default_batch_size)
        bg_layout.addWidget(self.batch_spin)
        gen_layout.addWidget(batch_group)

        gen_layout.addStretch()
        tabs.addTab(gen_tab, "Generation Defaults")

        # =====================================================================
        # Tab 3: Workspace
        # =====================================================================
        ws_tab = QWidget()
        w_layout = QVBoxLayout(ws_tab)
        ws_group = QGroupBox("Local Project Storage")
        wsg_layout = QVBoxLayout(ws_group)

        wsg_layout.addWidget(QLabel("Default Workspace Folder:"))
        ws_path_layout = QHBoxLayout()
        self.ws_input = QLineEdit(self.settings.workspace_directory)
        ws_path_layout.addWidget(self.ws_input)
        self.browse_ws_btn = QPushButton("Browse...")
        self.browse_ws_btn.clicked.connect(self._on_browse_workspace)
        ws_path_layout.addWidget(self.browse_ws_btn)
        wsg_layout.addLayout(ws_path_layout)

        w_layout.addWidget(ws_group)
        w_layout.addStretch()
        tabs.addTab(ws_tab, "Workspace")

        layout.addWidget(tabs)

        # Bottom Buttons
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        bottom_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setStyleSheet("background-color: #0284c7; color: #ffffff; font-weight: 600; border-radius: 6px; padding: 6px 16px;")
        self.save_btn.clicked.connect(self._on_save)
        bottom_layout.addWidget(self.save_btn)

        layout.addLayout(bottom_layout)

    def _on_test_connection(self):
        self.test_result_lbl.setText("⏳ Testing Groq AI Engine latency...")
        self.test_result_lbl.setStyleSheet("color: #38bdf8; font-size: 11px;")
        self.test_btn.setEnabled(False)

        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait()

        self._worker = ConnectionCheckWorker("groq", parent=self)
        self._worker.result_ready.connect(self._on_test_connection_finished)
        self._worker.start()

    def _on_test_connection_finished(self, resp):
        self.test_btn.setEnabled(True)
        if resp.connected:
            self.test_result_lbl.setText(f"✅ {resp.message} (Roundtrip Latency: {resp.latency_ms:.0f}ms)")
            self.test_result_lbl.setStyleSheet("color: #4ade80; font-weight: bold; font-size: 11px;")
        else:
            self.test_result_lbl.setText(f"❌ {resp.message}")
            self.test_result_lbl.setStyleSheet("color: #f87171; font-weight: bold; font-size: 11px;")

    def _cleanup_worker(self):
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait()

    def reject(self):
        self._cleanup_worker()
        super().reject()

    def closeEvent(self, event):
        self._cleanup_worker()
        super().closeEvent(event)

    def _on_browse_workspace(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Default Workspace Folder", self.ws_input.text())
        if dir_path:
            self.ws_input.setText(dir_path)

    def _on_save(self):
        self._cleanup_worker()
        self.settings.default_model = self.model_combo.currentText()
        self.settings.default_min_duration = self.min_spin.value()
        self.settings.default_preferred_duration = self.pref_spin.value()
        self.settings.default_max_duration = self.max_spin.value()
        self.settings.default_batch_size = self.batch_spin.value()
        self.settings.workspace_directory = self.ws_input.text().strip()

        SettingsManager.save_settings(self.settings)
        self.accept()
