"""
Tests for the Zombie Survival visual style.
Verifies:
- config/visual_styles/zombie_survival.json loads and adheres to the master visual guide.
- Preview images exist in both .png and .jpg formats.
- System instructions strictly conform to the locked character and zombie specifications.
- Zero forbidden fixed-example tokens appear in the style file.
- PresetManager and alias resolution work correctly.
- Thumbnail prompt builder generates specialized zombie survival thumbnail prompt with headline.
- Stage 5 prompt generator incorporates hero lock and uniform zombie lock without converting to historical attire.
"""
import json
import re
from pathlib import Path
import pytest
from app.presets.loader import PresetManager
from app.core.thumbnail_prompt_builder import build_viral_thumbnail_prompt

FORBIDDEN_TERMS_RE = re.compile(
    r"\b(lighthouse|keeper|finch|blackwood|fresnel|lamp sweep|"
    r"1453|mehmed|ottoman|byzantine|constantinople|caesar|cortes|dorothea|theodosian)\b",
    re.IGNORECASE,
)

STYLE_PATH = Path("config/visual_styles/zombie_survival.json")
PREVIEW_PNG = Path("assets/style_previews/zombie_survival.png")
PREVIEW_JPG = Path("assets/style_previews/zombie_survival.jpg")


def test_zombie_survival_style_file_and_schema():
    assert STYLE_PATH.exists(), f"Missing visual style file: {STYLE_PATH}"
    with open(STYLE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("id") == "zombie_survival"
    assert data.get("name") == "Zombie Survival"
    assert data.get("category") == "2D Animation"
    assert isinstance(data.get("description"), str) and len(data["description"]) > 10
    assert isinstance(data.get("system_instructions"), str) and len(data["system_instructions"]) > 100
    assert data.get("is_custom") is False


def test_zombie_survival_preview_images_exist():
    assert PREVIEW_PNG.exists(), f"Missing PNG preview: {PREVIEW_PNG}"
    assert PREVIEW_JPG.exists(), f"Missing JPG preview: {PREVIEW_JPG}"
    assert PREVIEW_PNG.stat().st_size > 0
    assert PREVIEW_JPG.stat().st_size > 0


def test_zombie_survival_no_forbidden_terms():
    with open(STYLE_PATH, "r", encoding="utf-8") as f:
        raw_text = f.read()

    matches = FORBIDDEN_TERMS_RE.findall(raw_text)
    assert not matches, f"Forbidden fixed-example terms found in {STYLE_PATH}: {matches}"


def test_zombie_survival_style_lock_elements():
    with open(STYLE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    instructions = data["system_instructions"]
    inst_lower = instructions.lower()

    # Hero character locks
    assert "off-white head" in inst_lower or "#f5f5f0" in inst_lower
    assert "dot eyes" in inst_lower
    assert "straight-line mouth" in inst_lower
    assert "backwards flat-red baseball cap" in inst_lower or "#d63a2a" in inst_lower
    assert "charcoal-grey zip-up hoodie" in inst_lower or "#333333" in inst_lower
    assert "pure-white t-shirt" in inst_lower or "#ffffff" in inst_lower
    assert "messenger bag strap" in inst_lower or "#4a2e1b" in inst_lower
    assert "stick arms" in inst_lower and "stick legs" in inst_lower

    # Zombie horde locks
    assert "pale olive-green" in inst_lower or "#8a9a66" in inst_lower
    assert "circular white eyes" in inst_lower
    assert "dot pupils" in inst_lower
    assert "jagged white teeth" in inst_lower or "sharp" in inst_lower
    assert "tattered dark-brown jackets" in inst_lower or "#5c4033" in inst_lower
    assert "shredded" in inst_lower

    # Zero 3D / Zero gore restrictions
    assert "zero 3d" in inst_lower
    assert "zero volumetric" in inst_lower
    assert "gradients" in inst_lower
    assert "zero photorealism" in inst_lower
    assert "zero blood" in inst_lower or "no blood" in inst_lower
    assert "zero gore" in inst_lower or "no gore" in inst_lower


def test_zombie_survival_preset_manager_integration():
    PresetManager.initialize()
    preset = PresetManager.get_style_by_id("zombie_survival")
    assert preset is not None
    assert preset.id == "zombie_survival"
    assert preset.name == "Zombie Survival"

    # Built-in check
    assert PresetManager.is_builtin_style("zombie_survival")

    # Canonical order list includes it
    all_styles = [s.id for s in PresetManager.get_all_styles()]
    assert "zombie_survival" in all_styles

    # Aliases
    assert PresetManager.get_style_by_id("zombie").id == "zombie_survival"
    assert PresetManager.get_style_by_id("zombies").id == "zombie_survival"
    assert PresetManager.get_style_by_id("zombie_apocalypse").id == "zombie_survival"


def test_zombie_survival_thumbnail_prompt_builder():
    headline = "DAY 30 SURVIVAL"
    prompt = build_viral_thumbnail_prompt(headline=headline, style_id="zombie_survival")
    p_lower = prompt.lower()

    assert "DAY 30 SURVIVAL" in prompt
    assert "flat-red baseball cap" in p_lower
    assert "charcoal" in p_lower
    assert "olive-green" in p_lower
    assert "sharp" in p_lower or "teeth" in p_lower
    assert "strict negative" in p_lower
    assert "photorealism" in p_lower


def test_zombie_survival_stage5_execution():
    from backend.pipeline.stage5_prompts import Stage5PromptGenerator
    from backend.inference.engine import BaseInferenceEngine
    from app.models.planning import ScheduledScene, ScheduledStoryboard
    from tests.test_fix5_batch_truncation import _build_dummy_analysis

    class MockEngine(BaseInferenceEngine):
        def __init__(self):
            super().__init__()
            self.last_user_prompt = ""
        def generate_text(self, prompt, system_prompt="", temperature=0.7, max_tokens=2048):
            self.last_user_prompt = prompt
            return json.dumps({
                "prompts": [
                    {
                        "scene_id": "001",
                        "prompt": "A 2D flat cartoon stick figure hero in backwards red cap and dark charcoal hoodie sprints down a narrow grocery aisle while pursued by a horde of uniform olive-green stick figure zombies with wide circular eyes and sharp jagged teeth.",
                        "subject": "Hero escaping zombie horde",
                        "composition": "Eye-level wide 1-point perspective"
                    }
                ]
            })
        def repair_and_parse_json(self, text):
            return json.loads(text)

    PresetManager.initialize()
    style = PresetManager.get_style_by_id("zombie_survival")
    engine = MockEngine()

    scenes = [
        ScheduledScene(
            scene_id="001",
            beat_id="BEAT-001",
            start_time=0.0,
            end_time=4.5,
            duration=4.5,
            narration_text="I grabbed my bag and ran down the aisle as they closed in.",
            visual_summary="Hero fleeing zombie horde in supermarket"
        )
    ]

    storyboard = ScheduledStoryboard(scenes=scenes, total_duration=4.5)
    analysis = _build_dummy_analysis(period="Modern Post-Apocalypse")

    res = Stage5PromptGenerator.execute(
        engine=engine,
        scheduled_storyboard=storyboard,
        analysis=analysis,
        style_preset=style,
        batch_size=2
    )

    assert len(res) == 1
    assert "MANDATORY ZOMBIE SURVIVAL CHARACTER & HORDE LOCKS" in engine.last_user_prompt
    assert "backwards flat-red baseball cap" in engine.last_user_prompt
    assert "tattered dark-brown jackets" in engine.last_user_prompt
    assert "historical figures in period attire" not in res[0].prompt
    assert "stick figure" in res[0].prompt

