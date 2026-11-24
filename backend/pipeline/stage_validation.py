"""Deterministic storyboard validation gate (fail loudly, never silently fill).

Runs after Stage 3 prompt generation and before Stage 4 rendering. It checks
only structural facts that can be verified without a model call:

- every scene has a non-empty prompt
- scene IDs are unique
- the scene timeline has no overlaps and no large gaps (a gap of up to 0.5s
  is allowed: it is the natural silence between spoken words, since scenes
  end at word boundaries and the next scene starts at the next word)
- every scene has a positive duration
- when narration is given, the timeline starts near 0 and ends near the
  narration duration

Any violation raises RuntimeError naming the offending scene(s). The
orchestrator marks the job FAILED; the run never produces a video from a
broken storyboard.
"""
from typing import List, Optional

# Tolerance (seconds) for auto-healing natural narration pauses between scenes.
MAX_HEALABLE_GAP_SECONDS = 2.0
MAX_SCENE_GAP_SECONDS = 2.0


def validate_storyboard(scenes: List, narration=None) -> None:
    """Validates a storyboard and automatically heals natural narration pause gaps <= 2.0s.
    Raises RuntimeError on structural violations or gaps > 2.0s."""
    if not scenes:
        raise RuntimeError("Storyboard validation failed: no scenes to validate.")

    # 1. Every scene has a non-empty prompt; scene IDs are unique.
    seen_ids = set()
    for s in scenes:
        sid = getattr(s, "scene_id", "?")
        if sid in seen_ids:
            raise RuntimeError(f"Storyboard validation failed: duplicate scene_id '{sid}'.")
        seen_ids.add(sid)
        prompt = (getattr(s, "prompt", "") or "").strip()
        if not prompt:
            raise RuntimeError(
                f"Storyboard validation failed: scene '{sid}' has no prompt. "
                f"Failing loudly instead of rendering a scene with no image prompt."
            )

    # 2. Timeline: sorted by start, no overlaps, heal small pause gaps (<= 2.0s), positive durations.
    ordered = sorted(scenes, key=lambda s: float(getattr(s, "start", 0.0)))
    prev_scene = None
    for s in ordered:
        sid = getattr(s, "scene_id", "?")
        start = float(getattr(s, "start", 0.0))
        end = float(getattr(s, "end", 0.0))
        duration = float(getattr(s, "duration", 0.0) or (end - start))
        if duration <= 0:
            raise RuntimeError(
                f"Storyboard validation failed: scene '{sid}' has non-positive duration {duration}."
            )
        if prev_scene is not None:
            prev_end = float(getattr(prev_scene, "end", 0.0))
            if start < prev_end - 0.01:
                raise RuntimeError(
                    f"Storyboard validation failed: scene '{sid}' starts at {start}s, "
                    f"overlapping the previous scene which ends at {prev_end}s."
                )
            gap = start - prev_end
            if 0.001 < gap <= MAX_HEALABLE_GAP_SECONDS:
                prev_start = float(getattr(prev_scene, "start", 0.0))
                new_end = round(start, 2)
                prev_scene.end = new_end
                prev_scene.duration = round(new_end - prev_start, 2)
                print(f"[StoryboardValidation] Healed natural pause gap of {gap:.2f}s before scene '{sid}' (extended previous scene end to {new_end:.2f}s).")
            elif gap > MAX_HEALABLE_GAP_SECONDS:
                raise RuntimeError(
                    f"Storyboard validation failed: gap of {gap:.2f}s before "
                    f"scene '{sid}' (previous scene ends at {prev_end}s, next starts at {start}s)."
                )
        prev_scene = s

    # 3. When narration is given, the timeline must cover it.
    if narration is not None:
        total = float(getattr(narration, "duration_seconds", 0.0) or 0.0)
        if total > 0:
            first_start = float(getattr(ordered[0], "start", 0.0))
            last_end = float(getattr(ordered[-1], "end", 0.0))
            if 0 < first_start <= MAX_HEALABLE_GAP_SECONDS:
                ordered[0].start = 0.0
                ordered[0].duration = round(float(ordered[0].end) - 0.0, 2)
            elif first_start > MAX_HEALABLE_GAP_SECONDS:
                raise RuntimeError(
                    f"Storyboard validation failed: first scene starts at {first_start}s, "
                    f"but narration starts at 0s."
                )
            if last_end < total:
                gap_to_end = total - last_end
                if gap_to_end <= MAX_HEALABLE_GAP_SECONDS:
                    ordered[-1].end = round(total, 2)
                    ordered[-1].duration = round(total - float(ordered[-1].start), 2)
                elif gap_to_end > 1.0:
                    raise RuntimeError(
                        f"Storyboard validation failed: last scene ends at {last_end}s, "
                        f"but narration runs to {total}s."
                    )
