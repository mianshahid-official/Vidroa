"""
Preset loader and manager for subjects and visual styles.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from app.models.presets import SubjectPreset, VisualStylePreset
from app.config.constants import SUBJECTS_DIR, STYLES_DIR


class PresetManager:
    """Discovers, loads, and manages subject and visual style presets."""

    _subjects_cache: Dict[str, SubjectPreset] = {}
    _styles_cache: Dict[str, VisualStylePreset] = {}
    _loaded: bool = False

    @classmethod
    def initialize(cls) -> None:
        """Loads all presets from disk into memory."""
        cls._subjects_cache.clear()
        cls._styles_cache.clear()

        # Load Subjects
        if SUBJECTS_DIR.exists():
            for p in sorted(SUBJECTS_DIR.glob("*.json")):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        preset = SubjectPreset(**data)
                        cls._subjects_cache[preset.id] = preset
                except Exception as e:
                    print(f"Error loading subject preset {p.name}: {e}")

        # Load Visual Styles
        if STYLES_DIR.exists():
            for p in sorted(STYLES_DIR.glob("*.json")):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        preset = VisualStylePreset(**data)
                        cls._styles_cache[preset.id] = preset
                except Exception as e:
                    print(f"Error loading visual style preset {p.name}: {e}")

        cls._loaded = True

    BUILTIN_STYLE_IDS = {
        "3d_stickman",
        "2d_stickman",
        "century_old_photograph",
        "vintage_photograph",
        "3d_red_blue_stickman",
        "bw_vintage_historical_photography",
        "paper_quilling",
        "mixed_media_collage",
        "paper_cutout",
    }

    @classmethod
    def is_builtin_style(cls, preset_id: str) -> bool:
        return preset_id in cls.BUILTIN_STYLE_IDS

    @classmethod
    def get_all_subjects(cls) -> List[SubjectPreset]:
        if not cls._loaded:
            cls.initialize()
        return list(cls._subjects_cache.values())

    @classmethod
    def get_all_styles(cls) -> List[VisualStylePreset]:
        """Returns visual style presets: canonical built-ins first, then custom styles."""
        if not cls._loaded:
            cls.initialize()

        canonical_order = [
            "3d_stickman",
            "2d_stickman",
            "century_old_photograph",
            "bw_vintage_historical_photography",
            "paper_quilling",
            "mixed_media_collage",
            "paper_cutout",
            "3d_red_blue_stickman",
        ]
        seen = set()
        result: List[VisualStylePreset] = []

        # 1. Built-in styles in canonical order
        for cid in canonical_order:
            p = cls._styles_cache.get(cid)
            if p and p.id not in seen:
                result.append(p)
                seen.add(p.id)
        # Suppress alias duplicate
        seen.add("vintage_photograph")

        # 2. Custom or newly added styles
        for p in sorted(cls._styles_cache.values(), key=lambda x: x.name):
            if p.id not in seen:
                result.append(p)
                seen.add(p.id)

        return result

    @classmethod
    def get_subject_by_id(cls, subject_id: str) -> Optional[SubjectPreset]:
        if not cls._loaded:
            cls.initialize()
        res = cls._subjects_cache.get(subject_id)
        if not res and cls._subjects_cache:
            return cls._subjects_cache.get("general_documentary") or list(cls._subjects_cache.values())[0]
        return res

    @classmethod
    def get_subject(cls, subject_id: str) -> Optional[SubjectPreset]:
        return cls.get_subject_by_id(subject_id)

    @classmethod
    def get_style_by_id(cls, style_id: str) -> Optional[VisualStylePreset]:
        if not cls._loaded:
            cls.initialize()
        # Aliases normalization
        if style_id in ("3d_stickman", "3d_stickman_style", "stickman_3d"):
            style_id = "3d_stickman"
        elif style_id in ("2d_stickman", "2d_stickman_style", "stickman_2d", "2d_stick_figure"):
            style_id = "2d_stickman"
        elif style_id in ("3d_red_blue_stickman", "red_blue_stickman_3d", "red_blue_stickman"):
            style_id = "3d_red_blue_stickman"
        elif style_id in ("vintage_photo", "vintage_photographs", "century_old_photographs"):
            style_id = "century_old_photograph"
        elif style_id in ("black_white_historical_photography", "bw_historical_photography"):
            style_id = "bw_vintage_historical_photography"
        elif style_id in ("quilling", "paper_quill", "paper_quilling_illustration"):
            style_id = "paper_quilling"
        elif style_id in ("collage", "mixed_media", "mixed_media_collage_illustration"):
            style_id = "mixed_media_collage"
        elif style_id in ("cutout", "paper_cut", "paper_cutout_illustration"):
            style_id = "paper_cutout"

        res = cls._styles_cache.get(style_id)
        if not res and style_id == "vintage_photograph":
            res = cls._styles_cache.get("century_old_photograph")
        elif not res and style_id == "century_old_photograph":
            res = cls._styles_cache.get("vintage_photograph")

        if not res and cls._styles_cache:
            return cls._styles_cache.get("2d_stickman") or list(cls._styles_cache.values())[0]
        return res

    @classmethod
    def get_style(cls, style_id: str) -> Optional[VisualStylePreset]:
        return cls.get_style_by_id(style_id)

    @classmethod
    def save_custom_subject(cls, preset: SubjectPreset) -> None:
        SUBJECTS_DIR.mkdir(parents=True, exist_ok=True)
        preset.is_custom = True
        filepath = SUBJECTS_DIR / f"{preset.id}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(preset.model_dump(), f, indent=2)
        cls._subjects_cache[preset.id] = preset

    @classmethod
    def save_custom_style(cls, preset: VisualStylePreset, preview_image_path: Optional[str] = None) -> None:
        STYLES_DIR.mkdir(parents=True, exist_ok=True)
        preset.is_custom = True
        filepath = STYLES_DIR / f"{preset.id}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(preset.model_dump(), f, indent=2)
        cls._styles_cache[preset.id] = preset

        if preview_image_path and Path(preview_image_path).exists():
            previews_dir = Path(__file__).resolve().parent.parent.parent / "assets" / "style_previews"
            previews_dir.mkdir(parents=True, exist_ok=True)
            dest_png = previews_dir / f"{preset.id}.png"
            try:
                import shutil
                shutil.copy2(preview_image_path, dest_png)
            except Exception as e:
                print(f"[PresetManager] Notice copying preview image: {e}")

    @classmethod
    def delete_custom_style(cls, preset_id: str) -> bool:
        """Safely deletes a custom visual style. Built-in core styles are protected."""
        if cls.is_builtin_style(preset_id):
            return False

        cls._styles_cache.pop(preset_id, None)
        filepath = STYLES_DIR / f"{preset_id}.json"
        if filepath.exists():
            try:
                filepath.unlink()
            except Exception as e:
                print(f"[PresetManager] Error removing style file {filepath}: {e}")

        # Remove preview image if present
        previews_dir = Path(__file__).resolve().parent.parent.parent / "assets" / "style_previews"
        for ext in (".png", ".jpg", ".jpeg"):
            t_path = previews_dir / f"{preset_id}{ext}"
            if t_path.exists():
                try:
                    t_path.unlink()
                except Exception:
                    pass
        return True

    @classmethod
    def delete_custom_subject(cls, preset_id: str) -> None:
        cls._subjects_cache.pop(preset_id, None)
        filepath = SUBJECTS_DIR / f"{preset_id}.json"
        if filepath.exists():
            filepath.unlink()
