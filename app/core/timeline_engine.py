"""
Timeline engine for scene operations: splitting, merging, deleting, and boundary adjustment.
"""
from typing import List, Optional, Tuple
from app.models.scene import VisualScene
from app.models.timeline import NarrationData


class TimelineEngine:
    """Manages scene lists, edits, splits, merges, and gapless boundary preservation."""

    @staticmethod
    def renumber_scenes(scenes: List[VisualScene]) -> List[VisualScene]:
        """Ensures consecutive, zero-padded 3-digit scene IDs (001, 002, ...)."""
        updated = []
        for i, sc in enumerate(scenes):
            new_id = f"{i + 1:03d}"
            sc_dict = sc.model_dump()
            sc_dict["scene_id"] = new_id
            updated.append(VisualScene(**sc_dict))
        return updated

    @staticmethod
    def find_nearest_word_boundary(
        timestamp: float,
        narration: Optional[NarrationData]
    ) -> Tuple[float, Optional[int]]:
        """Finds the closest word boundary (end of a word or start of next word) to a given timestamp."""
        if not narration or not narration.words:
            return round(timestamp, 3), None

        closest_idx = 0
        min_diff = float("inf")
        for i, w in enumerate(narration.words):
            # Check distance to word end
            diff_end = abs(w.end - timestamp)
            if diff_end < min_diff:
                min_diff = diff_end
                closest_idx = i

        split_t = narration.words[closest_idx].end
        return round(split_t, 3), closest_idx

    @classmethod
    def split_scene(
        cls,
        scenes: List[VisualScene],
        scene_id: str,
        split_time: float,
        narration: Optional[NarrationData] = None
    ) -> List[VisualScene]:
        """
        Splits the scene with scene_id at split_time into two scenes.
        Enforces word-boundary alignment if narration timestamps exist.
        """
        target_idx = next((i for i, s in enumerate(scenes) if s.scene_id == scene_id), None)
        if target_idx is None:
            raise ValueError(f"Scene with ID '{scene_id}' not found.")

        target = scenes[target_idx]
        if split_time <= target.start or split_time >= target.end:
            raise ValueError(f"Split time ({split_time}s) must be strictly between scene start ({target.start}s) and end ({target.end}s).")

        adjusted_split_time = split_time
        split_word_idx = None

        if narration and narration.words:
            adjusted_split_time, split_word_idx = cls.find_nearest_word_boundary(split_time, narration)
            # Ensure adjusted time is strictly within bounds
            if adjusted_split_time <= target.start or adjusted_split_time >= target.end:
                adjusted_split_time = round((target.start + target.end) / 2.0, 3)

        # Build first half
        first_end = adjusted_split_time
        first_duration = round(first_end - target.start, 3)
        first_word_idx = target.start_word_index
        first_end_word_idx = split_word_idx if split_word_idx is not None else target.end_word_index

        first_narration = target.narration_excerpt
        second_narration = target.narration_excerpt

        if narration and narration.words and first_word_idx is not None and first_end_word_idx is not None:
            first_narration = narration.get_excerpt(first_word_idx, first_end_word_idx)
            second_start_word_idx = min(first_end_word_idx + 1, len(narration.words) - 1)
            second_end_word_idx = target.end_word_index if target.end_word_index is not None else len(narration.words) - 1
            second_narration = narration.get_excerpt(second_start_word_idx, second_end_word_idx)
        else:
            second_start_word_idx = None
            second_end_word_idx = None

        scene_a = VisualScene(
            scene_id=target.scene_id,
            start=target.start,
            end=first_end,
            duration=first_duration,
            start_word_index=first_word_idx,
            end_word_index=first_end_word_idx,
            narration_excerpt=first_narration,
            visual_subject=f"{target.visual_subject} (Part 1)",
            visual_purpose=target.visual_purpose,
            framing_suggestion=target.framing_suggestion,
            prompt=target.prompt,
            is_manually_edited=True,
            is_validated=False
        )

        second_duration = round(target.end - first_end, 3)
        scene_b = VisualScene(
            scene_id=f"{target.scene_id}_b",
            start=first_end,
            end=target.end,
            duration=second_duration,
            start_word_index=second_start_word_idx,
            end_word_index=second_end_word_idx,
            narration_excerpt=second_narration,
            visual_subject=f"{target.visual_subject} (Part 2)",
            visual_purpose=target.visual_purpose,
            framing_suggestion=target.framing_suggestion,
            prompt=f"[Part 2] {target.prompt}",
            is_manually_edited=True,
            is_validated=False
        )

        new_list = scenes[:target_idx] + [scene_a, scene_b] + scenes[target_idx + 1:]
        return cls.renumber_scenes(new_list)

    @classmethod
    def merge_scenes(
        cls,
        scenes: List[VisualScene],
        scene_id_a: str,
        scene_id_b: str,
        narration: Optional[NarrationData] = None
    ) -> List[VisualScene]:
        """Merges two consecutive scenes into a single unified scene."""
        idx_a = next((i for i, s in enumerate(scenes) if s.scene_id == scene_id_a), None)
        idx_b = next((i for i, s in enumerate(scenes) if s.scene_id == scene_id_b), None)

        if idx_a is None or idx_b is None:
            raise ValueError("Both scenes to merge must exist in the timeline.")

        if abs(idx_a - idx_b) != 1:
            raise ValueError("Only adjacent consecutive scenes can be merged.")

        first_idx = min(idx_a, idx_b)
        second_idx = max(idx_a, idx_b)

        sc_a = scenes[first_idx]
        sc_b = scenes[second_idx]

        combined_start = min(sc_a.start, sc_b.start)
        combined_end = max(sc_a.end, sc_b.end)
        combined_duration = round(combined_end - combined_start, 3)

        start_word_idx = sc_a.start_word_index if sc_a.start_word_index is not None else sc_b.start_word_index
        end_word_idx = sc_b.end_word_index if sc_b.end_word_index is not None else sc_a.end_word_index

        if narration and narration.words and start_word_idx is not None and end_word_idx is not None:
            combined_narration = narration.get_excerpt(start_word_idx, end_word_idx)
        else:
            combined_narration = f"{sc_a.narration_excerpt} {sc_b.narration_excerpt}".strip()

        combined_subject = f"{sc_a.visual_subject} followed by {sc_b.visual_subject}"
        combined_prompt = f"{sc_a.prompt}\n\n[Continuing scene context]: {sc_b.prompt}"

        merged_scene = VisualScene(
            scene_id=sc_a.scene_id,
            start=combined_start,
            end=combined_end,
            duration=combined_duration,
            start_word_index=start_word_idx,
            end_word_index=end_word_idx,
            narration_excerpt=combined_narration,
            visual_subject=combined_subject,
            visual_purpose=sc_a.visual_purpose or sc_b.visual_purpose,
            framing_suggestion=sc_a.framing_suggestion or sc_b.framing_suggestion,
            prompt=combined_prompt,
            is_manually_edited=True,
            is_validated=False
        )

        new_list = scenes[:first_idx] + [merged_scene] + scenes[second_idx + 1:]
        return cls.renumber_scenes(new_list)

    @classmethod
    def delete_scene(
        cls,
        scenes: List[VisualScene],
        scene_id: str,
        narration: Optional[NarrationData] = None
    ) -> List[VisualScene]:
        """Deletes a scene and closes the timeline gap by extending the preceding or succeeding scene."""
        if len(scenes) <= 1:
            raise ValueError("Cannot delete the only remaining scene in the timeline.")

        idx = next((i for i, s in enumerate(scenes) if s.scene_id == scene_id), None)
        if idx is None:
            raise ValueError(f"Scene with ID '{scene_id}' not found.")

        target = scenes[idx]
        new_scenes = [s.model_copy(deep=True) for s in scenes]

        if idx > 0:
            # Extend preceding scene to cover target end
            prev = new_scenes[idx - 1]
            prev.end = target.end
            prev.duration = round(prev.end - prev.start, 3)
            prev.end_word_index = target.end_word_index
            if narration and narration.words and prev.start_word_index is not None and prev.end_word_index is not None:
                prev.narration_excerpt = narration.get_excerpt(prev.start_word_index, prev.end_word_index)
            prev.is_manually_edited = True
        else:
            # First scene was deleted; extend next scene to start at 0
            succ = new_scenes[idx + 1]
            succ.start = target.start
            succ.duration = round(succ.end - succ.start, 3)
            succ.start_word_index = target.start_word_index
            if narration and narration.words and succ.start_word_index is not None and succ.end_word_index is not None:
                succ.narration_excerpt = narration.get_excerpt(succ.start_word_index, succ.end_word_index)
            succ.is_manually_edited = True

        new_scenes.pop(idx)
        return cls.renumber_scenes(new_scenes)

    @classmethod
    def heal_gaps_and_overlaps(cls, scenes: List[VisualScene]) -> List[VisualScene]:
        """Automatically aligns consecutive scene edges to eliminate tiny float gaps and overlaps."""
        if not scenes:
            return []

        healed = []
        current_time = scenes[0].start

        for i, sc in enumerate(scenes):
            sc_dict = sc.model_dump()
            sc_dict["start"] = round(current_time, 3)
            # Ensure min duration of 0.5s
            if sc_dict["end"] <= sc_dict["start"]:
                sc_dict["end"] = round(sc_dict["start"] + 1.0, 3)
            sc_dict["duration"] = round(sc_dict["end"] - sc_dict["start"], 3)
            healed_scene = VisualScene(**sc_dict)
            healed.append(healed_scene)
            current_time = healed_scene.end

        return healed


    @classmethod
    def enforce_duration_limits(
        cls,
        scenes: List[VisualScene],
        min_duration: float = 0.5,
        max_duration: float = 6.0,
        target_duration: float = 4.5,
        narration: Optional[NarrationData] = None
    ) -> List[VisualScene]:
        """Strictly enforces that no scene exceeds max_duration and no scene is below min_duration."""
        if not scenes:
            return []

        framings = [
            "Wide establishing shot",
            "Medium tracking shot",
            "Close-up dramatic focus",
            "Low-angle cinematic perspective",
            "Over-the-shoulder reaction view"
        ]

        result = []
        for sc in scenes:
            dur = sc.duration
            if dur <= max_duration and dur >= min_duration:
                result.append(sc)
                continue

            num_parts = max(1, int(round(dur / target_duration)))
            while num_parts > 1 and (dur / num_parts) < min_duration:
                num_parts -= 1
            while (dur / num_parts) > max_duration:
                num_parts += 1

            part_len = dur / num_parts
            cur_start = sc.start

            for p_idx in range(num_parts):
                if p_idx == num_parts - 1:
                    cur_end = sc.end
                else:
                    target_t = cur_start + part_len
                    if narration and narration.words:
                        cur_end, _ = cls.find_nearest_word_boundary(target_t, narration)
                    else:
                        cur_end = round(target_t, 2)

                    if cur_end - cur_start < min_duration or sc.end - cur_end < min_duration:
                        cur_end = round(cur_start + part_len, 2)
                    if cur_end >= sc.end or cur_end <= cur_start:
                        cur_end = round(cur_start + part_len, 2)

                part_dur = round(cur_end - cur_start, 2)
                
                seg_excerpt = sc.narration_excerpt
                if narration and narration.words:
                    w_seg = [w.word for w in narration.words if w.start >= cur_start - 0.05 and w.end <= cur_end + 0.05]
                    if w_seg:
                        seg_excerpt = " ".join(w_seg)

                framing = framings[p_idx % len(framings)]
                
                sub = VisualScene(
                    scene_id=f"{len(result) + 1:03d}",
                    start=round(cur_start, 2),
                    end=round(cur_end, 2),
                    duration=part_dur,
                    narration_excerpt=seg_excerpt,
                    visual_subject=f"{sc.visual_subject} ({framing})" if p_idx > 0 else sc.visual_subject,
                    visual_purpose=sc.visual_purpose,
                    framing_suggestion=framing,
                    prompt=f"{framing}. {sc.prompt}" if sc.prompt else "",
                    is_validated=True
                )
                result.append(sub)
                cur_start = cur_end

        cleaned = []
        for sc in result:
            if cleaned and sc.duration < min_duration and (cleaned[-1].duration + sc.duration) <= max_duration:
                prev = cleaned[-1]
                prev.end = sc.end
                prev.duration = round(prev.end - prev.start, 2)
                prev.narration_excerpt = f"{prev.narration_excerpt} {sc.narration_excerpt}".strip()
            elif cleaned and sc.duration < min_duration:
                prev = cleaned[-1]
                combined_start = prev.start
                combined_end = sc.end
                mid_t = round((combined_start + combined_end) / 2.0, 2)
                if narration and narration.words:
                    mid_t, _ = cls.find_nearest_word_boundary(mid_t, narration)
                prev.end = mid_t
                prev.duration = round(prev.end - prev.start, 2)
                sc.start = mid_t
                sc.duration = round(sc.end - sc.start, 2)
                cleaned.append(sc)
            else:
                cleaned.append(sc)

        # Ensure coverage extends to the full narration duration if narration exists
        if narration and narration.duration_seconds and cleaned and cleaned[-1].end < narration.duration_seconds - 2.0:
            tail_start = cleaned[-1].end
            tail_end = round(narration.duration_seconds, 2)
            rem_dur = tail_end - tail_start
            num_tail_parts = max(1, int(round(rem_dur / target_duration)))
            part_len = rem_dur / num_tail_parts
            cur_s = tail_start
            for tp_idx in range(num_tail_parts):
                cur_e = tail_end if tp_idx == num_tail_parts - 1 else round(cur_s + part_len, 2)
                if narration.words and tp_idx < num_tail_parts - 1:
                    cur_e, _ = cls.find_nearest_word_boundary(cur_e, narration)
                w_seg = [w.word for w in narration.words if w.start >= cur_s - 0.05 and w.end <= cur_e + 0.05]
                ex = " ".join(w_seg) if w_seg else f"Scene continuing to {cur_e:.2f}s"
                framing = framings[(len(cleaned) + tp_idx) % len(framings)]
                tail_sc = VisualScene(
                    scene_id=f"{len(cleaned) + 1:03d}",
                    start=round(cur_s, 2),
                    end=round(cur_e, 2),
                    duration=round(cur_e - cur_s, 2),
                    narration_excerpt=ex,
                    visual_subject=f"Documentary Action: {ex[:45]}...",
                    framing_suggestion=framing,
                    prompt="",
                    is_validated=True
                )
                cleaned.append(tail_sc)
                cur_s = cur_e

        healed = cls.heal_gaps_and_overlaps(cleaned)
        return cls.renumber_scenes(healed)
