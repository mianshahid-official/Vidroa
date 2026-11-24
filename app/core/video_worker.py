"""
B-Roll Video Worker for PromptBeast / Vidroa.
Processes video storyboard scenes:
  1. Searches stock footage from Pexels / Pixabay (with style priority).
  2. Downloads top 3 candidates per scene.
  3. Evaluates the 5 strict quality gates.
  4. Trims the chosen candidate to scene duration (4.0 - 10.0s).
  5. Applies style grading (century-old sepia/grain/vignette or flat 2D cartoonize).
  6. Falls back to generated image if no candidate passes all gates.
"""
import os
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor

from app.models.scene import VisualScene
from app.core.video_parser import parse_video_visual
from app.core.stock_video_service import StockVideoService
from app.core.video_quality_gates import evaluate_quality_gates, trim_video_clip, MIN_VIDEO_DURATION, MAX_VIDEO_DURATION
from app.core.video_style_grader import grade_video_clip


class VideoWorker:
    """Worker handling search, download, gate validation, trimming, and grading for video scenes."""

    @classmethod
    def process_scene(
        cls,
        scene: VisualScene,
        style_id: str = "century_old_photograph",
        cache_dir: Optional[str] = None,
        candidate_provider: Optional[Callable[[List[str], str], List[Dict[str, Any]]]] = None,
        downloader: Optional[Callable[[Dict[str, Any], str], Optional[str]]] = None,
    ) -> Dict[str, Any]:
        """
        Processes a single video scene.
        Returns a result summary dict with success, active_candidate, fallback_needed.
        """
        # Ensure video fields are populated from visual description if needed
        if not scene.video_keywords or not scene.video_shot_description:
            parsed = parse_video_visual(scene.visual_idea or scene.visual_subject)
            if parsed:
                scene.is_video = True
                scene.video_shot_description = parsed["shot_description"]
                scene.video_keywords = parsed["keywords"]

        keywords = scene.video_keywords or [scene.visual_subject]
        target_dur = max(MIN_VIDEO_DURATION + 0.1, min(MAX_VIDEO_DURATION - 0.1, scene.duration))

        # Setup scene cache directory
        base_cache = Path(cache_dir or "video_cache")
        scene_cache = base_cache / f"scene_{scene.scene_id}"
        scene_cache.mkdir(parents=True, exist_ok=True)

        run_log = []
        run_log.append(f"[VideoWorker] Scene {scene.scene_id}: Searching stock video with keywords: {keywords}")

        # 1. Search candidates
        treatment = getattr(scene, "treatment", None)
        if candidate_provider:
            candidates = candidate_provider(keywords, style_id)
        else:
            candidates = StockVideoService.search_candidates(
                keywords=keywords,
                style_id=style_id,
                treatment=treatment,
                max_candidates=3
            )

        if not candidates:
            run_log.append(f"[VideoWorker] Scene {scene.scene_id}: No stock video candidates found.")

        # 2. Download and evaluate candidates
        valid_candidates = []
        for idx, cand in enumerate(candidates[:3]):
            cand_id = cand.get("candidate_id") or f"cand_{idx+1}"
            raw_path = str(scene_cache / f"{cand_id}_raw.mp4")

            # Download or copy file
            if downloader:
                file_p = downloader(cand, raw_path)
            else:
                if cand.get("file_path") and Path(cand.get("file_path")).exists():
                    file_p = cand.get("file_path")
                else:
                    file_p = StockVideoService.download_candidate(cand, raw_path)

            if not file_p or not Path(file_p).exists():
                cand["gate_passed"] = False
                cand["failure_reasons"] = ["Download failed"]
                continue

            cand["file_path"] = str(file_p)

            # Evaluate 5 Quality Gates
            passed, reasons = evaluate_quality_gates(
                candidate=cand,
                target_duration=target_dur,
                keywords=keywords,
                video_file_path=file_p
            )

            cand["gate_passed"] = passed
            cand["failure_reasons"] = reasons

            if passed:
                try:
                    # Trim candidate to scene duration
                    trimmed_p = str(scene_cache / f"{cand_id}_trimmed.mp4")
                    trim_video_clip(file_p, trimmed_p, target_dur)

                    # Style grading
                    graded_p = str(scene_cache / f"{cand_id}_graded.mp4")
                    grade_video_clip(trimmed_p, graded_p, style_id=style_id, treatment=treatment)

                    cand["trimmed_path"] = trimmed_p
                    cand["graded_path"] = graded_p
                    valid_candidates.append(cand)
                    run_log.append(f"[VideoWorker] Scene {scene.scene_id}: Candidate {cand_id} passed all gates.")
                except Exception as e:
                    cand["gate_passed"] = False
                    cand["failure_reasons"].append(f"Trim/Grade error: {e}")
                    run_log.append(f"[VideoWorker] Scene {scene.scene_id}: Error processing candidate {cand_id}: {e}")
            else:
                run_log.append(
                    f"[VideoWorker] Scene {scene.scene_id}: Candidate {cand_id} rejected. Reasons: {'; '.join(reasons)}"
                )

        scene.video_candidates = candidates

        # 3. Decision: Accepted or Fallback
        if valid_candidates:
            # Pick first valid candidate
            chosen = valid_candidates[0]
            scene.video_path = chosen.get("graded_path")
            scene.active_candidate_index = candidates.index(chosen)
            scene.is_video = True
            scene.is_video_fallback_to_image = False
            scene.generation_status = "video_ready"
            run_log.append(f"[VideoWorker] Scene {scene.scene_id}: Approved video clip placed: {scene.video_path}")
            return {
                "success": True,
                "scene_id": scene.scene_id,
                "video_path": scene.video_path,
                "fallback_needed": False,
                "log": run_log,
            }
        else:
            # Fall back to generated image
            fallback_msg = f"[VIDEO FALLBACK] Scene {scene.scene_id}: No candidate passed all quality gates. Falling back to generated image."
            print(fallback_msg)
            run_log.append(fallback_msg)
            scene.is_video_fallback_to_image = True
            scene.is_video = False
            scene.video_path = None
            scene.generation_status = "pending"
            return {
                "success": False,
                "scene_id": scene.scene_id,
                "video_path": None,
                "fallback_needed": True,
                "log": run_log,
            }

    @classmethod
    def re_roll_candidate(
        cls,
        scene: VisualScene,
    ) -> bool:
        """
        Swaps in the next already-downloaded candidate that passed quality gates.
        Returns True if a new candidate was swapped in.
        """
        candidates = scene.video_candidates or []
        passing = [c for c in candidates if c.get("gate_passed") and c.get("graded_path")]
        if len(passing) <= 1:
            return False

        # Find current index in passing list
        current_path = scene.video_path
        cur_idx = 0
        for i, c in enumerate(passing):
            if c.get("graded_path") == current_path:
                cur_idx = i
                break

        next_idx = (cur_idx + 1) % len(passing)
        next_cand = passing[next_idx]
        scene.video_path = next_cand.get("graded_path")
        scene.active_candidate_index = candidates.index(next_cand)
        return True
