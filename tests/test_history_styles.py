"""
Acceptance Test Suite for History Niche Visual Styles in PromptBeast / Vidroa.
Covers:
  1. Registration test: app style list contains antique_engraving, authentic_archival_photography,
     and historical_maps; each appears in style picker and thumbnail matrix.
  2. Master prompt test: master prompt files exist in config/ai_prompts/, load correctly,
     name the style, contain never-do lists, and contain VIDEO of / KEYWORDS and stills-held-still rules.
  3. Prompt generation test: sample history storyboard (5 scenes) expands image prompts matching style rules
     (engraving mentions cross-hatching/ink and no color; archival mentions silver gelatin/sepia and no torn edges;
     map mentions parchment/cartography and period-accurate place or route).
  4. B-roll test: VIDEO of visual under each new style parses into shot description + keywords,
     grader returns the right filter (not generic fallback), and stock video routing queries the right API first.
  5. Render test: one timeline per new style (1 still + 1 clip) renders 1280x720 with clip full screen
     and still held still.
"""
import os
import sys
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest
import numpy as np
from PIL import Image, ImageDraw

from app.presets.loader import PresetManager
from app.models.presets import VisualStylePreset
from app.models.scene import VisualScene
from app.models.timeline import NarrationData, WordTimestamp
from app.models.video_config import VideoRenderSettings, MotionPreset, TransitionStyle
from app.core.video_parser import parse_video_visual, is_video_visual
from app.core.video_style_grader import (
    get_style_filter,
    ANTIQUE_ENGRAVING_FILTER,
    ARCHIVAL_PHOTOGRAPHY_FILTER,
    CENTURY_OLD_FILTER,
    HISTORICAL_MAPS_FILTER,
    GENERAL_CINEMATIC_FILTER,
    grade_video_clip,
)
from app.core.stock_video_service import StockVideoService, determine_stock_route
from app.core.video_renderer import VideoRenderer
from backend.pipeline.stage3_prompt_generation import Stage3PromptGeneration
from backend.inference.engine import BaseInferenceEngine


@pytest.fixture
def temp_test_dir():
    d = tempfile.mkdtemp(prefix="vidroa_history_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


def create_lavfi_video(path: Path, pattern: str = "testsrc", duration: float = 4.5, size: str = "1280x720", fps: int = 24):
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"{pattern}=duration={duration}:size={size}:rate={fps}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(path)
    ]
    subprocess.run(cmd, capture_output=True, check=True)


# =============================================================================
# 1. REGISTRATION TEST
# =============================================================================

class TestStyleRegistration:
    """Verifies that all 3 new styles are registered and visible in style pickers."""

    def test_styles_in_preset_manager(self):
        PresetManager.initialize()
        all_styles = PresetManager.get_all_styles()
        style_ids = [s.id for s in all_styles]

        assert "antique_engraving" in style_ids, "antique_engraving missing from PresetManager"
        assert "authentic_archival_photography" in style_ids, "authentic_archival_photography missing from PresetManager"
        assert "historical_maps" in style_ids, "historical_maps missing from PresetManager"

        engraving = PresetManager.get_style_by_id("antique_engraving")
        assert engraving is not None
        assert "Engraving" in engraving.name
        assert "Historical" in engraving.category

        archival = PresetManager.get_style_by_id("authentic_archival_photography")
        assert archival is not None
        assert "Archival" in archival.name

        maps = PresetManager.get_style_by_id("historical_maps")
        assert maps is not None
        assert "Maps" in maps.name

    def test_styles_in_ui_components(self):
        """Verifies styles appear in StyleThumbnailMatrix and MainWindow combo options."""
        from app.ui.widgets.style_thumbnail_matrix import ALLOWED_STYLE_ORDER, StyleThumbnailMatrix
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication(sys.argv)

        order_ids = [s[0] for s in ALLOWED_STYLE_ORDER]
        assert "antique_engraving" in order_ids
        assert "authentic_archival_photography" in order_ids
        assert "historical_maps" in order_ids

        matrix = StyleThumbnailMatrix()
        card_ids = [c.style_id for c in matrix._cards]
        assert "antique_engraving" in card_ids
        assert "authentic_archival_photography" in card_ids
        assert "historical_maps" in card_ids


# =============================================================================
# 2. MASTER PROMPT TEST
# =============================================================================

class TestMasterPrompts:
    """Verifies master prompt files in config/ai_prompts/ adhere to all required rules."""

    @pytest.mark.parametrize("filename,style_id,style_name", [
        ("06_antique_engraving_ai_prompt.txt", "antique_engraving", "Antique Engraving"),
        ("07_authentic_archival_photography_ai_prompt.txt", "authentic_archival_photography", "Authentic Archival Photography"),
        ("08_historical_maps_ai_prompt.txt", "historical_maps", "Historical Maps"),
    ])
    def test_master_prompt_content(self, filename, style_id, style_name):
        prompts_dir = ROOT_DIR / "config" / "ai_prompts"
        prompt_file = prompts_dir / filename
        assert prompt_file.exists(), f"Master prompt file {filename} does not exist"

        text = prompt_file.read_text(encoding="utf-8")
        assert len(text) > 500, f"Master prompt {filename} is too short"
        assert style_name.lower() in text.lower(), f"Style name {style_name} not mentioned in {filename}"

        # Must contain never-do list (explicit negative constraints)
        assert ("never" in text.lower() or "strictly forbidden" in text.lower()), f"Never-do list missing in {filename}"

        # Must contain B-roll rule (VIDEO of ... KEYWORDS ...)
        assert "video of" in text.lower(), f"VIDEO of rule missing in {filename}"
        assert "keywords" in text, f"KEYWORDS token missing in {filename}"

        # Must contain stills-held-still rule
        assert ("held still" in text.lower() or "held completely still" in text.lower()), f"Stills-held-still rule missing in {filename}"

    def test_master_index_lists_new_styles(self):
        index_file = ROOT_DIR / "config" / "ai_prompts" / "00_MASTER_INDEX_AND_GUIDE.md"
        assert index_file.exists()
        content = index_file.read_text(encoding="utf-8")

        assert "06_antique_engraving_ai_prompt.txt" in content
        assert "07_authentic_archival_photography_ai_prompt.txt" in content
        assert "08_historical_maps_ai_prompt.txt" in content


# =============================================================================
# 3. PROMPT GENERATION TEST (5-SCENE HISTORY STORYBOARD)
# =============================================================================

class MockHistoryInferenceEngine(BaseInferenceEngine):
    """Generates mock LLM expanded prompts conforming to the active style instructions."""

    def __init__(self, style_id: str):
        self.style_id = style_id

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        import re
        scene_ids = re.findall(r'"scene_id":\s*"([^"]+)"', prompt)
        res = []
        for sid in scene_ids:
            if self.style_id == "antique_engraving":
                p_text = f"Scene {sid}: 18th-century copperplate engraving with intricate black-ink cross-hatching, stippling, and etched linework on aged cream paper, depicting the iron foundry blast furnaces. Pure black ink only, no color, no sepia wash, no photographic shading, no torn edges."
            elif self.style_id == "authentic_archival_photography":
                p_text = f"Scene {sid}: Authentic period silver gelatin photograph in warm sepia tones, fine film grain, subtle dust spots, hairline scratches, and optical lens vignetting filling the full 16:9 widescreen frame. No torn paper edges, no borders, no illustrations."
            elif self.style_id == "historical_maps":
                p_text = f"Scene {sid}: Period cartography on aged yellowed parchment with hand-drawn coastlines, ornate compass rose, and historical frontiers showing Nova Carthago and the Rhône river expedition route. Authentic historical topography, no modern roads or satellite imagery."
            else:
                p_text = f"Scene {sid}: Historical depiction."
            res.append({"scene_id": sid, "prompt": p_text})
        return json.dumps({"scenes": res})


class TestHistoryPromptGeneration:
    """Verifies that sample history storyboards generate prompts matching their style directives."""

    def test_five_scene_history_storyboard_prompts(self):
        # 5 scenes covering the styles
        storyboard = [
            # Scene 1: Antique Engraving
            VisualScene(
                scene_id="001",
                start=0.0, end=4.0, duration=4.0,
                narration_words="By the late eighteenth century, the iron foundry transformed the quiet river valley.",
                visual_subject="Antique 18th-century copperplate engraving of ironworks",
                is_video=False,
            ),
            # Scene 2: Authentic Archival Photography
            VisualScene(
                scene_id="002",
                start=4.0, end=8.5, duration=4.5,
                narration_words="Spectators watched as the Wright brothers prepared their fragile biplane.",
                visual_subject="Authentic archival photograph of Wright Flyer filling full frame",
                is_video=False,
            ),
            # Scene 3: Historical Maps
            VisualScene(
                scene_id="003",
                start=8.5, end=13.0, duration=4.5,
                narration_words="Hannibal assembled an army of sixty thousand soldiers in Hispania.",
                visual_subject="Period cartography on aged parchment of Mediterranean and Iberia",
                is_video=False,
            ),
            # Scene 4: Mixed Engraving scene
            VisualScene(
                scene_id="004",
                start=13.0, end=17.0, duration=4.0,
                narration_words="In his private study, the engineer refined the steam engine gears.",
                visual_subject="Fine steel-engraved line art with delicate cross-hatched shadows",
                is_video=False,
            ),
            # Scene 5: Mixed Archival scene
            VisualScene(
                scene_id="005",
                start=17.0, end=21.0, duration=4.0,
                narration_words="Down in the boiler room, firemen shoveled coal into roaring furnaces.",
                visual_subject="Silver gelatin archival plate with hairline scratches filling the frame",
                is_video=False,
            ),
        ]

        # 1. Test Engraving generation rules
        engine_engraving = MockHistoryInferenceEngine(style_id="antique_engraving")
        expanded_engraving = Stage3PromptGeneration.execute(
            storyboard=storyboard[:1],
            engine=engine_engraving,
            visual_style_id="antique_engraving",
        )
        p_engraving = expanded_engraving[0].prompt.lower()

        assert "cross-hatching" in p_engraving or "ink" in p_engraving, "Engraving prompt must mention cross-hatching or ink"
        assert "no color" in p_engraving, "Engraving prompt must enforce no color"
        assert "no torn edges" in p_engraving, "Engraving prompt must enforce no torn edges"

        # 2. Test Archival Photo generation rules
        engine_archival = MockHistoryInferenceEngine(style_id="authentic_archival_photography")
        expanded_archival = Stage3PromptGeneration.execute(
            storyboard=storyboard[1:2],
            engine=engine_archival,
            visual_style_id="authentic_archival_photography",
        )
        p_archival = expanded_archival[0].prompt.lower()

        assert ("silver gelatin" in p_archival or "sepia" in p_archival), "Archival photo prompt must mention silver gelatin or sepia"
        assert "no torn" in p_archival, "Archival photo prompt must enforce no torn edges"

        # 3. Test Maps generation rules
        engine_maps = MockHistoryInferenceEngine(style_id="historical_maps")
        expanded_maps = Stage3PromptGeneration.execute(
            storyboard=storyboard[2:3],
            engine=engine_maps,
            visual_style_id="historical_maps",
        )
        p_maps = expanded_maps[0].prompt.lower()

        assert ("parchment" in p_maps or "cartography" in p_maps), "Map prompt must mention parchment or cartography"
        assert ("nova carthago" in p_maps or "route" in p_maps or "rhône" in p_maps), "Map prompt must include period-accurate geography"


# =============================================================================
# 4. B-ROLL TEST (PARSING, STYLE GRADING, AND STOCK VIDEO ROUTING)
# =============================================================================

class TestHistoryBroll:
    """Verifies B-roll parsing, style grading filter mapping, and stock routing for the 3 styles."""

    @pytest.mark.parametrize("visual_text,expected_desc,expected_keywords", [
        (
            "VIDEO of Historical harbor quayside with merchant ships docked along stone wharves. KEYWORDS historic quayside, tall ships, harbor, 19th century, stone wharf.",
            "Historical harbor quayside with merchant ships docked along stone wharves.",
            ["historic quayside", "tall ships", "harbor", "19th century", "stone wharf"]
        ),
        (
            "VIDEO of Dramatic alpine mountain pass with rugged snow-dusted ridges. KEYWORDS alpine mountains, snowy pass, rugged peaks, alps.",
            "Dramatic alpine mountain pass with rugged snow-dusted ridges.",
            ["alpine mountains", "snowy pass", "rugged peaks", "alps"]
        ),
        (
            "VIDEO of Archival seaside onlookers watching coastal aviation trials. KEYWORDS coastal dunes, vintage spectators, early flight, Kill Devil Hills.",
            "Archival seaside onlookers watching coastal aviation trials.",
            ["coastal dunes", "vintage spectators", "early flight", "Kill Devil Hills"]
        ),
    ])
    def test_broll_visual_parsing(self, visual_text, expected_desc, expected_keywords):
        parsed = parse_video_visual(visual_text)
        assert parsed["is_video"] is True
        assert expected_desc in parsed["shot_description"]
        for kw in expected_keywords:
            assert kw in parsed["keywords"]

    def test_style_grader_filters(self):
        """Verifies each new style returns its dedicated filter and NOT the generic fallback."""
        f_engraving = get_style_filter("antique_engraving")
        assert f_engraving == ANTIQUE_ENGRAVING_FILTER
        assert f_engraving != GENERAL_CINEMATIC_FILTER
        assert "format=gray" in f_engraving or "contrast" in f_engraving

        f_archival = get_style_filter("authentic_archival_photography")
        assert f_archival == ARCHIVAL_PHOTOGRAPHY_FILTER
        assert f_archival != GENERAL_CINEMATIC_FILTER
        assert "colorchannelmixer" in f_archival

        f_maps = get_style_filter("historical_maps")
        assert f_maps == HISTORICAL_MAPS_FILTER
        assert f_maps != GENERAL_CINEMATIC_FILTER
        assert f_maps != CENTURY_OLD_FILTER

    def test_stock_video_routing(self):
        """Verifies stock video API routing and prioritization rules."""
        # Archival photography: Pexels first (realistic)
        p1, vt1 = determine_stock_route("authentic_archival_photography", ["early flight", "biplane"])
        assert p1 == "pexels"
        assert vt1 == "all"

        # Engraving with real footage keywords: Pexels first
        p2, vt2 = determine_stock_route("antique_engraving", ["ironworks", "foundry", "furnace"])
        assert p2 == "pexels"
        assert vt2 == "all"

        # Engraving with animation keyword: Pixabay animation first
        p3, vt3 = determine_stock_route("antique_engraving", ["animated", "sketch", "line art"])
        assert p3 == "pixabay"
        assert vt3 == "animation"

        # Maps with real place keywords: Pexels first
        p4, vt4 = determine_stock_route("historical_maps", ["alpine mountains", "rhône river"])
        assert p4 == "pexels"
        assert vt4 == "all"

        # Maps with animation keyword: Pixabay animation first
        p5, vt5 = determine_stock_route("historical_maps", ["animated", "terrain map", "motion graphic"])
        assert p5 == "pixabay"
        assert vt5 == "animation"


# =============================================================================
# 5. RENDER TEST (1 TIMELINE PER NEW STYLE: 1 STILL + 1 CLIP AT 1280x720)
# =============================================================================

class TestHistoryRenderEngine:
    """Renders 1 timeline per new style (1 still + 1 clip) at 1280x720 with clip full screen and still held still."""

    @pytest.mark.parametrize("style_id,style_label", [
        ("antique_engraving", "Antique Engraving"),
        ("authentic_archival_photography", "Authentic Archival Photography"),
        ("historical_maps", "Historical Maps"),
    ])
    def test_render_timeline_per_style(self, temp_test_dir, style_id, style_label):
        # 1. Create a still image
        still_img_path = temp_test_dir / f"still_{style_id}.jpg"
        img = Image.new("RGB", (1280, 720), color=(240, 235, 220))
        draw = ImageDraw.Draw(img)
        draw.rectangle([50, 50, 1230, 670], outline=(40, 30, 20), width=3)
        draw.text((640, 360), f"{style_label.upper()} STILL", fill=(30, 20, 10), anchor="mm")
        img.save(still_img_path, "JPEG")

        # 2. Create raw clip and grade it according to style
        raw_clip = temp_test_dir / f"raw_clip_{style_id}.mp4"
        create_lavfi_video(raw_clip, "testsrc", duration=4.5, size="1280x720")

        graded_clip = temp_test_dir / f"graded_clip_{style_id}.mp4"
        grade_video_clip(str(raw_clip), str(graded_clip), style_id=style_id)
        assert graded_clip.exists()

        # 3. Create dummy narration audio
        dummy_audio = temp_test_dir / f"narration_{style_id}.wav"
        cmd_a = [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "sine=frequency=440:duration=7.0",
            "-c:a", "pcm_s16le",
            str(dummy_audio)
        ]
        subprocess.run(cmd_a, capture_output=True, check=True)

        # 4. Construct scenes (1 held-still still + 1 full-screen stock clip)
        scene_still = VisualScene(
            scene_id="001",
            start=0.0, end=2.5, duration=2.5,
            visual_subject=f"{style_label} still plate",
            image_path=str(still_img_path),
            is_video=False,
            is_approved=True,
        )
        scene_clip = VisualScene(
            scene_id="002",
            start=2.5, end=7.0, duration=4.5,
            visual_subject=f"{style_label} b-roll video footage",
            video_path=str(graded_clip),
            is_video=True,
            video_approved=True,
            is_approved=True,
        )

        out_mp4 = temp_test_dir / f"render_{style_id}.mp4"
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

        assert Path(rendered_path).exists(), f"Rendered output missing for {style_id}"
        assert Path(rendered_path).stat().st_size > 1000

        # Probe output video to confirm 1280x720 and valid duration
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration:format=duration",
            "-of", "json",
            str(rendered_path)
        ]
        probe_res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        probe_data = json.loads(probe_res.stdout)
        stream_info = probe_data.get("streams", [{}])[0]

        assert stream_info.get("width") == 1280
        assert stream_info.get("height") == 720
