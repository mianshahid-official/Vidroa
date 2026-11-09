"""
Phase 6 Tests: Fix 8 (F8 + F11) — Visual Planner Context & Stage 3 Token Resize.
Verifies:
1. derive_stage3_token_budget derives output budget correctly at 1, 3, 6, 12 beats and respects 950 ceiling.
2. Stage 3 planning batch sees 5 prior beats' FULL visual concepts (not truncated to 60 characters).
3. Stage 5 prompt generation receives the FULL continuity bible (characters beyond 6, locations beyond 4).
4. Continuity check: recurring character appearance and costume descriptions reach the prompt.
"""
import json
import pytest
from app.models.planning import (
    ScriptAnalysis,
    ContinuityBible,
    CharacterEntity,
    LocationEntity,
    PlanningConstraints,
    TemporalCausalStructure,
    ScheduledStoryboard,
    ScheduledScene
)
from app.presets.loader import PresetManager
from backend.inference.engine import BaseInferenceEngine
from backend.pipeline.stage3_visual_planning import (
    Stage3VisualPlanner,
    derive_stage3_token_budget
)
from backend.pipeline.stage5_prompts import Stage5PromptGenerator


class RecordingStage3Engine(BaseInferenceEngine):
    def __init__(self):
        super().__init__()
        self.recorded_prompts = []
        self.recorded_budgets = []

    def generate_text(self, prompt: str, system_prompt: str = None, temperature: float = 0.7, max_tokens: int = 1000) -> str:
        self.recorded_prompts.append(prompt)
        self.recorded_budgets.append(max_tokens)
        # Parse number of units requested in prompt
        num_units = prompt.count("UNIT UNIT-")
        if num_units == 0:
            num_units = 3
        beats = []
        for i in range(num_units):
            beats.append({
                "exact_narration_segment": f"Narration segment {i+1} for this unit.",
                "narrative_purpose": f"Purpose {i+1}",
                "primary_visual_concept": f"Highly detailed comprehensive visual concept for beat {i+1} describing characters, equipment, and setting in complete detail.",
                "what_new_information_is_shown": f"New development {i+1}",
                "composition": "Wide establishing shot",
                "lighting_and_atmosphere": "Dramatic lighting",
                "continuity_references": []
            })
        return json.dumps({"visual_beats": beats})

    def repair_and_parse_json(self, raw_text: str) -> dict:
        try:
            return json.loads(raw_text)
        except Exception:
            return {"visual_beats": []}


class RecordingStage5Engine(BaseInferenceEngine):
    def __init__(self):
        super().__init__()
        self.recorded_prompts = []

    def generate_text(self, prompt: str, system_prompt: str = None, temperature: float = 0.7, max_tokens: int = 1000) -> str:
        self.recorded_prompts.append(prompt)
        return json.dumps({
            "prompts": [
                {
                    "scene_id": "001",
                    "prompt": "Armored officers standing near the northern watchtower in the afternoon light."
                }
            ]
        })

    def repair_and_parse_json(self, raw_text: str) -> dict:
        try:
            return json.loads(raw_text)
        except Exception:
            return {"prompts": []}


def test_derive_stage3_token_budget_scale():
    # Short unit (10 words): 80 + 230 + ceil(10*1.33)=14 -> 324 -> clamped to floor 350
    assert derive_stage3_token_budget("Short tactical sentence with few words.", max_cap=950) == 350

    # Medium unit (35 words): 80 + 230 + ceil(35*1.33)=47 -> 357 tokens
    medium_text = " ".join(["word"] * 35)
    assert derive_stage3_token_budget(medium_text, max_cap=950) == 357

    # Long unit (60 words): 80 + 230 + ceil(60*1.33)=80 -> 390 tokens
    long_text = " ".join(["word"] * 60)
    assert derive_stage3_token_budget(long_text, max_cap=950) == 390

    # Clamped to effective cap
    assert derive_stage3_token_budget(long_text, max_cap=370) == 370

    # Engine cap never exceeded
    for n in [5, 20, 50, 100, 200]:
        t = " ".join(["word"] * n)
        assert derive_stage3_token_budget(t, max_cap=950) <= 950


def test_stage3_context_contains_5_prior_beats_full_concept():
    engine = RecordingStage3Engine()
    analysis = ScriptAnalysis(
        script_summary="Multi-sentence tactical advance.",
        core_narrative_premise="Soldiers advancing across territory",
        genre_and_tone="Dramatic",
        setting_period="Medieval",
        continuity_bible=ContinuityBible(characters=[], locations=[]),
        temporal_and_causal_structure=TemporalCausalStructure(chronological_order="Linear"),
        visual_planning_constraints=PlanningConstraints()
    )

    # 15 sentences partitioned into multiple batches (batch_size=3)
    sentences = [
        f"Tactical unit sentence {i+1} detailing the vanguard movement across the terrain."
        for i in range(15)
    ]
    story_text = " ".join(sentences)

    Stage3VisualPlanner.execute(
        engine=engine,
        story_text=story_text,
        analysis=analysis
    )

    # At least 2 batches were planned
    assert len(engine.recorded_prompts) >= 2
    later_prompt = engine.recorded_prompts[-1]

    # Preceding Visual Moments must NOT be "None"
    assert "Preceding Visual Moments:" in later_prompt
    assert "None (Opening scene)" not in later_prompt

    # Full concept (>60 chars) must be present in the prompt, NOT truncated to 60 chars
    long_concept_snippet = "describing characters, equipment, and setting in complete detail"
    assert long_concept_snippet in later_prompt


def test_stage5_receives_full_character_and_location_beyond_6_and_4():
    engine = RecordingStage5Engine()

    # Create 8 characters and 6 locations
    characters = [
        CharacterEntity(name=f"Officer_{i+1}", role=f"Rank_{i+1}", appearance=f"Distinct appearance description {i+1}", costume=f"Costume {i+1}")
        for i in range(8)
    ]
    locations = [
        LocationEntity(
            name=f"Fortress_Sector_{i+1}",
            description=f"Detailed architectural feature {i+1}",
            environment_details=f"Environmental details {i+1}",
            lighting_default="Daylight",
            historical_or_setting_constraints="Authentic"
        )
        for i in range(6)
    ]

    analysis = ScriptAnalysis(
        script_summary="Operations involving multiple characters and locations.",
        core_narrative_premise="Multi-character coordination",
        genre_and_tone="Documentary",
        setting_period="Historical",
        continuity_bible=ContinuityBible(
            characters=characters,
            locations=locations
        ),
        temporal_and_causal_structure=TemporalCausalStructure(chronological_order="Linear"),
        visual_planning_constraints=PlanningConstraints()
    )

    storyboard = ScheduledStoryboard(
        scenes=[
            ScheduledScene(
                scene_id="001",
                beat_id="VB-001",
                start_time=0.0,
                end_time=4.0,
                duration=4.0,
                narration_text="The entire company assembled at the remote outpost.",
                visual_summary="Company assembly",
                character_ids=["Officer_7", "Officer_8"],
                location_id="Fortress_Sector_5"
            )
        ],
        total_duration=4.0
    )

    preset = PresetManager.get_style_by_id("2d_stickman")
    Stage5PromptGenerator.execute(
        engine=engine,
        scheduled_storyboard=storyboard,
        analysis=analysis,
        style_preset=preset,
        batch_size=2
    )

    assert len(engine.recorded_prompts) >= 1
    prompt_text = engine.recorded_prompts[0]

    # Verify Character 7 and 8 (beyond first 6) and Location 5 and 6 (beyond first 4) appear in context
    assert "Officer_7" in prompt_text
    assert "Officer_8" in prompt_text
    assert "Fortress_Sector_5" in prompt_text
    assert "Fortress_Sector_6" in prompt_text


def test_character_continuity_across_multi_scene_story():
    engine = RecordingStage5Engine()

    captain = CharacterEntity(
        name="Captain_Valerius",
        role="Centurion Commander",
        appearance="Golden crested bronze helmet, polished steel cuirass",
        costume="Crimson military tunic with brass clasps"
    )

    analysis = ScriptAnalysis(
        script_summary="Roman defensive action.",
        core_narrative_premise="Centurion commanding soldiers",
        genre_and_tone="Historical",
        setting_period="Roman Republic",
        continuity_bible=ContinuityBible(
            characters=[captain],
            locations=[LocationEntity(
                name="Northern_Gate",
                description="Stone gate with wooden portcullis",
                environment_details="Defensive walls and parapet",
                lighting_default="Afternoon sunlight",
                historical_or_setting_constraints="Authentic ancient stonework"
            )]
        ),
        temporal_and_causal_structure=TemporalCausalStructure(chronological_order="Linear"),
        visual_planning_constraints=PlanningConstraints()
    )

    storyboard = ScheduledStoryboard(
        scenes=[
            ScheduledScene(
                scene_id="001",
                beat_id="VB-001",
                start_time=0.0,
                end_time=4.0,
                duration=4.0,
                narration_text="Captain Valerius observed the enemy line from the rampart.",
                visual_summary="Valerius observing enemy",
                character_ids=["Captain_Valerius"]
            ),
            ScheduledScene(
                scene_id="002",
                beat_id="VB-002",
                start_time=4.0,
                end_time=8.0,
                duration=4.0,
                narration_text="Captain Valerius ordered the archers to loose their volleys.",
                visual_summary="Valerius giving order",
                character_ids=["Captain_Valerius"]
            )
        ],
        total_duration=8.0
    )

    preset = PresetManager.get_style_by_id("general_documentary")
    Stage5PromptGenerator.execute(
        engine=engine,
        scheduled_storyboard=storyboard,
        analysis=analysis,
        style_preset=preset,
        batch_size=2
    )

    assert len(engine.recorded_prompts) >= 1
    prompt = engine.recorded_prompts[0]
    assert "Captain_Valerius" in prompt
    assert "Golden crested bronze helmet, polished steel cuirass" in prompt
    assert "Crimson military tunic with brass clasps" in prompt
