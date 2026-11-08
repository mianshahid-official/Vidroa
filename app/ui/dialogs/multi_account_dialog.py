"""
Multi-Account Batch Generation Dialog for PromptBeast.
Handles high-volume image generation (e.g. 100 to 400+ prompts) across multiple
Google Gemini accounts (acc1..acc6) to bypass daily per-account generation limits.
"""

from pathlib import Path
from typing import List, Dict, Optional
import subprocess

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QWidget,
    QApplication,
    QMessageBox,
)

from app.core.browser_profiles_manager import BrowserProfilesManager


class MultiAccountGenerationDialog(QDialog):
    """
    Dialog facilitating split-batch image generation across multiple connected
    Google accounts with 1-click clipboard copying and profile launching.
    """

    def __init__(
        self,
        prompts: List[str],
        project_dir: Path,
        images_dir: Path,
        batch_size: int = 100,
        parent=None
    ):
        super().__init__(parent)
        self.prompts = [p.strip() for p in prompts if p.strip()]
        self.project_dir = project_dir
        self.images_dir = images_dir
        self.batch_size = max(10, batch_size)
        self.setWindowTitle("🚀 Multi-Account Gemini Generation (High-Volume Pacing)")
        self.setMinimumSize(680, 520)
        self.setStyleSheet("""
            QDialog {
                background-color: #0B0F17;
                color: #F8FAFC;
            }
        """)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header Title + Badge
        header_row = QHBoxLayout()
        title_lbl = QLabel("Multi-Account Batch Generation")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #F8FAFC;")
        header_row.addWidget(title_lbl)

        total_prompts = len(self.prompts)
        num_batches = (total_prompts + self.batch_size - 1) // self.batch_size
        badge_lbl = QLabel(f"{total_prompts} Prompts  •  {num_batches} Account Batches")
        badge_lbl.setStyleSheet("""
            font-size: 11px;
            font-weight: 700;
            color: #10B981;
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid #10B981;
            border-radius: 12px;
            padding: 3px 10px;
        """)
        header_row.addStretch()
        header_row.addWidget(badge_lbl)
        layout.addLayout(header_row)

        # Guidance text explaining rate limits and multi-account workflow
        desc_lbl = QLabel(
            "Google accounts typically allow ~100 image generations per day. "
            "To generate long stories without hitting limits or mixing scenes, PromptBeast automatically splits "
            "your prompts into 100-item batches mapped to separate Chrome profiles. "
            "Each profile downloads directly into its dedicated subfolder (images/acc1, images/acc2, etc.) "
            "and PromptBeast re-stitches all scenes in exact chronological order."
        )
        desc_lbl.setStyleSheet("font-size: 11px; color: #94A3B8; line-height: 1.4;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        # Scroll Area with Batch Rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: 1px solid #1E293B;
                border-radius: 8px;
            }
            QScrollBar:vertical {
                background: #0B0F17;
                width: 8px;
            }
            QScrollBar::handle:vertical {
                background: #334155;
                border-radius: 4px;
            }
        """)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(12, 12, 12, 12)
        c_layout.setSpacing(10)

        # Profile signed-in status cache
        profiles_info = {p["name"]: p for p in BrowserProfilesManager.get_all_profiles()}

        for b_idx in range(num_batches):
            acc_num = b_idx + 1
            acc_name = f"acc{acc_num}"
            start_idx = b_idx * self.batch_size
            end_idx = min(start_idx + self.batch_size, total_prompts)
            batch_prompts = self.prompts[start_idx:end_idx]
            count_in_batch = len(batch_prompts)

            p_info = profiles_info.get(acc_name, {})
            is_signed = p_info.get("is_signed_in", False)

            # Account subfolder
            acc_dir = self.images_dir if acc_num == 1 else (self.images_dir / acc_name)
            acc_dir.mkdir(parents=True, exist_ok=True)

            card = self._create_batch_card(
                acc_name=acc_name,
                batch_num=acc_num,
                start_num=start_idx + 1,
                end_num=end_idx,
                count=count_in_batch,
                is_signed=is_signed,
                batch_prompts=batch_prompts,
                acc_dir=acc_dir,
            )
            c_layout.addWidget(card)

        c_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        # Status feedback banner
        self.status_lbl = QLabel("Ready. Click any batch button to copy prompts and open Chrome.")
        self.status_lbl.setStyleSheet("font-size: 11px; color: #64748B; font-weight: 500;")
        layout.addWidget(self.status_lbl)

        # Bottom Action Bar
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(10)

        # Copy ALL button
        copy_all_btn = QPushButton("📋 Copy ALL Prompts (Single Account)")
        copy_all_btn.setFixedHeight(34)
        copy_all_btn.setCursor(Qt.PointingHandCursor)
        copy_all_btn.setStyleSheet("""
            QPushButton {
                background: #1E293B;
                color: #CBD5E1;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 0 12px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #334155;
                color: #FFFFFF;
            }
        """)
        copy_all_btn.clicked.connect(self._copy_all_prompts)
        bottom_row.addWidget(copy_all_btn)

        # Open Images Folder
        open_folder_btn = QPushButton("📂 Open Images Folder")
        open_folder_btn.setFixedHeight(34)
        open_folder_btn.setCursor(Qt.PointingHandCursor)
        open_folder_btn.setStyleSheet("""
            QPushButton {
                background: #1E293B;
                color: #CBD5E1;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 0 12px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #334155;
                color: #FFFFFF;
            }
        """)
        open_folder_btn.clicked.connect(self._open_images_folder)
        bottom_row.addWidget(open_folder_btn)

        bottom_row.addStretch()

        close_btn = QPushButton("Done")
        close_btn.setFixedHeight(34)
        close_btn.setFixedWidth(90)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #10B981;
                color: #0B0F17;
                font-size: 12px;
                font-weight: 800;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: #34D399;
            }
        """)
        close_btn.clicked.connect(self.accept)
        bottom_row.addWidget(close_btn)

        layout.addLayout(bottom_row)

    def _create_batch_card(
        self,
        acc_name: str,
        batch_num: int,
        start_num: int,
        end_num: int,
        count: int,
        is_signed: bool,
        batch_prompts: List[str],
        acc_dir: Path,
    ) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #0E1420;
                border: 1px solid #1E293B;
                border-radius: 6px;
                padding: 8px 12px;
            }
            QFrame:hover {
                border-color: #334155;
            }
        """)
        row = QHBoxLayout(card)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(12)

        # Profile Icon & Name
        acc_box = QVBoxLayout()
        acc_box.setSpacing(2)
        name_row = QHBoxLayout()
        name_row.setSpacing(6)
        n_lbl = QLabel(f"Batch {batch_num}: {acc_name.upper()}")
        n_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #F8FAFC;")
        name_row.addWidget(n_lbl)

        status_pill = QLabel("🟢 Signed in" if is_signed else "⚪ Not signed in")
        status_pill.setStyleSheet(
            "font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; "
            + ("background: rgba(16, 185, 129, 0.15); color: #34D399; border: 1px solid #10B981;"
               if is_signed else "background: rgba(100, 116, 139, 0.15); color: #94A3B8; border: 1px solid #334155;")
        )
        name_row.addWidget(status_pill)
        name_row.addStretch()
        acc_box.addLayout(name_row)

        range_lbl = QLabel(f"Prompts #{start_num} to #{end_num} ({count} images)  →  {acc_dir.name}/")
        range_lbl.setStyleSheet("font-size: 11px; color: #94A3B8;")
        acc_box.addWidget(range_lbl)
        row.addLayout(acc_box, 1)

        # Action: Copy Prompts Only
        copy_btn = QPushButton("📋 Copy Prompts")
        copy_btn.setFixedHeight(32)
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setStyleSheet("""
            QPushButton {
                background: #1E293B;
                color: #38BDF8;
                border: 1px solid #334155;
                border-radius: 5px;
                padding: 0 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #334155;
                color: #FFFFFF;
            }
        """)
        copy_btn.clicked.connect(lambda: self._copy_batch(batch_prompts, acc_name, start_num, end_num, copy_btn))
        row.addWidget(copy_btn)

        # Action: Copy & Launch Chrome Profile
        launch_btn = QPushButton(f"🚀 Copy & Launch {acc_name}")
        launch_btn.setFixedHeight(32)
        launch_btn.setCursor(Qt.PointingHandCursor)
        launch_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #7C3AED, stop:1 #4F46E5);
                color: #FFFFFF;
                font-size: 11px;
                font-weight: 700;
                border: none;
                border-radius: 5px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #8B5CF6, stop:1 #6366F1);
            }
        """)
        launch_btn.clicked.connect(
            lambda: self._launch_batch(batch_prompts, acc_name, start_num, end_num, acc_dir, launch_btn)
        )
        row.addWidget(launch_btn)

        return card

    def _copy_batch(self, batch_prompts: List[str], acc_name: str, start: int, end: int, btn: QPushButton):
        from app.core.export import StoryboardExporter
        cleaned = [StoryboardExporter.clean_prompt_single_line(p) for p in batch_prompts if p.strip()]
        text = "\n".join(cleaned)
        QApplication.clipboard().setText(text)
        verified = QApplication.clipboard().text()
        if verified != text:
            QMessageBox.critical(self, "Clipboard Error", f"Windows clipboard copy failed for {acc_name}.")
            return
        btn.setText("✓ Copied!")
        self.status_lbl.setText(f"✅ Copied {len(cleaned)} prompts for {acc_name} (Prompts #{start}-#{end}) to clipboard.")
        self.status_lbl.setStyleSheet("font-size: 11px; color: #4ADE80; font-weight: 600;")
        QTimer.singleShot(2500, lambda: btn.setText("📋 Copy Prompts"))

    def _launch_batch(
        self,
        batch_prompts: List[str],
        acc_name: str,
        start: int,
        end: int,
        acc_dir: Path,
        btn: QPushButton,
    ):
        from app.core.export import StoryboardExporter
        cleaned = [StoryboardExporter.clean_prompt_single_line(p) for p in batch_prompts if p.strip()]
        text = "\n".join(cleaned)

        # 1. Copy prompts to clipboard with verification
        QApplication.clipboard().setText(text)
        verified = QApplication.clipboard().text()
        if verified != text:
            QMessageBox.critical(self, "Clipboard Error", f"Windows clipboard copy failed for {acc_name}.")
            return

        # 2. Configure Chrome download directory
        BrowserProfilesManager.configure_download_dir(acc_name, acc_dir)

        # 3. Open Chrome profile
        ok, msg = BrowserProfilesManager.open_browser_profile(acc_name, download_dir=acc_dir, prompts_text=text)
        if ok:
            btn.setText("✓ Launched!")
            self.status_lbl.setText(
                f"🚀 {acc_name} opened! Download folder: {acc_dir.name}/. "
                f"Prompts #{start}-#{end} copied to clipboard — press Ctrl+V in Gemini!"
            )
            self.status_lbl.setStyleSheet("font-size: 11px; color: #4ADE80; font-weight: 600;")
            QTimer.singleShot(3500, lambda: btn.setText(f"🚀 Copy & Launch {acc_name}"))
        else:
            QMessageBox.critical(self, "Chrome Error", f"Could not launch {acc_name}:\n{msg}")

    def _copy_all_prompts(self):
        from app.core.export import StoryboardExporter
        cleaned = [StoryboardExporter.clean_prompt_single_line(p) for p in self.prompts if p.strip()]
        text = "\n".join(cleaned)
        QApplication.clipboard().setText(text)
        verified = QApplication.clipboard().text()
        if verified != text:
            QMessageBox.critical(self, "Clipboard Error", "Failed to verify copied prompts on clipboard.")
            return
        self.status_lbl.setText(f"✅ Copied all {len(cleaned)} prompts to clipboard.")
        self.status_lbl.setStyleSheet("font-size: 11px; color: #4ADE80; font-weight: 600;")

    def _open_images_folder(self):
        if self.images_dir.exists():
            try:
                subprocess.Popen(["explorer.exe", str(self.images_dir.resolve())])
            except Exception:
                pass

