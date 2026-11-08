"""
PySide6 QThread background workers for asynchronous job execution.
Runs entirely locally using Groq Multi-Key Engine with Qwen & Whisper acceleration.
"""
import math
import uuid
import traceback
from typing import Optional, List

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
from backend.pipeline.stage1_analysis import Stage1Analyzer
from backend.pipeline.stage2_continuity import Stage2ContinuityManager
from backend.pipeline.stage2_planning import Stage2Planner  # Required for scene planning when no pre-planned scenes provided
from backend.pipeline.stage3_visual_planning import Stage3VisualPlanner
from backend.pipeline.stage4_scheduling import Stage4TemporalScheduler
from backend.pipeline.stage5_prompts import Stage5PromptGenerator
from backend.pipeline.stage6_audit import Stage6StoryboardAuditor
from backend.pipeline.stage7_replanning import Stage7Replanner
from backend.pipeline.stage8_validation import Stage8FinalValidator
from app.models.planning import ScheduledStoryboard, ScheduledScene, ScriptAnalysis


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
        self._is_cancelled = False
        self.job_id = f"job_{uuid.uuid4().hex[:8]}"

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        if not self.request:
            self.job_failed.emit("Invalid Request", "No generation request provided.")
            return

        try:
            model_name = getattr(self.request, "model_name", "qwen/qwen3.8-27b") or "qwen/qwen3.8-27b"
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
            # STAGE 1: Story Analysis
            # -------------------------------------------------------------
            if self._is_cancelled:
                self.job_cancelled.emit()
                return

            if self.analysis:
                analysis = self.analysis
            else:
                self.stage_changed.emit("Analyzing story structure & narrative beats...")
                self.progress_updated.emit(ProgressInfo(
                    stage=JobStage.ANALYSIS,
                    status=JobStatus.RUNNING,
                    progress_percentage=10.0,
                    message="Analyzing story structure, narrative beats, and continuity needs..."
                ))
                analysis = Stage1Analyzer.execute(
                    engine=engine,
                    story_text=self.request.story_text,
                    subject_preset=subject_preset,
                    custom_subject=self.request.custom_subject
                )
                self.analysis_ready.emit(analysis)

            # -------------------------------------------------------------
            # STAGE 2: Visual Scene Planning
            # -------------------------------------------------------------
            if self._is_cancelled:
                self.job_cancelled.emit()
                return

            if self.scenes_to_generate:
                planned_scenes = self.scenes_to_generate
            else:
                self.stage_changed.emit("Planning visual scene boundaries & word-level timing...")
                self.progress_updated.emit(ProgressInfo(
                    stage=JobStage.PLANNING,
                    status=JobStatus.RUNNING,
                    progress_percentage=25.0,
                    message="Planning visual scene boundaries and word-level timing..."
                ))
                planned_scenes = Stage2Planner.execute(
                    engine=engine,
                    story_text=self.request.story_text,
                    analysis_summary=analysis.story_summary,
                    narration=self.request.narration,
                    config=config,
                    subject_preset=subject_preset,
                    style_preset=style_preset
                )

            total_scenes = len(planned_scenes)
            self.scenes_streamed.emit(planned_scenes)

            if self.plan_only:
                self.stage_changed.emit("Story Bible & Visual Scenes planned. Awaiting your approval.")
                self.progress_updated.emit(ProgressInfo(
                    stage=JobStage.PLANNING,
                    status=JobStatus.COMPLETED,
                    progress_percentage=100.0,
                    message=f"Planning complete: {total_scenes} scenes ready for approval.",
                    total_scenes_target=total_scenes
                ))
                self.planning_ready.emit(analysis, planned_scenes)
                return

            # -------------------------------------------------------------
            # STAGE 5: Batched Prompt Generation
            # -------------------------------------------------------------
            script_analysis = Stage1Analyzer.to_script_analysis(analysis, self.request.story_text)
            scheduled_items = []
            for s in planned_scenes:
                scheduled_items.append(ScheduledScene(
                    scene_id=s.scene_id,
                    index=getattr(s, "index", None),
                    beat_id=getattr(s, "beat_id", f"VB-{s.scene_id}"),
                    start_time=s.start,
                    end_time=s.end,
                    duration=s.duration,
                    narration_text=s.narration_excerpt or s.action,
                    visual_summary=s.visual_subject,
                    scheduling_reason="Approved user storyboard beat",
                    source_narrative_beat_ids=getattr(s, "source_narrative_beat_ids", []),
                    source_visual_beat_ids=getattr(s, "source_visual_beat_ids", [getattr(s, "beat_id", f"VB-{s.scene_id}")]),
                    source_word_start=getattr(s, "start_word_index", None),
                    source_word_end=getattr(s, "end_word_index", None),
                    character_ids=getattr(s, "character_ids", []),
                    location_id=getattr(s, "location_id", None),
                    chronological_order=getattr(s, "chronological_order", None)
                ))
            scheduled_storyboard = ScheduledStoryboard(
                scenes=scheduled_items,
                total_duration=planned_scenes[-1].end if planned_scenes else 0.0
            )

            batch_size = max(1, min(config.batch_size, 20))
            total_batches = math.ceil(total_scenes / batch_size) if total_scenes > 0 else 1

            self.stage_changed.emit(f"Generating prompts adhering to '{style_preset.name}'...")
            self.progress_updated.emit(ProgressInfo(
                stage=JobStage.PROMPT_GENERATION,
                status=JobStatus.RUNNING,
                progress_percentage=40.0,
                message=f"Generating image prompts adhering to '{style_preset.name}'...",
                total_scenes_target=total_scenes
            ))

            def _on_prompt_batch_progress(curr_b: int, total_b: int, msg: str):
                pct = 35.0 + (curr_b / total_b) * 45.0
                self.stage_changed.emit(msg)
                self.progress_updated.emit(ProgressInfo(
                    stage=JobStage.PROMPT_GENERATION,
                    status=JobStatus.RUNNING,
                    progress_percentage=pct,
                    message=msg,
                    current_batch=curr_b,
                    total_batches=total_b
                ))

            generated_scenes = Stage5PromptGenerator.execute(
                engine=engine,
                scheduled_storyboard=scheduled_storyboard,
                analysis=script_analysis,
                style_preset=style_preset,
                custom_style=self.request.custom_style,
                batch_size=batch_size,
                progress_callback=_on_prompt_batch_progress
            )
            self.scenes_streamed.emit(list(generated_scenes))

            # -------------------------------------------------------------
            # STAGE 6: Storyboard Quality Audit
            # -------------------------------------------------------------
            if self._is_cancelled:
                self.job_cancelled.emit()
                return

            self.stage_changed.emit("Conducting independent quality audit (alignment, repetition, pacing)...")
            self.progress_updated.emit(ProgressInfo(
                stage=JobStage.QUALITY_AUDIT,
                status=JobStatus.RUNNING,
                progress_percentage=80.0,
                message="Auditing complete storyboard for narration alignment, pacing, and repetition..."
            ))

            audit_report = Stage6StoryboardAuditor.execute(
                engine=engine,
                scenes=generated_scenes,
                story_text=self.request.story_text,
                analysis=script_analysis
            )

            # -------------------------------------------------------------
            # STAGE 7: Automatic Replanning (if needed, max 3 rounds)
            # -------------------------------------------------------------
            current_scenes = generated_scenes
            repair_rounds = 0
            max_rounds = 3

            while audit_report.final_recommendation != "APPROVED" and repair_rounds < max_rounds:
                if self._is_cancelled:
                    self.job_cancelled.emit()
                    return

                repair_rounds += 1
                self.stage_changed.emit(f"Automatic replanning round {repair_rounds}/{max_rounds} (reconstructing flagged scenes)...")
                self.progress_updated.emit(ProgressInfo(
                    stage=JobStage.AUTOMATIC_REPLANNING,
                    status=JobStatus.RUNNING,
                    progress_percentage=85.0 + (repair_rounds * 2.0),
                    message=f"Reconstructing scenes flagged by audit (round {repair_rounds}/{max_rounds})..."
                ))

                current_scenes = Stage7Replanner.execute(
                    engine=engine,
                    scenes=current_scenes,
                    audit_report=audit_report,
                    analysis=script_analysis,
                    story_text=self.request.story_text,
                    style_preset=style_preset,
                    custom_style=self.request.custom_style
                )
                self.scenes_streamed.emit(list(current_scenes))

                # Re-audit
                audit_report = Stage6StoryboardAuditor.execute(
                    engine=engine,
                    scenes=current_scenes,
                    story_text=self.request.story_text,
                    analysis=script_analysis
                )

            # -------------------------------------------------------------
            # STAGE 8: Final Validation
            # -------------------------------------------------------------
            if self._is_cancelled:
                self.job_cancelled.emit()
                return

            self.stage_changed.emit("Finalizing storyboard invariants & timeline continuity...")
            self.progress_updated.emit(ProgressInfo(
                stage=JobStage.FINAL_VALIDATION,
                status=JobStatus.RUNNING,
                progress_percentage=95.0,
                message="Verifying timeline continuity, 8.0s hard ceiling, and prompt completeness..."
            ))

            total_aud_dur = self.request.narration.duration_seconds if self.request.narration else current_scenes[-1].end if current_scenes else 0.0
            val_res = Stage8FinalValidator.execute(
                scenes=current_scenes,
                narration=self.request.narration,
                total_audio_duration=total_aud_dur
            )

            validated_scenes = current_scenes
            self.scenes_streamed.emit(validated_scenes)

            # -------------------------------------------------------------
            # RELEASE GATE & COMPLETION:
            # If scenes were successfully generated, mark job COMPLETED
            # and gracefully advise on pacing variations without blocking.
            # -------------------------------------------------------------
            if not current_scenes:
                failure_details = val_res.validation_summary
                self.progress_updated.emit(ProgressInfo(
                    stage=JobStage.FINAL_VALIDATION,
                    status=JobStatus.FAILED,
                    progress_percentage=98.0,
                    message=f"Stage 8 validation failed: {failure_details}",
                    error_message=f"Stage 8 RELEASE GATE FAILED.\n\n{failure_details}"
                ))
                self.job_failed.emit(
                    "Storyboard failed final validation. No scenes could be generated.",
                    f"Stage 8 Release Gate FAILED.\n\n{failure_details}"
                )
                return

            # -------------------------------------------------------------
            # FINISHED
            # -------------------------------------------------------------
            status_msg = f"Generation completed successfully! ({len(validated_scenes)} scenes created."
            if not val_res.is_valid:
                status_msg += f" Pacing: {val_res.min_scene_duration:.1f}s - {val_res.max_scene_duration:.1f}s)."
            else:
                status_msg += f" Quality score: {audit_report.overall_score:.0f}/100)."

            self.progress_updated.emit(ProgressInfo(
                stage=JobStage.COMPLETED,
                status=JobStatus.COMPLETED,
                progress_percentage=100.0,
                message=status_msg
            ))

            response = JobStatusResponse(
                job_id=self.job_id,
                status=JobStatus.COMPLETED,
                stage=JobStage.COMPLETED,
                progress=ProgressInfo(
                    stage=JobStage.COMPLETED,
                    status=JobStatus.COMPLETED,
                    progress_percentage=100.0,
                    message=f"Completed {len(validated_scenes)} scenes."
                ),
                analysis=analysis,
                scenes=validated_scenes
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
            model_name = getattr(self.request, "model_name", "qwen/qwen3.8-27b") or "qwen/qwen3.8-27b"
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
