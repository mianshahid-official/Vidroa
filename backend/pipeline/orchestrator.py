"""
Pipeline Orchestrator managing end-to-end 8-stage visual planning and storyboard generation.
Conforms strictly to the Google Antigravity Visual Planning Specification.
"""
import math
import traceback
from pathlib import Path
from typing import Optional, List
from app.models.job import JobStage, JobStatus
from app.models.presets import SubjectPreset, VisualStylePreset
from app.models.project import ProjectConfig, ImageCountMode
from app.models.scene import VisualScene, StoryAnalysis
from app.models.planning import ScriptAnalysis, VisualBeatPlan, ScheduledStoryboard, StoryboardAuditReport
from app.models.timeline import NarrationData
from app.presets.loader import PresetManager
from app.ai.schemas import JobCreateRequest
from backend.jobs.store import JobStore
from backend.inference.engine import BaseInferenceEngine
from backend.pipeline.stage1_analysis import Stage1Analyzer
from backend.pipeline.stage2_continuity import Stage2ContinuityManager
from backend.pipeline.stage3_visual_planning import Stage3VisualPlanner
from backend.pipeline.stage4_scheduling import Stage4TemporalScheduler
from backend.pipeline.stage5_prompts import Stage5PromptGenerator
from backend.pipeline.stage6_audit import Stage6StoryboardAuditor
from backend.pipeline.stage7_replanning import Stage7Replanner
from backend.pipeline.stage8_validation import Stage8FinalValidator


class PipelineOrchestrator:
    """Coordinates execution across all 8 stages with real-time job store reporting."""

    @classmethod
    def run_pipeline(
        cls,
        job_id: str,
        request: JobCreateRequest,
        engine: BaseInferenceEngine,
        project_dir: Optional[str] = None
    ) -> None:
        store = JobStore()

        try:
            # 0. Check cancellation
            if store.is_cancelled(job_id):
                return

            # Resolve Presets
            subject_preset = PresetManager.get_subject_by_id(request.subject_id)
            if not subject_preset:
                subject_preset = SubjectPreset(
                    id="history",
                    name="History",
                    description="Historical focus",
                    system_instructions=request.custom_subject or "Historical accuracy."
                )

            style_preset = PresetManager.get_style_by_id(request.visual_style_id)
            if not style_preset:
                style_preset = VisualStylePreset(
                    id="century_old_photograph",
                    name="Century-Old Photograph",
                    description="Archival vintage photographic style",
                    system_instructions=request.custom_style or "Authentic archival photography. Rich silver-toned monochrome or warm sepia. Period optics, no modern RGB colors."
                )

            p_dir = Path(project_dir) if project_dir else Path.cwd() / "projects" / (request.project_name or "default_project")

            # =========================================================================
            # STAGE 1: SCRIPT ANALYSIS (10%)
            # =========================================================================
            store.update_progress(
                job_id,
                stage=JobStage.SCRIPT_ANALYSIS,
                status=JobStatus.RUNNING,
                percentage=10.0,
                message="Stage 1/8: Analyzing narrative beats, factual claims, and setting period..."
            )

            story_analysis: StoryAnalysis = Stage1Analyzer.execute(
                engine=engine,
                story_text=request.story_text,
                subject_preset=subject_preset,
                custom_subject=request.custom_subject
            )
            store.set_analysis(job_id, story_analysis)

            script_analysis: ScriptAnalysis = Stage1Analyzer.to_script_analysis(
                analysis=story_analysis,
                story_text=request.story_text
            )

            if store.is_cancelled(job_id):
                return

            # =========================================================================
            # STAGE 2: CONTINUITY BIBLE (20%)
            # =========================================================================
            store.update_progress(
                job_id,
                stage=JobStage.CONTINUITY_BIBLE,
                status=JobStatus.RUNNING,
                percentage=20.0,
                message="Stage 2/8: Persisting Character, Location, Object, and Time Bibles..."
            )

            Stage2ContinuityManager.save_bibles_to_disk(
                project_dir=p_dir,
                continuity_bible=script_analysis.continuity_bible,
                time_period_summary=script_analysis.historical_or_setting_period,
                script_summary=script_analysis.script_summary,
                thumbnail_headline=script_analysis.thumbnail_headline or "",
                thumbnail_prompt=script_analysis.thumbnail_prompt or ""
            )

            if store.is_cancelled(job_id):
                return

            # =========================================================================
            # STAGE 3: NARRATION-ALIGNED VISUAL PLANNING (35%)
            # =========================================================================
            store.update_progress(
                job_id,
                stage=JobStage.VISUAL_PLANNING,
                status=JobStatus.RUNNING,
                percentage=35.0,
                message="Stage 3/8: Planning narration-aligned visual beats (WHAT the audience sees)..."
            )

            visual_plan: VisualBeatPlan = Stage3VisualPlanner.execute(
                engine=engine,
                story_text=request.story_text,
                analysis=script_analysis,
                subject_preset=subject_preset
            )

            if store.is_cancelled(job_id):
                return

            # =========================================================================
            # STAGE 4: TEMPORAL SCENE SCHEDULING (50%)
            # =========================================================================
            store.update_progress(
                job_id,
                stage=JobStage.TEMPORAL_SCHEDULING,
                status=JobStatus.RUNNING,
                percentage=50.0,
                message="Stage 4/8: Scheduling scene boundaries with audio synchronization (2.0s-8.0s hard cap)..."
            )

            total_audio_dur = request.narration.duration_seconds if request.narration else None
            scheduled_storyboard: ScheduledStoryboard = Stage4TemporalScheduler.execute(
                engine=engine,
                visual_plan=visual_plan,
                narration=request.narration,
                story_text=request.story_text,
                total_audio_duration=total_audio_dur
            )

            if store.is_cancelled(job_id):
                return

            # =========================================================================
            # STAGE 5: IMAGE PROMPT GENERATION (70%)
            # =========================================================================
            batch_sz = max(1, min(request.batch_size, 20))
            store.update_progress(
                job_id,
                stage=JobStage.PROMPT_GENERATION,
                status=JobStatus.RUNNING,
                percentage=65.0,
                message=f"Stage 5/8: Generating style-compliant prompts ({len(scheduled_storyboard.scenes)} scenes)..."
            )

            generated_scenes: List[VisualScene] = Stage5PromptGenerator.execute(
                engine=engine,
                scheduled_storyboard=scheduled_storyboard,
                analysis=script_analysis,
                style_preset=style_preset,
                custom_style=request.custom_style,
                batch_size=batch_sz
            )
            store.set_scenes(job_id, generated_scenes)

            if store.is_cancelled(job_id):
                return

            # =========================================================================
            # STAGE 6: STORYBOARD QUALITY AUDIT (85%)
            # =========================================================================
            store.update_progress(
                job_id,
                stage=JobStage.QUALITY_AUDIT,
                status=JobStatus.RUNNING,
                percentage=85.0,
                message="Stage 6/8: Conducting independent quality audit (alignment, repetition, pacing)..."
            )

            audit_report: StoryboardAuditReport = Stage6StoryboardAuditor.execute(
                engine=engine,
                scenes=generated_scenes,
                story_text=request.story_text,
                analysis=script_analysis
            )

            if store.is_cancelled(job_id):
                return

            # =========================================================================
            # STAGE 7: AUTOMATIC REPLANNING (90% - if required, max 3 rounds)
            # =========================================================================
            current_scenes = generated_scenes
            repair_rounds = 0
            max_rounds = 3

            while audit_report.final_recommendation != "APPROVED" and repair_rounds < max_rounds:
                repair_rounds += 1
                store.update_progress(
                    job_id,
                    stage=JobStage.AUTOMATIC_REPLANNING,
                    status=JobStatus.RUNNING,
                    percentage=88.0 + (repair_rounds * 2.0),
                    message=f"Stage 7/8: Automatic replanning round {repair_rounds}/{max_rounds} (reconstructing flagged scenes)..."
                )

                current_scenes = Stage7Replanner.execute(
                    engine=engine,
                    scenes=current_scenes,
                    audit_report=audit_report,
                    analysis=script_analysis,
                    story_text=request.story_text,
                    style_preset=style_preset,
                    custom_style=request.custom_style
                )
                store.set_scenes(job_id, current_scenes)

                # Re-audit repaired storyboard
                audit_report = Stage6StoryboardAuditor.execute(
                    engine=engine,
                    scenes=current_scenes,
                    story_text=request.story_text,
                    analysis=script_analysis
                )

            # =========================================================================
            # STAGE 8: FINAL STORYBOARD VALIDATION (95%)
            # =========================================================================
            store.update_progress(
                job_id,
                stage=JobStage.FINAL_VALIDATION,
                status=JobStatus.RUNNING,
                percentage=95.0,
                message="Stage 8/8: Finalizing storyboard invariants and verifying timeline continuity..."
            )

            val_res = Stage8FinalValidator.execute(
                scenes=current_scenes,
                narration=request.narration,
                total_audio_duration=scheduled_storyboard.total_duration
            )

            store.set_scenes(job_id, current_scenes)

            # =========================================================================
            # RELEASE GATE & COMPLETION:
            # If scenes were successfully generated, mark job COMPLETED
            # and gracefully advise on pacing variations without blocking.
            # =========================================================================
            if not current_scenes:
                failure_summary = val_res.validation_summary
                store.update_progress(
                    job_id,
                    stage=JobStage.FAILED,
                    status=JobStatus.FAILED,
                    percentage=98.0,
                    message="Stage 8 validation FAILED — no scenes could be generated.",
                    error=f"Stage 8 RELEASE GATE FAILED.\n\n{failure_summary}"
                )
                return

            # =========================================================================
            # COMPLETED (100%)
            # =========================================================================
            msg = f"Complete visual planning finished successfully! {len(current_scenes)} scenes ready."
            if not val_res.is_valid:
                msg += f" Note: Pacing {val_res.min_scene_duration:.1f}s - {val_res.max_scene_duration:.1f}s."
            else:
                msg += f" Audit score: {audit_report.overall_score:.0f}/100."
            store.update_progress(
                job_id,
                stage=JobStage.COMPLETED,
                status=JobStatus.COMPLETED,
                percentage=100.0,
                message=msg
            )

        except Exception as e:
            tb = traceback.format_exc()
            store.update_progress(
                job_id,
                stage=JobStage.FAILED,
                status=JobStatus.FAILED,
                percentage=0.0,
                message=f"Pipeline generation failed: {str(e)}",
                error=f"{str(e)}\n\n{tb}"
            )
