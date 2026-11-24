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

    @classmethod
    def get_all_subjects(cls) -> List[SubjectPreset]:
        if not cls._loaded:
            cls.initialize()
        return list(cls._subjects_cache.values())

    @classmethod
    def get_all_styles(cls) -> List[VisualStylePreset]:
        if not cls._loaded:
            cls.initialize()
        return list(cls._styles_cache.values())

    @classmethod
    def get_subject_by_id(cls, subject_id: str) -> Optional[SubjectPreset]:
        if not cls._loaded:
            cls.initialize()
        res = cls._subjects_cache.get(subject_id)
        if not res and cls._subjects_cache:
            return cls._subjects_cache.get("history") or list(cls._subjects_cache.values())[0]
        return res

    @classmethod
    def get_subject(cls, subject_id: str) -> Optional[SubjectPreset]:
        return cls.get_subject_by_id(subject_id)

    @classmethod
    def get_style_by_id(cls, style_id: str) -> Optional[VisualStylePreset]:
        if not cls._loaded:
            cls.initialize()

        if not style_id:
            style_id = "zombie_survival" if "zombie_survival" in cls._styles_cache else "century_old_photograph"

        # Direct hit check first
        if style_id in cls._styles_cache:
            return cls._styles_cache[style_id]

        # Aliases normalization
        sid = style_id.lower().strip()
        if sid in ("zombie", "zombies", "zombie_survival"):
            sid = "zombie_survival"
        elif sid in ("whatif", "what_if", "whatif_flat_vector", "flat_vector"):
            sid = "whatif_flat_vector"
        elif sid in ("vintage_photo", "vintage_photographs", "century_old_photographs"):
            sid = "century_old_photograph"
        elif sid in ("red_blue_stickman_3d", "3d_red_blue_stickman"):
            sid = "3d_red_blue_stickman"
        elif sid in ("2d_stick_figure", "2d_stickman"):
            sid = "2d_stickman"
        elif sid in ("3d_stick_figure", "3d_stickman"):
            sid = "3d_stickman"
        elif sid in ("black_white_historical_photography", "bw_historical_photography"):
            sid = "bw_vintage_historical_photography"
        elif sid in ("quilling", "paper_quill", "paper_quilling_illustration"):
            sid = "paper_quilling"
        elif sid in ("collage", "mixed_media", "mixed_media_collage_illustration"):
            sid = "mixed_media_collage"
        elif sid in ("cutout", "paper_cut", "paper_cutout_illustration"):
            sid = "paper_cutout"

        res = cls._styles_cache.get(sid)
        if not res and sid == "vintage_photograph":
            res = cls._styles_cache.get("century_old_photograph")
        elif not res and sid == "century_old_photograph":
            res = cls._styles_cache.get("vintage_photograph")

        if not res and cls._styles_cache:
            return cls._styles_cache.get("zombie_survival") or cls._styles_cache.get("century_old_photograph") or list(cls._styles_cache.values())[0]
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
    def save_custom_style(cls, preset: VisualStylePreset) -> None:
        STYLES_DIR.mkdir(parents=True, exist_ok=True)
        preset.is_custom = True
        filepath = STYLES_DIR / f"{preset.id}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(preset.model_dump(), f, indent=2)
        cls._styles_cache[preset.id] = preset

    @classmethod
    def delete_custom_style(cls, preset_id: str) -> None:
        cls._styles_cache.pop(preset_id, None)
        filepath = STYLES_DIR / f"{preset_id}.json"
        if filepath.exists():
            filepath.unlink()

    @classmethod
    def delete_custom_subject(cls, preset_id: str) -> None:
        cls._subjects_cache.pop(preset_id, None)
        filepath = SUBJECTS_DIR / f"{preset_id}.json"
        if filepath.exists():
            filepath.unlink()
