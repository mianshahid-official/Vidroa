"""
Regression and verification test suite for Defect C:
Stage 3 dynamic length-based token budget (1 beat per request), inter-request pacing,
and Groq rate-limit key management.

Verifies:
1. Dynamic budget unit test: derive_stage3_token_budget sizes budget based on actual unit text
   (80 scaffolding + 230 fixed beat tokens + segment cost), never exceeding effective cap.
2. Regression test with real transcript (Sixty_people_were_locked_inside):
   Asserts 1 UNIT per prompt, 'Plan exactly 1 distinct visual beat', budgets each >= unit need.
3. Persistently-truncating mock test: 1-beat call truncates twice -> RuntimeError naming the unit.
4. UNIT-33 fixture test: Exact text from real story plans cleanly with full segment echo.
5. Pacing tests with mocked time:
   - Two consecutive generate_text calls spaced >= 2s.
   - A 5s 429 wait satisfies pacing with no extra sleep.
6. Key-wait tests with mocked 429:
   - Retry-After: 2s (<= 3.0s) -> same key retried after wait without rotation.
   - Retry-After: 10s (> 3.0s) -> key marked on cooldown and rotated to next key (no 10s sleep).
   - Unparseable wait -> rotated to next key.
7. Effective-cap memory and decay test (using standard OTPM cap values, no 530).
"""
import json
import math
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
from app.ai.groq_engine import GroqEngine, GroqMultiKeyManager, REQUEST_PACING_SECONDS, parse_groq_retry_after
from backend.pipeline.stage3_visual_planning import (
    Stage3VisualPlanner,
    derive_stage3_token_budget,
    FIXED_BEAT_TOKENS,
    JSON_SCAFFOLDING_TOKENS
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
# 1. DYNAMIC BUDGET UNIT TESTS (LONG UNIT VS SHORT UNIT)
# =========================================================================

def test_stage3_dynamic_budget_sizing():
    """
    Verifies that derive_stage3_token_budget computes from actual unit text:
    budget = 80 scaffolding + 230 FIXED_BEAT_TOKENS + ceil(words * 1.33),
    clamped to max_cap with floor at min(350, max_cap).
    """
    assert FIXED_BEAT_TOKENS == 230
    assert JSON_SCAFFOLDING_TOKENS == 80

    # Short unit (10 words): 80 + 230 + ceil(10*1.33)=14 -> 324 -> clamped to floor 350
    short_text = "The vanguard crossed the frozen river quietly under morning mist."
    assert derive_stage3_token_budget(short_text, max_cap=950) == 350

    # Medium unit (35 words): 80 + 230 + ceil(35*1.33)=47 -> 357 tokens
    medium_text = " ".join(["word"] * 35)
    assert derive_stage3_token_budget(medium_text, max_cap=950) == 357

    # UNIT-33 real text (54 words): 80 + 230 + ceil(54*1.33)=72 -> 382 tokens
    unit_33_text = (
        "But the second floor is untouched. Your barricades held. The cost is real. "
        "The herd swept through the pharmacy and the hidden cache is gone. The roof catchment is gone. "
        "Miller cannot put weight on his leg. You count what is left on the yellow notepad, 44 ,000 calories and 47 gallons of water."
    )
    assert len(unit_33_text.split()) == 54
    assert derive_stage3_token_budget(unit_33_text, max_cap=950) == 382

    # Clamped to effective cap when cap is lower than requirement
    assert derive_stage3_token_budget(unit_33_text, max_cap=370) == 370
    assert derive_stage3_token_budget(unit_33_text, max_cap=300) == 300


# =========================================================================
# 2. REGRESSION TEST WITH REAL STORY DATA (1 UNIT PER PROMPT)
# =========================================================================

class OneBeatRecordingEngine(BaseInferenceEngine):
    """Records prompts and budgets, returning 1 beat per unit prompt."""
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

        # Parse unit ID and text from prompt
        m = re.search(r'UNIT (UNIT-\d+): "(.*?)"', prompt, re.DOTALL)
        uid = m.group(1) if m else "UNIT-01"
        utext = m.group(2) if m else "Narration text"

        return json.dumps({
            "visual_beats": [
                {
                    "exact_narration_segment": utext,
                    "narrative_purpose": f"Visualizes story progression for {uid}",
                    "primary_visual_concept": f"Detailed concrete visual depiction for {uid} with authentic setting.",
                    "what_new_information_is_shown": f"New visual development for {uid}",
                    "composition": "Eye-level medium-wide shot",
                    "lighting_and_atmosphere": "Dramatic ambient lighting with long shadows",
                    "continuity_references": ["Shopping Mall"]
                }
            ]
        })


def test_stage3_one_beat_calls_real_story(capsys):
    """
    Loads real transcript from Sixty_people_were_locked_inside.
    Verifies that:
    1. Every Stage 3 call asks for exactly 1 unit (1 beat per request).
    2. Prompt instruction states 'Plan exactly 1 distinct visual beat'.
    3. Budgets are recorded and each is >= its unit's need.
    4. Beats parse cleanly without 'Concrete depiction of' fills.
    """
    speech_path = Path(r"D:\AntiGravity\Omnivoice\output\Sixty_people_were_locked_inside_2026-11-09_14-07-30\speech.json")
    if not speech_path.exists():
        pytest.skip("Production audio speech.json not found on disk")

    data = json.load(open(speech_path, encoding="utf-8"))
    words = [w["word"].strip() for w in data.get("words", [])]
    story_text = " ".join(words[:250])  # First 250 words produces ~5-6 granular units

    engine = OneBeatRecordingEngine(effective_cap=950)
    analysis = _build_test_analysis()

    plan = Stage3VisualPlanner.execute(
        engine=engine,
        story_text=story_text,
        analysis=analysis
    )

    captured = capsys.readouterr()

    # Old batching errors must NOT appear
    assert "Parsed 1 beats, expected 2" not in captured.out
    assert "Parsed 1 beats, expected 3" not in captured.out

    # 1. Exactly 1 UNIT per prompt
    assert len(engine.call_prompts) >= 4
    for p, b in zip(engine.call_prompts, engine.call_budgets):
        assert "Plan exactly 1 distinct visual beat" in p
        assert p.count("UNIT UNIT-") == 1
        # Extract unit text and assert budget covers unit need
        m = re.search(r'UNIT UNIT-\d+: "(.*?)"', p, re.DOTALL)
        if m:
            unit_text = m.group(1)
            expected_budget = derive_stage3_token_budget(unit_text, max_cap=950)
            assert b == expected_budget

    # 2. All beats generated cleanly without fallback fill
    assert len(plan.visual_beats) >= len(engine.call_prompts)
    for beat in plan.visual_beats:
        assert beat.beat_id.startswith("VB-")
        assert "Concrete depiction of" not in beat.primary_visual_concept


# =========================================================================
# 3. PERSISTENTLY-TRUNCATING MOCK TEST (FAIL LOUDLY AFTER RETRY)
# =========================================================================

class AlwaysTruncatingEngine(BaseInferenceEngine):
    """Simulates Groq output truncating mid-stream on every call."""
    def __init__(self):
        super().__init__()
        self.call_count = 0

    def generate_text(self, prompt: str, system_prompt: str = None, temperature: float = 0.7, max_tokens: int = 1000) -> str:
        self.call_count += 1
        return '{"visual_beats": [{"exact_narration_segment": "Cut off mid-'

    def repair_and_parse_json(self, raw_text: str) -> dict:
        return {"visual_beats": []}


def test_stage3_persistently_truncating_mock_fails_loudly_naming_unit():
    """
    Proves that when a 1-beat call truncates twice (initial + 1 retry), it fails
    loudly with RuntimeError naming the offending unit (F5 pattern), with no silent fill.
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
    assert "Stage 3 planning failure" in err_msg
    assert "UNIT-01" in err_msg
    assert "output truncated or incomplete after retry" in err_msg
    # Attempt 1 + Attempt 2 = exactly 2 calls for UNIT-01 before failure
    assert engine.call_count == 2


# =========================================================================
# 4. UNIT-33 EXACT FIXTURE TEST (54-WORD NARRATION SEGMENT)
# =========================================================================

class Unit33EchoEngine(BaseInferenceEngine):
    """Echoes full long narration segment for UNIT-33."""
    def __init__(self):
        super().__init__()
        self.recorded_budgets = []

    def generate_text(self, prompt: str, system_prompt: str = None, temperature: float = 0.7, max_tokens: int = 1000) -> str:
        self.recorded_budgets.append(max_tokens)
        m = re.search(r'UNIT (UNIT-\d+): "(.*?)"', prompt, re.DOTALL)
        utext = m.group(2) if m else "Narration text"
        return json.dumps({
            "visual_beats": [
                {
                    "exact_narration_segment": utext,
                    "narrative_purpose": "Depicts grim tactical aftermath and supply audit on the second floor.",
                    "primary_visual_concept": "Weary survivor sitting at makeshift desk in dim sporting goods store counting supply tallies on yellow legal notepad.",
                    "what_new_information_is_shown": "Supply inventory reduced to 44,000 calories and Miller is injured",
                    "composition": "Medium shot with deep staging",
                    "lighting_and_atmosphere": "Low flickering emergency lighting casting long shadows across barricades",
                    "continuity_references": ["Sporting Goods Store", "Miller", "Yellow Notepad"]
                }
            ]
        })


def test_stage3_unit_33_real_story_fixture_clean_planning():
    """
    Verifies that UNIT-33 from Sixty_people_were_locked_inside (54 words):
    1. Derives dynamic budget sufficient for full segment echo (382 tokens).
    2. Plans cleanly in 1 attempt without truncation or silent fill.
    """
    speech_path = Path(r"D:\AntiGravity\Omnivoice\output\Sixty_people_were_locked_inside_2026-11-09_14-07-30\speech.json")
    if not speech_path.exists():
        pytest.skip("Production audio speech.json not found on disk")

    data = json.load(open(speech_path, encoding="utf-8"))
    words = [w["word"].strip() for w in data.get("words", [])]
    full_text = " ".join(words)
    idx = full_text.find("But the second floor is untouched")
    assert idx != -1

    unit_33_text = (
        "But the second floor is untouched. Your barricades held. The cost is real. "
        "The herd swept through the pharmacy and the hidden cache is gone. The roof catchment is gone. "
        "Miller cannot put weight on his leg. You count what is left on the yellow notepad, 44 ,000 calories and 47 gallons of water."
    )
    analysis = _build_test_analysis()
    engine = Unit33EchoEngine()

    unit_fixture = {
        "unit_id": "UNIT-33",
        "text": unit_33_text,
        "source_beat_ids": ["BEAT-033"]
    }

    beat = Stage3VisualPlanner._plan_single_unit(
        engine=engine,
        unit=unit_fixture,
        beat_number=33,
        allow_fill=False
    )

    # 1. Budget allocated was dynamically derived based on unit length (382 tokens)
    assert len(engine.recorded_budgets) == 1
    assert engine.recorded_budgets[0] == 382
    # 2. Beat parsed cleanly in 1 attempt without silent fill
    assert beat is not None
    assert beat.exact_narration_segment == unit_33_text
    assert "Weary survivor sitting at makeshift desk" in beat.primary_visual_concept
    assert "Concrete depiction of" not in beat.primary_visual_concept


# =========================================================================
# 5. PACING TESTS: MINIMUM 2-SECOND GAP BETWEEN REQUESTS
# =========================================================================

def test_groq_engine_pacing_two_consecutive_calls():
    """
    Verifies that two consecutive generate_text calls enforce a minimum 2-second gap.
    The second immediate call sleeps for the remaining time to reach 2.0s.
    """
    km = GroqMultiKeyManager(keys=["gsk_key1_AAAAAA"])
    engine = GroqEngine(key_manager=km)

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {"choices": [{"message": {"content": "Response"}}]}

    current_mock_time = 100.0

    def mock_monotonic():
        return current_mock_time

    def mock_sleep(sec):
        nonlocal current_mock_time
        current_mock_time += sec

    with patch("httpx.Client") as mock_client_cls, \
         patch("time.monotonic", side_effect=mock_monotonic), \
         patch("time.sleep", side_effect=mock_sleep) as tracked_sleep:

        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.post.return_value = resp_200

        # Call 1: initial last_request_time is 0.0, elapsed = 100.0 >= 2.0 -> no pacing sleep
        res1 = engine.generate_text("Prompt 1")
        assert res1 == "Response"
        assert tracked_sleep.call_count == 0

        # Call 2 immediately (elapsed = 0.0 < 2.0 -> sleeps 2.0s)
        res2 = engine.generate_text("Prompt 2")
        assert res2 == "Response"
        assert tracked_sleep.call_count == 1
        assert tracked_sleep.call_args[0][0] == 2.0


def test_groq_engine_pacing_satisfied_by_wait():
    """
    Verifies that if a 429 wait or cooldown wait already elapsed >= 2.0s,
    the pacing check is satisfied and adds NO extra sleep.
    """
    km = GroqMultiKeyManager(keys=["gsk_key1_AAAAAA"])
    engine = GroqEngine(key_manager=km)

    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.headers = {"retry-after": "2.5"}  # <= 3.0s -> same key retry
    resp_429.text = '{"error": {"message": "Rate limit reached. Please try again in 2.5s."}}'

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {"choices": [{"message": {"content": "Success after wait"}}]}

    current_mock_time = 100.0

    def mock_monotonic():
        return current_mock_time

    def mock_sleep(sec):
        nonlocal current_mock_time
        current_mock_time += sec

    with patch("httpx.Client") as mock_client_cls, \
         patch("time.monotonic", side_effect=mock_monotonic), \
         patch("time.sleep", side_effect=mock_sleep) as tracked_sleep:

        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.post.side_effect = [resp_429, resp_200]

        res = engine.generate_text("Test prompt")
        assert res == "Success after wait"

        # The 2.5s 429 wait was slept; pacing elapsed is 2.5s >= 2.0s so no extra pacing sleep occurred!
        assert tracked_sleep.call_count == 1
        assert tracked_sleep.call_args[0][0] == 2.5


# =========================================================================
# 6. KEY WAIT RULE TESTS: 429 HANDLING IN GROQ ENGINE
# =========================================================================

def test_parse_groq_retry_after():
    """Verifies retry-after parsing from headers and text bodies."""
    assert parse_groq_retry_after(text="Please try again in 1.8s.") == 1.8
    assert parse_groq_retry_after(text="try again in 500ms") == 0.5
    assert parse_groq_retry_after(text="try again in 12.7s") == 12.7

    assert parse_groq_retry_after(headers={"retry-after": "2.5"}) == 2.5
    assert parse_groq_retry_after(headers={"Retry-After": "10"}) == 10.0
    assert parse_groq_retry_after(headers={"x-ratelimit-reset-requests": "1.5s"}) == 1.5

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

    current_mock_time = 100.0

    def mock_monotonic():
        return current_mock_time

    def mock_sleep(sec):
        nonlocal current_mock_time
        current_mock_time += sec

    with patch("httpx.Client") as mock_client_cls, \
         patch("time.monotonic", side_effect=mock_monotonic), \
         patch("time.sleep", side_effect=mock_sleep) as mock_sleep:

        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.post.side_effect = [resp_429, resp_200]

        res = engine.generate_text("Test prompt")
        assert res == "Success after wait"

        # Assert time.sleep was called with 2.0s for the rate-limit wait
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
    Engine marks key on cooldown and rotates to the NEXT key in the pool (no 10s sleep).
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

    time_values = [100.0, 100.0, 103.0, 103.0]
    time_idx = 0

    def mock_monotonic():
        nonlocal time_idx
        v = time_values[min(time_idx, len(time_values) - 1)]
        time_idx += 1
        return v

    with patch("httpx.Client") as mock_client_cls, \
         patch("time.monotonic", side_effect=mock_monotonic), \
         patch("time.sleep") as mock_sleep:

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

    time_values = [100.0, 100.0, 103.0, 103.0]
    time_idx = 0

    def mock_monotonic():
        nonlocal time_idx
        v = time_values[min(time_idx, len(time_values) - 1)]
        time_idx += 1
        return v

    with patch("httpx.Client") as mock_client_cls, \
         patch("time.monotonic", side_effect=mock_monotonic), \
         patch("time.sleep") as mock_sleep:

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
# 7. EFFECTIVE-CAP TEST: ENGINE MEMORY AND DECAY (STANDARD VALUES)
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

    # Stage 3 derives from this effective cap
    stage3_budget = derive_stage3_token_budget("Unit text with words", max_cap=engine.current_effective_max_tokens())
    assert stage3_budget <= 750

    # Simulate 30s elapsed (still within 60s recovery interval)
    engine._effective_cap_timestamp = time.time() - 30.0
    assert engine.current_effective_max_tokens(baseline=950) == 750

    # Simulate 65s elapsed (exceeded 60s recovery interval)
    engine._effective_cap_timestamp = time.time() - 65.0
    assert engine.current_effective_max_tokens(baseline=950) == 950
