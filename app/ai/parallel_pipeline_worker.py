"""
Parallel Pipeline Worker: Orchestrates Modal Cloud OmniVoice TTS and Groq Story Analysis in parallel.
"""
import concurrent.futures
from pathlib import Path
from typing import Optional, List, Dict, Any

from PySide6.QtCore import QThread, Signal

from app.models.job import ProgressInfo, JobStage, JobStatus
from app.models.project import ProjectConfig
from app.ai.schemas import JobCreateRequest
from app.models.scene import StoryAnalysis, VisualScene
from app.models.timeline import NarrationData
from app.models.presets import SubjectPreset, VisualStylePreset
from app.presets.loader import PresetManager
from app.core.omnivoice_client import OmniVoiceClient, DEFAULT_MODAL_URL
from app.models.planning import ScriptAnalysis, VisualBeatPlan, ScheduledStoryboard
from backend.inference.engine import GroqInferenceEngine
from backend.pipeline.stage1_analysis import Stage1Analyzer
from backend.pipeline.stage2_continuity import Stage2ContinuityManager
from backend.pipeline.stage3_visual_planning import Stage3VisualPlanner
from backend.pipeline.stage4_scheduling import Stage4TemporalScheduler


class ParallelPipelineWorker(QThread):
    """
    Executes Modal Cloud OmniVoice TTS and Groq Storyboard Planning concurrently.
    """
    progress_updated = Signal(object)      # ProgressInfo
    stage_changed = Signal(str)           # message
    pipeline_ready = Signal(object, list, str, object)  # (analysis, planned_scenes, audio_path, narration)
    worker_failed = Signal(str, str)      # (user_msg, tech_details)

    def __init__(
        self,
        request: JobCreateRequest,
        voice_id: str = "narrator-deep-en",
        speed: float = 1.0,
        synthesize_voice: bool = True,
        modal_url: str = DEFAULT_MODAL_URL,
        existing_audio_path: Optional[str] = None,
        existing_narration: Optional[NarrationData] = None,
        project_dir: Optional[str] = None,
        parent=None
    ):
        super().__init__(parent)
        self.request = request
        self.voice_id = voice_id
        self.speed = speed
        self.synthesize_voice = synthesize_voice
        self.modal_url = modal_url
        self.existing_audio_path = existing_audio_path
        self.existing_narration = existing_narration
        self.project_dir = project_dir
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        story_text = self.request.story_text.strip()
        if not story_text:
            self.worker_failed.emit("Story script is empty.", "")
            return

        subject_preset = PresetManager.get_subject_by_id(self.request.subject_id) if hasattr(PresetManager, "get_subject_by_id") else None
        style_preset = PresetManager.get_style_by_id(self.request.visual_style_id) if hasattr(PresetManager, "get_style_by_id") else None

        tts_result: Dict[str, Any] = {}
        analysis_result: Optional[StoryAnalysis] = None
        scenes_result: List[VisualScene] = []
        tts_error = None
        groq_error = None

        self.stage_changed.emit("Starting parallel Voiceover Synthesis (Modal GPU) & Story Analysis (Groq)...")
        self.progress_updated.emit(ProgressInfo(
            stage=JobStage.ANALYSIS,
            status=JobStatus.RUNNING,
            progress_percentage=15.0,
            message="Synthesizing audio on Modal Cloud GPU & analyzing narrative beats in parallel..."
        ))

        def run_tts():
            if not self.synthesize_voice:
                return {
                    "audio_path": self.existing_audio_path,
                    "narration": self.existing_narration
                }

            if self.project_dir:
                out_dir = Path(self.project_dir)
            else:
                proj_name = self.request.project_name or "default_project"
                out_dir = Path.cwd() / "projects" / proj_name
            out_dir.mkdir(parents=True, exist_ok=True)
            out_wav = out_dir / "narration.wav"
            out_json = out_dir / "narration.json"

            # Check if existing audio file already exists for this project
            if out_wav.exists() and out_json.exists():
                try:
                    with open(out_json, "r", encoding="utf-8") as f:
                        narr_data = json.load(f)
                    narr = NarrationData(**narr_data)
                    print(f"[ParallelWorker] Reusing existing narration audio: {out_wav} ({narr.duration_seconds:.1f}s)")
                    return {
                        "audio_path": str(out_wav),
                        "narration": narr
                    }
                except Exception:
                    pass

            # Check if local Kokoro engine should handle synthesis (0 Modal requests)
            is_kokoro = self.voice_id.startswith("kokoro:") or any(
                self.voice_id.startswith(p) for p in ["am_", "af_", "bf_", "bm_", "ef_", "em_", "ff_", "hf_", "hm_"]
            )
            if is_kokoro:
                from app.core.kokoro_engine import KokoroTTSEngine
                kokoro_eng = KokoroTTSEngine.get_instance()

                def on_tts_p(p, msg):
                    self.progress_updated.emit(ProgressInfo(
                        stage=JobStage.AUDIO,
                        status=JobStatus.RUNNING,
                        progress_percentage=round(20.0 + (p / 100.0) * 70.0, 1),
                        message=f"Kokoro TTS: {msg} ({p:.0f}%)"
                    ))

                wav_path, narr = kokoro_eng.synthesize_to_file(
                    text=story_text,
                    output_path=str(out_wav),
                    voice=self.voice_id,
                    speed=self.speed,
                    progress_callback=on_tts_p
                )
                return {
                    "audio_path": wav_path,
                    "narration": narr
                }

            client = OmniVoiceClient(base_url=self.modal_url)
            return client.synthesize_script(
                text=story_text,
                voice_id=self.voice_id,
                speed=self.speed,
                output_dir=str(out_dir.resolve()),
                progress_callback=lambda pct, msg: None
            )

        def on_groq_beat(curr: int, total: int, msg: str):
            pct = 15.0 + (curr / total) * 75.0
            self.progress_updated.emit(ProgressInfo(
                stage=JobStage.PLANNING,
                status=JobStatus.RUNNING,
                progress_percentage=round(pct, 1),
                message=f"Groq AI planning storyboard: beat {curr}/{total} ({pct:.0f}%)"
            ))

        def run_groq():
            engine = GroqInferenceEngine(model_name=self.request.model_name)
            self.progress_updated.emit(ProgressInfo(
                stage=JobStage.SCRIPT_ANALYSIS,
                status=JobStatus.RUNNING,
                progress_percentage=10.0,
                message="Groq analyzing narrative structure & building story bible..."
            ))
            # Stage 1: Story Bible & Narrative Analysis
            analysis = Stage1Analyzer.execute(
                engine=engine,
                story_text=story_text,
                subject_preset=subject_preset,
                custom_subject=self.request.custom_subject
            )
            script_analysis = Stage1Analyzer.to_script_analysis(analysis, story_text)

            # Stage 2: Save Character, Location, Time, and Story bibles to disk
            if self.project_dir:
                try:
                    Stage2ContinuityManager.save_bibles_to_disk(
                        project_dir=Path(self.project_dir),
                        continuity_bible=script_analysis.continuity_bible,
                        time_period_summary=script_analysis.historical_or_setting_period,
                        script_summary=script_analysis.script_summary,
                        thumbnail_headline=script_analysis.thumbnail_headline or "",
                        thumbnail_prompt=script_analysis.thumbnail_prompt or ""
                    )
                except Exception as e:
                    print(f"[ParallelWorker] Bible save notice: {e}")

            # Stage 3: Narration-Aligned Visual Beat Planning
            self.progress_updated.emit(ProgressInfo(
                stage=JobStage.VISUAL_PLANNING,
                status=JobStatus.RUNNING,
                progress_percentage=40.0,
                message="Groq planning narration-aligned visual beats (WHAT to show)..."
            ))
            visual_plan = Stage3VisualPlanner.execute(
                engine=engine,
                story_text=story_text,
                analysis=script_analysis
            )

            self.progress_updated.emit(ProgressInfo(
                stage=JobStage.VISUAL_PLANNING,
                status=JobStatus.RUNNING,
                progress_percentage=75.0,
                message=f"Visual beats planned ({len(visual_plan.visual_beats)} beats). Awaiting audio sync..."
            ))
            return analysis, visual_plan

        visual_plan_result: Optional[VisualBeatPlan] = None
        if not self.synthesize_voice:
            tts_result = {
                "audio_path": self.existing_audio_path,
                "narration": self.existing_narration
            }
            try:
                analysis_result, visual_plan_result = run_groq()
            except Exception as e:
                groq_error = str(e)
                print(f"[ParallelWorker] Groq error: {e}")
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                fut_tts = executor.submit(run_tts)
                fut_groq = executor.submit(run_groq)

                try:
                    analysis_result, visual_plan_result = fut_groq.result(timeout=300)
                except Exception as e:
                    groq_error = str(e)
                    print(f"[ParallelWorker] Groq error: {e}")

                try:
                    tts_result = fut_tts.result(timeout=600)
                except Exception as e:
                    tts_error = str(e)
                    print(f"[ParallelWorker] TTS error: {e}")

        if self._is_cancelled:
            return

        if groq_error or not visual_plan_result:
            self.worker_failed.emit(
                "Storyboard planning failed. Please check your Groq API connection.",
                groq_error or "Visual beat plan was not generated."
            )
            return

        audio_path = tts_result.get("audio_path") if tts_result else self.existing_audio_path
        narration = tts_result.get("narration") if tts_result else self.existing_narration
        total_audio_dur = narration.duration_seconds if narration else None

        # Stage 4: Temporal Scene Scheduling using real audio timestamps
        self.progress_updated.emit(ProgressInfo(
            stage=JobStage.TEMPORAL_SCHEDULING,
            status=JobStatus.RUNNING,
            progress_percentage=85.0,
            message="Scheduling scene boundaries with audio synchronization (2.0s-8.0s hard cap)..."
        ))

        engine = GroqInferenceEngine(model_name=self.request.model_name)
        scheduled_storyboard = Stage4TemporalScheduler.execute(
            engine=engine,
            visual_plan=visual_plan_result,
            narration=narration,
            story_text=story_text,
            total_audio_duration=total_audio_dur
        )

        # Convert scheduled scenes to VisualScene for approval grid
        scenes_result = []
        for s in scheduled_storyboard.scenes:
            scenes_result.append(VisualScene(
                scene_id=s.scene_id,
                index=getattr(s, "index", None),
                start=s.start_time,
                end=s.end_time,
                duration=s.duration,
                narration_excerpt=s.narration_text,
                visual_subject=s.visual_summary,
                action=s.visual_summary,
                environment="Historical environment",
                composition="Eye-level wide shot",
                emotional_tone="Dramatic",
                historical_confidence="well_supported_reconstruction",
                prompt=f"[Planned Visual Shot — Awaiting Batch Prompt Gen]\n{s.visual_summary}",
                source_narrative_beat_ids=getattr(s, "source_narrative_beat_ids", []),
                source_visual_beat_ids=getattr(s, "source_visual_beat_ids", []),
                start_word_index=getattr(s, "source_word_start", None),
                end_word_index=getattr(s, "source_word_end", None),
                character_ids=getattr(s, "character_ids", []),
                location_id=getattr(s, "location_id", None),
                chronological_order=getattr(s, "chronological_order", None)
            ))

        self.progress_updated.emit(ProgressInfo(
            stage=JobStage.PLANNING,
            status=JobStatus.COMPLETED,
            progress_percentage=100.0,
            message=f"Voiceover ready & {len(scenes_result)} scenes planned for approval."
        ))

        self.pipeline_ready.emit(analysis_result, scenes_result, audio_path or "", narration)
