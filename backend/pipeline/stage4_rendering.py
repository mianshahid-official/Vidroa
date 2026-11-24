"""
Stage 4: Image Assignment and Local Video Rendering for PromptBeast.
Matches generated images to storyboard scenes, tracks missing assets,
and performs local FFmpeg compilation with Ken Burns motion, audio, and subtitles.
Zero Modal dependency.
"""
import os
import re
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable

from app.models.scene import VisualScene
from app.models.timeline import NarrationData
from app.models.video_config import VideoRenderSettings
from app.core.video_renderer import VideoRenderer


class Stage4RenderingManager:
    """
    Stage 4: Manages image asset assignment and triggers local FFmpeg video rendering.
    """

    @classmethod
    def bind_images_from_directory(
        cls,
        scenes: List[VisualScene],
        images_dir: str
    ) -> Dict[str, Any]:
        """
        Auto-binds images in directory to scenes matching by scene_id or numeric index.
        Recognizes formats: 'scene_001.png', '001.png', 'scene-001.jpg', '1.jpg', 'shot_01.webp', etc.
        """
        img_p = Path(images_dir)
        if not img_p.exists() or not img_p.is_dir():
            return {
                "assigned": 0,
                "missing": len(scenes),
                "missing_scene_ids": [s.scene_id for s in scenes],
                "unassigned_files": []
            }

        valid_extensions = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
        files = [f for f in img_p.iterdir() if f.is_file() and f.suffix.lower() in valid_extensions]

        # Map scene_id and integer index to scene objects
        scenes_by_id: Dict[str, VisualScene] = {}
        scenes_by_num: Dict[int, VisualScene] = {}

        for s in scenes:
            scenes_by_id[s.scene_id.lower()] = s
            try:
                num = int(s.scene_id)
                scenes_by_num[num] = s
            except ValueError:
                pass
            if s.index:
                scenes_by_num[s.index] = s

        assigned_scenes = set()
        assigned_files = set()

        for f in sorted(files):
            stem = f.stem.lower()
            # Direct match
            if stem in scenes_by_id:
                scenes_by_id[stem].image_path = str(f.resolve())
                assigned_scenes.add(scenes_by_id[stem].scene_id)
                assigned_files.add(f.name)
                continue

            # Accurate extraction: handles '01_Wide...', '001.png', 'scene_002', 'shot3'
            from app.core.asset_manager import extract_scene_number_from_filename
            val = extract_scene_number_from_filename(f.name)
            if val in scenes_by_num:
                matched_s = scenes_by_num[val]
                matched_s.image_path = str(f.resolve())
                assigned_scenes.add(matched_s.scene_id)
                assigned_files.add(f.name)
                continue

        missing_ids = [s.scene_id for s in scenes if s.scene_id not in assigned_scenes and not s.image_path]
        unassigned = [f.name for f in files if f.name not in assigned_files]

        return {
            "assigned": len(scenes) - len(missing_ids),
            "missing": len(missing_ids),
            "missing_scene_ids": missing_ids,
            "unassigned_files": unassigned
        }

    @classmethod
    def validate_assets_for_rendering(
        cls,
        scenes: List[VisualScene],
        audio_path: Optional[str] = None,
        allow_placeholders: bool = True
    ) -> Dict[str, Any]:
        """
        Verifies that all scenes have valid image files and that audio is present.
        """
        errors = []
        warnings = []

        if not audio_path or not Path(audio_path).exists():
            errors.append(f"Audio file missing or not found: {audio_path}")

        if not scenes:
            errors.append("Storyboard contains zero scenes.")

        missing_scenes = []
        for s in scenes:
            if not s.image_path or not Path(s.image_path).exists():
                missing_scenes.append(s.scene_id)

        if missing_scenes:
            msg = f"{len(missing_scenes)} scenes have missing images: {', '.join(missing_scenes[:10])}..."
            if allow_placeholders:
                warnings.append(f"{msg} (Placeholders will be automatically generated).")
            else:
                errors.append(msg)

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "missing_count": len(missing_scenes)
        }

    @classmethod
    def render_video_local(
        cls,
        scenes: List[VisualScene],
        audio_path: str,
        output_video_path: str,
        settings: Optional[VideoRenderSettings] = None,
        narration: Optional[NarrationData] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> str:
        """
        Renders complete video locally using FFmpeg with Ken Burns effects, audio, and subtitles.
        Never calls Modal for video rendering.
        """
        if not VideoRenderer.is_ffmpeg_available():
            raise RuntimeError("Local FFmpeg executable not found in system PATH. Please ensure FFmpeg is installed.")

        # Ensure placeholders exist for any missing image
        temp_placeholder_dir = Path(output_video_path).parent / "temp_placeholders"
        for idx, s in enumerate(scenes):
            if not s.image_path or not Path(s.image_path).exists():
                temp_placeholder_dir.mkdir(parents=True, exist_ok=True)
                ph_path = temp_placeholder_dir / f"placeholder_{s.scene_id}.png"
                if not ph_path.exists():
                    VideoRenderer.create_placeholder_image(
                        output_path=str(ph_path),
                        scene_num=idx + 1,
                        scene_title=s.visual_subject or s.narration_excerpt[:40]
                    )
                s.image_path = str(ph_path.resolve())

        # Execute local FFmpeg rendering
        rendered_file = VideoRenderer.render_video_sync(
            scenes=scenes,
            audio_path=audio_path,
            output_video_path=output_video_path,
            settings=settings,
            narration=narration,
            progress_callback=progress_callback
        )

        return rendered_file

