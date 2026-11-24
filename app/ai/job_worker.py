"""
PySide6 QThread background workers for asynchronous job execution.
Runs entirely locally using Groq Multi-Key Engine with Qwen & Whisper acceleration.
"""
import math
import uuid
import traceback
from typing import Optional, List, Dict, Any

try:
    from PySide6.QtCore import QThread, Signal
except (ImportError, ModuleNotFoundError):
    class QThread:
        def __init__(self, parent=None): pass
        def start(self): pass
        def isRunning(self): return False
        def terminate(self): pass
        def wait(self): pass
    class Signal:
        def __init__(self, *args): pass
        def emit(self, *args): pass
        def connect(self, *args): pass

from app.models.job import JobStatus, JobStage, ProgressInfo
from app.models.project import ProjectConfig, ImageCountMode
from app.models.presets import SubjectPreset, VisualStylePreset
from app.models.scene import VisualScene, StoryAnalysis
from app.presets.loader import PresetManager
from app.ai.schemas import (
    JobCreateRequest,
    JobStatusResponse,
    SceneRegenerateRequest,
    SceneRegenerateResponse,
)
from backend.inference.engine import GroqInferenceEngine
from backend.pipeline.stage1_story_intelligence import Stage1StoryIntelligence, Stage1Analyzer
from backend.pipeline.stage2_visual_storyboard import Stage2VisualStoryboard
from backend.pipeline.stage3_prompt_generation import Stage3PromptGeneration, Stage3PromptGenerator, Stage5PromptGenerator
from backend.pipeline.stage4_rendering import Stage4RenderingManager
from backend.pipeline.orchestrator import PipelineOrchestrator
from app.models.planning import ScheduledStoryboard, ScheduledScene, ScriptAnalysis, StoryIntelligence


class CloudJobWorker(QThread):
    """
    Background worker that executes the entire 4-stage storyboard generation locally
    powered by Groq's multi-key pooled inference engine (Qwen3-27B / GPT-OSS).
    """

    # Qt Signals matching original interface
    progress_updated = Signal(object) # ProgressInfo
    stage_changed = Signal(str)        # JobStage string
    scenes_streamed = Signal(list)     # List[VisualScene]
    analysis_ready = Signal(object)    # StoryAnalysis
    planning_ready = Signal(object, list) # (StoryAnalysis, List[VisualScene])
    job_completed = Signal(object)     # JobStatusResponse
    job_failed = Signal(str, str)      # (user_facing_error, technical_details)
    job_cancelled = Signal()

    def __init__(
        self,
        base_url: str = "",
        request: Optional[JobCreateRequest] = None,
        api_key: Optional[str] = None,
        auth_token: Optional[str] = None,
        poll_interval: float = 1.0,
        plan_only: bool = False,
        scenes_to_generate: Optional[List[VisualScene]] = None,
        analysis: Optional[StoryAnalysis] = None,
        bibles: Optional[Dict[str, Any]] = None,
        parent=None
    ):
        super().__init__(parent)
        self.base_url = base_url
        self.request = request
        self.api_key = api_key
        self.auth_token = auth_token
        self.poll_interval = poll_interval
        self.plan_only = plan_only
        self.scenes_to_generate = scenes_to_generate
        self.analysis = analysis
        self.bibles = bibles
        self._is_cancelled = False
        self.job_id = f"job_{uuid.uuid4().hex[:8]}"

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        if not self.request:
            self.job_failed.emit("Invalid Request", "No generation request provided.")
            return

        try:
            raw_model = getattr(self.request, "model_name", "qwen/qwen3.8-27b") or "qwen/qwen3.8-27b"
            model_name = "qwen/qwen3.8-27b" if "qwen3-30b" in raw_model.lower() else raw_model
            engine = GroqInferenceEngine(model_name=model_name)

            # Resolve Presets
            subject_preset = PresetManager.get_subject_by_id(self.request.subject_id)
            if not subject_preset:
                subject_preset = SubjectPreset(
                    id=self.request.subject_id,
                    name=self.request.subject_id,
                    description="Historical focus",
                    system_instructions=self.request.custom_subject or "Historical accuracy."
                )

            style_preset = PresetManager.get_style_by_id(self.request.visual_style_id)
            if not style_preset:
                style_preset = VisualStylePreset(
                    id=self.request.visual_style_id,
                    name=self.request.visual_style_id,
                    description="Archival style",
                    system_instructions=self.request.custom_style or "Cinematic archival photography."
                )

            config = ProjectConfig(
                subject_id=self.request.subject_id,
                custom_subject=self.request.custom_subject,
                visual_style_id=self.request.visual_style_id,
                custom_style=self.request.custom_style,
                image_count_mode=self.request.image_count_mode,
                target_image_count=self.request.target_image_count,
                timing_mode=self.request.timing_mode,
                min_duration=self.request.min_duration,
                preferred_duration=self.request.preferred_duration,
                max_duration=self.request.max_duration,
                batch_size=self.request.batch_size,
                model_name=model_name
            )

            # -------------------------------------------------------------
            # STAGE 1: Story Intelligence & Bible Context (User-Provided)
            # -------------------------------------------------------------
            if self._is_cancelled:
                self.job_cancelled.emit()
                return

            if self.bibles:
                story_intel = StoryIntelligence(
                    story_summary=self.bibles.get("story_bible", {}).get("logline", "") or self.request.story_text[:500],
                    characters=self.bibles.get("characters", []),
                    environments=self.bibles.get("environments", []),
                    objects_and_props=self.bibles.get("key_objects", []),
                    visual_style_bible=self.bibles.get("visual_style_bible", {})
                )
                analysis = self.analysis or story_intel.to_story_analysis()
            elif self.analysis:
                analysis = self.analysis
                story_intel = StoryIntelligence(story_summary=getattr(analysis, "story_summary", ""))
            else:
                # Per architecture requirements: Bibles are user-provided, never generated via Groq
                story_intel = StoryIntelligence(
                    story_summary=self.request.story_text[:500] if self.request.story_text else "Production Story",
                    characters=[{"name": "Protagonist", "physical_description": "Main character", "clothing_and_gear": "Standard clothing"}],
                    environments=[{"name": "Setting", "architectural_style": "Story environment"}],
                    objects_and_props=[],
                    visual_style_bible={"color_palette": f"Consistent with {style_preset.name}"}
                )
                analysis = story_intel.to_story_analysis()
                self.analysis_ready.emit(analysis)

            # -------------------------------------------------------------
            # STAGE 2: Visual Storyboard (User-Provided)
            # -------------------------------------------------------------
            if self._is_cancelled:
                self.job_cancelled.emit()
                return

            if self.scenes_to_generate:
                planned_scenes = self.scenes_to_generate
            else:
                # Per architecture requirements: Storyboards are user-provided, never generated via Groq
                raise ValueError(
                    "No storyboard scenes provided. Storyboards must be provided by the user. "
                    "Please import or paste storyboard scenes before running prompt expansion."
                )

            total_scenes = len(planned_scenes)
            self.scenes_streamed.emit(planned_scenes)

            if self.plan_only:
                self.stage_changed.emit("User storyboard scenes and bible loaded. Ready for prompt expansion.")
                self.progress_updated.emit(ProgressInfo(
                    stage=JobStage.VISUAL_STORYBOARD,
                    status=JobStatus.COMPLETED,
                    progress_percentage=100.0,
                    message=f"Storyboard ready: {total_scenes} scenes ready for prompt expansion.",
                    total_scenes_target=total_scenes
                ))
                self.planning_ready.emit(analysis, planned_scenes)
                return

            # -------------------------------------------------------------
            # STAGE 3: Image Prompt Generation
            # -------------------------------------------------------------
            if self._is_cancelled:
                self.job_cancelled.emit()
                return

            batch_size = max(1, min(config.batch_size, 15))

            self.stage_changed.emit(f"Stage 3/4: Generating prompts adhering strictly to '{style_preset.name}'...")
            self.progress_updated.emit(ProgressInfo(
                stage=JobStage.PROMPT_GENERATION,
                status=JobStatus.RUNNING,
                progress_percentage=50.0,
                message=f"Generating image prompts adhering to '{style_preset.name}'...",
                total_scenes_target=total_scenes
            ))

            def _on_prompt_batch_progress(pct: float, msg: str):
                scaled_pct = 50.0 + (pct / 100.0) * 45.0
                self.stage_changed.emit(msg)
                self.progress_updated.emit(ProgressInfo(
                    stage=JobStage.PROMPT_GENERATION,
                    status=JobStatus.RUNNING,
                    progress_percentage=scaled_pct,
                    message=msg,
                    total_scenes_target=total_scenes
                ))

            final_scenes = Stage3PromptGeneration.execute(
                storyboard=planned_scenes,
                story_intelligence=story_intel,
                style_preset=style_preset,
                visual_style_id=self.request.visual_style_id,
                custom_style=self.request.custom_style,
                batch_size=batch_size,
                engine=engine,
                progress_callback=_on_prompt_batch_progress,
                allow_partial=True
            )
            self.scenes_streamed.emit(list(final_scenes))

            error_count = sum(1 for s in final_scenes if getattr(s, "generation_status", "") == "error" or not (s.prompt and s.prompt.strip()))
            success_count = len(final_scenes) - error_count

            if error_count > 0:
                summary_msg = f"Generation finished: {success_count}/{len(final_scenes)} prompts ready ({error_count} need retry - highlighted in red)."
            else:
                summary_msg = f"Generation completed successfully! {len(final_scenes)} style-compliant scene prompts ready."

            # -------------------------------------------------------------
            # FINISHED (Ready for Stage 4 Image Assignment & Local Video Rendering)
            # -------------------------------------------------------------
            self.progress_updated.emit(ProgressInfo(
                stage=JobStage.COMPLETED,
                status=JobStatus.COMPLETED,
                progress_percentage=100.0,
                message=summary_msg
            ))

            response = JobStatusResponse(
                job_id=self.job_id,
                status=JobStatus.COMPLETED,
                stage=JobStage.COMPLETED,
                progress=ProgressInfo(
                    stage=JobStage.COMPLETED,
                    status=JobStatus.COMPLETED,
                    progress_percentage=100.0,
                    message=summary_msg
                ),
                analysis=analysis,
                scenes=final_scenes
            )
            self.job_completed.emit(response)

        except Exception as e:
            tb = traceback.format_exc()
            self.job_failed.emit("Model generation failed.", f"{str(e)}\n\n{tb}")


# Alias LocalJobWorker to CloudJobWorker for maximum compatibility
LocalJobWorker = CloudJobWorker


class SceneRegenerateWorker(QThread):
    """Background worker for regenerating a single scene without blocking UI."""

    regenerate_completed = Signal(object) # SceneRegenerateResponse
    regenerate_failed = Signal(str, str)  # (user_facing_error, technical_details)

    def __init__(
        self,
        base_url: str = "",
        request: Optional[SceneRegenerateRequest] = None,
        api_key: Optional[str] = None,
        auth_token: Optional[str] = None,
        parent=None
    ):
        super().__init__(parent)
        self.request = request

    def run(self):
        if not self.request:
            self.regenerate_failed.emit("Invalid Request", "No scene request provided.")
            return

        try:
            raw_model = getattr(self.request, "model_name", "qwen/qwen3.8-27b") or "qwen/qwen3.8-27b"
            model_name = "qwen/qwen3.8-27b" if "qwen3-30b" in raw_model.lower() else raw_model
            engine = GroqInferenceEngine(model_name=model_name)

            subject_preset = PresetManager.get_subject_by_id(self.request.subject_id)
            if not subject_preset:
                subject_preset = SubjectPreset(
                    id=self.request.subject_id,
                    name=self.request.subject_id,
                    description="Subject",
                    system_instructions=self.request.custom_subject or ""
                )

            style_preset = PresetManager.get_style_by_id(self.request.visual_style_id)
            if not style_preset:
                style_preset = VisualStylePreset(
                    id=self.request.visual_style_id,
                    name=self.request.visual_style_id,
                    description="Visual Style",
                    system_instructions=self.request.custom_style or ""
                )

            regenerated = Stage3PromptGenerator.regenerate_single_scene(
                engine=engine,
                scene=self.request.scene,
                story_summary=self.request.story_summary or "",
                subject_preset=subject_preset,
                style_preset=style_preset,
                custom_subject=self.request.custom_subject,
                custom_style=self.request.custom_style,
                continuity=self.request.continuity
            )

            resp = SceneRegenerateResponse(
                scene_id=regenerated.scene_id,
                visual_subject=regenerated.visual_subject,
                prompt=regenerated.prompt,
                framing_suggestion=regenerated.framing_suggestion,
                is_valid=True
            )
            self.regenerate_completed.emit(resp)
        except Exception as e:
            tb = traceback.format_exc()
            self.regenerate_failed.emit("Scene regeneration failed.", f"{str(e)}\n\n{tb}")
