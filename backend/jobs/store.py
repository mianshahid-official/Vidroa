"""
Thread-safe distributed Job Store for Modal cloud backend and local environments.
Supports real-time shared state across distributed serverless containers via modal.Dict.
"""
import threading
from typing import Dict, Optional, List, Any
from datetime import datetime, timezone
from app.models.job import GenerationJob, JobStage, JobStatus, ProgressInfo
from app.models.scene import VisualScene, StoryAnalysis


class JobStore:
    """Manages active and historical generation jobs using distributed modal.Dict or local memory."""

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
                cls._instance._modal_dict = None
                cls._instance._init_modal_dict()
        return cls._instance

    def _init_modal_dict(self):
        try:
            import modal
            if not modal.is_local():
                self._modal_dict = modal.Dict.from_name("promptbeast-jobs", create_if_missing=True)
        except Exception:
            self._modal_dict = None

    def _get_dict(self):
        if self._modal_dict is None:
            self._init_modal_dict()
        return self._modal_dict

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
                message="Job queued for processing.",
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

            m_dict = self._get_dict()
            if m_dict is not None:
                try:
                    m_dict[job_id] = {
                        "job": job.model_dump(mode="json"),
                        "analysis": None,
                        "scenes": [],
                        "cancelled": False
                    }
                except Exception as e:
                    print(f"[JobStore] Warning writing to modal.Dict: {e}")

            return job

    def get_job(self, job_id: str) -> Optional[GenerationJob]:
        with self._lock:
            m_dict = self._get_dict()
            if m_dict is not None:
                try:
                    if job_id in m_dict:
                        data = m_dict[job_id]
                        job_dict = data.get("job")
                        if job_dict:
                            job = GenerationJob(**job_dict)
                            self._local_jobs[job_id] = job
                            return job
                except Exception as e:
                    print(f"[JobStore] Warning reading from modal.Dict: {e}")

            return self._local_jobs.get(job_id)

    def get_analysis(self, job_id: str) -> Optional[StoryAnalysis]:
        with self._lock:
            m_dict = self._get_dict()
            if m_dict is not None:
                try:
                    if job_id in m_dict:
                        data = m_dict[job_id]
                        ana_dict = data.get("analysis")
                        if ana_dict:
                            return StoryAnalysis(**ana_dict)
                except Exception:
                    pass

            return self._local_analyses.get(job_id)

    def set_analysis(self, job_id: str, analysis: StoryAnalysis) -> None:
        with self._lock:
            self._local_analyses[job_id] = analysis
            if job_id in self._local_jobs:
                self._local_jobs[job_id].progress.analysis_completed = True
                self._local_jobs[job_id].progress.updated_at = datetime.now(timezone.utc)

            m_dict = self._get_dict()
            if m_dict is not None:
                try:
                    if job_id in m_dict:
                        data = dict(m_dict[job_id])
                        data["analysis"] = analysis.model_dump(mode="json")
                        if data.get("job"):
                            data["job"]["progress"]["analysis_completed"] = True
                            data["job"]["progress"]["updated_at"] = datetime.now(timezone.utc).isoformat()
                        m_dict[job_id] = data
                except Exception as e:
                    print(f"[JobStore] Error updating analysis in modal.Dict: {e}")

    def get_scenes(self, job_id: str) -> List[VisualScene]:
        with self._lock:
            m_dict = self._get_dict()
            if m_dict is not None:
                try:
                    if job_id in m_dict:
                        data = m_dict[job_id]
                        sc_list = data.get("scenes", [])
                        return [VisualScene(**s) for s in sc_list]
                except Exception:
                    pass

            return list(self._local_scenes.get(job_id, []))

    def set_scenes(self, job_id: str, scenes: List[VisualScene]) -> None:
        with self._lock:
            self._local_scenes[job_id] = scenes
            if job_id in self._local_jobs:
                self._local_jobs[job_id].progress.scenes_generated = len(scenes)
                self._local_jobs[job_id].progress.updated_at = datetime.now(timezone.utc)

            m_dict = self._get_dict()
            if m_dict is not None:
                try:
                    if job_id in m_dict:
                        data = dict(m_dict[job_id])
                        data["scenes"] = [s.model_dump(mode="json") for s in scenes]
                        if data.get("job"):
                            data["job"]["progress"]["scenes_generated"] = len(scenes)
                            data["job"]["progress"]["updated_at"] = datetime.now(timezone.utc).isoformat()
                        m_dict[job_id] = data
                except Exception as e:
                    print(f"[JobStore] Error updating scenes in modal.Dict: {e}")

    def append_scenes_batch(self, job_id: str, batch: List[VisualScene]) -> None:
        with self._lock:
            if job_id not in self._local_scenes:
                self._local_scenes[job_id] = []
            self._local_scenes[job_id].extend(batch)
            if job_id in self._local_jobs:
                self._local_jobs[job_id].progress.scenes_generated = len(self._local_scenes[job_id])
                self._local_jobs[job_id].progress.updated_at = datetime.now(timezone.utc)

            self.set_scenes(job_id, self._local_scenes[job_id])

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

            m_dict = self._get_dict()
            if m_dict is not None:
                try:
                    if job_id in m_dict:
                        data = dict(m_dict[job_id])
                        job_dict = data.get("job", {})
                        job_dict["stage"] = stage.value if hasattr(stage, "value") else str(stage)
                        job_dict["status"] = status.value if hasattr(status, "value") else str(status)
                        prog = job_dict.setdefault("progress", {})
                        prog["stage"] = stage.value if hasattr(stage, "value") else str(stage)
                        prog["status"] = status.value if hasattr(status, "value") else str(status)
                        prog["progress_percentage"] = round(percentage, 1)
                        prog["message"] = message
                        prog["current_batch"] = current_batch
                        prog["total_batches"] = total_batches
                        prog["updated_at"] = datetime.now(timezone.utc).isoformat()
                        if error:
                            job_dict["error"] = error
                            prog["error_message"] = error
                        if status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                            job_dict["completed_at"] = datetime.now(timezone.utc).isoformat()
                        data["job"] = job_dict
                        m_dict[job_id] = data
                except Exception as e:
                    print(f"[JobStore] Error updating progress in modal.Dict: {e}")

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

            m_dict = self._get_dict()
            if m_dict is not None:
                try:
                    if job_id in m_dict:
                        data = dict(m_dict[job_id])
                        data["cancelled"] = True
                        if data.get("job"):
                            data["job"]["status"] = "cancelled"
                            data["job"]["stage"] = "cancelled"
                            data["job"]["progress"]["status"] = "cancelled"
                            data["job"]["progress"]["message"] = "Job cancelled by user."
                            data["job"]["completed_at"] = datetime.now(timezone.utc).isoformat()
                        m_dict[job_id] = data
                        return True
                except Exception:
                    pass

            return job_id in self._local_jobs

    def is_cancelled(self, job_id: str) -> bool:
        with self._lock:
            if job_id in self._local_cancelled:
                return True

            m_dict = self._get_dict()
            if m_dict is not None:
                try:
                    if job_id in m_dict:
                        return bool(m_dict[job_id].get("cancelled", False))
                except Exception:
                    pass

            return False
