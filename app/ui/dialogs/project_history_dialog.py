"""
Project History and Workspace Manager Dialog.
Allows users to browse, search, view status, and open/resume any project from history or disk.
"""
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QFileDialog,
    QFrame,
    QAbstractItemView,
)

from app.core.project_manager import ProjectManager
from app.config.settings import SettingsManager


class ProjectHistoryDialog(QDialog):
    """Modern dark-themed Project History & Workspace Browser."""

    def __init__(self, workspace_dir: str, parent=None):
        super().__init__(parent)
        self.workspace_dir = workspace_dir
        self.selected_project_dir: Optional[str] = None
        self.projects_data: List[Dict[str, Any]] = []

        self.setWindowTitle("Project History & Workspace Manager")
        self.setMinimumSize(880, 520)
        self.resize(960, 560)

        self._setup_ui()
        self._load_projects()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header Bar
        header_layout = QHBoxLayout()
        title = QLabel("📁 <b>Projects & Generation History</b>")
        title.setStyleSheet("font-size: 16px; color: #38bdf8; font-weight: 700;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        ws_label = QLabel(f"<span style='color: #64748b;'>Workspace:</span> <span style='color: #cbd5e1;'>{self.workspace_dir}</span>")
        ws_label.setStyleSheet("font-size: 11px;")
        header_layout.addWidget(ws_label)

        layout.addLayout(header_layout)

        # Search / Filter Bar
        filter_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filter projects by name or status...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #1e293b;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
            }
        """)
        self.search_input.textChanged.connect(self._filter_table)
        filter_layout.addWidget(self.search_input)

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setFixedHeight(34)
        refresh_btn.setStyleSheet("background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155; border-radius: 6px; padding: 0 14px; font-weight: 600;")
        refresh_btn.clicked.connect(self._load_projects)
        filter_layout.addWidget(refresh_btn)

        layout.addLayout(filter_layout)

        # Projects Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Project Name", "Status", "Voiceover Audio", "Scenes", "Last Modified", "Folder Path"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #0b0f19;
                alternate-background-color: #0f172a;
                gridline-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #1e293b;
                border-radius: 6px;
                font-size: 12px;
            }
            QTableWidget::item:selected {
                background-color: #1e3a8a;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #1e293b;
                color: #94a3b8;
                padding: 6px 10px;
                border: 1px solid #0f172a;
                font-weight: 600;
                font-size: 11px;
            }
        """)
        self.table.itemDoubleClicked.connect(lambda item: self._on_open_selected())
        self.table.setColumnWidth(0, 220)
        layout.addWidget(self.table)

        # Action Buttons Bottom Bar
        btn_layout = QHBoxLayout()

        browse_btn = QPushButton("📂 Browse Other Folder...")
        browse_btn.setFixedHeight(36)
        browse_btn.setStyleSheet("background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155; border-radius: 6px; padding: 0 14px;")
        browse_btn.clicked.connect(self._on_browse_folder)
        btn_layout.addWidget(browse_btn)

        explorer_btn = QPushButton("📁 Show in Explorer")
        explorer_btn.setFixedHeight(36)
        explorer_btn.setStyleSheet("background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155; border-radius: 6px; padding: 0 14px;")
        explorer_btn.clicked.connect(self._on_show_in_explorer)
        btn_layout.addWidget(explorer_btn)

        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet("background-color: #1e293b; color: #94a3b8; border: 1px solid #334155; border-radius: 6px; padding: 0 16px;")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self.open_btn = QPushButton("🚀 Open / Resume Project")
        self.open_btn.setFixedHeight(36)
        self.open_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                border: 1px solid #3b82f6;
                border-radius: 6px;
                padding: 0 20px;
                font-weight: 700;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        self.open_btn.clicked.connect(self._on_open_selected)
        btn_layout.addWidget(self.open_btn)

        layout.addLayout(btn_layout)

    def _load_projects(self):
        """Scans workspace and settings for all available projects."""
        self.projects_data = ProjectManager.scan_projects(self.workspace_dir)
        self._populate_table(self.projects_data)

    def _populate_table(self, projects: List[Dict[str, Any]]):
        self.table.setRowCount(0)
        for row, p in enumerate(projects):
            self.table.insertRow(row)

            # Name
            name_item = QTableWidgetItem(p["name"])
            name_item.setData(Qt.ItemDataRole.UserRole, p["dir_path"])
            name_item.setForeground(Qt.GlobalColor.white)
            self.table.setItem(row, 0, name_item)

            # Status Badge
            status_item = QTableWidgetItem(p["status_text"])
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if "Complete" in p["status_text"]:
                status_item.setForeground(Qt.GlobalColor.green)
            elif "Storyboard Ready" in p["status_text"] or "Voiceover Ready" in p["status_text"]:
                status_item.setForeground(Qt.GlobalColor.yellow)
            elif "Interrupted" in p["status_text"] or "Incomplete" in p["status_text"]:
                status_item.setForeground(Qt.GlobalColor.magenta)
            else:
                status_item.setForeground(Qt.GlobalColor.gray)
            self.table.setItem(row, 1, status_item)

            # Voiceover
            vo_text = p.get("audio_text", "None")
            vo_item = QTableWidgetItem(vo_text)
            vo_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, vo_item)

            # Scenes
            scenes_text = f"{p.get('scene_count', 0)} scenes"
            scenes_item = QTableWidgetItem(scenes_text)
            scenes_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, scenes_item)

            # Modified
            mod_item = QTableWidgetItem(p.get("modified_str", "—"))
            mod_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 4, mod_item)

            # Path
            path_item = QTableWidgetItem(p["dir_path"])
            path_item.setForeground(Qt.GlobalColor.gray)
            self.table.setItem(row, 5, path_item)

        if projects:
            self.table.selectRow(0)

    def _filter_table(self, text: str):
        search = text.strip().lower()
        if not search:
            self._populate_table(self.projects_data)
            return

        filtered = [
            p for p in self.projects_data
            if search in p["name"].lower()
            or search in p["status_text"].lower()
            or search in p["dir_path"].lower()
        ]
        self._populate_table(filtered)

    def _on_open_selected(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a project to open.")
            return

        item = self.table.item(row, 0)
        if not item:
            return

        self.selected_project_dir = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def _on_browse_folder(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Open Project Directory", self.workspace_dir)
        if dir_path:
            self.selected_project_dir = dir_path
            self.accept()

    def _on_show_in_explorer(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a project row first.")
            return

        item = self.table.item(row, 0)
        if not item:
            return

        proj_path = Path(item.data(Qt.ItemDataRole.UserRole))
        if proj_path.exists():
            try:
                if os.name == 'nt':
                    subprocess.run(["explorer", str(proj_path.resolve())], check=False)
                else:
                    subprocess.run(["xdg-open", str(proj_path.resolve())], check=False)
            except Exception as e:
                QMessageBox.warning(self, "Explorer Error", f"Could not open folder: {e}")
        else:
            QMessageBox.warning(self, "Path Missing", f"Folder not found: {proj_path}")
