"""
Settings and Profiles Unified Full-Page Management for PromptBeast.
Combines Google/Chrome Browser Profiles (acc1..acc6), Groq Multi-Key Engine configuration,
workspace directories, and automatic cleanup of incomplete projects (no rendered MP4).
"""

import os
import shutil
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QFrame,
    QTabWidget,
    QGroupBox,
    QMessageBox,
    QScrollArea,
    QFileDialog,
    QPlainTextEdit,
)

from app.config.settings import AppSettings, SettingsManager
from app.ai.groq_engine import get_groq_engine
from app.ui.widgets.custom_combo import PBComboBox
from app.ui.widgets.profiles_panel import ProfilesManagerPanel


class SettingsProfilesPage(QWidget):
    """Full-page unified Settings and Profiles management view."""

    navigate_back = Signal()
    settings_saved = Signal(AppSettings)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = SettingsManager.load_settings()
        self.raw_api_keys: List[str] = []
        self._load_groq_keys()
        self._init_ui()

    def refresh_view(self):
        """Refreshes settings from disk and updates fields and profiles."""
        self.settings = SettingsManager.load_settings()
        self._load_groq_keys()
        if hasattr(self, "keys_edit"):
            self.keys_edit.setPlainText("\n".join(self.raw_api_keys))
        if hasattr(self, "ws_input"):
            self.ws_input.setText(self.settings.workspace_directory)
        if hasattr(self, "pexels_input"):
            self.pexels_input.setText(self.settings.pexels_api_key or "")
        if hasattr(self, "pixabay_input"):
            self.pixabay_input.setText(self.settings.pixabay_api_key or "")
        if hasattr(self, "profiles_panel"):
            self.profiles_panel.refresh_profiles()

    def _load_groq_keys(self):
        self.raw_api_keys = []
        if hasattr(self.settings, "api_keys") and self.settings.api_keys:
            for k in self.settings.api_keys:
                if k and k.strip() and k.strip() not in self.raw_api_keys:
                    self.raw_api_keys.append(k.strip())
        if self.settings.api_key and self.settings.api_key.strip():
            k = self.settings.api_key.strip()
            if k not in self.raw_api_keys:
                self.raw_api_keys.append(k)
        try:
            groq = get_groq_engine()
            for k in groq.api_keys:
                if k and k.strip() and k.strip() not in self.raw_api_keys:
                    self.raw_api_keys.append(k.strip())
        except Exception:
            pass
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        api_file = project_root / "groq api.txt"
        if api_file.exists():
            try:
                with open(api_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("gsk_") and line not in self.raw_api_keys:
                            self.raw_api_keys.append(line)
            except Exception:
                pass

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 20, 24, 20)
        root_layout.setSpacing(16)

        # 1. Top Header Bar
        top_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(3)

        title_lbl = QLabel("⚙️ Studio Settings & Profiles Management")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: 800; color: #FFFFFF; letter-spacing: 0.5px;")
        title_box.addWidget(title_lbl)

        sub_lbl = QLabel("Manage Google / Chrome browser profiles, Groq multi-key pooling, workspace paths, and project maintenance.")
        sub_lbl.setStyleSheet("font-size: 12px; color: #A0A0A0;")
        title_box.addWidget(sub_lbl)
        top_bar.addLayout(title_box)

        top_bar.addStretch()

        self.back_btn = QPushButton("⬅ Back to Studio")
        self.back_btn.setFixedHeight(34)
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: #1A1A1A;
                color: #F5F5F5;
                font-weight: 700;
                font-size: 11px;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background-color: #252525;
                border-color: #E53935;
                color: #FFFFFF;
            }
        """)
        self.back_btn.clicked.connect(lambda: self.navigate_back.emit())
        top_bar.addWidget(self.back_btn)

        root_layout.addLayout(top_bar)

        # 2. Main Tabs Container
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #282828;
                background-color: #141414;
                border-radius: 8px;
                padding: 12px;
            }
            QTabBar::tab {
                background-color: #1A1A1A;
                color: #A0A0A0;
                font-size: 12px;
                font-weight: 700;
                padding: 10px 20px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                border: 1px solid #282828;
                border-bottom: none;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background-color: #141414;
                color: #FFFFFF;
                border-top: 2px solid #E53935;
                border-bottom: 1px solid #141414;
            }
            QTabBar::tab:hover:!selected {
                background-color: #222222;
                color: #E0E0E0;
            }
        """)

        # Tab 1: Profiles Management
        self.profiles_panel = ProfilesManagerPanel(self)
        self.tabs.addTab(self.profiles_panel, "👤 Google / Chrome Profiles (acc1..acc6)")

        # Tab 2: Groq Multi-Key AI Engine
        groq_tab = self._create_groq_tab()
        self.tabs.addTab(groq_tab, "⚡ Groq Multi-Key AI Engine")

        # Tab 3: Storage & Maintenance (Delete Incomplete Projects)
        storage_tab = self._create_storage_tab()
        self.tabs.addTab(storage_tab, "📁 Storage & Incomplete Projects Cleanup")

        root_layout.addWidget(self.tabs, 1)

        # 3. Bottom Action Bar
        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()

        self.save_btn = QPushButton("💾 Save Settings")
        self.save_btn.setFixedHeight(36)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #E53935;
                color: #FFFFFF;
                font-size: 12px;
                font-weight: 800;
                border: 1px solid #FF4B4B;
                border-radius: 6px;
                padding: 0 24px;
            }
            QPushButton:hover {
                background-color: #FF4B4B;
            }
        """)
        self.save_btn.clicked.connect(self._on_save_settings)
        bottom_bar.addWidget(self.save_btn)

        root_layout.addLayout(bottom_bar)

    def _create_groq_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Groq Engine Group
        group = QGroupBox("⚡ Groq Multi-Key Pooling & High-Speed Inference")
        group.setStyleSheet("QGroupBox { font-size: 13px; font-weight: bold; color: #FFFFFF; }")
        g_layout = QVBoxLayout(group)
        g_layout.setSpacing(12)

        groq = get_groq_engine()
        key_count = len(self.raw_api_keys)
        info_lbl = QLabel(
            f"<b>Active Key Pool:</b> {key_count} Groq API keys loaded from "
            f"<code>groq api.txt</code> and app settings.<br>"
            "Keys are rotated round-robin automatically with instant failover on rate limits (429)."
        )
        info_lbl.setStyleSheet("color: #A0A0A0; font-size: 11px; line-height: 1.4;")
        info_lbl.setWordWrap(True)
        g_layout.addWidget(info_lbl)

        # Groq Model Selection
        model_row = QHBoxLayout()
        m_lbl = QLabel("Default Model:")
        m_lbl.setFixedWidth(110)
        m_lbl.setStyleSheet("color: #E0E0E0; font-size: 12px; font-weight: 600;")
        self.model_combo = PBComboBox()
        models = [
            ("qwen/qwen3.8-27b", "qwen/qwen3.8-27b (Fast, High Quality — Recommended)"),
            ("llama-3.3-70b-versatile", "llama-3.3-70b-versatile (Meta Llama 3.3 70B)"),
            ("llama-3.1-8b-instant", "llama-3.1-8b-instant (Fastest 8B Model)"),
            ("mixtral-8x7b-32768", "mixtral-8x7b-32768 (Mistral MoE 32k Context)"),
        ]
        for mid, mlabel in models:
            self.model_combo.addItem(mlabel, mid)

        idx = self.model_combo.findData(self.settings.default_model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        model_row.addWidget(m_lbl)
        model_row.addWidget(self.model_combo, 1)
        g_layout.addLayout(model_row)

        # API Keys Multi-line Text Area
        keys_lbl = QLabel("Groq API Keys (one per line):")
        keys_lbl.setStyleSheet("color: #E0E0E0; font-size: 12px; font-weight: 600;")
        g_layout.addWidget(keys_lbl)

        self.keys_edit = QPlainTextEdit()
        self.keys_edit.setPlaceholderText("Paste your Groq API keys here, one per line (e.g. gsk_...)...")
        self.keys_edit.setPlainText("\n".join(self.raw_api_keys))
        self.keys_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #101010;
                color: #FF4B4B;
                border: 1px solid #282828;
                border-radius: 6px;
                padding: 10px;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                min-height: 140px;
            }
            QPlainTextEdit:focus {
                border-color: #E53935;
            }
        """)
        g_layout.addWidget(self.keys_edit)

        layout.addWidget(group)

        # Stock Video APIs Group
        video_group = QGroupBox("🎬 Stock Video APIs (Pexels & Pixabay)")
        video_group.setStyleSheet("QGroupBox { font-size: 13px; font-weight: bold; color: #FFFFFF; }")
        vg_layout = QVBoxLayout(video_group)
        vg_layout.setSpacing(10)

        vg_desc = QLabel("Free API keys used to automatically download and trim B-roll video footage.")
        vg_desc.setStyleSheet("color: #A0A0A0; font-size: 11px;")
        vg_layout.addWidget(vg_desc)

        # Pexels API Key
        pex_row = QHBoxLayout()
        pex_lbl = QLabel("Pexels API Key:")
        pex_lbl.setFixedWidth(120)
        pex_lbl.setStyleSheet("color: #E0E0E0; font-size: 12px; font-weight: 600;")
        self.pexels_input = QLineEdit(self.settings.pexels_api_key or "")
        self.pexels_input.setPlaceholderText("Paste your Pexels API key here...")
        self.pexels_input.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        self.pexels_input.setStyleSheet("""
            QLineEdit {
                background-color: #101010;
                color: #F5F5F5;
                border: 1px solid #282828;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
            }
            QLineEdit:focus { border-color: #E53935; }
        """)
        pex_row.addWidget(pex_lbl)
        pex_row.addWidget(self.pexels_input, 1)
        vg_layout.addLayout(pex_row)

        # Pixabay API Key
        pix_row = QHBoxLayout()
        pix_lbl = QLabel("Pixabay API Key:")
        pix_lbl.setFixedWidth(120)
        pix_lbl.setStyleSheet("color: #E0E0E0; font-size: 12px; font-weight: 600;")
        self.pixabay_input = QLineEdit(self.settings.pixabay_api_key or "")
        self.pixabay_input.setPlaceholderText("Paste your Pixabay API key here...")
        self.pixabay_input.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        self.pixabay_input.setStyleSheet("""
            QLineEdit {
                background-color: #101010;
                color: #F5F5F5;
                border: 1px solid #282828;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
            }
            QLineEdit:focus { border-color: #E53935; }
        """)
        pix_row.addWidget(pix_lbl)
        pix_row.addWidget(self.pixabay_input, 1)
        vg_layout.addLayout(pix_row)

        layout.addWidget(video_group)
        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    def _create_storage_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(18)

        # 1. Workspace Directory
        ws_group = QGroupBox("📁 Workspace & Projects Directory")
        ws_group.setStyleSheet("QGroupBox { font-size: 13px; font-weight: bold; color: #FFFFFF; }")
        ws_layout = QVBoxLayout(ws_group)
        ws_layout.setSpacing(10)

        ws_desc = QLabel("Directory where all productions, storyboard metadata, images, and rendered videos are stored.")
        ws_desc.setStyleSheet("color: #A0A0A0; font-size: 11px;")
        ws_layout.addWidget(ws_desc)

        ws_row = QHBoxLayout()
        self.ws_input = QLineEdit(self.settings.workspace_directory)
        self.ws_input.setStyleSheet("""
            QLineEdit {
                background-color: #101010;
                color: #F5F5F5;
                border: 1px solid #282828;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #E53935;
            }
        """)
        ws_row.addWidget(self.ws_input, 1)

        browse_btn = QPushButton("Browse...")
        browse_btn.setFixedHeight(34)
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #1A1A1A;
                color: #FFFFFF;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 0 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                border-color: #E53935;
            }
        """)
        browse_btn.clicked.connect(self._on_browse_workspace)
        ws_row.addWidget(browse_btn)

        ws_layout.addLayout(ws_row)
        layout.addWidget(ws_group)

        # 2. Incomplete Projects Cleanup (Dedicated Feature Requested by User)
        maint_group = QGroupBox("🗑️ Project Maintenance & Cleanup")
        maint_group.setStyleSheet("QGroupBox { font-size: 13px; font-weight: bold; color: #FFFFFF; }")
        m_layout = QVBoxLayout(maint_group)
        m_layout.setSpacing(12)

        m_desc = QLabel(
            "<b>Automatic Incomplete Projects Cleanup:</b><br>"
            "Scans your workspace projects directory and automatically identifies all projects that do <b>not</b> "
            "have a completed rendered MP4 video in their <code>renders/</code> folder.<br>"
            "Clicking the button below will list them and let you delete them all in one click to reclaim disk space."
        )
        m_desc.setStyleSheet("color: #A0A0A0; font-size: 11px; line-height: 1.5;")
        m_desc.setWordWrap(True)
        m_layout.addWidget(m_desc)

        btn_row = QHBoxLayout()
        self.del_incomplete_btn = QPushButton("🗑️ Delete Incomplete Projects (No Rendered MP4)")
        self.del_incomplete_btn.setFixedHeight(38)
        self.del_incomplete_btn.setCursor(Qt.PointingHandCursor)
        self.del_incomplete_btn.setStyleSheet("""
            QPushButton {
                background-color: #221414;
                color: #FF4B4B;
                border: 1px solid #E53935;
                font-size: 12px;
                font-weight: 800;
                border-radius: 6px;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: #E53935;
                color: #FFFFFF;
                border-color: #FF7070;
            }
        """)
        self.del_incomplete_btn.clicked.connect(self._on_delete_incomplete_projects)
        btn_row.addWidget(self.del_incomplete_btn)
        btn_row.addStretch()
        m_layout.addLayout(btn_row)

        layout.addWidget(maint_group)
        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    def _on_browse_workspace(self):
        d = QFileDialog.getExistingDirectory(self, "Select Workspace Projects Directory", self.ws_input.text().strip())
        if d:
            self.ws_input.setText(d)

    def _on_save_settings(self):
        # 1. Update Groq Model
        chosen_model = self.model_combo.currentData()
        if chosen_model:
            self.settings.default_model = chosen_model

        # 2. Update Workspace Dir
        new_ws = self.ws_input.text().strip()
        if new_ws:
            self.settings.workspace_directory = new_ws

        # 3. Update Groq Keys
        lines = [ln.strip() for ln in self.keys_edit.toPlainText().splitlines() if ln.strip()]
        self.settings.api_keys = lines
        self.settings.api_key = lines[0] if lines else ""

        try:
            groq = get_groq_engine()
            groq.set_api_keys(lines)
        except Exception as ex:
            print(f"[Settings] groq engine set_api_keys notice: {ex}")

        # Also persist directly to local groq api.txt in project root
        try:
            base_dir = Path(__file__).resolve().parent.parent.parent.parent
            api_file = base_dir / "groq api.txt"
            with open(api_file, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + ("\n" if lines else ""))
        except Exception as ex:
            print(f"[Settings] groq api.txt write notice: {ex}")

        # 4. Update Stock Video Keys
        if hasattr(self, "pexels_input"):
            self.settings.pexels_api_key = self.pexels_input.text().strip()
        if hasattr(self, "pixabay_input"):
            self.settings.pixabay_api_key = self.pixabay_input.text().strip()

        SettingsManager.save_settings(self.settings)
        self.settings_saved.emit(self.settings)
        QMessageBox.information(self, "Settings Saved", f"Studio settings and {len(lines)} API key(s) updated successfully!")

    def _on_delete_incomplete_projects(self):
        """
        Deletes all project directories that do not contain a rendered MP4 video in their renders folder.
        """
        ws = self.ws_input.text().strip() or self.settings.workspace_directory
        ws_path = Path(ws)

        # Look in workspace root and workspace/projects
        search_dirs = [ws_path, ws_path / "projects", Path.cwd() / "projects"]
        all_candidate_dirs = []

        seen_paths = set()
        for root in search_dirs:
            if root.exists() and root.is_dir():
                for p in root.iterdir():
                    if p.is_dir() and not p.name.startswith(".") and p.resolve() not in seen_paths:
                        all_candidate_dirs.append(p)
                        seen_paths.add(p.resolve())

        if not all_candidate_dirs:
            QMessageBox.information(self, "No Projects Found", "No project directories found in the workspace.")
            return

        incomplete_dirs: List[Path] = []
        for p in all_candidate_dirs:
            # Check if this project directory has a valid rendered mp4
            renders_dir = p / "renders"
            has_rendered_mp4 = False

            if renders_dir.exists():
                for vid in renders_dir.glob("*.mp4"):
                    if vid.is_file() and vid.stat().st_size > 1024:
                        has_rendered_mp4 = True
                        break

            # Also check if an mp4 exists directly inside the project directory
            if not has_rendered_mp4:
                for vid in p.glob("*.mp4"):
                    if vid.is_file() and vid.stat().st_size > 1024:
                        has_rendered_mp4 = True
                        break

            if not has_rendered_mp4:
                incomplete_dirs.append(p)

        if not incomplete_dirs:
            QMessageBox.information(
                self,
                "All Projects Completed!",
                f"Scanned {len(all_candidate_dirs)} project(s). Every single project has a rendered MP4 video!\n"
                "There are zero incomplete projects to delete."
            )
            return

        names_preview = "\n".join([f"• {p.name}" for p in incomplete_dirs[:12]])
        if len(incomplete_dirs) > 12:
            names_preview += f"\n... and {len(incomplete_dirs) - 12} more"

        reply = QMessageBox.question(
            self,
            f"Delete {len(incomplete_dirs)} Incomplete Project(s)?",
            f"Found {len(incomplete_dirs)} project(s) with NO rendered MP4 video:\n\n"
            f"{names_preview}\n\n"
            "Do you want to permanently delete these incomplete project directories?\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            deleted_count = 0
            for p in incomplete_dirs:
                try:
                    shutil.rmtree(p, ignore_errors=True)
                    deleted_count += 1
                except Exception as ex:
                    print(f"Error removing {p}: {ex}")

            win = self.window()
            if win and hasattr(win, "_populate_project_combo"):
                win._populate_project_combo()

            QMessageBox.information(
                self,
                "Cleanup Complete",
                f"Successfully deleted {deleted_count} incomplete project(s)!"
            )
