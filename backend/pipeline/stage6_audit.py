"""
Stage 6: Complete Storyboard Quality Audit.
Performs global, end-to-end evaluation of narration alignment, semantic repetition,
temporal pacing, continuity, and visual style fidelity using Groq and deterministic checks.
Critical semantic defects independently block approval and cap quality score <= 74.0.
"""
import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from app.models.planning import (
    ScriptAnalysis,
    StoryboardAuditReport,
    CategoryScores,
    RepetitionFinding,
    TimingFinding,
    AlignmentFinding,
    SceneRepairInstruction
)
from app.models.scene import VisualScene
from backend.inference.engine import BaseInferenceEngine
from backend.pipeline.prompt_loader import load_system_prompt as _load_system_prompt
from backend.pipeline.story_pack import StoryPackManager


def load_system_prompt() -> str:
    return _load_system_prompt("stage5_validation.txt")


class Stage6StoryboardAuditor:
    """Executes holistic storyboard quality audit across all scenes."""

    @classmethod
    def execute(
        cls,
        engine: BaseInferenceEngine,
        scenes: List[VisualScene],
        story_text: str,
        analysis: ScriptAnalysis,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> StoryboardAuditReport:
        auditor_system_prompt = load_system_prompt()
        active_pack = StoryPackManager.match_pack(story_text)
        is_1453 = bool(active_pack and active_pack.id == "constantinople-1453")
        is_caesar = bool(active_pack and active_pack.id == "caesar-44bc")

        if progress_callback:
            progress_callback(1, 2, "Auditing complete storyboard for narration alignment, pacing, and repetition...")

        # Prepare compact, token-efficient scenes list for audit
        scene_lines = [
            f"- [{s.scene_id} | {s.start:.1f}-{s.end:.1f}s] Spoken: \"{s.narration_excerpt[:70]}\" | Visual: {s.visual_subject[:50]} | Prompt: {s.prompt[:70]}"
            for s in scenes
        ]
        condensed_scenes = "\n".join(scene_lines)

        user_prompt = f"""### STORYBOARD SCENES TO AUDIT:
{condensed_scenes}

### SCRIPT EXCERPT / SUMMARY:
\"\"\"{story_text.strip()[:2000]}\"\"\"

### CONTINUITY CONTEXT:
- Characters: {', '.join([c.name for c in analysis.continuity_bible.characters[:6]]) or 'Archetypes'}
- High-Risk Concepts: {', '.join(analysis.visual_planning_constraints.high_risk_repetition_concepts[:4]) or 'None'}

### INSTRUCTIONS:
Evaluate the storyboard against: 1. Narration Alignment, 2. Visual Repetition, 3. Temporal Pacing, 4. Style Fidelity.
MANDATORY REPETITION CHECK:
- Flag any scenes that depict essentially the same action or subject (e.g. 2 or 3 scenes of cannon bombardment or walls being hit).
- If repetition occurs, flag as "critical" in repetition_findings and include concrete scene_repairs recommending a progressive alternative.

Return strictly valid JSON matching this schema:
{{
  "overall_score": 0.0,
  "category_scores": {{
    "narration_alignment": 0.0,
    "visual_progression": 0.0,
    "temporal_pacing": 0.0,
    "continuity": 0.0,
    "style_fidelity": 0.0,
    "prompt_quality": 0.0
  }},
  "repetition_findings": [],
  "timing_findings": [],
  "alignment_findings": [],
  "scene_repairs": [],
  "final_recommendation": "APPROVED or NEEDS_REPAIR"
}}"""

        parsed = {}
        try:
            raw_res = engine.generate_text(
                prompt=user_prompt,
                system_prompt=auditor_system_prompt,
                temperature=0.2,
                max_tokens=850
            )
            parsed = engine.repair_and_parse_json(raw_res)
        except Exception as err:
            print(f"[Stage6Audit] Live LLM audit notice: {err}. Executing fail-closed deterministic auditor.")
            parsed = {}

        # 1. Programmatic invariant check for timing ceiling (hard 8.0s) and timeline gaps
        timing_findings: List[TimingFinding] = []
        for s in scenes:
            if s.duration > 8.05:
                timing_findings.append(TimingFinding(
                    scene_id=s.scene_id,
                    issue=f"Scene duration ({s.duration:.1f}s) exceeds the strict 8.0s hard ceiling.",
                    duration=s.duration
                ))

        for idx in range(len(scenes) - 1):
            gap = scenes[idx + 1].start - scenes[idx].end
            if gap > 0.5:
                timing_findings.append(TimingFinding(
                    scene_id=scenes[idx + 1].scene_id,
                    issue=f"Timeline gap of {gap:.1f}s detected between scenes #{scenes[idx].scene_id} and #{scenes[idx + 1].scene_id}",
                    duration=gap
                ))

        # 2. Programmatic check for whole-storyboard repetition and anomalies
        rep_findings: List[RepetitionFinding] = []
        align_findings: List[AlignmentFinding] = []
        scene_repairs: List[SceneRepairInstruction] = []

        stop_words = {
            "the", "and", "with", "from", "into", "that", "this", "over", "under", "scene", "shot",
            "view", "camera", "showing", "depicting", "visual", "figure", "figures", "style", "animation",
            "stickman", "authentic", "damaged", "physically", "aged", "archival", "photograph", "warm",
            "faded", "sepia", "silver", "gelatin", "monochrome", "tones", "worn", "torn", "edges",
            "black", "dust", "spots", "vertical", "plate", "scratches", "sharp", "central", "subject",
            "animated", "universe", "stylized", "render", "smooth", "matte", "plastic", "strict",
            "negative", "human", "face", "eyes", "nose", "mouth", "beard", "mustache", "hair",
            "skin", "texture", "fabric", "clothing", "photorealism", "live", "action", "colors",
            "optics", "period", "setting", "historical"
        }

        def extract_meaningful_tokens(text: str) -> set:
            raw_tokens = re.findall(r"\b[a-z]{4,}\b", text.lower())
            return {t for t in raw_tokens if t not in stop_words}

        # Whole-storyboard repetition tracking for specific story packs
        if is_1453:
            cannon_scenes: List[str] = []
            for s in scenes:
                txt_lower = s.visual_subject.lower()
                if any(k in txt_lower for k in ["cannon", "bombard", "artillery battery"]):
                    cannon_scenes.append(s.scene_id)

            # Flag excessive repetition clusters across whole storyboard
            if len(cannon_scenes) > 6:
                rep_findings.append(RepetitionFinding(
                    scene_ids=cannon_scenes[3:],
                    reason=f"Repetitive artillery cluster: {len(cannon_scenes)} scenes across storyboard depict cannon bombardment.",
                    severity="critical"
                ))

        # Check consecutive scene repetition
        for idx in range(len(scenes) - 1):
            s1 = scenes[idx]
            s2 = scenes[idx + 1]

            s1_subj_tokens = extract_meaningful_tokens(s1.visual_subject)
            s2_subj_tokens = extract_meaningful_tokens(s2.visual_subject)

            subj_overlap = len(s1_subj_tokens & s2_subj_tokens)
            subj_union = len(s1_subj_tokens | s2_subj_tokens) or 1
            subj_jaccard = subj_overlap / float(subj_union)

            clean_s1 = re.sub(r"\s*\(.*?\)", "", s1.visual_subject).strip().lower()
            clean_s2 = re.sub(r"\s*\(.*?\)", "", s2.visual_subject).strip().lower()
            identical_subject = (clean_s1 == clean_s2 and len(clean_s1) > 10)

            is_duplicate = (
                identical_subject or
                (subj_overlap >= 3 and subj_jaccard >= 0.70)
            )

            if is_1453:
                both_cannon = (
                    any(k in s1.visual_subject.lower() for k in ["cannon", "bombard", "artillery battery", "firing artillery"]) and
                    any(k in s2.visual_subject.lower() for k in ["cannon", "bombard", "artillery battery", "firing artillery"])
                )
                both_wall_impact = (
                    any(k in s1.visual_subject.lower() for k in ["crumble", "projectile slammed", "shattered wall", "broken wall", "falling wall"]) and
                    any(k in s2.visual_subject.lower() for k in ["crumble", "projectile slammed", "shattered wall", "broken wall", "falling wall"])
                )
                if both_cannon and both_wall_impact:
                    is_duplicate = True

            if is_duplicate:
                rep_findings.append(RepetitionFinding(
                    scene_ids=[s1.scene_id, s2.scene_id],
                    reason=f"Scenes #{s1.scene_id} and #{s2.scene_id} depict repetitive visual action: '{s1.visual_subject[:50]}'",
                    severity="critical"
                ))
                if not any(sr.scene_id == s2.scene_id for sr in scene_repairs):
                    req = "Replace repeated concept with progressive visual action advancing the story"
                    from backend.pipeline.stage4_scheduling import derive_progressive_subsegment_concept
                    sugg = derive_progressive_subsegment_concept(s2.visual_subject, s2.narration_excerpt.split(), 1, 2)
                    scene_repairs.append(SceneRepairInstruction(
                        scene_id=s2.scene_id,
                        problem=f"Consecutive visual loop with scene #{s1.scene_id}",
                        required_change=req,
                        suggested_visual_direction=sugg
                    ))

        # Check 3-scene window repetition (for 1453 siege artillery)
        if is_1453:
            for idx in range(len(scenes) - 2):
                s1 = scenes[idx]
                s2 = scenes[idx + 1]
                s3 = scenes[idx + 2]
                window_cannon_scenes = [
                    sc for sc in [s1, s2, s3]
                    if any(k in sc.visual_subject.lower() for k in ["cannon", "bombard", "artillery battery", "artillery crew", "projectile slammed", "cannonball"])
                    and not any(w in sc.narration_excerpt.lower() for w in ["rewrite history", "combination of", "remarkable part", "entire era", "21 years", "twenty-one", "young sultan", "wanted one thing", "enormous army", "tens of thousands"])
                ]
                if len(window_cannon_scenes) >= 2:
                    repeat_sc = window_cannon_scenes[1]
                    rep_findings.append(RepetitionFinding(
                        scene_ids=[window_cannon_scenes[0].scene_id, repeat_sc.scene_id],
                        reason=f"Repetitive artillery bombardment: Scenes #{window_cannon_scenes[0].scene_id} and #{repeat_sc.scene_id} both depict cannon firing/impact.",
                        severity="critical"
                    ))
                    if not any(sr.scene_id == repeat_sc.scene_id for sr in scene_repairs):
                        from backend.pipeline.stage4_scheduling import derive_progressive_subsegment_concept
                        rep_narr = repeat_sc.narration_excerpt.lower()
                        if any(w in rep_narr for w in ["repair", "timber", "rubble", "earth", "defenders rushed"]):
                            dir_sugg = "Byzantine defenders frantically stacking timber beams, earth, and rubble behind damaged wall sectors to plug crumbling breaches"
                        else:
                            dir_sugg = derive_progressive_subsegment_concept(repeat_sc.visual_subject, repeat_sc.narration_excerpt.split(), 1, 2)
                        scene_repairs.append(SceneRepairInstruction(
                            scene_id=repeat_sc.scene_id,
                            problem="Repetitive artillery bombardment loop",
                            required_change="Replace duplicate cannon scene with progressive visual action matching narration",
                            suggested_visual_direction=dir_sugg
                        ))

        # 3. Scene-by-scene semantic alignment check
        is_stickman_storyboard = bool(scenes and sum(1 for sc in scenes if "stickman" in sc.prompt.lower()) >= len(scenes) / 2)

        for idx, s in enumerate(scenes):
            narr_lower = s.narration_excerpt.lower()
            subj_lower = s.visual_subject.lower()
            p_lower = s.prompt.lower()

            # Premature event check: before siege begins (typically early scenes), depicting wall breaches or destruction
            if is_1453:
                is_early_exposition = idx < 10 and any(w in narr_lower for w in ["thousand years", "empire", "continents", "capital", "conquer", "21 years old", "shadow of its former glory"])
                if is_early_exposition and any(w in subj_lower for w in ["crumbling", "shattered wall", "projectile slammed", "breach", "collapsed"]):
                    align_findings.append(AlignmentFinding(
                        scene_id=s.scene_id,
                        issue=f"Premature event in scene #{s.scene_id}: Depicts wall breach/destruction before the siege even began ({s.narration_excerpt[:50]})."
                    ))
                    if not any(sr.scene_id == s.scene_id for sr in scene_repairs):
                        scene_repairs.append(SceneRepairInstruction(
                            scene_id=s.scene_id,
                            problem="Premature depiction of wall breach during historical exposition",
                            required_change="Show historical subject from narration instead of siege destruction",
                            suggested_visual_direction=f"Depict narration subject: {s.narration_excerpt[:60]}"
                        ))

                # Introduction mismatch: Narration introduces Mehmed II, but visual depicts wall breach or cannon without commander
                is_intro = any(w in narr_lower for w in ["his name was mehmed", "young ottoman sultan", "twenty-one years old", "21 years old", "wanted one thing above"])
                if is_intro and not any(w in subj_lower or w in p_lower for w in ["mehmed", "sultan", "commander", "ruler", "young"]):
                    align_findings.append(AlignmentFinding(
                        scene_id=s.scene_id,
                        issue=f"Character introduction mismatch in scene #{s.scene_id}: Spoken narration introduces Mehmed II but visual lacks the commander."
                    ))
                    if not any(sr.scene_id == s.scene_id for sr in scene_repairs):
                        scene_repairs.append(SceneRepairInstruction(
                            scene_id=s.scene_id,
                            problem="Failed character introduction",
                            required_change="Depict the young Sultan Mehmed II overlooking army",
                            suggested_visual_direction="Young Sultan Mehmed II focused with singular ambition on his goal to conquer Constantinople"
                        ))

                # Powerful cannons capable of smashing walls (Scene 10)
                if any(w in narr_lower for w in ["powerful cannons capable", "cannons capable of smashing"]) and not any(w in subj_lower for w in ["cannon", "bombard", "artillery"]):
                    align_findings.append(AlignmentFinding(
                        scene_id=s.scene_id,
                        issue=f"Semantic mismatch in scene #{s.scene_id}: Narration speaks of powerful cannons capable of smashing walls, but visual lacks artillery."
                    ))
                    if not any(sr.scene_id == s.scene_id for sr in scene_repairs):
                        scene_repairs.append(SceneRepairInstruction(
                            scene_id=s.scene_id,
                            problem="Missing powerful cannons",
                            required_change="Depict the colossal bronze bombard artillery battery outside the walls",
                            suggested_visual_direction="Colossal bronze siege bombard deployed outside the city walls: Ottoman artillery engineers preparing the massive cannon to smash stone defenses"
                        ))

            # 1. Character Faction Inversion Check (Caesar = RED, conspirators = BLUE) for stickman, OR Stickman Leak Check for non-stickman styles
            if is_caesar and is_stickman_storyboard:
                if re.search(r"\bblue\s+(3d\s+)?(stick\s+figure|stickman)\s*\((caesar|the dictator)\)", p_lower) or re.search(r"\bblue\s+(3d\s+)?stick\s+figure\s+caesar\b", p_lower):
                    align_findings.append(AlignmentFinding(
                        scene_id=s.scene_id,
                        issue=f"CRITICAL FACTION INVERSION in scene #{s.scene_id}: Caesar is described as a BLUE 3D stickman. Caesar must strictly be RED."
                    ))
                    if not any(sr.scene_id == s.scene_id for sr in scene_repairs):
                        scene_repairs.append(SceneRepairInstruction(
                            scene_id=s.scene_id,
                            problem="Caesar faction color inverted to blue",
                            required_change="Designate Caesar as the solid bright red 3D stick figure with gold toy crown",
                            suggested_visual_direction="Solid bright red 3D stick figure (Caesar with toy gold wire crown)"
                        ))

                if re.search(r"\bred\s+(3d\s+)?(stick\s+figure|stickman|figures|stickmen)\s*\((conspirators?|assassins?|liberatores?|cimber|casca|brutus)\)", p_lower):
                    align_findings.append(AlignmentFinding(
                        scene_id=s.scene_id,
                        issue=f"FACTION INVERSION in scene #{s.scene_id}: Conspirators are described as RED 3D stick figures. Conspirators must strictly be BLUE."
                    ))
                    if not any(sr.scene_id == s.scene_id for sr in scene_repairs):
                        scene_repairs.append(SceneRepairInstruction(
                            scene_id=s.scene_id,
                            problem="Conspirators faction color inverted to red",
                            required_change="Designate conspirators and senators as solid blue 3D stick figures",
                            suggested_visual_direction="Solid blue 3D stick figures (conspirators and senators)"
                        ))
            elif not is_stickman_storyboard:
                # In non-stickman styles (e.g. Century-Old Photograph, Paper-Cutout), ANY stickman mention is a critical defect
                if any(k in p_lower for k in ["stickman", "stick figure", "stickmen", "red 3d stick", "blue 3d stick"]):
                    align_findings.append(AlignmentFinding(
                        scene_id=s.scene_id,
                        issue=f"CRITICAL STYLE VIOLATION in scene #{s.scene_id}: 3D stick figure detected in non-stickman visual style."
                    ))
                    if not any(sr.scene_id == s.scene_id for sr in scene_repairs):
                        scene_repairs.append(SceneRepairInstruction(
                            scene_id=s.scene_id,
                            problem="3D stick figure leaked into non-stickman visual style",
                            required_change="Replace stick figure with visual subjects matching narrative style",
                            suggested_visual_direction=f"Visual figures matching spoken narration: {s.narration_excerpt[:60]}"
                        ))

            # 2. Pipeline Scaffolding / Fallback Leaks Check
            if any(k in s.prompt for k in ["Active progression:", "Consequential development:", "Establishing perspective:", "Setting: Fortified"]):
                align_findings.append(AlignmentFinding(
                    scene_id=s.scene_id,
                    issue=f"Pipeline scaffolding leak in scene #{s.scene_id}: Internal planning tags found in prompt."
                ))
                if not any(sr.scene_id == s.scene_id for sr in scene_repairs):
                    scene_repairs.append(SceneRepairInstruction(
                        scene_id=s.scene_id,
                        problem="Internal pipeline tags leaked into prompt",
                        required_change="Regenerate clean natural language prompt without planning tags",
                        suggested_visual_direction=f"Clean prompt visualizing: {s.narration_excerpt[:60]}"
                    ))

            # 3. Premature Assassination Action Check (outdoor/street scenes depicting Curia ambush)
            if is_caesar:
                is_outdoor_street = any(k in narr_lower for k in ["street", "crowd", "litter", "soothsayer", "spurinna", "artemidorus", "journey", "route", "morning of the ides", "domus"])
                has_ambush_visual = any(k in p_lower or k in subj_lower for k in ["knees with hands clasped in a false plea", "tillius cimber is on his knees", "glint of steel", "pack of starving wolves", "daggers concealed within the heavy folds"])
                if is_outdoor_street and has_ambush_visual:
                    align_findings.append(AlignmentFinding(
                        scene_id=s.scene_id,
                        issue=f"CRITICAL CHRONOLOGY VIOLATION in scene #{s.scene_id}: Street/outdoor narration depicts premature Senate assassination ambush."
                    ))
                    if not any(sr.scene_id == s.scene_id for sr in scene_repairs):
                        scene_repairs.append(SceneRepairInstruction(
                            scene_id=s.scene_id,
                            problem="Assassination ambush depicted prematurely outside Senate",
                            required_change="Replace with outdoor street, litter procession, or crowd visual matching narration",
                            suggested_visual_direction=f"Crowded Roman stone avenue with citizens and litter: {s.narration_excerpt[:60]}"
                        ))

            # 4. Premature Overland Ship Transport Reveal (depicting overland naval transport before narrated)
            if is_1453:
                has_overland_visual = any(k in p_lower or k in subj_lower for k in ["overland transit", "wooden trackway", "dragged overland", "greased wooden platform", "hauling warship", "wooden rollers", "warship is positioned on a greased"])
                narr_has_overland = any(k in narr_lower for k in ["overland", "greased", "transported", "dragged across", "another direction"])
                if has_overland_visual and not narr_has_overland:
                    align_findings.append(AlignmentFinding(
                        scene_id=s.scene_id,
                        issue=f"CRITICAL CHRONOLOGY VIOLATION in scene #{s.scene_id}: Overland naval transport or trackway depicted before the operation is narrated."
                    ))
                    if not any(sr.scene_id == s.scene_id for sr in scene_repairs):
                        if any(k in narr_lower for k in ["chain", "harbor", "golden horn"]):
                            fix_change = "Depict the entrance of the Golden Horn harbor blocked by the massive defensive iron chain"
                            fix_dir = "Massive heavy iron chain anchored between stone towers across the water, blocking the Ottoman fleet"
                        else:
                            fix_change = "Depict the 1453 Ottoman forces arriving and encamping outside the Theodosian land walls"
                            fix_dir = "Ottoman forces and commanders encamped outside the massive Theodosian land fortifications"
                        scene_repairs.append(SceneRepairInstruction(
                            scene_id=s.scene_id,
                            problem="Premature depiction of overland naval transit",
                            required_change=fix_change,
                            suggested_visual_direction=fix_dir
                        ))

                # 5. Premature Discarded Imperial Insignia Reveal (depicting fallen crown before narration)
                has_discarded_regalia = any(k in p_lower or k in subj_lower for k in ["discarded", "thrown away", "falling away"]) and any(k in p_lower or k in subj_lower for k in ["insignia", "crown", "regalia", "sash"])
                narr_has_discarded = any(k in narr_lower for k in ["insignia", "threw away", "disappearing", "last emperor"])
                if has_discarded_regalia and not narr_has_discarded:
                    align_findings.append(AlignmentFinding(
                        scene_id=s.scene_id,
                        issue=f"CRITICAL CHRONOLOGY VIOLATION in scene #{s.scene_id}: Discarded imperial insignia/crown depicted before the narrative describes Constantine shedding his regalia."
                    ))
                    if not any(sr.scene_id == s.scene_id for sr in scene_repairs):
                        scene_repairs.append(SceneRepairInstruction(
                            scene_id=s.scene_id,
                            problem="Premature depiction of discarded imperial insignia",
                            required_change="Depict Emperor Constantine XI in full imperial armor actively commanding the night defense atop the battlements",
                            suggested_visual_direction="Emperor Constantine XI in ornate Byzantine imperial armor leading exhausted defenders during the desperate night assault"
                        ))

            # Anachronism & Contradiction check (for historical packs)
            if is_1453 or is_caesar:
                if any(w in p_lower or w in subj_lower for w in ["tokyo", "laser", "neon skyscrapers", "denim", "holographic", "astronaut", "lunar", "spacesuit"]):
                    align_findings.append(AlignmentFinding(
                        scene_id=s.scene_id,
                        issue=f"Contradictory / anachronistic visual elements detected in scene #{s.scene_id}: {s.prompt[:80]}"
                    ))
                    if not any(sr.scene_id == s.scene_id for sr in scene_repairs):
                        scene_repairs.append(SceneRepairInstruction(
                            scene_id=s.scene_id,
                            problem="Anachronistic or contradictory content",
                            required_change="Align strictly with narrative period",
                            suggested_visual_direction="Visual reconstruction matching spoken narration"
                        ))

            # Style violation check for stickman (inspect positive prompt description, ignoring negative prompt exclusions)
            if "stickman" in p_lower:
                pos_prompt = p_lower.split("strict negative:")[0]
                violation_phrases = ["realistic beard", "realistic mustache", "human skin texture", "realistic face", "realistic facial features"]
                for w in violation_phrases:
                    for m in re.finditer(re.escape(w), pos_prompt):
                        start_ctx = max(0, m.start() - 25)
                        prefix = pos_prompt[start_ctx:m.start()].lower()
                        if not any(neg in prefix for neg in ["no ", "zero ", "without ", "never ", "not "]):
                            align_findings.append(AlignmentFinding(
                                scene_id=s.scene_id,
                                issue=f"Style fidelity violation in scene #{s.scene_id}: Realistic human facial attributes found in 3D stickman prompt."
                            ))
                            break

        # Check identical action copy-pasting across any scenes in storyboard
        action_map = {}
        for s in scenes:
            m_act = re.search(r"Action:\s*([^.]+)\.", s.prompt)
            if m_act:
                act_str = m_act.group(1).strip()
                if len(act_str) > 20:
                    if act_str in action_map:
                        prev_sid = action_map[act_str]
                        rep_findings.append(RepetitionFinding(
                            scene_ids=[prev_sid, s.scene_id],
                            reason=f"Scenes #{prev_sid} and #{s.scene_id} share identical copy-pasted action: '{act_str[:50]}...'",
                            severity="critical"
                        ))
                        if not any(sr.scene_id == s.scene_id for sr in scene_repairs):
                            scene_repairs.append(SceneRepairInstruction(
                                scene_id=s.scene_id,
                                problem="Duplicate action prompt copy-pasted from another scene",
                                required_change="Generate distinct unique visual action for this narration moment",
                                suggested_visual_direction=f"Unique action depicting: {s.narration_excerpt[:60]}"
                            ))
                    else:
                        action_map[act_str] = s.scene_id

        # Merge Groq parsed findings if any
        for rf in parsed.get("repetition_findings", []):
            if isinstance(rf, dict) and rf.get("scene_ids"):
                raw_sev = str(rf.get("severity", "warning")).lower()
                sev = "critical" if raw_sev in ("critical", "error", "high", "severe") else "warning"
                rep_findings.append(RepetitionFinding(
                    scene_ids=[str(x) for x in rf.get("scene_ids", [])],
                    reason=rf.get("reason", "Visual repetition detected"),
                    severity=sev
                ))

        for af in parsed.get("alignment_findings", []):
            if isinstance(af, dict) and af.get("scene_id"):
                align_findings.append(AlignmentFinding(
                    scene_id=str(af.get("scene_id")),
                    issue=af.get("issue", "Narration alignment issue")
                ))

        for sr in parsed.get("scene_repairs", []):
            if isinstance(sr, dict) and sr.get("scene_id"):
                sid = str(sr.get("scene_id")).strip().lstrip("#")
                sid_norm = f"{int(sid):03d}" if sid.isdigit() else sid
                has_issue = any(af.scene_id in (sid, sid_norm) for af in align_findings) or any(sid in rf.scene_ids or sid_norm in rf.scene_ids for rf in rep_findings)
                if has_issue and not any(x.scene_id in (sid, sid_norm) for x in scene_repairs):
                    scene_repairs.append(SceneRepairInstruction(
                        scene_id=sid_norm,
                        problem=sr.get("problem", "Needs visual improvement"),
                        required_change=sr.get("required_change", "Introduce distinct visual development"),
                        suggested_visual_direction=sr.get("suggested_visual_direction", "Show action or consequence")
                    ))

        # Mathematically exact, reproducible category scoring
        align_pen = len([af for af in align_findings if "chronology" in af.issue.lower() or "mismatch" in af.issue.lower()]) * 10.0
        char_pen = len([af for af in align_findings if "faction" in af.issue.lower()]) * 15.0
        prompt_pen = len([af for af in align_findings if "scaffolding" in af.issue.lower()]) * 10.0
        rep_pen = len(rep_findings) * 8.0
        time_pen = len(timing_findings) * 15.0

        cat_align = max(30.0, min(100.0, 95.0 - align_pen))
        cat_variety = max(30.0, min(100.0, 95.0 - rep_pen))
        cat_pacing = max(30.0, min(100.0, 98.0 - time_pen))
        cat_continuity = max(30.0, min(100.0, 95.0 - char_pen))
        cat_style = 95.0
        cat_prompt = max(30.0, min(100.0, 95.0 - prompt_pen))

        category_scores = CategoryScores(
            narration_alignment=cat_align,
            visual_progression=cat_variety,
            temporal_pacing=cat_pacing,
            continuity=cat_continuity,
            style_fidelity=cat_style,
            prompt_quality=cat_prompt
        )

        # Explicit weighted mathematical score (Weight sum = 100)
        # Weights: align=25, continuity=20, variety=15, pacing=15, prompt=15, style=10
        overall_score = round(
            (0.25 * cat_align +
             0.20 * cat_continuity +
             0.15 * cat_variety +
             0.15 * cat_pacing +
             0.15 * cat_prompt +
             0.10 * cat_style),
            1
        )

        has_critical_defects = (
            len(timing_findings) > 0 or
            len(scene_repairs) > 0 or
            len(align_findings) > 0 or
            any(rf.severity == "critical" for rf in rep_findings) or
            overall_score < 85.0
        )

        if has_critical_defects:
            rec = "NEEDS_REPAIR"
            final_overall_score = round(min(overall_score, 74.0), 1)
        else:
            rec = "APPROVED"
            final_overall_score = round(min(100.0, max(85.0, overall_score)), 1)

        report = StoryboardAuditReport(
            overall_score=final_overall_score,
            category_scores=category_scores,
            repetition_findings=rep_findings,
            timing_findings=timing_findings,
            alignment_findings=align_findings,
            scene_repairs=scene_repairs,
            final_recommendation=rec
        )

        if progress_callback:
            progress_callback(2, 2, f"Audit complete. Overall score: {overall_score:.1f}/100. Status: {rec}")

        return report
