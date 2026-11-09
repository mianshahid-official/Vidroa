"""
User settings persistence using local JSON config.
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.config.constants import (
    DEFAULT_MODAL_API_URL,
    DEFAULT_MODEL,
    DEFAULT_MIN_DURATION,
    DEFAULT_PREFERRED_DURATION,
    DEFAULT_MAX_DURATION,
    DEFAULT_BATCH_SIZE,
)


def get_default_workspace_dir() -> Path:
    base_dir = Path(__file__).resolve().parent.parent.parent
    proj_dir = base_dir / "projects"
    proj_dir.mkdir(parents=True, exist_ok=True)
    return proj_dir


class AppSettings(BaseModel):
    modal_api_url: str = Field(default=DEFAULT_MODAL_API_URL)
    api_key: Optional[str] = Field(default="")
    auth_token: Optional[str] = Field(default="")
    default_model: str = Field(default=DEFAULT_MODEL)
    default_subject_id: str = Field(default="general_documentary")
    default_visual_style_id: str = Field(default="2d_stickman")
    default_min_duration: float = Field(default=DEFAULT_MIN_DURATION)
    default_preferred_duration: float = Field(default=4.5)
    default_max_duration: float = Field(default=6.0)
    default_batch_size: int = Field(default=DEFAULT_BATCH_SIZE)
    workspace_directory: str = Field(default_factory=lambda: str(get_default_workspace_dir()))
    recent_projects: List[str] = Field(default_factory=list)
    auto_save_interval_seconds: int = Field(default=60)
    window_geometry: Optional[Dict[str, int]] = None


class SettingsManager:
    """Manages reading and writing application settings."""

    _SETTINGS_FILE = Path.home() / ".promptbeast" / "settings.json"

    @classmethod
    def get_settings_file_path(cls) -> Path:
        cls._SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        return cls._SETTINGS_FILE

    @classmethod
    def load_settings(cls) -> AppSettings:
        path = cls.get_settings_file_path()
        if not path.exists():
            # Check environment variables
            env_url = os.environ.get("MODAL_API_URL") or os.environ.get("PROMPTBEAST_API_URL")
            env_key = os.environ.get("MODAL_API_KEY") or os.environ.get("PROMPTBEAST_API_KEY")
            env_token = os.environ.get("AUTH_TOKEN")
            settings = AppSettings()
            if env_url:
                settings.modal_api_url = env_url
            if env_key:
                settings.api_key = env_key
            if env_token:
                settings.auth_token = env_token
            cls.save_settings(settings)
            return settings

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            settings = AppSettings(**data)
            # Guarantee workspace directory stays in current project repository
            default_ws = str(get_default_workspace_dir())
            if not settings.workspace_directory or "PromptBeast_Projects" in settings.workspace_directory:
                settings.workspace_directory = default_ws
                cls.save_settings(settings)
            elif not Path(settings.workspace_directory).exists():
                settings.workspace_directory = default_ws
                cls.save_settings(settings)
            if not settings.modal_api_url or not settings.modal_api_url.startswith("http") or settings.modal_api_url.lower() in ("groq", "none", "null"):
                settings.modal_api_url = DEFAULT_MODAL_API_URL
                cls.save_settings(settings)
            return settings
        except Exception:
            return AppSettings()

    @classmethod
    def save_settings(cls, settings: AppSettings) -> None:
        path = cls.get_settings_file_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings.model_dump(), f, indent=2)

    @classmethod
    def add_recent_project(cls, project_dir: str) -> None:
        settings = cls.load_settings()
        resolved = str(Path(project_dir).resolve())
        if resolved in settings.recent_projects:
            settings.recent_projects.remove(resolved)
        settings.recent_projects.insert(0, resolved)
        settings.recent_projects = settings.recent_projects[:10]
        cls.save_settings(settings)
