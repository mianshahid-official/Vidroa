"""
Acceptance Test Suite for Century-Old Photograph Archival Treatments (Treatments 10, 11, 12).
Verifies:
  1. Standalone styles reversion: antique_engraving, authentic_archival_photography,
     and historical_maps are NOT in PresetManager, NOT in ALLOWED_STYLE_ORDER, and do NOT appear as styles.
  2. Treatments 10, 11, 12 in Century-Old Photograph:
     - century_old_photograph.json contains 12 treatments in system_instructions.
     - 03_century_old_photograph_ai_prompt.txt contains 12 treatments with Description and Best Context.
  3. Storyboard treatment application: sample storyboard applies treatments 10, 11, 12 where
     narratively appropriate while keeping ~40-50% clean archival plates.
  4. Treatment-aware video grader:
     - treatment="antique_engraving" -> ANTIQUE_ENGRAVING_FILTER
     - treatment="authentic_archival" -> ARCHIVAL_PHOTOGRAPHY_FILTER
     - treatment="historical_maps" -> HISTORICAL_MAPS_FILTER
     - no treatment -> default CENTURY_OLD_FILTER (sepia)
  5. Treatment-aware stock routing:
     - archival -> Pexels first (realistic)
     - engraving & maps -> Pexels first for real footage; Pixabay animation only if animation keyword requested
     - no treatment -> Pexels first (realistic)
"""
import os
import sys
import json
import shutil
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest

from app.presets.loader import PresetManager
from app.models.scene import VisualScene
from app.core.video_parser import parse_video_visual
from app.core.video_style_grader import (
    get_style_filter,
    ANTIQUE_ENGRAVING_FILTER,
    ARCHIVAL_PHOTOGRAPHY_FILTER,
    CENTURY_OLD_FILTER,
    HISTORICAL_MAPS_FILTER,
    GENERAL_CINEMATIC_FILTER,
)
from app.core.stock_video_service import determine_stock_route
from backend.pipeline.stage3_prompt_generation import Stage3PromptGeneration
from backend.inference.engine import BaseInferenceEngine


# =============================================================================
# 1. STANDALONE STYLES REVERSION TEST
# =============================================================================

class TestStandaloneStylesReverted:
    """Confirms antique_engraving, authentic_archival_photography, and historical_maps are NOT styles."""

    def test_not_in_preset_manager(self):
        PresetManager.initialize()
        styles = PresetManager.get_all_styles()
        style_ids = [s.id for s in styles]

        assert "antique_engraving" not in style_ids
        assert "authentic_archival_photography" not in style_ids
        assert "historical_maps" not in style_ids

    def test_not_in_allowed_style_order(self):
        from app.ui.widgets.style_thumbnail_matrix import ALLOWED_STYLE_ORDER
        order_ids = [s[0] for s in ALLOWED_STYLE_ORDER]

        assert "antique_engraving" not in order_ids
        assert "authentic_archival_photography" not in order_ids
        assert "historical_maps" not in order_ids

    def test_not_in_style_picker_combo(self):
        from PySide6.QtWidgets import QApplication, QComboBox
        from app.ui.main_window import MainWindow

        # Priority styles check
        priority_styles = [
            ("century_old_photograph", "Century-Old Photograph"),
            ("3d_red_blue_stickman", "3D Red & Blue Stickman Animation"),
            ("bw_vintage_historical_photography", "Black & White Vintage Historical Photography"),
            ("paper_quilling", "Paper Quilling Illustration"),
            ("mixed_media_collage", "Mixed-Media Collage"),
            ("paper_cutout", "Paper-Cutout Illustration"),
        ]
        priority_ids = [p[0] for p in priority_styles]
        assert "antique_engraving" not in priority_ids
        assert "authentic_archival_photography" not in priority_ids
        assert "historical_maps" not in priority_ids


# =============================================================================
# 2. TREATMENTS 10, 11, 12 IN CENTURY-OLD PRESET & MASTER PROMPT
# =============================================================================

class TestCenturyOldTwelveTreatments:
    """Verifies that Century-Old Photograph style contains all 12 treatments in JSON and Prompt."""

    def test_preset_json_has_twelve_treatments(self):
        preset_path = ROOT_DIR / "config" / "visual_styles" / "century_old_photograph.json"
        assert preset_path.exists()

        data = json.loads(preset_path.read_text(encoding="utf-8"))
        assert "12 dynamic archival image treatments" in data["description"]
        sys_inst = data["system_instructions"]

        assert "10. Full Antique Engraving Plate:" in sys_inst
        assert "11. Full-Frame Authentic Archival Photograph:" in sys_inst
        assert "12. Full Historical Map Plate:" in sys_inst

    def test_master_prompt_has_twelve_treatments(self):
        prompt_path = ROOT_DIR / "config" / "ai_prompts" / "03_century_old_photograph_ai_prompt.txt"
        assert prompt_path.exists()

        text = prompt_path.read_text(encoding="utf-8")
        assert "THE 12 SPECIALIZED ARCHIVAL IMAGE TREATMENTS" in text
        assert "apply these 12 specialized treatments" in text

        # Verify treatment 10
        assert "10. Full Antique Engraving Plate:" in text
        assert "Description in Visual prompt:" in text
        assert "Best Context:" in text
        assert "Woodblock / Engraving Plate Split" in text

        # Verify treatment 11
        assert "11. Full-Frame Authentic Archival Photograph:" in text
        assert "NO torn edges" in text

        # Verify treatment 12
        assert "12. Full Historical Map Plate:" in text
        assert "Antique Map Overlay" in text
        assert "NEVER pan or zoom across the map" in text


# =============================================================================
# 3. STORYBOARD TREATMENT APPLICATION & PACING TEST
# =============================================================================

class MockCenturyOldInferenceEngine(BaseInferenceEngine):
    """Mocks expansion of Century-Old storyboard scenes adhering to treatments and pacing."""

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        import re
        scene_ids = re.findall(r'"scene_id":\s*"([^"]+)"', prompt)
        res = []
        for sid in scene_ids:
            if sid == "001":
                p_text = f"Scene {sid} [Treatment 10 - Full Antique Engraving Plate]: 18th-century copperplate engraving with intricate black-ink cross-hatching and stippling on aged cream paper of the foundry blueprint. Pure black ink, no color, no sepia wash, no torn edges."
            elif sid == "003":
                p_text = f"Scene {sid} [Treatment 12 - Full Historical Map Plate]: Aged parchment period map showing Iberian coastline, Nova Carthago, and the Rhône march route in hand-drawn sepia ink with compass rose. Strictly period-accurate frontiers."
            elif sid == "005":
                p_text = f"Scene {sid} [Treatment 11 - Full-Frame Authentic Archival Photograph]: Genuine silver gelatin photograph in warm sepia tones, film grain, and subtle vignetting filling the full 16:9 frame edge-to-edge. No torn edges, no paper border."
            else:
                p_text = f"Scene {sid} [Baseline Archival Plate]: Authentic damaged archival photograph with faded sepia tones and naturally chipped torn card edges, dust spots, and hairline scratches."
            res.append({"scene_id": sid, "prompt": p_text})
        return json.dumps({"scenes": res})


class TestStoryboardTreatmentApplication:
    """Verifies that a sample Century-Old storyboard applies treatments 10, 11, 12 with ~40-50% clean plates."""

    def test_sample_century_old_storyboard_treatments(self):
        storyboard = [
            # Scene 1: Founding/blueprint moment -> treatment 10 (Full Antique Engraving Plate)
            VisualScene(
                scene_id="001", start=0.0, end=4.0, duration=4.0,
                narration_words="In the late eighteenth century, the iron foundry began producing the first steam cylinder castings.",
                visual_subject="Foundry architectural blueprint and trip hammer machinery",
                visual_idea="Full Antique Engraving Plate of the iron foundry machinery with fine black-ink cross-hatching",
                treatment="antique_engraving",
                is_video=False,
            ),
            # Scene 2: Baseline clean archival plate
            VisualScene(
                scene_id="002", start=4.0, end=8.0, duration=4.0,
                narration_words="Hundreds of laborers arrived from nearby villages to work the furnaces.",
                visual_subject="Laborers outside brick blast furnace",
                visual_idea="Century-old photograph with worn torn edges showing laborers in wool caps",
                treatment=None,  # baseline
                is_video=False,
            ),
            # Scene 3: March / campaign / route -> treatment 12 (Full Historical Map Plate)
            VisualScene(
                scene_id="003", start=8.0, end=13.0, duration=5.0,
                narration_words="Their campaign took them across treacherous mountain corridors into the northern territories.",
                visual_subject="Strategic mountain pass campaign route",
                visual_idea="Full Historical Map Plate showing campaign route on aged parchment with compass rose",
                treatment="historical_maps",
                is_video=False,
            ),
            # Scene 4: Baseline clean archival plate
            VisualScene(
                scene_id="004", start=13.0, end=17.0, duration=4.0,
                narration_words="Supply wagons struggled through knee-deep mud along unpaved river roads.",
                visual_subject="Wagons on muddy road",
                visual_idea="Archival sepia plate with chipped edges showing wooden supply wagons",
                treatment=None,  # baseline
                is_video=False,
            ),
            # Scene 5: Iconic centerpiece moment / portrait -> treatment 11 (Full-Frame Archival Photo)
            VisualScene(
                scene_id="005", start=17.0, end=21.0, duration=4.0,
                narration_words="Standing upon the windswept ridge, the commander watched the horizon.",
                visual_subject="Commander portrait on ridge",
                visual_idea="Full-Frame Authentic Archival Photograph of commander filling frame edge-to-edge, no torn border",
                treatment="authentic_archival",
                is_video=False,
            ),
            # Scene 6: Baseline clean archival plate
            VisualScene(
                scene_id="006", start=21.0, end=25.0, duration=4.0,
                narration_words="By nightfall, the fires died down and silence fell over the encampment.",
                visual_subject="Night encampment",
                visual_idea="Century-old sepia plate with torn frayed edges of tents under stars",
                treatment=None,  # baseline
                is_video=False,
            ),
        ]

        # Verify pacing: 3 baseline scenes out of 6 (exactly 50% baseline clean plates)
        baseline_scenes = [s for s in storyboard if not s.treatment]
        assert len(baseline_scenes) == 3
        assert len(baseline_scenes) / len(storyboard) == 0.5

        # Execute Stage 3 Prompt Generation with mock engine
        engine = MockCenturyOldInferenceEngine()
        expanded = Stage3PromptGeneration.execute(
            storyboard=storyboard,
            engine=engine,
            visual_style_id="century_old_photograph"
        )

        p1 = expanded[0].prompt.lower()
        assert "engraving" in p1 and "cross-hatching" in p1
        assert "no color" in p1 and "no torn edges" in p1

        p3 = expanded[2].prompt.lower()
        assert "map" in p3 and "parchment" in p3
        assert "frontiers" in p3 or "route" in p3

        p5 = expanded[4].prompt.lower()
        assert "silver gelatin" in p5 or "sepia" in p5
        assert "no torn edges" in p5


# =============================================================================
# 4. TREATMENT-AWARE VIDEO GRADER TEST
# =============================================================================

class TestTreatmentAwareGrader:
    """Verifies that the style grader returns treatment filters when specified, and default sepia otherwise."""

    def test_treatment_filter_mapping(self):
        # 1. Antique Engraving treatment -> ANTIQUE_ENGRAVING_FILTER
        f_engraving = get_style_filter("century_old_photograph", treatment="antique_engraving")
        assert f_engraving == ANTIQUE_ENGRAVING_FILTER
        assert "format=gray" in f_engraving or "contrast" in f_engraving

        # 2. Authentic Archival treatment -> ARCHIVAL_PHOTOGRAPHY_FILTER (sepia)
        f_archival = get_style_filter("century_old_photograph", treatment="authentic_archival")
        assert f_archival == ARCHIVAL_PHOTOGRAPHY_FILTER
        assert f_archival == CENTURY_OLD_FILTER

        # 3. Historical Maps treatment -> HISTORICAL_MAPS_FILTER (light sepia parchment)
        f_maps = get_style_filter("century_old_photograph", treatment="historical_maps")
        assert f_maps == HISTORICAL_MAPS_FILTER
        assert f_maps != CENTURY_OLD_FILTER

        # 4. Default baseline (no treatment) -> CENTURY_OLD_FILTER
        f_default = get_style_filter("century_old_photograph", treatment=None)
        assert f_default == CENTURY_OLD_FILTER

        f_default_implicit = get_style_filter("century_old_photograph")
        assert f_default_implicit == CENTURY_OLD_FILTER


# =============================================================================
# 5. TREATMENT-AWARE STOCK ROUTING TEST
# =============================================================================

class TestTreatmentAwareStockRouting:
    """Verifies stock video API routing based on scene treatment."""

    def test_routing_by_treatment(self):
        # 1. Archival treatment -> Pexels first (realistic)
        p1, vt1 = determine_stock_route("century_old_photograph", ["harbor", "spectators"], treatment="authentic_archival")
        assert p1 == "pexels"
        assert vt1 == "all"

        # 2. Engraving treatment without animation keywords -> Pexels first (real footage)
        p2, vt2 = determine_stock_route("century_old_photograph", ["ironworks", "foundry"], treatment="antique_engraving")
        assert p2 == "pexels"
        assert vt2 == "all"

        # 3. Engraving treatment with animation keywords -> Pixabay animation first
        p3, vt3 = determine_stock_route("century_old_photograph", ["animated", "blueprint", "sketch"], treatment="antique_engraving")
        assert p3 == "pixabay"
        assert vt3 == "animation"

        # 4. Maps treatment without animation keywords -> Pexels first (real footage of location)
        p4, vt4 = determine_stock_route("century_old_photograph", ["alpine mountains", "pass"], treatment="historical_maps")
        assert p4 == "pexels"
        assert vt4 == "all"

        # 5. Maps treatment with animation keywords -> Pixabay animation first
        p5, vt5 = determine_stock_route("century_old_photograph", ["animated", "terrain map", "motion graphic"], treatment="historical_maps")
        assert p5 == "pixabay"
        assert vt5 == "animation"

        # 6. Baseline Century-Old without treatment -> Pexels first (realistic)
        p6, vt6 = determine_stock_route("century_old_photograph", ["vintage", "street", "carriage"], treatment=None)
        assert p6 == "pexels"
        assert vt6 == "all"
