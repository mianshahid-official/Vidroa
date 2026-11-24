"""
FrameForge-Inspired Cinematic Red & Black Design System.
Cinematic dark canvas (#101010) with dominant Crimson Red accents (#E53935, #FF4B4B, #B71C1C),
clean neutral panels (#181818, #222222), and zero unwanted borders around text labels.
"""

# =============================================================================
# DESIGN TOKENS
# =============================================================================

# Primary Brand Colors (FrameForge Red & Black)
COLOR_BRAND_PRIMARY = "#E53935"      # Crimson Red (Primary Brand & CTA)
COLOR_BRAND_ACCENT  = "#FF4B4B"      # Vibrant Accent Red
COLOR_BRAND_DARK    = "#B71C1C"      # Deep Blood Red
COLOR_BRAND_DEEP    = "#8A1212"      # Deepest Crimson Red
COLOR_BRAND_HOVER   = "#FF5252"      # Bright Red on Hover
COLOR_BRAND_PRESSED = "#D32F2F"      # Pressed Red State
COLOR_BRAND_DIM     = "rgba(229, 57, 53, 0.15)"
COLOR_BRAND_BORDER  = "rgba(229, 57, 53, 0.40)"
COLOR_BRAND_EMERALD = "#4CAF50"      # Success Green
COLOR_BRAND_MINT    = "#81C784"

# Dark Backgrounds
COLOR_BG_MAIN       = "#101010"      # Main dark canvas
COLOR_BG_SECONDARY  = "#151515"      # Sidebar & dark secondary surface
COLOR_BG_WORKSPACE  = "#181818"      # Workspace background
COLOR_GLASS_SURFACE = "#1B1B1B"      # Panels & containers
COLOR_GLASS_SURFACE_2 = "#222222"    # Elevated cards, input backings
COLOR_HOVER_SURFACE = "#282828"      # Subtle hover layer

# Borders
COLOR_BORDER_SUBTLE = "#2A2A2A"      # Subtle dividers
COLOR_BORDER_DEFAULT= "#333333"      # Card & field borders
COLOR_BORDER_GREEN  = "rgba(229, 57, 53, 0.30)" # Mapped to brand red border
COLOR_BORDER_ACTIVE = "#E53935"      # Active / focused red border

# Typography
COLOR_TEXT_PRIMARY   = "#F5F5F5"
COLOR_TEXT_SECONDARY = "#A0A0A0"
COLOR_TEXT_MUTED     = "#707070"

# Status
COLOR_STATUS_SUCCESS = "#4CAF50"
COLOR_STATUS_WARNING = "#FFB74D"
COLOR_STATUS_ERROR   = "#EF5350"
COLOR_STATUS_DISABLED= "#555555"

# =============================================================================
# MASTER QSS STYLESHEET
# =============================================================================

DARK_THEME_QSS = f"""
/* =========================================================================
   CINEMATIC RED & BLACK THEME (FRAMEFORGE DESIGN SYSTEM)
   Canvas: {COLOR_BG_MAIN} | Surface: {COLOR_GLASS_SURFACE} | Primary: {COLOR_BRAND_PRIMARY}
   ========================================================================= */

* {{
    font-family: "Segoe UI", "Inter", -apple-system, BlinkMacSystemFont, "Roboto", sans-serif;
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
    selection-color: #FFFFFF;
}}

/* STRICT NO BORDERS ON LABELS ACROSS ENTIRE APPLICATION */
QLabel {{
    background: transparent;
    background-color: transparent;
    border: none;
    outline: none;
    color: {COLOR_TEXT_PRIMARY};
}}

/* Toolbars & Menus */
QMenuBar {{
    background-color: {COLOR_BG_MAIN};
    border-bottom: 1px solid {COLOR_BORDER_SUBTLE};
    padding: 2px 6px;
    color: {COLOR_TEXT_SECONDARY};
}}

QMenuBar::item {{
    background-color: transparent;
    padding: 6px 12px;
    border-radius: 4px;
    color: {COLOR_TEXT_SECONDARY};
    font-weight: 500;
}}

QMenuBar::item:selected {{
    background-color: {COLOR_GLASS_SURFACE_2};
    color: {COLOR_BRAND_PRIMARY};
}}

QMenu {{
    background-color: {COLOR_BG_SECONDARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: 6px;
    padding: 4px;
}}

QMenu::item {{
    padding: 7px 24px 7px 12px;
    border-radius: 4px;
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
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: 8px;
}}

QFrame.glass-subtle {{
    background-color: {COLOR_GLASS_SURFACE_2};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: 8px;
}}

/* Inputs: LineEdits, TextEdits, PlainTextEdits */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {COLOR_BG_WORKSPACE};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: 6px;
    padding: 7px 11px;
    color: {COLOR_TEXT_PRIMARY};
    font-size: 13px;
}}

QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
    border: 1px solid #444444;
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {COLOR_BORDER_ACTIVE};
    background-color: #1E1E1E;
}}

QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
    background-color: #121212;
    color: {COLOR_STATUS_DISABLED};
    border-color: #252525;
}}

/* Combobox */
QComboBox {{
    background-color: {COLOR_GLASS_SURFACE_2};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: 6px;
    padding: 6px 12px;
    color: {COLOR_TEXT_PRIMARY};
    padding-right: 28px;
    min-height: 24px;
    font-weight: 500;
}}

QComboBox:hover {{
    border-color: #444444;
    background-color: #262626;
}}

QComboBox:focus {{
    border: 1px solid {COLOR_BORDER_ACTIVE};
    background-color: #1E1E1E;
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: none;
    background: transparent;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {COLOR_TEXT_SECONDARY};
    margin-right: 8px;
}}

QComboBox QAbstractItemView,
QComboBox QListView,
QListView {{
    background-color: {COLOR_BG_SECONDARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: 6px;
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
    border-radius: 4px;
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
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: 6px;
    padding: 7px 16px;
    font-size: 13px;
    font-weight: 600;
    color: {COLOR_TEXT_PRIMARY};
}}

QPushButton:hover {{
    background-color: {COLOR_HOVER_SURFACE};
    border-color: #555555;
    color: #FFFFFF;
}}

QPushButton:pressed {{
    background-color: {COLOR_BG_MAIN};
    border-color: {COLOR_BRAND_PRIMARY};
    color: {COLOR_BRAND_PRIMARY};
}}

QPushButton:disabled {{
    background-color: #141414;
    color: {COLOR_STATUS_DISABLED};
    border-color: #242424;
}}

/* Primary Brand Button (FrameForge Crimson CTA) */
QPushButton.primary-btn, QPushButton#PrimaryBtn {{
    background-color: {COLOR_BRAND_PRIMARY};
    color: #FFFFFF;
    border: 1px solid {COLOR_BRAND_ACCENT};
    border-radius: 6px;
    font-weight: 700;
    font-size: 13px;
    padding: 8px 18px;
}}

QPushButton.primary-btn:hover, QPushButton#PrimaryBtn:hover {{
    background-color: {COLOR_BRAND_HOVER};
    border-color: #FF7070;
    color: #FFFFFF;
}}

QPushButton.primary-btn:pressed, QPushButton#PrimaryBtn:pressed {{
    background-color: {COLOR_BRAND_PRESSED};
    border-color: {COLOR_BRAND_DARK};
}}

QPushButton.primary-btn:disabled, QPushButton#PrimaryBtn:disabled {{
    background-color: #2A2A2A;
    color: {COLOR_STATUS_DISABLED};
    border-color: #333333;
}}

/* Secondary Subdued Button */
QPushButton.secondary-btn {{
    background-color: {COLOR_GLASS_SURFACE_2};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    color: {COLOR_TEXT_SECONDARY};
    border-radius: 6px;
    padding: 6px 14px;
}}

QPushButton.secondary-btn:hover {{
    background-color: {COLOR_HOVER_SURFACE};
    color: {COLOR_TEXT_PRIMARY};
    border-color: #444444;
}}

/* Destructive / Stop Button */
QPushButton.destructive-btn, QPushButton#StopBtn {{
    background-color: rgba(239, 83, 80, 0.15);
    color: {COLOR_STATUS_ERROR};
    border: 1px solid rgba(239, 83, 80, 0.40);
    border-radius: 6px;
    font-weight: 600;
    padding: 6px 14px;
}}

QPushButton.destructive-btn:hover, QPushButton#StopBtn:hover {{
    background-color: {COLOR_STATUS_ERROR};
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
    width: 8px;
    margin: 0;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background: #333333;
    min-height: 24px;
    border-radius: 4px;
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
    height: 8px;
    margin: 0;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal {{
    background: #333333;
    min-width: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {COLOR_BRAND_PRIMARY};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* Progress Bar */
QProgressBar {{
    background-color: {COLOR_BG_WORKSPACE};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: 6px;
    text-align: center;
    color: {COLOR_TEXT_PRIMARY};
    font-size: 11px;
    font-weight: 600;
    height: 18px;
}}

QProgressBar::chunk {{
    background-color: {COLOR_BRAND_PRIMARY};
    border-radius: 5px;
}}

/* Status Bar */
QStatusBar {{
    background-color: {COLOR_BG_MAIN};
    border-top: 1px solid {COLOR_BORDER_SUBTLE};
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
    background-color: rgba(76, 175, 80, 0.15);
    color: {COLOR_STATUS_SUCCESS};
    border: 1px solid rgba(76, 175, 80, 0.40);
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}

QLabel.badge-lime, QLabel.badge-red {{
    background-color: rgba(229, 57, 53, 0.15);
    color: {COLOR_BRAND_ACCENT};
    border: 1px solid rgba(229, 57, 53, 0.40);
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 700;
}}

/* Sliders */
QSlider::groove:horizontal {{
    height: 6px;
    background: {COLOR_BG_WORKSPACE};
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

/* Tab Widget */
QTabWidget::pane {{
    border: 1px solid {COLOR_BORDER_DEFAULT};
    background-color: {COLOR_GLASS_SURFACE};
    border-radius: 8px;
    top: -1px;
}}

QTabBar::tab {{
    background-color: {COLOR_GLASS_SURFACE_2};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    color: {COLOR_TEXT_MUTED};
    padding: 6px 16px;
    margin-right: 3px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 600;
    font-size: 12px;
}}

QTabBar::tab:selected {{
    background-color: {COLOR_GLASS_SURFACE};
    border-color: {COLOR_BORDER_DEFAULT};
    color: #FFFFFF;
    border-bottom: 2px solid {COLOR_BRAND_PRIMARY};
}}

QTabBar::tab:hover:!selected {{
    background-color: {COLOR_HOVER_SURFACE};
    color: {COLOR_TEXT_PRIMARY};
}}

/* Table Views */
QTableWidget, QTableView {{
    background-color: {COLOR_BG_WORKSPACE};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: 8px;
    gridline-color: rgba(255, 255, 255, 0.05);
    color: {COLOR_TEXT_PRIMARY};
    selection-background-color: {COLOR_GLASS_SURFACE_2};
    selection-color: {COLOR_BRAND_PRIMARY};
}}

QHeaderView::section {{
    background-color: {COLOR_BG_SECONDARY};
    color: {COLOR_TEXT_SECONDARY};
    padding: 8px;
    font-weight: 600;
    font-size: 11px;
    border: none;
    border-bottom: 1px solid {COLOR_BORDER_DEFAULT};
}}

/* Splitters */
QSplitter::handle {{
    background-color: {COLOR_BORDER_SUBTLE};
}}

QSplitter::handle:hover {{
    background-color: {COLOR_BRAND_PRIMARY};
}}

/* Tooltips */
QToolTip {{
    background-color: #222222;
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BRAND_PRIMARY};
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 12px;
}}
"""
