"""
Pipeline Stage 2 Planning (Legacy Compatibility).
Delegates directly to the unified authoritative Stage 3 Visual Planner and Stage 4 Temporal Scheduler
to guarantee a single unified planning path across the application.
"""
from typing import List, Optional, Callable, Any
from app.models.scene import VisualScene
from app.models.timeline import NarrationData
from backend.inference.engine import BaseInferenceEngine


class Stage2Planner:
    """
    Legacy Stage 2 Planner interface.
    Delegates directly to the authoritative Stage 3 Visual Planner and Stage 4 Temporal Scheduler
    to guarantee a single unified planning path across the application.
    """

    @classmethod
    def execute(
        cls,
        engine: BaseInferenceEngine,
        story_text: str,
        analysis_summary: str,
        narration: Optional[NarrationData] = None,
        config: Optional[Any] = None,
        subject_preset: Optional[Any] = None,
        style_preset: Optional[Any] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[VisualScene]:
        from backend.pipeline.stage1_analysis import Stage1Analyzer
        from backend.pipeline.stage3_visual_planning import Stage3VisualPlanner
        from backend.pipeline.stage4_scheduling import Stage4TemporalScheduler, assert_sentence_boundary_validity

        script_analysis = Stage1Analyzer.to_script_analysis(None, story_text)
        visual_plan = Stage3VisualPlanner.execute(
            engine=engine,
            story_text=story_text,
            analysis=script_analysis,
            subject_preset=subject_preset,
            progress_callback=progress_callback
        )
        total_audio_dur = narration.duration_seconds if narration else None
        storyboard = Stage4TemporalScheduler.execute(
            engine=engine,
            visual_plan=visual_plan,
            narration=narration,
            story_text=story_text,
            total_audio_duration=total_audio_dur
        )

        scenes: List[VisualScene] = []
        for sc in storyboard.scenes:
            scenes.append(VisualScene(
                scene_id=sc.scene_id,
                index=sc.index,
                start=sc.start_time,
                end=sc.end_time,
                duration=sc.duration,
                start_word_index=sc.source_word_start,
                end_word_index=sc.source_word_end,
                narration_excerpt=sc.narration_text,
                visual_subject=sc.visual_summary,
                action=sc.visual_summary,
                environment="",
                composition="Wide establishing shot",
                emotional_tone="Dramatic",
                historical_confidence="well_supported_reconstruction",
                prompt="",
                continuity_checklist=[],
                source_narrative_beat_ids=sc.source_narrative_beat_ids,
                source_visual_beat_ids=sc.source_visual_beat_ids,
                character_ids=sc.character_ids,
                location_id=sc.location_id,
                chronological_order=sc.chronological_order,
                validation_notes=None
            ))

        assert_sentence_boundary_validity(scenes, story_text)
        return scenes
