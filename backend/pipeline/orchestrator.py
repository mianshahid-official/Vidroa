"""
Pipeline Orchestrator managing end-to-end 4-Stage visual planning and storyboard generation.
Streamlined 4-stage architecture:
- Stage 1: Story Intelligence
- Stage 2: Visual Storyboard
- Stage 3: Image Prompt Generation
- Stage 4: Image Assignment & Local Video Rendering
"""
import math
import traceback
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

from app.models.job import JobStage, JobStatus
from app.models.presets import SubjectPreset, VisualStylePreset
from app.models.project import ProjectConfig
from app.models.scene import VisualScene
from app.models.planning import StoryIntelligence, ScriptAnalysis
from app.models.timeline import NarrationData
from app.presets.loader import PresetManager
from app.ai.schemas import JobCreateRequest
from backend.jobs.store import JobStore
from backend.inference.engine import BaseInferenceEngine

from backend.pipeline.stage1_story_intelligence import Stage1StoryIntelligence
from backend.pipeline.stage2_visual_storyboard import Stage2VisualStoryboard
from backend.pipeline.stage3_prompt_generation import Stage3PromptGeneration
from backend.pipeline.stage4_rendering import Stage4RenderingManager
from backend.pipeline.stage_validation import validate_storyboard


class PipelineOrchestrator:
    """Coordinates execution across the 4 streamlined pipeline stages."""

    @classmethod
    def run_stage1(
        cls,
        story_text: str,
        narration: Optional[NarrationData] = None,
        user_visual_ideas: Optional[str] = None,
        subject_preset: Optional[SubjectPreset] = None,
        custom_subject: Optional[str] = None,
        style_preset: Optional[VisualStylePreset] = None,
        custom_style: Optional[str] = None,
        project_instructions: Optional[str] = None,
        project_dir: Optional[Path] = None,
        engine: Optional[BaseInferenceEngine] = None
    ) -> StoryIntelligence:
        """Stage 1: Extract dynamic story, character, environment, and visual bibles."""
        return Stage1StoryIntelligence.execute(
            engine=engine,
            story_text=story_text,
            narration=narration,
            user_visual_ideas=user_visual_ideas,
            subject_preset=subject_preset,
            custom_subject=custom_subject,
            style_preset=style_preset,
            custom_style=custom_style,
            project_instructions=project_instructions,
            project_dir=project_dir
        )

    @classmethod
    def run_stage2(
        cls,
        story_intelligence: StoryIntelligence,
        narration: Optional[NarrationData] = None,
        story_text: str = "",
        user_visual_ideas: Optional[str] = None,
        style_preset: Optional[VisualStylePreset] = None,
        config: Optional[ProjectConfig] = None,
        engine: Optional[BaseInferenceEngine] = None
    ) -> List[VisualScene]:
        """Stage 2: Plan visual storyboard without generating image prompts."""
        return Stage2VisualStoryboard.execute(
            story_intelligence=story_intelligence,
            narration=narration,
            story_text=story_text,
            user_visual_ideas=user_visual_ideas,
            style_preset=style_preset,
            config=config,
            engine=engine
        )

    @classmethod
    def run_stage3(
        cls,
        storyboard: List[VisualScene],
        story_intelligence: Optional[StoryIntelligence] = None,
        style_preset: Optional[VisualStylePreset] = None,
        visual_style_id: Optional[str] = None,
        custom_style: Optional[str] = None,
        aspect_ratio: str = "16:9",
        batch_size: int = 8,
        engine: Optional[BaseInferenceEngine] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        force_regenerate: bool = False
    ) -> List[VisualScene]:
        """Stage 3: Transform storyboard into concrete image prompts adhering strictly to visual style."""
        return Stage3PromptGeneration.execute(
            storyboard=storyboard,
            story_intelligence=story_intelligence,
            style_preset=style_preset,
            visual_style_id=visual_style_id,
            custom_style=custom_style,
            aspect_ratio=aspect_ratio,
            batch_size=batch_size,
            engine=engine,
            progress_callback=progress_callback,
            force_regenerate=force_regenerate
        )

    @classmethod
    def run_stage4(
        cls,
        scenes: List[VisualScene],
        audio_path: str,
        output_video_path: str,
        images_dir: Optional[str] = None,
        settings: Optional[Any] = None,
        narration: Optional[NarrationData] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> str:
        """Stage 4: Image assignment and local FFmpeg video compilation."""
        if images_dir:
            Stage4RenderingManager.bind_images_from_directory(scenes, images_dir)
        return Stage4RenderingManager.render_video_local(
            scenes=scenes,
            audio_path=audio_path,
            output_video_path=output_video_path,
            settings=settings,
            narration=narration,
            progress_callback=progress_callback
        )

    @classmethod
    def run_pipeline(
        cls,
        job_id: str,
        request: JobCreateRequest,
        engine: BaseInferenceEngine,
        project_dir: Optional[str] = None,
        render_video_after: bool = False
    ) -> None:
        """Runs the 4-stage pipeline end-to-end with status tracking."""
        store = JobStore()
        if not store.get_job(job_id):
            proj_name = request.project_name or "default_project"
            store.create_job(
                job_id=job_id,
                project_id=proj_name.lower().replace(" ", "_"),
                settings=request.model_dump()
            )

        try:
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
                    id="zombie_survival",
                    name="Zombie Survival",
                    description="Post-apocalyptic survival tone",
                    system_instructions=request.custom_style or "High-tension survival aesthetics, gritty lighting, cinematic depth."
                )

            p_dir = Path(project_dir) if project_dir else Path.cwd() / "projects" / (request.project_name or "default_project")
            p_dir.mkdir(parents=True, exist_ok=True)

            # =========================================================================
            # STAGE 1: STORY INTELLIGENCE (25%)
            # =========================================================================
            store.update_progress(
                job_id,
                stage=JobStage.STORY_INTELLIGENCE,
                status=JobStatus.RUNNING,
                percentage=15.0,
                message="Stage 1/4: Extracting dynamic Story, Character, and Environment Bibles..."
            )

            story_intel = cls.run_stage1(
                story_text=request.story_text,
                narration=request.narration,
                user_visual_ideas=getattr(request, "user_visual_ideas", None),
                subject_preset=subject_preset,
                custom_subject=request.custom_subject,
                style_preset=style_preset,
                custom_style=request.custom_style,
                project_dir=p_dir,
                engine=engine
            )

            # Update store with analysis for UI listeners
            store.set_analysis(job_id, story_intel.to_story_analysis())

            if store.is_cancelled(job_id):
                return

            # =========================================================================
            # STAGE 2: VISUAL STORYBOARD (50%)
            # =========================================================================
            store.update_progress(
                job_id,
                stage=JobStage.VISUAL_STORYBOARD,
                status=JobStatus.RUNNING,
                percentage=40.0,
                message="Stage 2/4: Structuring narration-aligned visual storyboard..."
            )

            storyboard_scenes = cls.run_stage2(
                story_intelligence=story_intel,
                narration=request.narration,
                story_text=request.story_text,
                user_visual_ideas=getattr(request, "user_visual_ideas", None),
                style_preset=style_preset,
                engine=engine
            )

            store.set_scenes(job_id, storyboard_scenes)

            if store.is_cancelled(job_id):
                return

            # =========================================================================
            # STAGE 3: IMAGE PROMPT GENERATION (85%)
            # =========================================================================
            batch_sz = max(1, min(request.batch_size, 15))
            store.update_progress(
                job_id,
                stage=JobStage.PROMPT_GENERATION,
                status=JobStatus.RUNNING,
                percentage=60.0,
                message=f"Stage 3/4: Generating {len(storyboard_scenes)} model-ready image prompts ({style_preset.name})..."
            )

            def prompt_cb(pct: float, msg: str):
                scaled_pct = 60.0 + (pct / 100.0) * 35.0
                store.update_progress(
                    job_id,
                    stage=JobStage.PROMPT_GENERATION,
                    status=JobStatus.RUNNING,
                    percentage=scaled_pct,
                    message=f"Stage 3/4: {msg}"
                )

            final_scenes = cls.run_stage3(
                storyboard=storyboard_scenes,
                story_intelligence=story_intel,
                style_preset=style_preset,
                visual_style_id=request.visual_style_id,
                custom_style=request.custom_style,
                batch_size=batch_sz,
                engine=engine,
                progress_callback=prompt_cb
            )

            # Validation gate (with narration): fail loudly before rendering.
            validate_storyboard(final_scenes, narration=request.narration)

            store.set_scenes(job_id, final_scenes)

            if store.is_cancelled(job_id):
                return

            # =========================================================================
            # STAGE 4: IMAGE ASSIGNMENT & RENDERING (OPTIONAL OR STANDALONE)
            # =========================================================================
            if render_video_after:
                store.update_progress(
                    job_id,
                    stage=JobStage.VIDEO_RENDERING,
                    status=JobStatus.RUNNING,
                    percentage=95.0,
                    message="Stage 4/4: Compiling video locally with FFmpeg..."
                )
                audio_file = p_dir / "narration.mp3"
                if not audio_file.exists():
                    audio_file = p_dir / "narration.wav"
                out_mp4 = p_dir / "final_video.mp4"

                cls.run_stage4(
                    scenes=final_scenes,
                    audio_path=str(audio_file),
                    output_video_path=str(out_mp4),
                    images_dir=str(p_dir / "images") if (p_dir / "images").exists() else None,
                    narration=request.narration
                )

            # =========================================================================
            # PIPELINE COMPLETED (100%)
            # =========================================================================
            store.update_progress(
                job_id,
                stage=JobStage.COMPLETED,
                status=JobStatus.COMPLETED,
                percentage=100.0,
                message=f"Pipeline complete! {len(final_scenes)} style-compliant scene prompts generated."
            )

        except Exception as e:
            tb = traceback.format_exc()
            store.update_progress(
                job_id,
                stage=JobStage.FAILED,
                status=JobStatus.FAILED,
                percentage=0.0,
                message=f"Pipeline failed: {str(e)}",
                error=f"{str(e)}\n\n{tb}"
            )
