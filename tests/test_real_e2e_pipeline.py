"""
Real End-to-End Test for PromptBeast Pipeline.
Exercises the entire real path without mocks:
1. Loads user-provided bibles from disk (audio and files/Bibles.txt) via BibleManager.
2. Loads user-provided storyboard scenes from disk (audio and files/story board zombie 1.txt).
3. Generates camera-ready image prompts via real Groq AI engine and verifies prose formatting (no headings, no bullets).
4. Saves project state and exports all production prompt files (txt, json, csv, prompts_only).
5. Renders a short synchronized video via real FFmpeg and verifies duration and file integrity.
"""
import os
import sys
import subprocess
import tempfile
from pathlib import Path
import pytest

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.bible_manager import BibleManager
from app.core.narration_workflow import parse_visual_breakdown_text, align_visuals_with_timestamps, import_script_json
from backend.inference.engine import GroqInferenceEngine
from backend.pipeline.stage3_prompt_generation import Stage3PromptGeneration
from app.presets.loader import PresetManager
from app.models.planning import StoryIntelligence
from app.core.export import StoryboardExporter
from app.core.video_renderer import VideoRenderer, VideoRenderSettings
from app.models.video_config import AspectRatio


class TestRealE2EPipeline:
    """Real end-to-end integration test running through the entire video pipeline."""

    def test_full_pipeline_real_e2e(self):
        # 1. Load user-provided production bibles
        bible_path = Path("audio and files/Bibles.txt")
        assert bible_path.exists(), "audio and files/Bibles.txt not found"
        bibles_map = BibleManager.load_bibles_from_path(bible_path)
        assert bibles_map, "Failed to load bibles from audio and files/Bibles.txt"
        bible_name = list(bibles_map.keys())[0]
        bible = bibles_map[bible_name]

        assert len(bible.get("characters", [])) >= 1, "Expected at least 1 character in bible"
        assert len(bible.get("environments", [])) >= 1, "Expected at least 1 environment in bible"

        # 2. Load user-provided storyboard scenes
        sb_path = Path("audio and files/story board zombie 1.txt")
        assert sb_path.exists(), "audio and files/story board zombie 1.txt not found"
        raw_sb = sb_path.read_text(encoding="utf-8")
        parsed_items = parse_visual_breakdown_text(raw_sb)
        assert len(parsed_items) >= 2, f"Expected at least 2 storyboard items, got {len(parsed_items)}"

        # Load narration timestamps
        json_res = import_script_json("audio and files/speech.json")
        assert json_res.success, f"Failed to load speech.json: {json_res.message}"
        narration = json_res.narration

        aligned_scenes = align_visuals_with_timestamps(
            visual_items=parsed_items[:2],
            narration=narration,
            total_audio_duration=narration.duration_seconds
        )
        assert len(aligned_scenes) == 2, f"Expected 2 aligned scenes, got {len(aligned_scenes)}"

        # 3. Generate prompts via real Groq AI engine
        engine = GroqInferenceEngine()
        style_preset = PresetManager.get_style_by_id("zombie_survival")
        story_intel = StoryIntelligence(
            story_summary=bible.get("story_bible", {}).get("logline", "Zombie survival story"),
            characters=bible.get("characters", []),
            environments=bible.get("environments", []),
            objects_and_props=bible.get("key_objects", []),
            visual_style_bible=bible.get("visual_style_bible", {})
        )

        generated_scenes = Stage3PromptGeneration.execute(
            storyboard=aligned_scenes,
            story_intelligence=story_intel,
            style_preset=style_preset,
            visual_style_id="zombie_survival",
            batch_size=2,
            engine=engine
        )

        # Verify generated prompts: non-empty, simple prose, NO headings, NO bullet points
        for sc in generated_scenes:
            assert sc.prompt and len(sc.prompt.strip()) > 20, f"Prompt empty for scene {sc.scene_id}"
            assert "**Subject:**" not in sc.prompt, f"Heading found in scene {sc.scene_id} prompt: {sc.prompt}"
            assert "**Environment:**" not in sc.prompt, f"Heading found in scene {sc.scene_id} prompt: {sc.prompt}"
            assert not sc.prompt.startswith("#"), f"Markdown header found: {sc.prompt}"
            assert "\n-" not in sc.prompt, f"Bullet point found: {sc.prompt}"
            assert "\n*" not in sc.prompt, f"Bullet point found: {sc.prompt}"

        # 4. Save project & export prompt files
        temp_dir = Path(tempfile.mkdtemp(prefix="pb_real_e2e_"))
        exports = StoryboardExporter.save_all_exports(
            output_dir=str(temp_dir),
            scenes=generated_scenes,
            narration=narration
        )

        for exp_key in ["text", "timeline_json", "prompts_json", "csv", "prompts_only"]:
            assert exp_key in exports, f"Missing export key: {exp_key}"
            exp_file = Path(exports[exp_key])
            assert exp_file.exists(), f"Export file does not exist: {exp_file}"
            assert exp_file.stat().st_size > 0, f"Export file is empty: {exp_file}"

        # 5. Render short video via FFmpeg
        audio_src = Path("audio and files/speech.mp3")
        assert audio_src.exists(), "Audio file audio and files/speech.mp3 missing"

        render_scenes = [aligned_scenes[0], aligned_scenes[1]]
        render_scenes[0].start = 0.0
        render_scenes[0].end = 2.0
        render_scenes[0].duration = 2.0
        render_scenes[1].start = 2.0
        render_scenes[1].end = 4.0
        render_scenes[1].duration = 2.0

        out_mp4 = temp_dir / "rendered_output.mp4"
        render_cfg = VideoRenderSettings(
            fps=24,
            ken_burns_enabled=False,
            render_subtitles=False
        )

        video_path = VideoRenderer.render_video_sync(
            scenes=render_scenes,
            audio_path=str(audio_src.resolve()),
            output_video_path=str(out_mp4),
            settings=render_cfg,
            narration=narration
        )

        assert Path(video_path).exists(), f"Rendered video missing at: {video_path}"
        assert Path(video_path).stat().st_size > 1000, "Rendered video file is too small"

        # Verify video duration with ffprobe
        cmd = [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        probe_res = subprocess.run(cmd, capture_output=True, text=True)
        dur = float(probe_res.stdout.strip())
        assert 3.5 <= dur <= 5.0, f"Video duration mismatch: expected ~4.0s, got {dur}s"
