"""
PromptBeast Studio Pro — Master Green Glassmorphism Design System.
Cinematic dark interface with Electric Lime (#A3FF12), Emerald (#10B981), Mint (#34D399),
and deep forest green translucent glass surfaces.
"""

# =============================================================================
# DESIGN TOKENS
# =============================================================================

# Primary Brand Colors
COLOR_BRAND_PRIMARY = "#A3FF12"      # Electric Lime (Primary Brand & CTA)
COLOR_BRAND_EMERALD = "#10B981"      # Emerald (Success & Accents)
COLOR_BRAND_MINT    = "#34D399"      # Mint (Highlights & Active)
COLOR_BRAND_DEEP    = "#064E3B"      # Deep Green (Shadows & Accents)

# Dark Backgrounds
COLOR_BG_MAIN       = "#080D0B"      # Main dark canvas
COLOR_BG_SECONDARY  = "#0D1510"      # Secondary dark surface
COLOR_BG_WORKSPACE  = "#111B14"      # Workspace background
COLOR_GLASS_SURFACE = "rgba(20, 32, 24, 0.76)"
COLOR_GLASS_SURFACE_2 = "rgba(27, 41, 31, 0.68)"
COLOR_HOVER_SURFACE = "rgba(40, 57, 43, 0.78)"

# Glass Borders
COLOR_BORDER_SUBTLE = "rgba(255, 255, 255, 0.08)"
COLOR_BORDER_GREEN  = "rgba(163, 255, 18, 0.12)"
COLOR_BORDER_ACTIVE = "rgba(163, 255, 18, 0.55)"

# Typography
COLOR_TEXT_PRIMARY   = "#F0F5F0"
COLOR_TEXT_SECONDARY = "#B1BDB3"
COLOR_TEXT_MUTED     = "#89978D"

# Status
COLOR_STATUS_SUCCESS = "#34D399"
COLOR_STATUS_WARNING = "#FBBF24"
COLOR_STATUS_ERROR   = "#FF647C"
COLOR_STATUS_DISABLED= "#667269"

# =============================================================================
# MASTER QSS STYLESHEET
# =============================================================================

DARK_THEME_QSS = f"""
/* =========================================================================
   PROMPTBEAST STUDIO PRO — MASTER GREEN GLASSMORPHISM THEME
   Canvas: {COLOR_BG_MAIN} | Surface: {COLOR_GLASS_SURFACE} | Primary: {COLOR_BRAND_PRIMARY}
   ========================================================================= */

* {{
    font-family: "Inter", "Segoe UI", -apple-system, BlinkMacSystemFont, "Roboto", sans-serif;
    font-size: 13px;
    color: {COLOR_TEXT_PRIMARY};
    outline: none;
}}

QMainWindow, QDialog {{
    background-color: {COLOR_BG_MAIN};
    color: {COLOR_TEXT_PRIMARY};
}}

QWidget {{
    background-color: transparent;
    selection-background-color: {COLOR_BRAND_PRIMARY};
    selection-color: #081009;
}}

/* Toolbars & Menus */
QMenuBar {{
    background-color: {COLOR_BG_MAIN};
    border-bottom: 1px solid {COLOR_BORDER_GREEN};
    padding: 2px 6px;
    color: {COLOR_TEXT_SECONDARY};
}}

QMenuBar::item {{
    background-color: transparent;
    padding: 6px 12px;
    border-radius: 6px;
    color: {COLOR_TEXT_SECONDARY};
    font-weight: 500;
}}

QMenuBar::item:selected {{
    background-color: {COLOR_GLASS_SURFACE_2};
    color: {COLOR_BRAND_PRIMARY};
}}

QMenu {{
    background-color: {COLOR_BG_SECONDARY};
    border: 1px solid {COLOR_BORDER_GREEN};
    border-radius: 8px;
    padding: 4px;
}}

QMenu::item {{
    padding: 7px 24px 7px 12px;
    border-radius: 6px;
    color: {COLOR_TEXT_PRIMARY};
    font-size: 12px;
}}

QMenu::item:selected {{
    background-color: {COLOR_HOVER_SURFACE};
    color: {COLOR_BRAND_PRIMARY};
}}

QMenu::separator {{
    height: 1px;
    background-color: {COLOR_BORDER_SUBTLE};
    margin: 4px 6px;
}}

/* Glass Panels & Unified Workspaces */
QFrame.glass, QWidget.glass {{
    background-color: {COLOR_GLASS_SURFACE};
    border: 1px solid {COLOR_BORDER_GREEN};
    border-radius: 12px;
}}

QFrame.glass-subtle {{
    background-color: {COLOR_GLASS_SURFACE_2};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: 10px;
}}

/* Inputs: LineEdits, TextEdits, PlainTextEdits */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {COLOR_BG_SECONDARY};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: 8px;
    padding: 7px 11px;
    color: {COLOR_TEXT_PRIMARY};
    font-size: 13px;
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {COLOR_BORDER_ACTIVE};
    background-color: {COLOR_BG_WORKSPACE};
}}

QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
    background-color: #060907;
    color: {COLOR_STATUS_DISABLED};
    border-color: rgba(255, 255, 255, 0.04);
}}

/* Combobox */
QComboBox {{
    background-color: {COLOR_GLASS_SURFACE_2};
    border: 1px solid {COLOR_BORDER_GREEN};
    border-radius: 8px;
    padding: 6px 12px;
    color: {COLOR_TEXT_PRIMARY};
    padding-right: 28px;
    min-height: 22px;
    font-weight: 500;
}}

QComboBox:hover {{
    border-color: {COLOR_BORDER_ACTIVE};
    background-color: {COLOR_HOVER_SURFACE};
}}

QComboBox:focus {{
    border: 1px solid {COLOR_BORDER_ACTIVE};
    background-color: {COLOR_BG_WORKSPACE};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border-left: none;
    background: transparent;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {COLOR_TEXT_SECONDARY};
    margin-right: 10px;
}}

QComboBox QAbstractItemView,
QComboBox QListView,
QListView {{
    background-color: {COLOR_BG_SECONDARY};
    border: 1px solid {COLOR_BORDER_GREEN};
    border-radius: 8px;
    selection-background-color: {COLOR_HOVER_SURFACE};
    selection-color: {COLOR_BRAND_PRIMARY};
    color: {COLOR_TEXT_PRIMARY};
    padding: 6px;
    outline: none;
}}

QComboBox QAbstractItemView::item,
QListView::item {{
    background-color: transparent;
    color: {COLOR_TEXT_PRIMARY};
    padding: 8px 12px;
    min-height: 24px;
    border-radius: 6px;
}}

QComboBox QAbstractItemView::item:selected,
QListView::item:selected {{
    background-color: {COLOR_GLASS_SURFACE_2};
    color: {COLOR_BRAND_PRIMARY};
    font-weight: 600;
}}

QComboBox QAbstractItemView::item:hover,
QListView::item:hover {{
    background-color: {COLOR_HOVER_SURFACE};
    color: #FFFFFF;
}}

/* Default Buttons */
QPushButton {{
    background-color: {COLOR_GLASS_SURFACE_2};
    border: 1px solid {COLOR_BORDER_GREEN};
    border-radius: 8px;
    padding: 7px 14px;
    font-size: 13px;
    font-weight: 500;
    color: {COLOR_TEXT_PRIMARY};
}}

QPushButton:hover {{
    background-color: {COLOR_HOVER_SURFACE};
    border-color: {COLOR_BORDER_ACTIVE};
    color: #FFFFFF;
}}

QPushButton:pressed {{
    background-color: {COLOR_BG_MAIN};
    color: {COLOR_BRAND_PRIMARY};
}}

QPushButton:disabled {{
    background-color: #060907;
    color: {COLOR_STATUS_DISABLED};
    border-color: rgba(255, 255, 255, 0.04);
}}

/* Primary Brand Button (Electric Lime CTA) */
QPushButton.primary-btn, QPushButton#PrimaryBtn {{
    background-color: {COLOR_BRAND_PRIMARY};
    color: #081009;
    border: 1px solid {COLOR_BRAND_PRIMARY};
    border-radius: 8px;
    font-weight: 700;
    font-size: 13px;
    padding: 8px 18px;
}}

QPushButton.primary-btn:hover, QPushButton#PrimaryBtn:hover {{
    background-color: #B4FF33;
    border-color: #B4FF33;
    color: #000000;
}}

QPushButton.primary-btn:pressed, QPushButton#PrimaryBtn:pressed {{
    background-color: #8CE60A;
    border-color: #8CE60A;
}}

QPushButton.primary-btn:disabled, QPushButton#PrimaryBtn:disabled {{
    background-color: rgba(163, 255, 18, 0.15);
    color: {COLOR_STATUS_DISABLED};
    border-color: rgba(163, 255, 18, 0.2);
}}

/* Secondary Subdued Button */
QPushButton.secondary-btn {{
    background-color: {COLOR_GLASS_SURFACE_2};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    color: {COLOR_TEXT_SECONDARY};
    border-radius: 8px;
    padding: 6px 14px;
}}

QPushButton.secondary-btn:hover {{
    background-color: {COLOR_HOVER_SURFACE};
    color: {COLOR_TEXT_PRIMARY};
    border-color: {COLOR_BORDER_GREEN};
}}

/* Destructive / Stop Button */
QPushButton.destructive-btn, QPushButton#StopBtn {{
    background-color: rgba(255, 100, 124, 0.12);
    color: {COLOR_STATUS_ERROR};
    border: 1px solid rgba(255, 100, 124, 0.45);
    border-radius: 8px;
    font-weight: 600;
    padding: 6px 14px;
}}

QPushButton.destructive-btn:hover, QPushButton#StopBtn:hover {{
    background-color: rgba(255, 100, 124, 0.25);
    color: #FFFFFF;
}}

/* Scroll Area & Minimalist Scrollbars */
QScrollArea {{
    background-color: transparent;
    border: none;
}}

QScrollBar:vertical {{
    border: none;
    background: {COLOR_BG_MAIN};
    width: 6px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: rgba(255, 255, 255, 0.15);
    min-height: 28px;
    border-radius: 3px;
}}

QScrollBar::handle:vertical:hover {{
    background: {COLOR_BRAND_PRIMARY};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    border: none;
    background: {COLOR_BG_MAIN};
    height: 6px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background: rgba(255, 255, 255, 0.15);
    min-width: 28px;
    border-radius: 3px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {COLOR_BRAND_PRIMARY};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* Progress Bar */
QProgressBar {{
    background-color: {COLOR_BG_SECONDARY};
    border: 1px solid {COLOR_BORDER_GREEN};
    border-radius: 6px;
    text-align: center;
    color: {COLOR_TEXT_PRIMARY};
    font-size: 11px;
    font-weight: 600;
    height: 16px;
}}

QProgressBar::chunk {{
    background-color: {COLOR_BRAND_PRIMARY};
    border-radius: 5px;
}}

/* Status Bar */
QStatusBar {{
    background-color: {COLOR_BG_MAIN};
    border-top: 1px solid {COLOR_BORDER_GREEN};
    color: {COLOR_TEXT_SECONDARY};
    padding: 4px 12px;
    font-size: 12px;
}}

/* Typography Classes */
QLabel.heading {{
    font-size: 16px;
    font-weight: 700;
    color: {COLOR_TEXT_PRIMARY};
    letter-spacing: 0.3px;
}}

QLabel.subheading {{
    font-size: 13px;
    color: {COLOR_TEXT_SECONDARY};
}}

QLabel.muted {{
    font-size: 12px;
    color: {COLOR_TEXT_MUTED};
}}

QLabel.badge-green {{
    background-color: rgba(16, 185, 129, 0.15);
    color: {COLOR_BRAND_MINT};
    border: 1px solid rgba(16, 185, 129, 0.35);
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}}

QLabel.badge-lime {{
    background-color: rgba(163, 255, 18, 0.14);
    color: {COLOR_BRAND_PRIMARY};
    border: 1px solid rgba(163, 255, 18, 0.35);
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 700;
}}

/* Sliders */
QSlider::groove:horizontal {{
    height: 6px;
    background: {COLOR_BG_SECONDARY};
    border-radius: 3px;
}}

QSlider::sub-page:horizontal {{
    background: {COLOR_BRAND_PRIMARY};
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background: #FFFFFF;
    border: 2px solid {COLOR_BRAND_PRIMARY};
    width: 16px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 8px;
}}

QSlider::handle:horizontal:hover {{
    background: {COLOR_BRAND_PRIMARY};
    border-color: #FFFFFF;
}}

/* Tab Widget (When tabs are used internally) */
QTabWidget::pane {{
    border: 1px solid {COLOR_BORDER_GREEN};
    background-color: {COLOR_GLASS_SURFACE};
    border-radius: 10px;
    top: -1px;
}}

QTabBar::tab {{
    background-color: {COLOR_GLASS_SURFACE_2};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    color: {COLOR_TEXT_MUTED};
    padding: 8px 18px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: 600;
    font-size: 12px;
}}

QTabBar::tab:selected {{
    background-color: {COLOR_GLASS_SURFACE};
    border-color: {COLOR_BORDER_GREEN};
    color: {COLOR_BRAND_PRIMARY};
    border-bottom: 2px solid {COLOR_BRAND_PRIMARY};
}}

QTabBar::tab:hover:!selected {{
    background-color: {COLOR_HOVER_SURFACE};
    color: {COLOR_TEXT_PRIMARY};
}}

/* Table Views */
QTableWidget, QTableView {{
    background-color: {COLOR_BG_SECONDARY};
    border: 1px solid {COLOR_BORDER_GREEN};
    border-radius: 10px;
    gridline-color: rgba(255, 255, 255, 0.05);
    color: {COLOR_TEXT_PRIMARY};
    selection-background-color: {COLOR_GLASS_SURFACE_2};
    selection-color: {COLOR_BRAND_PRIMARY};
}}

QHeaderView::section {{
    background-color: {COLOR_BG_WORKSPACE};
    color: {COLOR_TEXT_SECONDARY};
    padding: 8px;
    font-weight: 600;
    font-size: 11px;
    border: none;
    border-bottom: 1px solid {COLOR_BORDER_GREEN};
}}

/* Splitters */
QSplitter::handle {{
    background-color: {COLOR_BORDER_GREEN};
}}

QSplitter::handle:hover {{
    background-color: {COLOR_BRAND_PRIMARY};
}}

/* Tooltips */
QToolTip {{
    background-color: #0A110D;
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER_GREEN};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}
"""
