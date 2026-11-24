"""
API Request and Response schemas for PromptBeast Desktop Studio and Inference Engine.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from app.models.project import ImageCountMode, TimingMode, ProjectConfig
from app.models.timeline import WordTimestamp, NarrationData
from app.models.scene import VisualScene, StoryAnalysis, StoryContinuity
from app.models.job import JobStage, JobStatus, ProgressInfo


class JobCreateRequest(BaseModel):
    project_name: str
    story_text: str
    narration: Optional[NarrationData] = None
    subject_id: str = "history"
    custom_subject: Optional[str] = None
    visual_style_id: str = "zombie_survival"
    custom_style: Optional[str] = None
    image_count_mode: ImageCountMode = ImageCountMode.AUTOMATIC
    target_image_count: int = 30
    timing_mode: TimingMode = TimingMode.AI_DECIDES
    min_duration: float = 3.0
    preferred_duration: float = 5.0
    max_duration: float = 8.0
    batch_size: int = 10
    model_name: str = "qwen/qwen3.8-27b"

    def to_config(self) -> ProjectConfig:
        return ProjectConfig(
            subject_id=self.subject_id,
            custom_subject=self.custom_subject,
            visual_style_id=self.visual_style_id,
            custom_style=self.custom_style,
            image_count_mode=self.image_count_mode,
            target_image_count=self.target_image_count,
            timing_mode=self.timing_mode,
            min_duration=self.min_duration,
            preferred_duration=self.preferred_duration,
            max_duration=self.max_duration,
        )


class JobCreateResponse(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.QUEUED
    message: str = "Job successfully queued for local Groq processing."


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    stage: JobStage
    progress: ProgressInfo
    analysis: Optional[StoryAnalysis] = None
    scenes: List[VisualScene] = Field(default_factory=list)
    error: Optional[str] = None


class JobCancelResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str


class SceneRegenerateRequest(BaseModel):
    scene: VisualScene
    story_summary: Optional[str] = ""
    subject_id: str = "history"
    custom_subject: Optional[str] = None
    visual_style_id: str = "zombie_survival"
    custom_style: Optional[str] = None
    continuity: Optional[StoryContinuity] = None
    model_name: str = "qwen/qwen3.8-27b"


class SceneRegenerateResponse(BaseModel):
    scene_id: str
    visual_subject: str
    prompt: str
    framing_suggestion: Optional[str] = None
    is_valid: bool = True
    validation_notes: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "1.0.0"
    gpu: str = "Local / Groq"
    model: str = "qwen/qwen3.8-27b"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConnectionTestResponse(BaseModel):
    connected: bool
    latency_ms: float
    message: str
    backend_info: Optional[HealthResponse] = None
