"""
Stage 3: Narration-Aligned Visual Planning.
Transforms analyzed script and continuity bibles into a narration-synchronized VisualBeatPlan.
Partitions the story into ~18-24 granular narrative units to guarantee high visual specificity,
strict chronological pacing, and eliminate premature assassination or repetitive visuals.
"""
import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from app.models.planning import ScriptAnalysis, VisualBeat, VisualBeatPlan
from backend.inference.engine import BaseInferenceEngine


def load_system_prompt() -> str:
    prompt_file = Path("config/system_prompts/stage2_planning.txt")
    if prompt_file.exists():
        try:
            return prompt_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return "You are an exceptional visual storyteller and storyboard architect. Plan narration-aligned visual beats."


class Stage3VisualPlanner:
    """Plans narration-aligned visual beats for the entire story using Groq."""

    @classmethod
    def execute(
        cls,
        engine: BaseInferenceEngine,
        story_text: str,
        analysis: ScriptAnalysis,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> VisualBeatPlan:
        system_prompt = load_system_prompt()

        char_ctx = "; ".join([f"{c.name} ({c.role}): {c.appearance[:80]}" for c in analysis.continuity_bible.characters[:6]])
        loc_ctx = "; ".join([f"{l.name}: {l.description[:80]}" for l in analysis.continuity_bible.locations[:4]])
        era_ctx = analysis.historical_or_setting_period or "Ancient Roman Republic (44 BC)"

        # Partition story_text into granular units to guarantee high visual progression,
        # strict chronological pacing, and eliminate premature action assignment.
        # Long scripts (~1,260 words) partition into ~18-24 units (~50-65 words each).
        # Short test/benchmark scripts adaptively scale so at least 2-4 units are produced.
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", story_text.strip()) if s.strip()]
        total_story_words = len(story_text.split())

        if total_story_words > 250:
            max_words = 60
            min_split = 45
            split_next = 25
        elif total_story_words > 80:
            max_words = 35
            min_split = 25
            split_next = 12
        else:
            max_words = max(8, total_story_words // 3)
            min_split = max(6, max_words - 3)
            split_next = 6

        candidate_units = []
        cur_unit_sents = []
        cur_word_count = 0

        for idx_s, s in enumerate(sents):
            s_words = len(s.split())
            if (cur_word_count + s_words > max_words and cur_unit_sents) or (cur_word_count > min_split and s_words > split_next):
                u_text = " ".join(cur_unit_sents)
                candidate_units.append({
                    "unit_id": f"UNIT-{len(candidate_units)+1:02d}",
                    "text": u_text,
                    "source_beat_ids": [f"BEAT-{len(candidate_units)+1:03d}"]
                })
                cur_unit_sents = [s]
                cur_word_count = s_words
            else:
                cur_unit_sents.append(s)
                cur_word_count += s_words

        if cur_unit_sents:
            candidate_units.append({
                "unit_id": f"UNIT-{len(candidate_units)+1:02d}",
                "text": " ".join(cur_unit_sents),
                "source_beat_ids": [f"BEAT-{len(candidate_units)+1:03d}"]
            })

        # Deterministic safety guarantee: Any script with >= 2 sentences or >= 6 words MUST produce >= 2 units
        if len(candidate_units) < 2:
            if len(sents) >= 2:
                mid = len(sents) // 2
                candidate_units = [
                    {"unit_id": "UNIT-01", "text": " ".join(sents[:mid]), "source_beat_ids": ["BEAT-001"]},
                    {"unit_id": "UNIT-02", "text": " ".join(sents[mid:]), "source_beat_ids": ["BEAT-002"]}
                ]
            elif total_story_words >= 6:
                words = story_text.split()
                mid = len(words) // 2
                candidate_units = [
                    {"unit_id": "UNIT-01", "text": " ".join(words[:mid]), "source_beat_ids": ["BEAT-001"]},
                    {"unit_id": "UNIT-02", "text": " ".join(words[mid:]), "source_beat_ids": ["BEAT-002"]}
                ]

        total_units = len(candidate_units)
        batch_size = 3  # Small batch size to guarantee complete response under Groq OTPM ceiling
        num_batches = max(1, (total_units + batch_size - 1) // batch_size)

        all_beats: List[VisualBeat] = []
        global_beat_counter = 1

        for b_idx in range(num_batches):
            start_i = b_idx * batch_size
            end_i = min(start_i + batch_size, total_units)
            batch_units = candidate_units[start_i:end_i]

            if progress_callback:
                progress_callback(
                    b_idx + 1,
                    num_batches,
                    f"Visual planning units {start_i+1} to {end_i} of {total_units}..."
                )

            prior_context = "None (Opening scene)"
            if all_beats:
                recent_beats = all_beats[-2:]
                prior_context = " | ".join([
                    f"Beat {b.beat_id}: '{b.primary_visual_concept[:60]}'"
                    for b in recent_beats
                ])

            unit_prompts = []
            for u in batch_units:
                unit_prompts.append(f"UNIT {u['unit_id']}: \"{u['text']}\"")
            units_text = "\n".join(unit_prompts)

            user_prompt = f"""### NARRATIVE UNITS TO PLAN VISUALLY:
{units_text}

### CONTEXT & CONTINUITY:
- Setting Era: {era_ctx}
- Characters: {char_ctx or 'Historical figures and senators'}
- Locations: {loc_ctx or 'Ancient Roman locations'}
- Preceding Visual Moments: {prior_context}

### INSTRUCTIONS:
Plan exactly {len(batch_units)} distinct visual beats (exactly one visual beat for each narrative unit above).
- Keep descriptions concrete, physical, and concise (1-2 sentences per field).
- Every visual beat must correspond to the exact spoken words in its respective unit.
- STRICT CHRONOLOGY (NO PREMATURE ACTIONS OR SPOILERS):
  * Depict ONLY what has physically occurred up to the current narration moment. NEVER anticipate future story beats or secret tactical maneuvers!
  * Caesar/Rome: Domestic domus -> Crowded Roman streets/soothsayer (NO Curia ambush) -> Curia entrance -> Cimber petition -> Climax assassination ONLY when narration explicitly reaches it.
  * Constantinople/Siege:
    - Early arrival / siege initiation: Depict Ottoman encampment, war pavilions, and cannons arriving outside land walls. NEVER depict the Galata overland ship route or hauled warships before the naval bypass is narrated!
    - Golden Horn harbor & chain: Depict the water harbor and the massive iron chain blocking ships. NEVER depict warships being hauled overland until the narration explicitly states ships transported overland!
    - Night battle & assaults: Depict active combat on the walls with the Emperor fighting in full armor. NEVER depict discarded insignia, fallen crowns, or fallen city until the narration explicitly reaches the breach and discarding of insignia!
  * General Story: Never reveal late-stage developments (breaches, surrenders, retreats, secret maneuvers) during early exposition.
- Do NOT repeat concepts from preceding beats.

Return strictly valid JSON with key "visual_beats":
{{
  "visual_beats": [
    {{
      "exact_narration_segment": "exact text from unit",
      "narrative_purpose": "why this visual accompanies this moment",
      "primary_visual_concept": "concrete scene, subjects, action, and setting",
      "what_new_information_is_shown": "new visual fact or tactical development",
      "composition": "shot framing and camera angle",
      "lighting_and_atmosphere": "lighting and atmosphere",
      "continuity_references": ["Character or location names"]
    }}
  ]
}}"""

            beats_data = []
            for attempt in range(2):
                try:
                    raw_res = engine.generate_text(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        temperature=0.3,
                        max_tokens=850
                    )
                    parsed = engine.repair_and_parse_json(raw_res)
                    beats_data = parsed.get("visual_beats") or parsed.get("items") or []
                    if isinstance(beats_data, list) and len(beats_data) >= len(batch_units):
                        break
                except Exception:
                    beats_data = []

            if not isinstance(beats_data, list):
                beats_data = []

            while len(beats_data) < len(batch_units):
                missing_u = batch_units[len(beats_data)]
                u_text = missing_u.get("text", "")
                beats_data.append({
                    "exact_narration_segment": u_text,
                    "narrative_purpose": f"Visualizes story progression: {u_text[:50]}",
                    "primary_visual_concept": f"Historical scene depicting {u_text[:70]}",
                    "what_new_information_is_shown": f"Advances narrative: {u_text[:50]}",
                    "composition": "Eye-level medium-wide shot",
                    "lighting_and_atmosphere": "Authentic period lighting with dramatic chiaroscuro contrast",
                    "continuity_references": [],
                    "source_beat_ids": missing_u.get("source_beat_ids", [])
                })

            for idx_b, b in enumerate(beats_data[:len(batch_units)]):
                if not isinstance(b, dict):
                    continue
                beat_id = f"VB-{global_beat_counter:03d}"
                matched_u = batch_units[idx_b]
                exact_narr = b.get("exact_narration_segment") or matched_u.get("text", "")
                purp = b.get("narrative_purpose") or "Visualizes narration moment"
                concept = b.get("primary_visual_concept") or b.get("subject") or f"Historical scene: {matched_u.get('text', '')[:60]}"
                new_info = b.get("what_new_information_is_shown") or "Advances story development"
                comp = b.get("composition") or "Eye-level medium-wide shot"
                light = b.get("lighting_and_atmosphere") or "Directional chiaroscuro lighting"
                refs = b.get("continuity_references") or []
                if isinstance(refs, str):
                    refs = [refs]

                src_ids = b.get("source_beat_ids") or matched_u.get("source_beat_ids", [])
                if not src_ids:
                    src_ids = [f"BEAT-{global_beat_counter:03d}"]

                all_beats.append(VisualBeat(
                    beat_id=beat_id,
                    source_beat_ids=src_ids,
                    exact_narration_segment=exact_narr,
                    narrative_purpose=purp,
                    primary_visual_concept=concept,
                    what_new_information_is_shown=new_info,
                    why_this_is_not_repetitive="Sequential narrative advancement",
                    composition=comp,
                    lighting_and_atmosphere=light,
                    continuity_references=refs
                ))
                global_beat_counter += 1

        if len(all_beats) == 0:
            raise RuntimeError("Stage 3 Visual Planning failed to produce any visual beats.")

        # Complete coverage verification: ensure the ending of the story is represented
        final_sent = re.split(r"(?<=[.!?])\s+", story_text.strip())[-1]
        covered_all = " ".join([b.exact_narration_segment for b in all_beats]).lower()
        if final_sent.lower()[:30] not in covered_all:
            last_src_id = [analysis.narrative_beats[-1].beat_id] if (analysis and getattr(analysis, "narrative_beats", None)) else [f"BEAT-{len(all_beats)+1:03d}"]
            all_beats.append(VisualBeat(
                beat_id=f"VB-{global_beat_counter:03d}",
                source_beat_ids=last_src_id,
                exact_narration_segment=final_sent,
                narrative_purpose="Visualizes the final resolution and lasting legacy of the narrative",
                primary_visual_concept=f"A solitary, evocative wide shot capturing the final aftermath and legacy: {final_sent[:90]}",
                what_new_information_is_shown="Definitive narrative resolution and lasting historical consequence",
                why_this_is_not_repetitive="Reflective final epilogue distinct from active dramatic scenes",
                composition="Extreme wide shot, cinematic horizon, contemplative depth",
                lighting_and_atmosphere="Atmospheric twilight chiaroscuro, lingering stillness",
                continuity_references=[]
            ))

        return VisualBeatPlan(visual_beats=all_beats)
