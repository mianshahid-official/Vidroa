import re
import pytest
from backend.pipeline.story_pack import StoryPackManager
from backend.pipeline.stage1_analysis import Stage1Analyzer
from app.presets.loader import PresetManager
from backend.inference.engine import MockInferenceEngine


def test_constantinople_story_auto_matched_and_logged(capsys):
    story = (
        "In 1453, the Ottoman forces under Sultan Mehmed prepared for the final siege "
        "of Constantinople against Emperor Constantine XI."
    )
    matched = StoryPackManager.match_pack(story)
    assert matched is not None
    assert matched.id == "constantinople-1453"
    captured = capsys.readouterr()
    assert "[StoryPack] story pack constantinople-1453 auto-matched on keyword" in captured.out


def test_non_history_story_has_zero_leakage():
    PresetManager.initialize()
    engine = MockInferenceEngine()
    preset = PresetManager.get_subject_by_id("general_documentary")

    zombie_script = (
        "The sirens stopped three days ago, but the chewing hasn't. "
        "From the attic vent the world looks gray and jittery like a corrupted broadcast. "
        "Below on Elm Street they wander in stuttering, lurching rhythms, guided only by the lingering memory of hunger. "
        "Light attracts them, so the dark is your only bedsheet. "
        "Sound carries half a mile across the dead suburbs, so canned beans are eaten cold, "
        "and every footstep across hardwood must land on the ball of the foot, rolling toward the heel. "
        "Down in the kitchen a single strip of duct tape keeps the back door handle from rattling against the jam."
    )

    # 1. Ensure story pack match is None
    pack = StoryPackManager.match_pack(zombie_script)
    assert pack is None

    # 2. Run Stage 1 Analysis
    analysis = Stage1Analyzer.execute(engine, zombie_script, preset)

    # Convert to combined text representation
    combined_text = (
        f"{analysis.story_summary} "
        f"{' '.join([c.name + ' ' + c.physical_description for c in analysis.continuity.characters])} "
        f"{' '.join([l.name + ' ' + l.environmental_features for l in analysis.continuity.locations])} "
        f"{analysis.continuity.time_period.era if analysis.continuity.time_period else ''} "
        f"{analysis.thumbnail_headline} {analysis.thumbnail_prompt}"
    ).lower()

    # Verify zero leakage of ancient siege / roman figures
    forbidden_leak_pattern = re.compile(
        r"\b(constantinople|mehmed|caesar|cannon|bombard|theodosian|curia|brutus|cimber|1453|ottoman|byzantine)\b",
        re.IGNORECASE
    )
    matches = forbidden_leak_pattern.findall(combined_text)
    assert len(matches) == 0, f"Found leaked story-specific tokens in non-history story: {matches}"
