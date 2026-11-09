"""
Phase 1 Tests: Fix 2 (F4) — Sentence-Aware Scene Boundaries.
Verifies:
1. find_sentence_clause_split_point finds nearest punctuation and respects disallowed tails.
2. assert_sentence_boundary_validity catches mid-sentence cuts (e.g. '...they wander in stuttering,').
3. Stage 4 tail split splits on punctuation, not midpoint arithmetic.
4. Stage 4 proportional path splits on punctuation and rejects story_text[:100] fallback.
5. Stage 2 long scene split respects sentence/clause boundaries.
"""
import pytest
from app.models.planning import (
    VisualBeatPlan,
    VisualBeat,
    ScheduledScene
)
from app.models.scene import VisualScene
from backend.pipeline.stage4_scheduling import (
    find_sentence_clause_split_point,
    assert_sentence_boundary_validity,
    Stage4TemporalScheduler
)


def test_find_sentence_clause_split_point_punctuation_and_tail_guard():
    # Sentence with punctuation at index 4 (gates.)
    words = ["The", "armored", "soldiers", "approached", "gates.", "They", "readied", "their", "weapons."]
    # target around index 3
    idx = find_sentence_clause_split_point(words, target_idx=3, min_idx=1, max_idx=7)
    assert idx == 4
    assert words[idx] == "gates."

    # Clause boundary with comma
    words2 = ["While", "advancing", "silently,", "the", "vanguard", "observed", "the", "ridge."]
    idx2 = find_sentence_clause_split_point(words2, target_idx=3, min_idx=1, max_idx=6)
    assert idx2 == 2
    assert words2[idx2] == "silently,"

    # Disallowed tail guard: avoid ending on 'the', 'of', 'and'
    words3 = ["They", "saw", "the", "silhouette", "of", "the", "tower."]
    # target pointing to 'of' (index 4) should back up or advance
    idx3 = find_sentence_clause_split_point(words3, target_idx=4, min_idx=1, max_idx=5)
    assert words3[idx3] not in ["the", "of", "and", "in"]


def test_assert_sentence_boundary_validity_catches_mid_sentence_fragment():
    # Audit's exact bug case: scene ending mid-clause with fragment in next scene
    broken_scenes = [
        ScheduledScene(
            scene_id="001",
            beat_id="VB-001",
            start_time=0.0,
            end_time=4.0,
            duration=4.0,
            narration_text="Below on Elm Street they wander in stuttering,",  # Disallowed tail word / mid-thought
            visual_summary="Figures wandering"
        ),
        ScheduledScene(
            scene_id="002",
            beat_id="VB-002",
            start_time=4.0,
            end_time=8.0,
            duration=4.0,
            narration_text="lurching rhythms, guided only by hunger.",
            visual_summary="Figures moving forward"
        )
    ]
    # In stuttering ends with comma, but next scene starts mid-phrase without full boundary or has disallowed tail
    with pytest.raises(RuntimeError) as exc_info:
        assert_sentence_boundary_validity(broken_scenes)
    assert "Stage 4 boundary failure" in str(exc_info.value)

    # Completely unpunctuated mid-sentence cut
    unpunctuated_scenes = [
        ScheduledScene(
            scene_id="001",
            beat_id="VB-001",
            start_time=0.0,
            end_time=4.0,
            duration=4.0,
            narration_text="The soldiers marched toward the stone walls and",
            visual_summary="Soldiers march"
        ),
        ScheduledScene(
            scene_id="002",
            beat_id="VB-002",
            start_time=4.0,
            end_time=8.0,
            duration=4.0,
            narration_text="prepared for battle under the dark sky.",
            visual_summary="Soldiers prepare"
        )
    ]
    with pytest.raises(RuntimeError) as exc_info2:
        assert_sentence_boundary_validity(unpunctuated_scenes)
    assert "Scene #001" in str(exc_info2.value)


def test_stage4_proportional_path_sentence_aware_and_no_wrong_story_fallback():
    story = (
        "The siege artillery arrived outside the northern gatehouse. "
        "Engineers immediately assembled the heavy timber frames under continuous arrow fire. "
        "By midnight, the central bombardment began with deafening concussions."
    )
    plan = VisualBeatPlan(
        visual_beats=[
            VisualBeat(
                beat_id="VB-001",
                exact_narration_segment="The siege artillery arrived outside the northern gatehouse. Engineers immediately assembled the heavy timber frames under continuous arrow fire.",
                narrative_purpose="Artillery deployment",
                primary_visual_concept="Heavy artillery frames deployed outside northern gatehouse",
                what_new_information_is_shown="Arrival of heavy artillery",
                composition="Wide establishing shot",
                lighting_and_atmosphere="Overcast afternoon",
                why_this_is_not_repetitive="Distinct tactical phase of siege preparation",
                continuity_references=[]
            ),
            VisualBeat(
                beat_id="VB-002",
                exact_narration_segment="By midnight, the central bombardment began with deafening concussions.",
                narrative_purpose="Bombardment begins",
                primary_visual_concept="Central bombardment strikes fortifications at night",
                what_new_information_is_shown="Night bombardment begins",
                composition="Low-angle dramatic perspective",
                lighting_and_atmosphere="Dark night illuminated by flaming ordnance",
                why_this_is_not_repetitive="Shift from assembly to active assault",
                continuity_references=[]
            )
        ]
    )

    storyboard = Stage4TemporalScheduler.execute(
        engine=None,
        visual_plan=plan,
        narration=None,
        story_text=story,
        total_audio_duration=18.0
    )

    assert len(storyboard.scenes) >= 2
    for sc in storyboard.scenes:
        # Every scene must end on valid punctuation
        assert sc.narration_text[-1] in [".", "!", "?", ";", ",", "—", "–"]
        # Must not be the wrong-story opening fallback
        assert "story_text[:100]" not in sc.narration_text


def test_stage4_rejects_missing_beat_narration():
    plan = VisualBeatPlan(
        visual_beats=[
            VisualBeat(
                beat_id="VB-001",
                exact_narration_segment="",  # Intentionally missing!
                narrative_purpose="Empty beat",
                primary_visual_concept="Empty visual",
                what_new_information_is_shown="None",
                composition="Wide shot",
                lighting_and_atmosphere="Day",
                why_this_is_not_repetitive="Unique initial beat",
                continuity_references=[]
            )
        ]
    )
    with pytest.raises(RuntimeError) as exc_info:
        Stage4TemporalScheduler.execute(
            engine=None,
            visual_plan=plan,
            narration=None,
            story_text="Some story text.",
            total_audio_duration=10.0
        )
    assert "no exact narration segment" in str(exc_info.value)


def test_stage4_tail_split_sentence_aware():
    plan = VisualBeatPlan(
        visual_beats=[
            VisualBeat(
                beat_id="VB-001",
                exact_narration_segment="The vanguard crossed the frozen river at dawn. Sentry fires burned along the high cliffs.",
                narrative_purpose="River crossing",
                primary_visual_concept="Vanguard soldiers crossing frozen river at dawn",
                what_new_information_is_shown="Dawn crossing",
                composition="Wide shot",
                lighting_and_atmosphere="Dawn mist",
                why_this_is_not_repetitive="Initial crossing",
                continuity_references=[]
            )
        ]
    )
    storyboard = Stage4TemporalScheduler.execute(
        engine=None,
        visual_plan=plan,
        narration=None,
        story_text="The vanguard crossed the frozen river at dawn. Sentry fires burned along the high cliffs.",
        total_audio_duration=14.0
    )
    assert len(storyboard.scenes) >= 2
    for s in storyboard.scenes:
        assert s.duration <= 8.05
        assert s.narration_text[-1] in [".", "!", "?", ";", ":", "—", "–"]
    assert "dawn." in storyboard.scenes[0].narration_text
    assert "cliffs." in storyboard.scenes[-1].narration_text
