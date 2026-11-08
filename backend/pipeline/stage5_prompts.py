"""
Stage 5: Image Prompt Generation.
Translates scheduled visual scenes into production image generation prompts
honoring user-selected visual styles, continuity bibles, and narration synchronization.
Guarantees authoritative character faction coloring (e.g. Caesar = RED, conspirators = BLUE),
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


def load_system_prompt() -> str:
    prompt_file = Path("config/system_prompts/stage4_prompts.txt")
    if prompt_file.exists():
        try:
            return prompt_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return "You are a master AI image prompt architect. Generate detailed, style-compliant image prompts."


def resolve_stickman_characters(analysis: ScriptAnalysis) -> Tuple[str, List[str]]:
    """
    Identifies the primary protagonist (who must be RED) and supporting characters (BLUE).
    In 3D Red & Blue Stickman animation:
    - Primary protagonist (Caesar) = SOLID BRIGHT RED 3D STICKMAN
    - All other characters (Brutus, Cassius, Casca, Tillius Cimber, Antony, Calpurnia, senators, citizens) = SOLID BLUE 3D STICKMEN
    """
    chars = analysis.continuity_bible.characters if analysis and analysis.continuity_bible else []
    protagonist_name = "Caesar"
    
    # Check if there is an explicit protagonist or matching keywords
    proto_keywords = ["caesar", "julius", "dictator", "protagonist", "emperor", "sultan", "lead"]
    found = None
    for c in chars:
        c_role = (c.role or "").lower()
        c_name = c.name.lower()
        if any(k in c_role or k in c_name for k in proto_keywords):
            found = c.name
            break
            
    if found:
        protagonist_name = found
    elif chars:
        protagonist_name = chars[0].name

    other_names = [c.name for c in chars if c.name.lower() != protagonist_name.lower()]
    return protagonist_name, other_names


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
    """Derives period-appropriate setting from narration text without hardcoded ramparts."""
    narr_l = narration.lower()
    period = analysis.historical_or_setting_period if analysis else "Historical Setting"

    if any(w in narr_l for w in ["senate", "curia", "pompey", "magistrate", "petition", "toga", "chamber", "throne", "gold chair"]):
        if is_3d_stickman:
            return "Interior of the grand Roman Senate Curia with smooth rounded marble columns and matte stone floor"
        return "Interior of the grand Roman Senate Curia with towering marble columns and classical stone floor"
    elif any(w in narr_l for w in ["street", "forum", "crowd", "litter", "soothsayer", "road", "walk", "avenue", "sprawling"]):
        if is_3d_stickman:
            return "Stylized 3D Roman forum stone avenue with rounded blocky insulae buildings and matte clay textures"
        return "Ancient Roman forum stone avenue with classical insulae buildings and cobblestone paving"
    elif any(w in narr_l for w in ["nightmare", "domus", "house", "calpurnia", "bed", "morning", "gable"]):
        if is_3d_stickman:
            return "Inside the private domus residence with stylized classical Roman architecture and soft morning lighting"
        return "Inside the private domus residence with classical Roman domestic architecture and soft morning light"
    elif any(w in narr_l for w in ["rubicon", "forces", "battle", "general", "triumph"]):
        return "Panoramic vista of classical territories with atmospheric horizon"
    elif any(w in narr_l for w in ["constantinople", "theodosian", "byzantine", "bosphorus", "golden horn", "sultan", "mehmed"]):
        if is_3d_stickman:
            return "Stylized 3D 15th-century stone and brick Theodosian fortifications of Constantinople"
        return "Massive 15th-century stone and brick Theodosian fortifications of Constantinople"
    else:
        if is_3d_stickman:
            return f"Stylized 3D {period} setting with rounded geometric classical stone structures"
        return f"Authentic {period} setting with period architecture and atmospheric lighting"


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
        batch_size: int = 4,
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

        is_3d_stickman = any(k in style_name.lower() or k in (style_preset.id if style_preset else "").lower() for k in ["stickman", "3d red & blue", "red_blue"])

        # Determine authoritative character color identity
        protagonist_name, supporting_names = resolve_stickman_characters(analysis)

        stickman_faction_rules = ""
        if is_3d_stickman:
            stickman_faction_rules = f"""
### MANDATORY 3D RED & BLUE STICKMAN ANATOMY & FACTION COLOR DIRECTIVES:
1. ZERO HUMAN ANATOMY & NO FACIAL FEATURES:
   - Characters must NEVER have realistic human faces, eyes, noses, mouths, beards, mustaches, human hair, or skin textures!
   - Every human is a simplified 3D stick figure with a smooth featureless spherical head and cylindrical limbs.
   - ZERO realistic cloth fabrics, embroidered silk caftans, velvet robes, tunics, or realistic armor. Bodies are solid matte colored 3D stick figures.
2. STRICT AUTHORITATIVE CHARACTER COLOR IDENTITY (PERSISTENT & IMMUTABLE):
   - PRIMARY PROTAGONIST ({protagonist_name}) = 100% EXCLUSIVELY SOLID BRIGHT RED 3D STICK FIGURE (with a simple toy gold wire crown, smooth red spherical head, cylindrical limbs).
   - ALL OTHER CHARACTERS ({", ".join(supporting_names) or "senators, conspirators, crowds, citizens"}) = 100% EXCLUSIVELY SOLID BLUE 3D STICK FIGURES (smooth blue spherical heads, cylindrical limbs).
   - ABSOLUTE RULE: {protagonist_name} MUST ALWAYS BE RED. {protagonist_name} NEVER becomes blue, even when attacked, sitting, walking, or falling!
   - Conspirators and senators MUST ALWAYS BE BLUE. Conspirators NEVER become red!
   - Faction color is bound strictly to character IDENTITY, never narrative aggression or location!
3. RENDER STYLE:
   - Stylized 3D CGI toy universe, smooth rounded geometry, matte plastic/clay surfaces, warm volumetric lighting, zero photorealism.
"""

        # Build character context for prompt
        if is_3d_stickman:
            char_ctx = (
                f"{protagonist_name}: Solid bright red 3D stick figure with smooth featureless sphere head, simple geometric gold toy crown, cylindrical limbs. "
                f"Other figures ({', '.join(supporting_names[:5])}): Solid blue 3D stick figures with smooth featureless sphere heads, cylindrical limbs."
            )
        else:
            char_ctx = "; ".join([f"{c.name}: {c.appearance}, wearing {c.costume}" for c in analysis.continuity_bible.characters[:6]])
            
        loc_ctx = "; ".join([f"{l.name}: {l.description}" for l in analysis.continuity_bible.locations[:4]])

        output_visual_scenes: List[VisualScene] = []
        batch_size = max(2, min(batch_size, 4))
        num_batches = max(1, (total_scenes + batch_size - 1) // batch_size)

        for b_idx in range(num_batches):
            start_i = b_idx * batch_size
            end_i = min(start_i + batch_size, total_scenes)
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

            if is_3d_stickman:
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
1. Ground the visual in the exact narration moment. Depict only what has occurred so far (NO premature actions; NO premature reveals of overland ship transport or discarded crowns).
2. If style is 3D Red & Blue Stickman: Strictly follow character colors ({protagonist_name} = RED, all conspirators/senators = BLUE).
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

            p_items = []
            max_attempts = 2
            for attempt in range(max_attempts):
                try:
                    raw_res = engine.generate_text(
                        prompt=user_prompt,
                        system_prompt="You are a master AI video prompt architect. Output strictly valid JSON only.",
                        temperature=0.3,
                        max_tokens=1024
                    )
                    parsed = engine.repair_and_parse_json(raw_res)
                    p_items = parsed.get("prompts") or parsed.get("items") or []
                    if isinstance(p_items, list) and len(p_items) >= len(batch_scenes):
                        break
                except Exception as err:
                    print(f"[Stage5Prompts] Batch {b_idx + 1} attempt {attempt + 1} notice: {err}")
                    time.sleep(1.0)

            # Map responses back to scenes
            prompt_by_id = {}
            if isinstance(p_items, list):
                for item in p_items:
                    if isinstance(item, dict):
                        sid = str(item.get("scene_id", "")).strip().lstrip("#")
                        prompt_by_id[sid] = item
                        m = re.search(r'\d+', sid)
                        if m:
                            prompt_by_id[str(int(m.group()))] = item

            # Individual selective retry for any missing scene in this batch
            for s in batch_scenes:
                sid_clean = s.scene_id.lstrip("#")
                m_s = re.search(r'\d+', s.scene_id)
                num_key = str(int(m_s.group())) if m_s else sid_clean
                
                matched = prompt_by_id.get(sid_clean) or prompt_by_id.get(s.scene_id) or prompt_by_id.get(num_key)
                
                # If missing from batch, attempt a dedicated single-scene request
                if not matched or not matched.get("prompt"):
                    try:
                        clean_concept = sanitize_action_summary(s.visual_summary, s.narration_text)
                        if is_3d_stickman:
                            char_directive_single = f"Generate a single production image prompt strictly adhering to {protagonist_name} = RED 3D stickman and others = BLUE 3D stickmen."
                        else:
                            char_directive_single = f"Generate a single production image prompt adhering to {style_name}. Ground characters in period-accurate human attire from the Character Bible. ZERO stick figures."

                        single_prompt = f"""### VISUAL STYLE: {style_name}
{stickman_faction_rules}

### SCENE TO PROMPT:
- Scene ID: {s.scene_id}
- Narration: \"{s.narration_text}\"
- Visual Concept: {clean_concept}
- Setting: {derive_contextual_environment(s.narration_text, analysis, is_3d_stickman=is_3d_stickman)}

{char_directive_single}
Return JSON: {{"scene_id": "{s.scene_id}", "prompt": "full prompt text", "subject": "{clean_concept}", "composition": "Eye-level medium shot"}}"""
                        single_raw = engine.generate_text(
                            prompt=single_prompt,
                            system_prompt="Output strictly valid JSON only.",
                            temperature=0.3,
                            max_tokens=400
                        )
                        single_parsed = engine.repair_and_parse_json(single_raw)
                        if single_parsed.get("prompt"):
                            matched = single_parsed
                            prompt_by_id[sid_clean] = matched
                    except Exception as e_single:
                        print(f"[Stage5] Single-scene retry notice for {s.scene_id}: {e_single}")

                # Build final prompt text
                is_fallback_scene = False
                if matched and isinstance(matched, dict) and matched.get("prompt"):
                    p_text = matched.get("prompt", "").strip()
                    comp = matched.get("composition") or "Eye-level medium shot"
                    env = matched.get("environment") or derive_contextual_environment(s.narration_text, analysis, is_3d_stickman=is_3d_stickman)
                    subj = matched.get("subject") or sanitize_action_summary(s.visual_summary, s.narration_text)
                else:
                    # Clean semantic fallback (ZERO scaffolding, ZERO leaked tags, ZERO generic ramparts)
                    is_fallback_scene = True
                    comp = "Eye-level wide cinematic shot"
                    env = derive_contextual_environment(s.narration_text, analysis, is_3d_stickman=is_3d_stickman)
                    subj = sanitize_action_summary(s.visual_summary, s.narration_text)

                    if is_3d_stickman:
                        narr_lower = s.narration_text.lower()
                        has_caesar = any(k in narr_lower for k in ["caesar", "dictator", "magistrate", "husband"])
                        
                        if has_caesar:
                            chars_clause = f"The solid bright red 3D stickman leader ({protagonist_name} with featureless red sphere head, toy gold wire crown, and cylindrical limbs) surrounded by solid blue 3D stick figures"
                        else:
                            chars_clause = "Solid blue 3D stick figures with smooth featureless spherical heads and cylindrical limbs"

                        p_text = (
                            f"3D red-and-blue stylized stickman animation. "
                            f"{env}. "
                            f"{chars_clause}. "
                            f"Action: {subj}. "
                            f"{comp}, stylized 3D toy CGI geometry, matte plastic surfaces, warm volumetric lighting, zero photorealism."
                        )
                    else:
                        p_text = (
                            f"{style_name} aesthetic. {env}. "
                            f"Action: {subj}. {comp}, authentic historical period details, cinematic lighting."
                        )

                # =============================================================
                # POST-PROCESSING SANITIZATION (Authoritative Rule Enforcement)
                # =============================================================
                if is_3d_stickman:
                    # 1. Strip any realistic human facial features or realistic clothing
                    p_text = re.sub(r"\b(with a|with|having a|wearing a)?\s*(dark|trimmed|short|full|imperial)?\s*(beard|beards|mustache|mustaches)\b", "", p_text, flags=re.IGNORECASE)
                    p_text = re.sub(r"\b(wearing (an|a)?\s*(imperial|embroidered)?\s*(turban|silk caftan|velvet cape|tunic|leather boots|flowing robe|armor plate|cape|cloak))\b", "solid matte colored stick figure", p_text, flags=re.IGNORECASE)
                    p_text = re.sub(r"\bhuman (face|eyes|skin|facial features|hair)\b", "featureless spherical 3D stickman head", p_text, flags=re.IGNORECASE)
                    p_text = re.sub(r"\b(realistic|photorealistic|detailed)\s+(face|eyes|skin|beard|mustache|clothing)\b", "featureless smooth 3D geometry", p_text, flags=re.IGNORECASE)

                    # 2. Strict Faction Color Enforcement:
                    # Caesar must ALWAYS be RED.
                    p_text = re.sub(
                        r"\b(solid\s+)?blue\s+(3d\s+)?(stick\s+figure|stickman)\s*\((caesar|the dictator|julius caesar)\)",
                        r"solid bright red 3D stick figure (\4 with gold toy crown)",
                        p_text,
                        flags=re.IGNORECASE
                    )
                    p_text = re.sub(
                        r"\b(solid\s+)?blue\s+(3d\s+)?stick\s+figure\s+caesar\b",
                        "solid bright red 3D stick figure Caesar",
                        p_text,
                        flags=re.IGNORECASE
                    )
                    # Conspirators / senators must ALWAYS be BLUE.
                    p_text = re.sub(
                        r"\b(solid\s+)?(bright\s+)?red\s+(3d\s+)?(stick\s+figure|stickman|figures|stickmen)\s*\((conspirators?|assassins?|liberatores?|cimber|casca|brutus|cassius|senators?)\)",
                        r"solid blue 3D \4 (\5)",
                        p_text,
                        flags=re.IGNORECASE
                    )
                    p_text = re.sub(
                        r"\ba\s+single\s+bright\s+red\s+3d\s+stick\s+figure\s*\(cimber\)",
                        "a single solid blue 3D stick figure (Cimber)",
                        p_text,
                        flags=re.IGNORECASE
                    )
                    p_text = re.sub(
                        r"\ba\s+pack\s+of\s+solid\s+bright\s+red\s+3d\s+stick\s+figures\s*\(liberatores\)",
                        "a pack of solid blue 3D stick figures (Liberatores)",
                        p_text,
                        flags=re.IGNORECASE
                    )

                    # 3. Faction purity enforcement for siege/defending/attacking scenes
                    p_lower = p_text.lower()
                    narr_lower = s.narration_text.lower()
                    is_defending_scene = any(w in narr_lower or w in p_lower for w in ["repaired", "defenders", "inside the city", "rubble", "timber", "walls resisted", "harbor", "chain"])
                    is_attacking_scene = any(w in narr_lower or w in p_lower for w in ["cannon", "bombard", "encampment", "dragged overland", "artillery battery", "opened fire outside", "ottoman cannons"])
                    is_combat_clash = any(w in narr_lower or w in p_lower for w in ["final assault", "hand-to-hand", "clash", "storming", "combat"])

                    if is_defending_scene and not is_combat_clash and "caesar" not in narr_lower:
                        if "zero red figures" not in p_lower:
                            p_text += " Exclusively solid blue 3D stick figures inside the city. Zero red figures present."
                    elif is_attacking_scene and not is_combat_clash and "caesar" not in narr_lower:
                        if "zero blue figures" not in p_lower:
                            p_text += " Exclusively solid bright red 3D stick figures outside the fortifications. Zero blue figures present."

                    # 4. Clean up any leaked pipeline scaffolding
                    p_text = re.sub(r"\b(Active progression|Consequential development|Establishing perspective):\s*", "", p_text)
                    p_text = re.sub(r"^(A wide, low|A split|A solitary, evocative wide shot)\s*—?\s*", "", p_text)
                    p_text = re.sub(r"Setting:\s*Fortified historical cityscape and defensive ramparts\.?", "", p_text)
                    p_text = re.sub(r"Setting:\s*Fortified historical setting\.?", "", p_text)
                    p_text = re.sub(r"\s+", " ", p_text).strip()

                    # 5. Append Negative Prompts
                    if "STRICT NEGATIVE:" not in p_text:
                        p_text = (
                            f"{p_text.rstrip('. ')}. 3D animated stickman universe, stylized toy CGI render, smooth matte plastic. "
                            f"STRICT NEGATIVE: human face, realistic eyes, nose, mouth, beard, mustache, human hair, human skin texture, realistic fabric, realistic clothing, turban, cape, cloak, tunic, boots, doll, claymation human, photorealism, live-action."
                        )
                else:
                    # NON-STICKMAN STYLES (Century-Old Photograph, Black & White, Vintage, Oil Painting, etc.):
                    # 1. Clean up any leaked pipeline scaffolding
                    p_text = re.sub(r"\b(Active progression|Consequential development|Establishing perspective):\s*", "", p_text)
                    p_text = re.sub(r"^(A wide, low|A split|A solitary, evocative wide shot)\s*—?\s*", "", p_text)
                    p_text = re.sub(r"Setting:\s*Fortified historical cityscape and defensive ramparts\.?", "", p_text)
                    p_text = re.sub(r"Setting:\s*Fortified historical setting\.?", "", p_text)
                    p_text = re.sub(r"\s+", " ", p_text).strip()

                    # 2. Strict Stickman Removal: eradicate any accidental stickman or colored toy mentions
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
                    validation_notes="PROMPT_GENERATION_FALLBACK" if is_fallback_scene else None
                )
                output_visual_scenes.append(v_scene)

        return output_visual_scenes
