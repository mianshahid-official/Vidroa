"""
Tests for the What-If Flat Vector visual style (Task 2, Section 5).
Verifies:
- config/visual_styles/whatif_flat_vector.json loads and contains all required fields.
- Preview images exist in both .png and .jpg formats.
- System instructions strictly conform to the locked style specification.
- Zero forbidden fixed-example tokens appear in the style file.
- PresetManager and alias resolution work correctly.
"""
import json
import re
from pathlib import Path
import pytest
from app.presets.loader import PresetManager

FORBIDDEN_TERMS_RE = re.compile(
    r"\b(lighthouse|keeper|finch|blackwood|fresnel|lamp sweep|"
    r"1453|mehmed|ottoman|byzantine|constantinople|caesar|cortes|dorothea|theodosian)\b",
    re.IGNORECASE,
)

STYLE_PATH = Path("config/visual_styles/whatif_flat_vector.json")
PREVIEW_PNG = Path("assets/style_previews/whatif_flat_vector.png")
PREVIEW_JPG = Path("assets/style_previews/whatif_flat_vector.jpg")


def test_whatif_style_file_and_schema():
    assert STYLE_PATH.exists(), f"Missing visual style file: {STYLE_PATH}"
    with open(STYLE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Required fields
    assert data.get("id") == "whatif_flat_vector"
    assert data.get("name") == "What-If Flat Vector"
    assert data.get("category") == "2D Animation"
    assert isinstance(data.get("description"), str) and len(data["description"]) > 10
    assert isinstance(data.get("system_instructions"), str) and len(data["system_instructions"]) > 100
    assert data.get("is_custom") is False


def test_whatif_preview_images_exist():
    assert PREVIEW_PNG.exists(), f"Missing PNG preview: {PREVIEW_PNG}"
    assert PREVIEW_JPG.exists(), f"Missing JPG preview: {PREVIEW_JPG}"
    assert PREVIEW_PNG.stat().st_size > 0
    assert PREVIEW_JPG.stat().st_size > 0


def test_whatif_no_forbidden_terms():
    with open(STYLE_PATH, "r", encoding="utf-8") as f:
        raw_text = f.read()

    matches = FORBIDDEN_TERMS_RE.findall(raw_text)
    assert not matches, f"Forbidden fixed-example terms found in {STYLE_PATH}: {matches}"


def test_whatif_style_lock_elements():
    with open(STYLE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    instructions = data["system_instructions"]

    # Verify key style locks are present
    assert "black stick figure" in instructions.lower()
    assert "round" in instructions.lower() and "black head" in instructions.lower()
    assert "white dot eyes" in instructions.lower()
    assert "bright red hoodie" in instructions.lower()
    assert "uniform thickness" in instructions.lower()
    assert "1/20" in instructions
    assert "dark navy" in instructions.lower()
    assert "glowing windows" in instructions.lower()
    assert "16:9" in instructions
    assert "strictly avoid" in instructions.lower()


def test_whatif_preset_manager_integration():
    PresetManager.initialize()
    preset = PresetManager.get_style_by_id("whatif_flat_vector")
    assert preset is not None
    assert preset.id == "whatif_flat_vector"
    assert preset.name == "What-If Flat Vector"

    # Built-in check
    assert PresetManager.is_builtin_style("whatif_flat_vector")

    # Canonical order list includes it
    all_styles = [s.id for s in PresetManager.get_all_styles()]
    assert "whatif_flat_vector" in all_styles

    # Aliases
    assert PresetManager.get_style_by_id("what_if_flat_vector").id == "whatif_flat_vector"
    assert PresetManager.get_style_by_id("whatif").id == "whatif_flat_vector"
    assert PresetManager.get_style_by_id("what_if").id == "whatif_flat_vector"
