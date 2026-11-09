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
from app.models.presets import SubjectPreset
from backend.inference.engine import BaseInferenceEngine
from backend.pipeline.prompt_loader import load_system_prompt as _load_system_prompt
from backend.pipeline.story_pack import StoryPackManager


def load_system_prompt() -> str:
    return _load_system_prompt("stage3_visual_planning.txt")


def derive_stage3_token_budget(
    num_beats: int = 1,
    max_cap: int = 950,
    tokens_per_beat: int = 320,
    json_scaffolding: int = 80
) -> int:
    """
    Derives output token budget for Stage 3 Visual Planning.
    Real measured per-beat cost from 9-field schema with 50-60 word narration segments:
    - exact_narration_segment: ~70 tokens
    - primary_visual_concept: ~70 tokens
    - narrative_purpose + what_new_information_is_shown: ~60 tokens
    - composition + lighting_and_atmosphere + continuity_references: ~60 tokens
    - JSON field syntax & quotation marks: ~60 tokens
    Total measured per-beat cost: ~320 tokens (range 250-350 tokens).
    JSON scaffolding: ~80 tokens.
    For 1 beat: 80 + 320 = 400 tokens (fits comfortably under 950 cap and reduced 530 cap).
    Clamped to effective max_cap with floor at min(350, max_cap).
    """
    budget = json_scaffolding + (num_beats * tokens_per_beat)
    floor = min(350, max_cap)
    return min(max_cap, max(floor, budget))


class Stage3VisualPlanner:
    """Plans narration-aligned visual beats for the entire story using Groq."""

    @classmethod
    def execute(
        cls,
        engine: BaseInferenceEngine,
        story_text: str,
        analysis: ScriptAnalysis,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        subject_preset: Optional[SubjectPreset] = None,
        allow_fill: bool = False
    ) -> VisualBeatPlan:
        system_prompt = load_system_prompt()
        pack = StoryPackManager.match_pack(story_text)

        char_ctx = "; ".join([f"{c.name} ({c.role}): {c.appearance}" + (f", Costume: {c.costume}" if getattr(c, 'costume', None) else "") for c in analysis.continuity_bible.characters])
        loc_ctx = "; ".join([f"{l.name}: {l.description}" + (f", Environment: {l.environment_details}" if getattr(l, 'environment_details', None) else "") for l in analysis.continuity_bible.locations])
        era_ctx = analysis.historical_or_setting_period or (pack.period.get("era") if pack and pack.period else "Setting Period")

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
        # DEFECT C FIX: Exactly 1 beat per request, fixed. No batching, no exceptions.
        all_beats: List[VisualBeat] = []
        global_beat_counter = 1

        for u_idx, unit in enumerate(candidate_units):
            batch_units = [unit]

            if progress_callback:
                progress_callback(
                    u_idx + 1,
                    total_units,
                    f"Visual planning unit {u_idx + 1} of {total_units}: {unit['unit_id']}..."
                )

            prior_context = "None (Opening scene)"
            if all_beats:
                recent_beats = all_beats[-5:]
                prior_context = " | ".join([
                    f"Beat {b.beat_id}: '{b.primary_visual_concept}'"
                    for b in recent_beats
                ])

            user_prompt = f"""### NARRATIVE UNITS TO PLAN VISUALLY:
UNIT {unit['unit_id']}: "{unit['text']}"

### CONTEXT & CONTINUITY:
- Setting: {era_ctx}
- Characters: {char_ctx or 'Focal figures from narration'}
- Locations: {loc_ctx or 'Key locations from narration'}
- Preceding Visual Moments: {prior_context}

### INSTRUCTIONS:
Plan exactly 1 distinct visual beat (exactly one visual beat for the narrative unit above).
- Keep descriptions concrete, physical, and concise (1-2 sentences per field).
- Every visual beat must correspond to the exact spoken words in its respective unit.
- STRICT CHRONOLOGY (NO PREMATURE ACTIONS OR SPOILERS):
  * Depict ONLY what has physically occurred up to the current narration moment. NEVER anticipate future story beats or secret tactical maneuvers!
  * General Story: Never reveal late-stage developments (breaches, surrenders, retreats, secret maneuvers) during early exposition.{f"\n\n### STORY-SPECIFIC RULES:\n{pack.prompt_fragment}" if pack and pack.prompt_fragment else ""}{f"\n\n### SUBJECT RULES:\n{subject_preset.system_instructions}" if subject_preset and getattr(subject_preset, 'system_instructions', None) else ""}
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
            eff_cap = engine.current_effective_max_tokens(baseline=950) if hasattr(engine, "current_effective_max_tokens") else 950
            batch_budget = derive_stage3_token_budget(1, max_cap=eff_cap)

            for attempt in range(2):
                try:
                    raw_res = engine.generate_text(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        temperature=0.3,
                        max_tokens=batch_budget
                    )
                    parsed = engine.repair_and_parse_json(raw_res)
                    if isinstance(parsed, dict):
                        beats_data = parsed.get("visual_beats") or parsed.get("items") or []
                        if not beats_data and "primary_visual_concept" in parsed:
                            beats_data = [parsed]
                    elif isinstance(parsed, list):
                        beats_data = parsed

                    if isinstance(beats_data, list) and len(beats_data) >= 1:
                        if len(beats_data) > 1:
                            # If engine returned multiple beats (e.g. canned mock engine), select the one matching this unit
                            selected_beat = None
                            u_text_l = unit.get("text", "").lower()
                            for b in beats_data:
                                if isinstance(b, dict):
                                    b_narr = (b.get("exact_narration_segment") or "").lower()
                                    if b_narr and (b_narr in u_text_l or u_text_l in b_narr):
                                        selected_beat = b
                                        break
                            if selected_beat is None:
                                selected_beat = beats_data[u_idx] if u_idx < len(beats_data) else beats_data[0]
                            beats_data = [selected_beat]
                        break
                    else:
                        print(
                            f"[Stage3VisualPlanning] Loud Truncation Notice: Parsed {len(beats_data) if isinstance(beats_data, list) else 0} beats, "
                            f"expected 1 for unit {unit['unit_id']}. Attempting retry..."
                        )
                except Exception as err:
                    print(f"[Stage3VisualPlanning] Generation error on attempt {attempt+1} for unit {unit['unit_id']}: {err}")
                    beats_data = []

            if not isinstance(beats_data, list):
                beats_data = []

            if len(beats_data) < len(batch_units):
                missing_unit_ids = [u["unit_id"] for u in batch_units[len(beats_data):]]
                print(
                    f"[Stage3VisualPlanning] Warning: Batch incomplete. Expected {len(batch_units)} visual beats, "
                    f"parsed {len(beats_data)}. Missing units: {missing_unit_ids}."
                )
                if not allow_fill:
                    raise RuntimeError(
                        f"Stage 3 planning failure: Unit {unit['unit_id']} output truncated or incomplete "
                        f"after retry (parsed {len(beats_data)} beats, expected 1). "
                        f"Text: '{unit.get('text', '')[:60]}...'"
                    )

            while len(beats_data) < len(batch_units):
                missing_u = batch_units[len(beats_data)]
                print(f"[Stage3VisualPlanning] Filling missing beat for unit {missing_u.get('unit_id')} via grounded derivation.")
                u_text = missing_u.get("text", "").strip()
                if not u_text:
                    raise RuntimeError(f"Stage 3 planning failure: Unit {missing_u.get('unit_id')} has empty text.")
                u_words = [w for w in re.sub(r"[^\w\s]", "", u_text).split() if len(w) >= 4 and w.lower() not in {
                    "that", "this", "with", "from", "into", "their", "have", "been", "were", "they", "there", "what", "when", "where", "which"
                }]
                if not u_words:
                    raise RuntimeError(f"Stage 3 planning failure: Unit {missing_u.get('unit_id')} text '{u_text}' contains no groundable content.")
                core_focus = ", ".join(u_words[:4])
                grounded_concept = f"Concrete depiction of {core_focus} during narrative action: {u_text.rstrip('.')}."

                beats_data.append({
                    "exact_narration_segment": u_text,
                    "narrative_purpose": f"Visualizes story progression: {core_focus}",
                    "primary_visual_concept": grounded_concept,
                    "what_new_information_is_shown": f"Focuses narrative on {core_focus}",
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
                concept = b.get("primary_visual_concept") or b.get("subject")
                if not concept:
                    u_t = matched_u.get("text", "").strip()
                    cw = [w for w in re.sub(r"[^\w\s]", "", u_t).split() if len(w) >= 4]
                    concept = f"Concrete depiction of {', '.join(cw[:3])}: {u_t.rstrip('.')}."
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
