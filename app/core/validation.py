"""
Comprehensive validator for timelines, scene bounds, prompt quality, and continuity constraints.
"""
from typing import List, Optional
from app.models.scene import VisualScene, StoryContinuity
from app.models.timeline import NarrationData
from app.models.project import ProjectConfig, ImageCountMode
from app.models.validation import (
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)


class TimelineValidator:
    """Performs rigorous timeline and prompt validation."""

    CLICHE_FILLER_PHRASES = [
        "cinematic lighting",
        "mysterious atmosphere",
        "soft lighting",
        "octane render",
        "unreal engine 5",
        "photorealistic 8k",
        "masterpiece trending on artstation",
        "epic composition"
    ]

    @classmethod
    def validate_project(
        cls,
        scenes: List[VisualScene],
        narration: Optional[NarrationData] = None,
        config: Optional[ProjectConfig] = None,
        continuity: Optional[StoryContinuity] = None
    ) -> ValidationResult:
        issues: List[ValidationIssue] = []

        if not scenes:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                rule="NO_SCENES",
                message="Timeline has no generated scenes.",
                suggested_action="Run storyboard generation."
            ))
            return ValidationResult(is_valid=False, total_scenes_checked=0, issues=issues)

        # 1. Unique IDs & Sequential Order
        seen_ids = set()
        for idx, sc in enumerate(scenes):
            if sc.scene_id in seen_ids:
                issues.append(ValidationIssue(
                    scene_id=sc.scene_id,
                    severity=ValidationSeverity.ERROR,
                    rule="DUPLICATE_SCENE_ID",
                    message=f"Duplicate scene ID '{sc.scene_id}' detected at index {idx}.",
                    suggested_action="Renumber scenes sequentially."
                ))
            seen_ids.add(sc.scene_id)

        # 2. Timing Order and Gaps / Overlaps
        first_spoken = narration.words[0].start if (narration and narration.words) else 0.0
        total_narration_dur = narration.duration_seconds if narration else scenes[-1].end

        if scenes[0].start > first_spoken + 0.1:
            issues.append(ValidationIssue(
                scene_id=scenes[0].scene_id,
                severity=ValidationSeverity.WARNING,
                rule="INITIAL_GAP",
                message=f"First scene starts at {scenes[0].start}s, after initial spoken word at {first_spoken}s.",
                suggested_action="Adjust first scene start time to 0.0s."
            ))

        for i in range(len(scenes)):
            curr = scenes[i]

            # Start < End
            if curr.start >= curr.end:
                issues.append(ValidationIssue(
                    scene_id=curr.scene_id,
                    severity=ValidationSeverity.ERROR,
                    rule="INVALID_TIME_ORDER",
                    message=f"Scene {curr.scene_id} start time ({curr.start}s) >= end time ({curr.end}s).",
                    suggested_action="Fix scene start and end times."
                ))

            # Duration Consistency
            expected_dur = round(curr.end - curr.start, 3)
            if abs(curr.duration - expected_dur) > 0.05:
                issues.append(ValidationIssue(
                    scene_id=curr.scene_id,
                    severity=ValidationSeverity.WARNING,
                    rule="DURATION_MISMATCH",
                    message=f"Scene {curr.scene_id} duration ({curr.duration}s) does not match end - start ({expected_dur}s).",
                    suggested_action="Recalculate duration."
                ))

            # Duration Bounds check against config
            if config:
                if curr.duration < config.min_duration - 0.1:
                    issues.append(ValidationIssue(
                        scene_id=curr.scene_id,
                        severity=ValidationSeverity.INFO,
                        rule="DURATION_BELOW_MIN",
                        message=f"Scene {curr.scene_id} duration ({curr.duration}s) is shorter than minimum preferred ({config.min_duration}s).",
                        suggested_action="Consider merging with adjacent scene."
                    ))
                elif curr.duration > config.max_duration + 0.5:
                    issues.append(ValidationIssue(
                        scene_id=curr.scene_id,
                        severity=ValidationSeverity.INFO,
                        rule="DURATION_ABOVE_MAX",
                        message=f"Scene {curr.scene_id} duration ({curr.duration}s) exceeds preferred maximum ({config.max_duration}s).",
                        suggested_action="Consider splitting scene."
                    ))

            # Check gap / overlap with next scene
            if i < len(scenes) - 1:
                next_sc = scenes[i + 1]
                diff = round(next_sc.start - curr.end, 3)
                if abs(diff) > 0.05:
                    if diff > 0:
                        issues.append(ValidationIssue(
                            scene_id=curr.scene_id,
                            severity=ValidationSeverity.ERROR,
                            rule="TIMELINE_GAP",
                            message=f"Gap of {diff}s detected between Scene {curr.scene_id} (ends {curr.end}s) and Scene {next_sc.scene_id} (starts {next_sc.start}s).",
                            suggested_action="Snap boundaries together."
                        ))
                    else:
                        issues.append(ValidationIssue(
                            scene_id=curr.scene_id,
                            severity=ValidationSeverity.ERROR,
                            rule="TIMELINE_OVERLAP",
                            message=f"Overlap of {abs(diff)}s detected between Scene {curr.scene_id} and Scene {next_sc.scene_id}.",
                            suggested_action="Snap boundaries together."
                        ))

        # 3. Last Scene Coverage
        last_scene = scenes[-1]
        if narration and total_narration_dur > 0 and last_scene.end < (total_narration_dur - 0.5):
            issues.append(ValidationIssue(
                scene_id=last_scene.scene_id,
                severity=ValidationSeverity.WARNING,
                rule="INCOMPLETE_COVERAGE",
                message=f"Last scene ends at {last_scene.end}s, before total narration ends at {total_narration_dur}s.",
                suggested_action="Extend last scene to narration end."
            ))

        # 4. Target Image Count Check
        if config and config.image_count_mode == ImageCountMode.EXACT:
            if len(scenes) != config.target_image_count:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    rule="EXACT_COUNT_MISMATCH",
                    message=f"Scene count ({len(scenes)}) does not match requested exact count ({config.target_image_count}).",
                    suggested_action="Regenerate with exact count redistribution or adjust manually."
                ))

        # 5. Prompt Quality Checks
        for idx, sc in enumerate(scenes):
            if not sc.visual_subject or not sc.visual_subject.strip():
                issues.append(ValidationIssue(
                    scene_id=sc.scene_id,
                    severity=ValidationSeverity.ERROR,
                    rule="MISSING_VISUAL_SUBJECT",
                    message=f"Scene {sc.scene_id} has no visual subject defined.",
                    suggested_action="Enter visual subject or regenerate scene."
                ))

            if not sc.prompt or not sc.prompt.strip():
                issues.append(ValidationIssue(
                    scene_id=sc.scene_id,
                    severity=ValidationSeverity.ERROR,
                    rule="EMPTY_PROMPT",
                    message=f"Scene {sc.scene_id} has an empty image prompt.",
                    suggested_action="Generate prompt for scene."
                ))
            else:
                words = sc.prompt.strip().split()
                if len(words) < 15:
                    issues.append(ValidationIssue(
                        scene_id=sc.scene_id,
                        severity=ValidationSeverity.WARNING,
                        rule="SHORT_PROMPT",
                        message=f"Scene {sc.scene_id} prompt is too short ({len(words)} words; recommend >= 25 words).",
                        suggested_action="Enrich scene with framing, environment, lighting, and textures."
                    ))

                # Check duplicate consecutive prompts
                if idx > 0 and sc.prompt.strip() == scenes[idx - 1].prompt.strip():
                    issues.append(ValidationIssue(
                        scene_id=sc.scene_id,
                        severity=ValidationSeverity.WARNING,
                        rule="DUPLICATE_CONSECUTIVE_PROMPT",
                        message=f"Scene {sc.scene_id} has an identical prompt to preceding Scene {scenes[idx - 1].scene_id}.",
                        suggested_action="Differentiate visual framing or merge scenes."
                    ))

                # Check filler phrases
                lower_p = sc.prompt.lower()
                matched_fillers = [f for f in cls.CLICHE_FILLER_PHRASES if f in lower_p]
                if matched_fillers:
                    issues.append(ValidationIssue(
                        scene_id=sc.scene_id,
                        severity=ValidationSeverity.INFO,
                        rule="GENERIC_FILLER_DETECTED",
                        message=f"Scene {sc.scene_id} contains generic filler phrases: {', '.join(matched_fillers)}.",
                        suggested_action="Replace with concrete physical lighting and camera descriptions."
                    ))

                # Check excessive verbosity (target 50-90 words)
                if len(words) > 135:
                    issues.append(ValidationIssue(
                        scene_id=sc.scene_id,
                        severity=ValidationSeverity.INFO,
                        rule="EXCESSIVE_VERBOSITY",
                        message=f"Scene {sc.scene_id} prompt has {len(words)} words (recommended: 50-90 words). Consider trimming aesthetic filler.",
                        suggested_action="Streamline prompt to 50-90 words focusing on action, setting, and composition."
                    ))

        # 6. Repetitive Visual Loop Detection across consecutive scenes
        import re
        for idx in range(1, len(scenes)):
            prev = scenes[idx - 1]
            curr = scenes[idx]
            prev_t = f"{prev.visual_subject} {getattr(prev, 'action', '')}".lower()
            curr_t = f"{curr.visual_subject} {getattr(curr, 'action', '')}".lower()
            prev_tokens = set(re.findall(r"\b[a-z]{4,}\b", prev_t))
            curr_tokens = set(re.findall(r"\b[a-z]{4,}\b", curr_t))
            overlap = len(prev_tokens & curr_tokens)
            union = len(prev_tokens | curr_tokens) if (prev_tokens or curr_tokens) else 1
            if (overlap / float(union) > 0.65) or (prev.visual_subject.strip().lower() == curr.visual_subject.strip().lower()):
                issues.append(ValidationIssue(
                    scene_id=curr.scene_id,
                    severity=ValidationSeverity.WARNING,
                    rule="REPETITIVE_VISUAL_LOOP",
                    message=f"Scene {curr.scene_id} repeats the visual subject/action of Scene {prev.scene_id} without new narrative progression.",
                    suggested_action="Differentiate with progressive action, consequence, or new visual fact."
                ))

        # 7. Historical Anachronism Check
        if continuity and getattr(continuity, "time_period", None):
            tp = continuity.time_period
            tp_text = f"{tp.era} {tp.decade_or_year or ''}".lower()
            is_pre_1826 = any(w in tp_text for w in ["1453", "medieval", "crusade", "byzantine", "rome", "roman", "greece", "greek", "ancient", "1500", "1600", "1700"])
            if is_pre_1826:
                for sc in scenes:
                    full_p = f"{sc.visual_subject} {sc.prompt}".lower()
                    if "fez" in full_p:
                        issues.append(ValidationIssue(
                            scene_id=sc.scene_id,
                            severity=ValidationSeverity.WARNING,
                            rule="ANACHRONISM_DETECTED",
                            message=f"Scene {sc.scene_id} references a 'fez', which is anachronistic for pre-1826 historical settings.",
                            suggested_action="Replace fez with period-appropriate turban or helmet."
                        ))

        has_errors = any(i.severity == ValidationSeverity.ERROR for i in issues)
        return ValidationResult(
            is_valid=(not has_errors),
            total_scenes_checked=len(scenes),
            issues=issues
        )
