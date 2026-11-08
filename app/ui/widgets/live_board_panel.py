"""
Live Board Monitor Panel for PromptBeast.
Displays real-time pipeline execution, stage indicators (Script, Scenes, Prompts, Images, Clips, Voice, Render),
incoming image wall previews, Chrome profile status pills (acc1..acc6), and activity feed.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QProgressBar,
    QScrollArea,
    QGridLayout,
)

from app.core.browser_profiles_manager import BrowserProfilesManager


class StageIndicatorRow(QWidget):
    """Single stage row showing status icon, name, and subtitle."""

    def __init__(self, stage_id: str, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.stage_id = stage_id
        self._state = "pending"  # pending, active, done, error
        self.setStyleSheet("background: transparent; border: none;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 6, 4, 6)
        layout.setSpacing(10)

        self.dot_lbl = QLabel("⚪")
        self.dot_lbl.setStyleSheet("font-size: 13px; color: #475569;")

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)

        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #ffffff; background: transparent;")

        self.sub_lbl = QLabel(subtitle)
        self.sub_lbl.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent;")

        text_layout.addWidget(self.title_lbl)
        text_layout.addWidget(self.sub_lbl)

        layout.addWidget(self.dot_lbl)
        layout.addLayout(text_layout)
        layout.addStretch()

    def set_state(self, state: str):
        self._state = state
        if state == "active":
            self.dot_lbl.setText("🟢")
            self.title_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #34d399;")
            self.sub_lbl.setStyleSheet("font-size: 11px; color: #10b981;")
        elif state == "done":
            self.dot_lbl.setText("✅")
            self.title_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #f8fafc;")
            self.sub_lbl.setStyleSheet("font-size: 11px; color: #64748b;")
        elif state == "error":
            self.dot_lbl.setText("❌")
            self.title_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #ef4444;")
        else:
            self.dot_lbl.setText("⚪")
            self.title_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #64748b;")
            self.sub_lbl.setStyleSheet("font-size: 11px; color: #475569;")


class LiveBoardPanel(QWidget):
    """Master Live Board Monitor Panel."""

    stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LiveBoardPanel")
        self._stages: Dict[str, StageIndicatorRow] = {}
        self._profile_pills: Dict[str, QLabel] = {}
        self._init_ui()

        # Poller for Chrome profile pills
        self._pill_timer = QTimer(self)
        self._pill_timer.timeout.connect(self.refresh_profile_pills)
        self._pill_timer.start(4000)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(14)

        # Header Bar
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("""
            background-color: #0b111a;
            border: 1px solid #1a2536;
            border-radius: 12px;
            padding: 10px 16px;
        """)
        h_layout = QHBoxLayout(hdr_frame)
        h_layout.setContentsMargins(8, 6, 8, 6)

        left_info = QVBoxLayout()
        left_info.setSpacing(2)
        pipe_tag = QLabel("● PIPELINE MONITOR")
        pipe_tag.setStyleSheet("color: #10b981; font-size: 10px; font-weight: 700; letter-spacing: 0.5px;")
        self.project_title_lbl = QLabel("No project active")
        self.project_title_lbl.setStyleSheet("font-size: 20px; font-weight: 800; color: #f8fafc;")
        left_info.addWidget(pipe_tag)
        left_info.addWidget(self.project_title_lbl)
        h_layout.addLayout(left_info)
        h_layout.addStretch()

        # Stats Counters
        self.stat_elapsed = self._create_stat_box("ELAPSED", "00:00")
        self.stat_left = self._create_stat_box("REMAINING", "--:--")
        self.stat_images = self._create_stat_box("IMAGES", "0")
        h_layout.addWidget(self.stat_elapsed)
        h_layout.addWidget(self.stat_left)
        h_layout.addWidget(self.stat_images)

        self.stop_btn = QPushButton("■ Stop run")
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background: rgba(239, 68, 68, 0.15);
                color: #f87171;
                border: 1px solid #ef4444;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.3);
            }
        """)
        self.stop_btn.clicked.connect(self.stop_requested.emit)
        h_layout.addWidget(self.stop_btn)
        main_layout.addWidget(hdr_frame)

        # Center split: Stages Column (left) + Live Feeds (right)
        center_row = QHBoxLayout()
        center_row.setSpacing(14)

        # Left Column: Stages Box
        stages_box = QFrame()
        stages_box.setFixedWidth(240)
        stages_box.setStyleSheet("""
            background-color: #0b111a;
            border: 1px solid #1a2536;
            border-radius: 6px;
            padding: 12px;
        """)
        s_layout = QVBoxLayout(stages_box)
        s_layout.setContentsMargins(10, 10, 10, 10)
        s_layout.setSpacing(4)

        s_title = QLabel("Pipeline Stages")
        s_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569; letter-spacing: 0.5px; margin-bottom: 6px;")
        s_layout.addWidget(s_title)

        stages_meta = [
            ("script", "Script", "analyzing story & beats"),
            ("scenes", "Scenes", "writing scene rows"),
            ("prompts", "Prompts", "building consistency prompts"),
            ("images", "Images", "generating visual stills"),
            ("clips", "Hook Clips", "dynamic animated video clips"),
            ("voice", "Voiceover", "Kokoro Offline / Modal Cloud synthesis"),
            ("render", "Render & Publish", "concatenating, karaoke & audio mux"),
        ]
        for sid, stitle, ssub in stages_meta:
            row = StageIndicatorRow(sid, stitle, ssub, stages_box)
            self._stages[sid] = row
            s_layout.addWidget(row)

        s_layout.addStretch()
        center_row.addWidget(stages_box)

        # Right Column: Progress + Image Arrivals + Account Pills + Activity
        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        # Progress bar card
        prog_card = QFrame()
        prog_card.setStyleSheet("""
            background-color: #0b111a;
            border: 1px solid #1a2536;
            border-radius: 6px;
            padding: 12px 16px;
        """)
        p_layout = QVBoxLayout(prog_card)
        p_layout.setContentsMargins(8, 8, 8, 8)
        p_layout.setSpacing(6)

        p_row = QHBoxLayout()
        self.disk_count_lbl = QLabel("0 pictures on disk")
        self.disk_count_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #f8fafc;")
        self.prog_pct_lbl = QLabel("0%")
        self.prog_pct_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #10b981;")
        p_row.addWidget(self.disk_count_lbl)
        p_row.addStretch()
        p_row.addWidget(self.prog_pct_lbl)
        p_layout.addLayout(p_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #16202e;
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
                border-radius: 4px;
            }
        """)
        p_layout.addWidget(self.progress_bar)
        right_col.addWidget(prog_card)

        # Live Image Arrivals Box
        arrivals_box = QFrame()
        arrivals_box.setStyleSheet("""
            background-color: #0b111a;
            border: 1px solid #1a2536;
            border-radius: 6px;
            padding: 12px;
        """)
        a_layout = QVBoxLayout(arrivals_box)
        a_layout.setContentsMargins(10, 8, 10, 8)
        a_layout.setSpacing(8)

        arr_title = QLabel("Images as they arrive")
        arr_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #94a3b8;")
        a_layout.addWidget(arr_title)

        self.arrival_empty_lbl = QLabel("No images yet. The moment each scene is generated, it appears here in real-time.")
        self.arrival_empty_lbl.setAlignment(Qt.AlignCenter)
        self.arrival_empty_lbl.setStyleSheet("color: #475569; font-size: 12px; min-height: 80px;")
        a_layout.addWidget(self.arrival_empty_lbl)

        # Scroll for thumbnails
        self.arrivals_scroll = QScrollArea()
        self.arrivals_scroll.setFixedHeight(120)
        self.arrivals_scroll.setWidgetResizable(True)
        self.arrivals_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.arrivals_container = QWidget()
        self.arrivals_layout = QHBoxLayout(self.arrivals_container)
        self.arrivals_layout.setContentsMargins(0, 0, 0, 0)
        self.arrivals_layout.setSpacing(8)
        self.arrivals_layout.setAlignment(Qt.AlignLeft)
        self.arrivals_scroll.setWidget(self.arrivals_container)
        self.arrivals_scroll.hide()
        a_layout.addWidget(self.arrivals_scroll)

        right_col.addWidget(arrivals_box)

        # Account status pills row (acc1..acc6)
        pills_card = QFrame()
        pills_card.setStyleSheet("""
            background-color: #0b111a;
            border: 1px solid #1a2536;
            border-radius: 6px;
            padding: 10px;
        """)
        pills_layout = QHBoxLayout(pills_card)
        pills_layout.setContentsMargins(6, 6, 6, 6)
        pills_layout.setSpacing(10)

        for i in range(1, 7):
            name = f"acc{i}"
            pill = QLabel(f"● {name}: Checking...")
            pill.setStyleSheet("""
                font-size: 11px;
                font-weight: 600;
                color: #64748b;
                background-color: #121c2c;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 6px 12px;
            """)
            self._profile_pills[name] = pill
            pills_layout.addWidget(pill)

        right_col.addWidget(pills_card)

        # Activity log card
        act_card = QFrame()
        act_card.setStyleSheet("""
            background-color: #0b111a;
            border: 1px solid #1a2536;
            border-radius: 6px;
            padding: 12px;
        """)
        act_layout = QVBoxLayout(act_card)
        act_layout.setContentsMargins(8, 6, 8, 6)
        act_layout.setSpacing(4)

        act_title = QLabel("Activity Stream")
        act_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569; letter-spacing: 0.5px;")
        act_layout.addWidget(act_title)

        self.activity_lbl = QLabel("Ready. Press Run Pipeline to start production.")
        self.activity_lbl.setStyleSheet("color: #94a3b8; font-size: 12px; font-family: 'Consolas', monospace;")
        act_layout.addWidget(self.activity_lbl)

        right_col.addWidget(act_card)
        center_row.addLayout(right_col, 1)

        main_layout.addLayout(center_row, 1)

        self.refresh_profile_pills()

    def _create_stat_box(self, label: str, value: str) -> QFrame:
        f = QFrame()
        f.setFixedSize(100, 50)
        f.setStyleSheet("""
            background-color: #101826;
            border: 1px solid #1e293b;
            border-radius: 8px;
        """)
        l = QVBoxLayout(f)
        l.setContentsMargins(6, 4, 6, 4)
        l.setSpacing(1)
        lbl = QLabel(label)
        lbl.setStyleSheet("font-size: 9px; font-weight: 700; color: #94a3b8; letter-spacing: 0.5px; background: transparent;")
        val = QLabel(value)
        val.setStyleSheet("font-size: 16px; font-weight: 800; color: #ffffff; background: transparent;")
        l.addWidget(lbl)
        l.addWidget(val)
        f.val_label = val
        return f

    def refresh_profile_pills(self):
        profiles = BrowserProfilesManager.get_all_profiles()
        prof_map = {p["name"]: p for p in profiles}

        for name, pill in self._profile_pills.items():
            info = prof_map.get(name)
            if not info:
                continue
            if info["is_signed_in"]:
                pill.setText(f"● {name}: Signed in")
                pill.setStyleSheet("""
                    font-size: 11px;
                    font-weight: 600;
                    color: #34d399;
                    background-color: rgba(16, 185, 129, 0.12);
                    border: 1px solid #10b981;
                    border-radius: 6px;
                    padding: 6px 12px;
                """)
            elif info["in_use"]:
                pill.setText(f"● {name}: In use")
                pill.setStyleSheet("""
                    font-size: 11px;
                    font-weight: 600;
                    color: #fbbf24;
                    background-color: rgba(245, 158, 11, 0.12);
                    border: 1px solid #f59e0b;
                    border-radius: 6px;
                    padding: 6px 12px;
                """)
            else:
                pill.setText(f"● {name}: Not signed in")
                pill.setStyleSheet("""
                    font-size: 11px;
                    font-weight: 600;
                    color: #64748b;
                    background-color: #121c2c;
                    border: 1px solid #1e293b;
                    border-radius: 6px;
                    padding: 6px 12px;
                """)

    def set_stage_status(self, stage_id: str, status: str):
        if stage_id in self._stages:
            self._stages[stage_id].set_state(status)

    def set_activity(self, message: str):
        self.activity_lbl.setText(message)

    def set_progress(self, current: int, total: int):
        self.disk_count_lbl.setText(f"{current} of {total} pictures on disk")
        pct = int((current / max(1, total)) * 100)
        self.prog_pct_lbl.setText(f"{pct}%")
        self.progress_bar.setValue(pct)
        if hasattr(self.stat_images, "val_label"):
            self.stat_images.val_label.setText(str(current))

    def add_arrived_image(self, img_path: str):
        if not Path(img_path).exists():
            return
        self.arrival_empty_lbl.hide()
        self.arrivals_scroll.show()

        pix = QPixmap(img_path)
        if not pix.isNull():
            lbl = QLabel()
            lbl.setFixedSize(140, 100)
            lbl.setPixmap(pix.scaled(140, 100, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
            lbl.setStyleSheet("border-radius: 6px; border: 1px solid #10b981;")
            self.arrivals_layout.addWidget(lbl)
