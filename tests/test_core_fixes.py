"""
Regression tests for the Script Beanie core fixes (2026-11-10).

Fix 1: Stage 3 fails loudly instead of silently filling template prompts.
Fix 2: Deterministic storyboard validation gate (prompts, IDs, timeline).
Fix 3: Groq engine — 950 output cap, effective-cap memory, 2s pacing,
       key-wait rule (<=3s same key, >3s rotate), no silent model fallback.
Fix 4: Stage 3 batch size derived from the measured per-prompt cost.
Fix 5: MASTER prompt carries no fixed story example.
Fix 6: Dead Stage4TemporalScheduler stub is gone.
"""
import json
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import httpx

from app.ai.groq_engine import (
    GroqEngine,
    GroqMultiKeyManager,
    parse_groq_retry_after,
    parse_groq_reduced_max_tokens,
)
from app.models.planning import StoryIntelligence
from app.models.presets import VisualStylePreset
from app.models.scene import VisualScene
from app.models.timeline import NarrationData
from app.presets.loader import PresetManager
from backend.inference.engine import MockInferenceEngine
from backend.pipeline.stage3_prompt_generation import (
    Stage3PromptGeneration,
    derive_stage3_batch_size,
)
from backend.pipeline.stage_validation import validate_storyboard


def make_scene(scene_id, start, end, prompt=""):
    return VisualScene(
        scene_id=scene_id,
        start=start,
        end=end,
        duration=round(end - start, 3),
        narration_excerpt=f"Narration for scene {scene_id}.",
        visual_subject=f"Subject {scene_id}",
        visual_idea=f"Visual idea {scene_id}",
        prompt=prompt,
        is_approved=False,
    )


# =========================================================================
# Fake httpx (scripted responses) for engine tests
# =========================================================================

class FakeResponse:
    def __init__(self, status_code, text="", json_data=None, headers=None):
        self.status_code = status_code
        self.text = text
        self._json_data = json_data
        self.headers = headers or {}

    def json(self):
        if self._json_data is not None:
            return self._json_data
        raise ValueError("no json body")


def ok_response(content="Hello world"):
    return FakeResponse(200, json_data={"choices": [{"message": {"content": content}}]})


class FakeClient:
    """Scripted httpx.Client replacement. script/posts are class-level so
    every fresh Client() instance in the retry loop shares them."""
    script = []
    posts = []

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, headers=None, json=None):
        FakeClient.posts.append((url, dict(headers or {}), dict(json or {})))
        if not FakeClient.script:
            raise RuntimeError("FakeClient ran out of scripted responses")
        return FakeClient.script.pop(0)


class TestEngineProtections(unittest.TestCase):
    def setUp(self):
        FakeClient.script = []
        FakeClient.posts = []

    def _make_engine(self, keys=None):
        keys = keys or [
            "gsk_" + "a" * 40,
            "gsk_" + "b" * 40,
        ]
        engine = GroqEngine(key_manager=GroqMultiKeyManager(keys=keys))
        # Disable the 2s pacing sleep so engine tests run fast.
        engine.REQUEST_PACING_SECONDS = 0
        return engine

    # --- parse helpers ----------------------------------------------------

    def test_parse_retry_after_returns_none_when_unparseable(self):
        self.assertIsNone(parse_groq_retry_after(text="Something went wrong"))
        self.assertIsNone(parse_groq_retry_after(headers={}))
        self.assertIsNone(parse_groq_retry_after())

    def test_parse_retry_after_parses_seconds_and_ms(self):
        self.assertEqual(parse_groq_retry_after(text="try again in 2s"), 2.0)
        self.assertEqual(parse_groq_retry_after(text="try again in 0.1s"), 0.1)
        self.assertEqual(parse_groq_retry_after(text="try again in 500ms"), 0.5)
        self.assertEqual(parse_groq_retry_after(headers={"retry-after": "7"}), 7.0)

    def test_parse_reduced_max_tokens(self):
        self.assertEqual(
            parse_groq_reduced_max_tokens("reduce max_tokens to 800 and retry"), 800
        )
        self.assertIsNone(parse_groq_reduced_max_tokens("try again in 2s"))

    # --- effective cap ----------------------------------------------------

    def test_effective_cap_accessor(self):
        engine = self._make_engine()
        self.assertEqual(engine.current_effective_max_tokens(), 950)
        engine._effective_cap = 800
        engine._effective_cap_until = time.time() + 60
        self.assertEqual(engine.current_effective_max_tokens(), 800)
        # Expired recovery window -> baseline again.
        engine._effective_cap_until = time.time() - 1
        self.assertEqual(engine.current_effective_max_tokens(), 950)

    # --- generate_text with scripted HTTP --------------------------------

    def test_generate_text_clamps_max_tokens_to_950(self):
        engine = self._make_engine()
        FakeClient.script = [ok_response("done")]
        with mock.patch.object(httpx, "Client", FakeClient):
            result = engine.generate_text(prompt="test", max_tokens=3000)
        self.assertEqual(result, "done")
        self.assertEqual(len(FakeClient.posts), 1)
        self.assertEqual(FakeClient.posts[0][2]["max_tokens"], 950)

    def test_429_short_wait_retries_same_key(self):
        engine = self._make_engine()
        FakeClient.script = [
            FakeResponse(429, text="Rate limit exceeded. Please try again in 0.1s."),
            ok_response("recovered"),
        ]
        with mock.patch.object(httpx, "Client", FakeClient):
            result = engine.generate_text(prompt="test", max_tokens=3000)
        self.assertEqual(result, "recovered")
        self.assertEqual(len(FakeClient.posts), 2)
        key1 = FakeClient.posts[0][1]["Authorization"]
        key2 = FakeClient.posts[1][1]["Authorization"]
        self.assertEqual(key1, key2, "short 429 wait must retry the SAME key")
        # The 429 also lowered the effective cap to 800.
        self.assertEqual(FakeClient.posts[1][2]["max_tokens"], 800)

    def test_429_long_wait_rotates_key(self):
        engine = self._make_engine()
        FakeClient.script = [
            FakeResponse(429, text="Rate limit exceeded. Please try again in 30s."),
            ok_response("recovered"),
        ]
        with mock.patch.object(httpx, "Client", FakeClient):
            result = engine.generate_text(prompt="test", max_tokens=3000)
        self.assertEqual(result, "recovered")
        self.assertEqual(len(FakeClient.posts), 2)
        key1 = FakeClient.posts[0][1]["Authorization"]
        key2 = FakeClient.posts[1][1]["Authorization"]
        self.assertNotEqual(key1, key2, "long 429 wait must rotate to another key")

    def test_429_reduce_directive_sets_cap(self):
        engine = self._make_engine()
        FakeClient.script = [
            FakeResponse(
                429,
                text="Rate limit exceeded. Please reduce max_tokens to 600 and try again in 30s.",
            ),
            ok_response("recovered"),
        ]
        with mock.patch.object(httpx, "Client", FakeClient):
            result = engine.generate_text(prompt="test", max_tokens=3000)
        self.assertEqual(result, "recovered")
        self.assertEqual(FakeClient.posts[1][2]["max_tokens"], 600)

    def test_no_silent_model_fallback(self):
        # One key, every attempt 429s with a short wait -> same-key retries
        # until attempts are exhausted, then fail loudly. No gpt-oss call.
        engine = self._make_engine(keys=["gsk_" + "c" * 40])
        FakeClient.script = [
            FakeResponse(429, text="Rate limit exceeded. Please try again in 0.1s.")
        ] * 20
        with mock.patch.object(httpx, "Client", FakeClient):
            with self.assertRaises(RuntimeError):
                engine.generate_text(prompt="test", max_tokens=3000)
        self.assertTrue(len(FakeClient.posts) >= 1)
        for _url, _headers, payload in FakeClient.posts:
            self.assertEqual(payload["model"], "qwen/qwen3.8-27b")
            self.assertNotIn("gpt-oss", payload["model"])


# =========================================================================
# Fix 1: Stage 3 fails loudly
# =========================================================================

class PartialEngine:
    """Returns prompts for only the first scene of a batch (simulates a
    truncated / incomplete model response)."""

    def __init__(self, scene_ids_to_return):
        self.scene_ids_to_return = scene_ids_to_return

    def generate_text(self, prompt=None, system_prompt=None, temperature=None, max_tokens=None):
        items = [
            {"scene_id": sid, "prompt": f"Real prompt for {sid}", "negative_prompt": "none"}
            for sid in self.scene_ids_to_return
        ]
        return json.dumps({"scenes": items})


class RaisingEngine:
    def generate_text(self, prompt=None, system_prompt=None, temperature=None, max_tokens=None):
        raise RuntimeError("simulated engine failure")


class TestStage3FailLoudly(unittest.TestCase):
    def setUp(self):
        self.style = PresetManager.get_style_by_id("zombie_survival")
        self.intel = StoryIntelligence(story_summary="Mall survival.")

    def _scenes(self):
        return [
            make_scene("001", 0.0, 3.8),
            make_scene("002", 4.0, 8.0),
        ]

    def test_missing_scene_raises_and_names_it(self):
        with self.assertRaises(RuntimeError) as ctx:
            Stage3PromptGeneration.execute(
                storyboard=self._scenes(),
                story_intelligence=self.intel,
                style_preset=self.style,
                engine=PartialEngine(["001"]),
            )
        self.assertIn("002", str(ctx.exception))

    def test_engine_error_raises_instead_of_filling(self):
        with self.assertRaises(RuntimeError):
            Stage3PromptGeneration.execute(
                storyboard=self._scenes(),
                story_intelligence=self.intel,
                style_preset=self.style,
                engine=RaisingEngine(),
            )

    def test_no_template_fill_marker(self):
        # A complete response still works and is not a template fill.
        scenes = self._scenes()
        updated = Stage3PromptGeneration.execute(
            storyboard=scenes,
            story_intelligence=self.intel,
            style_preset=self.style,
            engine=PartialEngine(["001", "002"]),
        )
        for s in updated:
            self.assertTrue(s.prompt.startswith("Real prompt for"))

    def test_allow_partial_marks_missing_scenes_as_error(self):
        # With allow_partial=True, missing scene 002 is marked with generation_status="error"
        # without raising an unhandled exception.
        scenes = self._scenes()
        result = Stage3PromptGeneration.execute(
            storyboard=scenes,
            story_intelligence=self.intel,
            style_preset=self.style,
            engine=PartialEngine(["001"]),
            allow_partial=True,
        )
        self.assertEqual(len(result), 2)
        s1 = next(s for s in result if s.scene_id == "001")
        s2 = next(s for s in result if s.scene_id == "002")
        self.assertTrue(s1.prompt.startswith("Real prompt for 001"))
        self.assertEqual(s2.generation_status, "error")
        self.assertFalse(s2.is_validated)

    def test_pass2_retry_recovers_missing_scene(self):
        # Engine fails on first attempt for 002, but in Pass 2 (single scene retry) succeeds.
        class FlakyEngine:
            def __init__(self):
                self.calls = 0

            def generate_text(self, prompt=None, system_prompt=None, temperature=None, max_tokens=None):
                self.calls += 1
                if self.calls == 1:
                    # Pass 1 batch: returns only 001
                    return json.dumps({"scenes": [{"scene_id": "001", "prompt": "Prompt 001", "negative_prompt": ""}]})
                else:
                    # Pass 2 retry for missing scene 002: succeeds
                    return json.dumps({"scenes": [{"scene_id": "002", "prompt": "Recovered Prompt 002", "negative_prompt": ""}]})

        scenes = self._scenes()
        result = Stage3PromptGeneration.execute(
            storyboard=scenes,
            story_intelligence=self.intel,
            style_preset=self.style,
            engine=FlakyEngine(),
            allow_partial=False,
        )
        self.assertEqual(len(result), 2)
        s1 = next(s for s in result if s.scene_id == "001")
        s2 = next(s for s in result if s.scene_id == "002")
        self.assertEqual(s1.prompt, "Prompt 001")
        self.assertEqual(s2.prompt, "Recovered Prompt 002")


# =========================================================================
# Fix 2: Validation gate
# =========================================================================

class TestValidationGate(unittest.TestCase):
    def test_valid_storyboard_passes(self):
        scenes = [
            make_scene("001", 0.0, 3.8, prompt="A prompt"),
            make_scene("002", 4.0, 8.0, prompt="Another prompt"),
        ]
        # Small inter-word gap (0.2s) is allowed.
        validate_storyboard(scenes)

    def test_valid_storyboard_with_narration_passes(self):
        scenes = [
            make_scene("001", 0.0, 3.8, prompt="A prompt"),
            make_scene("002", 4.0, 8.0, prompt="Another prompt"),
        ]
        narration = NarrationData(text="x", words=[], duration_seconds=8.0)
        validate_storyboard(scenes, narration=narration)

    def test_missing_prompt_raises(self):
        scenes = [make_scene("001", 0.0, 3.8, prompt="")]
        with self.assertRaises(RuntimeError) as ctx:
            validate_storyboard(scenes)
        self.assertIn("001", str(ctx.exception))

    def test_duplicate_scene_id_raises(self):
        scenes = [
            make_scene("001", 0.0, 3.8, prompt="A"),
            make_scene("001", 4.0, 8.0, prompt="B"),
        ]
        with self.assertRaises(RuntimeError):
            validate_storyboard(scenes)

    def test_overlap_raises(self):
        scenes = [
            make_scene("001", 0.0, 5.0, prompt="A"),
            make_scene("002", 4.0, 8.0, prompt="B"),
        ]
        with self.assertRaises(RuntimeError):
            validate_storyboard(scenes)

    def test_large_gap_raises(self):
        scenes = [
            make_scene("001", 0.0, 3.8, prompt="A"),
            make_scene("002", 6.0, 10.0, prompt="B"),
        ]
        with self.assertRaises(RuntimeError):
            validate_storyboard(scenes)

    def test_narration_not_covered_raises(self):
        scenes = [make_scene("001", 0.0, 3.8, prompt="A")]
        narration = NarrationData(text="x", words=[], duration_seconds=30.0)
        with self.assertRaises(RuntimeError):
            validate_storyboard(scenes, narration=narration)

    def test_natural_pause_gap_healed_without_error(self):
        # 0.74s pause between sentences (e.g. 9.04s to 9.78s) must be healed,
        # extending previous scene's end to next scene's start without raising.
        scenes = [
            make_scene("003", 7.02, 9.04, prompt="Scene 3 prompt"),
            make_scene("004", 9.78, 18.86, prompt="Scene 4 prompt"),
        ]
        validate_storyboard(scenes)
        self.assertEqual(scenes[0].end, 9.78)
        self.assertEqual(scenes[0].duration, round(9.78 - 7.02, 2))


# =========================================================================
# Fix 4: Derived batch size
# =========================================================================

class CountingEngine:
    """Wraps the mock engine, counts generate_text calls."""

    def __init__(self, inner):
        self.inner = inner
        self.calls = 0

    def generate_text(self, *args, **kwargs):
        self.calls += 1
        return self.inner.generate_text(*args, **kwargs)

    def current_effective_max_tokens(self, baseline=950):
        return baseline


class TestDerivedBatchSize(unittest.TestCase):
    def test_mock_engine_defaults_to_950_cap(self):
        self.assertEqual(derive_stage3_batch_size(MockInferenceEngine(), 8), 2)

    def test_reduced_cap_still_two(self):
        class Cap800:
            def current_effective_max_tokens(self, baseline=950):
                return 800

        self.assertEqual(derive_stage3_batch_size(Cap800(), 8), 2)

    def test_small_cap_drops_to_one(self):
        class Cap600:
            def current_effective_max_tokens(self, baseline=950):
                return 600

        self.assertEqual(derive_stage3_batch_size(Cap600(), 8), 1)

    def test_requested_size_is_an_upper_bound(self):
        self.assertEqual(derive_stage3_batch_size(MockInferenceEngine(), 1), 1)

    def test_stage3_uses_derived_batch_size(self):
        # 6 scenes, derived batch size 2 -> exactly 3 engine calls.
        scenes = [make_scene(f"{i:03d}", float(i * 4), float(i * 4 + 4)) for i in range(6)]
        style = PresetManager.get_style_by_id("zombie_survival")
        intel = StoryIntelligence(story_summary="Mall survival.")
        engine = CountingEngine(MockInferenceEngine())
        updated = Stage3PromptGeneration.execute(
            storyboard=scenes,
            story_intelligence=intel,
            style_preset=style,
            engine=engine,
            batch_size=8,
        )
        self.assertEqual(engine.calls, 3)
        for s in updated:
            self.assertTrue(len(s.prompt) > 0)


# =========================================================================
# Fix 5: MASTER prompt has no fixed story example
# Fix 6: Dead stub is gone
# =========================================================================

class TestMasterPromptAndDeadCode(unittest.TestCase):
    def test_master_prompt_has_no_fixed_zombie_example(self):
        prompt_file = ROOT_DIR / "config" / "ai_prompts" / "01_zombie_survival_ai_prompt.txt"
        text = prompt_file.read_text(encoding="utf-8")
        self.assertNotIn("Sixty people were locked inside", text)
        self.assertNotIn("By Day 20, you will find proof", text)

    def test_dead_stage4_scheduler_stub_is_gone(self):
        import backend.pipeline.stage2_visual_storyboard as stage2_mod

        self.assertFalse(hasattr(stage2_mod, "Stage4TemporalScheduler"))


# =========================================================================
# Fix 7: StoryboardExporter and Clipboard robustness
# =========================================================================

class TestStoryboardExporterAndClipboard(unittest.TestCase):
    def test_clean_prompt_single_line_strips_mj_flags_and_placeholders(self):
        from app.core.export import StoryboardExporter
        raw = "/imagine prompt: [Planned Visual Shot - Awaiting Batch Prompt Gen] Wide shot of mall --ar 16:9 --style raw"
        clean = StoryboardExporter.clean_prompt_single_line(raw)
        self.assertEqual(clean, "Wide shot of mall")

    def test_export_to_prompts_only_and_text(self):
        from app.core.export import StoryboardExporter
        scenes = [
            make_scene("001", 0.0, 3.5, prompt="/imagine prompt: Scene 1 prompt --ar 16:9"),
            make_scene("002", 3.5, 7.0, prompt="Scene 2 prompt --style raw"),
        ]
        prompts_only = StoryboardExporter.export_to_prompts_only(scenes)
        lines = prompts_only.strip().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("prompt", lines[0])
        self.assertIn("prompt", lines[1])

        text_out = StoryboardExporter.export_to_text(scenes)
        self.assertIn("IMAGE 001", text_out)
        self.assertIn("IMAGE 002", text_out)
        self.assertIn("prompt", text_out)
        self.assertNotIn("--ar 16:9", text_out)

    def test_copy_to_system_clipboard_handles_text(self):
        from app.core.export import copy_to_system_clipboard
        ok = copy_to_system_clipboard("Automated test clipboard payload")
        self.assertTrue(ok)


class TestNavigationAndImagesPanel(unittest.TestCase):
    def test_images_panel_and_scene_sync_distinct(self):
        from app.ui.widgets import ImagesPanel, SceneSyncPanel
        self.assertIsNotNone(ImagesPanel)
        self.assertIsNotNone(SceneSyncPanel)
        self.assertIsNot(ImagesPanel, SceneSyncPanel)

    def test_sidebar_navigation_order(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from app.ui.widgets.sidebar_nav import SidebarNav
        nav = SidebarNav()
        keys = list(nav._buttons.keys())
        self.assertIn("images", keys)
        self.assertEqual(keys.index("images"), 2)
        self.assertTrue(keys.index("studio") < keys.index("images") < keys.index("deliverables"))


if __name__ == "__main__":
    unittest.main()
