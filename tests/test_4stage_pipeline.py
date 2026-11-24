"""
Comprehensive Test Suite for PromptBeast's Streamlined 4-Stage Architecture.
Tests Stage 1, Stage 2, Stage 3, Stage 4, and the unified PipelineOrchestrator.
Validates zero cross-story contamination across multiple genres:
- Zombie Survival Story
- Constantinople 1453 Documentary
- Julius Caesar Documentary
- Science Explainer (Quantum Physics)
"""
import os
import sys
import json
import shutil
import unittest
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.models.job import JobStage, JobStatus
from app.models.presets import SubjectPreset, VisualStylePreset
from app.models.scene import VisualScene
from app.models.planning import StoryIntelligence, ScriptAnalysis
from app.models.timeline import NarrationData, WordTimestamp
from app.presets.loader import PresetManager
from app.ai.schemas import JobCreateRequest
from backend.jobs.store import JobStore
from backend.inference.engine import MockInferenceEngine

from backend.pipeline.stage1_story_intelligence import (
    Stage1StoryIntelligence,
    save_story_bibles,
    is_valid_thumbnail_headline,
    extract_smart_fallback_headline
)
from backend.pipeline.stage2_visual_storyboard import Stage2VisualStoryboard
from backend.pipeline.stage3_prompt_generation import Stage3PromptGeneration
from backend.pipeline.stage4_rendering import Stage4RenderingManager
from backend.pipeline.orchestrator import PipelineOrchestrator


class Test4StagePipeline(unittest.TestCase):

    def setUp(self):
        self.test_dir = ROOT_DIR / "tests" / "test_scratch"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.engine = MockInferenceEngine()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # =========================================================================
    # STAGE 1: STORY INTELLIGENCE TESTS
    # =========================================================================

    def test_stage1_zombie_survival(self):
        """Verify dynamic extraction on Zombie Survival story with zero contamination."""
        zombie_script = (
            "Sixty people were locked inside this mall on the first night. "
            "By Day 20, you will find proof that one of them is still alive. "
            "And that is the least dangerous thing down there. "
            "A shadowy infected figure stands motionless at the end of the basement tunnel."
        )
        intel = Stage1StoryIntelligence.execute(
            engine=self.engine,
            story_text=zombie_script,
            subject_preset=SubjectPreset(id="zombie", name="Survival Horror", description="", system_instructions=""),
            project_dir=self.test_dir
        )
        self.assertIsInstance(intel, StoryIntelligence)
        self.assertTrue(len(intel.story_summary) > 0)

        # Check that files were persisted to disk
        self.assertTrue((self.test_dir / "character_bible.txt").exists())
        self.assertTrue((self.test_dir / "location_bible.txt").exists())
        self.assertTrue((self.test_dir / "story_bible.txt").exists())

        # Check for ZERO contamination (no Caesar or Constantinople in a zombie story)
        full_output = json.dumps(intel.model_dump()).lower()
        self.assertNotIn("caesar", full_output)
        self.assertNotIn("constantinople", full_output)
        self.assertNotIn("byzantine", full_output)

    def test_stage1_caesar_documentary(self):
        """Verify dynamic extraction on Caesar documentary with zero contamination."""
        caesar_script = (
            "In 44 BC, Julius Caesar entered the Roman Senate for the Ides of March. "
            "Sixty conspirators, led by Brutus and Cassius, drew hidden daggers. "
            "The dictator fell at the foot of Pompey's statue, stabbed twenty-three times."
        )
        intel = Stage1StoryIntelligence.execute(
            engine=self.engine,
            story_text=caesar_script,
            subject_preset=SubjectPreset(id="history", name="Roman History", description="", system_instructions=""),
            project_dir=self.test_dir
        )
        self.assertIsInstance(intel, StoryIntelligence)
        full_output = json.dumps(intel.model_dump()).lower()
        # Verify no zombie contamination in Roman history
        self.assertNotIn("zombie", full_output)
        self.assertNotIn("infected", full_output)
        self.assertNotIn("shopping mall", full_output)

    def test_stage1_quantum_science_explainer(self):
        """Verify dynamic extraction on Science explainer with zero contamination."""
        science_script = (
            "At the subatomic scale, particles do not occupy fixed positions. "
            "In quantum superposition, an electron behaves simultaneously as a wave and a particle "
            "until observation collapses its wavefunction."
        )
        intel = Stage1StoryIntelligence.execute(
            engine=self.engine,
            story_text=science_script,
            subject_preset=SubjectPreset(id="science", name="Quantum Physics", description="", system_instructions=""),
            project_dir=self.test_dir
        )
        self.assertIsInstance(intel, StoryIntelligence)
        full_output = json.dumps(intel.model_dump()).lower()
        self.assertNotIn("zombie", full_output)
        self.assertNotIn("caesar", full_output)

    def test_thumbnail_headline_validation(self):
        """Test high-CTR thumbnail headline validation rules."""
        self.assertTrue(is_valid_thumbnail_headline("SURVIVE DAY 20"))
        self.assertTrue(is_valid_thumbnail_headline("THE FINAL NIGHT"))
        self.assertFalse(is_valid_thumbnail_headline("HOW TO SURVIVE"))
        self.assertFalse(is_valid_thumbnail_headline("WHY DID THEY DIE"))
        self.assertFalse(is_valid_thumbnail_headline("A"))

        fallback = extract_smart_fallback_headline("Sixty people trapped inside abandoned shopping mall basement.")
        self.assertTrue(len(fallback.split()) in (2, 3))

    # =========================================================================
    # STAGE 2: VISUAL STORYBOARD TESTS
    # =========================================================================

    def test_stage2_visual_storyboard_with_user_ideas(self):
        """Test storyboard generation with pre-planned user ideas and narration timestamps."""
        intel = StoryIntelligence(
            story_summary="Zombie mall survival.",
            characters=[{"name": "Survivor", "physical_description": "Man in dark hoodie"}],
            environments=[{"name": "Basement corridor", "architectural_style": "Concrete mall basement"}]
        )
        user_ideas = (
            "Visual 1 Words: Sixty people were locked inside this mall on the first night. Visual: Steel shutters locked.\n"
            "Visual 2 Words: By Day 20, you will find proof that one of them is still alive. Visual: Fresh footprints in dust."
        )
        narration = NarrationData(
            text="Sixty people were locked inside this mall on the first night. By Day 20, you will find proof that one of them is still alive.",
            words=[
                WordTimestamp(word="Sixty", start=0.0, end=0.4),
                WordTimestamp(word="people", start=0.4, end=0.8),
                WordTimestamp(word="were", start=0.8, end=1.0),
                WordTimestamp(word="locked", start=1.0, end=1.4),
                WordTimestamp(word="inside", start=1.4, end=1.8),
                WordTimestamp(word="this", start=1.8, end=2.0),
                WordTimestamp(word="mall", start=2.0, end=2.4),
                WordTimestamp(word="on", start=2.4, end=2.6),
                WordTimestamp(word="the", start=2.6, end=2.8),
                WordTimestamp(word="first", start=2.8, end=3.2),
                WordTimestamp(word="night.", start=3.2, end=3.8),
                WordTimestamp(word="By", start=4.0, end=4.2),
                WordTimestamp(word="Day", start=4.2, end=4.6),
                WordTimestamp(word="20,", start=4.6, end=5.0),
                WordTimestamp(word="you", start=5.0, end=5.2),
                WordTimestamp(word="will", start=5.2, end=5.4),
                WordTimestamp(word="find", start=5.4, end=5.8),
                WordTimestamp(word="proof", start=5.8, end=6.2),
                WordTimestamp(word="that", start=6.2, end=6.4),
                WordTimestamp(word="one", start=6.4, end=6.6),
                WordTimestamp(word="of", start=6.6, end=6.8),
                WordTimestamp(word="them", start=6.8, end=7.0),
                WordTimestamp(word="is", start=7.0, end=7.2),
                WordTimestamp(word="still", start=7.2, end=7.5),
                WordTimestamp(word="alive.", start=7.5, end=8.0)
            ],
            duration_seconds=8.0,
            is_estimated=False
        )

        scenes = Stage2VisualStoryboard.execute(
            story_intelligence=intel,
            narration=narration,
            user_visual_ideas=user_ideas
        )

        self.assertEqual(len(scenes), 2)
        self.assertEqual(scenes[0].scene_id, "001")
        self.assertEqual(scenes[1].scene_id, "002")
        self.assertAlmostEqual(scenes[0].start, 0.0, places=1)
        self.assertAlmostEqual(scenes[1].start, 4.0, places=1)

        # Crucial Requirement: NO image prompts should be generated at Stage 2
        for s in scenes:
            self.assertEqual(s.prompt, "")
            self.assertEqual(s.generation_status, "pending")
            self.assertTrue(len(s.visual_description) > 0)

    # =========================================================================
    # STAGE 3: IMAGE PROMPT GENERATION TESTS
    # =========================================================================

    def test_stage3_prompt_generation_and_approval_protection(self):
        """Test prompt expansion adhering to visual style and protecting approved scenes."""
        scenes = [
            VisualScene(
                scene_id="001",
                start=0.0,
                end=3.8,
                duration=3.8,
                narration_excerpt="Sixty people were locked inside.",
                visual_subject="Locked mall shutters",
                visual_idea="Steel shutters locked down",
                prompt="Approved custom prompt by user --ar 16:9",
                is_approved=True
            ),
            VisualScene(
                scene_id="002",
                start=4.0,
                end=8.0,
                duration=4.0,
                narration_excerpt="By Day 20, proof that one is still alive.",
                visual_subject="Footprints in concrete dust",
                visual_idea="Fresh footprints in dusty concrete corridor",
                prompt="",
                is_approved=False
            )
        ]

        style = PresetManager.get_style_by_id("zombie_survival")
        intel = StoryIntelligence(story_summary="Mall survival.")

        updated_scenes = Stage3PromptGeneration.execute(
            storyboard=scenes,
            story_intelligence=intel,
            style_preset=style,
            engine=self.engine,
            force_regenerate=False
        )

        # Scene 001 was approved: MUST be preserved exactly!
        self.assertEqual(updated_scenes[0].prompt, "Approved custom prompt by user --ar 16:9")

        # Scene 002 was pending: MUST now have a clean generated prompt without Midjourney flags
        self.assertTrue(len(updated_scenes[1].prompt) > 0)
        self.assertNotIn("/imagine", updated_scenes[1].prompt)
        self.assertNotIn("--ar", updated_scenes[1].prompt)
        self.assertNotIn("--style raw", updated_scenes[1].prompt)

    # =========================================================================
    # STAGE 4: ASSET ASSIGNMENT & RENDERING TESTS
    # =========================================================================

    def test_stage4_image_binding_and_validation(self):
        """Test auto-binding images from folder and tracking missing assets."""
        img_dir = self.test_dir / "images"
        img_dir.mkdir(parents=True, exist_ok=True)

        # Create dummy image files
        (img_dir / "scene_001.png").write_bytes(b"dummy_png_data")
        (img_dir / "scene_002.jpg").write_bytes(b"dummy_jpg_data")

        scenes = [
            VisualScene(scene_id="001", start=0.0, end=4.0, duration=4.0, visual_subject="Scene 1"),
            VisualScene(scene_id="002", start=4.0, end=8.0, duration=4.0, visual_subject="Scene 2"),
            VisualScene(scene_id="003", start=8.0, end=12.0, duration=4.0, visual_subject="Scene 3")
        ]

        bind_res = Stage4RenderingManager.bind_images_from_directory(scenes, str(img_dir))
        self.assertEqual(bind_res["assigned"], 2)
        self.assertEqual(bind_res["missing"], 1)
        self.assertIn("003", bind_res["missing_scene_ids"])

        val_res = Stage4RenderingManager.validate_assets_for_rendering(
            scenes=scenes,
            audio_path=str(self.test_dir / "audio.mp3"),
            allow_placeholders=True
        )
        self.assertFalse(val_res["is_valid"])  # False because audio.mp3 does not exist on disk
        self.assertIn("Audio file missing", val_res["errors"][0])

    # =========================================================================
    # PIPELINE ORCHESTRATOR END-TO-END TEST
    # =========================================================================

    def test_pipeline_orchestrator_end_to_end(self):
        """Test running all 4 stages cleanly through PipelineOrchestrator."""
        job_id = "test_job_12345"
        req = JobCreateRequest(
            project_name="TestMallSurvival",
            story_text="Sixty people were trapped inside this mall. Shadows lurked in every corner.",
            subject_id="zombie",
            visual_style_id="zombie_survival"
        )

        PipelineOrchestrator.run_pipeline(
            job_id=job_id,
            request=req,
            engine=self.engine,
            project_dir=str(self.test_dir)
        )

        store = JobStore()
        job = store.get_job(job_id)
        self.assertIsNotNone(job)
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertEqual(job.stage, JobStage.COMPLETED)

        scenes = store.get_scenes(job_id)
        self.assertTrue(len(scenes) > 0)
        for s in scenes:
            self.assertTrue(len(s.prompt) > 0)
            self.assertEqual(s.generation_status, "generated")


if __name__ == "__main__":
    unittest.main()

