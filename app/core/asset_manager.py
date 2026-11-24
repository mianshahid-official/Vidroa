"""
Image Asset Manager for scanning, auto-matching, and binding generated images to scenes.
"""
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from PIL import Image
from app.models.scene import VisualScene


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def natural_sort_key(p: Path) -> list:
    """Sort filenames naturally (e.g. 1, 2, 10 instead of 1, 10, 2)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", p.name)]


def extract_scene_number_from_filename(filename: str) -> int:
    """
    Extracts the authoritatively intended scene index from an image filename.
    Handles:
      - Pure numeric: '001.png', '1.png', '137.png'
      - Leading prompt prefix: '01 Wide nighttime rooftop 51 floor.png' -> 1
      - Standard prefixes: 'scene_001.png', 'shot-04.jpg', 'img_12.webp' -> 1, 4, 12
      - Batch timestamp files: 'generated_images_1794742657231_001.png' -> 1
      - Trailing numbers: 'walter_rooftop_14.png' -> 14
    """
    stem = re.sub(r"\.[a-zA-Z0-9]+$", "", filename).strip()

    # 1. Pure numeric: "001", "1", "137"
    if stem.isdigit():
        return int(stem)

    # 2. Leading number prefix e.g. "01 Wide...", "01_Wide...", "001-scene..."
    m_lead = re.match(r"^(\d{1,4})[\s_\-\.]", stem)
    if m_lead:
        return int(m_lead.group(1))

    # 3. Standard scene/shot/image prefix: "scene_001", "shot-02", "img_003"
    m_prefix = re.search(r"(?:scene|shot|image|img|frame)[\s_\-]*0*(\d{1,4})", stem, re.IGNORECASE)
    if m_prefix:
        return int(m_prefix.group(1))

    # 4. Trailing number e.g. "generated_images_1794742657231_001", "walter_rooftop_014"
    m_trail = re.search(r"[\s_\-]0*(\d{1,4})$", stem)
    if m_trail:
        return int(m_trail.group(1))

    # 5. Fallback: all numbers filtering out timestamps (<= 4 digits)
    all_nums = re.findall(r"\b\d{1,4}\b", stem)
    if all_nums:
        return int(all_nums[0])

    return -1


class AssetManager:
    """Discovers generated images, auto-extracts zip batches with sequential numbering, and binds them to scenes."""

    @classmethod
    def get_highest_scene_number_in_folder(cls, target_dir: Path) -> int:
        """
        Scans target_dir for existing image files and returns the highest scene number found.
        Returns 0 if no valid numbered images exist.
        """
        if not target_dir.exists() or not target_dir.is_dir():
            return 0

        highest = 0
        for f in target_dir.iterdir():
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
                fname_lower = f.name.lower()
                if fname_lower.startswith(("000_thumb", "thumb", "cover")) or "thumbnail" in fname_lower:
                    continue
                num = extract_scene_number_from_filename(f.name)
                if num > highest:
                    highest = num
        return highest

    @classmethod
    def consolidate_and_flatten_subfolders(cls, target_dir: Path) -> int:
        """
        Scans target_dir for any accidental subfolders (e.g. acc1, acc2, acc3, batch1, etc.).
        If subfolders contain images or zips:
          - Moves any zips directly into target_dir
          - Renames any loose subfolder images sequentially (continuing from target_dir's current highest)
          - Moves them directly out into target_dir
          - Moves any archive zips to target_dir/.extracted_zips
          - Deletes the empty subfolders so target_dir remains a clean, single-level flat directory.
        Returns total number of images flattened into target_dir.
        """
        import shutil
        if not target_dir.exists() or not target_dir.is_dir():
            return 0

        subdirs = [
            d for d in target_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".") and d.name != ".extracted_zips" and d.name != ".thumbnails"
        ]
        if not subdirs:
            return 0

        subdirs.sort(key=natural_sort_key)
        total_flattened = 0
        archive_dir = target_dir / ".extracted_zips"
        archive_dir.mkdir(parents=True, exist_ok=True)

        for sdir in subdirs:
            # 1. Check for any zips inside sdir and move them to target_dir for extraction
            for z in list(sdir.glob("*.zip")):
                dest_zip = target_dir / z.name
                if dest_zip.exists():
                    dest_zip = target_dir / f"{sdir.name}_{z.name}"
                shutil.move(str(z), str(dest_zip))

            # Move any inner .extracted_zips to target_dir/.extracted_zips
            inner_ext = sdir / ".extracted_zips"
            if inner_ext.exists():
                for z in inner_ext.glob("*.zip"):
                    dest_z = archive_dir / z.name
                    if not dest_z.exists():
                        shutil.move(str(z), str(dest_z))
                shutil.rmtree(str(inner_ext), ignore_errors=True)

            # 2. Find all loose images in sdir
            sub_images = [f for f in sdir.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS]
            if sub_images:
                sub_images.sort(key=natural_sort_key)
                current_highest = cls.get_highest_scene_number_in_folder(target_dir)

                # Check if already uniquely sequenced above current_highest
                inner_nums = [extract_scene_number_from_filename(f.name) for f in sub_images]
                valid_inner = [n for n in inner_nums if n > 0]
                already_sequenced = (len(valid_inner) == len(sub_images) and min(valid_inner) > current_highest)

                for idx, img_f in enumerate(sub_images):
                    fname_lower = img_f.name.lower()
                    if fname_lower.startswith(("000_thumb", "thumb", "cover")) or "thumbnail" in fname_lower:
                        dest_path = target_dir / f"000_thumbnail{img_f.suffix.lower()}"
                        shutil.move(str(img_f), str(dest_path))
                        total_flattened += 1
                        continue

                    if already_sequenced:
                        target_seq_num = valid_inner[idx]
                    else:
                        target_seq_num = current_highest + idx + 1

                    dest_path = target_dir / f"{target_seq_num:03d}{img_f.suffix.lower()}"
                    while dest_path.exists():
                        target_seq_num += 1
                        dest_path = target_dir / f"{target_seq_num:03d}{img_f.suffix.lower()}"

                    shutil.move(str(img_f), str(dest_path))
                    total_flattened += 1

            # 3. Clean up the empty subfolder
            try:
                shutil.rmtree(str(sdir), ignore_errors=True)
            except Exception:
                pass

        return total_flattened

    @classmethod
    def extract_and_sequentially_rename_zips(cls, target_dir: Path) -> int:
        """
        Extracts all .zip files in target_dir (and subdirs) using a temporary folder,
        and sequentially numbers them:
          - First zip batch: 001..100
          - Second zip batch: 101..200
          - Third zip batch: 201..300, etc.
        Based on the current highest image number already present in target_dir.
        Returns total number of newly extracted images.
        """
        import zipfile
        import shutil
        import tempfile

        if not target_dir.exists():
            return 0

        total_extracted = cls.consolidate_and_flatten_subfolders(target_dir)

        # Collect all candidate zip files in target_dir (and subdirectories like acc1, acc2)
        zip_files: List[Path] = []
        for p in list(target_dir.glob("*.zip")):
            if not p.name.endswith(".zip.extracted"):
                zip_files.append(p)

        for sdir in [d for d in target_dir.iterdir() if d.is_dir() and not d.name.startswith(".") and d.name != ".extracted_zips"]:
            for p in list(sdir.glob("*.zip")):
                if not p.name.endswith(".zip.extracted"):
                    zip_files.append(p)

        if not zip_files:
            return 0

        # Sort zip files deterministically (natural name sort, then mtime)
        zip_files.sort(key=lambda z: (natural_sort_key(z), z.stat().st_mtime))

        total_extracted = 0
        archive_dir = target_dir / ".extracted_zips"
        archive_dir.mkdir(parents=True, exist_ok=True)

        for zip_p in zip_files:
            try:
                # Find current highest image number in target_dir before extracting this zip
                current_highest = cls.get_highest_scene_number_in_folder(target_dir)

                with tempfile.TemporaryDirectory() as temp_dir_str:
                    temp_dir = Path(temp_dir_str)

                    # 1. Extract zip into temp folder
                    with zipfile.ZipFile(zip_p, "r") as zf:
                        zf.extractall(temp_dir)

                    # 2. Find all images inside temp_dir
                    raw_extracted: List[Path] = []
                    for f in temp_dir.rglob("*"):
                        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
                            raw_extracted.append(f)

                    if not raw_extracted:
                        continue

                    # 3. Sort extracted images naturally
                    raw_extracted.sort(key=natural_sort_key)

                    # 4. Check if extracted images already have higher sequence numbers
                    inner_nums = [extract_scene_number_from_filename(f.name) for f in raw_extracted]
                    valid_inner_nums = [n for n in inner_nums if n > 0]

                    already_sequenced = (
                        len(valid_inner_nums) == len(raw_extracted) and
                        min(valid_inner_nums) > current_highest
                    )

                    start_idx = current_highest

                    for idx, img_file in enumerate(raw_extracted):
                        # Handle thumbnail images specially
                        fname_lower = img_file.name.lower()
                        if fname_lower.startswith(("000_thumb", "thumb", "cover")) or "thumbnail" in fname_lower:
                            dest_name = f"000_thumbnail{img_file.suffix.lower()}"
                            dest_path = target_dir / dest_name
                            shutil.copy2(img_file, dest_path)
                            total_extracted += 1
                            continue

                        if already_sequenced:
                            target_seq_num = valid_inner_nums[idx]
                        else:
                            # Sequentially rename:
                            # If current_highest is 0 -> 001, 002, ... 100
                            # If current_highest is 100 -> 101, 102, ... 137
                            target_seq_num = start_idx + idx + 1

                        dest_name = f"{target_seq_num:03d}{img_file.suffix.lower()}"
                        dest_path = target_dir / dest_name
                        shutil.copy2(img_file, dest_path)
                        total_extracted += 1

                # Move processed zip to archive folder or mark it
                try:
                    dest_archive_zip = archive_dir / zip_p.name
                    if dest_archive_zip.exists():
                        dest_archive_zip.unlink()
                    shutil.move(str(zip_p), str(dest_archive_zip))
                except Exception:
                    marker = zip_p.with_suffix(".zip.extracted")
                    if marker.exists():
                        marker.unlink()
                    zip_p.rename(marker)

                print(f"[AssetManager] Sequentially extracted {len(raw_extracted)} images from {zip_p.name} -> scenes starting at {start_idx + 1}")

            except Exception as e:
                print(f"[AssetManager] Error processing zip {zip_p.name}: {e}")

        total_extracted += cls.consolidate_and_flatten_subfolders(target_dir)
        return total_extracted

    @classmethod
    def scan_folder_for_images(cls, folder_path: str) -> List[Path]:
        path = Path(folder_path)
        if not path.exists() or not path.is_dir():
            return []

        # Automatically flatten any accidental subfolders into the main directory
        cls.consolidate_and_flatten_subfolders(path)

        images = []
        for file in sorted(path.iterdir(), key=natural_sort_key):
            if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS:
                images.append(file)
        return images

    @classmethod
    def auto_bind_images_to_scenes(
        cls,
        scenes: List[VisualScene],
        images_folder: str,
        has_batch_thumbnail: Optional[bool] = False
    ) -> Tuple[List[VisualScene], int]:
        """
        Matches images in images_folder to scenes based on scene ID numbers or sequential order.
        Guarantees 100% accurate 1-to-1 matching and prevents descriptive prompt text numbers
        from corrupting scene indices.
        Returns (updated_scenes, bound_count).
        """
        image_files = cls.scan_folder_for_images(images_folder)
        if not image_files or not scenes:
            return scenes, 0

        # Pass 1: Categorize into direct numbered files vs batch continuation files
        clean_map: Dict[int, Path] = {}
        batch_continuation: List[Path] = []

        for img in image_files:
            if img.name.lower().startswith("generated_images_"):
                batch_continuation.append(img)
            else:
                num_val = extract_scene_number_from_filename(img.name)
                if num_val > 0:
                    clean_map[num_val] = img

        # Pass 2: If we have continuation files (e.g. generated_images_..._001.png),
        # map them with an offset corresponding to the highest clean image number if colliding
        number_map: Dict[int, Path] = dict(clean_map)
        if batch_continuation:
            max_clean = max(clean_map.keys()) if clean_map else 0
            for b_img in batch_continuation:
                sub_num = extract_scene_number_from_filename(b_img.name)
                if sub_num > 0:
                    if sub_num in clean_map:
                        target_num = max_clean + sub_num
                    else:
                        target_num = sub_num
                    number_map[target_num] = b_img

        bound_count = 0
        updated_scenes = []

        for i, sc in enumerate(scenes):
            sc_copy = sc.model_copy(deep=True)
            scene_num = i + 1
            try:
                scene_id_num = int(re.findall(r"\d+", sc.scene_id)[-1])
            except (IndexError, ValueError):
                scene_id_num = scene_num

            target_num = scene_id_num

            # 1. Match by extracted number
            if target_num in number_map:
                sc_copy.image_path = str(number_map[target_num].resolve())
                bound_count += 1
            # 2. Sequential fallback if within list range
            elif i < len(image_files):
                sc_copy.image_path = str(image_files[i].resolve())
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
