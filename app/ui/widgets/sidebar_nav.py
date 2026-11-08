"""
PromptBeast Studio Pro — Master Glassmorphism Sidebar Navigation.
Features unified workflow groupings (CREATE, MANAGE, SYSTEM), subtle stage numbering,
compact collapsible glass sidebar, and Electric Lime active indicator.
"""
from typing import Dict, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QButtonGroup,
    QToolTip,
)
from app.ui.theme import (
    COLOR_BRAND_PRIMARY,
    COLOR_BRAND_EMERALD,
    COLOR_GLASS_SURFACE,
    COLOR_GLASS_SURFACE_2,
    COLOR_HOVER_SURFACE,
    COLOR_BORDER_GREEN,
    COLOR_BORDER_SUBTLE,
    COLOR_BORDER_ACTIVE,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
)


class NavButton(QPushButton):
    """Custom styled sidebar button with stage number, icon, and electric lime indicator."""

    def __init__(
        self,
        key: str,
        title: str,
        icon_str: str,
        num_str: Optional[str] = None,
        parent=None
    ):
        super().__init__(parent)
        self.key = key
        self.title = title
        self.icon_str = icon_str
        self.num_str = num_str
        self._is_collapsed = False

        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(40)
        self.setToolTip(f"{num_str + ' — ' if num_str else ''}{title}")
        self._update_display()

    def set_collapsed(self, collapsed: bool):
        self._is_collapsed = collapsed
        self._update_display()

    def _update_display(self):
        if self._is_collapsed:
            self.setText(self.icon_str)
            self.setStyleSheet(f"""
                QPushButton {{
                    text-align: center;
                    color: {COLOR_TEXT_SECONDARY};
                    font-size: 15px;
                    font-weight: 600;
                    background-color: transparent;
                    border: 1px solid transparent;
                    border-radius: 8px;
                    margin: 2px 4px;
                }}
                QPushButton:hover {{
                    background-color: {COLOR_HOVER_SURFACE};
                    color: {COLOR_TEXT_PRIMARY};
                    border: 1px solid {COLOR_BORDER_SUBTLE};
                }}
                QPushButton:checked {{
                    background-color: rgba(163, 255, 18, 0.12);
                    color: {COLOR_BRAND_PRIMARY};
                    font-weight: 700;
                    border: 1px solid {COLOR_BORDER_GREEN};
                    border-left: 3px solid {COLOR_BRAND_PRIMARY};
                }}
            """)
        else:
            num_part = f"{self.num_str}  " if self.num_str else "    "
            self.setText(f"  {self.icon_str}   {num_part}{self.title}")
            self.setStyleSheet(f"""
                QPushButton {{
                    text-align: left;
                    padding-left: 10px;
                    color: {COLOR_TEXT_SECONDARY};
                    font-size: 13px;
                    font-weight: 500;
                    background-color: transparent;
                    border: 1px solid transparent;
                    border-radius: 8px;
                    margin: 1px 0px;
                }}
                QPushButton:hover {{
                    background-color: {COLOR_HOVER_SURFACE};
                    color: {COLOR_TEXT_PRIMARY};
                    border: 1px solid {COLOR_BORDER_SUBTLE};
                }}
                QPushButton:checked {{
                    background-color: rgba(163, 255, 18, 0.12);
                    color: {COLOR_BRAND_PRIMARY};
                    font-weight: 600;
                    border: 1px solid {COLOR_BORDER_GREEN};
                    border-left: 3px solid {COLOR_BRAND_PRIMARY};
                }}
            """)


class SidebarNav(QWidget):
    """
    Sleek collapsible glass sidebar containing 6 numbered production stages
    grouped under CREATE, MANAGE, and SYSTEM.
    """

    page_changed = Signal(str)  # Emits page key e.g. 'production', 'scene_studio', etc.

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidebarNav")
        self._is_collapsed = False
        self.setFixedWidth(224)

        self._buttons: Dict[str, NavButton] = {}
        self._section_headers: Dict[str, QLabel] = {}
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)

        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet(f"""
            #SidebarNav {{
                background-color: {COLOR_GLASS_SURFACE};
                border-right: 1px solid {COLOR_BORDER_GREEN};
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 14, 10, 14)
        layout.setSpacing(4)

        # App Brand Header
        self.brand_box = QFrame()
        self.brand_box.setStyleSheet("background: transparent; border: none;")
        b_layout = QVBoxLayout(self.brand_box)
        b_layout.setContentsMargins(2, 0, 2, 10)
        b_layout.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        logo_lbl = QLabel("⚡")
        logo_lbl.setStyleSheet(f"font-size: 18px; color: {COLOR_BRAND_PRIMARY};")

        self.name_lbl = QLabel("PROMPTBEAST")
        self.name_lbl.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {COLOR_TEXT_PRIMARY}; letter-spacing: 0.6px;")

        self.pro_badge = QLabel("PRO")
        self.pro_badge.setStyleSheet(f"""
            font-size: 9px;
            font-weight: 800;
            color: {COLOR_BRAND_PRIMARY};
            background: rgba(163, 255, 18, 0.14);
            border: 1px solid rgba(163, 255, 18, 0.4);
            border-radius: 4px;
            padding: 1px 4px;
        """)

        title_row.addWidget(logo_lbl)
        title_row.addWidget(self.name_lbl)
        title_row.addWidget(self.pro_badge)
        title_row.addStretch()
        b_layout.addLayout(title_row)

        self.sub_lbl = QLabel("Studio Pro · AI Video Engine")
        self.sub_lbl.setStyleSheet(f"font-size: 10px; color: {COLOR_TEXT_MUTED}; font-weight: 500; padding-left: 24px;")
        b_layout.addWidget(self.sub_lbl)
        layout.addWidget(self.brand_box)

        # -------------------------------------------------------------
        # UNIFORM NAVIGATION ITEMS (No section divisions, no console)
        # -------------------------------------------------------------
        self._add_nav_item("production", "Production", "🎬", "01", layout)
        self._add_nav_item("studio", "Studio", "🎞️", "02", layout)
        self._add_nav_item("scene_sync", "Scene Sync", "🔄", "03", layout)
        self._add_nav_item("deliverables", "Deliverables", "⚡", "04", layout)
        self._add_nav_item("profiles", "Profiles", "👤", "05", layout)
        self._add_nav_item("settings", "Settings", "⚙️", None, layout)

        layout.addStretch()

        # Bottom Collapse/Expand Toggle
        self.collapse_btn = QPushButton("◀  Collapse Sidebar")
        self.collapse_btn.setFixedHeight(32)
        self.collapse_btn.setCursor(Qt.PointingHandCursor)
        self.collapse_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: 6px;
                color: {COLOR_TEXT_MUTED};
                font-size: 11px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {COLOR_HOVER_SURFACE};
                color: {COLOR_TEXT_PRIMARY};
                border-color: {COLOR_BORDER_GREEN};
            }}
        """)
        self.collapse_btn.clicked.connect(self.toggle_collapse)
        layout.addWidget(self.collapse_btn)

        # Default active page: Production
        if "production" in self._buttons:
            self._buttons["production"].setChecked(True)

    def _add_section_header(self, text: str, layout: QVBoxLayout):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            font-size: 10px;
            font-weight: 700;
            color: {COLOR_TEXT_MUTED};
            letter-spacing: 0.8px;
            margin-top: 6px;
            margin-bottom: 2px;
            padding-left: 8px;
        """)
        self._section_headers[text] = lbl
        layout.addWidget(lbl)

    def _add_nav_item(self, key: str, text: str, icon_str: str, num_str: Optional[str], layout: QVBoxLayout):
        btn = NavButton(key, text, icon_str, num_str, self)
        btn.clicked.connect(lambda: self._on_btn_clicked(key))
        self._button_group.addButton(btn)
        self._buttons[key] = btn
        layout.addWidget(btn)

    def _on_btn_clicked(self, key: str):
        self.page_changed.emit(key)

    def set_current_page(self, key: str):
        """
        Activates the navigation button corresponding to key.
        Provides robust backward compatibility mapping for aliases.
        """
        # Backward compatibility aliases
        key_map = {
            "scene_studio": "studio",
            "audio_subtitles": "production",
            "final_render": "deliverables",
            "projects_exports": "production",
            "profiles_accounts": "profiles",
        }
        target_key = key_map.get(key, key)

        if target_key in self._buttons:
            self._buttons[target_key].setChecked(True)
            self.page_changed.emit(target_key)

    def toggle_collapse(self):
        self._is_collapsed = not self._is_collapsed
        if self._is_collapsed:
            self.setFixedWidth(64)
            self.name_lbl.setVisible(False)
            self.pro_badge.setVisible(False)
            self.sub_lbl.setVisible(False)
            for h in self._section_headers.values():
                h.setVisible(False)
            self.collapse_btn.setText("▶")
            self.collapse_btn.setToolTip("Expand Sidebar")
        else:
            self.setFixedWidth(224)
            self.name_lbl.setVisible(True)
            self.pro_badge.setVisible(True)
            self.sub_lbl.setVisible(True)
            for h in self._section_headers.values():
                h.setVisible(True)
            self.collapse_btn.setText("◀  Collapse Sidebar")
            self.collapse_btn.setToolTip("Collapse Sidebar")

        for btn in self._buttons.values():
            btn.set_collapsed(self._is_collapsed)
