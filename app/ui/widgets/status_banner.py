"""
Connection status badge and notification banner widget.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame


class StatusBannerWidget(QWidget):
    """Displays cloud connection status badge and current model name."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(12)

        # Connection Pill
        self.status_pill = QLabel("● CONNECTED")
        self.status_pill.setStyleSheet(
            "background-color: #064E3B; color: #34D399; border: 1px solid #059669; "
            "border-radius: 12px; padding: 3px 10px; font-size: 11px; font-weight: 700;"
        )
        layout.addWidget(self.status_pill)

        # Model / GPU Info
        self.model_lbl = QLabel("Model: Qwen3-30B-A3B-Instruct (NVIDIA L4 24GB)")
        self.model_lbl.setStyleSheet("color: #94A3B8; font-size: 11px;")
        layout.addWidget(self.model_lbl)

        layout.addStretch()

        # Latency
        self.latency_lbl = QLabel("Ping: 2.1ms")
        self.latency_lbl.setStyleSheet("color: #64748B; font-size: 11px;")
        layout.addWidget(self.latency_lbl)

    def set_connected(self, model: str, gpu: str, latency_ms: float):
        self.status_pill.setText("● CONNECTED")
        self.status_pill.setStyleSheet(
            "background-color: #064E3B; color: #34D399; border: 1px solid #059669; "
            "border-radius: 12px; padding: 3px 10px; font-size: 11px; font-weight: 700;"
        )
        self.model_lbl.setText(f"Model: {model} ({gpu})")
        self.latency_lbl.setText(f"Ping: {latency_ms:.1f}ms")

    def set_offline(self, message: str = "Cloud AI unavailable"):
        self.status_pill.setText("● OFFLINE")
        self.status_pill.setStyleSheet(
            "background-color: #450A0A; color: #F87171; border: 1px solid #991B1B; "
            "border-radius: 12px; padding: 3px 10px; font-size: 11px; font-weight: 700;"
        )
        self.model_lbl.setText(message)
        self.latency_lbl.setText("Ping: —")

    def set_not_configured(self):
        self.status_pill.setText("● NOT CONFIGURED")
        self.status_pill.setStyleSheet(
            "background-color: #451A03; color: #FBBF24; border: 1px solid #B45309; "
            "border-radius: 12px; padding: 3px 10px; font-size: 11px; font-weight: 700;"
        )
        self.model_lbl.setText("Cloud API URL not set. Please configure in Settings.")
        self.latency_lbl.setText("Ping: —")
