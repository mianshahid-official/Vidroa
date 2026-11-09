"""
Unit tests for Leakage Audit Step 1: Single source of truth for prompts (C.1).
Verifies:
1. Shared prompt loader correctly resolves and loads all valid prompt files.
2. Missing prompt files raise FileNotFoundError.
3. PromptBuilder loads base_system.txt and raises FileNotFoundError on missing files.
4. Inline system prompt constants (STAGE1_SYSTEM_PROMPT, STAGE2_SYSTEM_PROMPT, STAGE3_SYSTEM_PROMPT) are removed.
5. Orphaned Stage4Validator and stage4_validation.txt are deleted.
6. stage3_visual_planning.txt exists and is loaded by Stage3VisualPlanner.
"""
import os
import sys
import unittest
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.pipeline.prompt_loader import load_system_prompt, get_system_prompt_path
from app.ai.prompt_builder import PromptBuilder


class TestStep1PromptLoader(unittest.TestCase):

    def test_all_expected_prompts_exist_and_load(self):
        expected_prompts = [
            "base_system.txt",
            "stage1_analysis.txt",
            "stage2_planning.txt",
            "stage3_prompts.txt",
            "stage3_scheduling.txt",
            "stage3_visual_planning.txt",
            "stage4_prompts.txt",
            "stage5_validation.txt",
            "stage6_replanning.txt",
        ]
        for filename in expected_prompts:
            content = load_system_prompt(filename)
            self.assertTrue(len(content) > 50, f"Prompt {filename} content was suspiciously short: {len(content)} chars")

    def test_missing_prompt_raises_filenotfound(self):
        with self.assertRaises(FileNotFoundError):
            load_system_prompt("non_existent_prompt_file_12345.txt")

    def test_prompt_builder_load_template(self):
        content = PromptBuilder.load_prompt_template("base_system.txt")
        self.assertTrue(len(content) > 20)

        with self.assertRaises(FileNotFoundError):
            PromptBuilder.load_prompt_template("non_existent_template.txt")

    def test_orphaned_stage4_validation_deleted(self):
        self.assertFalse(
            (PROJECT_ROOT / "config" / "system_prompts" / "stage4_validation.txt").exists(),
            "config/system_prompts/stage4_validation.txt should have been deleted."
        )
        self.assertFalse(
            (PROJECT_ROOT / "backend" / "pipeline" / "stage4_validation.py").exists(),
            "backend/pipeline/stage4_validation.py should have been deleted."
        )

        import backend.pipeline
        self.assertFalse(
            hasattr(backend.pipeline, "Stage4Validator"),
            "backend.pipeline should not export Stage4Validator."
        )

    def test_inline_prompt_constants_deleted(self):
        import backend.pipeline.stage1_analysis as s1
        self.assertFalse(
            hasattr(s1, "STAGE1_SYSTEM_PROMPT"),
            "stage1_analysis.py should not define STAGE1_SYSTEM_PROMPT constant."
        )

        import backend.pipeline.stage2_planning as s2
        self.assertFalse(
            hasattr(s2, "STAGE2_SYSTEM_PROMPT"),
            "stage2_planning.py should not define STAGE2_SYSTEM_PROMPT constant."
        )

        import backend.pipeline.stage3_prompts as s3
        self.assertFalse(
            hasattr(s3, "STAGE3_SYSTEM_PROMPT"),
            "stage3_prompts.py should not define STAGE3_SYSTEM_PROMPT constant."
        )

    def test_stage_loader_callers(self):
        import backend.pipeline.stage1_analysis as s1
        import backend.pipeline.stage3_visual_planning as s3v
        import backend.pipeline.stage4_scheduling as s4
        import backend.pipeline.stage5_prompts as s5
        import backend.pipeline.stage6_audit as s6
        import backend.pipeline.stage7_replanning as s7

        self.assertTrue("narrative intelligence analyst" in s1.load_stage1_system_prompt() or "story architect" in s1.load_stage1_system_prompt())
        self.assertTrue("visual narrative" in s3v.load_system_prompt() or "visual storyteller" in s3v.load_system_prompt())
        self.assertTrue("video editor and visual pacing specialist" in s4.load_system_prompt() or "temporal storyboard" in s4.load_system_prompt())
        self.assertTrue("IMAGE PROMPT GENERATION" in s5.load_system_prompt() or "image generation prompts" in s5.load_system_prompt() or "visual prompt" in s5.load_system_prompt())
        self.assertTrue("VALIDATION" in s6.load_system_prompt() or "AUDIT" in s6.load_system_prompt() or "quality auditor" in s6.load_system_prompt() or "repetition" in s6.load_system_prompt())
        self.assertTrue("REPLANNING" in s7.load_system_prompt() or "storyboard reconstruction" in s7.load_system_prompt())


if __name__ == "__main__":
    unittest.main()
