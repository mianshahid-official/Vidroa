"""
Selected Scene Inspector and Prompt Editor widget.
"""
from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QDoubleSpinBox,
    QPushButton,
    QGroupBox,
    QFrame,
    QMessageBox,
    QInputDialog,
    QScrollArea,
)
from app.models.scene import VisualScene


class SceneEditorWidget(QWidget):
    """Inspector and Editor for the currently selected visual storyboard scene."""

    scene_updated = Signal(object)        # VisualScene
    regenerate_requested = Signal(str)    # scene_id
    split_requested = Signal(str, float)  # scene_id, split_time
    merge_requested = Signal(str)         # scene_id
    delete_requested = Signal(str)        # scene_id
    create_scene_requested = Signal()     # Request create new scene

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_scene: Optional[VisualScene] = None
        self._setup_ui()

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll Area to prevent layout crush
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header Bar
        header_layout = QHBoxLayout()
        self.scene_title_lbl = QLabel("No Scene Selected")
        self.scene_title_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #f8fafc;")
        header_layout.addWidget(self.scene_title_lbl)

        self.edited_badge = QLabel("MANUALLY EDITED")
        self.edited_badge.setStyleSheet(
            "background-color: #451a03; color: #f59e0b; border: 1px solid #b45309; "
            "border-radius: 4px; padding: 2px 8px; font-size: 10px; font-weight: 700;"
        )
        self.edited_badge.setVisible(False)
        header_layout.addWidget(self.edited_badge)

        header_layout.addStretch()

        self.save_status_lbl = QLabel("")
        self.save_status_lbl.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: bold;")
        header_layout.addWidget(self.save_status_lbl)

        layout.addLayout(header_layout)

        # Timing Box
        timing_group = QGroupBox("Scene Timing and Boundaries")
        timing_layout = QHBoxLayout(timing_group)
        timing_layout.setSpacing(10)

        # Start Time
        start_box = QVBoxLayout()
        start_box.addWidget(QLabel("Start Time (s):"))
        self.start_spin = QDoubleSpinBox()
        self.start_spin.setRange(0.0, 9999.0)
        self.start_spin.setDecimals(2)
        self.start_spin.setSingleStep(0.2)
        self.start_spin.valueChanged.connect(self._on_timing_changed)
        start_box.addWidget(self.start_spin)
        timing_layout.addLayout(start_box)

        # End Time
        end_box = QVBoxLayout()
        end_box.addWidget(QLabel("End Time (s):"))
        self.end_spin = QDoubleSpinBox()
        self.end_spin.setRange(0.0, 9999.0)
        self.end_spin.setDecimals(2)
        self.end_spin.setSingleStep(0.2)
        self.end_spin.valueChanged.connect(self._on_timing_changed)
        end_box.addWidget(self.end_spin)
        timing_layout.addLayout(end_box)

        # Duration Display
        dur_box = QVBoxLayout()
        dur_box.addWidget(QLabel("Duration:"))
        self.dur_val_lbl = QLabel("0.00s")
        self.dur_val_lbl.setStyleSheet("font-size: 14px; font-weight: 700; color: #38bdf8; padding: 4px;")
        dur_box.addWidget(self.dur_val_lbl)
        timing_layout.addLayout(dur_box)

        layout.addWidget(timing_group)

        # Narration Excerpt
        narration_group = QGroupBox("Spoken Narration Excerpt")
        narration_layout = QVBoxLayout(narration_group)
        self.narration_edit = QPlainTextEdit()
        self.narration_edit.setPlaceholderText("Spoken narration corresponding to this visual scene...")
        self.narration_edit.setMaximumHeight(65)
        narration_layout.addWidget(self.narration_edit)
        layout.addWidget(narration_group)

        # Visual Details
        visual_group = QGroupBox("Visual Subject and Framing")
        visual_layout = QVBoxLayout(visual_group)

        subj_layout = QHBoxLayout()
        subj_layout.addWidget(QLabel("Visual Subject:"))
        self.subject_input = QLineEdit()
        self.subject_input.setPlaceholderText("Core subject of this scene...")
        subj_layout.addWidget(self.subject_input)
        visual_layout.addLayout(subj_layout)

        framing_layout = QHBoxLayout()
        framing_layout.addWidget(QLabel("Framing / Angle:"))
        self.framing_input = QLineEdit()
        self.framing_input.setPlaceholderText("e.g. Wide establishing shot, Eye-level medium...")
        framing_layout.addWidget(self.framing_input)
        visual_layout.addLayout(framing_layout)

        layout.addWidget(visual_group)

        # Large Prompt Editor
        prompt_group = QGroupBox("Image Generation Prompt")
        prompt_layout = QVBoxLayout(prompt_group)

        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setPlaceholderText("Detailed generation prompt...")
        self.prompt_edit.setMinimumHeight(90)
        self.prompt_edit.textChanged.connect(self._on_prompt_text_changed)
        prompt_layout.addWidget(self.prompt_edit)

        # Prompt statistics
        prompt_meta_layout = QHBoxLayout()
        self.word_count_lbl = QLabel("0 words | 0 chars")
        self.word_count_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        prompt_meta_layout.addWidget(self.word_count_lbl)
        prompt_meta_layout.addStretch()

        prompt_layout.addLayout(prompt_meta_layout)
        layout.addWidget(prompt_group)

        # Action Buttons
        btn_layout = QHBoxLayout()

        self.save_btn = QPushButton("💾 Save Changes")
        self.save_btn.setStyleSheet("background-color: #065f46; border: 1px solid #059669; color: #ffffff; font-weight: 600; padding: 6px 12px; border-radius: 4px;")
        self.save_btn.clicked.connect(self._on_save_clicked)
        btn_layout.addWidget(self.save_btn)

        self.regen_btn = QPushButton("⚡ Regenerate")
        self.regen_btn.setStyleSheet("background-color: #4f46e5; border: 1px solid #6366f1; color: #ffffff; padding: 6px 12px; border-radius: 4px;")
        self.regen_btn.clicked.connect(self._on_regenerate_clicked)
        btn_layout.addWidget(self.regen_btn)

        self.split_btn = QPushButton("✂ Split")
        self.split_btn.setStyleSheet("background-color: #334155; color: #ffffff; padding: 6px 10px; border-radius: 4px;")
        self.split_btn.clicked.connect(self._on_split_clicked)
        btn_layout.addWidget(self.split_btn)

        self.merge_btn = QPushButton("☍ Merge")
        self.merge_btn.setStyleSheet("background-color: #334155; color: #ffffff; padding: 6px 10px; border-radius: 4px;")
        self.merge_btn.clicked.connect(self._on_merge_clicked)
        btn_layout.addWidget(self.merge_btn)

        self.delete_btn = QPushButton("🗑 Delete")
        self.delete_btn.setStyleSheet("background-color: #7f1d1d; border: 1px solid #991b1b; color: #fca5a5; padding: 6px 10px; border-radius: 4px;")
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        btn_layout.addWidget(self.delete_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

        scroll.setWidget(container)
        root_layout.addWidget(scroll)

        self.setEnabled(False)

    def load_scene(self, scene: Optional[VisualScene]):
        self._current_scene = scene
        self.save_status_lbl.setText("")
        if scene is None:
            self.scene_title_lbl.setText("No Scene Selected")
            self.edited_badge.setVisible(False)
            self.start_spin.setValue(0.0)
            self.end_spin.setValue(0.0)
            self.dur_val_lbl.setText("0.00s")
            self.narration_edit.setPlainText("")
            self.subject_input.setText("")
            self.framing_input.setText("")
            self.prompt_edit.setPlainText("")
            self.setEnabled(False)
            return

        self.setEnabled(True)
        self.scene_title_lbl.setText(f"Scene #{scene.scene_id}")
        self.edited_badge.setVisible(scene.is_manually_edited)

        # Block signals to avoid triggering callbacks while loading
        self.start_spin.blockSignals(True)
        self.end_spin.blockSignals(True)
        self.prompt_edit.blockSignals(True)

        self.start_spin.setValue(scene.start)
        self.end_spin.setValue(scene.end)
        self.dur_val_lbl.setText(f"{scene.duration:.2f}s")
        self.narration_edit.setPlainText(scene.narration_excerpt)
        self.subject_input.setText(scene.visual_subject)
        self.framing_input.setText(scene.framing_suggestion or "")
        self.prompt_edit.setPlainText(scene.prompt)

        self.start_spin.blockSignals(False)
        self.end_spin.blockSignals(False)
        self.prompt_edit.blockSignals(False)

        self._update_word_count()

    def _on_timing_changed(self):
        start = self.start_spin.value()
        end = self.end_spin.value()
        dur = round(max(0.0, end - start), 2)
        self.dur_val_lbl.setText(f"{dur:.2f}s")

    def _on_prompt_text_changed(self):
        self._update_word_count()

    def _update_word_count(self):
        text = self.prompt_edit.toPlainText().strip()
        words = len(text.split()) if text else 0
        chars = len(text)
        self.word_count_lbl.setText(f"{words} words | {chars} chars")

    def _on_save_clicked(self):
        if not self._current_scene:
            return

        start = self.start_spin.value()
        end = self.end_spin.value()
        if end <= start:
            QMessageBox.warning(self, "Invalid Timing", "End time must be greater than start time.")
            return

        updated = self._current_scene.model_copy(deep=True)
        updated.start = round(start, 3)
        updated.end = round(end, 3)
        updated.duration = round(end - start, 3)
        updated.narration_excerpt = self.narration_edit.toPlainText().strip()
        updated.visual_subject = self.subject_input.text().strip()
        updated.framing_suggestion = self.framing_input.text().strip()
        updated.prompt = self.prompt_edit.toPlainText().strip()
        updated.is_manually_edited = True

        self._current_scene = updated
        self.edited_badge.setVisible(True)
        self.save_status_lbl.setText("✅ Saved!")
        self.scene_updated.emit(updated)

    def _on_regenerate_clicked(self):
        if self._current_scene:
            self.regenerate_requested.emit(self._current_scene.scene_id)

    def _on_split_clicked(self):
        if not self._current_scene:
            return
        default_mid = round((self._current_scene.start + self._current_scene.end) / 2.0, 2)
        split_time, ok = QInputDialog.getDouble(
            self,
            "Split Scene",
            f"Enter split timestamp between {self._current_scene.start:.2f}s and {self._current_scene.end:.2f}s:",
            default_mid,
            self._current_scene.start + 0.1,
            self._current_scene.end - 0.1,
            2
        )
        if ok:
            self.split_requested.emit(self._current_scene.scene_id, split_time)

    def _on_merge_clicked(self):
        if self._current_scene:
            self.merge_requested.emit(self._current_scene.scene_id)

    def _on_delete_clicked(self):
        if not self._current_scene:
            return
        res = QMessageBox.question(
            self,
            "Delete Scene",
            f"Are you sure you want to delete Scene #{self._current_scene.scene_id}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if res == QMessageBox.Yes:
            self.delete_requested.emit(self._current_scene.scene_id)
