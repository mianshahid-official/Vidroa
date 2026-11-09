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


FIXED_BEAT_TOKENS = 230
JSON_SCAFFOLDING_TOKENS = 80


def derive_stage3_token_budget(
    unit_text: str = "",
    max_cap: int = 950,
    fixed_beat_tokens: int = FIXED_BEAT_TOKENS,
    json_scaffolding: int = JSON_SCAFFOLDING_TOKENS
) -> int:
    """
    Derives output token budget for Stage 3 Visual Planning (1 beat per request).
    Budget = 80 scaffolding + FIXED_BEAT_TOKENS + segment cost.
    - FIXED_BEAT_TOKENS: Measured from real beats in repo tests = 230 tokens
      (non-segment fields: purpose, concept, new_info, composition, lighting, references + JSON syntax).
    - Segment cost: ceil(unit words * 1.33) covering model echoing the full unit text in exact_narration_segment.
    Clamped to effective max_cap with floor at min(350, max_cap).
    """
    import math
    if isinstance(unit_text, int):
        words = unit_text * 30
    elif isinstance(unit_text, str):
        words = len(unit_text.split())
    else:
        words = 0

    segment_cost = math.ceil(words * 1.33)
    budget = json_scaffolding + fixed_beat_tokens + segment_cost
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
        all_beats: List[VisualBeat] = []
        global_beat_counter = 1

        for u_idx, unit in enumerate(candidate_units):
            if progress_callback:
                progress_callback(
                    u_idx + 1,
                    total_units,
                    f"Visual planning unit {u_idx + 1} of {total_units}: {unit['unit_id']}..."
                )

            eff_cap = engine.current_effective_max_tokens(baseline=950) if hasattr(engine, "current_effective_max_tokens") else 950

            beat = cls._plan_single_unit(
                engine=engine,
                system_prompt=system_prompt,
                unit=unit,
                era_ctx=era_ctx,
                char_ctx=char_ctx,
                loc_ctx=loc_ctx,
                all_beats=all_beats,
                pack=pack,
                subject_preset=subject_preset,
                eff_cap=eff_cap,
                allow_fill=allow_fill,
                beat_number=global_beat_counter
            )
            all_beats.append(beat)
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

    @staticmethod
    def _extract_beats_list(parsed: Any) -> List[Dict[str, Any]]:
        beats_data = []
        if isinstance(parsed, dict):
            beats_data = parsed.get("visual_beats") or parsed.get("items") or []
            if not beats_data and "primary_visual_concept" in parsed:
                beats_data = [parsed]
        elif isinstance(parsed, list):
            beats_data = parsed
        return [b for b in beats_data if isinstance(b, dict)]

    @staticmethod
    def _match_beats_to_units(beats_data: List[Dict[str, Any]], units: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Matches returned visual beats to narrative units by exact_narration_segment text alignment,
        falling back to sequence order if text matching is ambiguous.
        Guarantees returning exactly len(units) beats.
        """
        matched: List[Optional[Dict[str, Any]]] = [None] * len(units)
        used_indices = set()

        # Pass 1: exact or substring narration match
        for u_idx, u in enumerate(units):
            u_text = u.get("text", "").strip().lower()
            if not u_text:
                continue
            best_beat_idx = None
            best_score = 0
            for b_idx, b in enumerate(beats_data):
                if b_idx in used_indices or not isinstance(b, dict):
                    continue
                b_narr = (b.get("exact_narration_segment") or "").strip().lower()
                if not b_narr:
                    continue
                if b_narr in u_text or u_text in b_narr:
                    score = len(b_narr)
                    if score > best_score:
                        best_score = score
                        best_beat_idx = b_idx
            if best_beat_idx is not None:
                matched[u_idx] = beats_data[best_beat_idx]
                used_indices.add(best_beat_idx)

        # Pass 2: Word-overlap match
        for u_idx, u in enumerate(units):
            if matched[u_idx] is not None:
                continue
            u_text = u.get("text", "").strip().lower()
            u_words = set(re.findall(r'\b[a-z]{4,}\b', u_text))
            best_beat_idx = None
            best_overlap = 0
            for b_idx, b in enumerate(beats_data):
                if b_idx in used_indices or not isinstance(b, dict):
                    continue
                b_narr = (b.get("exact_narration_segment") or "").strip().lower()
                b_words = set(re.findall(r'\b[a-z]{4,}\b', b_narr))
                overlap = len(u_words & b_words)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_beat_idx = b_idx
            if best_beat_idx is not None and best_overlap > 0:
                matched[u_idx] = beats_data[best_beat_idx]
                used_indices.add(best_beat_idx)

        # Pass 3: Sequential fallback from remaining unused beats
        for u_idx, u in enumerate(units):
            if matched[u_idx] is not None:
                continue
            for b_idx, b in enumerate(beats_data):
                if b_idx not in used_indices and isinstance(b, dict):
                    matched[u_idx] = b
                    used_indices.add(b_idx)
                    break

        # Pass 4: Fallback by index or first beat
        for u_idx, u in enumerate(units):
            if matched[u_idx] is None:
                if u_idx < len(beats_data) and isinstance(beats_data[u_idx], dict):
                    matched[u_idx] = beats_data[u_idx]
                elif beats_data and isinstance(beats_data[0], dict):
                    matched[u_idx] = beats_data[0]
                else:
                    matched[u_idx] = {}

        return [b for b in matched if b is not None]

    @staticmethod
    def _create_visual_beat(
        beat_dict: Dict[str, Any],
        unit: Dict[str, Any],
        beat_number: int
    ) -> VisualBeat:
        beat_id = f"VB-{beat_number:03d}"
        exact_narr = beat_dict.get("exact_narration_segment") or unit.get("text", "")
        purp = beat_dict.get("narrative_purpose") or "Visualizes narration moment"
        concept = beat_dict.get("primary_visual_concept") or beat_dict.get("subject")
        if not concept:
            u_t = unit.get("text", "").strip()
            cw = [w for w in re.sub(r"[^\w\s]", "", u_t).split() if len(w) >= 4]
            concept = f"Concrete depiction of {', '.join(cw[:3])}: {u_t.rstrip('.')}."
        new_info = beat_dict.get("what_new_information_is_shown") or "Advances story development"
        comp = beat_dict.get("composition") or "Eye-level medium-wide shot"
        light = beat_dict.get("lighting_and_atmosphere") or "Directional chiaroscuro lighting"
        refs = beat_dict.get("continuity_references") or []
        if isinstance(refs, str):
            refs = [refs]

        src_ids = beat_dict.get("source_beat_ids") or unit.get("source_beat_ids", [])
        if not src_ids:
            src_ids = [f"BEAT-{beat_number:03d}"]

        return VisualBeat(
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
        )

    @staticmethod
    def _derive_grounded_beat(unit: Dict[str, Any], beat_number: int) -> VisualBeat:
        u_text = unit.get("text", "").strip()
        if not u_text:
            raise RuntimeError(f"Stage 3 planning failure: Unit {unit.get('unit_id')} has empty text.")
        u_words = [w for w in re.sub(r"[^\w\s]", "", u_text).split() if len(w) >= 4 and w.lower() not in {
            "that", "this", "with", "from", "into", "their", "have", "been", "were", "they", "there", "what", "when", "where", "which"
        }]
        if not u_words:
            raise RuntimeError(f"Stage 3 planning failure: Unit {unit.get('unit_id')} text '{u_text}' contains no groundable content.")
        core_focus = ", ".join(u_words[:4])
        grounded_concept = f"Concrete depiction of {core_focus} during narrative action: {u_text.rstrip('.')}."

        beat_dict = {
            "exact_narration_segment": u_text,
            "narrative_purpose": f"Visualizes story progression: {core_focus}",
            "primary_visual_concept": grounded_concept,
            "what_new_information_is_shown": f"Focuses narrative on {core_focus}",
            "composition": "Eye-level medium-wide shot",
            "lighting_and_atmosphere": "Authentic period lighting with dramatic chiaroscuro contrast",
            "continuity_references": [],
            "source_beat_ids": unit.get("source_beat_ids", [])
        }
        return Stage3VisualPlanner._create_visual_beat(beat_dict, unit, beat_number)

    @staticmethod
    def _build_user_prompt(
        units: List[Dict[str, Any]],
        era_ctx: str,
        char_ctx: str,
        loc_ctx: str,
        all_beats: List[VisualBeat],
        pack: Any,
        subject_preset: Optional[SubjectPreset]
    ) -> str:
        units_text = "\n".join([f"UNIT {u['unit_id']}: \"{u['text']}\"" for u in units])
        prior_context = "None (Opening scene)"
        if all_beats:
            recent_beats = all_beats[-5:]
            prior_context = " | ".join([
                f"Beat {b.beat_id}: '{b.primary_visual_concept}'"
                for b in recent_beats
            ])

        if len(units) == 1:
            plan_instruction = "Plan exactly 1 distinct visual beat (exactly one visual beat for the narrative unit above)."
        else:
            plan_instruction = f"Plan exactly {len(units)} distinct visual beats (exactly one visual beat for each narrative unit above)."

        return f"""### NARRATIVE UNITS TO PLAN VISUALLY:
{units_text}

### CONTEXT & CONTINUITY:
- Setting: {era_ctx}
- Characters: {char_ctx or 'Focal figures from narration'}
- Locations: {loc_ctx or 'Key locations from narration'}
- Preceding Visual Moments: {prior_context}

### INSTRUCTIONS:
{plan_instruction}
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

    @classmethod
    def _plan_single_unit(
        cls,
        engine: BaseInferenceEngine,
        unit: Dict[str, Any],
        system_prompt: str = "You are an expert visual director.",
        era_ctx: str = "",
        char_ctx: str = "",
        loc_ctx: str = "",
        all_beats: Optional[List[VisualBeat]] = None,
        pack: Any = None,
        subject_preset: Optional[SubjectPreset] = None,
        eff_cap: int = 950,
        allow_fill: bool = False,
        beat_number: int = 1,
        max_attempts: int = 2
    ) -> VisualBeat:
        if all_beats is None:
            all_beats = []

        user_prompt = cls._build_user_prompt(
            units=[unit],
            era_ctx=era_ctx,
            char_ctx=char_ctx,
            loc_ctx=loc_ctx,
            all_beats=all_beats,
            pack=pack,
            subject_preset=subject_preset
        )
        u_budget = derive_stage3_token_budget(unit.get("text", ""), max_cap=eff_cap)
        beats_data = []

        for attempt in range(max_attempts):
            try:
                raw_res = engine.generate_text(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=0.3,
                    max_tokens=u_budget
                )
                parsed = engine.repair_and_parse_json(raw_res)
                beats_data = cls._extract_beats_list(parsed)
                if len(beats_data) >= 1:
                    break
                else:
                    print(
                        f"[Stage3VisualPlanning] Loud Truncation Notice: Parsed {len(beats_data)} beats, "
                        f"expected 1 for unit {unit['unit_id']}. Attempting retry... (Attempt {attempt+1}/{max_attempts})"
                    )
            except Exception as err:
                print(f"[Stage3VisualPlanning] Generation error for unit {unit['unit_id']} on attempt {attempt+1}: {err}")
                beats_data = []

        if len(beats_data) >= 1:
            matched = cls._match_beats_to_units(beats_data, [unit])
            return cls._create_visual_beat(matched[0], unit, beat_number)

        print(
            f"[Stage3VisualPlanning] Warning: Batch incomplete. Expected 1 visual beat, "
            f"parsed {len(beats_data)} for unit {unit['unit_id']}."
        )
        if not allow_fill:
            raise RuntimeError(
                f"Stage 3 planning failure: Unit {unit['unit_id']} output truncated or incomplete "
                f"after retry (parsed {len(beats_data)} beats, expected 1). "
                f"Text: '{unit.get('text', '')[:60]}...'"
            )

        print(f"[Stage3VisualPlanning] Filling missing beat for unit {unit.get('unit_id')} via grounded derivation.")
        return cls._derive_grounded_beat(unit, beat_number)
