"""
Pipeline Stage 2: Visual scene segmentation and word-level timestamp alignment.
Handles stories of any length (from 50 words to 5,000+ words) using semantic chunking
and authoritative system prompts.
"""
from typing import List, Optional, Tuple, Callable, Any
import math
import re
from app.models.presets import SubjectPreset, VisualStylePreset
from app.models.project import ProjectConfig, ImageCountMode, TimingMode
from app.models.scene import VisualScene
from app.models.timeline import NarrationData
from app.core.timestamp_parser import TimestampParser
from app.core.timeline_engine import TimelineEngine
from backend.inference.engine import BaseInferenceEngine
from backend.pipeline.prompt_loader import load_system_prompt


FRAMING_PROGRESSION = [
    "Wide establishing shot — macroscopic scale & environmental atmosphere",
    "Medium character focus — intense posture, hands, tools, and period attire",
    "Extreme close-up macro — tactile archival detail, historical relics, worn textures",
    "Low-angle dramatic perspective — chiaroscuro lighting, deep shadows, and cinematic gravity",
    "Overhead top-down perspective — strategic overview, documents, maps, and spatial context",
    "Side profile candid shot — natural posture, authentic period depth layers"
]

VISUAL_SUBJECT_BEATS = [
    "establishing environmental view, architectural structures, and historical setting",
    "dynamic interaction, human action, and intense focus on focal figures",
    "intimate close detail of period artifacts, tools, documents, and tactile surfaces",
    "dramatic wide aftermath, shifting perspective, and atmospheric shadows",
    "archival schematic, tactical layout, or authentic document detail",
    "intense character portrait in natural period lighting with deep contrast"
]

def derive_smart_subscene_subject(base_subject: str, sub_excerpt: str, part_idx: int, total_parts: int) -> Tuple[str, str]:
    """
    Derives an authentic, story-driven visual subject and action from the narration excerpt
    dynamically without hardcoded story-specific strings or robotic templates.
    """
    clean_base = re.sub(r"\s*\(Angle\s*\d+\)", "", base_subject).strip()
    clean_base = re.sub(r"\s*—\s*.*$", "", clean_base).strip()

    # 1. If sub_excerpt contains descriptive text, extract the authentic narration clause
    if sub_excerpt and len(sub_excerpt.strip()) > 5:
        words = sub_excerpt.strip().split()
        clause = " ".join(words[:8]).rstrip(".,;:!?")
        subj = f"{clean_base} — {clause}"
        action = f"Visual depiction corresponding to: {clause}"
        return subj, action

    # 2. Sequential narrative progression
    FRAMING_VARIATIONS = [
        "establishing perspective of the developing situation",
        "dramatic character focus capturing immediate emotional reaction",
        "detailed focus on key narrative elements and surroundings",
        "shifting perspective highlighting consequential developments"
    ]
    variation = FRAMING_VARIATIONS[part_idx % len(FRAMING_VARIATIONS)]
    subj = f"{clean_base} — {variation}"
    action = f"Story progression: {variation}"
    return subj, action


def audit_and_heal_repetitions(scenes: List[VisualScene], narration: Optional[NarrationData] = None) -> List[VisualScene]:
    """
    Detects and eliminates visual loops where consecutive scenes repeat essentially the same subject/action.
    If consecutive scenes share high word similarity or repeat the same entity without progressive action,
    it evolves the subsequent scene into a distinct progressive storytelling beat based on the transcript.
    """
    if len(scenes) < 2:
        return scenes

    for i in range(1, len(scenes)):
        prev = scenes[i - 1]
        curr = scenes[i]

        prev_text = f"{prev.visual_subject} {prev.action}".lower()
        curr_text = f"{curr.visual_subject} {curr.action}".lower()

        prev_tokens = set(re.findall(r"\b[a-z]{4,}\b", prev_text))
        curr_tokens = set(re.findall(r"\b[a-z]{4,}\b", curr_text))

        overlap = len(prev_tokens & curr_tokens)
        union = len(prev_tokens | curr_tokens) if (prev_tokens or curr_tokens) else 1
        jaccard = overlap / float(union)

        # If similarity is high (> 0.5) or identical base subjects, evolve into a progressive action!
        if jaccard > 0.5 or (prev.visual_subject.strip().lower() == curr.visual_subject.strip().lower()):
            sub_excerpt = curr.narration_excerpt
            new_subj, new_act = derive_smart_subscene_subject(curr.visual_subject, sub_excerpt, i, len(scenes))
            curr.visual_subject = new_subj
            curr.action = new_act
            if not curr.composition or curr.composition == prev.composition:
                curr.composition = FRAMING_PROGRESSION[(i + 2) % len(FRAMING_PROGRESSION)]

    return scenes


from backend.pipeline.stage4_scheduling import (
    find_sentence_clause_split_point,
    assert_sentence_boundary_validity
)


def split_long_scene(sc: VisualScene, max_dur: float = 8.0, narration: Optional[NarrationData] = None) -> List[VisualScene]:
    """Splits a scene exceeding max_dur into diverse sub-scenes with sentence-aware boundaries."""
    if sc.duration <= max_dur:
        return [sc]

    num_parts = int(math.ceil(sc.duration / max_dur))
    words = sc.narration_excerpt.split() if sc.narration_excerpt else []

    if len(words) < num_parts * 2:
        part_dur = round(sc.duration / num_parts, 3)
        sub_scenes = []
        cur_s = sc.start
        for p_idx in range(num_parts):
            cur_e = round(cur_s + part_dur, 3) if p_idx < num_parts - 1 else sc.end
            p_dur = round(cur_e - cur_s, 3)
            sub_excerpt = sc.narration_excerpt
            framing = FRAMING_PROGRESSION[p_idx % len(FRAMING_PROGRESSION)]
            sub_subject, action_desc = derive_smart_subscene_subject(sc.visual_subject, sub_excerpt, p_idx, num_parts)
            sub_scenes.append(sc.model_copy(update={
                "start": cur_s,
                "end": cur_e,
                "duration": p_dur,
                "narration_excerpt": sub_excerpt,
                "visual_subject": sub_subject,
                "action": action_desc,
                "composition": framing,
                "framing_suggestion": framing
            }))
            cur_s = cur_e
        return sub_scenes

    # Partition words along sentence/clause boundaries
    partitions = []
    prev_w = 0
    for p in range(num_parts):
        if p == num_parts - 1:
            partitions.append(words[prev_w:])
        else:
            target = prev_w + max(2, len(words) // num_parts)
            split_w = find_sentence_clause_split_point(
                words,
                target_idx=target,
                min_idx=prev_w + 1,
                max_idx=len(words) - (num_parts - p)
            )
            partitions.append(words[prev_w : split_w + 1])
            prev_w = split_w + 1

    sub_scenes = []
    cur_s = sc.start
    total_words_count = len(words)
    for p_idx, part_words in enumerate(partitions):
        part_ratio = len(part_words) / max(1, total_words_count)
        p_dur = round(sc.duration * part_ratio, 3)
        cur_e = round(cur_s + p_dur, 3) if p_idx < num_parts - 1 else sc.end
        actual_dur = round(cur_e - cur_s, 3)
        sub_excerpt = " ".join(part_words)
        framing = FRAMING_PROGRESSION[p_idx % len(FRAMING_PROGRESSION)]
        sub_subject, action_desc = derive_smart_subscene_subject(sc.visual_subject, sub_excerpt, p_idx, num_parts)
        sub_scenes.append(sc.model_copy(update={
            "start": cur_s,
            "end": cur_e,
            "duration": actual_dur,
            "narration_excerpt": sub_excerpt,
            "visual_subject": sub_subject,
            "action": action_desc,
            "composition": framing,
            "framing_suggestion": framing
        }))
        cur_s = cur_e

    return sub_scenes


def _chunk_words(words, target_chunk_size=90) -> List[Tuple[int, int]]:
    """Splits word list into sentence-aligned chunks of ~80-110 words."""
    chunks = []
    i = 0
    n = len(words)
    while i < n:
        end_cand = min(i + target_chunk_size, n)
        best_break = end_cand
        if end_cand < n:
            for j in range(end_cand, min(end_cand + 25, n)):
                if words[j].word.endswith((".", "!", "?")):
                    best_break = j + 1
                    break
            else:
                for j in range(end_cand, max(i + 40, end_cand - 25), -1):
                    if words[j].word.endswith((".", "!", "?")):
                        best_break = j + 1
                        break
        chunks.append((i, best_break - 1))
        i = best_break
    return chunks


class Stage2Planner:
    """Executes Stage 2 visual scene planning and boundary placement."""

    @classmethod
    def execute(
        cls,
        engine: BaseInferenceEngine,
        story_text: str,
        analysis_summary: str,
        narration: Optional[NarrationData],
        config: ProjectConfig,
        subject_preset: Optional[SubjectPreset] = None,
        style_preset: Optional[VisualStylePreset] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[VisualScene]:
        # Ensure narration with word-level timestamps is available
        if not narration or not narration.words:
            narration = TimestampParser.estimate_from_text(story_text)

        words = narration.words
        total_words = len(words)
        if total_words == 0:
            raise ValueError("Story contains no readable words.")

        subj_name = subject_preset.name if subject_preset else "General Story"
        subj_instr = subject_preset.system_instructions if subject_preset else "Historical documentary visuals."
        style_name = style_preset.name if style_preset else "Century-Old Photograph"
        style_instr = style_preset.system_instructions if style_preset else "Vintage historical archival photography, sepia and monochrome, authentic grain, 19th/early 20th century archive."

        subject_rules = config.custom_subject if (config.subject_id == "custom" and config.custom_subject) else subj_instr
        style_rules = config.custom_style if (config.visual_style_id == "custom" and config.custom_style) else style_instr

        # For short scripts (<= 100 words), single call is optimal
        if total_words <= 100:
            chunks = [(0, total_words - 1)]
        else:
            chunks = _chunk_words(words, target_chunk_size=95)

        all_scenes: List[VisualScene] = []
        global_scene_counter = 1

        for c_idx, (w_start, w_end) in enumerate(chunks):
            chunk_words = words[w_start:w_end + 1]
            chunk_start_time = chunk_words[0].start
            chunk_end_time = chunk_words[-1].end
            chunk_excerpt = narration.get_excerpt(w_start, w_end)

            if progress_callback:
                progress_callback(c_idx + 1, len(chunks), f"Planning scenes for beat {c_idx + 1}/{len(chunks)}...")

            chunk_dur = round(chunk_end_time - chunk_start_time, 2)
            target_scenes = max(2, int(math.ceil(chunk_dur / 5.2)))

            user_prompt = (
                f"=== STORY CONTEXT ===\n"
                f"Summary: {analysis_summary}\n"
                f"Visual Style: {style_name} -> {style_rules}\n"
                f"Subject Domain: {subj_name} -> {subject_rules}\n\n"
                f"=== CHUNK {c_idx + 1}/{len(chunks)} TO SEGMENT ===\n"
                f"Time Range: {chunk_start_time:.2f}s to {chunk_end_time:.2f}s (Duration: {chunk_dur:.2f}s)\n"
                f"Word Range: word {w_start} to word {w_end} ({len(chunk_words)} words)\n"
                f"Narration Excerpt:\n\"{chunk_excerpt}\"\n\n"
                f"CRITICAL STORYBOARDING RULES:\n"
                f"1. Generate between {target_scenes} and {target_scenes + 2} distinct visual scenes for this {chunk_dur:.1f}s section.\n"
                f"2. Every scene duration MUST be between 2.5s and 7.5s (strictly <= 8.0s hard cap).\n"
                f"3. DEDICATED VISUALS FOR KEY ACTIONS: When this transcript excerpt mentions a key physical action, shock, or decision (e.g. ships destroyed/burned, mutinous debate, entering Tenochtitlan, nighttime retreat, final siege), you MUST create a specific visual scene vividly depicting that concrete action!\n"
                f"4. NEVER leave major actions unillustrated (do NOT replace dramatic events with passive standing soldiers).\n"
                f"Return JSON object with 'scenes' array."
            )

            try:
                data = engine.generate_structured_json(
                    prompt=user_prompt,
                    system_prompt=load_system_prompt("stage2_planning.txt"),
                    temperature=0.3,
                    max_tokens=3000
                )
                raw_scenes = data.get("scenes", [])
            except Exception as e:
                print(f"[Stage2Planner] Chunk {c_idx + 1} LLM planning failed: {e}. Using deterministic sentence fallback.")
                raw_scenes = []

            # Fallback if LLM produced no scenes for this chunk: create 1-3 scenes from sentence breaks
            if not raw_scenes:
                dur = round(chunk_end_time - chunk_start_time, 3)
                num_sub = max(1, int(round(dur / 5.0)))
                step = dur / num_sub
                raw_scenes = []
                for s_i in range(num_sub):
                    st = round(chunk_start_time + s_i * step, 2)
                    et = round(chunk_start_time + (s_i + 1) * step, 2) if s_i < num_sub - 1 else chunk_end_time
                    raw_scenes.append({
                        "start": st,
                        "end": et,
                        "duration": round(et - st, 2),
                        "narration_excerpt": chunk_excerpt[:80],
                        "visual_subject": f"{subject_preset.name} scene beat",
                        "visual_modality": "cinematic_scene",
                        "framing_suggestion": "Medium establishing shot"
                    })

            for s in raw_scenes:
                sc_id = f"{global_scene_counter:03d}"
                start_t = float(s.get("start", chunk_start_time))
                end_t = float(s.get("end", chunk_end_time))
                if end_t <= start_t:
                    end_t = start_t + 4.0

                dur = round(end_t - start_t, 3)
                visual_mod = s.get("visual_modality", "cinematic_scene")
                if visual_mod not in ["cinematic_scene", "infographic_chart", "blueprint_schematic", "historical_document", "tactical_map", "data_counter"]:
                    visual_mod = "cinematic_scene"

                narr_ex = s.get("narration_excerpt", "") or chunk_excerpt[:100]

                scene = VisualScene(
                    scene_id=sc_id,
                    start=start_t,
                    end=end_t,
                    duration=dur,
                    narration_excerpt=narr_ex,
                    visual_subject=s.get("visual_subject", "Scene visual subject"),
                    action=s.get("action", ""),
                    environment=s.get("environment", ""),
                    composition=s.get("composition", "") or s.get("framing_suggestion", "Medium shot"),
                    emotional_tone=s.get("emotional_tone", ""),
                    historical_confidence=s.get("historical_confidence", "well_supported_reconstruction"),
                    historical_event=s.get("historical_event", ""),
                    transition_to_next_scene=s.get("transition_to_next_scene", ""),
                    visual_modality=visual_mod,
                    visual_purpose=s.get("visual_purpose", ""),
                    framing_suggestion=s.get("framing_suggestion", "Medium shot"),
                    prompt=""
                )
                all_scenes.append(scene)
                global_scene_counter += 1

        # Heal gaps and overlaps so timeline is perfectly continuous from word 0 to end
        all_scenes = TimelineEngine.heal_gaps_and_overlaps(all_scenes)

        # STRICT HARD CAP: No image may ever stay on screen longer than 8.0 seconds
        max_cap = 8.0
        capped_scenes = []
        for sc in all_scenes:
            capped_scenes.extend(split_long_scene(sc, max_dur=max_cap, narration=narration))

        all_scenes = TimelineEngine.renumber_scenes(capped_scenes)

        # Guarantee coverage to the very last word of narration without monolithic duplicate cloning
        final_time = round(words[-1].end, 2)
        if all_scenes and all_scenes[-1].end < final_time:
            tail_gap = round(final_time - all_scenes[-1].end, 2)
            if tail_gap <= max_cap:
                tail_excerpt = narration.get_excerpt_by_time(all_scenes[-1].end, final_time) if narration else ""
                all_scenes.append(VisualScene(
                    scene_id=f"{len(all_scenes)+1:03d}",
                    start=round(all_scenes[-1].end, 2),
                    end=final_time,
                    duration=tail_gap,
                    narration_excerpt=tail_excerpt or words[-1].word,
                    visual_subject=f"{subj_name} — concluding resolution and historical legacy",
                    action="Concluding aftermath and historical legacy across the region",
                    composition="Wide cinematic pull-back shot with atmospheric horizon",
                    historical_confidence="documented",
                    visual_modality="cinematic_scene",
                    framing_suggestion="Wide cinematic pull-back shot with atmospheric horizon",
                    prompt=""
                ))
            else:
                cur_tail = all_scenes[-1].end
                num_tail_parts = int(math.ceil(tail_gap / 5.5))
                tail_step = round(tail_gap / num_tail_parts, 2)
                for t_i in range(num_tail_parts):
                    t_end = round(cur_tail + tail_step, 2) if t_i < num_tail_parts - 1 else final_time
                    t_excerpt = narration.get_excerpt_by_time(cur_tail, t_end) if narration else ""
                    framing = FRAMING_PROGRESSION[(len(all_scenes) + t_i) % len(FRAMING_PROGRESSION)]
                    beat = VISUAL_SUBJECT_BEATS[(len(all_scenes) + t_i) % len(VISUAL_SUBJECT_BEATS)]
                    all_scenes.append(VisualScene(
                        scene_id=f"{len(all_scenes)+1:03d}",
                        start=cur_tail,
                        end=t_end,
                        duration=round(t_end - cur_tail, 2),
                        narration_excerpt=t_excerpt or words[-1].word,
                        visual_subject=f"{subj_name} — {beat}",
                        action=f"Historical resolution: {beat}",
                        composition=framing,
                        historical_confidence="documented",
                        visual_modality="cinematic_scene",
                        framing_suggestion=framing,
                        prompt=""
                    ))
                    cur_tail = t_end
            all_scenes = TimelineEngine.renumber_scenes(all_scenes)

        # Eliminate repetitive visual loops across consecutive scenes
        all_scenes = audit_and_heal_repetitions(all_scenes, narration=narration)

        # =====================================================================
        # REAL-TIME QC AUDIT & ENFORCEMENT
        # =====================================================================
        qc_repaired = False
        final_qc_scenes = []
        for sc in all_scenes:
            if sc.duration > max_cap:
                final_qc_scenes.extend(split_long_scene(sc, max_dur=max_cap, narration=narration))
                qc_repaired = True
            else:
                final_qc_scenes.append(sc)

        if qc_repaired:
            all_scenes = TimelineEngine.renumber_scenes(final_qc_scenes)
            print(f"[Stage2 QC] Auto-repaired scenes exceeding 8.0s cap.")

        print(f"[Stage2 QC] Passed! {len(all_scenes)} scenes planned, strictly capped at {max_cap}s max duration.")

        assert_sentence_boundary_validity(all_scenes, story_text)

        if config.timing_mode == TimingMode.AI_DECIDES:
            return all_scenes

        res_scenes = TimelineEngine.enforce_duration_limits(
            scenes=all_scenes,
            min_duration=config.min_duration,
            max_duration=min(8.0, config.max_duration),
            target_duration=min(5.0, config.preferred_duration),
            narration=narration
        )
        assert_sentence_boundary_validity(res_scenes, story_text)
        return res_scenes
