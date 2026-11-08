"""
Image Asset Manager Panel.
Enables selecting image directories, auto-binding images to scenes, and thumbnail previewing.
"""
from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QScrollArea, QFrame, QGridLayout, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QIcon

import json
from app.models.scene import VisualScene
from app.models.timeline import NarrationData
from app.core.asset_manager import AssetManager
from app.core.timestamp_parser import TimestampParser


class SceneImageCard(QFrame):
    """Visual card displaying a scene's thumbnail, scene number, and bound image status."""

    image_changed = Signal(int, str)  # (scene_index, image_path)

    def __init__(self, scene_index: int, scene: VisualScene, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.scene_index = scene_index
        self.scene = scene
        self._setup_ui()

    def _setup_ui(self):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            SceneImageCard {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
            }
            SceneImageCard:hover {
                border-color: #38bdf8;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Header: Scene Number & Duration
        hdr = QHBoxLayout()
        num_lbl = QLabel(f"<b>Scene {self.scene_index + 1}</b> ({self.scene.scene_id})")
        num_lbl.setStyleSheet("color: #38bdf8; font-size: 12px;")
        dur_lbl = QLabel(f"{self.scene.duration:.1f}s")
        dur_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        hdr.addWidget(num_lbl)
        hdr.addStretch()
        hdr.addWidget(dur_lbl)
        layout.addLayout(hdr)

        # Thumbnail display
        self.thumb_lbl = QLabel()
        self.thumb_lbl.setFixedSize(200, 112)
        self.thumb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_lbl.setStyleSheet("background-color: #0f172a; border-radius: 4px; color: #64748b; font-size: 11px;")
        self._update_thumbnail()
        layout.addWidget(self.thumb_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

        # Visual Summary / Caption
        caption_text = getattr(self.scene, "visual_summary", None) or getattr(self.scene, "visual_subject", "No summary")
        if len(caption_text) > 40:
            caption_text = caption_text[:37] + "..."
        caption_lbl = QLabel(caption_text)
        caption_lbl.setStyleSheet("color: #cbd5e1; font-size: 11px;")
        caption_lbl.setToolTip(getattr(self.scene, "image_prompt", None) or getattr(self.scene, "prompt", ""))
        layout.addWidget(caption_lbl)

        # File path / Status
        self.file_lbl = QLabel(self._get_file_display_name())
        self.file_lbl.setStyleSheet("color: #4ade80;" if self.scene.image_path else "color: #94a3b8; font-size: 10px;")
        layout.addWidget(self.file_lbl)

        # Choose File Button
        pick_btn = QPushButton("Change Image...")
        pick_btn.setFixedHeight(24)
        pick_btn.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #e2e8f0;
                font-size: 10px;
                border-radius: 4px;
                padding: 0 8px;
            }
            QPushButton:hover {
                background-color: #475569;
            }
        """)
        pick_btn.clicked.connect(self._on_pick_file)
        layout.addWidget(pick_btn)

    def _get_file_display_name(self) -> str:
        if self.scene.image_path and Path(self.scene.image_path).exists():
            return f"✅ {Path(self.scene.image_path).name}"
        return "⚠️ Placeholder (No image)"

    def _update_thumbnail(self):
        if self.scene.image_path and Path(self.scene.image_path).exists():
            thumb_file = AssetManager.generate_thumbnail(self.scene.image_path, (200, 112))
            if thumb_file and Path(thumb_file).exists():
                pix = QPixmap(thumb_file)
                self.thumb_lbl.setPixmap(pix.scaled(200, 112, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
                return
        self.thumb_lbl.setText("🖼️\nNo Image Asset")

    def _on_pick_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select Image for Scene {self.scene_index + 1}",
            "",
            "Image Files (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if file_path:
            self.scene.image_path = file_path
            self._update_thumbnail()
            self.file_lbl.setText(self._get_file_display_name())
            self.file_lbl.setStyleSheet("color: #4ade80;")
            self.image_changed.emit(self.scene_index, file_path)


class ImageAssetPanel(QWidget):
    """Panel managing image folder ingestion, auto-binding, and scene previews."""

    images_updated = Signal(list)        # List[VisualScene]
    audio_selected = Signal(str)         # audio_file_path
    narration_selected = Signal(object)  # NarrationData
    scenes_realigned = Signal(list)      # List[VisualScene]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.scenes: List[VisualScene] = []
        self.images_folder: Optional[str] = None
        self._cards: List[SceneImageCard] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Header
        top_bar = QHBoxLayout()
        header_lbl = QLabel("🖼️ Generated Image Assets")
        header_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #38bdf8;")
        top_bar.addWidget(header_lbl)
        top_bar.addStretch()

        self.match_status_lbl = QLabel("No scenes loaded.")
        self.match_status_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
        top_bar.addWidget(self.match_status_lbl)

        layout.addLayout(top_bar)

        desc_lbl = QLabel("Generate images in your favorite generator (e.g. Midjourney, FLUX, DALL-E) and place them in a folder. PromptBeast automatically binds them by number (001.png, 002.png).")
        desc_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        # Actions Row: Choose Images | Select Audio | Select Timestamps JSON | Auto-Match
        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)
        
        self.folder_btn = QPushButton("📁 Choose Images Folder")
        self.folder_btn.setFixedHeight(34)
        self.folder_btn.setStyleSheet("""
            QPushButton {
                background-color: #141821;
                color: #38BDF8;
                font-weight: 700;
                font-size: 11px;
                border-radius: 5px;
                border: 1px solid #262C38;
                padding: 0 14px;
            }
            QPushButton:hover {
                background-color: #19202C;
                border-color: #38BDF8;
                color: #FFFFFF;
            }
        """)
        self.folder_btn.clicked.connect(self._on_choose_folder)
        actions_row.addWidget(self.folder_btn)

        self.audio_btn = QPushButton("🎙️ Select Audio File...")
        self.audio_btn.setFixedHeight(34)
        self.audio_btn.setStyleSheet("""
            QPushButton {
                background-color: #141821;
                color: #B8F24A;
                font-weight: 700;
                font-size: 11px;
                border-radius: 5px;
                border: 1px solid #262C38;
                padding: 0 14px;
            }
            QPushButton:hover {
                background-color: #19202C;
                border-color: #B8F24A;
                color: #FFFFFF;
            }
        """)
        self.audio_btn.clicked.connect(self._on_choose_audio)
        actions_row.addWidget(self.audio_btn)

        self.ts_btn = QPushButton("⏱️ Select timeline.json / Timings...")
        self.ts_btn.setFixedHeight(34)
        self.ts_btn.setStyleSheet("""
            QPushButton {
                background-color: #141821;
                color: #A855F7;
                font-weight: 700;
                font-size: 11px;
                border-radius: 5px;
                border: 1px solid #262C38;
                padding: 0 14px;
            }
            QPushButton:hover {
                background-color: #19202C;
                border-color: #A855F7;
                color: #FFFFFF;
            }
        """)
        self.ts_btn.clicked.connect(self._on_choose_timestamps)
        actions_row.addWidget(self.ts_btn)

        self.auto_match_btn = QPushButton("🔄 Auto-Match Images")
        self.auto_match_btn.setFixedHeight(34)
        self.auto_match_btn.setStyleSheet("""
            QPushButton {
                background-color: #141821;
                color: #F3F1EC;
                font-weight: 600;
                font-size: 11px;
                border-radius: 5px;
                border: 1px solid #262C38;
                padding: 0 14px;
            }
            QPushButton:hover {
                background-color: #19202C;
                border-color: #343C4C;
            }
        """)
        self.auto_match_btn.setFixedHeight(34)
        self.auto_match_btn.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #f1f5f9;
                font-weight: 600;
                font-size: 11px;
                border-radius: 5px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background-color: #475569;
            }
        """)
        self.auto_match_btn.clicked.connect(self._on_auto_match)
        actions_row.addWidget(self.auto_match_btn)

        actions_row.addStretch()
        layout.addLayout(actions_row)

        # Status summary row
        info_row = QHBoxLayout()
        info_row.setSpacing(16)
        self.folder_path_lbl = QLabel("📁 Folder: (Not selected)")
        self.folder_path_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        info_row.addWidget(self.folder_path_lbl)

        self.audio_path_lbl = QLabel("🎙️ Audio: (Not selected)")
        self.audio_path_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        info_row.addWidget(self.audio_path_lbl)

        self.ts_path_lbl = QLabel("⏱️ Timings: (Auto from story)")
        self.ts_path_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        info_row.addWidget(self.ts_path_lbl)
        info_row.addStretch()
        layout.addLayout(info_row)

        # Scroll Area with Card Grid
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(4, 4, 4, 4)
        self.grid_layout.setSpacing(12)
        self.scroll_area.setWidget(self.grid_container)

        layout.addWidget(self.scroll_area)

    def load_scenes(self, scenes: List[VisualScene], images_folder: Optional[str] = None):
        self.scenes = scenes
        if images_folder:
            self.images_folder = images_folder
            self.folder_path_lbl.setText(f"Folder: {Path(images_folder).name}")

        self._refresh_cards()

    def _on_choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Generated Images Folder")
        if folder:
            self.images_folder = folder
            self.folder_path_lbl.setText(f"📁 Folder: {Path(folder).name}")
            self.folder_path_lbl.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: bold;")
            self._on_auto_match()

    def _on_choose_audio(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Voiceover Audio File",
            "",
            "Audio Files (*.mp3 *.wav *.m4a *.flac *.ogg *.aac);;All Files (*.*)"
        )
        if file_path:
            p = Path(file_path)
            self.audio_path_lbl.setText(f"🎙️ Audio: {p.name}")
            self.audio_path_lbl.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: bold;")
            self.audio_selected.emit(file_path)

            # Auto-detect companion speech.json, timeline.json, or timestamps.json
            for c_path in [p.with_suffix(".json"), p.parent / "speech.json", p.parent / "timeline.json", p.parent / "timestamps.json"]:
                if c_path.exists():
                    self._load_timestamps_file(str(c_path), auto_detected=True)
                    break

    def _on_choose_timestamps(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select timeline.json or speech.json Timestamps File",
            "",
            "JSON Files (*.json);;All Files (*.*)"
        )
        if file_path:
            self._load_timestamps_file(file_path, auto_detected=False)

    def _load_timestamps_file(self, file_path: str, auto_detected: bool = False):
        try:
            p = Path(file_path)
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 1. Timeline JSON format with image-level timings
            if isinstance(data, dict) and "images" in data and isinstance(data["images"], list) and self.scenes:
                img_map = {str(item.get("image_id", "")).zfill(3): item for item in data["images"]}
                updated_count = 0
                for sc in self.scenes:
                    k = sc.scene_id.zfill(3)
                    if k in img_map:
                        sc_info = img_map[k]
                        sc.start = float(sc_info.get("start", sc.start))
                        sc.end = float(sc_info.get("end", sc.end))
                        sc.duration = round(sc.end - sc.start, 2)
                        updated_count += 1
                self.ts_path_lbl.setText(f"⏱️ Timings: {p.name} ({updated_count} scenes timed)")
                self.ts_path_lbl.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: bold;")
                self.scenes_realigned.emit(self.scenes)
                if not auto_detected:
                    QMessageBox.information(self, "Timeline Applied", f"Successfully loaded scene timings for {updated_count} scenes from {p.name}!")
                return

            # 2. Word-level timestamps format (e.g. speech.json)
            narration = TimestampParser.load_from_json(file_path)
            self.ts_path_lbl.setText(f"⏱️ Timings: {p.name} ({narration.duration_seconds:.1f}s, {len(narration.words)} words)")
            self.ts_path_lbl.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: bold;")
            self.narration_selected.emit(narration)
            if not auto_detected:
                QMessageBox.information(self, "Timestamps Loaded", f"Successfully loaded {len(narration.words)} word timestamps from {p.name}!")
        except Exception as e:
            if not auto_detected:
                QMessageBox.critical(self, "Timestamps Load Error", f"Failed to parse {file_path}:\n{e}")

    def _on_auto_match(self):
        if not self.images_folder or not Path(self.images_folder).exists():
            QMessageBox.information(self, "Select Folder", "Please choose an image folder first.")
            return

        if not self.scenes:
            img_exts = (".png", ".jpg", ".jpeg", ".webp")
            raw_files = [f for f in Path(self.images_folder).iterdir() if f.suffix.lower() in img_exts]
            import re
            def sort_key(p):
                nums = re.findall(r"\d+", p.name)
                return int(nums[0]) if nums else p.name.lower()
            img_files = sorted([str(f.resolve()) for f in raw_files], key=lambda x: sort_key(Path(x)))
            if img_files:
                dur = 5.0
                auto_scenes = []
                cur_t = 0.0
                for idx, img_p in enumerate(img_files):
                    end_t = round(cur_t + dur, 2)
                    auto_scenes.append(VisualScene(
                        scene_id=f"{idx+1:03d}",
                        start=cur_t,
                        end=end_t,
                        duration=dur,
                        visual_subject=Path(img_p).stem,
                        image_path=img_p
                    ))
                    cur_t = end_t
                self.scenes = auto_scenes
                self._refresh_cards()
                self.images_updated.emit(self.scenes)
                return
            else:
                QMessageBox.information(self, "No Images Found", "No image files found in the selected folder.")
                return

        updated_scenes, bound_count = AssetManager.auto_bind_images_to_scenes(self.scenes, self.images_folder)
        self.scenes = updated_scenes
        self._refresh_cards()
        self.images_updated.emit(self.scenes)

    def _refresh_cards(self):
        # Clear existing cards cleanly
        for card in self._cards:
            self.grid_layout.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

        if not self.scenes:
            self.match_status_lbl.setText("No scenes loaded.")
            return

        bound_count = sum(1 for s in self.scenes if s.image_path and Path(s.image_path).exists())
        self.match_status_lbl.setText(f"Matched {bound_count} / {len(self.scenes)} images")
        if bound_count == len(self.scenes):
            self.match_status_lbl.setStyleSheet("color: #4ade80; font-size: 12px; font-weight: bold;")
        else:
            self.match_status_lbl.setStyleSheet("color: #fbbf24; font-size: 12px;")

        cols = 3
        for i, sc in enumerate(self.scenes):
            card = SceneImageCard(i, sc, self.grid_container)
            card.image_changed.connect(self._on_card_image_changed)
            r = i // cols
            c = i % cols
            self.grid_layout.addWidget(card, r, c)
            self._cards.append(card)

    def _on_card_image_changed(self, scene_index: int, image_path: str):
        if 0 <= scene_index < len(self.scenes):
            self.scenes[scene_index].image_path = image_path
            bound_count = sum(1 for s in self.scenes if s.image_path and Path(s.image_path).exists())
            self.match_status_lbl.setText(f"Matched {bound_count} / {len(self.scenes)} images")
            self.images_updated.emit(self.scenes)
