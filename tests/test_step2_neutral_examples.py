"""
Unit tests for Leakage Audit Step 2: Neutral worked examples in every .txt (C.3).
Verifies:
1. No .txt prompt files contain hardcoded story keywords (1453, Mehmed, Byzantine, etc.).
2. .txt prompt files consistently use the neutral lighthouse / coastal setting worked example.
3. 3d_red_blue_stickman.json visual style contains no story-specific military/siege faction examples.
4. Thumbnail generator and prompt builder build from story context rather than hardcoded siege battlefield.
5. Fallback headline defaults to UNTITLED STORY, not FORGOTTEN CONQUEST or CONSTANTINOPLE FALLS.
"""
import re
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.pipeline.prompt_loader import load_system_prompt
from app.core.thumbnail_prompt_builder import build_viral_thumbnail_prompt
from backend.pipeline.stage1_analysis import extract_smart_fallback_headline


FORBIDDEN_STORY_PATTERN = re.compile(
    r"\b(constantinople|mehmed|byzantine|turban|1453|bombard|caravel|morion|tenochtitlan)\b",
    re.IGNORECASE
)


class TestStep2NeutralExamples(unittest.TestCase):

    def test_prompt_txt_files_contain_no_leakage_keywords(self):
        prompt_files = [
            "stage1_analysis.txt",
            "stage2_planning.txt",
            "stage3_prompts.txt",
            "stage3_visual_planning.txt",
            "stage4_prompts.txt",
            "stage5_validation.txt",
        ]
        for filename in prompt_files:
            content = load_system_prompt(filename)
            matches = FORBIDDEN_STORY_PATTERN.findall(content)
            self.assertEqual(
                matches,
                [],
                f"File '{filename}' leaked story keywords: {matches}"
            )

    def test_lighthouse_keeper_example_in_stage1_and_stage4(self):
        s1 = load_system_prompt("stage1_analysis.txt")
        self.assertIn("lighthouse", s1.lower())
        self.assertIn("fresnel", s1.lower())

        s4 = load_system_prompt("stage4_prompts.txt")
        self.assertIn("lighthouse", s4.lower())

    def test_3d_red_blue_stickman_json_has_no_leakage(self):
        style_file = PROJECT_ROOT / "config" / "visual_styles" / "3d_red_blue_stickman.json"
        content = style_file.read_text(encoding="utf-8")
        matches = FORBIDDEN_STORY_PATTERN.findall(content)
        self.assertEqual(matches, [], f"3d_red_blue_stickman.json leaked keywords: {matches}")
        self.assertNotIn("Ottoman", content)
        self.assertNotIn("Byzantine", content)

    def test_thumbnail_prompt_builder_uses_story_context(self):
        # When given non-history story context, thumbnail should NOT mention siege battlefield or fortress walls
        th_prompt = build_viral_thumbnail_prompt(
            headline="THE FINAL PROTOCOL",
            style_id="3d_red_blue_stickman",
            story_context="deep space research station orbiting Europa",
            era_or_setting="futuristic sci-fi"
        )
        self.assertNotIn("siege battlefield", th_prompt.lower())
        self.assertNotIn("fortress walls", th_prompt.lower())
        self.assertIn("THE FINAL PROTOCOL", th_prompt)
        self.assertIn("deep space research station", th_prompt)

    def test_extract_smart_fallback_headline(self):
        # Empty text should fallback to UNTITLED STORY
        self.assertEqual(extract_smart_fallback_headline(""), "UNTITLED STORY")
        self.assertEqual(extract_smart_fallback_headline("the a in"), "UNTITLED STORY")
        # Text with content words
        hl = extract_smart_fallback_headline("Quantum particle accelerator experiments reveal unknown anomalies")
        self.assertNotIn("CONQUEST", hl)
        self.assertNotIn("EMPIRE", hl)
        self.assertIn("QUANTUM", hl)


if __name__ == "__main__":
    unittest.main()
