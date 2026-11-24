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
    modal_api_url: str = Field(default="")
    api_key: Optional[str] = Field(default="")
    api_keys: List[str] = Field(default_factory=list)
    auth_token: Optional[str] = Field(default="")
    default_model: str = Field(default=DEFAULT_MODEL)
    default_subject_id: str = Field(default="history")
    default_visual_style_id: str = Field(default="zombie_survival")
    default_min_duration: float = Field(default=DEFAULT_MIN_DURATION)
    default_preferred_duration: float = Field(default=4.5)
    default_max_duration: float = Field(default=6.0)
    default_batch_size: int = Field(default=DEFAULT_BATCH_SIZE)
    workspace_directory: str = Field(default_factory=lambda: str(get_default_workspace_dir()))
    recent_projects: List[str] = Field(default_factory=list)
    auto_save_interval_seconds: int = Field(default=60)
    window_geometry: Optional[Dict[str, int]] = None
    pexels_api_key: Optional[str] = Field(default="", description="Pexels Stock Video API Key")
    pixabay_api_key: Optional[str] = Field(default="", description="Pixabay Stock Video API Key")


class SettingsManager:
    """Manages reading and writing application settings."""

    @classmethod
    def get_settings_file_path(cls) -> Path:
        base_dir = Path(__file__).resolve().parent.parent.parent
        # Prefer local repository config to prevent cross-app collision
        local_config = base_dir / "config" / "user_settings.json"
        local_config.parent.mkdir(parents=True, exist_ok=True)
        return local_config

    @classmethod
    def load_settings(cls) -> AppSettings:
        path = cls.get_settings_file_path()
        base_dir = Path(__file__).resolve().parent.parent.parent
        default_ws = str(get_default_workspace_dir().resolve())

        if not path.exists():
            # Check home fallback
            home_config = Path.home() / ".promptbeast" / "settings.json"
            if home_config.exists():
                try:
                    with open(home_config, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    settings = AppSettings(**data)
                    cls.save_settings(settings)
                    return settings
                except Exception:
                    pass

            # Check environment variables
            env_url = os.environ.get("PROMPTBEAST_API_URL")
            env_key = os.environ.get("GROQ_API_KEY") or os.environ.get("PROMPTBEAST_API_KEY")
            env_token = os.environ.get("AUTH_TOKEN")
            env_pexels = os.environ.get("PEXELS_API_KEY", "")
            env_pixabay = os.environ.get("PIXABAY_API_KEY", "")
            settings = AppSettings(
                workspace_directory=default_ws,
                pexels_api_key=env_pexels,
                pixabay_api_key=env_pixabay
            )
            if env_url:
                settings.modal_api_url = env_url
            if env_key:
                settings.api_key = env_key
                settings.api_keys = [k.strip() for k in env_key.split(",") if k.strip()]
            if env_token:
                settings.auth_token = env_token
            cls.save_settings(settings)
            return settings

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            settings = AppSettings(**data)
            
            # Guarantee workspace directory stays strictly inside current app repository
            ws_path = str(settings.workspace_directory or "").strip()
            base_str = str(base_dir.resolve()).lower()
            
            if (not ws_path or
                "v2promptbeast" in ws_path.lower() or
                "promptbeast_projects" in ws_path.lower() or
                not ws_path.lower().startswith(base_str) or
                not Path(ws_path).exists()):
                settings.workspace_directory = default_ws

            # Clean recent_projects so they only show projects from this workspace
            clean_recents = []
            for rp in settings.recent_projects:
                if rp and Path(rp).exists() and "v2promptbeast" not in rp.lower() and str(Path(rp).resolve()).lower().startswith(base_str):
                    clean_recents.append(str(Path(rp).resolve()))
            settings.recent_projects = clean_recents

            # Ensure api_key and api_keys stay in sync
            if settings.api_key and not settings.api_keys:
                settings.api_keys = [settings.api_key.strip()]
            elif settings.api_keys:
                if not settings.api_key or settings.api_key not in settings.api_keys:
                    settings.api_key = settings.api_keys[0].strip()
                settings.api_key = settings.api_keys[0].strip()

            # Auto-discover from local groq api.txt if keys are still empty
            if not settings.api_keys:
                candidate_api_files = [
                    base_dir / "groq api.txt",
                    Path.cwd() / "groq api.txt",
                ]
                for caf in candidate_api_files:
                    if caf.exists():
                        try:
                            with open(caf, "r", encoding="utf-8") as f:
                                k_list = [ln.strip() for ln in f if ln.strip().startswith("gsk_")]
                                if k_list:
                                    settings.api_keys = k_list
                                    settings.api_key = k_list[0]
                                    break
                        except Exception:
                            pass

            cls.save_settings(settings)
            return settings
        except Exception:
            fallback = AppSettings(workspace_directory=default_ws)
            cls.save_settings(fallback)
            return fallback

    @classmethod
    def save_settings(cls, settings: AppSettings) -> None:
        base_dir = Path(__file__).resolve().parent.parent.parent
        # Save to local repository config
        local_config = base_dir / "config" / "user_settings.json"
        local_config.parent.mkdir(parents=True, exist_ok=True)
        with open(local_config, "w", encoding="utf-8") as f:
            json.dump(settings.model_dump(), f, indent=2)

        # Also sync to global user config for external tool compatibility
        home_config = Path.home() / ".promptbeast" / "settings.json"
        try:
            home_config.parent.mkdir(parents=True, exist_ok=True)
            with open(home_config, "w", encoding="utf-8") as f:
                json.dump(settings.model_dump(), f, indent=2)
        except Exception:
            pass

    @classmethod
    def add_recent_project(cls, project_dir: str) -> None:
        settings = cls.load_settings()
        resolved = str(Path(project_dir).resolve())
        if resolved in settings.recent_projects:
            settings.recent_projects.remove(resolved)
        settings.recent_projects.insert(0, resolved)
        settings.recent_projects = settings.recent_projects[:10]
        cls.save_settings(settings)
