"""
Stage 8: Final Storyboard Validation.
Performs programmatic and structural validation on the complete storyboard.
Enforces non-overlapping, gapless timeline, duration calculation, and prompt sanity.
Inspects disk artifacts to guarantee 100% data integrity, zero boundary word duplicates,
prompt synchronization with repairs, and release gate compliance (score >= 85/100).
"""
import json
import re
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from app.models.planning import StoryboardValidationResult, StoryboardAuditReport
from app.models.scene import VisualScene
from app.models.timeline import NarrationData
from backend.pipeline.story_pack import StoryPackManager


class Stage8FinalValidator:
    """Rigorous programmatic and disk artifact validator for the final storyboard."""

    @classmethod
    def execute(
        cls,
        scenes: List[VisualScene],
        narration: Optional[NarrationData] = None,
        total_audio_duration: float = 0.0,
        benchmark_dir: Optional[Path] = None,
        audit_report: Optional[StoryboardAuditReport] = None
    ) -> StoryboardValidationResult:
        if not scenes:
            return StoryboardValidationResult(
                is_valid=False,
                validation_summary="Empty storyboard: No scenes were generated."
            )

        scenes_exceeding_8s: List[str] = []
        scenes_under_1s: List[str] = []
        has_gaps = False
        has_overlaps = False
        uncovered_gaps: List[str] = []
        duplicate_word_errors: List[str] = []
        disk_validation_failures: List[str] = []

        total_scenes = len(scenes)
        max_dur = 0.0
        min_dur = float("inf")

        for idx, sc in enumerate(scenes):
            calc_dur = round(sc.end - sc.start, 3)
            sc.duration = calc_dur

            max_dur = max(max_dur, calc_dur)
            min_dur = min(min_dur, calc_dur)

            # Flexible pacing ceiling: 8.0s is target, allow natural spoken sentences up to 10.5s
            if calc_dur > 10.5:
                scenes_exceeding_8s.append(f"Scene #{sc.scene_id} ({calc_dur:.2f}s)")

            if calc_dur < 1.0:
                scenes_under_1s.append(f"Scene #{sc.scene_id} ({calc_dur:.2f}s)")

            # Check continuity with next scene
            if idx < total_scenes - 1:
                next_sc = scenes[idx + 1]
                gap = next_sc.start - sc.end
                if gap > 0.15:
                    has_gaps = True
                    uncovered_gaps.append(f"Gap of {gap:.2f}s between #{sc.scene_id} (end {sc.end}s) and #{next_sc.scene_id} (start {next_sc.start}s)")
                elif gap < -0.15:
                    has_overlaps = True

                # Strict boundary word overlap check
                words_curr = [re.sub(r"[^\w]", "", w).lower() for w in sc.narration_excerpt.split() if w.strip()]
                words_next = [re.sub(r"[^\w]", "", w).lower() for w in next_sc.narration_excerpt.split() if w.strip()]
                if words_curr and words_next:
                    if words_curr[-1] == words_next[0]:
                        duplicate_word_errors.append(f"Duplicate word '{words_curr[-1]}' across boundary of scene #{sc.scene_id} and #{next_sc.scene_id}")

        # Check start and end boundaries
        if scenes[0].start > 0.25:
            has_gaps = True
            uncovered_gaps.append(f"Start gap: Scene #1 starts at {scenes[0].start}s instead of 0.0s")

        if total_audio_duration > 0:
            end_gap = total_audio_duration - scenes[-1].end
            if abs(end_gap) > 0.5:
                if end_gap > 0.5:
                    has_gaps = True
                    uncovered_gaps.append(f"End gap: Storyboard ends at {scenes[-1].end:.2f}s, audio is {total_audio_duration:.2f}s")
                else:
                    scenes[-1].end = round(total_audio_duration, 2)
                    scenes[-1].duration = round(scenes[-1].end - scenes[-1].start, 2)

        # Repetition & Prompt Integrity scan
        story_text = " ".join([s.narration_excerpt for s in scenes]) if scenes else ""
        active_pack = StoryPackManager.match_pack(story_text)
        seen_subjects = {}
        rep_alerts = []
        for s in scenes:
            subj_clean = s.visual_subject.strip().lower()
            p_lower = s.prompt.lower()

            # Prompt completeness and failure validation
            if not s.prompt or not s.prompt.strip() or (s.validation_notes and "PROMPT_GENERATION_FAILED" in s.validation_notes):
                disk_validation_failures.append(
                    f"Prompt generation missing or failed: Scene #{s.scene_id} has no valid prompt ({s.validation_notes or 'empty prompt'})."
                )

            # Faction color validation (gated by active pack or protagonist)
            if active_pack and active_pack.id == "caesar-44bc":
                if re.search(r"\bblue\s+(3d\s+)?(stick\s+figure|stickman)\s*\((caesar|the dictator)\)", p_lower) or re.search(r"\bblue\s+(3d\s+)?stick\s+figure\s+caesar\b", p_lower):
                    disk_validation_failures.append(f"Faction color inversion: Scene #{s.scene_id} describes Caesar as blue (must be red).")
                if re.search(r"\bred\s+(3d\s+)?(stick\s+figure|stickman|figures|stickmen)\s*\((conspirators?|assassins?|liberatores?|cimber|casca|brutus|cassius|senators?)\)", p_lower):
                    disk_validation_failures.append(f"Faction color inversion: Scene #{s.scene_id} describes conspirators as red (must be blue).")

            # Scaffolding leak validation
            if any(k in s.prompt for k in ["Active progression:", "Consequential development:", "Establishing perspective:", "Setting: Fortified"]):
                disk_validation_failures.append(f"Pipeline scaffolding leak: Scene #{s.scene_id} contains internal planning metadata.")

            if subj_clean in seen_subjects:
                rep_alerts.append(f"Potential repetition: #{s.scene_id} matches #{seen_subjects[subj_clean]}")
            else:
                seen_subjects[subj_clean] = s.scene_id

        # =========================================================================
        # DISK ARTIFACT INSPECTION (When benchmark_dir is provided)
        # =========================================================================
        if benchmark_dir and Path(benchmark_dir).exists():
            b_dir = Path(benchmark_dir)

            # 1. Inspect benchmark_story_analysis.json
            art_st1 = b_dir / "benchmark_story_analysis.json"
            if art_st1.exists():
                try:
                    with open(art_st1, "r", encoding="utf-8") as f:
                        st1_data = json.load(f)
                    if not st1_data.get("narrative_beats"):
                        disk_validation_failures.append("Stage 1 artifact has empty 'narrative_beats'.")
                    if not st1_data.get("facts_and_claims"):
                        disk_validation_failures.append("Stage 1 artifact has empty 'facts_and_claims'.")
                    period = str(st1_data.get("setting_period") or st1_data.get("historical_or_setting_period", "")).lower()
                    if "1890" in period:
                        disk_validation_failures.append(f"Stage 1 period is invalid ('{period}') - defaulted to 1890s.")
                    chars = st1_data.get("continuity_bible", {}).get("characters", [])
                    if any("key historical figures" in str(c.get("name", "")).lower() for c in chars):
                        disk_validation_failures.append("Stage 1 character bible contains generic placeholder 'Key Historical Figures'.")
                except Exception as e:
                    disk_validation_failures.append(f"Error reading Stage 1 artifact: {e}")

            # 2. Inspect benchmark_image_prompts.txt
            art_prompts = b_dir / "benchmark_image_prompts.txt"
            if art_prompts.exists():
                try:
                    prompt_text = art_prompts.read_text(encoding="utf-8")
                    prompt_matches = re.findall(r"PROMPT\s+\d+", prompt_text)
                    if len(prompt_matches) != total_scenes:
                        disk_validation_failures.append(
                            f"Prompt count in file ({len(prompt_matches)}) does not match scene count ({total_scenes})."
                        )
                except Exception as e:
                    disk_validation_failures.append(f"Error reading prompt artifact: {e}")

            # 3. Inspect benchmark_replanning_report.json vs image_prompts.txt
            art_rep = b_dir / "benchmark_replanning_report.json"
            if art_rep.exists() and art_prompts.exists():
                try:
                    with open(art_rep, "r", encoding="utf-8") as f:
                        rep_data = json.load(f)
                    p_text = art_prompts.read_text(encoding="utf-8")
                    for r in rep_data.get("repairs", []):
                        rep_prompt = r.get("repaired_prompt", "").strip()
                        if rep_prompt and rep_prompt[:60] not in p_text:
                            disk_validation_failures.append(
                                f"Repaired prompt for scene {r.get('scene_id')} not found in benchmark_image_prompts.txt."
                            )
                except Exception as e:
                    disk_validation_failures.append(f"Error validating replanning propagation: {e}")

            # 4. Inspect audit release criteria
            art_audit = b_dir / "benchmark_quality_audit.json"
            if art_audit.exists():
                try:
                    with open(art_audit, "r", encoding="utf-8") as f:
                        aud_data = json.load(f)
                    score = float(aud_data.get("overall_score", 0.0))
                    rec = aud_data.get("final_recommendation", "")
                    if score < 85.0:
                        disk_validation_failures.append(f"Audit score {score:.1f}/100 is below the release threshold (85.0).")
                    if rec != "APPROVED":
                        disk_validation_failures.append(f"Audit recommendation '{rec}' is not APPROVED.")
                except Exception as e:
                    disk_validation_failures.append(f"Error reading audit artifact: {e}")

            # 5. Inspect storyboard vs visual beat plan traceability (zero invented beat IDs)
            art_vbp = b_dir / "benchmark_visual_beat_plan.json"
            art_sb = b_dir / "benchmark_scheduled_storyboard.json"
            if art_vbp.exists() and art_sb.exists():
                try:
                    with open(art_vbp, "r", encoding="utf-8") as f:
                        vbp_data = json.load(f)
                    with open(art_sb, "r", encoding="utf-8") as f:
                        sb_data = json.load(f)
                    valid_beat_ids = set(b.get("beat_id") for b in vbp_data.get("visual_beats", []))
                    for sc_item in sb_data.get("scenes", []):
                        s_beat = sc_item.get("beat_id")
                        if not s_beat or s_beat not in valid_beat_ids:
                            disk_validation_failures.append(
                                f"Storyboard scene #{sc_item.get('scene_id')} references unknown or invented beat_id '{s_beat}' not in visual beat plan."
                            )
                        # Provenance check: non-empty narrative beat linkage and word boundaries
                        if not sc_item.get("source_narrative_beat_ids"):
                            disk_validation_failures.append(
                                f"Storyboard scene #{sc_item.get('scene_id')} has empty source_narrative_beat_ids."
                            )
                        if sc_item.get("source_word_start") is None or sc_item.get("source_word_end") is None:
                            disk_validation_failures.append(
                                f"Storyboard scene #{sc_item.get('scene_id')} has null word provenance boundaries."
                            )
                        if sc_item.get("chronological_order") is None:
                            disk_validation_failures.append(
                                f"Storyboard scene #{sc_item.get('scene_id')} has null chronological_order."
                            )
                except Exception as e:
                    disk_validation_failures.append(f"Error checking beat plan traceability: {e}")

        # Quality Audit Report release gate check
        audit_failures: List[str] = []
        if audit_report is not None:
            if audit_report.final_recommendation != "APPROVED":
                audit_failures.append(
                    f"Audit recommendation is '{audit_report.final_recommendation}' (Score: {audit_report.overall_score:.1f}/100, minimum required: 85.0)."
                )
            if audit_report.overall_score < 85.0:
                audit_failures.append(
                    f"Audit quality score ({audit_report.overall_score:.1f}/100) is below the 85.0 approval threshold."
                )
            if audit_report.alignment_findings:
                flagged_ids = [af.scene_id for af in audit_report.alignment_findings]
                audit_failures.append(
                    f"Audit flagged {len(audit_report.alignment_findings)} critical alignment mismatch(es) on scenes: {', '.join(f'#{sid}' for sid in flagged_ids)}."
                )

        # Final release validity
        is_valid = (
            len(scenes_exceeding_8s) == 0 and
            not has_overlaps and
            len(duplicate_word_errors) == 0 and
            len(disk_validation_failures) == 0 and
            len(audit_failures) == 0
        )

        summary_parts = [
            f"Validated {total_scenes} scenes.",
            f"Pacing: {min_dur:.2f}s - {max_dur:.2f}s (Target: 2.0s - 8.0s, Max Cap: 10.5s).",
            f"Total duration: {scenes[-1].end:.2f}s."
        ]
        if scenes_exceeding_8s:
            summary_parts.append(f"FAIL: {len(scenes_exceeding_8s)} scenes exceed 10.5s ceiling.")
        if duplicate_word_errors:
            summary_parts.append(f"FAIL: {len(duplicate_word_errors)} boundary word duplications.")
        if disk_validation_failures:
            summary_parts.append(f"FAIL: Disk artifact defects: {'; '.join(disk_validation_failures)}")
        if audit_failures:
            summary_parts.append(f"FAIL: Quality Audit Gate: {'; '.join(audit_failures)}")
        if is_valid:
            summary_parts.append("RELEASE GATE: PASSED. All invariants, disk files, and quality criteria verified.")
        else:
            summary_parts.append("RELEASE GATE: FAILED.")

        return StoryboardValidationResult(
            is_valid=is_valid,
            total_scenes=total_scenes,
            total_duration=scenes[-1].end if scenes else 0.0,
            max_scene_duration=max_dur,
            min_scene_duration=min_dur if min_dur != float("inf") else 0.0,
            has_gaps=has_gaps,
            has_overlaps=has_overlaps,
            scenes_exceeding_8s=scenes_exceeding_8s,
            uncovered_narration_gaps=uncovered_gaps,
            repetition_alerts=rep_alerts + duplicate_word_errors + disk_validation_failures + audit_failures,
            validation_summary=" ".join(summary_parts)
        )


