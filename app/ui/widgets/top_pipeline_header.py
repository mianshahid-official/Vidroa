"""
Top Pipeline Header and Stepper Bar for Stickman Director / PromptBeast.
Exact match to FrameForge top navigation:
  Left: Clapperboard Icon + STICKMAN DIRECTOR (Red) + Subtitle
  Center: 4-Step Interactive Pipeline Stepper (Audio & Script -> Visual Style -> Prompts & Flow -> Images & Render)
  Right: Settings Button (Full-page switch)
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QFrame,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
)


class StepperNode(QWidget):
    """Clickable node in the horizontal pipeline stepper."""

    clicked = Signal(str)

    def __init__(self, step_id: str, step_num: int, label_text: str, parent=None):
        super().__init__(parent)
        self.step_id = step_id
        self.step_num = step_num
        self.label_text = label_text
        self.state = "pending"  # "pending", "active", "completed"
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignCenter)

        # Circle Badge
        self.circle = QLabel(str(self.step_num))
        self.circle.setFixedSize(26, 26)
        self.circle.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.circle, 0, Qt.AlignCenter)

        # Label Text
        self.label = QLabel(self.label_text)
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label, 0, Qt.AlignCenter)

        self.update_state("pending")

    def update_state(self, state: str):
        self.state = state
        if state == "completed":
            self.circle.setText("✓")
            self.circle.setStyleSheet("""
                QLabel {
                    background-color: rgba(46, 125, 50, 0.25);
                    color: #4CAF50;
                    border: 1px solid #4CAF50;
                    border-radius: 13px;
                    font-size: 13px;
                    font-weight: 800;
                }
            """)
            self.label.setStyleSheet("color: #4CAF50; font-size: 10px; font-weight: 600;")
        elif state == "active":
            self.circle.setText(str(self.step_num))
            self.circle.setStyleSheet("""
                QLabel {
                    background-color: #E53935;
                    color: #FFFFFF;
                    border: 1px solid #FF4B4B;
                    border-radius: 13px;
                    font-size: 12px;
                    font-weight: 800;
                }
            """)
            self.label.setStyleSheet("color: #FFFFFF; font-size: 10px; font-weight: 800;")
        else:  # pending
            self.circle.setText(str(self.step_num))
            self.circle.setStyleSheet("""
                QLabel {
                    background-color: #1A1A1A;
                    color: #A0A0A0;
                    border: 1px solid #2E2E2E;
                    border-radius: 13px;
                    font-size: 11px;
                    font-weight: 600;
                }
            """)
            self.label.setStyleSheet("color: #707070; font-size: 10px; font-weight: 600;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.step_id)
        super().mousePressEvent(event)


class TopPipelineHeader(QFrame):
    """
    Top Header Bar featuring app brand on left, 4-step pipeline in center,
    and settings button on right.
    """

    step_selected = Signal(str)  # "audio_script", "visual_style", "studio", "render"
    settings_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(62)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet("""
            QFrame {
                background-color: #0E0E0E;
                border-bottom: 1px solid #1E1E1E;
            }
        """)
        self._init_ui()

    def _init_ui(self):
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(18, 0, 18, 0)
        root_layout.setSpacing(16)

        # =====================================================================
        # LEFT: Brand Title and Subtitle
        # =====================================================================
        brand_box = QHBoxLayout()
        brand_box.setSpacing(10)
        brand_box.setAlignment(Qt.AlignVCenter)

        logo_lbl = QLabel("🎬")
        logo_lbl.setStyleSheet("font-size: 18px; background: transparent; border: none;")
        brand_box.addWidget(logo_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        title_col.setAlignment(Qt.AlignVCenter)

        self.main_title = QLabel("STICKMAN DIRECTOR")
        self.main_title.setStyleSheet("""
            background: transparent;
            color: #E53935;
            font-size: 14px;
            font-weight: 900;
            letter-spacing: 0.8px;
            border: none;
        """)
        title_col.addWidget(self.main_title)

        self.sub_title = QLabel("PromptBeast Pro • 11x Groq Pool")
        self.sub_title.setStyleSheet("""
            background: transparent;
            color: #707070;
            font-size: 10px;
            font-weight: 600;
            border: none;
        """)
        title_col.addWidget(self.sub_title)
        brand_box.addLayout(title_col)

        root_layout.addLayout(brand_box)
        root_layout.addStretch(1)

        # =====================================================================
        # CENTER: 4-Step Horizontal Pipeline Stepper
        # =====================================================================
        stepper_box = QHBoxLayout()
        stepper_box.setSpacing(0)
        stepper_box.setAlignment(Qt.AlignCenter)

        # Node 1: Audio & Script
        self.node1 = StepperNode("audio_script", 1, "Audio & Script")
        self.node1.clicked.connect(self._on_node_clicked)
        stepper_box.addWidget(self.node1)

        # Connector 1
        self.line1 = QFrame()
        self.line1.setFixedWidth(50)
        self.line1.setFixedHeight(2)
        self.line1.setStyleSheet("background-color: #2A2A2A; border: none;")
        stepper_box.addWidget(self.line1)

        # Node 2: Visual Style
        self.node2 = StepperNode("visual_style", 2, "Visual Style")
        self.node2.clicked.connect(self._on_node_clicked)
        stepper_box.addWidget(self.node2)

        # Connector 2
        self.line2 = QFrame()
        self.line2.setFixedWidth(50)
        self.line2.setFixedHeight(2)
        self.line2.setStyleSheet("background-color: #2A2A2A; border: none;")
        stepper_box.addWidget(self.line2)

        # Node 3: Prompts & Flow
        self.node3 = StepperNode("studio", 3, "Prompts & Flow")
        self.node3.clicked.connect(self._on_node_clicked)
        stepper_box.addWidget(self.node3)

        # Connector 3
        self.line3 = QFrame()
        self.line3.setFixedWidth(50)
        self.line3.setFixedHeight(2)
        self.line3.setStyleSheet("background-color: #2A2A2A; border: none;")
        stepper_box.addWidget(self.line3)

        # Node 4: Images & Render
        self.node4 = StepperNode("render", 4, "Images & Render")
        self.node4.clicked.connect(self._on_node_clicked)
        stepper_box.addWidget(self.node4)

        root_layout.addLayout(stepper_box)
        root_layout.addStretch(1)

        # =====================================================================
        # RIGHT: Settings Button
        # =====================================================================
        self.settings_btn = QPushButton("⚙ Settings")
        self.settings_btn.setFixedHeight(32)
        self.settings_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #161616;
                color: #D1D5DB;
                font-size: 11px;
                font-weight: 700;
                border: 1px solid #2E2E2E;
                border-radius: 6px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background-color: #222222;
                border-color: #E53935;
                color: #FFFFFF;
            }
            QPushButton:checked {
                background-color: #221414;
                border-color: #E53935;
                color: #FF4B4B;
            }
        """)
        self.settings_btn.setCheckable(True)
        self.settings_btn.clicked.connect(self._on_settings_clicked)
        root_layout.addWidget(self.settings_btn)

        # Default state
        self.set_active_step("audio_script")

    def _on_node_clicked(self, step_id: str):
        self.settings_btn.setChecked(False)
        self.set_active_step(step_id)
        self.step_selected.emit(step_id)

    def _on_settings_clicked(self):
        self.settings_btn.setChecked(True)
        self.settings_clicked.emit()

    def set_active_step(self, step_id: str):
        """Updates the visual stepper states based on current workflow phase."""
        self.settings_btn.setChecked(step_id == "settings")

        if step_id in ("audio_script", "production", "01"):
            self.node1.update_state("active")
            self.line1.setStyleSheet("background-color: #2A2A2A; border: none;")
            self.node2.update_state("pending")
            self.line2.setStyleSheet("background-color: #2A2A2A; border: none;")
            self.node3.update_state("pending")
            self.line3.setStyleSheet("background-color: #2A2A2A; border: none;")
            self.node4.update_state("pending")

        elif step_id in ("visual_style", "style", "presets"):
            self.node1.update_state("completed")
            self.line1.setStyleSheet("background-color: #4CAF50; border: none;")
            self.node2.update_state("active")
            self.line2.setStyleSheet("background-color: #2A2A2A; border: none;")
            self.node3.update_state("pending")
            self.line3.setStyleSheet("background-color: #2A2A2A; border: none;")
            self.node4.update_state("pending")

        elif step_id in ("studio", "prompts_flow", "02"):
            self.node1.update_state("completed")
            self.line1.setStyleSheet("background-color: #4CAF50; border: none;")
            self.node2.update_state("completed")
            self.line2.setStyleSheet("background-color: #4CAF50; border: none;")
            self.node3.update_state("active")
            self.line3.setStyleSheet("background-color: #2A2A2A; border: none;")
            self.node4.update_state("pending")

        elif step_id in ("render", "images", "deliverables", "03", "04"):
            self.node1.update_state("completed")
            self.line1.setStyleSheet("background-color: #4CAF50; border: none;")
            self.node2.update_state("completed")
            self.line2.setStyleSheet("background-color: #4CAF50; border: none;")
            self.node3.update_state("completed")
            self.line3.setStyleSheet("background-color: #4CAF50; border: none;")
            self.node4.update_state("active")

        elif step_id == "settings":
            # Leave stepper at current completion level and highlight settings button
            pass
