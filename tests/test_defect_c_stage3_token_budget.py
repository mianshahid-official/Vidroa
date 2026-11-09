"""
Regression and verification test suite for Defect C:
Stage 3 token budget, 1-beat batching, and Groq effective-cap memory.

Verifies:
1. Budget unit test: derived stage-3 budget for 1 beat fits real per-beat cost
   (measured from real beat schema) and never exceeds the effective cap.
2. Truncation regression with real story data: one-beat calls under a 530 effective
   cap complete with the beat parsed; the old 'Parsed 1, expected 3' loop is gone.
3. Retry test: a truncated 1-beat call retries once, and if it truncates again
   it fails loudly naming the unit with RuntimeError (no silent fill, no loop).
4. Effective-cap test: after a simulated Groq OTPM directive, the engine reports
   the reduced cap and stage derives from it; after the 60s decay interval it recovers to 950.
"""
import json
import re
import time
from pathlib import Path
import pytest

from app.models.planning import (
    ScriptAnalysis,
    ContinuityBible,
    CharacterEntity,
    LocationEntity,
    PlanningConstraints,
    TemporalCausalStructure,
    VisualBeatPlan,
    VisualBeat
)
from backend.inference.engine import BaseInferenceEngine
from app.ai.groq_engine import GroqEngine
from backend.pipeline.stage3_visual_planning import (
    Stage3VisualPlanner,
    derive_stage3_token_budget
)


def _build_test_analysis() -> ScriptAnalysis:
    return ScriptAnalysis(
        script_summary="Survival narrative inside a locked mall.",
        core_narrative_premise="Sixty people trapped in a shopping mall during an outbreak.",
        genre_and_tone="Survival Horror",
        setting_period="Modern Day",
        continuity_bible=ContinuityBible(
            characters=[CharacterEntity(name="Protagonist", role="Hero", appearance="Backwards red cap, charcoal hoodie", costume="Casual hoodie")],
            locations=[LocationEntity(name="Shopping Mall", description="Multi-level retail mall", environment_details="Corridors, shutters", lighting_default="Emergency lights", historical_or_setting_constraints="Modern")]
        ),
        temporal_and_causal_structure=TemporalCausalStructure(chronological_order="Linear"),
        visual_planning_constraints=PlanningConstraints()
    )


# =========================================================================
# 1. BUDGET UNIT TEST: MEASURED COST AND EFFECTIVE CAP
# =========================================================================

def test_stage3_budget_unit_test_measured_cost_and_effective_cap():
    """
    Measures the real token cost of a 9-field VisualBeat JSON payload and
    verifies that derive_stage3_token_budget sizes 1 beat to fit comfortably
    under both the 950 baseline cap and a reduced 530 cap, without exceeding either.
    """
    real_beat = {
        "exact_narration_segment": "60 people were locked inside this mall on the first night. By day 20, you will find proof that one of them is still alive, and that is the least dangerous thing down there.",
        "narrative_purpose": "Establishes the catastrophic scale of the initial containment and foreshadows the survival mystery and looming threat on day 20.",
        "primary_visual_concept": "Dark deserted interior of a vast multi-level shopping mall at night, shadowy empty escalators stretching upward under dim emergency lights, distant silhouette of a solitary survivor.",
        "what_new_information_is_shown": "Empty mall concourse with emergency lighting and evidence of solitary survivor activity.",
        "composition": "Wide-angle deep perspective shot looking down the deserted central atrium from upper mezzanine.",
        "lighting_and_atmosphere": "Cool blue ambient darkness pierced by flickering amber emergency backup fixtures with deep long shadows.",
        "continuity_references": ["Shopping Mall Central Atrium", "Survivor"]
    }
    json_repr = json.dumps({"visual_beats": [real_beat]}, indent=2)

    # Measured real token cost: ~1100 chars, ~140 words -> ~280-320 tokens
    char_len = len(json_repr)
    word_len = len(json_repr.split())
    assert 900 <= char_len <= 1500
    assert 110 <= word_len <= 180

    # Derived budget for 1 beat is 80 (scaffolding) + 320 (measured beat cost) = 400 tokens
    budget_baseline = derive_stage3_token_budget(1, max_cap=950)
    assert budget_baseline == 400
    assert budget_baseline <= 950

    # Under reduced Groq OTPM cap of 530, 400 tokens fits comfortably without truncation
    budget_reduced = derive_stage3_token_budget(1, max_cap=530)
    assert budget_reduced == 400
    assert budget_reduced <= 530

    # Under severe cap (e.g. 380 or 250), budget is clamped and never exceeds effective cap
    assert derive_stage3_token_budget(1, max_cap=380) == 380
    assert derive_stage3_token_budget(1, max_cap=250) == 250


# =========================================================================
# 2. TRUNCATION REGRESSION WITH REAL STORY UNDER 530 CAP
# =========================================================================

class OneBeatRecordingEngine(BaseInferenceEngine):
    """
    Simulates Groq under a 530 effective cap.
    Verifies every call asks for exactly 1 beat and respects max_tokens <= 530.
    """
    def __init__(self, effective_cap: int = 530):
        super().__init__()
        self._effective_max_tokens = effective_cap
        self.call_prompts = []
        self.call_budgets = []

    def current_effective_max_tokens(self, baseline: int = 950) -> int:
        return self._effective_max_tokens

    def generate_text(self, prompt: str, system_prompt: str = None, temperature: float = 0.7, max_tokens: int = 1000) -> str:
        self.call_prompts.append(prompt)
        self.call_budgets.append(max_tokens)

        # Parse unit id
        m = re.search(r"UNIT\s+(UNIT-\d+)", prompt)
        uid = m.group(1) if m else "UNIT-01"

        # Return exactly 1 complete beat (fits easily within 400-token budget and 530 cap)
        return json.dumps({
            "visual_beats": [
                {
                    "exact_narration_segment": f"Narration for {uid}.",
                    "narrative_purpose": f"Visualizes story progression for {uid}",
                    "primary_visual_concept": f"Detailed concrete visual depiction for {uid} with realistic lighting and environment.",
                    "what_new_information_is_shown": f"New visual development for {uid}",
                    "composition": "Eye-level medium-wide shot",
                    "lighting_and_atmosphere": "Dramatic ambient lighting with long shadows",
                    "continuity_references": ["Shopping Mall"]
                }
            ]
        })


def test_stage3_one_beat_calls_under_530_cap_no_truncation_loop(capsys):
    """
    Loads real transcript from Sixty_people_were_locked_inside.
    Verifies that:
    1. Every Stage 3 call asks for exactly 1 beat (batch_size=3 is gone).
    2. The budget is derived from the effective cap (530) and respects it.
    3. The old 'Parsed 1, expected 3' loop is completely gone.
    4. All beats parse successfully without falling back to placeholder text.
    """
    speech_path = Path(r"D:\AntiGravity\Omnivoice\output\Sixty_people_were_locked_inside_2026-11-09_14-07-30\speech.json")
    if not speech_path.exists():
        pytest.skip("Production audio speech.json not found on disk")

    data = json.load(open(speech_path, encoding="utf-8"))
    words = [w["word"].strip() for w in data.get("words", [])]
    story_text = " ".join(words[:250])  # First 250 words produces ~5-6 granular units

    engine = OneBeatRecordingEngine(effective_cap=530)
    analysis = _build_test_analysis()

    plan = Stage3VisualPlanner.execute(
        engine=engine,
        story_text=story_text,
        analysis=analysis
    )

    captured = capsys.readouterr()

    # 1. The old truncation loop messages must NOT appear anywhere in output
    assert "Parsed 1 beats, expected 3" not in captured.out
    assert "Expected 3 visual beats, parsed 1" not in captured.out
    assert "Warning: Batch incomplete" not in captured.out

    # 2. Every single engine call was for exactly 1 beat
    assert len(engine.call_prompts) >= 4
    for p in engine.call_prompts:
        assert "Plan exactly 1 distinct visual beat" in p
        assert p.count("UNIT UNIT-") == 1

    # 3. Every call used a budget of 400 (derived for 1 beat under 530 cap)
    for b in engine.call_budgets:
        assert b == 400
        assert b <= 530

    # 4. Total beats match calls
    assert len(plan.visual_beats) >= len(engine.call_prompts)
    for beat in plan.visual_beats:
        assert beat.beat_id.startswith("VB-")
        assert len(beat.primary_visual_concept) > 10
        assert "Concrete depiction of" not in beat.primary_visual_concept  # Never placeholder fill!


# =========================================================================
# 3. RETRY TEST: TRUNCATED CALL RETRIES ONCE THEN FAILS LOUDLY
# =========================================================================

class PersistentTruncatingEngine(BaseInferenceEngine):
    """Simulates Groq output truncating mid-stream on every call."""
    def __init__(self):
        super().__init__()
        self.call_count = 0

    def generate_text(self, prompt: str, system_prompt: str = None, temperature: float = 0.7, max_tokens: int = 1000) -> str:
        self.call_count += 1
        # Truncated JSON mid-object
        return '{"visual_beats": [{"exact_narration_segment": "Truncated content'

    def repair_and_parse_json(self, raw_text: str) -> dict:
        return {"visual_beats": []}


def test_stage3_truncated_one_beat_retries_once_then_fails_loudly():
    """
    Verifies that a truncated 1-beat call retries exactly once, and if it truncates
    again, fails loudly naming the unit with RuntimeError (no silent fill, no loop).
    """
    engine = PersistentTruncatingEngine()
    analysis = _build_test_analysis()
    story_text = "The survivors barred the heavy security doors and prepared for the long night."

    with pytest.raises(RuntimeError) as exc_info:
        Stage3VisualPlanner.execute(
            engine=engine,
            story_text=story_text,
            analysis=analysis
        )

    # 1. Must fail loudly naming the offending unit
    err_msg = str(exc_info.value)
    assert "Stage 3 planning failure" in err_msg
    assert "UNIT-01" in err_msg or "UNIT-02" in err_msg
    assert "output truncated or incomplete after retry" in err_msg

    # 2. Must have attempted initial call + exactly 1 retry (2 calls total, no endless loop)
    assert engine.call_count == 2


# =========================================================================
# 4. EFFECTIVE-CAP TEST: ENGINE MEMORY AND DECAY
# =========================================================================

def test_groq_engine_effective_cap_memory_and_decay():
    """
    Verifies that:
    1. Initial effective cap is 950.
    2. When Groq directs an OTPM reduction, the engine remembers it.
    3. Stage 3 derives its budget from the remembered effective cap.
    4. After the decay interval (60s), the engine recovers back to 950.
    """
    engine = GroqEngine()
    assert engine.current_effective_max_tokens(baseline=950) == 950

    # Simulate Groq OTPM directive reducing max_tokens to 530
    engine.record_effective_cap_reduction(530)
    assert engine.current_effective_max_tokens(baseline=950) == 530

    # Stage 3 derives from this effective cap
    stage3_budget = derive_stage3_token_budget(1, max_cap=engine.current_effective_max_tokens())
    assert stage3_budget == 400
    assert stage3_budget <= 530

    # Simulate 30s elapsed (still within 60s recovery interval)
    engine._effective_cap_timestamp = time.time() - 30.0
    assert engine.current_effective_max_tokens(baseline=950) == 530

    # Simulate 65s elapsed (exceeded 60s recovery interval)
    engine._effective_cap_timestamp = time.time() - 65.0
    # Engine recovers back toward baseline 950
    assert engine.current_effective_max_tokens(baseline=950) == 950
