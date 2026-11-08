"""
Visual Art Style Studio Matrix for PromptBeast.
Displays curated, production-ready art style presets as responsive 16:9 visual studio cards.
Features instant 1-click selection, active glow highlights, and mouse-wheel horizontal scrolling.
"""

from pathlib import Path
from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QScrollArea,
    QSizePolicy,
)

from app.presets.loader import PresetManager
from app.models.presets import VisualStylePreset


class StyleThumbnailCard(QFrame):
    """Studio visual card representing an art style with 16:9 thumbnail and category badge."""

    selected = Signal(str)

    def __init__(
        self,
        style_id: str,
        name: str,
        category: str,
        image_path: Optional[str] = None,
        parent=None
    ):
        super().__init__(parent)
        self.style_id = style_id
        self.style_name = name
        self.category = category
        self.image_path = image_path
        self._is_active = False

        self._pixmap: Optional[QPixmap] = None
        if self.image_path and Path(self.image_path).exists():
            p = QPixmap(self.image_path)
            if not p.isNull():
                self._pixmap = p

        self.setObjectName("StyleThumbnailCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedWidth(160)
        self.setFixedHeight(175)
        self._init_ui()

    def _init_ui(self):
        self.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # 16:9 Image Thumbnail Container Box
        self.img_container = QFrame()
        self.img_container.setFixedHeight(96)
        self.img_container.setStyleSheet("""
            QFrame {
                background-color: #06090E;
                border-radius: 5px;
                border: 1px solid rgba(255, 255, 255, 0.06);
            }
        """)
        img_layout = QVBoxLayout(self.img_container)
        img_layout.setContentsMargins(0, 0, 0, 0)
        img_layout.setSpacing(0)

        self.img_lbl = QLabel(self.img_container)
        self.img_lbl.setAlignment(Qt.AlignCenter)
        self.img_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        if self._pixmap:
            self.img_lbl.setPixmap(
                self._pixmap.scaled(148, 92, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            cat_short = self.category[:14] if self.category else "Art"
            self.img_lbl.setText(f"🎨\n{cat_short}")
            self.img_lbl.setStyleSheet("color: #64748B; font-size: 11px; font-weight: 600; text-align: center;")

        # Top overlay bar: Category pill
        overlay_bar = QHBoxLayout()
        overlay_bar.setContentsMargins(4, 4, 4, 0)
        cat_text = self.category if len(self.category) <= 12 else (self.category[:10] + "..")
        self.cat_pill = QLabel(cat_text)
        self.cat_pill.setStyleSheet("""
            background-color: rgba(8, 12, 18, 0.85);
            color: #94A3B8;
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 3px;
            padding: 1px 5px;
            font-size: 9px;
            font-weight: 600;
        """)
        overlay_bar.addWidget(self.cat_pill)
        overlay_bar.addStretch()

        img_layout.addLayout(overlay_bar)
        img_layout.addWidget(self.img_lbl)
        layout.addWidget(self.img_container)

        # Style Name
        self.name_lbl = QLabel(self.style_name)
        self.name_lbl.setWordWrap(True)
        self.name_lbl.setAlignment(Qt.AlignCenter)
        self.name_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #CBD5E1; max-height: 36px;")
        layout.addWidget(self.name_lbl)

        # Active indicator badge
        self.status_pill = QLabel("Click to Select")
        self.status_pill.setAlignment(Qt.AlignCenter)
        self.status_pill.setStyleSheet("font-size: 9px; color: #64748B; padding: 1px 0;")
        layout.addWidget(self.status_pill)

        self._update_style()

    def set_active(self, active: bool):
        self._is_active = active
        self._update_style()

    def _update_style(self):
        if self._is_active:
            self.setStyleSheet("""
                #StyleThumbnailCard {
                    background-color: rgba(16, 28, 20, 0.95);
                    border: 2px solid #A3FF12;
                    border-radius: 8px;
                }
            """)
            self.name_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #A3FF12;")
            self.status_pill.setText("★ Active Style")
            self.status_pill.setStyleSheet("font-size: 9px; font-weight: 700; color: #34D399;")
        else:
            self.setStyleSheet("""
                #StyleThumbnailCard {
                    background-color: rgba(14, 20, 28, 0.65);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 8px;
                }
                #StyleThumbnailCard:hover {
                    border-color: rgba(163, 255, 18, 0.5);
                    background-color: rgba(22, 34, 30, 0.85);
                }
            """)
            self.name_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #CBD5E1;")
            self.status_pill.setText("Click to Select")
            self.status_pill.setStyleSheet("font-size: 9px; color: #64748B;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.selected.emit(self.style_id)
        super().mousePressEvent(event)


class HorizontalScrollArea(QScrollArea):
    """Smooth horizontal scroll area supporting mouse wheel horizontal scrolling."""

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y() or event.angleDelta().x()
        if delta:
            h_bar = self.horizontalScrollBar()
            if h_bar:
                h_bar.setValue(h_bar.value() - delta // 2)
                event.accept()
                return
        super().wheelEvent(event)


class StyleThumbnailMatrix(QWidget):
    """
    Professional studio visual art style selector with horizontal rack layout,
    instant 1-click selection, and real-time active indicators.
    """

    style_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_id: str = "3d_stickman"
        self._cards: List[StyleThumbnailCard] = []
        self._init_ui()

    def _init_ui(self):
        self.setMinimumWidth(0)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # Header bar
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        header_title = QLabel("🎨 Visual Art Style Guide")
        header_title.setStyleSheet("font-size: 13px; font-weight: 800; color: #F8FAFC;")
        header_row.addWidget(header_title)

        self.active_style_badge = QLabel("3D Stickman Style Active")
        self.active_style_badge.setStyleSheet("""
            font-size: 11px;
            font-weight: 700;
            color: #A3FF12;
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid rgba(163, 255, 18, 0.4);
            border-radius: 6px;
            padding: 3px 10px;
        """)
        header_row.addWidget(self.active_style_badge)
        header_row.addStretch()

        main_layout.addLayout(header_row)

        # Horizontal Scroll Area for Cards Rack
        self.scroll_area = HorizontalScrollArea()
        self.scroll_area.setFixedHeight(196)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #080C14;
                border: 1px solid rgba(163, 255, 18, 0.16);
                border-radius: 8px;
            }
            QScrollBar:horizontal {
                background: #0B0F17;
                height: 6px;
                margin: 0px 4px 2px 4px;
                border-radius: 3px;
            }
            QScrollBar::handle:horizontal {
                background: rgba(163, 255, 18, 0.3);
                border-radius: 3px;
                min-width: 24px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #A3FF12;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)

        self.cards_content_widget = QWidget()
        self.cards_content_widget.setStyleSheet("background: transparent;")
        self.cards_row_layout = QHBoxLayout(self.cards_content_widget)
        self.cards_row_layout.setContentsMargins(8, 8, 8, 8)
        self.cards_row_layout.setSpacing(10)
        self.cards_row_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.scroll_area.setWidget(self.cards_content_widget)
        main_layout.addWidget(self.scroll_area)

        self.refresh_styles()

    def refresh_styles(self):
        """Builds all visual style cards from PresetManager."""
        PresetManager.initialize()

        while self.cards_row_layout.count() > 0:
            item = self.cards_row_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._cards.clear()

        styles: List[VisualStylePreset] = PresetManager.get_all_styles()
        artworks_dir = Path(__file__).resolve().parent.parent.parent.parent / "assets" / "style_previews"

        for s in styles:
            candidates = [
                artworks_dir / f"{s.id}.png",
                artworks_dir / f"{s.id}.jpg",
                artworks_dir / f"{s.id}.jpeg",
            ]
            if s.id == "century_old_photograph":
                candidates.append(artworks_dir / "vintage_photograph.png")

            img_p = None
            for c in candidates:
                if c.exists():
                    img_p = str(c.resolve())
                    break

            card = StyleThumbnailCard(
                style_id=s.id,
                name=s.name,
                category=s.category or "Art",
                image_path=img_p,
                parent=self.cards_content_widget
            )
            card.selected.connect(self.select_style)
            self._cards.append(card)
            self.cards_row_layout.addWidget(card)

        # Preserve selection
        existing_ids = [c.style_id for c in self._cards]
        if self._selected_id in existing_ids:
            self.select_style(self._selected_id)
        elif self._cards:
            self.select_style(self._cards[0].style_id)

    def select_style(self, style_id: str):
        """Selects a style and updates active states across all cards."""
        # Normalize aliases
        if style_id in ("3d_stickman", "3d_stickman_style", "stickman_3d"):
            style_id = "3d_stickman"
        elif style_id in ("2d_stickman", "2d_stickman_style", "stickman_2d", "2d_stick_figure"):
            style_id = "2d_stickman"
        elif style_id in ("vintage_photograph", "vintage_photo", "century_old_photographs"):
            style_id = "century_old_photograph"
        elif style_id in ("stick_figure", "stickman", "red_blue_stickman_3d"):
            style_id = "3d_red_blue_stickman"
        elif style_id in ("black_white_historical_photography", "bw_historical_photography"):
            style_id = "bw_vintage_historical_photography"
        elif style_id in ("quilling", "paper_quill", "paper_quilling_illustration"):
            style_id = "paper_quilling"
        elif style_id in ("collage", "mixed_media", "mixed_media_collage_illustration"):
            style_id = "mixed_media_collage"
        elif style_id in ("cutout", "paper_cut", "paper_cutout_illustration"):
            style_id = "paper_cutout"

        self._selected_id = style_id
        selected_name = "3D Stickman Style"

        for c in self._cards:
            is_match = (c.style_id == style_id)
            c.set_active(is_match)
            if is_match:
                selected_name = c.style_name

        self.active_style_badge.setText(f"★ {selected_name} Active")
        self.style_selected.emit(style_id)

    def current_style_id(self) -> str:
        return self._selected_id
