"""
Data models for generation jobs, stages, progress, and cloud communication.
"""
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class JobStage(str, Enum):
    QUEUED = "queued"
    AUDIO = "audio_synthesis"
    # Stage 1-8 formal redesign stages
    SCRIPT_ANALYSIS = "script_analysis"
    CONTINUITY_BIBLE = "continuity_bible"
    VISUAL_PLANNING = "visual_planning"
    TEMPORAL_SCHEDULING = "temporal_scheduling"
    PROMPT_GENERATION = "prompt_generation"
    QUALITY_AUDIT = "quality_audit"
    AUTOMATIC_REPLANNING = "automatic_replanning"
    FINAL_VALIDATION = "final_validation"

    # Compatibility aliases
    ANALYSIS = "story_analysis"
    ANALYZING = "story_analysis"
    PLANNING = "visual_planning"
    GENERATING = "prompt_generation"
    VALIDATING = "validation"
    REGENERATING = "regeneration"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProgressInfo(BaseModel):
    stage: JobStage = JobStage.QUEUED
    status: JobStatus = JobStatus.QUEUED
    progress_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    current_batch: int = 0
    total_batches: int = 0
    scenes_generated: int = 0
    total_scenes_target: int = 0
    regenerated_count: int = 0
    message: str = "Initializing..."
    analysis_completed: bool = False
    planning_completed: bool = False
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class GenerationJob(BaseModel):
    job_id: str = Field(..., description="Unique UUID for cloud generation job")
    project_id: str
    status: JobStatus = JobStatus.QUEUED
    stage: JobStage = JobStage.QUEUED
    progress: ProgressInfo = Field(default_factory=ProgressInfo)
    settings: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
