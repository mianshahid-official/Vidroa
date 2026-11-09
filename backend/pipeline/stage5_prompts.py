"""
Stage 5: Image Prompt Generation.
Translates scheduled visual scenes into production image generation prompts
honoring user-selected visual styles, continuity bibles, and narration synchronization.
Guarantees authoritative character faction coloring (e.g. Protagonist = RED, supporting/opposing = BLUE),
robust batching with per-scene retries, and zero pipeline scaffolding leakage.
"""
import json
import re
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable, Tuple
from app.models.planning import (
    ScriptAnalysis,
    ScheduledStoryboard,
    ScheduledScene,
    GeneratedPromptBatch,
    GeneratedPromptItem
)
from app.models.presets import VisualStylePreset, SubjectPreset
from app.models.scene import VisualScene
from backend.inference.engine import BaseInferenceEngine
from backend.pipeline.prompt_loader import load_system_prompt as _load_system_prompt
from backend.pipeline.story_pack import StoryPackManager, sanitize_stickman_prompt


def load_system_prompt() -> str:
    return _load_system_prompt("stage4_prompts.txt")


def resolve_stickman_characters(analysis: ScriptAnalysis, story_text: str = "") -> Tuple[str, List[str]]:
    """Resolves protagonist and supporting cast from character bible or active story pack."""
    chars = analysis.continuity_bible.characters if analysis and analysis.continuity_bible else []
    pack = StoryPackManager.match_pack(story_text)
    if pack and pack.faction_rules.get("protagonist_name"):
        return pack.faction_rules["protagonist_name"], pack.faction_rules.get("opponents", [])

    if chars:
        protagonist_name = chars[0].name
        other_names = [c.name for c in chars[1:]]
        return protagonist_name, other_names
    return "Protagonist", ["Supporting characters", "Crowd", "Citizens"]


def sanitize_action_summary(raw_summary: str, narration: str) -> str:
    """Strips internal planning tokens, brackets, and leaked pipeline tags."""
    clean = raw_summary.strip()
    clean = re.sub(r"\s*—\s*(Active progression|Consequential development|Establishing perspective):.*$", "", clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r"^(A wide, low|A split|A solitary, evocative wide shot)\s*—?\s*", "", clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r"\(Angle\s*\d+\)", "", clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r"\((Establishing development|Active progression|Dramatic consequence|Climax|Resolution)\)", "", clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r"\[.*?\]", "", clean).strip()
    
    if not clean or len(clean) < 6:
        clean = f"Visual depiction of {narration[:60]}"
    return clean


def derive_contextual_environment(narration: str, analysis: ScriptAnalysis, is_3d_stickman: bool = False) -> str:
    """Derives setting from narration and continuity location bible without generic templates."""
    narr_l = narration.lower()
    period = analysis.historical_or_setting_period if analysis else "Setting"
    pack = StoryPackManager.match_pack(narration)

    # 1. Match from location bible
    locations = analysis.continuity_bible.locations if analysis and analysis.continuity_bible else []
    if not locations and pack and pack.locations:
        locations = pack.locations
    for loc in locations:
        loc_name = getattr(loc, "name", "") if hasattr(loc, "name") else loc.get("name", "")
        loc_desc = getattr(loc, "description", "") if hasattr(loc, "description") else loc.get("environmental_features", "")
        if any(w in narr_l for w in loc_name.lower().split() if len(w) > 3):
            if is_3d_stickman:
                return f"Stylized 3D {loc_name} with {loc_desc[:60]} and smooth matte toy textures"
            return f"{loc_name} with {loc_desc[:80]}"

    # 2. Grounded derivation from narration nouns and setting period (zero generic templates)
    narr_clean = re.sub(r"[^\w\s]", "", narration)
    stop_words = {
        "the", "and", "with", "from", "into", "that", "this", "over", "under", "scene", "shot",
        "view", "camera", "showing", "depicting", "visual", "figure", "figures", "style", "animation",
        "stickman", "authentic", "damaged", "warm", "faded", "tones", "black", "sharp", "central",
        "animated", "stylized", "smooth", "strict", "human", "they", "their", "were", "been", "have",
        "about", "which", "where", "when", "there", "below", "above", "across", "along", "through",
        "then", "than", "these", "those", "them", "some", "such", "each", "more", "most", "also",
        "just", "only", "even", "once", "here", "ever", "very", "much"
    }
    content_nouns = [w for w in narr_clean.split() if len(w) >= 4 and w.lower() not in stop_words]
    if not content_nouns:
        raise RuntimeError(
            f"Stage 5 environment derivation failure: Narration '{narration[:60]}' contains no groundable content nouns. "
            f"Generic template fallback ('Authentic {period} setting') is strictly prohibited."
        )

    focal_nouns = ", ".join(content_nouns[:3])
    if is_3d_stickman:
        return f"Stylized 3D {period} environment focusing on {focal_nouns} with clean geometric shapes"
    return f"{period} environment featuring {focal_nouns} with grounded atmospheric lighting"


def derive_safe_batch_size(
    requested_batch_size: int = 2,
    max_output_tokens: int = 950,
    estimated_tokens_per_prompt: int = 350,
    json_scaffolding_tokens: int = 100
) -> int:
    """
    Derives safe batch size from real output token budget.
    Under Groq Free Tier (950 token ceiling for Qwen models):
    - Each detailed prompt requires ~250-350 tokens.
    - Scaffolding requires ~100 tokens.
    - 2 prompts: ~800 tokens (safe within 950 cap).
    - 4 prompts: ~1500 tokens (guaranteed truncation at 950 cap).
    Therefore, safe batch size is dynamically capped at 2 under the 950 ceiling.
    """
    usable_tokens = max(0, max_output_tokens - json_scaffolding_tokens)
    calculated_capacity = max(1, usable_tokens // max(1, estimated_tokens_per_prompt))
    return max(1, min(requested_batch_size, calculated_capacity))


class Stage5PromptGenerator:
    """Generates rich image generation prompts adhering to user style and continuity."""

    @classmethod
    def execute(
        cls,
        engine: BaseInferenceEngine,
        scheduled_storyboard: ScheduledStoryboard,
        analysis: ScriptAnalysis,
        style_preset: Optional[VisualStylePreset] = None,
        custom_style: Optional[str] = None,
        batch_size: int = 2,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[VisualScene]:
        system_prompt = load_system_prompt()
        scenes = scheduled_storyboard.scenes
        total_scenes = len(scenes)

        if total_scenes == 0:
            return []

        # Build style guidance string
        style_name = style_preset.name if style_preset else "3D Red & Blue Stickman Animation"
        style_instructions = style_preset.system_instructions if style_preset else (
            "Stylized 3D stick figures with smooth spherical heads. NO human faces, NO beards, NO realistic clothing."
        )
        if custom_style:
            style_instructions += f"\nCustom Style Directive: {custom_style}"

        is_3d_red_blue = (style_preset.id if style_preset else "") in ("3d_red_blue_stickman", "red_blue_stickman_3d") or "3d red & blue" in style_name.lower() or "red & blue" in style_name.lower()
        is_general_stickman = any(k in (style_preset.id if style_preset else "").lower() or k in style_name.lower() for k in ["stickman", "stick_figure"])

        # Determine authoritative character color identity
        story_text = " ".join([s.narration_text for s in scenes]) if scenes else ""
        active_pack = StoryPackManager.match_pack(story_text)
        protagonist_name, supporting_names = resolve_stickman_characters(analysis, story_text)

        stickman_faction_rules = ""
        if is_3d_red_blue:
            proto_prop = (active_pack.faction_rules.get("protagonist_prop") if active_pack and active_pack.faction_rules else "")
            proto_prop_clause = f" (with {proto_prop})" if proto_prop else ""
            pack_frag = f"\n{active_pack.prompt_fragment}\n" if active_pack and active_pack.prompt_fragment else ""

            stickman_faction_rules = f"""
### MANDATORY 3D RED & BLUE STICKMAN ANATOMY & FACTION COLOR DIRECTIVES:
1. ZERO HUMAN ANATOMY & NO FACIAL FEATURES:
   - Characters must NEVER have realistic human faces, eyes, noses, mouths, beards, mustaches, human hair, or skin textures!
   - Every human is a simplified 3D stick figure with a smooth featureless spherical head and cylindrical limbs.
   - ZERO realistic cloth fabrics, embroidered silk caftans, velvet robes, tunics, or realistic armor. Bodies are solid matte colored 3D stick figures.
2. STRICT AUTHORITATIVE CHARACTER COLOR IDENTITY (PERSISTENT & IMMUTABLE):
   - PRIMARY PROTAGONIST ({protagonist_name}) = 100% EXCLUSIVELY SOLID BRIGHT RED 3D STICK FIGURE{proto_prop_clause}.
   - ALL OTHER CHARACTERS ({", ".join(supporting_names) or "supporting cast, crowd, citizens"}) = 100% EXCLUSIVELY SOLID BLUE 3D STICK FIGURES.
   - ABSOLUTE RULE: {protagonist_name} MUST ALWAYS BE RED. {protagonist_name} NEVER becomes blue!
   - Opposing and supporting figures MUST ALWAYS BE BLUE. They NEVER become red!
   - Faction color is bound strictly to character IDENTITY, never narrative aggression or location!
3. RENDER STYLE:
   - Stylized 3D CGI toy universe, smooth rounded geometry, matte plastic/clay surfaces, warm volumetric lighting, zero photorealism.{pack_frag}
"""

        # Build character context for prompt
        if is_3d_red_blue:
            proto_prop = (active_pack.faction_rules.get("protagonist_prop") if active_pack and active_pack.faction_rules else "")
            proto_prop_clause = f", {proto_prop}" if proto_prop else ""
            char_ctx = (
                f"{protagonist_name}: Solid bright red 3D stick figure with smooth featureless sphere head{proto_prop_clause}, cylindrical limbs. "
                f"Other figures ({', '.join(supporting_names[:5])}): Solid blue 3D stick figures with smooth featureless sphere heads, cylindrical limbs."
            )
        elif is_general_stickman:
            char_ctx = f"Characters: Stylized stickman characters adhering to {style_name}. Keep character clothing, gear, and expressions faithful to the story."
        else:
            char_ctx = "; ".join([f"{c.name}: {c.appearance}, wearing {c.costume}" for c in analysis.continuity_bible.characters[:6]])
            
        loc_ctx = "; ".join([f"{l.name}: {l.description}" for l in analysis.continuity_bible.locations[:4]])

        output_visual_scenes: List[VisualScene] = []
        effective_batch_size = derive_safe_batch_size(
            requested_batch_size=batch_size,
            max_output_tokens=950
        )
        num_batches = max(1, (total_scenes + effective_batch_size - 1) // effective_batch_size)

        for b_idx in range(num_batches):
            start_i = b_idx * effective_batch_size
            end_i = min(start_i + effective_batch_size, total_scenes)
            batch_scenes = scenes[start_i:end_i]

            if progress_callback:
                progress_callback(
                    b_idx + 1,
                    num_batches,
                    f"Generating prompt batch {b_idx + 1} of {num_batches} (scenes {start_i+1}–{end_i} of {total_scenes})..."
                )

            # Format batch payload for Groq
            batch_descriptions = []
            for s in batch_scenes:
                clean_concept = sanitize_action_summary(s.visual_summary, s.narration_text)
                batch_descriptions.append({
                    "scene_id": s.scene_id,
                    "narration": s.narration_text,
                    "visual_concept": clean_concept,
                    "timing": f"{s.start_time:.1f}s - {s.end_time:.1f}s ({s.duration:.1f}s)"
                })

            if is_3d_red_blue:
                continuity_block = f"""### CONTINUITY CONTEXT:
- Characters: {char_ctx}
- Protagonist (RED): {protagonist_name}
- Supporting Figures (BLUE): {", ".join(supporting_names) or "Supporting figures"}
- Settings: {loc_ctx or 'Stylized 3D settings'}
- Period: {analysis.historical_or_setting_period}"""
            else:
                continuity_block = f"""### CONTINUITY CONTEXT:
- Characters: {char_ctx or 'Historical figures'}
- Settings: {loc_ctx or f'{analysis.historical_or_setting_period} locations'}
- Period: {analysis.historical_or_setting_period}"""

            user_prompt = f"""### USER-SELECTED VISUAL STYLE:
Style: {style_name}
{style_instructions}
{stickman_faction_rules}

{continuity_block}

### SCENES TO WRITE PROMPTS FOR (BATCH {b_idx + 1} OF {num_batches}):
{json.dumps(batch_descriptions, indent=2)}

### INSTRUCTIONS:
For each scene in this batch, write a standalone, vivid, production-ready image generation prompt.
Strict rules:
1. Ground the visual in the exact narration moment. Depict only what has occurred so far (NO premature actions or spoilers).
2. If style is 3D Red & Blue Stickman: Strictly follow character colors ({protagonist_name} = RED, supporting/opposing figures = BLUE).
3. If style is photographic, cinematic, or historical (NOT stickman): Characters must be realistic human figures in authentic period attire. ZERO stick figures.
4. Output concise, vivid prompts ready for image generation with composition, environment, subjects, and action.
5. Do NOT output raw metadata tags like "Action:", "Setting:", or "Active progression:". Write natural English descriptions.

Return strictly valid JSON:
{{
  "prompts": [
    {{
      "scene_id": "001",
      "prompt": "Full standalone image generation prompt with concrete subjects, action, setting, lighting, and composition...",
      "subject": "Primary subject",
      "composition": "Shot framing"
    }}
  ]
}}"""

            def _extract_prompt_text(item: Any) -> str:
                if not isinstance(item, dict):
                    return ""
                val = (
                    item.get("prompt") or
                    item.get("final_image_prompt") or
                    item.get("image_prompt") or
                    ""
                )
                return str(val).strip()

            def _extract_scene_id(item: Any) -> str:
                if not isinstance(item, dict):
                    return ""
                val = (
                    item.get("scene_id") or
                    item.get("id") or
                    item.get("visual_beat_id") or
                    ""
                )
                return str(val).strip().lstrip("#")

            p_items = []
            max_attempts = 2
            # Derive token budget for this specific batch (prompt tokens + JSON scaffolding)
            batch_token_budget = min(950, max(450, len(batch_scenes) * 350 + 100))
            prompt_by_id: Dict[str, Any] = {}

            for attempt in range(max_attempts):
                try:
                    raw_res = engine.generate_text(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        temperature=0.3,
                        max_tokens=batch_token_budget
                    )
                    parsed = engine.repair_and_parse_json(raw_res)
                    if isinstance(parsed, dict):
                        p_items = parsed.get("prompts") or parsed.get("items") or parsed.get("scenes") or []
                    elif isinstance(parsed, list):
                        p_items = parsed

                    # Map parsed responses to scene IDs
                    if isinstance(p_items, list):
                        for item in p_items:
                            if isinstance(item, dict):
                                sid = _extract_scene_id(item)
                                p_text = _extract_prompt_text(item)
                                if sid and p_text:
                                    prompt_by_id[sid] = item
                                    m = re.search(r'\d+', sid)
                                    if m:
                                        prompt_by_id[str(int(m.group()))] = item

                    # Check if all scenes in this batch are already satisfied
                    all_present = True
                    for s in batch_scenes:
                        sid_clean = s.scene_id.lstrip("#")
                        m_s = re.search(r'\d+', s.scene_id)
                        num_key = str(int(m_s.group())) if m_s else sid_clean
                        matched = prompt_by_id.get(sid_clean) or prompt_by_id.get(s.scene_id) or prompt_by_id.get(num_key)
                        if not matched or not _extract_prompt_text(matched):
                            all_present = False
                            break
                    if all_present:
                        break
                except Exception as err:
                    print(f"[Stage5Prompts] Batch {b_idx + 1} attempt {attempt + 1} notice: {err}")
                    time.sleep(1.0)

            # Detect truncated or missing scenes in this batch
            missing_scenes = []
            for s in batch_scenes:
                sid_clean = s.scene_id.lstrip("#")
                m_s = re.search(r'\d+', s.scene_id)
                num_key = str(int(m_s.group())) if m_s else sid_clean
                matched = prompt_by_id.get(sid_clean) or prompt_by_id.get(s.scene_id) or prompt_by_id.get(num_key)
                if not matched or not _extract_prompt_text(matched):
                    missing_scenes.append(s)

            if missing_scenes:
                missing_ids = [s.scene_id for s in missing_scenes]
                print(
                    f"[Stage5Prompts] WARNING: Batch {b_idx + 1} output incomplete/truncated! "
                    f"Requested {len(batch_scenes)} scenes, successfully parsed {len(batch_scenes) - len(missing_scenes)}. "
                    f"Missing/truncated scenes: {missing_ids}. Initiating targeted selective retry for missing scenes only."
                )

            # Targeted selective retry ONLY for missing or truncated scenes
            for s in missing_scenes:
                try:
                    clean_concept = sanitize_action_summary(s.visual_summary, s.narration_text)
                    if is_3d_red_blue:
                        char_directive_single = f"Generate a single production image prompt strictly adhering to {protagonist_name} = RED 3D stickman and others = BLUE 3D stickmen."
                    elif is_general_stickman:
                        char_directive_single = f"Generate a single production image prompt adhering to {style_name}. Keep character visual design strictly conforming to {style_name}."
                    else:
                        char_directive_single = f"Generate a single production image prompt adhering to {style_name}. Ground characters in period-accurate human attire from the Character Bible. ZERO stick figures."

                    single_prompt = f"""### VISUAL STYLE: {style_name}
{stickman_faction_rules}

### SCENE TO PROMPT:
- Scene ID: {s.scene_id}
- Narration: \"{s.narration_text}\"
- Visual Concept: {clean_concept}
- Setting: {derive_contextual_environment(s.narration_text, analysis, is_3d_stickman=is_general_stickman)}

{char_directive_single}
Return JSON: {{"scene_id": "{s.scene_id}", "prompt": "full prompt text", "subject": "{clean_concept}", "composition": "Eye-level medium shot"}}"""

                    single_raw = engine.generate_text(
                        prompt=single_prompt,
                        system_prompt=system_prompt,
                        temperature=0.3,
                        max_tokens=450
                    )
                    single_parsed = engine.repair_and_parse_json(single_raw)
                    if isinstance(single_parsed, dict):
                        single_p = _extract_prompt_text(single_parsed)
                        if not single_p and "prompts" in single_parsed and isinstance(single_parsed["prompts"], list) and single_parsed["prompts"]:
                            single_p = _extract_prompt_text(single_parsed["prompts"][0])
                            single_parsed = single_parsed["prompts"][0]
                        elif not single_p and "items" in single_parsed and isinstance(single_parsed["items"], list) and single_parsed["items"]:
                            single_p = _extract_prompt_text(single_parsed["items"][0])
                            single_parsed = single_parsed["items"][0]
                        if single_p:
                            sid_clean = s.scene_id.lstrip("#")
                            prompt_by_id[sid_clean] = single_parsed
                            m_s = re.search(r'\d+', s.scene_id)
                            if m_s:
                                prompt_by_id[str(int(m_s.group()))] = single_parsed
                            print(f"[Stage5Prompts] Successfully recovered scene #{s.scene_id} via selective retry.")
                except Exception as e_single:
                    print(f"[Stage5Prompts] Selective retry error for scene #{s.scene_id}: {e_single}")

            # Assemble visual scenes for this batch
            for s in batch_scenes:
                sid_clean = s.scene_id.lstrip("#")
                m_s = re.search(r'\d+', s.scene_id)
                num_key = str(int(m_s.group())) if m_s else sid_clean

                matched = prompt_by_id.get(sid_clean) or prompt_by_id.get(s.scene_id) or prompt_by_id.get(num_key)
                prompt_str = _extract_prompt_text(matched) if matched else ""

                # Softened F1 fail-hard: flag per-scene instead of aborting the entire job
                if not matched or not prompt_str:
                    err_msg = (
                        f"PROMPT_GENERATION_FAILED: Scene #{s.scene_id} output was missing, "
                        f"truncated, or malformed after batch and selective retry attempts."
                    )
                    print(f"[Stage5Prompts] ERROR: {err_msg} Flagging scene without generic fallback substitution.")
                    v_scene = VisualScene(
                        scene_id=s.scene_id,
                        index=getattr(s, "index", None),
                        start=s.start_time,
                        end=s.end_time,
                        duration=s.duration,
                        start_word_index=getattr(s, "source_word_start", getattr(s, "start_word_index", None)),
                        end_word_index=getattr(s, "source_word_end", getattr(s, "end_word_index", None)),
                        narration_excerpt=s.narration_text,
                        visual_subject=s.visual_summary or "Unassigned Subject",
                        action=s.visual_summary or "",
                        environment=derive_contextual_environment(s.narration_text, analysis, is_3d_stickman=is_general_stickman),
                        composition="Eye-level medium shot",
                        emotional_tone="Dramatic",
                        historical_confidence="uncertain",
                        prompt="",  # Explicitly empty — NEVER generic fallback!
                        continuity_checklist=[],
                        source_narrative_beat_ids=getattr(s, "source_narrative_beat_ids", []),
                        source_visual_beat_ids=getattr(s, "source_visual_beat_ids", []),
                        character_ids=getattr(s, "character_ids", []),
                        location_id=getattr(s, "location_id", None),
                        chronological_order=getattr(s, "chronological_order", None),
                        is_validated=False,
                        validation_notes=err_msg
                    )
                    output_visual_scenes.append(v_scene)
                    continue

                p_text = prompt_str
                comp = matched.get("composition") or matched.get("shot_type") or "Eye-level medium shot"
                env = matched.get("environment") or matched.get("setting") or derive_contextual_environment(s.narration_text, analysis, is_3d_stickman=is_general_stickman)
                subj = matched.get("subject") or matched.get("visual_details_added") or sanitize_action_summary(s.visual_summary, s.narration_text)

                # =============================================================
                # POST-PROCESSING SANITIZATION (Authoritative Rule Enforcement)
                # =============================================================
                if is_3d_red_blue:
                    p_text = sanitize_stickman_prompt(
                        prompt_text=p_text,
                        protagonist_name=protagonist_name,
                        supporting_names=supporting_names,
                        active_pack=active_pack,
                        narration_text=s.narration_text
                    )
                else:
                    # NON-RED-BLUE STYLES (Century-Old Photograph, 3D Stickman, 2D Stickman, Black & White, Vintage, etc.):
                    # 1. Clean up any leaked pipeline scaffolding
                    p_text = re.sub(r"\b(Active progression|Consequential development|Establishing perspective):\s*", "", p_text)
                    p_text = re.sub(r"^(A wide, low|A split|A solitary, evocative wide shot)\s*—?\s*", "", p_text)
                    p_text = re.sub(r"Setting:\s*Fortified historical cityscape and defensive ramparts\.?", "", p_text)
                    p_text = re.sub(r"Setting:\s*Fortified historical setting\.?", "", p_text)
                    p_text = re.sub(r"\s+", " ", p_text).strip()

                    # 2. Strict Stickman Removal: ONLY purge stickman references if this is a non-stickman style
                    if not is_general_stickman:
                        p_text = re.sub(r"\ba\s+(red|blue)\s+3d\s+stickman\s+figure\s+representing\b", "historical figure depicting", p_text, flags=re.IGNORECASE)
                        p_text = re.sub(r"\b(solid\s+)?(bright\s+)?(red|blue)\s+3d\s+stick\s*(man|figure|figures|men)\b", "historical figures in period attire", p_text, flags=re.IGNORECASE)
                        p_text = re.sub(r"\b3d\s+stick\s*(man|figure|figures|men)\b", "figures in period attire", p_text, flags=re.IGNORECASE)
                        p_text = re.sub(r"\bfeatureless\s+spherical\s+(3d\s+)?stickman\s+head\b", "period headwear", p_text, flags=re.IGNORECASE)
                        p_text = re.sub(r"\bmonochromatic palette with distinct red and blue character accents\b", "monochromatic archival palette", p_text, flags=re.IGNORECASE)
                        p_text = re.sub(r"\bgeometric red body\b", "period military attire", p_text, flags=re.IGNORECASE)
                        p_text = re.sub(r"\bblank red surface\b", "weathered determined expression", p_text, flags=re.IGNORECASE)
                        p_text = re.sub(r"\s+", " ", p_text).strip()

                v_scene = VisualScene(
                    scene_id=s.scene_id,
                    index=getattr(s, "index", None),
                    start=s.start_time,
                    end=s.end_time,
                    duration=s.duration,
                    start_word_index=getattr(s, "source_word_start", getattr(s, "start_word_index", None)),
                    end_word_index=getattr(s, "source_word_end", getattr(s, "end_word_index", None)),
                    narration_excerpt=s.narration_text,
                    visual_subject=subj,
                    action=s.visual_summary,
                    environment=env,
                    composition=comp,
                    emotional_tone="Dramatic",
                    historical_confidence="well_supported_reconstruction",
                    prompt=p_text,
                    continuity_checklist=[],
                    source_narrative_beat_ids=getattr(s, "source_narrative_beat_ids", []),
                    source_visual_beat_ids=getattr(s, "source_visual_beat_ids", []),
                    character_ids=getattr(s, "character_ids", []),
                    location_id=getattr(s, "location_id", None),
                    chronological_order=getattr(s, "chronological_order", None),
                    validation_notes=None
                )
                output_visual_scenes.append(v_scene)

        return output_visual_scenes
