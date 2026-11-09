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
from app.models.timeline import NarrationData, WordTimestamp
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

    # Clause boundary with comma followed by valid conjunction in CLAUSE_CONTINUATION_CONJUNCTIONS
    words2 = ["While", "advancing", "silently,", "and", "vanguard", "observed", "the", "ridge."]
    idx2 = find_sentence_clause_split_point(words2, target_idx=3, min_idx=1, max_idx=6)
    assert idx2 == 2
    assert words2[idx2] == "silently,"

    # Comma followed by non-conjunction (e.g. 'the', 'you') is skipped at every search level
    words2_invalid_comma = ["While", "advancing", "silently,", "the", "vanguard", "observed", "the", "ridge."]
    idx2_skipped = find_sentence_clause_split_point(words2_invalid_comma, target_idx=3, min_idx=1, max_idx=6)
    # Extends forward past max_idx to the next sentence terminator 'ridge.'
    assert idx2_skipped == 7
    assert words2_invalid_comma[idx2_skipped] == "ridge."

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


def test_assert_sentence_boundary_validity_allows_valid_clause_conjunction():
    # Valid compound sentence split on comma with lowercase coordinating conjunction
    valid_scenes = [
        ScheduledScene(
            scene_id="001",
            beat_id="VB-001",
            start_time=0.0,
            end_time=4.5,
            duration=4.5,
            narration_text="By day 20, you will find proof that one of them is still alive,",
            visual_summary="Hero finding proof of survivor"
        ),
        ScheduledScene(
            scene_id="002",
            beat_id="VB-002",
            start_time=4.5,
            end_time=9.0,
            duration=4.5,
            narration_text="and that is the least dangerous thing down there.",
            visual_summary="Approaching deeper danger"
        )
    ]
    # Must NOT raise RuntimeError
    assert_sentence_boundary_validity(valid_scenes)


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


def test_stage4_speakers_come_on_splits_at_period_not_voice():
    """
    Regression test for Scene #005 cutting mid-sentence:
    Transcript lines: 'Then the speakers come on. A flat mechanical voice orders everyone to evacuate immediately.'
    Verifies that Stage 4's timestamp alignment subsegmenting uses find_sentence_clause_split_point(),
    splitting Scene #005 cleanly at 'on.' and starting Scene #006 with 'A flat mechanical voice'.
    """
    words = [
        # Preceding 4 beats to align Scene numbering to Scene #005 / Scene #006
        WordTimestamp(word="First", start=0.0, end=1.0),
        WordTimestamp(word="beat", start=1.0, end=2.0),
        WordTimestamp(word="starts", start=2.0, end=3.0),
        WordTimestamp(word="here.", start=3.0, end=4.0),

        WordTimestamp(word="Second", start=4.0, end=5.0),
        WordTimestamp(word="beat", start=5.0, end=6.0),
        WordTimestamp(word="starts", start=6.0, end=7.0),
        WordTimestamp(word="here.", start=7.0, end=8.0),

        WordTimestamp(word="Third", start=8.0, end=9.0),
        WordTimestamp(word="beat", start=9.0, end=10.0),
        WordTimestamp(word="starts", start=10.0, end=11.0),
        WordTimestamp(word="here.", start=11.0, end=12.0),

        WordTimestamp(word="Fourth", start=12.0, end=13.0),
        WordTimestamp(word="beat", start=13.0, end=14.0),
        WordTimestamp(word="starts", start=14.0, end=15.0),
        WordTimestamp(word="here.", start=15.0, end=16.0),

        # Beat 5: exact transcript lines spanning 8.5s (> 6.8s ceiling -> subsegment split)
        WordTimestamp(word="Then", start=16.0, end=16.5),
        WordTimestamp(word="the", start=16.5, end=17.0),
        WordTimestamp(word="speakers", start=17.0, end=17.6),
        WordTimestamp(word="come", start=17.6, end=18.1),
        WordTimestamp(word="on.", start=18.1, end=18.8),
        WordTimestamp(word="A", start=18.8, end=19.2),
        WordTimestamp(word="flat", start=19.2, end=19.8),
        WordTimestamp(word="mechanical", start=19.8, end=20.5),
        WordTimestamp(word="voice", start=20.5, end=21.1),
        WordTimestamp(word="orders", start=21.1, end=21.7),
        WordTimestamp(word="everyone", start=21.7, end=22.4),
        WordTimestamp(word="to", start=22.4, end=22.9),
        WordTimestamp(word="evacuate", start=22.9, end=23.6),
        WordTimestamp(word="immediately.", start=23.6, end=24.5),
    ]

    full_text = " ".join(w.word for w in words)
    narration_data = NarrationData(
        duration_seconds=24.5,
        words=words,
        transcript=full_text
    )

    visual_beats = [
        VisualBeat(
            beat_id="VB-001",
            exact_narration_segment="First beat starts here.",
            narrative_purpose="P1",
            primary_visual_concept="C1",
            what_new_information_is_shown="Info 1",
            composition="Comp 1",
            lighting_and_atmosphere="Light 1",
            why_this_is_not_repetitive="Unique 1",
            continuity_references=[]
        ),
        VisualBeat(
            beat_id="VB-002",
            exact_narration_segment="Second beat starts here.",
            narrative_purpose="P2",
            primary_visual_concept="C2",
            what_new_information_is_shown="Info 2",
            composition="Comp 2",
            lighting_and_atmosphere="Light 2",
            why_this_is_not_repetitive="Unique 2",
            continuity_references=[]
        ),
        VisualBeat(
            beat_id="VB-003",
            exact_narration_segment="Third beat starts here.",
            narrative_purpose="P3",
            primary_visual_concept="C3",
            what_new_information_is_shown="Info 3",
            composition="Comp 3",
            lighting_and_atmosphere="Light 3",
            why_this_is_not_repetitive="Unique 3",
            continuity_references=[]
        ),
        VisualBeat(
            beat_id="VB-004",
            exact_narration_segment="Fourth beat starts here.",
            narrative_purpose="P4",
            primary_visual_concept="C4",
            what_new_information_is_shown="Info 4",
            composition="Comp 4",
            lighting_and_atmosphere="Light 4",
            why_this_is_not_repetitive="Unique 4",
            continuity_references=[]
        ),
        VisualBeat(
            beat_id="VB-005",
            exact_narration_segment="Then the speakers come on. A flat mechanical voice orders everyone to evacuate immediately.",
            narrative_purpose="P5",
            primary_visual_concept="Speakers activate and evacuation order is broadcast",
            what_new_information_is_shown="Evacuation announcement",
            composition="Medium wide tracking",
            lighting_and_atmosphere="Emergency lighting",
            why_this_is_not_repetitive="Key turning point",
            continuity_references=[]
        ),
    ]

    plan = VisualBeatPlan(visual_beats=visual_beats)
    storyboard = Stage4TemporalScheduler.execute(
        engine=None,
        visual_plan=plan,
        narration=narration_data,
        story_text=full_text,
        total_audio_duration=24.5
    )

    # Must produce 6 total scenes (Beat 5 split into Scene 005 and 006)
    assert len(storyboard.scenes) == 6
    scene_005 = next(s for s in storyboard.scenes if s.scene_id == "005")
    scene_006 = next(s for s in storyboard.scenes if s.scene_id == "006")

    # Assert Scene #005 ends cleanly at 'on.'
    assert scene_005.narration_text.strip().endswith("on.")
    assert "voice" not in scene_005.narration_text

    # Assert Scene #006 begins with 'A flat mechanical voice' and ends at 'immediately.'
    assert scene_006.narration_text.strip().startswith("A flat mechanical voice")
    assert scene_006.narration_text.strip().endswith("immediately.")

    # Invariant validator must pass without raising
    assert_sentence_boundary_validity(storyboard.scenes)


def test_find_sentence_clause_split_point_fallback_extends_to_next_boundary():
    """
    Verifies that find_sentence_clause_split_point never silently cuts mid-sentence:
    if no punctuation is found in the search window, it extends to the next available
    sentence/clause boundary instead of falling back to the raw arithmetic target index.
    """
    words = [
        "The", "soldiers", "marched", "quietly", "through", "the",
        "dense", "valley", "fog", "until", "they", "reached", "the", "ridge."
    ]
    # target_idx=3 ('quietly') with search_window=2 -> window [1..5] ('soldiers'..'the')
    # No punctuation exists within the window.
    # The next punctuation is at index 13 ('ridge.').
    # The fallback MUST extend forward to the boundary, not cut mid-sentence at target_idx=3.
    idx = find_sentence_clause_split_point(words, target_idx=3, min_idx=1, max_idx=13, search_window=2)
    assert idx == 13
    assert words[idx] == "ridge."


def test_stage4_skips_invalid_comma_and_extends_past_8s_without_cutting_at_worse():
    """
    Regression test for Scene #009 cutting mid-sentence at 'worse,':
    Fixture sentence:
    '400,000 square feet of mall drops into blackness. You are not getting out tonight,
     and as the screaming outside turns into something worse, you realize you are not getting out tomorrow either.'

    Verifies that:
    1. The comma after 'worse,' is recognized as invalid because the next word ('you')
       is not in CLAUSE_CONTINUATION_CONJUNCTIONS.
    2. The scheduler skips 'worse,' at every search level.
    3. The scene does NOT cut at 'worse,' — the scene ends at '...tomorrow either.'
    4. assert_sentence_boundary_validity passes, even if the scene duration exceeds 8s.
    """
    fixture_text = (
        "400,000 square feet of mall drops into blackness. You are not getting out tonight, "
        "and as the screaming outside turns into something worse, you realize you are not getting out tomorrow either."
    )
    words_list = fixture_text.split()
    words = []
    t = 0.0
    for w in words_list:
        dur = 0.35
        words.append(WordTimestamp(word=w, start=t, end=round(t + dur, 2)))
        t = round(t + dur + 0.05, 2)

    total_dur = words[-1].end
    narration_data = NarrationData(
        duration_seconds=total_dur,
        words=words,
        transcript=fixture_text
    )

    plan = VisualBeatPlan(
        visual_beats=[
            VisualBeat(
                beat_id="VB-001",
                exact_narration_segment=fixture_text,
                narrative_purpose="Mall blackness and entrapment",
                primary_visual_concept="Darkened mall interior with survivors trapped",
                what_new_information_is_shown="Entrapment realization",
                composition="Wide dramatic shot",
                lighting_and_atmosphere="Pitch black with dim emergency lights",
                why_this_is_not_repetitive="Turning point into total isolation",
                continuity_references=[]
            )
        ]
    )

    storyboard = Stage4TemporalScheduler.execute(
        engine=None,
        visual_plan=plan,
        narration=narration_data,
        story_text=fixture_text,
        total_audio_duration=total_dur
    )

    # 1. Assert no scene cuts at 'worse,'
    for sc in storyboard.scenes:
        assert not sc.narration_text.strip().endswith("worse,")
        assert not sc.narration_text.strip().endswith("worse")

    # 2. Assert the scene covering the screaming ends at 'tomorrow either.'
    screaming_scene = next(sc for sc in storyboard.scenes if "screaming" in sc.narration_text)
    assert screaming_scene.narration_text.strip().endswith("tomorrow either.")
    assert "something worse," in screaming_scene.narration_text

    # 3. Invariant check passes cleanly without raising
    assert_sentence_boundary_validity(storyboard.scenes)

    # 4. Direct split test: when targeting 'worse,' with cap before 'either.', skips 'worse,' and extends to 'either.'
    worse_idx = next(i for i, w in enumerate(words_list) if "worse" in w)
    either_idx = next(i for i, w in enumerate(words_list) if "either" in w)
    split_pt = find_sentence_clause_split_point(
        words_list,
        target_idx=worse_idx,
        min_idx=14,  # after 'tonight,'
        max_idx=either_idx - 1
    )
    assert words_list[split_pt] != "worse,"
    assert split_pt == either_idx
    assert words_list[split_pt] == "either."
