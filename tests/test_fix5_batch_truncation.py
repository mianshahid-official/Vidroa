"""
Regression and verification test suite for Fix 5 (F5 v2):
Eliminate Silent Token Truncation and Incomplete Batch Output.

Covers:
1. Safe batch size derivation from real token budgets.
2. Truncation detection and selective retry for missing scenes only.
3. Per-scene failure softening (one failing scene does not crash good scenes,
   and fails loudly with the scene named).
4. Prompt generation across batch sizes of 1, 4, 8, and 20 scenes.
"""
import json
import pytest
from app.models.planning import (
    ScheduledScene,
    ScheduledStoryboard,
    ScriptAnalysis,
    ContinuityBible,
    CharacterEntity,
    LocationEntity,
    PlanningConstraints,
    TemporalCausalStructure
)
from app.models.scene import VisualScene
from app.presets.loader import PresetManager
from backend.inference.engine import BaseInferenceEngine, MockInferenceEngine
from backend.pipeline.stage5_prompts import Stage5PromptGenerator, derive_safe_batch_size
from backend.pipeline.stage8_validation import Stage8FinalValidator


def _build_dummy_analysis(period: str = "Ancient Historical Era") -> ScriptAnalysis:
    return ScriptAnalysis(
        script_summary="Historical narrative depicting soldiers approaching fortified city gates.",
        core_narrative_premise="Soldiers advance toward city gates",
        genre_and_tone="Dramatic Historical",
        setting_period=period,
        continuity_bible=ContinuityBible(
            characters=[
                CharacterEntity(name="Captain", role="Commander", appearance="Armored officer with cape", costume="Scale armor"),
                CharacterEntity(name="Archer", role="Scout", appearance="Light archer with composite bow", costume="Leather tunic")
            ],
            locations=[
                LocationEntity(
                    name="City Gate",
                    description="Massive wooden gate set within stone ramparts",
                    environment_details="Stone ramparts, dust and wind",
                    lighting_default="Dramatic daylight",
                    historical_or_setting_constraints="Authentic ancient stonework, zero modern structures"
                )
            ]
        ),
        temporal_and_causal_structure=TemporalCausalStructure(chronological_order="Linear"),
        visual_planning_constraints=PlanningConstraints()
    )


def _build_storyboard(scenes_data) -> ScheduledStoryboard:
    scheduled = []
    t = 0.0
    for sid, narr, action in scenes_data:
        scheduled.append(ScheduledScene(
            scene_id=sid,
            beat_id=f"VB-{sid}",
            start_time=t,
            end_time=t + 4.0,
            duration=4.0,
            narration_text=narr,
            visual_summary=action
        ))
        t += 4.0
    return ScheduledStoryboard(scenes=scheduled, total_duration=t)


# =========================================================================
# 1. BATCH SIZE DERIVATION
# =========================================================================

def test_batch_size_derivation():
    # Under free-tier 950-token cap: (950 - 100) // 350 = 2
    assert derive_safe_batch_size(requested_batch_size=4, max_output_tokens=950) == 2
    assert derive_safe_batch_size(requested_batch_size=1, max_output_tokens=950) == 1
    assert derive_safe_batch_size(requested_batch_size=20, max_output_tokens=950) == 2
    assert derive_safe_batch_size(requested_batch_size=2, max_output_tokens=950) == 2

    # Under paid-tier 2000-token cap: (2000 - 100) // 350 = 5
    assert derive_safe_batch_size(requested_batch_size=4, max_output_tokens=2000) == 4
    assert derive_safe_batch_size(requested_batch_size=8, max_output_tokens=2000) == 5
    assert derive_safe_batch_size(requested_batch_size=1, max_output_tokens=2000) == 1


# =========================================================================
# 2. TRUNCATION DETECTION & SELECTIVE RETRY
# =========================================================================

class TruncatingMockEngine(BaseInferenceEngine):
    """
    Simulates a batch call that truncates and only returns the first scene,
    but recovers the missing scene during the selective retry call.
    """
    def __init__(self):
        self.batch_calls = 0
        self.retry_calls = 0

    def generate_text(self, prompt: str, system_prompt=None, temperature=None, max_tokens=None) -> str:
        if "SCENES TO WRITE PROMPTS FOR" in prompt:
            self.batch_calls += 1
            # Truncated response: only scene 001 returned
            return json.dumps({
                "prompts": [
                    {
                        "scene_id": "001",
                        "prompt": "Armored soldiers in rank formation advancing steadily toward fortified city gates under a stormy sky.",
                        "subject": "Soldiers approaching gates",
                        "composition": "Wide cinematic shot"
                    }
                ]
            })
        elif "SCENE TO PROMPT:" in prompt:
            self.retry_calls += 1
            return json.dumps({
                "scene_id": "002",
                "prompt": "Vanguard archers drawing composite bows as iron portcullis drops down with heavy clang.",
                "subject": "Archers drawing bows",
                "composition": "Low angle dramatic shot"
            })
        return "{}"


def test_truncation_detection_and_selective_retry(capsys):
    engine = TruncatingMockEngine()
    analysis = _build_dummy_analysis()
    storyboard = _build_storyboard([
        ("001", "The soldiers approached the outer gates in silence.", "Soldiers march toward gate"),
        ("002", "Archers drew their bows as the iron portcullis began to fall.", "Archers draw bows")
    ])

    scenes = Stage5PromptGenerator.execute(
        engine=engine,
        scheduled_storyboard=storyboard,
        analysis=analysis,
        batch_size=2
    )

    captured = capsys.readouterr()
    # Verify loud warning
    assert "WARNING: Batch 1 output incomplete/truncated" in captured.out
    assert "selective retry for missing scenes only" in captured.out
    assert "Successfully recovered scene #002 via selective retry" in captured.out

    # Verify both scenes exist and have correct prompts
    assert len(scenes) == 2
    assert scenes[0].scene_id == "001"
    assert "Armored soldiers" in scenes[0].prompt
    assert scenes[1].scene_id == "002"
    assert "Vanguard archers" in scenes[1].prompt

    # Verify engine calls: 1 batch call + 1 targeted retry call
    assert engine.batch_calls >= 1
    assert engine.retry_calls == 1


# =========================================================================
# 3. SOFTENED PER-SCENE FAILURE
# =========================================================================

class SingleSceneFailingEngine(BaseInferenceEngine):
    """
    Simulates Scene 002 failing completely (e.g. malformed JSON or empty output),
    while Scene 001 and Scene 003 succeed.
    """
    def generate_text(self, prompt: str, system_prompt=None, temperature=None, max_tokens=None) -> str:
        if "SCENE TO PROMPT:" in prompt and "002" in prompt:
            # Failure on retry for scene 002
            return "MALFORMED_NON_JSON_TRUNCATED..."
        elif "SCENES TO WRITE PROMPTS FOR" in prompt:
            # Batch call returns scenes 001 and 003, omits 002
            return json.dumps({
                "prompts": [
                    {
                        "scene_id": "001",
                        "prompt": "Soldiers assembling at the edge of the valley before sunrise.",
                        "subject": "Soldiers assembling",
                        "composition": "Wide establishing shot"
                    },
                    {
                        "scene_id": "003",
                        "prompt": "Heavy bronze battering ram striking the reinforced timber barricade.",
                        "subject": "Battering ram striking gate",
                        "composition": "Close-up impact shot"
                    }
                ]
            })
        return "{}"


def test_per_scene_failure_preserves_good_scenes_and_fails_loudly():
    engine = SingleSceneFailingEngine()
    analysis = _build_dummy_analysis()
    storyboard = _build_storyboard([
        ("001", "The soldiers assembled at dawn in the valley.", "Soldiers assemble"),
        ("002", "An unknown horn echoed across the mist-covered ridge.", "Horn echoes"),
        ("003", "The battering ram struck the barricade with tremendous force.", "Ram strikes barricade")
    ])

    # Must NOT raise RuntimeError!
    scenes = Stage5PromptGenerator.execute(
        engine=engine,
        scheduled_storyboard=storyboard,
        analysis=analysis,
        batch_size=2
    )

    assert len(scenes) == 3
    # Scene 1 succeeded
    assert scenes[0].scene_id == "001"
    assert len(scenes[0].prompt) > 20

    # Scene 2 failed per-scene: prompt is empty (NO generic fallback), flagged in validation_notes
    assert scenes[1].scene_id == "002"
    assert scenes[1].prompt == ""
    assert scenes[1].is_validated is False
    assert "PROMPT_GENERATION_FAILED" in (scenes[1].validation_notes or "")

    # Scene 3 succeeded
    assert scenes[2].scene_id == "003"
    assert len(scenes[2].prompt) > 20

    # Release gate MUST fail loudly and identify Scene 002
    val_res = Stage8FinalValidator.execute(scenes=scenes)
    assert not val_res.is_valid
    assert "Scene #002" in val_res.validation_summary
    assert "PROMPT_GENERATION_FAILED" in val_res.validation_summary


# =========================================================================
# 4. BATCH SIZES 1, 4, 8, 20 EXECUTION
# =========================================================================

@pytest.mark.parametrize("scene_count", [1, 4, 8, 20])
def test_prompt_generation_batch_sizes(scene_count):
    engine = MockInferenceEngine()
    analysis = _build_dummy_analysis()
    scenes_data = [
        (f"{i+1:03d}", f"Narration segment {i+1} detailing military movements.", f"Military action {i+1}")
        for i in range(scene_count)
    ]
    storyboard = _build_storyboard(scenes_data)

    scenes = Stage5PromptGenerator.execute(
        engine=engine,
        scheduled_storyboard=storyboard,
        analysis=analysis,
        batch_size=4  # Automatically derived to safe batches of 2
    )

    assert len(scenes) == scene_count
    for i, s in enumerate(scenes):
        assert s.scene_id == f"{i+1:03d}"
        assert len(s.prompt) > 20
        # No generic template keywords
        assert not s.prompt.startswith("Aesthetic:")
        assert "PROMPT_GENERATION_FAILED" not in (s.validation_notes or "")
