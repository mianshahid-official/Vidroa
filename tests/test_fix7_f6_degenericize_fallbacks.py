"""
Phase 5 Tests: Fix 7 (F6 + F9) — De-genericize Remaining Fallbacks & Verify F9 Quarantine.
Verifies:
1. derive_contextual_environment derives setting from narration nouns without bible match, never emitting "Authentic {period} setting".
2. Stage 3 missing beat builds concept from unit text, never emitting "Historical scene depicting ...".
3. derive_progressive_subsegment_concept extracts actual action verbs/objects, not first-5-words keyword salad.
4. F9 verification: shared code paths leak zero Roman / Caesar / Constantinople rules for non-history stories (e.g. zombie story).
"""
import pytest
from app.models.planning import (
    ScriptAnalysis,
    ContinuityBible,
    CharacterEntity,
    LocationEntity,
    PlanningConstraints,
    TemporalCausalStructure
)
from backend.inference.engine import BaseInferenceEngine
from backend.pipeline.stage5_prompts import derive_contextual_environment, Stage5PromptGenerator
from backend.pipeline.stage3_visual_planning import Stage3VisualPlanner
from backend.pipeline.stage4_scheduling import derive_progressive_subsegment_concept
from app.models.planning import ScheduledStoryboard, ScheduledScene


class MockMissingBeatEngine(BaseInferenceEngine):
    def generate_text(self, prompt: str, system_prompt: str = None, temperature: float = 0.7, max_tokens: int = 1000) -> str:
        # Intentionally returns empty visual beats to trigger Stage 3 missing-beat derivation!
        return '{"visual_beats": []}'

    def repair_and_parse_json(self, raw_text: str) -> dict:
        return {"visual_beats": []}


def test_derive_contextual_environment_narration_nouns_no_generic_template():
    analysis = ScriptAnalysis(
        script_summary="Story set in medieval era.",
        core_narrative_premise="Soldiers navigating forest",
        genre_and_tone="Dramatic",
        setting_period="12th Century Medieval",
        continuity_bible=ContinuityBible(
            characters=[],
            locations=[]  # Zero locations in bible!
        ),
        temporal_and_causal_structure=TemporalCausalStructure(chronological_order="Linear"),
        visual_planning_constraints=PlanningConstraints()
    )

    narration = "The scouting party navigated through a dense misty pine forest near the river gorge."
    env = derive_contextual_environment(narration, analysis, is_3d_stickman=False)

    # Must contain narration nouns
    assert any(noun in env.lower() for noun in ["forest", "river", "gorge", "scouting", "misty", "pine"])
    # Must NEVER be the generic template string
    assert "authentic 12th century medieval setting with atmospheric lighting" not in env.lower()
    assert "authentic setting with atmospheric lighting" not in env.lower()

    # Ungroundable narration must fail loudly
    with pytest.raises(RuntimeError) as exc_info:
        derive_contextual_environment("They were with it then and there.", analysis)
    assert "contains no groundable content nouns" in str(exc_info.value)


def test_stage3_missing_beat_concept_derived_from_unit_text():
    engine = MockMissingBeatEngine()
    analysis = ScriptAnalysis(
        script_summary="Expedition story.",
        core_narrative_premise="Expedition across tundra",
        genre_and_tone="Adventure",
        setting_period="Late 19th Century",
        continuity_bible=ContinuityBible(characters=[], locations=[]),
        temporal_and_causal_structure=TemporalCausalStructure(chronological_order="Linear"),
        visual_planning_constraints=PlanningConstraints()
    )

    story_text = "The polar explorers hauled heavy sledges across jagged glacial ridges under the howling blizzard."
    plan = Stage3VisualPlanner.execute(
        engine=engine,
        story_text=story_text,
        analysis=analysis
    )

    assert len(plan.visual_beats) >= 1
    beat = plan.visual_beats[0]

    # Concept must be grounded in unit text nouns
    concept = beat.primary_visual_concept
    assert "Historical scene depicting" not in concept
    assert "Historical scene:" not in concept
    assert any(w in concept.lower() for w in ["polar", "explorers", "sledges", "glacial", "ridges", "blizzard"])


def test_derive_progressive_subsegment_concept_extracts_action():
    base = "Armored soldiers assaulting fortified gate"
    seg_words = ["advancing", "relentlessly", "toward", "the", "massive", "iron", "portcullis"]

    concept = derive_progressive_subsegment_concept(
        base_concept=base,
        seg_words=seg_words,
        part_idx=1,
        total_parts=3
    )

    # Must include the action verb and object
    assert "advancing" in concept.lower()
    assert any(obj in concept.lower() for obj in ["portcullis", "iron", "massive"])
    # Must not be a raw 5-word slice
    assert "advancing relentlessly toward the massive" not in concept


def test_f9_zero_leakage_in_shared_code_for_non_history_story():
    # Zombie apocalypse narrative
    zombie_story = (
        "Below on Elm Street they wander in stuttering, lurching rhythms, guided only by hunger. "
        "Survivors barricaded the second-floor windows with wooden planks and sheet metal."
    )
    analysis = ScriptAnalysis(
        script_summary="Zombie survival horror story.",
        core_narrative_premise="Survivors barricade against the infected",
        genre_and_tone="Horror Survival",
        setting_period="Modern Day Post-Apocalypse",
        continuity_bible=ContinuityBible(
            characters=[CharacterEntity(name="Sarah", role="Survivor", appearance="Jeans and jacket", costume="Modern jacket")],
            locations=[LocationEntity(name="Suburban House", description="Boarded-up two-story house", environment_details="Debris and shattered glass", lighting_default="Dusk", historical_or_setting_constraints="None")]
        ),
        temporal_and_causal_structure=TemporalCausalStructure(chronological_order="Linear"),
        visual_planning_constraints=PlanningConstraints()
    )

    # Test derive_contextual_environment
    env = derive_contextual_environment(
        narration="Survivors barricaded the second-floor windows with wooden planks and sheet metal.",
        analysis=analysis,
        is_3d_stickman=False
    )
    assert not any(k in env.lower() for k in ["caesar", "rome", "constantinople", "mehmed", "byzantine", "ottoman"])

    # Test Stage 4 subsegment concept
    sub_concept = derive_progressive_subsegment_concept(
        base_concept="Survivors boarding up windows",
        seg_words=["hammering", "heavy", "timber", "across", "broken", "glass"],
        part_idx=1,
        total_parts=2
    )
    assert not any(k in sub_concept.lower() for k in ["caesar", "rome", "constantinople", "mehmed", "byzantine", "cannon"])
