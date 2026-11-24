"""
FastAPI route definitions for PromptBeast Cloud API.
"""
import uuid
import threading
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Header, Depends
from app.ai.schemas import (
    JobCreateRequest,
    JobCreateResponse,
    JobStatusResponse,
    JobCancelResponse,
    SceneRegenerateRequest,
    SceneRegenerateResponse,
    HealthResponse,
    ConnectionTestResponse,
)
from app.presets.loader import PresetManager
from app.models.presets import SubjectPreset, VisualStylePreset
from app.models.job import JobStatus, JobStage
from backend.jobs.store import JobStore
from backend.config import backend_config
from backend.inference.engine import BaseInferenceEngine, MockInferenceEngine
from backend.pipeline.orchestrator import PipelineOrchestrator
from backend.pipeline.stage3_prompt_generation import Stage3PromptGeneration, Stage3PromptGenerator

api_router = APIRouter(prefix="/api/v1")

# Global inference engine reference and loading status
_active_engine: Optional[BaseInferenceEngine] = None
_model_loading_status: str = "healthy"  # "healthy", "loading", "error"
_model_loading_message: str = "Ready"
_model_lock = threading.Lock()


def get_inference_engine() -> BaseInferenceEngine:
    global _active_engine
    if _active_engine is None:
        try:
            from backend.inference.engine import GroqInferenceEngine
            _active_engine = GroqInferenceEngine()
        except Exception:
            _active_engine = MockInferenceEngine()
    return _active_engine


def set_inference_engine(engine: BaseInferenceEngine) -> None:
    global _active_engine, _model_loading_status, _model_loading_message
    _active_engine = engine
    _model_loading_status = "healthy"
    _model_loading_message = "Ready"


def initialize_model_engine():
    """Initializes the vLLM engine if running direct local worker mode."""
    global _active_engine, _model_loading_status, _model_loading_message
    with _model_lock:
        _model_loading_status = "loading"
        _model_loading_message = f"Loading model {backend_config.model_hf_path} onto {backend_config.gpu_type} GPU..."
        try:
            from vllm import LLM
            from backend.inference.engine import VLLMInferenceEngine

            vllm_kwargs = {
                "model": backend_config.model_hf_path,
                "max_model_len": backend_config.max_model_len,
                "gpu_memory_utilization": backend_config.gpu_memory_utilization,
                "trust_remote_code": True,
                "enforce_eager": True,
            }
            if "AWQ" in backend_config.model_hf_path.upper():
                vllm_kwargs["quantization"] = "awq"
            elif "GPTQ" in backend_config.model_hf_path.upper():
                vllm_kwargs["quantization"] = "gptq"

            print(f"[ModelService] Initializing vLLM engine: {vllm_kwargs}")
            llm = LLM(**vllm_kwargs)
            _active_engine = VLLMInferenceEngine(llm)
            _model_loading_status = "healthy"
            _model_loading_message = f"Connected successfully ({backend_config.model_name})."
            print("[ModelService] Model successfully loaded and ready for inference!")
        except Exception as e:
            import traceback
            traceback.print_exc()
            from backend.inference.engine import ErrorReportingEngine
            _model_loading_status = "error"
            _model_loading_message = f"Model load error: {str(e)}"
            _active_engine = ErrorReportingEngine(str(e))
            print(f"[ModelService] ERROR loading model: {e}")


def verify_auth(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None)
):
    """Verifies API key / Auth token if backend authentication is configured."""
    expected_key = backend_config.api_key.strip()
    expected_token = backend_config.auth_token.strip()

    if not expected_key and not expected_token:
        # No auth required in local/open mode
        return

    if expected_token:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Bearer token.")
        token = authorization.split("Bearer ")[1].strip()
        if token != expected_token:
            raise HTTPException(status_code=403, detail="Invalid authorization token.")
        return

    if expected_key:
        if not x_api_key or x_api_key.strip() != expected_key:
            raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key.")


@api_router.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint - returns immediately from CPU web function."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        gpu=backend_config.gpu_type,
        model=backend_config.model_name,
        timestamp=datetime.now(timezone.utc)
    )


@api_router.post("/test_connection", response_model=ConnectionTestResponse)
def test_connection(_: None = Depends(verify_auth)):
    """Validates connectivity and authentication instantly."""
    health = health_check()
    return ConnectionTestResponse(
        connected=True,
        latency_ms=1.0,
        message=f"Connected successfully to PromptBeast Local ({backend_config.model_name}).",
        backend_info=health
    )


@api_router.post("/jobs", response_model=JobCreateResponse)
def create_job(
    request: JobCreateRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(verify_auth)
):
    """Submits a new generation job and begins asynchronous processing."""
    store = JobStore()
    job_id = str(uuid.uuid4())
    project_id = request.project_name.lower().replace(" ", "_")

    store.create_job(
        job_id=job_id,
        project_id=project_id,
        settings=request.model_dump()
    )

    engine = get_inference_engine()

    # Launch in background thread
    background_tasks.add_task(
        PipelineOrchestrator.run_pipeline,
        job_id=job_id,
        request=request,
        engine=engine
    )

    return JobCreateResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        message="Storyboard generation job queued successfully."
    )


@api_router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str, _: None = Depends(verify_auth)):
    """Retrieves current progress, stages, and streamed scenes for a job."""
    store = JobStore()
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    analysis = store.get_analysis(job_id)
    scenes = store.get_scenes(job_id)

    return JobStatusResponse(
        job_id=job_id,
        status=job.status,
        stage=job.stage,
        progress=job.progress,
        analysis=analysis,
        scenes=scenes,
        error=job.error
    )


@api_router.post("/jobs/{job_id}/cancel", response_model=JobCancelResponse)
def cancel_job(job_id: str, _: None = Depends(verify_auth)):
    """Cancels a running job."""
    store = JobStore()
    cancelled = store.cancel_job(job_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found or already finished.")

    return JobCancelResponse(
        job_id=job_id,
        status=JobStatus.CANCELLED,
        message=f"Job '{job_id}' cancelled."
    )


@api_router.post("/scenes/regenerate", response_model=SceneRegenerateResponse)
def regenerate_scene(
    request: SceneRegenerateRequest,
    _: None = Depends(verify_auth)
):
    """Regenerates a single scene prompt on demand."""
    engine = get_inference_engine()
    subject_preset = PresetManager.get_subject_by_id(request.subject_id)
    if not subject_preset:
        subject_preset = SubjectPreset(
            id=request.subject_id,
            name=request.subject_id,
            description="Subject",
            system_instructions=request.custom_subject or ""
        )

    style_preset = PresetManager.get_style_by_id(request.visual_style_id)
    if not style_preset:
        style_preset = VisualStylePreset(
            id=request.visual_style_id,
            name=request.visual_style_id,
            description="Visual Style",
            system_instructions=request.custom_style or ""
        )

    regenerated = Stage3PromptGenerator.regenerate_single_scene(
        engine=engine,
        scene=request.scene,
        story_summary=request.story_summary or "",
        subject_preset=subject_preset,
        style_preset=style_preset,
        custom_subject=request.custom_subject,
        custom_style=request.custom_style,
        continuity=request.continuity
    )

    return SceneRegenerateResponse(
        scene_id=regenerated.scene_id,
        visual_subject=regenerated.visual_subject,
        prompt=regenerated.prompt,
        framing_suggestion=regenerated.framing_suggestion,
        is_valid=True
    )
