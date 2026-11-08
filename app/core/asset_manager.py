"""
Image Asset Manager for scanning, auto-matching, and binding generated images to scenes.
"""
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from PIL import Image
from app.models.scene import VisualScene


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


class AssetManager:
    """Discovers generated images and binds them to scenes."""

    @classmethod
    def scan_folder_for_images(cls, folder_path: str) -> List[Path]:
        path = Path(folder_path)
        if not path.exists() or not path.is_dir():
            return []

        images = []
        for file in sorted(path.iterdir()):
            if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS:
                images.append(file)
        return images

    @classmethod
    def auto_bind_images_to_scenes(
        cls,
        scenes: List[VisualScene],
        images_folder: str,
        has_batch_thumbnail: Optional[bool] = None
    ) -> Tuple[List[VisualScene], int]:
        """
        Matches images in images_folder to scenes based on scene ID numbers or sequential order.
        Supports YouTube batch generation contract:
        - Image 01 is the YouTube Thumbnail cover.
        - Story scenes begin at Image 02 (Scene 1 -> Image 02, Scene 2 -> Image 03, etc.).
        Returns (updated_scenes, bound_count).
        """
        image_files = cls.scan_folder_for_images(images_folder)
        if not image_files or not scenes:
            return scenes, 0

        # Build index map: try to extract numbers from filenames e.g. "001", "scene_2", "img-3"
        number_map: Dict[int, Path] = {}
        for img in image_files:
            nums = re.findall(r"\d+", img.stem)
            if nums:
                try:
                    num_val = int(nums[-1])
                    number_map[num_val] = img
                except ValueError:
                    pass

        # Detect Batch Thumbnail contract:
        # If user explicitly specifies or if total images >= len(scenes) + 1 and image 1 exists
        if has_batch_thumbnail is None:
            has_batch_thumbnail = bool(len(image_files) >= len(scenes) + 1 and 1 in number_map and 2 in number_map)

        offset = 1 if has_batch_thumbnail else 0

        bound_count = 0
        updated_scenes = []

        for i, sc in enumerate(scenes):
            sc_copy = sc.model_copy(deep=True)
            scene_num = i + 1
            # Try matching parsed scene_id e.g. "001" -> 1
            try:
                scene_id_num = int(re.findall(r"\d+", sc.scene_id)[-1])
            except (IndexError, ValueError):
                scene_id_num = scene_num

            target_num = scene_id_num + offset

            # 1. Match by extracted number
            if target_num in number_map:
                sc_copy.image_path = str(number_map[target_num].resolve())
                bound_count += 1
            # 2. Sequential fallback if within list range
            elif (i + offset) < len(image_files):
                sc_copy.image_path = str(image_files[i + offset].resolve())
                bound_count += 1

            updated_scenes.append(sc_copy)

        return updated_scenes, bound_count

    @classmethod
    def generate_thumbnail(
        cls,
        image_path: str,
        thumb_size: Tuple[int, int] = (160, 90)
    ) -> Optional[str]:
        """Generates and caches a lightweight thumbnail file for UI previews."""
        img_p = Path(image_path)
        if not img_p.exists():
            return None

        thumb_dir = img_p.parent / ".thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        thumb_path = thumb_dir / f"thumb_{img_p.stem}.jpg"

        if thumb_path.exists() and thumb_path.stat().st_mtime >= img_p.stat().st_mtime:
            return str(thumb_path.resolve())

        try:
            with Image.open(img_p) as img:
                img = img.convert("RGB")
                img.thumbnail(thumb_size, Image.Resampling.LANCZOS)
                img.save(thumb_path, "JPEG", quality=85)
            return str(thumb_path.resolve())
        except Exception:
            return None
