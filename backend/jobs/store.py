"""
Thread-safe local in-memory Job Store for PromptBeast.
Operates 100% locally with zero cloud/Modal dependencies.
"""
import threading
from typing import Dict, Optional, List, Any
from datetime import datetime, timezone
from app.models.job import GenerationJob, JobStage, JobStatus, ProgressInfo
from app.models.scene import VisualScene, StoryAnalysis


class JobStore:
    """Manages active and historical generation jobs in thread-safe local memory."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(JobStore, cls).__new__(cls)
                cls._instance._local_jobs: Dict[str, GenerationJob] = {}
                cls._instance._local_analyses: Dict[str, StoryAnalysis] = {}
                cls._instance._local_scenes: Dict[str, List[VisualScene]] = {}
                cls._instance._local_cancelled: set = set()
        return cls._instance

    @property
    def _jobs(self):
        return self._local_jobs

    def create_job(self, job_id: str, project_id: str, settings: Dict[str, Any]) -> GenerationJob:
        with self._lock:
            now = datetime.now(timezone.utc)
            progress = ProgressInfo(
                stage=JobStage.QUEUED,
                status=JobStatus.QUEUED,
                progress_percentage=0.0,
                message="Job queued for local processing.",
                started_at=now,
                updated_at=now
            )
            job = GenerationJob(
                job_id=job_id,
                project_id=project_id,
                status=JobStatus.QUEUED,
                stage=JobStage.QUEUED,
                progress=progress,
                settings=settings,
                created_at=now
            )
            self._local_jobs[job_id] = job
            self._local_scenes[job_id] = []
            return job

    def get_job(self, job_id: str) -> Optional[GenerationJob]:
        with self._lock:
            return self._local_jobs.get(job_id)

    def get_analysis(self, job_id: str) -> Optional[StoryAnalysis]:
        with self._lock:
            return self._local_analyses.get(job_id)

    def set_analysis(self, job_id: str, analysis: StoryAnalysis) -> None:
        with self._lock:
            self._local_analyses[job_id] = analysis
            if job_id in self._local_jobs:
                self._local_jobs[job_id].progress.analysis_completed = True
                self._local_jobs[job_id].progress.updated_at = datetime.now(timezone.utc)

    def get_scenes(self, job_id: str) -> List[VisualScene]:
        with self._lock:
            return list(self._local_scenes.get(job_id, []))

    def set_scenes(self, job_id: str, scenes: List[VisualScene]) -> None:
        with self._lock:
            self._local_scenes[job_id] = list(scenes)
            if job_id in self._local_jobs:
                self._local_jobs[job_id].progress.scenes_generated = len(scenes)
                self._local_jobs[job_id].progress.updated_at = datetime.now(timezone.utc)

    def append_scenes_batch(self, job_id: str, batch: List[VisualScene]) -> None:
        with self._lock:
            if job_id not in self._local_scenes:
                self._local_scenes[job_id] = []
            self._local_scenes[job_id].extend(batch)
            if job_id in self._local_jobs:
                self._local_jobs[job_id].progress.scenes_generated = len(self._local_scenes[job_id])
                self._local_jobs[job_id].progress.updated_at = datetime.now(timezone.utc)

    def update_progress(
        self,
        job_id: str,
        stage: JobStage,
        status: JobStatus,
        percentage: float,
        message: str,
        current_batch: int = 0,
        total_batches: int = 0,
        error: Optional[str] = None
    ) -> None:
        with self._lock:
            if job_id in self._local_jobs:
                job = self._local_jobs[job_id]
                job.stage = stage
                job.status = status
                job.progress.stage = stage
                job.progress.status = status
                job.progress.progress_percentage = round(percentage, 1)
                job.progress.message = message
                job.progress.current_batch = current_batch
                job.progress.total_batches = total_batches
                job.progress.updated_at = datetime.now(timezone.utc)
                if error:
                    job.error = error
                    job.progress.error_message = error
                if status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                    job.completed_at = datetime.now(timezone.utc)

    def cancel_job(self, job_id: str) -> bool:
        with self._lock:
            self._local_cancelled.add(job_id)
            if job_id in self._local_jobs:
                job = self._local_jobs[job_id]
                job.status = JobStatus.CANCELLED
                job.stage = JobStage.CANCELLED
                job.progress.status = JobStatus.CANCELLED
                job.progress.message = "Job cancelled by user."
                job.completed_at = datetime.now(timezone.utc)
                return True
            return False

    def is_cancelled(self, job_id: str) -> bool:
        with self._lock:
            return job_id in self._local_cancelled
