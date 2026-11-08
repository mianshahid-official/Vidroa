"""
Profiles Manager Panel for PromptBeast.
Allows signing into up to 6+ Google/Gemini accounts using isolated Chrome profiles
with real-time cookie session detection and 1-click launch.
"""

import os
import subprocess
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QFrame,
    QGridLayout,
    QScrollArea,
    QMessageBox,
    QGraphicsDropShadowEffect,
)

from app.core.browser_profiles_manager import BrowserProfilesManager


class ProfileCard(QFrame):
    """Card widget representing a single Chrome browser profile."""

    login_requested = Signal(str)
    refresh_requested = Signal()

    def __init__(self, profile_data: dict, parent=None):
        super().__init__(parent)
        self.profile_data = profile_data
        self.setObjectName("ProfileCard")
        self._init_ui()

    def _init_ui(self):
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            #ProfileCard {
                background-color: #0d1522;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 16px;
            }
            #ProfileCard:hover {
                border-color: #10b981;
                background-color: #101c2e;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Header Row: Icon + Name + Status Pill
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        icon_lbl = QLabel("👤")
        icon_lbl.setStyleSheet("font-size: 20px; background: transparent;")

        name_lbl = QLabel(self.profile_data["name"])
        name_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #f8fafc;")

        header_row.addWidget(icon_lbl)
        header_row.addWidget(name_lbl)
        header_row.addStretch()

        # Status Pill
        is_signed = self.profile_data["is_signed_in"]
        in_use = self.profile_data["in_use"]

        if is_signed:
            status_text = "🟢 Signed in"
            status_style = "background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid #10b981;"
        elif in_use:
            status_text = "🟡 In use"
            status_style = "background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid #f59e0b;"
        else:
            status_text = "⚪ Not signed in"
            status_style = "background: rgba(100, 116, 139, 0.15); color: #94a3b8; border: 1px solid #334155;"

        status_pill = QLabel(status_text)
        status_pill.setStyleSheet(f"""
            font-size: 11px;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 10px;
            {status_style}
        """)
        header_row.addWidget(status_pill)
        layout.addLayout(header_row)

        # Path info / description
        desc_lbl = QLabel(self.profile_data["status_label"])
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("font-size: 12px; color: #64748b; min-height: 28px;")
        layout.addWidget(desc_lbl)

        # Action Buttons Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        login_btn = QPushButton("➔ Open & Login in Chrome")
        login_btn.setCursor(Qt.PointingHandCursor)
        login_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
                color: #ffffff;
                font-size: 12px;
                font-weight: 600;
                border: none;
                border-radius: 6px;
                padding: 7px 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #34d399);
            }
            QPushButton:pressed {
                background: #047857;
            }
        """)
        login_btn.clicked.connect(lambda: self.login_requested.emit(self.profile_data["name"]))

        folder_btn = QPushButton("📁 Folder")
        folder_btn.setCursor(Qt.PointingHandCursor)
        folder_btn.setStyleSheet("""
            QPushButton {
                background: #1e293b;
                color: #cbd5e1;
                font-size: 12px;
                font-weight: 500;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 7px 12px;
            }
            QPushButton:hover {
                background: #334155;
                color: #f8fafc;
            }
        """)
        folder_btn.clicked.connect(self._open_folder)

        btn_row.addWidget(login_btn, 3)
        btn_row.addWidget(folder_btn, 1)
        layout.addLayout(btn_row)

    def _open_folder(self):
        p = self.profile_data["path"]
        if os.path.exists(p):
            if sys.platform == "win32":
                os.startfile(p)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", p])
            else:
                subprocess.Popen(["xdg-open", p])


class ProfilesManagerPanel(QWidget):
    """Master Profiles Tab Widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ProfilesManagerPanel")
        self._init_ui()

        # Poller to refresh status every 5 seconds
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh_profiles)
        self._refresh_timer.start(5000)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(18)

        # Header Card
        header_card = QFrame()
        header_card.setStyleSheet("""
            QFrame {
                background-color: #0d1522;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 16px;
            }
        """)
        h_layout = QVBoxLayout(header_card)
        h_layout.setContentsMargins(16, 14, 16, 14)
        h_layout.setSpacing(10)

        top_h_row = QHBoxLayout()
        title_lbl = QLabel("Chrome Browser Profiles Manager")
        title_lbl.setStyleSheet("font-size: 20px; font-weight: 800; color: #f8fafc;")

        self.signed_count_badge = QLabel("0 of 6 signed in")
        self.signed_count_badge.setStyleSheet("""
            font-size: 12px;
            font-weight: 700;
            color: #10b981;
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid #10b981;
            border-radius: 12px;
            padding: 4px 12px;
        """)

        top_h_row.addWidget(title_lbl)
        top_h_row.addWidget(self.signed_count_badge)
        top_h_row.addStretch()

        open_all_btn = QPushButton("➔ Open All Profiles to Login")
        open_all_btn.setCursor(Qt.PointingHandCursor)
        open_all_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
                color: #ffffff;
                font-size: 13px;
                font-weight: 700;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #34d399);
            }
        """)
        open_all_btn.clicked.connect(self._on_open_all)
        top_h_row.addWidget(open_all_btn)
        h_layout.addLayout(top_h_row)

        desc = QLabel(
            "Manage your Chrome browser profile instances. Click <b>Open & Login</b> to launch Chrome with that profile, "
            "sign into Google / Gemini once, and session cookies are saved permanently for automated AI image and script generation!"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 13px; color: #94a3b8; line-height: 1.4;")
        h_layout.addWidget(desc)

        main_layout.addWidget(header_card)

        # Create New Profile Bar
        create_bar = QFrame()
        create_bar.setStyleSheet("""
            QFrame {
                background-color: #0b111a;
                border: 1px dashed #1e293b;
                border-radius: 6px;
                padding: 8px 12px;
            }
        """)
        c_layout = QHBoxLayout(create_bar)
        c_layout.setContentsMargins(8, 4, 8, 4)
        c_layout.setSpacing(10)

        c_lbl = QLabel("➕ Create New Profile:")
        c_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #cbd5e1;")

        self.new_prof_input = QLineEdit()
        self.new_prof_input.setPlaceholderText("Profile name e.g. acc7, secondary_google")
        self.new_prof_input.setStyleSheet("""
            QLineEdit {
                background: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 6px;
                color: #f8fafc;
                padding: 6px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #10b981;
            }
        """)

        create_btn = QPushButton("📁 Create Profile Folder")
        create_btn.setCursor(Qt.PointingHandCursor)
        create_btn.setStyleSheet("""
            QPushButton {
                background: #1e293b;
                color: #f8fafc;
                font-size: 12px;
                font-weight: 600;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background: #334155;
                border-color: #10b981;
            }
        """)
        create_btn.clicked.connect(self._on_create_profile)

        c_layout.addWidget(c_lbl)
        c_layout.addWidget(self.new_prof_input, 1)
        c_layout.addWidget(create_btn)
        main_layout.addWidget(create_bar)

        # Storage location label
        loc_row = QHBoxLayout()
        loc_title = QLabel("Configured Chrome Profiles List")
        loc_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #f8fafc;")

        loc_path_lbl = QLabel(f"Storage: <code>{BrowserProfilesManager.get_profiles_dir()}</code>")
        loc_path_lbl.setStyleSheet("font-size: 12px; color: #64748b;")

        loc_row.addWidget(loc_title)
        loc_row.addStretch()
        loc_row.addWidget(loc_path_lbl)
        main_layout.addLayout(loc_row)

        # Scroll area containing the card grid
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.cards_container = QWidget()
        self.cards_layout = QGridLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(14)

        self.scroll_area.setWidget(self.cards_container)
        main_layout.addWidget(self.scroll_area, 1)

        # Initial populate
        self.refresh_profiles()

    def refresh_profiles(self):
        """Refreshes the profile cards and counts."""
        # Clear existing cards
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        profiles = BrowserProfilesManager.get_all_profiles()
        signed_count = sum(1 for p in profiles if p["is_signed_in"])
        total_count = len(profiles)

        self.signed_count_badge.setText(f"{signed_count} of {total_count} signed in")
        if signed_count > 0:
            self.signed_count_badge.setStyleSheet("""
                font-size: 12px;
                font-weight: 700;
                color: #34d399;
                background: rgba(16, 185, 129, 0.15);
                border: 1px solid #10b981;
                border-radius: 12px;
                padding: 4px 12px;
            """)
        else:
            self.signed_count_badge.setStyleSheet("""
                font-size: 12px;
                font-weight: 700;
                color: #f59e0b;
                background: rgba(245, 158, 11, 0.15);
                border: 1px solid #f59e0b;
                border-radius: 12px;
                padding: 4px 12px;
            """)

        cols = 3
        for idx, p in enumerate(profiles):
            row = idx // cols
            col = idx % cols
            card = ProfileCard(p, self.cards_container)
            card.login_requested.connect(self._on_login_requested)
            self.cards_layout.addWidget(card, row, col)

    def _on_login_requested(self, name: str):
        ok, msg = BrowserProfilesManager.open_browser_profile(name)
        if ok:
            win = self.window()
            if hasattr(win, "statusBar") and win.statusBar():
                win.statusBar().showMessage(f"🚀 {msg}", 5000)
        else:
            QMessageBox.warning(self, "Chrome Launch Error", msg)

    def _on_open_all(self):
        ok, msg = BrowserProfilesManager.open_all_profiles()
        if ok:
            win = self.window()
            if hasattr(win, "statusBar") and win.statusBar():
                win.statusBar().showMessage(f"🚀 {msg}", 6000)
        else:
            QMessageBox.warning(self, "Launch Error", msg)

    def _on_create_profile(self):
        name = self.new_prof_input.text().strip()
        if not name:
            return
        ok, res = BrowserProfilesManager.create_profile(name)
        if ok:
            self.new_prof_input.clear()
            self.refresh_profiles()
        else:
            QMessageBox.warning(self, "Create Profile Error", res)
