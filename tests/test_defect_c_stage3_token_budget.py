"""
Regression and verification test suite for Defect C:
Stage 3 token budget (2-beat batching with 1-beat fallback) and Groq short-delay key wait.

Verifies:
1. Budget unit test: derive_stage3_token_budget sizes 2 beats to 720 and 1 beat to 400
   under 950 baseline, never exceeding effective cap.
2. Regression test with real transcript (Sixty_people_were_locked_inside):
   Asserts 2 UNITs per prompt and 720 budgets.
3. Truncating-mock test: Proves 2-to-1 fallback completes with no silent fill and no failure.
4. Persistently-truncating mock test: Proves 1-beat retry fails loudly naming the unit.
5. Key-wait tests with mocked 429:
   - Retry-After: 2s (<= 3.0s) -> same key retried after wait without rotation.
   - Retry-After: 10s (> 3.0s) -> key marked on cooldown and rotated to next key.
   - Unparseable wait -> rotated to next key.
6. Effective-cap memory and decay test (using standard OTPM cap values).
"""
import json
import re
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
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
from app.ai.groq_engine import GroqEngine, GroqMultiKeyManager, parse_groq_retry_after
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
# 1. BUDGET UNIT TEST: 2 BEATS == 720, 1 BEAT == 400
# =========================================================================

def test_stage3_budget_unit_test():
    """
    Verifies that derive_stage3_token_budget derives:
    - 2 beats: 80 + 2 * 320 = 720 tokens at 950 baseline cap
    - 1 beat: 80 + 1 * 320 = 400 tokens at 950 baseline cap
    - 3 beats: 80 + 3 * 320 = 1040 clamped to 950 cap
    - Clamped to effective max_cap with floor at min(350, max_cap)
    """
    assert derive_stage3_token_budget(2, max_cap=950) == 720
    assert derive_stage3_token_budget(1, max_cap=950) == 400
    assert derive_stage3_token_budget(3, max_cap=950) == 950

    # Under reduced cap (e.g. 700 tokens), 2 beats is clamped to 700
    assert derive_stage3_token_budget(2, max_cap=700) == 700
    # 1 beat under 700 cap remains 400
    assert derive_stage3_token_budget(1, max_cap=700) == 400

    # Under severe cap (e.g. 350 tokens)
    assert derive_stage3_token_budget(1, max_cap=350) == 350


# =========================================================================
# 2. REGRESSION TEST WITH REAL STORY DATA (2 UNITS PER PROMPT, 720 BUDGET)
# =========================================================================

class TwoBeatRecordingEngine(BaseInferenceEngine):
    """Records prompts and budgets, returning 2 beats for 2-unit prompts."""
    def __init__(self, effective_cap: int = 950):
        super().__init__()
        self._effective_max_tokens = effective_cap
        self.call_prompts = []
        self.call_budgets = []

    def current_effective_max_tokens(self, baseline: int = 950) -> int:
        return self._effective_max_tokens

    def generate_text(self, prompt: str, system_prompt: str = None, temperature: float = 0.7, max_tokens: int = 1000) -> str:
        self.call_prompts.append(prompt)
        self.call_budgets.append(max_tokens)

        # Parse unit IDs and text from prompt
        units = re.findall(r'UNIT (UNIT-\d+): "(.*?)"', prompt)
        if not units:
            units = [("UNIT-01", "Narration text")]

        beats = []
        for uid, utext in units:
            beats.append({
                "exact_narration_segment": utext,
                "narrative_purpose": f"Visualizes story progression for {uid}",
                "primary_visual_concept": f"Detailed concrete visual depiction for {uid} with authentic setting.",
                "what_new_information_is_shown": f"New visual development for {uid}",
                "composition": "Eye-level medium-wide shot",
                "lighting_and_atmosphere": "Dramatic ambient lighting with long shadows",
                "continuity_references": ["Shopping Mall"]
            })
        return json.dumps({"visual_beats": beats})


def test_stage3_two_beat_calls_real_story(capsys):
    """
    Loads real transcript from Sixty_people_were_locked_inside.
    Verifies that:
    1. Prompts ask for 2 units per batch (batch_size=2) with 720 budget.
    2. Prompt instruction states 'Plan exactly 2 distinct visual beats'.
    3. The old 'Parsed 1 beats, expected 3' truncation loop is completely absent.
    4. Beats parse cleanly without fallback fills.
    """
    speech_path = Path(r"D:\AntiGravity\Omnivoice\output\Sixty_people_were_locked_inside_2026-11-09_14-07-30\speech.json")
    if not speech_path.exists():
        pytest.skip("Production audio speech.json not found on disk")

    data = json.load(open(speech_path, encoding="utf-8"))
    words = [w["word"].strip() for w in data.get("words", [])]
    story_text = " ".join(words[:250])  # First 250 words produces ~5-6 granular units

    engine = TwoBeatRecordingEngine(effective_cap=950)
    analysis = _build_test_analysis()

    plan = Stage3VisualPlanner.execute(
        engine=engine,
        story_text=story_text,
        analysis=analysis
    )

    captured = capsys.readouterr()

    # Old 3-beat truncation errors must NOT appear
    assert "Parsed 1 beats, expected 3" not in captured.out
    assert "Expected 3 visual beats, parsed 1" not in captured.out

    # Batches have 2 units (except possibly 1 odd tail unit)
    assert len(engine.call_prompts) >= 2
    for p, b in zip(engine.call_prompts[:-1], engine.call_budgets[:-1]):
        assert "Plan exactly 2 distinct visual beats" in p
        assert p.count("UNIT UNIT-") == 2
        assert b == 720

    # All beats generated cleanly
    assert len(plan.visual_beats) >= len(engine.call_prompts) * 2 - 1
    for beat in plan.visual_beats:
        assert beat.beat_id.startswith("VB-")
        assert "Concrete depiction of" not in beat.primary_visual_concept


# =========================================================================
# 3. TRUNCATING-MOCK TEST: 2-TO-1 FALLBACK COMPLETES WITH NO SILENT FILL
# =========================================================================

class FallbackTruncatingEngine(BaseInferenceEngine):
    """
    Truncates 2-beat batches (returns only 1 beat),
    but succeeds on 1-beat fallback calls (returns 1 beat).
    """
    def __init__(self):
        super().__init__()
        self.two_beat_calls = 0
        self.one_beat_calls = 0
        self.recorded_budgets = []

    def generate_text(self, prompt: str, system_prompt: str = None, temperature: float = 0.7, max_tokens: int = 1000) -> str:
        self.recorded_budgets.append(max_tokens)
        units = re.findall(r'UNIT (UNIT-\d+): "(.*?)"', prompt)

        if len(units) == 2:
            self.two_beat_calls += 1
            # Truncation: returns only 1 beat for a 2-unit request
            uid, utext = units[0]
            return json.dumps({
                "visual_beats": [
                    {
                        "exact_narration_segment": utext,
                        "narrative_purpose": "Incomplete batch output",
                        "primary_visual_concept": f"Concept for {uid}",
                        "what_new_information_is_shown": "Partial output",
                        "composition": "Wide shot",
                        "lighting_and_atmosphere": "Overcast",
                        "continuity_references": []
                    }
                ]
            })
        else:
            self.one_beat_calls += 1
            uid, utext = units[0] if units else ("UNIT-01", "Text")
            return json.dumps({
                "visual_beats": [
                    {
                        "exact_narration_segment": utext,
                        "narrative_purpose": f"Visualizes story progression for {uid}",
                        "primary_visual_concept": f"Complete fallback concept for {uid} under 1-beat budget.",
                        "what_new_information_is_shown": f"New development for {uid}",
                        "composition": "Medium shot",
                        "lighting_and_atmosphere": "Dramatic lighting",
                        "continuity_references": []
                    }
                ]
            })


def test_stage3_truncating_mock_2_to_1_fallback_completes_cleanly():
    """
    Proves that when a 2-beat call truncates (< 2 beats), the planner does NOT retry
    the 2-beat call and does NOT fill silently: it shrinks the pair to two 1-beat calls
    (budget 400 each), which complete successfully.
    """
    engine = FallbackTruncatingEngine()
    analysis = _build_test_analysis()
    # 2 sentences -> 2 units
    story_text = "The survivors barred the heavy security doors. Then they retreated to the second floor."

    plan = Stage3VisualPlanner.execute(
        engine=engine,
        story_text=story_text,
        analysis=analysis,
        allow_fill=False
    )

    # 1. Exactly 1 two-beat call was attempted (budget 720)
    assert engine.two_beat_calls == 1
    assert engine.recorded_budgets[0] == 720

    # 2. Shrunk to two 1-beat fallback calls (budget 400 each)
    assert engine.one_beat_calls == 2
    assert engine.recorded_budgets[1] == 400
    assert engine.recorded_budgets[2] == 400

    # 3. Both beats produced cleanly without silent fill
    assert len(plan.visual_beats) == 2
    for b in plan.visual_beats:
        assert "Complete fallback concept" in b.primary_visual_concept
        assert "Concrete depiction of" not in b.primary_visual_concept


# =========================================================================
# 4. PERSISTENTLY-TRUNCATING MOCK TEST: FAILS LOUDLY NAMING THE UNIT
# =========================================================================

class AlwaysTruncatingEngine(BaseInferenceEngine):
    """Truncates on every call (both 2-beat and 1-beat)."""
    def __init__(self):
        super().__init__()
        self.call_count = 0

    def generate_text(self, prompt: str, system_prompt: str = None, temperature: float = 0.7, max_tokens: int = 1000) -> str:
        self.call_count += 1
        # Incomplete / unparseable JSON
        return '{"visual_beats": [{"exact_narration_segment": "Cut off mid-'

    def repair_and_parse_json(self, raw_text: str) -> dict:
        return {"visual_beats": []}


def test_stage3_persistently_truncating_mock_fails_loudly_naming_unit():
    """
    Proves that when a 1-beat fallback call still truncates, it fails loudly
    with RuntimeError naming the offending unit (F5 pattern), with no silent fill.
    """
    engine = AlwaysTruncatingEngine()
    analysis = _build_test_analysis()
    story_text = "The survivors barred the heavy security doors. Then they retreated to the second floor."

    with pytest.raises(RuntimeError) as exc_info:
        Stage3VisualPlanner.execute(
            engine=engine,
            story_text=story_text,
            analysis=analysis,
            allow_fill=False
        )

    err_msg = str(exc_info.value)
    # Must fail loudly naming the unit and 1-beat fallback
    assert "Stage 3 planning failure" in err_msg
    assert "UNIT-01" in err_msg
    assert "1-beat fallback retry" in err_msg


# =========================================================================
# 5. KEY WAIT RULE TESTS: 429 HANDLING IN GROQ ENGINE
# =========================================================================

def test_parse_groq_retry_after():
    """Verifies retry-after parsing from headers and text bodies."""
    # From body text
    assert parse_groq_retry_after(text="Please try again in 1.8s.") == 1.8
    assert parse_groq_retry_after(text="try again in 500ms") == 0.5
    assert parse_groq_retry_after(text="try again in 12.7s") == 12.7

    # From headers
    assert parse_groq_retry_after(headers={"retry-after": "2.5"}) == 2.5
    assert parse_groq_retry_after(headers={"Retry-After": "10"}) == 10.0
    assert parse_groq_retry_after(headers={"x-ratelimit-reset-requests": "1.5s"}) == 1.5

    # Unparseable returns None
    assert parse_groq_retry_after(headers={}, text="Generic rate limit message.") is None
    assert parse_groq_retry_after() is None


def test_groq_engine_short_wait_retries_same_key():
    """
    When Groq returns HTTP 429 with requested wait <= 3.0s:
    Engine sleeps and retries the SAME API key without marking cooldown or rotating.
    """
    km = GroqMultiKeyManager(keys=["gsk_key1_AAAAAA", "gsk_key2_BBBBBB"])
    engine = GroqEngine(key_manager=km)

    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.headers = {"retry-after": "2.0"}
    resp_429.text = '{"error": {"message": "Rate limit reached. Please try again in 2.0s."}}'

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {"choices": [{"message": {"content": "Success after wait"}}]}

    with patch("httpx.Client") as mock_client_cls, patch("time.sleep") as mock_sleep:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.post.side_effect = [resp_429, resp_200]

        res = engine.generate_text("Test prompt")
        assert res == "Success after wait"

        # Assert time.sleep was called with 2.0s
        mock_sleep.assert_called_once_with(2.0)

        # Assert post was called twice, BOTH times with the SAME key (key1)
        assert mock_client.post.call_count == 2
        first_call_auth = mock_client.post.call_args_list[0][1]["headers"]["Authorization"]
        second_call_auth = mock_client.post.call_args_list[1][1]["headers"]["Authorization"]
        assert first_call_auth == "Bearer gsk_key1_AAAAAA"
        assert second_call_auth == "Bearer gsk_key1_AAAAAA"


def test_groq_engine_long_wait_rotates_key():
    """
    When Groq returns HTTP 429 with requested wait > 3.0s:
    Engine marks key on cooldown and rotates to the NEXT key in the pool.
    """
    km = GroqMultiKeyManager(keys=["gsk_key1_AAAAAA", "gsk_key2_BBBBBB"])
    engine = GroqEngine(key_manager=km)

    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.headers = {"retry-after": "10.0"}
    resp_429.text = '{"error": {"message": "Rate limit reached. Please try again in 10.0s."}}'

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {"choices": [{"message": {"content": "Success on second key"}}]}

    with patch("httpx.Client") as mock_client_cls, patch("time.sleep") as mock_sleep:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.post.side_effect = [resp_429, resp_200]

        res = engine.generate_text("Test prompt")
        assert res == "Success on second key"

        # Should NOT sleep 10s in worker thread
        mock_sleep.assert_not_called()

        # Assert first call used key1, second call rotated to key2
        assert mock_client.post.call_count == 2
        first_call_auth = mock_client.post.call_args_list[0][1]["headers"]["Authorization"]
        second_call_auth = mock_client.post.call_args_list[1][1]["headers"]["Authorization"]
        assert first_call_auth == "Bearer gsk_key1_AAAAAA"
        assert second_call_auth == "Bearer gsk_key2_BBBBBB"


def test_groq_engine_unparseable_wait_rotates_key():
    """
    When Groq returns HTTP 429 with unparseable delay:
    Engine marks cooldown with fallback (2.0s) and rotates to the NEXT key.
    """
    km = GroqMultiKeyManager(keys=["gsk_key1_AAAAAA", "gsk_key2_BBBBBB"])
    engine = GroqEngine(key_manager=km)

    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.headers = {}
    resp_429.text = 'Rate limit exceeded.'

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {"choices": [{"message": {"content": "Success after rotation"}}]}

    with patch("httpx.Client") as mock_client_cls, patch("time.sleep") as mock_sleep:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.post.side_effect = [resp_429, resp_200]

        res = engine.generate_text("Test prompt")
        assert res == "Success after rotation"

        # Rotates key
        assert mock_client.post.call_count == 2
        first_call_auth = mock_client.post.call_args_list[0][1]["headers"]["Authorization"]
        second_call_auth = mock_client.post.call_args_list[1][1]["headers"]["Authorization"]
        assert first_call_auth == "Bearer gsk_key1_AAAAAA"
        assert second_call_auth == "Bearer gsk_key2_BBBBBB"


# =========================================================================
# 6. EFFECTIVE-CAP TEST: ENGINE MEMORY AND DECAY (STANDARD VALUES)
# =========================================================================

def test_groq_engine_effective_cap_memory_and_decay():
    """
    Verifies that:
    1. Initial effective cap is 950.
    2. When Groq directs an OTPM reduction (e.g. 750 tokens), engine remembers it.
    3. Stage 3 derives its budget from the remembered effective cap.
    4. After the decay interval (60s), the engine recovers back to 950.
    """
    engine = GroqEngine()
    assert engine.current_effective_max_tokens(baseline=950) == 950

    # Simulate Groq OTPM directive reducing max_tokens to 750
    engine.record_effective_cap_reduction(750)
    assert engine.current_effective_max_tokens(baseline=950) == 750

    # Stage 3 derives from this effective cap: 2 beats = 720 (fits under 750)
    stage3_budget = derive_stage3_token_budget(2, max_cap=engine.current_effective_max_tokens())
    assert stage3_budget == 720

    # Simulate 30s elapsed (still within 60s recovery interval)
    engine._effective_cap_timestamp = time.time() - 30.0
    assert engine.current_effective_max_tokens(baseline=950) == 750

    # Simulate 65s elapsed (exceeded 60s recovery interval)
    engine._effective_cap_timestamp = time.time() - 65.0
    assert engine.current_effective_max_tokens(baseline=950) == 950
