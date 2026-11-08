"""
High-performance FFmpeg Video Rendering Engine.
Compiles storyboard scenes, image assets, Ken Burns camera motion,
voiceover audio, and dynamic karaoke subtitles into upload-ready MP4 videos.
"""
import os
import re
import subprocess
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any, Tuple
from PIL import Image, ImageDraw, ImageFont

try:
    from PySide6.QtCore import QThread, Signal, QObject
except (ImportError, ModuleNotFoundError):
    class QObject:
        def __init__(self, parent=None): pass
    class QThread:
        def __init__(self, parent=None): pass
        def start(self): pass
        def isRunning(self): return False
        def terminate(self): pass
        def wait(self): pass
    class Signal:
        def __init__(self, *args): pass
        def emit(self, *args): pass
        def connect(self, *args): pass

from app.models.scene import VisualScene
from app.models.timeline import NarrationData
from app.models.video_config import (
    VideoRenderSettings,
    AspectRatio,
    MotionPreset,
    VideoOverlay,
    SubtitlePreset
)
from app.core.subtitle_engine import SubtitleEngine


def escape_ffmpeg_filter_path(path_str: str) -> str:
    r"""
    Escapes a file path for FFmpeg filtergraph strings on Windows and Unix.
    Colons and backslashes need escaping: 'D:\path\sub.ass' -> 'D\:/path/sub.ass'
    """
    p = str(Path(path_str).resolve()).replace("\\", "/")
    # Escape colon after drive letter e.g. D: -> D\:
    if len(p) >= 2 and p[1] == ":":
        p = p[0] + "\\:" + p[2:]
    # Escape single quotes and brackets if any
    p = p.replace("'", "\\'").replace("[", "\\[").replace("]", "\\]")
    return p


class VideoRenderer:
    """Core video rendering engine using FFmpeg."""

    @staticmethod
    def is_ffmpeg_available() -> bool:
        """Checks if ffmpeg is accessible on system PATH."""
        return shutil.which("ffmpeg") is not None

    @classmethod
    def create_placeholder_image(
        cls,
        output_path: str,
        scene_num: int,
        scene_title: str,
        width: int = 1920,
        height: int = 1080
    ) -> str:
        """Creates a professional placeholder image if an image asset is missing for a scene."""
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        # Gradient dark slate background
        img = Image.new("RGB", (width, height), color=(18, 24, 38))
        draw = ImageDraw.Draw(img)

        # Subtle grid / box decoration
        margin = int(width * 0.05)
        draw.rectangle(
            [margin, margin, width - margin, height - margin],
            outline=(45, 55, 75),
            width=3
        )

        header_text = f"SCENE {scene_num:02d}"
        body_text = scene_title if len(scene_title) < 60 else (scene_title[:57] + "...")

        # Draw text
        try:
            font_lg = ImageFont.truetype("arial.ttf", int(height * 0.06))
            font_sm = ImageFont.truetype("arial.ttf", int(height * 0.035))
        except Exception:
            font_lg = ImageFont.load_default()
            font_sm = ImageFont.load_default()

        draw.text((width // 2, height // 2 - 40), header_text, fill=(0, 210, 255), anchor="mm", font=font_lg)
        draw.text((width // 2, height // 2 + 30), body_text, fill=(200, 210, 225), anchor="mm", font=font_sm)

        img.save(out_p, "JPEG", quality=90)
        return str(out_p.resolve())

    @classmethod
    def build_zoompan_filter(
        cls,
        motion: MotionPreset,
        scene_index: int,
        duration_sec: float,
        fps: int,
        target_w: int,
        target_h: int,
        zoom_factor: float = 1.15
    ) -> str:
        """
        Builds the FFmpeg filter for shake-free static video or soft, smooth Ken Burns camera motion.
        """
        dur_frames = max(1, int(round(duration_sec * fps)))

        eff_motion = motion
        if motion == MotionPreset.SUBTLE_ALTERNATING:
            eff_motion = MotionPreset.ZOOM_IN if (scene_index % 2 == 0) else MotionPreset.ZOOM_OUT

        # Clean, 100% shake-free static video (preserves authentic torn/worn paper edges)
        if eff_motion == MotionPreset.STATIC or eff_motion is None:
            return (
                f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
                f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black,"
                f"setsar=1,fps={fps},trim=duration={duration_sec:.3f},setpts=PTS-STARTPTS"
            )

        # Smooth Ken Burns (with trunc rounding to eliminate FFmpeg integer pixel wobble/jitter)
        zoom_range = max(0.04, zoom_factor - 1.0)
        step = zoom_range / max(1, dur_frames)

        if eff_motion == MotionPreset.ZOOM_IN:
            z_expr = f"min(zoom+{step:.5f},{zoom_factor:.3f})"
            x_expr = "trunc(iw/2-(iw/zoom/2))"
            y_expr = "trunc(ih/2-(ih/zoom/2))"
        elif eff_motion == MotionPreset.ZOOM_OUT:
            z_expr = f"if(lte(zoom,1.0),{zoom_factor:.3f},max(1.0,zoom-{step:.5f}))"
            x_expr = "trunc(iw/2-(iw/zoom/2))"
            y_expr = "trunc(ih/2-(ih/zoom/2))"
        elif eff_motion == MotionPreset.PAN_LEFT_RIGHT:
            pan_speed = (target_w * 0.06) / max(1, dur_frames)
            z_expr = "1.08"
            x_expr = f"if(lte(on,1),0,min(iw-iw/zoom,x+{pan_speed:.3f}))"
            y_expr = "trunc(ih/2-(ih/zoom/2))"
        elif eff_motion == MotionPreset.PAN_RIGHT_LEFT:
            pan_speed = (target_w * 0.06) / max(1, dur_frames)
            z_expr = "1.08"
            x_expr = f"if(lte(on,1),iw-iw/zoom,max(0,x-{pan_speed:.3f}))"
            y_expr = "trunc(ih/2-(ih/zoom/2))"
        else:
            return (
                f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
                f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black,"
                f"setsar=1,fps={fps},trim=duration={duration_sec:.3f},setpts=PTS-STARTPTS"
            )

        return (
            f"scale={target_w*2}:{target_h*2}:force_original_aspect_ratio=increase,"
            f"crop={target_w*2}:{target_h*2},"
            f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d={dur_frames}:s={target_w}x{target_h}:fps={fps},"
            f"trim=duration={duration_sec:.3f},setpts=PTS-STARTPTS"
        )

    @classmethod
    def render_video(
        cls,
        scenes: List[VisualScene],
        audio_path: str,
        output_video_path: str,
        settings: Optional[VideoRenderSettings] = None,
        narration: Optional[NarrationData] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> str:
        return cls.render_video_sync(
            scenes=scenes,
            audio_path=audio_path,
            output_video_path=output_video_path,
            settings=settings,
            narration=narration,
            progress_callback=progress_callback
        )

    @classmethod
    def render_video_sync(
        cls,
        scenes: List[VisualScene],
        audio_path: str,
        output_video_path: str,
        settings: Optional[VideoRenderSettings] = None,
        narration: Optional[NarrationData] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> str:
        """
        Compiles scenes, images, Ken Burns motion, voiceover, and subtitles into MP4.
        """
        if not cls.is_ffmpeg_available():
            raise RuntimeError("FFmpeg is not installed or not found on system PATH.")

        if not scenes:
            raise ValueError("No scenes provided for video rendering.")

        audio_p = Path(audio_path)
        if not audio_p.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        cfg = settings or VideoRenderSettings()
        
        # Robust aspect ratio resolution (handles enum, string, or tuple)
        ar = getattr(cfg, "aspect_ratio", AspectRatio.LANDSCAPE_16_9)
        if isinstance(ar, str):
            if "9:16" in ar or "vertical" in ar.lower():
                target_w, target_h = (1080, 1920)
            elif "1:1" in ar or "square" in ar.lower():
                target_w, target_h = (1080, 1080)
            else:
                target_w, target_h = (1920, 1080)
        elif hasattr(ar, "dimensions"):
            target_w, target_h = ar.dimensions
        elif isinstance(ar, (list, tuple)) and len(ar) >= 2:
            target_w, target_h = (int(ar[0]), int(ar[1]))
        else:
            target_w, target_h = (1920, 1080)

        fps = cfg.fps
        out_p = Path(output_video_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        temp_dir = Path(tempfile.mkdtemp(prefix="promptbeast_render_"))

        try:
            if progress_callback:
                progress_callback(5.0, "Preparing scene visual assets...")

            # 1. Resolve image paths for all scenes, generating placeholders if necessary
            prepared_images: List[str] = []
            for i, sc in enumerate(scenes):
                if sc.image_path and Path(sc.image_path).exists():
                    prepared_images.append(sc.image_path)
                else:
                    placeholder_file = str(temp_dir / f"placeholder_{i+1:03d}.jpg")
                    cls.create_placeholder_image(
                        placeholder_file,
                        scene_num=i + 1,
                        scene_title=getattr(sc, "visual_summary", None) or getattr(sc, "visual_subject", sc.scene_id),
                        width=target_w,
                        height=target_h
                    )
                    prepared_images.append(placeholder_file)

            # 2. Memory-Safe Segmented Rendering (Immune to Out-Of-Memory and Windows CMD length limits)
            # Phase 1: Encode motion segments scene-by-scene (O(1) memory per scene)
            seg_files: List[Path] = []
            total_scenes = len(scenes)

            for i, (sc, img_path) in enumerate(zip(scenes, prepared_images)):
                dur = max(0.5, sc.duration)
                zoom_filter = cls.build_zoompan_filter(
                    motion=cfg.motion_preset,
                    scene_index=i,
                    duration_sec=dur,
                    fps=fps,
                    target_w=target_w,
                    target_h=target_h,
                    zoom_factor=cfg.motion_intensity
                )
                seg_file = temp_dir / f"seg_{i:04d}.ts"
                seg_cmd = [
                    "ffmpeg", "-y",
                    "-loop", "1", "-t", str(dur), "-i", img_path,
                    "-vf", zoom_filter,
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-crf", "18",
                    "-pix_fmt", "yuv420p",
                    "-r", str(fps),
                    str(seg_file)
                ]
                proc = subprocess.run(seg_cmd, capture_output=True, text=True)
                if proc.returncode != 0:
                    raise RuntimeError(f"Failed encoding scene #{i+1} motion segment:\n{proc.stderr}")
                seg_files.append(seg_file)

                if progress_callback:
                    pct = 5.0 + ((i + 1) / total_scenes) * 65.0
                    progress_callback(round(pct, 1), f"Rendering camera motion: Scene {i+1}/{total_scenes} ({pct:.0f}%)")

            # Phase 2: Create concat list for seamless demuxer joining
            concat_txt = temp_dir / "concat_list.txt"
            with open(concat_txt, "w", encoding="utf-8") as f:
                for sf in seg_files:
                    f.write(f"file '{sf.name}'\n")

            # Phase 3: Final Composite Pass with audio, visual overlays, and karaoke subtitles
            current_v = "[0:v]"
            filter_chains = []

            # Overlays
            if cfg.video_overlay == VideoOverlay.SUBTLE_VIGNETTE:
                filter_chains.append(f"{current_v}vignette=PI/5[v_vig]")
                current_v = "[v_vig]"
            elif cfg.video_overlay == VideoOverlay.LETTERBOX_CINEMATIC:
                bar_h = int(target_h * 0.10)
                filter_chains.append(f"{current_v}drawbox=x=0:y=0:w={target_w}:h={bar_h}:color=black@1.0:t=fill,drawbox=x=0:y={target_h-bar_h}:w={target_w}:h={bar_h}:color=black@1.0:t=fill[v_lb]")
                current_v = "[v_lb]"

            # Subtitles
            sub_preset = getattr(cfg.subtitle_config, "preset", SubtitlePreset.NONE)
            if sub_preset != SubtitlePreset.NONE:
                effective_narration = narration
                if not effective_narration or not effective_narration.words:
                    effective_narration = SubtitleEngine.synthesize_narration_from_scenes(scenes)

                if effective_narration and effective_narration.words:
                    sub_file = str(temp_dir / "subtitles.ass")
                    SubtitleEngine.generate_ass_subtitles(
                        narration=effective_narration,
                        output_ass_path=sub_file,
                        config=cfg.subtitle_config,
                        target_w=target_w,
                        target_h=target_h
                    )
                    escaped_sub = escape_ffmpeg_filter_path(sub_file)
                    filter_chains.append(f"{current_v}ass='{escaped_sub}'[vfinal]")
                    current_v = "[vfinal]"

            final_cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", str(concat_txt.name),
                "-i", str(audio_p.resolve())
            ]

            if filter_chains:
                final_cmd.extend(["-filter_complex", ";\n".join(filter_chains), "-map", current_v])
            else:
                final_cmd.extend(["-map", "0:v"])

            # Calculate total expected duration
            total_duration = max(1.0, sum(sc.duration for sc in scenes))
            if narration and narration.duration_seconds > 0:
                total_duration = min(total_duration, narration.duration_seconds)

            final_cmd.extend([
                "-map", "1:a",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "20",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                "-movflags", "+faststart",
                str(out_p.resolve())
            ])

            if progress_callback:
                progress_callback(72.0, "Compiling final video with audio & subtitles...")

            process = subprocess.Popen(
                final_cmd,
                cwd=str(temp_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                encoding="utf-8",
                errors="replace"
            )

            time_pattern = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")

            while True:
                line = process.stderr.readline()
                if not line and process.poll() is not None:
                    break
                if not line:
                    continue

                match = time_pattern.search(line)
                if match and total_duration > 0:
                    hrs = int(match.group(1))
                    mins = int(match.group(2))
                    secs = float(match.group(3))
                    current_sec = hrs * 3600 + mins * 60 + secs
                    pct = min(99.0, 72.0 + (current_sec / total_duration) * 27.0)
                    if progress_callback:
                        progress_callback(round(pct, 1), f"Finalizing render: {current_sec:.1f}s / {total_duration:.1f}s ({pct:.0f}%)")

            returncode = process.wait()
            if returncode != 0:
                err_output = process.stderr.read() if process.stderr else ""
                raise RuntimeError(f"FFmpeg final composite failed (exit code {returncode}):\n{err_output}")

            if progress_callback:
                progress_callback(100.0, f"Final video ready: {out_p.name}")

            return str(out_p.resolve())

        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)


class VideoRenderWorker(QThread):
    """
    Background worker thread for asynchronous video rendering with Qt signals.
    """
    progress = Signal(float, str)
    finished = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        scenes: List[VisualScene],
        audio_path: str,
        output_video_path: str,
        settings: Optional[VideoRenderSettings] = None,
        narration: Optional[NarrationData] = None,
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        self.scenes = scenes
        self.audio_path = audio_path
        self.output_video_path = output_video_path
        self.settings = settings
        self.narration = narration
        self._is_cancelled = False

    def run(self):
        try:
            def cb(pct: float, msg: str):
                if not self._is_cancelled:
                    self.progress.emit(pct, msg)

            out_file = VideoRenderer.render_video_sync(
                scenes=self.scenes,
                audio_path=self.audio_path,
                output_video_path=self.output_video_path,
                settings=self.settings,
                narration=self.narration,
                progress_callback=cb
            )
            if not self._is_cancelled:
                self.finished.emit(out_file)
        except Exception as e:
            if not self._is_cancelled:
                self.error.emit(str(e))

    def cancel(self):
        self._is_cancelled = True
