"""
Data models for project configuration, state, and serialization.
"""
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from app.models.scene import VisualScene, StoryAnalysis, StoryContinuity
from app.models.timeline import NarrationData
from app.models.video_config import VideoRenderSettings


class ImageCountMode(str, Enum):
    AUTOMATIC = "automatic"
    EXACT = "exact"


class TimingMode(str, Enum):
    AI_DECIDES = "ai_decides"
    TARGET = "target"
    FIXED = "fixed"


class ProjectConfig(BaseModel):
    subject_id: str = Field(default="general_documentary", description="Selected subject ID")
    custom_subject: Optional[str] = Field(default=None, description="Custom subject guidance if subject is custom")
    visual_style_id: str = Field(default="2d_stickman", description="Selected visual style ID")
    custom_style: Optional[str] = Field(default=None, description="Custom style instructions")
    image_count_mode: ImageCountMode = Field(default=ImageCountMode.AUTOMATIC)
    target_image_count: int = Field(default=30, ge=1, le=500, description="Target scene count when exact mode is selected")
    timing_mode: TimingMode = Field(default=TimingMode.AI_DECIDES)
    min_duration: float = Field(default=0.5, ge=0.5, le=60.0, description="Minimum image duration in seconds")
    preferred_duration: float = Field(default=5.0, ge=1.0, le=60.0, description="Preferred image duration in seconds")
    max_duration: float = Field(default=6.0, ge=1.0, le=120.0, description="Maximum image duration in seconds")
    batch_size: int = Field(default=10, ge=1, le=50, description="Number of scenes generated per cloud batch")
    model_name: str = Field(default="Qwen3-30B-A3B-Instruct-2507")
    video_settings: VideoRenderSettings = Field(default_factory=VideoRenderSettings)


class ProjectState(BaseModel):
    story_raw_text: str = Field(default="")
    story_file_path: Optional[str] = None
    timestamps_file_path: Optional[str] = None
    audio_file_path: Optional[str] = None
    images_folder_path: Optional[str] = None
    narration: Optional[NarrationData] = None
    analysis: Optional[StoryAnalysis] = None
    scenes: List[VisualScene] = Field(default_factory=list)
    last_rendered_video_path: Optional[str] = None
    last_job_id: Optional[str] = None
    last_generation_status: Optional[str] = None
    thumbnail_headline: Optional[str] = None
    thumbnail_prompt: Optional[str] = None
    style_preset_id: Optional[str] = None
    is_dirty: bool = False


class StoryProject(BaseModel):
    name: str = Field(..., description="Project name")
    project_dir: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "1.0.0"
    config: ProjectConfig = Field(default_factory=ProjectConfig)
    state: ProjectState = Field(default_factory=ProjectState)

    @property
    def total_scenes(self) -> int:
        return len(self.state.scenes)

    @property
    def total_duration(self) -> float:
        if not self.state.scenes:
            if self.state.narration:
                return self.state.narration.duration_seconds
            return 0.0
        return round(self.state.scenes[-1].end - self.state.scenes[0].start, 3)
