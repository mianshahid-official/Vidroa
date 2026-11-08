"""
In-App QR Code Dialog for Mobile Video Download.
Displays an offline-generated scannable QR code directly on screen
so users can scan with their phone camera to download videos over local Wi-Fi.
"""
import io
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage, QClipboard
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QApplication
)

try:
    import qrcode
except ImportError:
    qrcode = None


class QRCodeDialog(QDialog):
    """Clean dark-themed dialog displaying a scannable QR code for local Wi-Fi download."""

    def __init__(self, url: str, file_name: str = "final_video.mp4", parent=None):
        super().__init__(parent)
        self.url = url
        self.file_name = file_name
        self.setWindowTitle("📱 Mobile Wi-Fi Video Download")
        self.setFixedSize(380, 480)
        self.setStyleSheet("""
            QDialog {
                background-color: #0B0F17;
                border: 1px solid #1E293B;
                border-radius: 10px;
            }
        """)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Title
        title_lbl = QLabel("📱 Save Video to Phone")
        title_lbl.setStyleSheet("color: #F8FAFC; font-size: 16px; font-weight: 800;")
        title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_lbl)

        sub_lbl = QLabel(
            "Point your phone camera at this QR code to download directly to your Camera Roll."
        )
        sub_lbl.setStyleSheet("color: #94A3B8; font-size: 11px;")
        sub_lbl.setWordWrap(True)
        sub_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(sub_lbl)

        # QR Code Display Container
        qr_container = QFrame()
        qr_container.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 3px solid #10B981;
                border-radius: 12px;
                padding: 12px;
            }
        """)
        qc_layout = QVBoxLayout(qr_container)
        qc_layout.setContentsMargins(8, 8, 8, 8)

        self.qr_img_lbl = QLabel()
        self.qr_img_lbl.setAlignment(Qt.AlignCenter)
        self.qr_img_lbl.setFixedSize(220, 220)

        # Generate QR code
        pix = self._generate_qr_pixmap(self.url)
        if pix:
            self.qr_img_lbl.setPixmap(pix.scaled(220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.qr_img_lbl.setText("QR Code Error")

        qc_layout.addWidget(self.qr_img_lbl, 0, Qt.AlignCenter)
        layout.addWidget(qr_container, 0, Qt.AlignCenter)

        # URL row + Copy Button
        url_box = QHBoxLayout()
        url_lbl = QLabel(self.url)
        url_lbl.setStyleSheet("color: #38BDF8; font-size: 11px; font-family: monospace; font-weight: 700;")
        url_lbl.setAlignment(Qt.AlignCenter)
        url_box.addWidget(url_lbl, 1)

        copy_btn = QPushButton("📋 Copy Link")
        copy_btn.setFixedHeight(26)
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #1E293B;
                color: #CBD5E1;
                font-size: 10px;
                font-weight: 600;
                border-radius: 4px;
                border: 1px solid #334155;
                padding: 0 8px;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #FFFFFF;
            }
        """)
        copy_btn.clicked.connect(self._copy_url)
        url_box.addWidget(copy_btn)
        layout.addLayout(url_box)

        # Notice
        hint_lbl = QLabel("⚡ Phone and PC must be on the same Wi-Fi network.")
        hint_lbl.setStyleSheet("color: #64748B; font-size: 10px;")
        hint_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint_lbl)

        # Close button
        close_btn = QPushButton("Done")
        close_btn.setFixedHeight(34)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: #0B0F17;
                font-size: 12px;
                font-weight: 800;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #34D399;
            }
        """)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _generate_qr_pixmap(self, text: str) -> Optional[QPixmap]:
        if qrcode is None:
            return None
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=1
            )
            qr.add_data(text)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            qimg = QImage()
            qimg.loadFromData(buf.getvalue(), "PNG")
            return QPixmap.fromImage(qimg)
        except Exception as e:
            print(f"[QRCodeDialog] Generation notice: {e}")
            return None

    def _copy_url(self):
        cb = QApplication.clipboard()
        if cb:
            cb.setText(self.url)

