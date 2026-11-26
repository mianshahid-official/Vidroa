"""
Quality Gates for B-Roll Stock Video Clips in PromptBeast / Vidroa.
Enforces the 5 strict quality gates before any clip is accepted:
  1. Duration after trim is longer than 4 seconds and shorter than 10 seconds (4.0 < duration < 10.0).
  2. Resolution is at least 720p (min dimension >= 720 or width >= 1280).
  3. Not too dark and not blown out (mean brightness in [25.0, 230.0]).
  4. Actually moving (mean frame-to-frame difference >= motion_threshold).
  5. Tag match: at least 2 of the KEYWORDS appear in the clip's tags or title.
If no candidate passes all gates, the pipeline falls back to a generated image.
"""
import os
import re
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import numpy as np


# Minimum and maximum duration limits in seconds
MIN_VIDEO_DURATION = 4.0
MAX_VIDEO_DURATION = 10.0

# Brightness sane band (0-255 scale)
MIN_MEAN_BRIGHTNESS = 25.0
MAX_MEAN_BRIGHTNESS = 230.0

# Motion difference threshold (mean absolute difference between consecutive frames)
MOTION_DIFF_THRESHOLD = 2.0

# Minimum resolution threshold
MIN_RES_WIDTH = 1280
MIN_RES_HEIGHT = 720


def get_video_metadata(file_path: str) -> Dict[str, Any]:
    """Probes video duration, width, height using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration:format=duration",
        "-of", "json",
        str(file_path)
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        stream = data.get("streams", [{}])[0]
        fmt = data.get("format", {})
        dur = float(stream.get("duration") or fmt.get("duration") or 0.0)
        w = int(stream.get("width") or 0)
        h = int(stream.get("height") or 0)
        return {"duration": dur, "width": w, "height": h}
    except Exception as e:
        print(f"[QualityGates] ffprobe error on {file_path}: {e}")
        return {"duration": 0.0, "width": 0, "height": 0}


def extract_sampled_frames(file_path: str, num_frames: int = 5, width: int = 320, height: int = 180) -> Optional[np.ndarray]:
    """
    Extracts num_frames evenly distributed frames from the video as RGB24 numpy array (N, H, W, 3).
    Returns None if extraction fails.
    """
    cmd = [
        "ffmpeg", "-v", "error",
        "-i", str(file_path),
        "-vf", f"scale={width}:{height},fps=2",
        "-vframes", str(num_frames),
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "-"
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True)
        raw_bytes = proc.stdout
        expected_size = num_frames * width * height * 3
        actual_frames = len(raw_bytes) // (width * height * 3)
        if actual_frames < 2:
            return None
        arr = np.frombuffer(raw_bytes[: actual_frames * width * height * 3], dtype=np.uint8)
        return arr.reshape(actual_frames, height, width, 3)
    except Exception as e:
        print(f"[QualityGates] Frame extraction error on {file_path}: {e}")
        return None


def check_tag_match(keywords: List[str], tags: List[str], title: str = "") -> Tuple[bool, int, List[str]]:
    """
    Gate 5: Tag match check.
    At least 2 of the KEYWORDS must appear in the clip's tags or title.
    (If total keywords provided < 2, all provided keywords must appear).
    Returns (passed, match_count, matched_keywords).
    """
    if not keywords:
        return False, 0, []

    # Normalize tags and title text into a searchable blob
    blob = " ".join(tags).lower() + " " + title.lower()
    # Normalize punctuation
    blob_tokens = re.findall(r"\w+", blob)
    blob_text = " ".join(blob_tokens)

    matched = []
    for kw in keywords:
        kw_clean = kw.strip().lower()
        if not kw_clean:
            continue
        # Split multi-word keyword e.g. "flat 2D", "silver keys"
        words = re.findall(r"\w+", kw_clean)
        if not words:
            continue
        # Match if full keyword phrase is in blob, or if any substantial word matches
        if kw_clean in blob_text:
            matched.append(kw)
        elif all(w in blob_tokens for w in words):
            matched.append(kw)
        elif len(words) > 1 and any(w in blob_tokens for w in words if len(w) > 3):
            matched.append(kw)

    req_matches = 2 if len(keywords) >= 2 else len(keywords)
    passed = len(matched) >= req_matches
    return passed, len(matched), matched


def evaluate_quality_gates(
    candidate: Dict[str, Any],
    target_duration: float,
    keywords: List[str],
    video_file_path: Optional[str] = None,
) -> Tuple[bool, List[str]]:
    """
    Evaluates all 5 quality gates on a candidate video clip.
    Returns (all_passed: bool, failure_reasons: List[str]).
    """
    failures = []
    file_p = video_file_path or candidate.get("file_path")

    # Gate 1: Duration check
    # Both target scene duration and source clip duration must permit a clip strictly in (4.0, 10.0)
    eff_dur = float(candidate.get("duration") or 0.0)
    if file_p and Path(file_p).exists():
        meta = get_video_metadata(file_p)
        if meta["duration"] > 0:
            eff_dur = meta["duration"]

    if not (MIN_VIDEO_DURATION < target_duration < MAX_VIDEO_DURATION):
        failures.append(
            f"Gate 1 Failed (Duration): Scene duration ({target_duration:.2f}s) "
            f"not strictly between {MIN_VIDEO_DURATION}s and {MAX_VIDEO_DURATION}s."
        )
    elif eff_dur < MIN_VIDEO_DURATION or eff_dur < target_duration:
        failures.append(
            f"Gate 1 Failed (Duration): Source clip duration ({eff_dur:.1f}s) is shorter than target scene duration ({target_duration:.1f}s) or {MIN_VIDEO_DURATION}s."
        )

    # Gate 2: Resolution check (at least 720p)
    width = int(candidate.get("width") or 0)
    height = int(candidate.get("height") or 0)
    if file_p and Path(file_p).exists():
        meta = get_video_metadata(file_p)
        if meta["width"] > 0:
            width = meta["width"]
            height = meta["height"]

    is_720p = (width >= MIN_RES_WIDTH and height >= MIN_RES_HEIGHT) or (min(width, height) >= MIN_RES_HEIGHT)
    if not is_720p:
        failures.append(
            f"Gate 2 Failed (Resolution): Video resolution ({width}x{height}) is below 720p ({MIN_RES_WIDTH}x{MIN_RES_HEIGHT})."
        )

    # Gate 5: Tag match check (metadata-based)
    tags = candidate.get("tags") or []
    title = candidate.get("title") or ""
    tag_ok, match_cnt, matched_kw = check_tag_match(keywords, tags, title)
    if not tag_ok:
        failures.append(
            f"Gate 5 Failed (Tag Match): Only {match_cnt} keyword(s) matched in tags/title. "
            f"Required at least 2. (Keywords: {keywords}, Matched: {matched_kw})."
        )

    # Visual inspection gates (3 & 4) requiring downloaded video frames
    if file_p and Path(file_p).exists():
        frames = extract_sampled_frames(file_p, num_frames=5)
        if frames is not None and len(frames) >= 2:
            # Gate 3: Brightness check
            # Mean brightness across all sampled frames
            # Rec. 601 luma: Y = 0.299 R + 0.587 G + 0.114 B
            luma = 0.299 * frames[:, :, :, 0] + 0.587 * frames[:, :, :, 1] + 0.114 * frames[:, :, :, 2]
            mean_brightness = float(np.mean(luma))
            if mean_brightness < MIN_MEAN_BRIGHTNESS:
                failures.append(
                    f"Gate 3 Failed (Brightness): Clip is too dark (mean brightness {mean_brightness:.1f} < {MIN_MEAN_BRIGHTNESS})."
                )
            elif mean_brightness > MAX_MEAN_BRIGHTNESS:
                failures.append(
                    f"Gate 3 Failed (Brightness): Clip is blown out (mean brightness {mean_brightness:.1f} > {MAX_MEAN_BRIGHTNESS})."
                )

            # Gate 4: Motion check
            # Calculate mean frame-to-frame difference
            diffs = [
                np.mean(np.abs(frames[idx].astype(float) - frames[idx - 1].astype(float)))
                for idx in range(1, len(frames))
            ]
            mean_diff = float(np.mean(diffs))
            if mean_diff < MOTION_DIFF_THRESHOLD:
                failures.append(
                    f"Gate 4 Failed (Motion): Clip is effectively static (mean frame diff {mean_diff:.2f} < {MOTION_DIFF_THRESHOLD})."
                )
        else:
            failures.append("Gates 3 & 4 Inconclusive: Could not extract sample video frames for quality checks.")

    all_passed = (len(failures) == 0)
    return all_passed, failures


def trim_video_clip(input_path: str, output_path: str, target_duration: float) -> str:
    """
    Trims a video clip using FFmpeg to target_duration (strictly between 4.0s and 10.0s).
    """
    if not (MIN_VIDEO_DURATION < target_duration < MAX_VIDEO_DURATION):
        raise ValueError(
            f"Target duration {target_duration:.2f}s is outside valid B-roll bounds "
            f"({MIN_VIDEO_DURATION}s < dur < {MAX_VIDEO_DURATION}s)."
        )
    clamped_dur = float(target_duration)
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-ss", "0",
        "-t", f"{clamped_dur:.3f}",
        "-i", str(input_path),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-an",
        str(out_p.resolve())
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg trim failed: {proc.stderr}")

    return str(out_p.resolve())
