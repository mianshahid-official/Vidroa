"""
Visual Style & Reference Thumbnail Matrix for PromptBeast.
Presents the visual art style presets as rich, perfectly scaled visual cards.
Supports Zombie Survival, What If Flat Vector, Stickman, Century-Old Photo, etc.
"""

from pathlib import Path
from typing import Optional, List
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QSizePolicy,
    QScrollArea
)

from app.presets.loader import PresetManager


ALLOWED_STYLE_ORDER = [
    ("zombie_survival", "Zombie Survival", "2D Flat Cartoon"),
    ("3d_red_blue_stickman", "Red & Blue Stickman", "3D Animation"),
    ("whatif_flat_vector", "What If Flat Vector", "2D Minimalist Vector"),
    ("century_old_photograph", "Century-Old Photograph", "Historical Archival"),
]


class StyleThumbnailCard(QFrame):
    """Clickable responsive visual card representing a visual art style with dedicated Master Prompt copy."""

    selected = Signal(str)

    def __init__(self, style_id: str, name: str, category: str, image_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.style_id = style_id
        self.style_name = name
        self.category = category
        self.image_path = image_path
        self._pixmap: Optional[QPixmap] = None
        if self.image_path and Path(self.image_path).exists():
            p = QPixmap(self.image_path)
            if not p.isNull():
                self._pixmap = p

        self._is_active = False
        self.setObjectName("StyleThumbnailCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFixedWidth(170)
        self.setFixedHeight(200)
        self._init_ui()

    def _init_ui(self):
        self.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        # Image thumbnail container box
        self.img_lbl = QLabel()
        self.img_lbl.setFixedHeight(106)
        self.img_lbl.setFixedWidth(156)
        self.img_lbl.setAlignment(Qt.AlignCenter)
        self.img_lbl.setStyleSheet("""
            background-color: #0A0A0A;
            border-radius: 4px;
            border: none;
            padding: 2px;
        """)

        if self._pixmap:
            self.img_lbl.setPixmap(
                self._pixmap.scaled(156, 106, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            self.img_lbl.setText("🎨\n" + self.category)
            self.img_lbl.setStyleSheet("background: #141414; color: #707070; font-size: 11px; border-radius: 4px; border: none;")

        layout.addWidget(self.img_lbl)

        # Style Name
        self.name_lbl = QLabel(self.style_name)
        self.name_lbl.setWordWrap(True)
        self.name_lbl.setAlignment(Qt.AlignCenter)
        self.name_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #A0A0A0; max-height: 28px; border: none; background: transparent;")
        layout.addWidget(self.name_lbl)

        # Dedicated Copy Prompt Button on the card
        self.copy_btn = QPushButton("📋 Copy Prompt")
        self.copy_btn.setFixedHeight(28)
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(229, 57, 53, 0.16);
                color: #FF5252;
                font-weight: 700;
                font-size: 11px;
                border: 1px solid rgba(229, 57, 53, 0.45);
                border-radius: 4px;
                padding: 0 8px;
            }
            QPushButton:hover {
                background-color: #E53935;
                color: #FFFFFF;
                border-color: #FF7070;
            }
            QPushButton:pressed {
                background-color: #B71C1C;
            }
        """)
        self.copy_btn.clicked.connect(self._on_copy_prompt_clicked)
        layout.addWidget(self.copy_btn)

        self._update_style()

    def _on_copy_prompt_clicked(self):
        prompts_dir = Path(__file__).resolve().parent.parent.parent.parent / "config" / "ai_prompts"
        prompt_map = {
            "zombie_survival": "01_zombie_survival_ai_prompt.txt",
            "whatif_flat_vector": "02_whatif_flat_vector_ai_prompt.txt",
            "century_old_photograph": "03_century_old_photograph_ai_prompt.txt",
            "3d_red_blue_stickman": "05_3d_red_blue_stickman_ai_prompt.txt",
        }
        filename = prompt_map.get(self.style_id, "01_zombie_survival_ai_prompt.txt")
        target_path = prompts_dir / filename
        if target_path.exists():
            try:
                content = target_path.read_text(encoding="utf-8")
                from app.core.export import copy_to_system_clipboard
                copy_to_system_clipboard(content)
                self.copy_btn.setText("✓ Copied!")
                QTimer.singleShot(2500, lambda: self.copy_btn.setText("📋 Copy Prompt"))
            except Exception as e:
                print(f"[CopyPrompt] error: {e}")
        self.selected.emit(self.style_id)

    def set_active(self, active: bool):
        self._is_active = active
        self._update_style()

    def _update_style(self):
        if self._is_active:
            self.setStyleSheet("""
                #StyleThumbnailCard {
                    background-color: #201717;
                    border: 2px solid #E53935;
                    border-radius: 8px;
                }
            """)
            self.name_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #FFFFFF; border: none; background: transparent;")
        else:
            self.setStyleSheet("""
                #StyleThumbnailCard {
                    background-color: #171717;
                    border: 1px solid #2E2E2E;
                    border-radius: 8px;
                }
                #StyleThumbnailCard:hover {
                    border-color: #E53935;
                    background-color: #1E1A1A;
                }
            """)
            self.name_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #A0A0A0; border: none; background: transparent;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.selected.emit(self.style_id)
        super().mousePressEvent(event)


class StyleThumbnailMatrix(QWidget):
    """Clean responsive horizontal slider displaying the curated visual style cards."""

    style_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_id: str = "zombie_survival"
        self._cards: List[StyleThumbnailCard] = []
        self._init_ui()

    def _init_ui(self):
        self.setMinimumWidth(0)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # Header row (Active Style Badge only - avoids duplicate title with parent card)
        header_row = QHBoxLayout()
        header_row.addStretch()

        self.active_style_badge = QLabel("★ Zombie Survival Active")
        self.active_style_badge.setStyleSheet("""
            font-size: 11px;
            font-weight: 700;
            color: #FF5252;
            background: rgba(229, 57, 53, 0.15);
            border: 1px solid #E53935;
            border-radius: 6px;
            padding: 3px 10px;
        """)

        header_row.addWidget(self.active_style_badge)
        main_layout.addLayout(header_row)

        # Scroll Area for all style cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFixedHeight(225)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background: #101010;
                border: 1px solid #282828;
                border-radius: 8px;
            }
            QScrollBar:horizontal {
                height: 8px;
                background: #141414;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background: #333333;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #E53935;
            }
        """)

        self.cards_frame = QWidget()
        self.cards_row_layout = QHBoxLayout(self.cards_frame)
        self.cards_row_layout.setContentsMargins(8, 6, 8, 6)
        self.cards_row_layout.setSpacing(10)
        self.cards_row_layout.setAlignment(Qt.AlignLeft)

        self.scroll_area.setWidget(self.cards_frame)
        main_layout.addWidget(self.scroll_area)

        self._populate_styles()

    def _populate_styles(self):
        PresetManager.initialize()
        artworks_dir = Path(__file__).resolve().parent.parent.parent.parent / "assets" / "style_previews"

        for sid, default_name, default_cat in ALLOWED_STYLE_ORDER:
            candidates = [
                artworks_dir / f"{sid}.png",
                artworks_dir / f"{sid}.jpg",
            ]
            if sid == "century_old_photograph":
                candidates.append(artworks_dir / "vintage_photograph.png")

            img_p = None
            for c in candidates:
                if c.exists():
                    img_p = str(c.resolve())
                    break

            card = StyleThumbnailCard(
                style_id=sid,
                name=default_name,
                category=default_cat,
                image_path=img_p,
                parent=self.cards_frame
            )
            card.selected.connect(self.select_style)
            self._cards.append(card)
            self.cards_row_layout.addWidget(card)

        # Default selection: Zombie Survival if available, else first card
        default_sel = "zombie_survival" if any(c.style_id == "zombie_survival" for c in self._cards) else "century_old_photograph"
        self.select_style(default_sel)

    def select_style(self, style_id: str):
        sid = style_id.lower().strip()
        if sid in ("zombie", "zombies", "zombie_survival"):
            sid = "zombie_survival"
        elif sid in ("whatif", "what_if", "whatif_flat_vector", "flat_vector"):
            sid = "whatif_flat_vector"
        elif sid in ("vintage_photograph", "vintage_photo", "century_old_photographs", "century_old_photograph"):
            sid = "century_old_photograph"
        elif sid in ("stick_figure", "stickman", "red_blue_stickman_3d", "3d_red_blue_stickman", "red_and_blue", "red_blue"):
            sid = "3d_red_blue_stickman"
        else:
            sid = "zombie_survival"

        self._selected_id = sid
        for c in self._cards:
            is_match = (c.style_id == sid)
            c.set_active(is_match)
            if is_match:
                self.active_style_badge.setText(f"★ {c.style_name} Active")

        self.style_selected.emit(sid)

    def current_style_id(self) -> str:
        return self._selected_id
