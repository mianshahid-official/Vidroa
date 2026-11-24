"""
Stage 2: Visual Storyboard Module for PromptBeast.
Converts narration and visual ideas into an optimized structured storyboard
with precise timestamps, concrete visual descriptions, camera framing, and bible references.
Does NOT generate image prompts at this stage.
"""
import math
import re
from pathlib import Path
from typing import List, Optional, Dict, Any

from app.models.scene import VisualScene
from app.models.planning import StoryIntelligence, ScriptAnalysis
from app.models.timeline import NarrationData
from app.models.presets import VisualStylePreset
from app.models.project import ProjectConfig
from app.core.narration_workflow import parse_visual_breakdown_text, align_visuals_with_timestamps
from backend.inference.engine import BaseInferenceEngine


class Stage2VisualStoryboard:
    """
    Stage 2: Builds an optimized visual storyboard matching visuals to narration timing,
    preserving character and environment continuity without generating image prompts.
    """

    @classmethod
    def execute(
        cls,
        story_intelligence: StoryIntelligence,
        narration: Optional[NarrationData] = None,
        story_text: str = "",
        user_visual_ideas: Optional[str] = None,
        style_preset: Optional[VisualStylePreset] = None,
        config: Optional[ProjectConfig] = None,
        engine: Optional[BaseInferenceEngine] = None,
        min_duration: float = 2.0,
        max_duration: float = 8.0
    ) -> List[VisualScene]:
        """
        Builds the complete structured visual storyboard.
        """
        # Determine duration limits from config if available
        if config:
            min_dur = getattr(config, "min_duration", min_duration) or min_duration
            max_dur = getattr(config, "max_duration", max_duration) or max_duration
        else:
            min_dur = min_duration
            max_dur = max_duration

        scenes: List[VisualScene] = []

        # Case A: User supplied visual breakdown ideas (e.g. sample data.txt)
        if user_visual_ideas and user_visual_ideas.strip():
            items = parse_visual_breakdown_text(user_visual_ideas.strip())
            if items:
                scenes = align_visuals_with_timestamps(
                    visual_items=items,
                    narration=narration,
                    total_audio_duration=narration.duration_seconds if narration else None
                )

        # Case B: No user breakdown, plan scenes dynamically from narration segments / sentences
        if not scenes:
            scenes = cls._plan_scenes_from_narration(
                story_intelligence=story_intelligence,
                narration=narration,
                story_text=story_text,
                min_dur=min_dur,
                max_dur=max_dur
            )

        # Enhance scenes with bible references, characters, environments, and visual descriptions
        cls._enrich_scenes_with_intelligence(scenes, story_intelligence)

        # Seamless timeline: heal natural sentence pauses (gaps <= 2.0s) between scenes
        for i in range(len(scenes) - 1):
            curr_s = scenes[i]
            next_s = scenes[i + 1]
            gap = float(next_s.start) - float(curr_s.end)
            if 0.0 < gap <= 2.0:
                curr_s.end = round(float(next_s.start), 2)
                curr_s.duration = round(float(curr_s.end) - float(curr_s.start), 2)

        return scenes

    @classmethod
    def _plan_scenes_from_narration(
        cls,
        story_intelligence: StoryIntelligence,
        narration: Optional[NarrationData],
        story_text: str,
        min_dur: float,
        max_dur: float
    ) -> List[VisualScene]:
        scenes: List[VisualScene] = []

        if narration and narration.words:
            # Group words into 3.0s - 6.0s natural pacing chunks
            words = narration.words
            chunk_words = []
            chunk_start = words[0].start
            w_start_idx = 0

            for idx, w in enumerate(words):
                chunk_words.append(w.word)
                curr_dur = w.end - chunk_start
                is_sentence_end = w.word.rstrip().endswith((".", "!", "?"))
                is_clause_end = w.word.rstrip().endswith((",", ";", ":"))
                is_last_word = (idx == len(words) - 1)

                should_split = False
                if curr_dur >= max_dur:
                    should_split = True
                elif curr_dur >= min_dur and (is_sentence_end or (curr_dur >= 4.0 and is_clause_end)):
                    should_split = True
                elif is_last_word:
                    should_split = True

                if should_split and chunk_words:
                    s_id = f"{len(scenes) + 1:03d}"
                    seg_text = " ".join(chunk_words).strip()
                    end_time = w.end
                    dur = max(0.5, round(end_time - chunk_start, 2))

                    scenes.append(VisualScene(
                        scene_id=s_id,
                        index=len(scenes) + 1,
                        start=round(chunk_start, 2),
                        end=round(end_time, 2),
                        duration=dur,
                        start_word_index=w_start_idx,
                        end_word_index=idx,
                        narration_excerpt=seg_text,
                        visual_subject=f"Visual scene: {seg_text[:70]}",
                        visual_idea=f"Depicts: {seg_text}",
                        visual_description=f"Action and environment illustrating {seg_text}",
                        prompt="",
                        generation_status="pending"
                    ))

                    # Reset for next chunk
                    chunk_words = []
                    w_start_idx = idx + 1
                    if idx + 1 < len(words):
                        chunk_start = words[idx + 1].start
        else:
            # Fallback: slice sentences from story_text
            text = story_text or story_intelligence.story_summary
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
            if not sentences:
                sentences = [text] if text else ["Opening establishing shot."]

            curr_t = 0.0
            avg_dur = 4.0
            for i, sent in enumerate(sentences):
                s_id = f"{i + 1:03d}"
                start_t = curr_t
                end_t = curr_t + avg_dur
                curr_t = end_t
                scenes.append(VisualScene(
                    scene_id=s_id,
                    index=i + 1,
                    start=round(start_t, 2),
                    end=round(end_t, 2),
                    duration=round(avg_dur, 2),
                    narration_excerpt=sent,
                    visual_subject=f"Visual scene: {sent[:70]}",
                    visual_idea=f"Depicts: {sent}",
                    visual_description=f"Action and environment illustrating {sent}",
                    prompt="",
                    generation_status="pending"
                ))

        # Seamless timeline: heal natural sentence pauses (gaps <= 2.0s) between scenes
        for i in range(len(scenes) - 1):
            curr_s = scenes[i]
            next_s = scenes[i + 1]
            gap = float(next_s.start) - float(curr_s.end)
            if 0.0 < gap <= 2.0:
                curr_s.end = round(float(next_s.start), 2)
                curr_s.duration = round(float(curr_s.end) - float(curr_s.start), 2)

        return scenes

    @classmethod
    def _enrich_scenes_with_intelligence(
        cls,
        scenes: List[VisualScene],
        story_intelligence: StoryIntelligence
    ):
        """
        Attaches character tags, environment IDs, and camera framing suggestions
        from StoryIntelligence to each scene based on narrative matching.
        """
        chars = story_intelligence.characters or []
        envs = story_intelligence.environments or []

        for idx, scene in enumerate(scenes):
            combined_text = f"{scene.narration_excerpt} {scene.visual_idea} {scene.visual_subject}".lower()

            # Detect characters
            found_chars = []
            for c in chars:
                c_name = str(c.get("name", "")).strip()
                if c_name and c_name.lower() in combined_text:
                    found_chars.append(c_name)
            scene.character_ids = found_chars

            # Detect primary location
            found_env = None
            for e in envs:
                e_name = str(e.get("name", "")).strip()
                if e_name and e_name.lower() in combined_text:
                    found_env = e_name
                    break
            if not found_env and envs:
                found_env = str(envs[0].get("name", ""))
            scene.location_id = found_env
            scene.environment = found_env or "Story environment"

            # Enrich visual description and composition
            if not scene.visual_description:
                scene.visual_description = scene.visual_idea or f"Visual depiction of: {scene.narration_excerpt[:80]}"

            if not scene.composition:
                # Alternate dynamic camera compositions
                shot_rotations = [
                    "Wide cinematic establishing shot, eye-level framing",
                    "Medium shot capturing physical action and immediate surroundings",
                    "Close-up focal shot emphasizing tension, expression, or key prop",
                    "Low-angle dramatic perspective emphasizing scale and atmosphere",
                    "Over-the-shoulder perspective framing subject against environment"
                ]
                scene.composition = shot_rotations[idx % len(shot_rotations)]

