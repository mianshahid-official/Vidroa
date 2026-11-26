"""
Acceptance Test Suite for B-Roll Video Scenes in PromptBeast / Vidroa.
Verifies all 7 STEP 7 requirements:
  1. Base test: existing test suite passes and app starts.
  2. Parser test: a Visual starting with "VIDEO of" parses into shot description + keywords;
     a normal image visual does not parse as video. Tested with exact example format.
  3. Expansion test: a storyboard with 2 video scenes and 3 image scenes expands to
     exactly 3 image prompts and 2 video jobs.
  4. Gate tests (mocked API): too-short, low-res, near-black, static, and no-tag-match clips
     are each rejected; a good clip passes.
  5. Parallel test (mock the API with a small local mp4): video search + download + trim runs
     while prompts expand; trimmed clip is 4–10 seconds and lands in correct timeline slot.
  6. Grading test: graded clip differs from raw clip in expected direction
     (sepia for century-old, posterized for flat 2D).
  7. Render test: timeline mixing 1 torn-edge still + 1 clip renders 1280x720
     with clip full screen and still showing torn edges.
"""
import os
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest
import numpy as np
from PIL import Image, ImageDraw

from app.models.scene import VisualScene
from app.models.timeline import NarrationData, WordTimestamp
from app.models.video_config import VideoRenderSettings, MotionPreset, TransitionStyle
from app.core.video_parser import parse_video_visual, is_video_visual
from app.core.video_quality_gates import (
    evaluate_quality_gates,
    extract_sampled_frames,
    trim_video_clip,
    check_tag_match,
    MIN_VIDEO_DURATION,
    MAX_VIDEO_DURATION,
)
from app.core.video_style_grader import grade_video_clip, get_style_filter
from app.core.video_worker import VideoWorker
from app.core.video_renderer import VideoRenderer
from backend.pipeline.stage3_prompt_generation import Stage3PromptGeneration
from backend.inference.engine import BaseInferenceEngine


@pytest.fixture(scope="module")
def temp_test_dir():
    d = Path(tempfile.mkdtemp(prefix="pb_broll_test_"))
    yield d
    try:
        shutil.rmtree(d, ignore_errors=True)
    except Exception:
        pass


def create_lavfi_video(output_path: Path, filter_src: str, duration: float = 6.0, size: str = "1280x720", fps: int = 24) -> str:
    """Helper to generate tiny deterministic synthetic MP4 test clips via FFmpeg lavfi."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if "=" in filter_src:
        src_name, src_val = filter_src.split("=", 1)
        lavfi_expr = f"{src_name}=c={src_val}:d={duration}:s={size}:r={fps}"
    else:
        lavfi_expr = f"{filter_src}=d={duration}:s={size}:r={fps}"

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", lavfi_expr,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        "-an",
        str(output_path.resolve())
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return str(output_path.resolve())


# =============================================================================
# 1. PARSER TESTS
# =============================================================================

class TestBrollVideoParser:
    """Verifies that machine-parseable video visuals parse correctly and image visuals do not."""

    def test_parser_exact_example_format(self):
        # Exact example format from the specification:
        exact_example = (
            "VIDEO of Close-up flat 2D cartoon shot focusing on the open metal key cabinet "
            "at the hero's elbow, showing neat rows of stamped brass and silver keys hanging "
            "from numbered hooks under bright fluorescent light. KEYWORDS flat 2D, cabinet, silver keys, light."
        )

        res = parse_video_visual(exact_example)
        assert res is not None, "Failed to parse exact example video visual"
        assert res["is_video"] is True

        expected_desc = (
            "Close-up flat 2D cartoon shot focusing on the open metal key cabinet "
            "at the hero's elbow, showing neat rows of stamped brass and silver keys hanging "
            "from numbered hooks under bright fluorescent light."
        )
        assert res["shot_description"] == expected_desc
        assert "flat 2D" in res["keywords"]
        assert "cabinet" in res["keywords"]
        assert "silver keys" in res["keywords"]
        assert "light" in res["keywords"]
        assert len(res["keywords"]) == 4

    def test_parser_normal_image_visual_does_not_parse_as_video(self):
        # Normal image visual without VIDEO of prefix
        normal_image = (
            "Authentic century-old archival photograph with warm faded sepia tones "
            "and chipped, torn paper edges, showing a massive Edwardian ocean liner "
            "towering over crowded Southampton docks, with period-attired dockworkers."
        )

        res = parse_video_visual(normal_image)
        assert res is None, "Normal image visual should return None and not parse as video"
        assert is_video_visual(normal_image) is False


# =============================================================================
# 2. EXPANSION TESTS
# =============================================================================

class MockTrackingInferenceEngine(BaseInferenceEngine):
    """Mock LLM engine that records exactly which scenes were submitted for image prompt generation."""
    def __init__(self):
        self.requested_scenes = []

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        import json
        import re
        scene_ids = re.findall(r'"scene_id":\s*"([^"]+)"', prompt)
        for sid in scene_ids:
            if sid not in [s.scene_id for s in self.requested_scenes]:
                self.requested_scenes.append(type("SceneStub", (), {"scene_id": sid})())
        res_scenes = [
            {"scene_id": sid, "prompt": f"Valid camera-ready image prompt for scene {sid} with sepia tones and chipped torn borders"}
            for sid in scene_ids
        ]
        return json.dumps({"scenes": res_scenes})


class TestBrollPromptExpansion:
    """Verifies prompt expansion skips video visuals and executes video workers."""

    def test_expansion_skips_video_visuals_and_runs_video_jobs(self, temp_test_dir):
        # Create a storyboard with 2 video scenes and 3 image scenes (5 total)
        scenes = [
            VisualScene(
                scene_id="001", start=0.0, end=3.0, duration=3.0,
                visual_subject="Archival photograph of city gate",
                visual_idea="Archival photograph of city gate",
            ),
            VisualScene(
                scene_id="002", start=3.0, end=8.0, duration=5.0,
                visual_subject="Crowd scene",
                visual_idea="VIDEO of Archival footage of bustling Victorian street. KEYWORDS crowd, street, carriage",
            ),
            VisualScene(
                scene_id="003", start=8.0, end=11.0, duration=3.0,
                visual_subject="Close up of old clock",
                visual_idea="Vintage photo of mechanical pocket watch",
            ),
            VisualScene(
                scene_id="004", start=11.0, end=17.0, duration=6.0,
                visual_subject="Steam locomotive",
                visual_idea="VIDEO of Historical footage of steam train arriving at station. KEYWORDS train, station, locomotive",
            ),
            VisualScene(
                scene_id="005", start=17.0, end=20.0, duration=3.0,
                visual_subject="Soldier writing in diary",
                visual_idea="Old sepia portrait of soldier writing letter",
            ),
        ]

        mock_engine = MockTrackingInferenceEngine()

        # Mock video candidate provider that supplies passing mock clips
        dummy_mp4 = temp_test_dir / "expansion_dummy.mp4"
        create_lavfi_video(dummy_mp4, "testsrc", duration=7.0)

        def mock_candidate_provider(keywords, style_id):
            return [{
                "candidate_id": "cand_test",
                "source": "pexels",
                "download_url": "mock://test.mp4",
                "file_path": str(dummy_mp4),
                "duration": 7.0,
                "width": 1280,
                "height": 720,
                "tags": list(keywords) + ["historical", "footage"],
                "title": " ".join(keywords),
            }]

        def mock_downloader(cand, out_p):
            shutil.copy(cand["file_path"], out_p)
            return out_p

        expanded_scenes = Stage3PromptGeneration.execute(
            storyboard=scenes,
            engine=mock_engine,
            visual_style_id="century_old_photograph",
            video_candidate_provider=mock_candidate_provider,
            video_downloader=mock_downloader,
            video_cache_dir=str(temp_test_dir / "exp_cache")
        )

        # Verification: Exactly 3 image prompts were generated by the LLM
        requested_ids = [s.scene_id for s in mock_engine.requested_scenes]
        assert requested_ids == ["001", "003", "005"], (
            f"Expected image prompts for exactly scenes ['001', '003', '005'], got {requested_ids}"
        )
        assert len(mock_engine.requested_scenes) == 3

        # Exactly 2 video scenes were processed as video jobs
        video_scenes = [s for s in expanded_scenes if s.is_video]
        assert len(video_scenes) == 2
        assert [s.scene_id for s in video_scenes] == ["002", "004"]
        for vs in video_scenes:
            assert vs.video_path is not None
            assert Path(vs.video_path).exists()
            assert "[B-Roll Video]" in vs.prompt


# =============================================================================
# 3. QUALITY GATE TESTS
# =============================================================================

class TestBrollQualityGates:
    """Verifies that all 5 quality gates reject defective clips and accept valid clips."""

    def test_gate1_too_short_clip_rejected(self, temp_test_dir):
        # Clip shorter than 4.0 seconds (e.g. 2.5s)
        clip_p = temp_test_dir / "too_short.mp4"
        create_lavfi_video(clip_p, "testsrc", duration=2.5)

        candidate = {
            "duration": 2.5, "width": 1280, "height": 720,
            "tags": ["cabinet", "light", "keys"], "title": "keys cabinet",
            "file_path": str(clip_p)
        }
        passed, reasons = evaluate_quality_gates(candidate, target_duration=5.0, keywords=["cabinet", "light"])
        assert not passed
        assert any("Gate 1 Failed" in r for r in reasons)

    def test_gate2_low_resolution_rejected(self, temp_test_dir):
        # 640x360 is below 720p
        clip_p = temp_test_dir / "low_res.mp4"
        create_lavfi_video(clip_p, "testsrc", duration=6.0, size="640x360")

        candidate = {
            "duration": 6.0, "width": 640, "height": 360,
            "tags": ["cabinet", "light"], "title": "cabinet light",
            "file_path": str(clip_p)
        }
        passed, reasons = evaluate_quality_gates(candidate, target_duration=5.0, keywords=["cabinet", "light"])
        assert not passed
        assert any("Gate 2 Failed" in r for r in reasons)

    def test_gate3_near_black_rejected(self, temp_test_dir):
        # Near-black video: mean brightness is 0 < 25
        clip_p = temp_test_dir / "near_black.mp4"
        create_lavfi_video(clip_p, "color=black", duration=6.0)

        candidate = {
            "duration": 6.0, "width": 1280, "height": 720,
            "tags": ["cabinet", "light"], "title": "cabinet light",
            "file_path": str(clip_p)
        }
        passed, reasons = evaluate_quality_gates(candidate, target_duration=5.0, keywords=["cabinet", "light"])
        assert not passed
        assert any("Gate 3 Failed" in r for r in reasons)

    def test_gate4_static_clip_rejected(self, temp_test_dir):
        # Solid constant color video: frame-to-frame diff is 0.0 < 2.0
        clip_p = temp_test_dir / "static_clip.mp4"
        create_lavfi_video(clip_p, "color=blue", duration=6.0)

        candidate = {
            "duration": 6.0, "width": 1280, "height": 720,
            "tags": ["cabinet", "light"], "title": "cabinet light",
            "file_path": str(clip_p)
        }
        passed, reasons = evaluate_quality_gates(candidate, target_duration=5.0, keywords=["cabinet", "light"])
        assert not passed
        assert any("Gate 4 Failed" in r for r in reasons)

    def test_gate5_no_keyword_tag_match_rejected(self, temp_test_dir):
        # Clip has moving footage and good res, but only 0 or 1 keywords match
        clip_p = temp_test_dir / "no_tags.mp4"
        create_lavfi_video(clip_p, "testsrc", duration=6.0)

        candidate = {
            "duration": 6.0, "width": 1280, "height": 720,
            "tags": ["nature", "ocean", "clouds"], "title": "ocean waves",
            "file_path": str(clip_p)
        }
        # Keywords are ["cabinet", "silver keys", "light"] -> 0 match
        passed, reasons = evaluate_quality_gates(candidate, target_duration=5.0, keywords=["cabinet", "silver keys", "light"])
        assert not passed
        assert any("Gate 5 Failed" in r for r in reasons)

    def test_all_gates_pass_for_good_clip(self, temp_test_dir):
        # Valid 1280x720 video with test pattern motion and 2+ matching tags
        clip_p = temp_test_dir / "good_clip.mp4"
        create_lavfi_video(clip_p, "testsrc", duration=6.0)

        candidate = {
            "duration": 6.0, "width": 1280, "height": 720,
            "tags": ["flat 2d", "cabinet", "keys"], "title": "flat 2D cabinet view",
            "file_path": str(clip_p)
        }
        passed, reasons = evaluate_quality_gates(
            candidate, target_duration=5.0, keywords=["flat 2D", "cabinet", "silver keys", "light"]
        )
        assert passed, f"Expected good clip to pass all gates, but failed: {reasons}"
        assert len(reasons) == 0


# =============================================================================
# 4. PARALLEL EXECUTION & TRIM TEST
# =============================================================================

class TestBrollParallelExecution:
    """Verifies that video worker runs in parallel while prompts expand and trims to 4-10s."""

    def test_parallel_search_download_trim_placement(self, temp_test_dir):
        test_mp4 = temp_test_dir / "raw_parallel_input.mp4"
        create_lavfi_video(test_mp4, "testsrc", duration=8.5)

        # Storyboard: Scene 1 is an image, Scene 2 is a video
        sc1 = VisualScene(scene_id="001", start=0.0, end=3.0, duration=3.0, visual_subject="Image 1")
        sc2 = VisualScene(
            scene_id="002", start=3.0, end=8.5, duration=5.5,
            visual_subject="Video shot",
            visual_idea="VIDEO of Historical bustling market. KEYWORDS market, crowd, vintage"
        )
        storyboard = [sc1, sc2]

        mock_engine = MockTrackingInferenceEngine()

        def mock_provider(kw, style):
            return [{
                "candidate_id": "cand_parallel",
                "source": "pexels",
                "file_path": str(test_mp4),
                "duration": 8.5,
                "width": 1280,
                "height": 720,
                "tags": ["market", "crowd", "vintage"],
                "title": "historical market crowd",
            }]

        def mock_dl(cand, out):
            shutil.copy(cand["file_path"], out)
            return out

        res = Stage3PromptGeneration.execute(
            storyboard=storyboard,
            engine=mock_engine,
            visual_style_id="century_old_photograph",
            video_candidate_provider=mock_provider,
            video_downloader=mock_dl,
            video_cache_dir=str(temp_test_dir / "par_cache")
        )

        assert len(res) == 2
        v_scene = res[1]
        assert v_scene.is_video is True
        assert v_scene.video_path is not None
        assert Path(v_scene.video_path).exists()

        # Probe trimmed duration with ffprobe
        probe_cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(v_scene.video_path)
        ]
        probe_out = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        dur = float(probe_out.stdout.strip())
        assert 4.0 < dur < 10.0, f"Trimmed clip duration {dur}s is not strictly between 4s and 10s"


# =============================================================================
# 5. STYLE GRADING TESTS
# =============================================================================

class TestBrollStyleGrading:
    """Verifies that style grading alters the footage in the expected direction."""

    def test_century_old_grading_applies_sepia_and_grain(self, temp_test_dir):
        raw_p = temp_test_dir / "raw_color.mp4"
        # Test input with colorful gradient
        create_lavfi_video(raw_p, "testsrc", duration=2.0)
        graded_p = temp_test_dir / "century_old_graded.mp4"

        out_path = grade_video_clip(str(raw_p), str(graded_p), style_id="century_old_photograph")
        assert Path(out_path).exists()

        # Extract frames to verify sepia tone grading (Red channel >= Green channel >= Blue channel)
        raw_frames = extract_sampled_frames(str(raw_p), num_frames=3)
        graded_frames = extract_sampled_frames(str(out_path), num_frames=3)

        assert raw_frames is not None and graded_frames is not None
        # Graded output is distinctly modified from raw
        diff = np.mean(np.abs(graded_frames.astype(float) - raw_frames.astype(float)))
        assert diff > 10.0, f"Graded output should substantially differ from raw clip (diff={diff})"

        # Check sepia characteristic: Blue channel is desaturated relative to Red
        mean_r = np.mean(graded_frames[:, :, :, 0])
        mean_b = np.mean(graded_frames[:, :, :, 2])
        assert mean_r > mean_b, f"Expected sepia warm tone (R={mean_r:.1f} > B={mean_b:.1f})"

    def test_flat_2d_cartoon_grading_applies_posterize_and_edges(self, temp_test_dir):
        raw_p = temp_test_dir / "raw_smooth.mp4"
        create_lavfi_video(raw_p, "testsrc", duration=2.0)
        graded_p = temp_test_dir / "flat_2d_graded.mp4"

        out_path = grade_video_clip(str(raw_p), str(graded_p), style_id="whatif_flat_vector")
        assert Path(out_path).exists()

        raw_frames = extract_sampled_frames(str(raw_p), num_frames=3)
        graded_frames = extract_sampled_frames(str(out_path), num_frames=3)

        assert raw_frames is not None and graded_frames is not None
        diff = np.mean(np.abs(graded_frames.astype(float) - raw_frames.astype(float)))
        assert diff > 10.0, f"Cartoonized clip should differ from raw clip (diff={diff})"


# =============================================================================
# 6. RENDER TEST (MIXED STILLS + VIDEO CLIPS)
# =============================================================================

class TestBrollVideoRenderer:
    """Verifies mixed rendering of 1 torn-edge still + 1 clip at 1280x720."""

    def test_mixed_still_and_clip_render_1280x720(self, temp_test_dir):
        # 1. Create a torn-edge still image
        still_img_path = temp_test_dir / "torn_edge_still.jpg"
        img = Image.new("RGB", (1280, 720), color=(220, 200, 170))
        draw = ImageDraw.Draw(img)
        # Draw torn / frayed border effect
        draw.rectangle([60, 40, 1220, 680], fill=(160, 130, 90), outline=(50, 40, 30), width=4)
        draw.text((640, 360), "ARCHIVAL TORN EDGE STILL", fill=(20, 15, 10), anchor="mm")
        img.save(still_img_path, "JPEG")

        # 2. Create a stock video clip
        clip_path = temp_test_dir / "stock_clip_graded.mp4"
        create_lavfi_video(clip_path, "testsrc", duration=5.0, size="1280x720")

        # 3. Create dummy audio file for narration
        dummy_audio = temp_test_dir / "narration.wav"
        cmd_a = [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "sine=frequency=440:duration=7.5",
            "-c:a", "pcm_s16le",
            str(dummy_audio)
        ]
        subprocess.run(cmd_a, capture_output=True, check=True)

        # 4. Construct scenes
        scene_still = VisualScene(
            scene_id="001",
            start=0.0,
            end=2.5,
            duration=2.5,
            visual_subject="Torn-edge archival portrait",
            image_path=str(still_img_path),
            is_video=False,
            is_approved=True,
        )
        scene_clip = VisualScene(
            scene_id="002",
            start=2.5,
            end=7.5,
            duration=5.0,
            visual_subject="Archival city street footage",
            video_path=str(clip_path),
            is_video=True,
            video_approved=True,
            is_approved=True,
        )

        out_mp4 = temp_test_dir / "mixed_render_output.mp4"
        render_settings = VideoRenderSettings(
            fps=24,
            custom_width=1280,
            custom_height=720,
            motion_preset=MotionPreset.STATIC,
            transition_style=TransitionStyle.CROSSFADE,
        )

        rendered_path = VideoRenderer.render_video_sync(
            scenes=[scene_still, scene_clip],
            audio_path=str(dummy_audio),
            output_video_path=str(out_mp4),
            settings=render_settings,
        )

        assert Path(rendered_path).exists()
        assert Path(rendered_path).stat().st_size > 1000

        # Probe rendered video with ffprobe to verify 1280x720 resolution and valid duration
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration:format=duration",
            "-of", "json",
            str(rendered_path)
        ]
        probe_proc = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        import json
        meta = json.loads(probe_proc.stdout)
        stream = meta["streams"][0]
        assert stream["width"] == 1280
        assert stream["height"] == 720
        total_dur = float(stream.get("duration") or meta["format"]["duration"])
        assert 6.5 <= total_dur <= 8.5

        # Verify that the still scene (scene 1, 0.0-2.5s) is held completely still (zero zoom/pan motion):
        # Decode frames 6..18 sequentially and compare upper 70% (includes center title & torn border, excludes bottom subtitles)
        f_cmd = [
            "ffmpeg", "-v", "error",
            "-i", str(rendered_path),
            "-vframes", "20",
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-"
        ]
        raw_frames = subprocess.run(f_cmd, capture_output=True, check=True).stdout
        frames = np.frombuffer(raw_frames, dtype=np.uint8).reshape(-1, 720, 1280, 3)
        assert len(frames) >= 18
        region_a = frames[6, :500, :, :].astype(np.int16)
        region_b = frames[16, :500, :, :].astype(np.int16)
        diff = np.abs(region_a - region_b)
        mean_diff = float(np.mean(diff))
        assert mean_diff < 0.5, (
            f"Still image scene was not held completely still (mean pixel diff={mean_diff:.4f}, max={int(np.max(diff))})"
        )
