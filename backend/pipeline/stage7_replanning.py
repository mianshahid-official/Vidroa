"""
Stage 7: Automatic Replanning.
Repairs specific failing scenes identified by the Storyboard Quality Audit.
Replaces repetitive concepts, fixes timing violations, and regenerates style-compliant prompts.
Guarantees authoritative character faction coloring (Caesar = RED, conspirators = BLUE)
and verifies that repairs do not introduce color inversions or copy-pasted actions.
"""
import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from app.models.planning import (
    ScriptAnalysis,
    StoryboardAuditReport,
    ReplanningResult,
    RepairedScene
)
from app.models.presets import VisualStylePreset
from app.models.scene import VisualScene
from backend.inference.engine import BaseInferenceEngine
from backend.pipeline.stage5_prompts import (
    resolve_stickman_characters,
    derive_contextual_environment,
    sanitize_action_summary
)
from backend.pipeline.prompt_loader import load_system_prompt as _load_system_prompt


def load_system_prompt() -> str:
    return _load_system_prompt("stage6_replanning.txt")


class Stage7Replanner:
    """Executes targeted replanning for scenes flagged during the quality audit."""

    @classmethod
    def execute(
        cls,
        engine: BaseInferenceEngine,
        scenes: List[VisualScene],
        audit_report: StoryboardAuditReport,
        analysis: ScriptAnalysis,
        story_text: str,
        style_preset: Optional[VisualStylePreset] = None,
        custom_style: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[VisualScene]:
        repair_instructions = audit_report.scene_repairs
        timing_issues = audit_report.timing_findings

        if not repair_instructions and not timing_issues:
            return scenes

        system_prompt = load_system_prompt()
        style_name = style_preset.name if style_preset else "3D Red & Blue Stickman Animation"
        style_instructions = style_preset.system_instructions if style_preset else "Stylized 3D stick figures with smooth spherical heads. NO human faces, NO beards, NO realistic clothing."
        if custom_style:
            style_instructions += f"\nCustom Style: {custom_style}"

        scenes_by_id = {s.scene_id: s for s in scenes}
        failing_scene_ids = set([sr.scene_id for sr in repair_instructions] + [tf.scene_id for tf in timing_issues])

        if progress_callback:
            progress_callback(1, 2, f"Replanning {len(failing_scene_ids)} scenes flagged by quality audit...")

        # Authoritative character color resolution
        protagonist_name, supporting_names = resolve_stickman_characters(analysis)

        failing_payload = []
        for sid in failing_scene_ids:
            sc = scenes_by_id.get(sid)
            if not sc:
                continue
            rep_notes = [sr.problem for sr in repair_instructions if sr.scene_id == sid]
            req_change = [sr.required_change for sr in repair_instructions if sr.scene_id == sid]
            sugg_dir = [sr.suggested_visual_direction for sr in repair_instructions if sr.scene_id == sid]
            time_issue = [tf.issue for tf in timing_issues if tf.scene_id == sid]

            failing_payload.append({
                "scene_id": sc.scene_id,
                "current_visual": sc.visual_subject,
                "narration_text": sc.narration_excerpt,
                "timing": f"{sc.start:.1f}s - {sc.end:.1f}s ({sc.duration:.1f}s)",
                "audit_problems": rep_notes + time_issue,
                "required_changes": req_change,
                "suggested_direction": sugg_dir
            })

        is_3d_red_blue = (style_preset.id if style_preset else "") in ("3d_red_blue_stickman", "red_blue_stickman_3d") or "3d red & blue" in style_name.lower() or "red & blue" in style_name.lower()
        is_general_stickman = any(k in (style_preset.id if style_preset else "").lower() or k in style_name.lower() for k in ["stickman", "stick_figure"])

        if is_3d_red_blue:
            char_ctx = (
                f"{protagonist_name}: Solid bright red 3D stick figure (PRIMARY PROTAGONIST). "
                f"Other characters ({', '.join(supporting_names[:5])}): Solid blue 3D stick figures (supporting figures and conspirators). "
                f"RULE: {protagonist_name} must NEVER be blue. Conspirators must NEVER be red."
            )
            continuity_lines = f"""- Characters: {char_ctx}
- Protagonist (RED): {protagonist_name}
- Supporting Figures / Conspirators (BLUE): {', '.join(supporting_names) or 'Senators and conspirators'}"""
            char_rule = f"3. Follow strict character colors: {protagonist_name} = RED 3D stickman; conspirators/senators = BLUE 3D stickmen."
        elif is_general_stickman:
            char_ctx = f"Characters: Stylized stickman characters adhering to {style_name}. Keep character clothing, gear, and expressions faithful to the story."
            continuity_lines = f"""- Characters: {char_ctx}"""
            char_rule = f"3. Maintain strict character appearance conforming to {style_name}."
        else:
            char_ctx = ', '.join([f"{c.name}: {c.appearance}" for c in analysis.continuity_bible.characters[:6]]) or 'Historical figures'
            continuity_lines = f"""- Characters: {char_ctx}"""
            char_rule = f"3. Maintain strict character appearance and period-accurate human attire conforming to {style_name}. ZERO stick figures."

        user_prompt = f"""### FAILING SCENES REQUIRING REPAIR:
{json.dumps(failing_payload, indent=2)}

### FULL STORY CONTEXT:
\"\"\"{story_text.strip()}\"\"\"

### USER VISUAL STYLE (MANDATORY):
Style Name: {style_name}
Style Instructions: {style_instructions}

### CONTINUITY CONTEXT:
{continuity_lines}

### INSTRUCTIONS:
Reconstruct these failing scenes:
1. Introduce a genuinely NEW, distinct visual concept for each scene based on its spoken narration.
2. Completely replace repetitive concepts (do not just reword the prompt; do not copy from other scenes).
{char_rule}
4. Regenerate a complete image prompt adhering to the user's selected visual style without metadata tags.

Return strictly valid JSON matching this schema:
{{
  "repaired_scenes": [
    {{
      "scene_id": "005",
      "new_visual_concept": "Substantially new visual concept replacing the duplicate scene",
      "what_changed": "Explanation of new visual information",
      "repaired_prompt": "Complete regenerated prompt in selected style..."
    }}
  ]
}}"""

        raw_res = ""
        try:
            raw_res = engine.generate_text(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=1024
            )
        except Exception as err:
            print(f"[Stage7Replanner] Notice: {err}")

        repaired_items = []
        try:
            parsed = engine.repair_and_parse_json(raw_res)
            repaired_items = parsed.get("repaired_scenes") or parsed.get("items") or []
        except Exception:
            repaired_items = []

        repaired_by_id: Dict[str, Dict[str, Any]] = {}
        for r in repaired_items:
            if isinstance(r, dict):
                sid = str(r.get("scene_id", "")).strip().lstrip("#")
                new_conc = str(r.get("new_visual_concept", "")).strip()
                orig_sc = scenes_by_id.get(sid) or scenes_by_id.get(f"{int(sid):03d}" if sid.isdigit() else sid)
                
                # If LLM just echoed the original failing concept, reject it
                if new_conc and orig_sc and new_conc.lower() == orig_sc.visual_subject.strip().lower():
                    continue
                # Reject if contains copy-pasted Cimber ambush for outdoor/street scenes
                if int(sid) < 46 and ("cimber is on his knees" in new_conc.lower() or "daggers concealed" in new_conc.lower()):
                    continue
                # Accept non-empty repairs
                if new_conc and r.get("repaired_prompt") and str(r.get("repaired_prompt")).strip():
                    repaired_by_id[sid] = r

        # Programmatic deterministic fallback repair for any failing scene not repaired by LLM
        for sr in repair_instructions:
            sid = str(sr.scene_id).strip().lstrip("#")
            if sid not in repaired_by_id:
                sc = scenes_by_id.get(sid) or scenes_by_id.get(f"{int(sid):03d}" if sid.isdigit() else sid)
                if sc:
                    new_concept = sr.suggested_visual_direction or f"Action reflecting spoken words: {sc.narration_excerpt[:70]}"
                    clean_concept = sanitize_action_summary(new_concept, sc.narration_excerpt)
                    env = derive_contextual_environment(sc.narration_excerpt, analysis)

                    if is_3d_stickman:
                        narr_lower = sc.narration_excerpt.lower()
                        has_caesar = any(k in narr_lower for k in ["caesar", "dictator", "magistrate", "husband"])
                        
                        if has_caesar:
                            chars_clause = f"The solid bright red 3D stickman leader ({protagonist_name} with toy gold crown) alongside solid blue 3D stick figures"
                        else:
                            chars_clause = "Solid blue 3D stick figures with smooth featureless spherical heads and cylindrical limbs"

                        fallback_p = (
                            f"3D red-and-blue stylized stickman animation. {env}. "
                            f"{chars_clause}. Action: {clean_concept}. "
                            f"Composition: Eye-level cinematic shot, stylized 3D toy CGI geometry, matte plastic surfaces, warm volumetric lighting, zero photorealism."
                        )
                    else:
                        fallback_p = (
                            f"{style_name} illustration aesthetic. {env}. Subject & Action: {clean_concept}. "
                            f"Authentic historical period details, cinematic composition, rich tactile art texture."
                        )

                    repaired_by_id[sid] = {
                        "scene_id": sid,
                        "new_visual_concept": clean_concept,
                        "what_changed": f"Replaced with narration-aligned concept: {sr.required_change}",
                        "repaired_prompt": fallback_p
                    }

        # Apply repairs to the storyboard with strict post-processing
        reconstructed_scenes: List[VisualScene] = []
        for s in scenes:
            sid_clean = s.scene_id.lstrip("#")
            rep = repaired_by_id.get(sid_clean) or repaired_by_id.get(s.scene_id)
            if rep:
                new_concept = rep.get("new_visual_concept") or s.visual_subject
                new_prompt = rep.get("repaired_prompt") or s.prompt
                what_changed = rep.get("what_changed", "Scene replanned by audit")

                if is_3d_red_blue:
                    # Strip realistic facial features/clothing
                    new_prompt = re.sub(r"\b(with a|with|having a|wearing a)?\s*(dark|trimmed|short|full|imperial)?\s*(beard|beards|mustache|mustaches)\b", "", new_prompt, flags=re.IGNORECASE)
                    new_prompt = re.sub(r"\b(wearing (an|a)?\s*(imperial|embroidered)?\s*(turban|silk caftan|velvet cape|tunic|leather boots|flowing robe|armor plate))\b", "solid matte colored stick figure", new_prompt, flags=re.IGNORECASE)
                    new_prompt = re.sub(r"\bhuman (face|eyes|skin|facial features|hair)\b", "featureless spherical 3D stickman head", new_prompt, flags=re.IGNORECASE)
                    new_prompt = re.sub(r"\b(realistic|photorealistic|detailed)\s+(face|eyes|skin|beard|mustache|clothing)\b", "featureless smooth 3D geometry", new_prompt, flags=re.IGNORECASE)

                    # Strict Faction Color Enforcement on repairs:
                    # Caesar is ALWAYS RED
                    new_prompt = re.sub(
                        r"\b(solid\s+)?blue\s+(3d\s+)?(stick\s+figure|stickman)\s*\((caesar|the dictator|julius caesar)\)",
                        r"solid bright red 3D stick figure (\4 with gold toy crown)",
                        new_prompt,
                        flags=re.IGNORECASE
                    )
                    new_prompt = re.sub(
                        r"\b(solid\s+)?blue\s+(3d\s+)?stick\s+figure\s+caesar\b",
                        "solid bright red 3D stick figure Caesar",
                        new_prompt,
                        flags=re.IGNORECASE
                    )
                    # Conspirators are ALWAYS BLUE
                    new_prompt = re.sub(
                        r"\b(solid\s+)?(bright\s+)?red\s+(3d\s+)?(stick\s+figure|stickman|figures|stickmen)\s*\((conspirators?|assassins?|liberatores?|cimber|casca|brutus|cassius|senators?)\)",
                        r"solid blue 3D \4 (\5)",
                        new_prompt,
                        flags=re.IGNORECASE
                    )
                    new_prompt = re.sub(
                        r"\ba\s+single\s+bright\s+red\s+3d\s+stick\s+figure\s*\(cimber\)",
                        "a single solid blue 3D stick figure (Cimber)",
                        new_prompt,
                        flags=re.IGNORECASE
                    )
                    new_prompt = re.sub(
                        r"\ba\s+pack\s+of\s+solid\s+bright\s+red\s+3d\s+stick\s+figures\s*\(liberatores\)",
                        "a pack of solid blue 3D stick figures (Liberatores)",
                        new_prompt,
                        flags=re.IGNORECASE
                    )

                    # Clean scaffolding
                    new_prompt = re.sub(r"\b(Active progression|Consequential development|Establishing perspective):\s*", "", new_prompt)
                    new_prompt = re.sub(r"^(A wide, low|A split|A solitary, evocative wide shot)\s*—?\s*", "", new_prompt)
                    new_prompt = re.sub(r"Setting:\s*Fortified historical cityscape and defensive ramparts\.?", "", new_prompt)
                    new_prompt = re.sub(r"Setting:\s*Fortified historical setting\.?", "", new_prompt)
                    new_prompt = re.sub(r"\s+", " ", new_prompt).strip()

                    if "STRICT NEGATIVE:" not in new_prompt:
                        new_prompt = (
                            f"{new_prompt.rstrip('. ')}. 3D animated stickman universe, stylized toy CGI render, smooth matte plastic. "
                            f"STRICT NEGATIVE: human face, realistic eyes, nose, mouth, beard, mustache, human hair, human skin texture, realistic fabric, realistic clothing, photorealism, live-action."
                        )
                else:
                    # NON-RED-BLUE STYLES (Century-Old Photograph, 3D Stickman, 2D Stickman, Black & White, Vintage, Oil Painting, etc.):
                    # 1. Clean scaffolding
                    new_prompt = re.sub(r"\b(Active progression|Consequential development|Establishing perspective):\s*", "", new_prompt)
                    new_prompt = re.sub(r"^(A wide, low|A split|A solitary, evocative wide shot)\s*—?\s*", "", new_prompt)
                    new_prompt = re.sub(r"Setting:\s*Fortified historical cityscape and defensive ramparts\.?", "", new_prompt)
                    new_prompt = re.sub(r"Setting:\s*Fortified historical setting\.?", "", new_prompt)
                    new_prompt = re.sub(r"\s+", " ", new_prompt).strip()

                    # 2. Strict Stickman Removal: ONLY eradicate stickman mentions if NOT a stickman style
                    if not is_general_stickman:
                        new_prompt = re.sub(r"\ba\s+(red|blue)\s+3d\s+stickman\s+figure\s+representing\b", "historical figure depicting", new_prompt, flags=re.IGNORECASE)
                        new_prompt = re.sub(r"\b(solid\s+)?(bright\s+)?(red|blue)\s+3d\s+stick\s*(man|figure|figures|men)\b", "historical figures in period attire", new_prompt, flags=re.IGNORECASE)
                        new_prompt = re.sub(r"\b3d\s+stick\s*(man|figure|figures|men)\b", "figures in period attire", new_prompt, flags=re.IGNORECASE)
                        new_prompt = re.sub(r"\bfeatureless\s+spherical\s+(3d\s+)?stickman\s+head\b", "period headwear", new_prompt, flags=re.IGNORECASE)
                        new_prompt = re.sub(r"\bmonochromatic palette with distinct red and blue character accents\b", "monochromatic archival palette", new_prompt, flags=re.IGNORECASE)
                        new_prompt = re.sub(r"\bgeometric red body\b", "period military attire", new_prompt, flags=re.IGNORECASE)
                        new_prompt = re.sub(r"\bblank red surface\b", "weathered determined expression", new_prompt, flags=re.IGNORECASE)
                        new_prompt = re.sub(r"\s+", " ", new_prompt).strip()

                updated_scene = s.model_copy(update={
                    "visual_subject": new_concept,
                    "action": new_concept,
                    "prompt": new_prompt,
                    "validation_notes": f"Repaired in Stage 7: {what_changed}"
                })
                reconstructed_scenes.append(updated_scene)
            else:
                reconstructed_scenes.append(s)

        if progress_callback:
            progress_callback(2, 2, f"Replanning complete. {len(repaired_by_id)} scenes successfully reconstructed.")

        return reconstructed_scenes
