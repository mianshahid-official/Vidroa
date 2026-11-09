import pytest
from backend.pipeline.story_pack import StoryPackManager, sanitize_stickman_prompt
from backend.pipeline.stage1_analysis import Stage1Analyzer
from backend.pipeline.stage6_audit import Stage6StoryboardAuditor
from app.models.scene import VisualScene
from app.models.planning import (
    ScriptAnalysis,
    ContinuityBible,
    PlanningConstraints,
    TemporalCausalStructure,
)
from app.models.presets import SubjectPreset
from backend.inference.engine import BaseInferenceEngine


class MockAuditEngine(BaseInferenceEngine):
    def generate_text(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        return "{}"

    def repair_and_parse_json(self, raw_text: str) -> dict:
        return {}


def test_story_pack_discovery():
    packs = StoryPackManager.list_pack_ids()
    assert "constantinople-1453" in packs
    assert "caesar-44bc" in packs
    assert "cortes-1519" in packs
    assert "dorothea-1841" in packs

    pack_1453 = StoryPackManager.get_pack("constantinople-1453")
    assert pack_1453 is not None
    assert pack_1453.name == "Fall of Constantinople (1453)"
    assert "constantinople" in pack_1453.match_keywords


def test_story_pack_auto_match(capsys):
    story_1453 = "The final siege of Constantinople began in 1453 with giant bombards."
    matched = StoryPackManager.match_pack(story_1453)
    assert matched is not None
    assert matched.id == "constantinople-1453"
    captured = capsys.readouterr()
    assert "[StoryPack] story pack constantinople-1453 auto-matched on keyword" in captured.out

    non_history_story = "The sirens stopped three days ago, but the chewing hasn't on Elm Street."
    matched_none = StoryPackManager.match_pack(non_history_story)
    assert matched_none is None


def test_stage1_fallbacks_neutral_vs_pack():
    engine = MockAuditEngine()
    preset = SubjectPreset(
        id="general_documentary",
        name="General Documentary",
        description="General documentary",
        system_instructions="Neutral instructions"
    )
    zombie_story = "The sirens stopped three days ago, but the chewing hasn't on Elm Street."
    analysis_zombie = Stage1Analyzer.execute(engine, zombie_story, preset)
    chars = analysis_zombie.continuity.characters
    assert len(chars) > 0
    assert "Constantine" not in chars[0].name
    assert "Caesar" not in chars[0].name

    locs = analysis_zombie.continuity.locations
    assert len(locs) > 0
    assert "Theodosian" not in locs[0].name
    assert "Rome" not in locs[0].name

    period = analysis_zombie.continuity.time_period.era if analysis_zombie.continuity.time_period else ""
    assert "44 BC" not in period
    assert "1453" not in period

    # Constantinople pack test
    story_1453 = "In 1453 Constantinople faced the Ottoman fleet."
    analysis_1453 = Stage1Analyzer.execute(engine, story_1453, preset)
    chars_1453 = analysis_1453.continuity.characters
    assert any("Constantine" in c.name or "Mehmed" in c.name for c in chars_1453)


def test_stage6_audit_quarantine():
    engine = MockAuditEngine()
    analysis = ScriptAnalysis(
        script_summary="Sci-fi narrative set in year 2150.",
        core_narrative_premise="Exploration of colony worlds.",
        genre_and_tone="Sci-Fi Drama",
        historical_or_setting_period="2150 Futuristic Era",
        continuity_bible=ContinuityBible(),
        temporal_and_causal_structure=TemporalCausalStructure(chronological_order="Linear"),
        visual_planning_constraints=PlanningConstraints()
    )

    # A non-history sci-fi or post-apocalyptic scene
    scenes = [
        VisualScene(
            scene_id="1",
            index=1,
            start=0.0,
            end=4.0,
            duration=4.0,
            narration_excerpt="An astronaut walks down neon skyscrapers wearing denim in 2150.",
            visual_subject="Astronaut in denim in front of neon skyscrapers",
            prompt="An astronaut walking along futuristic neon skyscrapers in denim, sci-fi concept art."
        ),
        VisualScene(
            scene_id="2",
            index=2,
            start=4.0,
            end=7.5,
            duration=3.5,
            narration_excerpt="The sirens sounded across the colonies.",
            visual_subject="Sirens echoing across colony towers",
            prompt="Futuristic colony towers with warning lights glowing against the night."
        )
    ]

    report = Stage6StoryboardAuditor.execute(
        engine=engine,
        scenes=scenes,
        story_text="An astronaut walks down neon skyscrapers wearing denim in 2150. The sirens sounded.",
        analysis=analysis
    )

    # Verify no false-positive anachronism findings were raised for denim / neon / astronaut
    anachronism_findings = [f for f in report.alignment_findings if "anachronistic" in f.issue.lower()]
    assert len(anachronism_findings) == 0

    # Verify no Ottoman or Caesar repairs leaked in
    all_repairs_str = " ".join(r.problem + " " + r.required_change + " " + r.suggested_visual_direction for r in report.scene_repairs)
    assert "ottoman" not in all_repairs_str.lower()
    assert "caesar" not in all_repairs_str.lower()
    assert "mehmed" not in all_repairs_str.lower()
    assert "theodosian" not in all_repairs_str.lower()


def test_sanitize_stickman_prompt():
    raw = "A 3D stickman scene. Note: avoid realistic beard. strict negative: realistic skin, realistic face."
    sanitized = sanitize_stickman_prompt(raw)
    assert "strict negative:" in sanitized
