"""
Visual Style & Reference Thumbnail Matrix for PromptBeast Studio.
Presents curated built-in and user-defined custom visual art styles as professional studio cards.
Includes dynamic custom style creation, live preview thumbnails, and 1-click deletion.
"""

from pathlib import Path
from typing import Optional, List, Dict
import shutil

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QWheelEvent
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QMessageBox,
)

from app.presets.loader import PresetManager
from app.models.presets import VisualStylePreset


class StyleThumbnailCard(QFrame):
    """Studio visual card representing an art style with 16:9 thumbnail, badge, and delete option."""

    selected = Signal(str)
    delete_requested = Signal(str, str)  # (style_id, style_name)

    def __init__(
        self,
        style_id: str,
        name: str,
        category: str,
        image_path: Optional[str] = None,
        is_custom: bool = False,
        parent=None
    ):
        super().__init__(parent)
        self.style_id = style_id
        self.style_name = name
        self.category = category
        self.image_path = image_path
        self.is_custom = is_custom
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

        # Image thumbnail container box
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

        img_layout.addWidget(self.img_lbl)

        # Top overlay bar inside thumbnail: Category tag + Delete icon (for custom)
        overlay_bar = QHBoxLayout()
        overlay_bar.setContentsMargins(4, 4, 4, 0)

        # Category pill
        cat_text = self.category if len(self.category) <= 12 else (self.category[:10] + "..")
        self.cat_pill = QLabel(cat_text)
        self.cat_pill.setStyleSheet("""
            background-color: rgba(8, 12, 18, 0.85);
            color: #94A3B8;
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 3px;
            padding: 1px 4px;
            font-size: 9px;
            font-weight: 600;
        """)
        overlay_bar.addWidget(self.cat_pill)
        overlay_bar.addStretch()

        if self.is_custom:
            self.del_btn = QPushButton("✕")
            self.del_btn.setFixedSize(18, 18)
            self.del_btn.setCursor(Qt.PointingHandCursor)
            self.del_btn.setToolTip(f"Delete custom style '{self.style_name}'")
            self.del_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(239, 68, 68, 0.8);
                    color: #FFFFFF;
                    border: none;
                    border-radius: 9px;
                    font-size: 10px;
                    font-weight: bold;
                    padding: 0;
                }
                QPushButton:hover {
                    background-color: #EF4444;
                    color: #FFFFFF;
                }
            """)
            self.del_btn.clicked.connect(self._on_delete_clicked)
            overlay_bar.addWidget(self.del_btn)

        # We nest the overlay_bar directly over the img_container layout
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
        self.status_pill = QLabel("Select")
        self.status_pill.setAlignment(Qt.AlignCenter)
        self.status_pill.setStyleSheet("""
            font-size: 9px;
            color: #64748B;
            padding: 1px 0;
        """)
        layout.addWidget(self.status_pill)

        self._update_style()

    def _on_delete_clicked(self):
        self.delete_requested.emit(self.style_id, self.style_name)

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


class AddStyleCard(QFrame):
    """Clickable '+ Add Custom Style' card displayed at the end of the rack."""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AddStyleCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedWidth(130)
        self.setFixedHeight(175)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            #AddStyleCard {
                background-color: rgba(14, 20, 28, 0.35);
                border: 2px dashed rgba(163, 255, 18, 0.3);
                border-radius: 8px;
            }
            #AddStyleCard:hover {
                border-color: #A3FF12;
                background-color: rgba(16, 185, 129, 0.12);
            }
        """)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(6)

        plus_lbl = QLabel("➕")
        plus_lbl.setAlignment(Qt.AlignCenter)
        plus_lbl.setStyleSheet("font-size: 24px; color: #34D399; background: transparent; border: none;")
        layout.addWidget(plus_lbl)

        txt_lbl = QLabel("Add Custom\nArt Style")
        txt_lbl.setAlignment(Qt.AlignCenter)
        txt_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #CBD5E1; background: transparent; border: none;")
        layout.addWidget(txt_lbl)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class HorizontalScrollArea(QScrollArea):
    """Smooth horizontal scroll area supporting mouse wheel horizontal scrolling."""

    def wheelEvent(self, event: QWheelEvent):
        # Convert vertical wheel scrolling to horizontal scroll for seamless rack navigation
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
    custom style integration, 1-click management, and real-time active indicators.
    """

    style_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_id: str = "century_old_photograph"
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

        self.active_style_badge = QLabel("Century-Old Photograph Active")
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

        # Add Custom Style button in header
        self.add_style_btn = QPushButton("➕ Add Custom Style")
        self.add_style_btn.setCursor(Qt.PointingHandCursor)
        self.add_style_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #059669);
                color: #FFFFFF;
                font-weight: 700;
                font-size: 11px;
                border: 1px solid #34D399;
                border-radius: 5px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #A3FF12, stop:1 #10B981);
                color: #081009;
                border-color: #A3FF12;
            }
        """)
        self.add_style_btn.clicked.connect(self._open_style_creator)
        header_row.addWidget(self.add_style_btn)

        # Manage Styles button
        self.manage_btn = QPushButton("⚙️ Manage Styles")
        self.manage_btn.setCursor(Qt.PointingHandCursor)
        self.manage_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(27, 41, 31, 0.7);
                color: #CBD5E1;
                border: 1px solid rgba(163, 255, 18, 0.2);
                border-radius: 5px;
                padding: 4px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                color: #A3FF12;
                border-color: #34D399;
                background-color: rgba(40, 60, 45, 0.85);
            }
        """)
        self.manage_btn.clicked.connect(self._open_style_manager)
        header_row.addWidget(self.manage_btn)

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
        """Clears and rebuilds style cards from PresetManager."""
        PresetManager.initialize()

        # Clear existing cards
        while self.cards_row_layout.count() > 0:
            item = self.cards_row_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._cards.clear()

        styles: List[VisualStylePreset] = PresetManager.get_all_styles()
        artworks_dir = Path(__file__).resolve().parent.parent.parent.parent / "assets" / "style_previews"

        for s in styles:
            # Locate preview image
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
                is_custom=s.is_custom,
                parent=self.cards_content_widget
            )
            card.selected.connect(self.select_style)
            card.delete_requested.connect(self._on_card_delete_requested)
            self._cards.append(card)
            self.cards_row_layout.addWidget(card)

        # Add the '+ Add Custom Style' card at the end of the rack
        add_card = AddStyleCard(self.cards_content_widget)
        add_card.clicked.connect(self._open_style_creator)
        self.cards_row_layout.addWidget(add_card)

        # Preserve or fall back selection
        existing_ids = [c.style_id for c in self._cards]
        if self._selected_id in existing_ids:
            self.select_style(self._selected_id)
        elif self._cards:
            self.select_style(self._cards[0].style_id)

    def select_style(self, style_id: str):
        """Selects a style and updates active states across all cards."""
        # Normalize aliases
        if style_id in ("vintage_photograph", "vintage_photo", "century_old_photographs"):
            style_id = "century_old_photograph"
        elif style_id in ("stick_figure", "stickman", "red_blue_stickman_3d", "2d_stick_figure"):
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
        selected_name = "Century-Old Photograph"

        for c in self._cards:
            is_match = (c.style_id == style_id)
            c.set_active(is_match)
            if is_match:
                selected_name = c.style_name

        self.active_style_badge.setText(f"★ {selected_name} Active")
        self.style_selected.emit(style_id)

    def current_style_id(self) -> str:
        return self._selected_id

    def _on_card_delete_requested(self, style_id: str, style_name: str):
        reply = QMessageBox.question(
            self,
            "Delete Custom Art Style",
            f"Are you sure you want to permanently delete custom style:\n\n'{style_name}'?\n\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            PresetManager.delete_custom_style(style_id)
            if self._selected_id == style_id:
                self._selected_id = "century_old_photograph"
            self.refresh_styles()
            self.style_selected.emit(self._selected_id)

    def _open_style_creator(self):
        from app.ui.dialogs.preset_editor_dialog import PresetEditorDialog
        dlg = PresetEditorDialog(self)
        dlg._on_new_style()
        dlg.styles_updated.connect(self.refresh_styles)
        dlg.exec()
        self.refresh_styles()

    def _open_style_manager(self):
        from app.ui.dialogs.preset_editor_dialog import PresetEditorDialog
        dlg = PresetEditorDialog(self, initial_style_id=self._selected_id)
        dlg.styles_updated.connect(self.refresh_styles)
        dlg.exec()
        self.refresh_styles()
