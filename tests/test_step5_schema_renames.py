import json
import pytest
from app.models.scene import VisualScene, StoryAnalysis
from app.models.planning import (
    ScriptAnalysis,
    ContinuityBible,
    PlanningConstraints,
    TemporalCausalStructure,
)
from backend.inference.engine import MockInferenceEngine


def test_visual_scene_confidence_and_event_aliases():
    # New schema names
    sc1 = VisualScene(
        scene_id="001",
        start=0.0,
        end=4.0,
        duration=4.0,
        visual_subject="Lighthouse on rock",
        confidence="documented",
        depicted_event="Keeper begins night watch"
    )
    assert sc1.confidence == "documented"
    assert sc1.historical_confidence == "documented"
    assert sc1.depicted_event == "Keeper begins night watch"
    assert sc1.historical_event == "Keeper begins night watch"

    # Legacy schema names via validation alias
    sc2 = VisualScene(
        scene_id="002",
        start=4.0,
        end=8.0,
        duration=4.0,
        visual_subject="Storm waves",
        historical_confidence="artistic_interpretation",
        historical_event="Storm intensifies"
    )
    assert sc2.confidence == "artistic_interpretation"
    assert sc2.historical_confidence == "artistic_interpretation"
    assert sc2.depicted_event == "Storm intensifies"
    assert sc2.historical_event == "Storm intensifies"


def test_story_analysis_major_events_and_uncertainties_aliases():
    # New names
    sa1 = StoryAnalysis(
        story_summary="Maritime tale.",
        major_events=["Arrival", "Gale", "Dawn"],
        uncertainties=["Exact wind speed"]
    )
    assert sa1.major_events == ["Arrival", "Gale", "Dawn"]
    assert sa1.major_historical_events == ["Arrival", "Gale", "Dawn"]
    assert sa1.uncertainties == ["Exact wind speed"]
    assert sa1.historical_uncertainties == ["Exact wind speed"]

    # Legacy names
    sa2 = StoryAnalysis(
        story_summary="Maritime tale.",
        major_historical_events=["Arrival", "Gale", "Dawn"],
        historical_uncertainties=["Exact wind speed"]
    )
    assert sa2.major_events == ["Arrival", "Gale", "Dawn"]
    assert sa2.major_historical_events == ["Arrival", "Gale", "Dawn"]
    assert sa2.uncertainties == ["Exact wind speed"]
    assert sa2.historical_uncertainties == ["Exact wind speed"]


def test_script_analysis_setting_period_alias():
    # New name
    sa1 = ScriptAnalysis(
        script_summary="Summary",
        core_narrative_premise="Premise",
        genre_and_tone="Tone",
        setting_period="Early 20th Century Maritime",
        continuity_bible=ContinuityBible(),
        temporal_and_causal_structure=TemporalCausalStructure(chronological_order="Linear"),
        visual_planning_constraints=PlanningConstraints()
    )
    assert sa1.setting_period == "Early 20th Century Maritime"
    assert sa1.historical_or_setting_period == "Early 20th Century Maritime"

    # Legacy name
    sa2 = ScriptAnalysis(
        script_summary="Summary",
        core_narrative_premise="Premise",
        genre_and_tone="Tone",
        historical_or_setting_period="Early 20th Century Maritime",
        continuity_bible=ContinuityBible(),
        temporal_and_causal_structure=TemporalCausalStructure(chronological_order="Linear"),
        visual_planning_constraints=PlanningConstraints()
    )
    assert sa2.setting_period == "Early 20th Century Maritime"
    assert sa2.historical_or_setting_period == "Early 20th Century Maritime"


def test_mock_inference_engine_neutral_fixtures():
    engine = MockInferenceEngine()
    raw = engine.generate_text("STAGE 1: STORY ANALYSIS for test script")
    parsed = json.loads(raw)
    assert "lighthouse" in parsed["story_summary"].lower()
    assert "ancient civilization" not in parsed["story_summary"].lower()
    assert "major_events" in parsed
    assert "uncertainties" in parsed

    # Test visual beats fixture
    prompt_vb = "VISUAL PLANNING\nUNIT 001: The wind began to roar.\nUNIT 002: He climbed the spiral stairs."
    raw_vb = engine.generate_text(prompt_vb)
    assert "spiral iron staircase" in raw_vb
    assert "ancient stone monoliths" not in raw_vb
