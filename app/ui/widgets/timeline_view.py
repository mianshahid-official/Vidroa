"""
Interactive QPainter-based Visual Timeline Widget for PromptBeast.
"""
from typing import List, Optional
from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QSize
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QFont,
    QFontMetrics,
    QMouseEvent,
    QWheelEvent,
    QLinearGradient,
)
from PySide6.QtWidgets import QWidget, QToolTip
from app.models.scene import VisualScene


class TimelineCanvas(QWidget):
    """Custom canvas rendering timeline ruler, scene blocks, and scrub playhead."""

    scene_selected = Signal(str) # scene_id
    playhead_moved = Signal(float) # seconds

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumHeight(130)
        self.setFocusPolicy(Qt.StrongFocus)

        self.scenes: List[VisualScene] = []
        self.selected_scene_id: Optional[str] = None
        self.hovered_scene_id: Optional[str] = None
        self.playhead_time: float = 0.0

        # Rendering scale
        self.pixels_per_second: float = 24.0 # default scale
        self.min_pixels_per_second: float = 5.0
        self.max_pixels_per_second: float = 120.0
        self.ruler_height: int = 28
        self.block_height: int = 70
        self.margin_left: int = 16
        self.margin_top: int = 8

        # Colors
        self.bg_color = QColor("#0A0D14")
        self.ruler_bg = QColor("#0F1420")
        self.ruler_tick = QColor("#334155")
        self.ruler_text = QColor("#64748B")
        self.block_bg = QColor("#161F30")
        self.block_border = QColor("#2A3854")
        self.block_selected_border = QColor("#6366F1")
        self.block_hover_border = QColor("#38BDF8")
        self.playhead_color = QColor("#06B6D4")

    def set_scenes(self, scenes: List[VisualScene], select_first: bool = False):
        self.scenes = scenes
        if select_first and scenes:
            self.selected_scene_id = scenes[0].scene_id
        self._update_geometry()
        self.update()

    def set_selected_scene_id(self, scene_id: Optional[str]):
        if self.selected_scene_id != scene_id:
            self.selected_scene_id = scene_id
            self.update()

    def set_playhead_time(self, seconds: float):
        self.playhead_time = max(0.0, seconds)
        self.update()

    def zoom_in(self):
        self.pixels_per_second = min(self.max_pixels_per_second, self.pixels_per_second * 1.25)
        self._update_geometry()
        self.update()

    def zoom_out(self):
        self.pixels_per_second = max(self.min_pixels_per_second, self.pixels_per_second / 1.25)
        self._update_geometry()
        self.update()

    def fit_to_width(self, available_width: Optional[int] = None):
        if not self.scenes:
            return
        total_dur = self.scenes[-1].end if self.scenes else 1.0
        if total_dur <= 0:
            return
        width = available_width if available_width is not None else self.parentWidget().width() if self.parentWidget() else self.width()
        usable_width = max(100, width - self.margin_left * 2 - 40)
        self.pixels_per_second = max(self.min_pixels_per_second, min(self.max_pixels_per_second, usable_width / total_dur))
        self._update_geometry()
        self.update()

    def _update_geometry(self):
        total_dur = self.scenes[-1].end if self.scenes else 60.0
        total_width = int(self.margin_left * 2 + total_dur * self.pixels_per_second + 100)
        self.setMinimumWidth(total_width)

    def sizeHint(self) -> QSize:
        total_dur = self.scenes[-1].end if self.scenes else 60.0
        w = int(self.margin_left * 2 + total_dur * self.pixels_per_second + 100)
        return QSize(max(800, w), 140)

    def time_to_x(self, t: float) -> float:
        return self.margin_left + t * self.pixels_per_second

    def x_to_time(self, x: float) -> float:
        return max(0.0, (x - self.margin_left) / self.pixels_per_second)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background
        painter.fillRect(self.rect(), self.bg_color)

        # Draw Ruler
        self._draw_ruler(painter)

        # Draw Scene Blocks
        self._draw_scene_blocks(painter)

        # Draw Playhead
        self._draw_playhead(painter)

    def _draw_ruler(self, painter: QPainter):
        ruler_rect = QRectF(0, 0, self.width(), self.ruler_height)
        painter.fillRect(ruler_rect, self.ruler_bg)

        # Bottom ruler line
        painter.setPen(QPen(QColor("#1E293B"), 1))
        painter.drawLine(0, self.ruler_height, self.width(), self.ruler_height)

        # Determine tick step (1s, 5s, 10s, 30s)
        if self.pixels_per_second >= 40:
            step = 1.0
            sub_step = 0.5
        elif self.pixels_per_second >= 15:
            step = 5.0
            sub_step = 1.0
        elif self.pixels_per_second >= 6:
            step = 10.0
            sub_step = 5.0
        else:
            step = 30.0
            sub_step = 10.0

        total_dur = self.scenes[-1].end + 10.0 if self.scenes else 60.0
        font = QFont("Segoe UI", 8)
        painter.setFont(font)

        t = 0.0
        while t <= total_dur:
            x = self.time_to_x(t)
            if x > self.width():
                break

            # Major tick
            painter.setPen(QPen(self.ruler_tick, 1.5))
            painter.drawLine(int(x), self.ruler_height - 10, int(x), self.ruler_height)

            # Label
            mins = int(t // 60)
            secs = int(t % 60)
            lbl = f"{mins:02d}:{secs:02d}"
            painter.setPen(self.ruler_text)
            painter.drawText(QRectF(x - 20, 4, 40, 14), Qt.AlignCenter, lbl)

            # Minor ticks
            if sub_step > 0:
                st = t + sub_step
                while st < t + step and st <= total_dur:
                    sx = self.time_to_x(st)
                    painter.setPen(QPen(QColor("#1E293B"), 1))
                    painter.drawLine(int(sx), self.ruler_height - 5, int(sx), self.ruler_height)
                    st += sub_step

            t += step

    def _draw_scene_blocks(self, painter: QPainter):
        if not self.scenes:
            painter.setPen(QColor("#475569"))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(QRectF(self.margin_left, 45, 400, 30), Qt.AlignLeft, "No storyboard scenes generated yet.")
            return

        block_y = self.ruler_height + self.margin_top
        for sc in self.scenes:
            x_start = self.time_to_x(sc.start)
            x_end = self.time_to_x(sc.end)
            w = max(28.0, x_end - x_start - 2.0) # 2px gap

            rect = QRectF(x_start, block_y, w, self.block_height)
            is_selected = (sc.scene_id == self.selected_scene_id)
            is_hovered = (sc.scene_id == self.hovered_scene_id)

            # Gradient background
            grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            if is_selected:
                grad.setColorAt(0, QColor("#312E81"))
                grad.setColorAt(1, QColor("#1E1B4B"))
            elif is_hovered:
                grad.setColorAt(0, QColor("#1E293B"))
                grad.setColorAt(1, QColor("#172033"))
            else:
                grad.setColorAt(0, QColor("#131B2A"))
                grad.setColorAt(1, QColor("#0D131F"))

            painter.setBrush(QBrush(grad))

            # Border Pen
            if is_selected:
                pen = QPen(self.block_selected_border, 2)
            elif is_hovered:
                pen = QPen(self.block_hover_border, 1.5)
            elif sc.is_manually_edited:
                pen = QPen(QColor("#F59E0B"), 1)
            else:
                pen = QPen(self.block_border, 1)

            painter.setPen(pen)
            painter.drawRoundedRect(rect, 6, 6)

            # Top Badge Bar
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.setPen(QColor("#F8FAFC") if is_selected else QColor("#94A3B8"))
            id_rect = QRectF(rect.x() + 6, rect.y() + 6, rect.width() - 12, 16)
            painter.drawText(id_rect, Qt.AlignLeft | Qt.AlignVCenter, f"#{sc.scene_id}")

            # Duration badge
            if rect.width() > 50:
                painter.setFont(QFont("Segoe UI", 8))
                painter.setPen(QColor("#38BDF8"))
                dur_text = f"{sc.duration:.1f}s"
                painter.drawText(id_rect, Qt.AlignRight | Qt.AlignVCenter, dur_text)

            # Visual Subject snippet
            if rect.width() > 60:
                painter.setFont(QFont("Segoe UI", 8))
                painter.setPen(QColor("#CBD5E1") if is_selected else QColor("#64748B"))
                subj_rect = QRectF(rect.x() + 6, rect.y() + 24, rect.width() - 12, 28)
                subj_text = sc.visual_subject or sc.narration_excerpt
                metrics = QFontMetrics(painter.font())
                elided = metrics.elidedText(subj_text, Qt.ElideRight, int(subj_rect.width()))
                painter.drawText(subj_rect, Qt.AlignLeft | Qt.AlignTop, elided)

            # Manually Edited Dot
            if sc.is_manually_edited:
                painter.setBrush(QBrush(QColor("#F59E0B")))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(QPointF(rect.right() - 8, rect.bottom() - 8), 3, 3)

    def _draw_playhead(self, painter: QPainter):
        px = self.time_to_x(self.playhead_time)
        if px < 0 or px > self.width():
            return

        painter.setPen(QPen(self.playhead_color, 2))
        painter.drawLine(int(px), 0, int(px), self.height())

        # Playhead triangle handle
        painter.setBrush(QBrush(self.playhead_color))
        handle = [
            QPointF(px - 5, 0),
            QPointF(px + 5, 0),
            QPointF(px, 8)
        ]
        painter.drawPolygon(handle)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            click_time = self.x_to_time(event.position().x())
            self.playhead_time = click_time
            self.playhead_moved.emit(click_time)

            # Find clicked scene
            for sc in self.scenes:
                if sc.start <= click_time <= sc.end:
                    self.selected_scene_id = sc.scene_id
                    self.scene_selected.emit(sc.scene_id)
                    break
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        hover_time = self.x_to_time(event.position().x())
        found_sc = None
        for sc in self.scenes:
            if sc.start <= hover_time <= sc.end:
                found_sc = sc
                break

        if found_sc:
            if self.hovered_scene_id != found_sc.scene_id:
                self.hovered_scene_id = found_sc.scene_id
                tip = (
                    f"Scene {found_sc.scene_id} ({found_sc.start:.2f}s - {found_sc.end:.2f}s, {found_sc.duration:.2f}s)\n"
                    f"Subject: {found_sc.visual_subject}\n"
                    f"Narration: \"{found_sc.narration_excerpt}\""
                )
                QToolTip.showText(event.globalPosition().toPoint(), tip, self)
                self.update()
        else:
            if self.hovered_scene_id is not None:
                self.hovered_scene_id = None
                self.update()

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() == Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)
