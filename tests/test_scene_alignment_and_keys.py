import sys
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.narration_workflow import parse_visual_breakdown_text, align_visuals_with_timestamps, import_script_json
from app.config.settings import SettingsManager, AppSettings
from app.ai.groq_engine import get_groq_engine


def test_zombie_survival_scene_alignment():
    """Verify that scenes with sub-clauses and number words do not desync or collapse to 0.80s."""
    speech_path = Path("New folder/speech.json")
    story_path = Path("New folder/storyboard.txt")
    if not speech_path.exists() or not story_path.exists():
        return

    res = import_script_json(str(speech_path))
    assert res.success
    story_text = story_path.read_text(encoding="utf-8")
    items = parse_visual_breakdown_text(story_text)
    assert len(items) == 160

    scenes = align_visuals_with_timestamps(items, res.narration)
    assert len(scenes) == 160

    # Scene 1, 2, 3 must be nicely divided sub-clauses (~1.5s - 2.5s each), NOT 21.72s
    sc1 = scenes[0]
    sc2 = scenes[1]
    sc3 = scenes[2]
    assert sc1.start == 0.0
    assert sc3.duration < 5.0, f"Scene 3 duration was {sc3.duration}s, should be < 5.0s!"
    assert sc2.duration < 5.0, f"Scene 2 duration was {sc2.duration}s, should be < 5.0s!"

    # Scenes 60-160 must have natural multi-second durations, not collapsed 0.80s
    scenes_60_to_100 = scenes[59:100]
    non_point_eight = sum(1 for s in scenes_60_to_100 if s.duration > 1.2)
    assert non_point_eight > 35, f"Expected most scenes to have normal durations, got {non_point_eight}"

    # Timeline bounds must match audio length
    last_scene = scenes[-1]
    assert abs(last_scene.end - res.narration.duration_seconds) < 0.1


def test_groq_keys_engine_setter_and_persistence(tmp_path):
    """Verify that groq.api_keys setter works without AttributeError and persists multiple keys."""
    engine = get_groq_engine()
    test_keys = ["gsk_key1111111111111111111111", "gsk_key2222222222222222222222"]
    
    # Setter test
    engine.api_keys = test_keys
    assert engine.api_keys == test_keys

    # AppSettings test
    orig = SettingsManager.load_settings()
    try:
        settings = SettingsManager.load_settings()
        settings.api_keys = test_keys
        SettingsManager.save_settings(settings)

        reloaded = SettingsManager.load_settings()
        assert reloaded.api_keys == test_keys
        assert reloaded.api_key == test_keys[0]
    finally:
        # Restore original user settings
        SettingsManager.save_settings(orig)
