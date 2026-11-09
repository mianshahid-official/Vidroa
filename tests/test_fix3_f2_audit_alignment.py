"""
Phase 2 Tests: Fix 3 (F2) — Real Narration <-> Prompt Alignment Audit & Stage 6 Token Budget.
Verifies:
1. derive_stage6_audit_budget derives correct token budget at 1, 8, 20, 60 scenes and respects 950 cap.
2. Scene 007 regression: doors narration with mattress prompt is flagged as mismatch with scene repair and score <= 74.
3. Controls: properly matched scenes (infantry, archers, battering ram) are NOT flagged.
4. Auditor prompt feed contains full narration (> 70 chars) and >= 300 chars of prompt.
5. LLM-suggested scene repairs survive merge on their own merits (no has_issue gate).
"""
import json
import pytest
from app.models.planning import (
    ScriptAnalysis,
    ContinuityBible,
    CharacterEntity,
    LocationEntity,
    PlanningConstraints,
    TemporalCausalStructure
)
from app.models.scene import VisualScene
from backend.inference.engine import BaseInferenceEngine
from backend.pipeline.stage6_audit import (
    Stage6StoryboardAuditor,
    derive_stage6_audit_budget
)


class RecordingMockEngine(BaseInferenceEngine):
    def __init__(self, canned_response: dict = None):
        super().__init__()
        self.canned_response = canned_response or {
            "overall_score": 95.0,
            "category_scores": {
                "narration_alignment": 95.0,
                "visual_progression": 95.0,
                "temporal_pacing": 95.0,
                "continuity": 95.0,
                "style_fidelity": 95.0,
                "prompt_quality": 95.0
            },
            "repetition_findings": [],
            "timing_findings": [],
            "alignment_findings": [],
            "scene_repairs": [],
            "final_recommendation": "APPROVED"
        }
        self.last_prompt = ""
        self.last_max_tokens = 0

    def generate_text(self, prompt: str, system_prompt: str = None, temperature: float = 0.7, max_tokens: int = 1000) -> str:
        self.last_prompt = prompt
        self.last_max_tokens = max_tokens
        return json.dumps(self.canned_response)

    def repair_and_parse_json(self, raw_text: str) -> dict:
        try:
            return json.loads(raw_text)
        except Exception:
            return dict(self.canned_response)


def _build_dummy_analysis() -> ScriptAnalysis:
    return ScriptAnalysis(
        script_summary="General historical narrative depicting siege operations.",
        core_narrative_premise="Soldiers advancing on fortress",
        genre_and_tone="Dramatic Historical",
        setting_period="Medieval",
        continuity_bible=ContinuityBible(
            characters=[CharacterEntity(name="Commander", role="Lead", appearance="Armored knight", costume="Chainmail")],
            locations=[LocationEntity(name="Gatehouse", description="Stone gatehouse", environment_details="Mud and stone", lighting_default="Daylight", historical_or_setting_constraints="Authentic")]
        ),
        temporal_and_causal_structure=TemporalCausalStructure(chronological_order="Linear"),
        visual_planning_constraints=PlanningConstraints()
    )


def test_derive_stage6_audit_budget_scale():
    # 1 scene: base 200 + 45 = 245, clamped to min floor 450
    b1 = derive_stage6_audit_budget(1, max_cap=950)
    assert b1 == 450

    # 8 scenes: 200 + 8 * 45 = 560
    b8 = derive_stage6_audit_budget(8, max_cap=950)
    assert b8 == 560

    # 20 scenes: 200 + 20 * 45 = 1100 -> capped at 950
    b20 = derive_stage6_audit_budget(20, max_cap=950)
    assert b20 == 950

    # 60 scenes: 200 + 60 * 45 = 2900 -> capped at 950
    b60 = derive_stage6_audit_budget(60, max_cap=950)
    assert b60 == 950
    assert b60 <= 950


def test_audit_regression_scene_007_doors_narration_mattress_prompt_flagged():
    engine = RecordingMockEngine()
    analysis = _build_dummy_analysis()

    # The audit's exact defect case: narration describes doors breaking, prompt depicts a man on a mattress
    mismatched_scene = VisualScene(
        scene_id="007",
        start=24.0,
        end=28.5,
        duration=4.5,
        narration_excerpt="The double doors groaned under the iron battering ram, splinters flying as heavy hinges gave way.",
        visual_subject="Man in bedroom",
        prompt="A man lying on a worn mattress inside a dim attic bedroom, staring at the ceiling in quiet despair, soft shadow falling across bedframe.",
        composition="Medium shot"
    )

    report = Stage6StoryboardAuditor.execute(
        engine=engine,
        scenes=[mismatched_scene],
        story_text="The double doors groaned under the iron battering ram...",
        analysis=analysis
    )

    # Must be flagged as an alignment finding
    assert len(report.alignment_findings) >= 1
    mismatch_findings = [af for af in report.alignment_findings if "007" in af.scene_id and "mismatch" in af.issue.lower()]
    assert len(mismatch_findings) >= 1

    # Must generate a scene repair for 007
    repairs_007 = [sr for sr in report.scene_repairs if "007" in sr.scene_id]
    assert len(repairs_007) >= 1

    # Overall score must be capped <= 74.0 and recommendation must be NEEDS_REPAIR
    assert report.overall_score <= 74.0
    assert report.final_recommendation == "NEEDS_REPAIR"


def test_audit_controls_matched_scenes_not_flagged():
    engine = RecordingMockEngine()
    analysis = _build_dummy_analysis()

    # Valid scenes matching narration with prompt
    matched_scenes = [
        VisualScene(
            scene_id="001",
            start=0.0,
            end=4.0,
            duration=4.0,
            narration_excerpt="The infantry units advanced toward the fortified iron gates under a hail of arrows.",
            visual_subject="Infantry units advancing on city gates",
            prompt="Dramatic wide shot of armored infantry units advancing toward fortified iron gates with shields raised under hail of arrows, dust and grit.",
            composition="Wide shot"
        ),
        VisualScene(
            scene_id="002",
            start=4.0,
            end=8.0,
            duration=4.0,
            narration_excerpt="Archers positioned along the upper battlements fired coordinated volleys into the valley below.",
            visual_subject="Archers firing from battlements",
            prompt="Medium shot of archers positioned along high stone battlements drawing bows and firing arrow volleys downward.",
            composition="Medium low angle"
        ),
        VisualScene(
            scene_id="003",
            start=8.0,
            end=12.0,
            duration=4.0,
            narration_excerpt="A heavy timber battering ram slammed repeatedly into the reinforced portcullis.",
            visual_subject="Battering ram hitting portcullis",
            prompt="Close-up tracking perspective of heavy timber battering ram impacting reinforced iron portcullis with sparks and wood debris.",
            composition="Close-up dynamic"
        )
    ]

    report = Stage6StoryboardAuditor.execute(
        engine=engine,
        scenes=matched_scenes,
        story_text="The infantry units advanced toward the fortified iron gates...",
        analysis=analysis
    )

    # Controls must have zero alignment findings and zero repairs
    assert len(report.alignment_findings) == 0
    assert len(report.scene_repairs) == 0
    assert report.overall_score >= 85.0
    assert report.final_recommendation == "APPROVED"


def test_audit_feed_contains_full_narration_and_over_300_chars_prompt():
    engine = RecordingMockEngine()
    analysis = _build_dummy_analysis()

    long_narration = "The vanguard crossed the frozen river before dawn while engineers constructed defensive palisades along the ridge to repel enemy cavalry."
    long_prompt = (
        "A highly detailed cinematic shot depicting armored medieval soldiers crossing a freezing winter river "
        "at daybreak, ice floating along murky current, heavy vapor rising from soldiers' breaths as engineers assemble "
        "timber fortification beams in background under cold grey sky with atmospheric lighting and mist."
    )
    assert len(long_narration) > 100
    assert len(long_prompt) > 300

    scene = VisualScene(
        scene_id="001",
        start=0.0,
        end=5.0,
        duration=5.0,
        narration_excerpt=long_narration,
        visual_subject="Soldiers crossing river at dawn",
        prompt=long_prompt,
        composition="Wide establishing shot"
    )

    Stage6StoryboardAuditor.execute(
        engine=engine,
        scenes=[scene],
        story_text=long_narration,
        analysis=analysis
    )

    captured_prompt = engine.last_prompt
    # Must contain full narration without truncation to 70 chars
    assert f'Spoken: "{long_narration}"' in captured_prompt
    # Must contain at least 300 characters of prompt
    assert long_prompt[:300] in captured_prompt


def test_llm_suggested_repairs_survive_without_deterministic_finding():
    # LLM suggests repair for scene 002 even though 002 has no deterministic finding
    llm_response = {
        "overall_score": 90.0,
        "category_scores": {
            "narration_alignment": 90.0,
            "visual_progression": 90.0,
            "temporal_pacing": 90.0,
            "continuity": 90.0,
            "style_fidelity": 90.0,
            "prompt_quality": 90.0
        },
        "repetition_findings": [],
        "timing_findings": [],
        "alignment_findings": [],
        "scene_repairs": [
            {
                "scene_id": "002",
                "problem": "Pacing feels slightly stagnant",
                "required_change": "Introduce more dynamic movement",
                "suggested_visual_direction": "Zoom in on commander's tactical hand signal"
            }
        ],
        "final_recommendation": "APPROVED"
    }
    engine = RecordingMockEngine(canned_response=llm_response)
    analysis = _build_dummy_analysis()

    matched_scene_1 = VisualScene(
        scene_id="001",
        start=0.0,
        end=4.0,
        duration=4.0,
        narration_excerpt="The soldiers advanced across the field.",
        visual_subject="Soldiers advancing across field",
        prompt="Soldiers advancing across open field with armor glistening.",
        composition="Wide"
    )
    matched_scene_2 = VisualScene(
        scene_id="002",
        start=4.0,
        end=8.0,
        duration=4.0,
        narration_excerpt="The commander observed the enemy formation from the hilltop.",
        visual_subject="Commander observing enemy formation",
        prompt="Commander on hilltop observing enemy formation through telescope.",
        composition="Medium"
    )

    report = Stage6StoryboardAuditor.execute(
        engine=engine,
        scenes=[matched_scene_1, matched_scene_2],
        story_text="The soldiers advanced...",
        analysis=analysis
    )

    # Even though scene 002 had no deterministic alignment or repetition finding,
    # the LLM-suggested repair must survive into report.scene_repairs
    repairs_002 = [sr for sr in report.scene_repairs if "002" in sr.scene_id]
    assert len(repairs_002) == 1
    assert "commander's tactical hand signal" in repairs_002[0].suggested_visual_direction
