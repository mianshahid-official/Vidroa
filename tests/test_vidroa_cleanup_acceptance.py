"""
Acceptance tests for Vidroa cleanup:
1. Subtitles checkbox + two-way sync with SubtitleEditor + settings persistence across restart.
2. Two-file render ({project}_nosubtitles.mp4 and {project}_subtitles.mp4 + final_video.mp4).
3. ProjectManager save/load preserves image_path, video bindings, treatment, and render_subtitles.
4. Desktop UI workflow preserves treatments 10/11/12 through VideoWorker -> grader & stock routing.
5. PresetManager & StyleThumbnailMatrix do not silently fall back to zombie_survival for unknown IDs.
6. VIDEO 4-10s duration rule is enforced loudly without clamping or looping.
"""
import json
import subprocess
import tempfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import pytest

from PySide6.QtWidgets import QApplication

from app.models.project import StoryProject, ProjectConfig, ProjectState
from app.models.scene import VisualScene
from app.models.timeline import NarrationData, WordTimestamp
from app.models.video_config import SubtitlePreset, VideoRenderSettings, MotionPreset, TransitionStyle
from app.core.project_manager import ProjectManager
from app.core.video_renderer import VideoRenderer, VideoRenderWorker
from app.core.video_worker import VideoWorker
from app.core.narration_workflow import align_visuals_with_timestamps
from app.core.video_style_grader import (
    ANTIQUE_ENGRAVING_FILTER,
    ARCHIVAL_PHOTOGRAPHY_FILTER,
    HISTORICAL_MAPS_FILTER,
    get_style_filter,
)
from app.presets.loader import PresetManager
from app.ui.widgets.render_panel import RenderPanel
from app.ui.widgets.style_thumbnail_matrix import StyleThumbnailMatrix


def _make_wav(path: Path, duration: float = 2.0):
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}", "-c:a", "pcm_s16le", str(path)],
        capture_output=True,
        check=True,
    )


def _make_jpg(path: Path, color=(30, 60, 120)):
    img = Image.new("RGB", (640, 360), color=color)
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 40, 600, 320], outline=(200, 200, 200), width=4)
    img.save(path, "JPEG")


def _grab_mid_frame(video_path: Path, ts: float = 1.0) -> np.ndarray:
    cmd = [
        "ffmpeg", "-v", "error",
        "-ss", f"{ts:.2f}",
        "-i", str(video_path),
        "-frames:v", "1",
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "-"
    ]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.uint8)


class TestSubtitlesCheckboxAndTwoFileRender:
    def test_checkbox_sync_and_persistence(self, tmp_path):
        app = QApplication.instance() or QApplication([])
        panel = RenderPanel()
        assert panel.chk_subtitles.isChecked() is True
        assert panel.sub_editor.config.preset == SubtitlePreset.HORMOZI_KARAOKE

        # Unchecking checkbox sets editor to NONE
        panel.chk_subtitles.setChecked(False)
        assert panel.sub_editor.config.preset == SubtitlePreset.NONE

        # Selecting a style preset in editor re-checks box
        panel.sub_editor.select_preset(SubtitlePreset.CINEMATIC_GOLD)
        assert panel.chk_subtitles.isChecked() is True
        assert panel.sub_editor.config.preset == SubtitlePreset.CINEMATIC_GOLD

        # Persist False state through ProjectManager save + load
        proj_dir = tmp_path / "proj_persist"
        proj = StoryProject(
            name="PersistTest",
            project_dir=str(proj_dir),
            config=ProjectConfig(render_subtitles=False),
        )
        ProjectManager.save_project(proj)
        reloaded = ProjectManager.load_project(str(proj_dir))
        assert reloaded.config.render_subtitles is False

        # Simulated app restart: fresh RenderPanel loads project and restores unchecked checkbox
        from PySide6.QtWidgets import QMainWindow
        win2 = QMainWindow()
        win2.project = reloaded
        panel2 = RenderPanel(win2)
        win2.setCentralWidget(panel2)
        panel2.load_project_data([])
        assert panel2.chk_subtitles.isChecked() is False
        assert panel2.sub_editor.config.preset == SubtitlePreset.NONE
        win2.close()

    def test_two_file_render_subtitles_on_and_off(self, tmp_path):
        img_p = tmp_path / "still_001.jpg"
        audio_p = tmp_path / "voice.wav"
        _make_jpg(img_p, color=(15, 25, 45))
        _make_wav(audio_p, duration=2.5)

        narration = NarrationData(
            duration_seconds=2.5,
            words=[
                WordTimestamp(word="HELLO", start=0.2, end=0.9),
                WordTimestamp(word="WORLD", start=0.9, end=1.6),
                WordTimestamp(word="TODAY", start=1.6, end=2.3),
            ],
        )
        sc = VisualScene(
            scene_id="001",
            start=0.0,
            end=2.5,
            duration=2.5,
            narration_excerpt="HELLO WORLD TODAY",
            visual_subject="Dark studio",
            image_path=str(img_p),
            is_approved=True,
        )

        renders_dir = tmp_path / "renders"
        clean_p = renders_dir / "Demo_nosubtitles.mp4"
        subbed_p = renders_dir / "Demo_subtitles.mp4"

        settings = VideoRenderSettings(
            fps=24,
            custom_width=640,
            custom_height=360,
            motion_preset=MotionPreset.STATIC,
            transition_style=TransitionStyle.CUT,
        )

        # 1. Subtitles ON: produces clean + subbed, distinct byte sizes and frames
        chosen_on = VideoRenderer.render_dual_video_sync(
            scenes=[sc],
            audio_path=str(audio_p),
            clean_video_path=str(clean_p),
            subbed_video_path=str(subbed_p),
            burn_subtitles=True,
            settings=settings,
            narration=narration,
        )
        assert Path(chosen_on).resolve() == subbed_p.resolve()
        assert clean_p.exists() and subbed_p.exists()
        assert clean_p.stat().st_size != subbed_p.stat().st_size

        frame_clean = _grab_mid_frame(clean_p, ts=1.0)
        frame_subbed = _grab_mid_frame(subbed_p, ts=1.0)
        assert frame_clean.shape == frame_subbed.shape
        assert not np.array_equal(frame_clean, frame_subbed), "Subtitled render frames should differ from clean video"

        # 2. Subtitles OFF: skips subbed file, outputs clean file
        subbed_off_p = renders_dir / "DemoOff_subtitles.mp4"
        clean_off_p = renders_dir / "DemoOff_nosubtitles.mp4"
        chosen_off = VideoRenderer.render_dual_video_sync(
            scenes=[sc],
            audio_path=str(audio_p),
            clean_video_path=str(clean_off_p),
            subbed_video_path=str(subbed_off_p),
            burn_subtitles=False,
            settings=settings,
            narration=narration,
        )
        assert Path(chosen_off).resolve() == clean_off_p.resolve()
        assert clean_off_p.exists()
        assert not subbed_off_p.exists()

        # 3. Verify RenderPanel._on_worker_finished copies matching output to final_video.mp4 and sets preview path
        panel = RenderPanel()
        panel._on_worker_finished(str(subbed_p))
        final_p = renders_dir / "final_video.mp4"
        assert Path(panel._output_video_path).resolve() == subbed_p.resolve()
        assert final_p.exists() and final_p.stat().st_size == subbed_p.stat().st_size

        panel._on_worker_finished(str(clean_off_p))
        assert Path(panel._output_video_path).resolve() == clean_off_p.resolve()
        assert final_p.stat().st_size == clean_off_p.stat().st_size


class TestProjectPersistenceAndDesktopTreatments:
    def test_project_save_load_preserves_bindings_and_metadata(self, tmp_path):
        proj_dir = tmp_path / "proj_bindings"
        sc1 = VisualScene(
            scene_id="001",
            start=0.0,
            end=3.0,
            duration=3.0,
            narration_excerpt="First line.",
            visual_subject="Ship",
            visual_idea="Engraved ship",
            visual_description="19th century ship plate",
            image_path=str(tmp_path / "001.png"),
            treatment="antique_engraving",
            generation_status="generated",
            prompt="Detailed engraved tall ship.",
        )
        sc2 = VisualScene(
            scene_id="002",
            start=3.0,
            end=8.0,
            duration=5.0,
            narration_excerpt="Second line.",
            visual_subject="Marching soldiers",
            is_video=True,
            video_path=str(tmp_path / "002_graded.mp4"),
            video_keywords=["archival footage", "soldiers", "march"],
            video_shot_description="Vintage footage of marching column",
            treatment="authentic_archival",
            generation_status="video_ready",
        )
        proj = StoryProject(
            name="BindTest",
            project_dir=str(proj_dir),
            config=ProjectConfig(visual_style_id="century_old_photograph", render_subtitles=False),
            state=ProjectState(
                images_folder_path=str(tmp_path / "imgs"),
                thumbnail_headline="FORGOTTEN VOYAGE",
                thumbnail_prompt="Epic ship engraving thumbnail",
                style_preset_id="century_old_photograph",
                extracted_bibles={"characters": [{"name": "Captain"}]},
                user_visual_ideas_raw="Visual 1 Words: ...",
                scenes=[sc1, sc2],
            ),
        )
        ProjectManager.save_project(proj)
        loaded = ProjectManager.load_project(str(proj_dir))

        assert loaded.state.images_folder_path == str(tmp_path / "imgs")
        assert loaded.state.thumbnail_headline == "FORGOTTEN VOYAGE"
        assert loaded.state.thumbnail_prompt == "Epic ship engraving thumbnail"
        assert loaded.state.style_preset_id == "century_old_photograph"
        assert loaded.state.extracted_bibles == {"characters": [{"name": "Captain"}]}
        assert loaded.state.user_visual_ideas_raw == "Visual 1 Words: ..."
        assert len(loaded.state.scenes) == 2

        l1, l2 = loaded.state.scenes
        assert l1.image_path == str(tmp_path / "001.png")
        assert l1.treatment == "antique_engraving"
        assert l1.visual_description == "19th century ship plate"
        assert l1.generation_status == "generated"
        assert l2.is_video is True
        assert l2.video_path == str(tmp_path / "002_graded.mp4")
        assert l2.video_keywords == ["archival footage", "soldiers", "march"]
        assert l2.video_shot_description == "Vintage footage of marching column"
        assert l2.treatment == "authentic_archival"
        assert l2.generation_status == "video_ready"

    def test_desktop_flow_preserves_treatments_10_11_12(self, tmp_path):
        narration = NarrationData(
            duration_seconds=15.0,
            words=[
                WordTimestamp(word="One", start=0.0, end=2.0),
                WordTimestamp(word="two", start=2.0, end=5.0),
                WordTimestamp(word="three", start=5.0, end=7.0),
                WordTimestamp(word="four", start=7.0, end=10.0),
                WordTimestamp(word="five", start=10.0, end=12.0),
                WordTimestamp(word="six", start=12.0, end=15.0),
            ],
        )
        visual_items = [
            {"id": "1", "words": "One two", "visual_idea": "VIDEO of Antique copperplate engraving machinery in motion. KEYWORDS antique engraving, copperplate, foundry"},
            {"id": "2", "words": "three four", "visual_idea": "VIDEO of Full-frame archival silver gelatin street footage. KEYWORDS authentic archival photography, street, crowd"},
            {"id": "3", "words": "five six", "visual_idea": "VIDEO of Aged parchment historical map route animation. KEYWORDS historical map, compass rose, route"},
        ]
        scenes = align_visuals_with_timestamps(visual_items, narration)
        assert scenes[0].treatment == "antique_engraving"
        assert scenes[1].treatment == "authentic_archival"
        assert scenes[2].treatment == "historical_maps"

        # Verify grader filter matches treatment properly
        assert get_style_filter("century_old_photograph", scenes[0].treatment) == ANTIQUE_ENGRAVING_FILTER
        assert get_style_filter("century_old_photograph", scenes[1].treatment) == ARCHIVAL_PHOTOGRAPHY_FILTER
        assert get_style_filter("century_old_photograph", scenes[2].treatment) == HISTORICAL_MAPS_FILTER

    def test_no_silent_fallback_and_broll_duration_reported(self, tmp_path):
        PresetManager.initialize()
        assert PresetManager.get_style_by_id("unknown_nonexistent_style_xyz") is None

        app = QApplication.instance() or QApplication([])
        matrix = StyleThumbnailMatrix()
        matrix.select_style("century_old_photograph")
        assert matrix.current_style_id() == "century_old_photograph"
        # Unknown style should not silently switch to zombie_survival
        matrix.select_style("totally_unknown_style_123")
        assert matrix.current_style_id() == "century_old_photograph"

        # VideoWorker rejects out-of-range duration (e.g. 12.0s) instead of clamping
        out_of_range_sc = VisualScene(
            scene_id="001",
            start=0.0,
            end=12.0,
            duration=12.0,
            visual_subject="Harbor crowd",
            is_video=True,
            video_keywords=["harbor", "crowd"],
        )
        res = VideoWorker.process_scene(out_of_range_sc, cache_dir=str(tmp_path / "cache"))
        assert res["success"] is False
        assert res["fallback_needed"] is True
        assert "VIDEO DURATION INVALID" in res.get("error", "")
