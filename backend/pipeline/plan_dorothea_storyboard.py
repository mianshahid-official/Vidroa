"""
Executes Groq AI Pipeline for Dorothea Dix Story:
- Stage 1: Narrative Analysis & Story Bible (Character & Location continuity)
- Stage 2: Storyboard Planning & Dynamic Pacing (Groq AI decides total images & exact cut points)
- Stage 3: Prompt Generation in Century-Old Photograph style
"""
import os
import sys
import json
from pathlib import Path

# Set up project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.inference.engine import GroqInferenceEngine
from backend.pipeline.stage1_analysis import Stage1Analyzer
from backend.pipeline.stage2_planning import Stage2Planner
from backend.pipeline.stage3_prompts import Stage3PromptGenerator
from app.models.presets import SubjectPreset, VisualStylePreset
from app.models.project import ProjectConfig, TimingMode
from app.models.timeline import NarrationData


def run_planning():
    story_path = Path("story.txt")
    narration_path = Path("projects/Dorothea_Dix_1841/audio/narration.json")

    with open(story_path, "r", encoding="utf-8") as f:
        story_text = f.read().strip()

    with open(narration_path, "r", encoding="utf-8") as f:
        narr_dict = json.load(f)
        narration = NarrationData(**narr_dict)

    print(f"Loaded story: {len(story_text.split())} words")
    print(f"Loaded narration: {len(narration.words)} words, {narration.duration_seconds:.2f} seconds")

    engine = GroqInferenceEngine()

    from app.presets.loader import PresetManager

    subject_preset = PresetManager.get_subject_by_id("history")
    style_preset = PresetManager.get_style_by_id("vintage_photograph")

    config = ProjectConfig(
        timing_mode=TimingMode.AI_DECIDES
    )

    # 1. Stage 1: Story Analysis & Bible
    print("\n--- Running Stage 1: Story Analysis & Character Bible ---")
    analysis = Stage1Analyzer.execute(
        engine=engine,
        story_text=story_text,
        subject_preset=subject_preset
    )
    print(f"Analysis complete: {analysis.story_summary[:120]}...")
    if analysis.continuity and analysis.continuity.characters:
        for c in analysis.continuity.characters:
            print(f"  Character: {c.name} - {c.description[:80]}")

    # 2. Stage 2: Storyboard Planning (AI Decides Scene Count & Pacing)
    print("\n--- Running Stage 2: Storyboard Planning (Groq AI Decides Scenes & Placings) ---")
    scenes = Stage2Planner.execute(
        engine=engine,
        story_text=story_text,
        analysis_summary=analysis.story_summary,
        narration=narration,
        config=config,
        subject_preset=subject_preset,
        style_preset=style_preset
    )

    print(f"\nGroq AI Decided Total Scenes: {len(scenes)}")
    for sc in scenes:
        print(f"  Scene {sc.scene_id} [{sc.start:.1f}s - {sc.end:.1f}s | {sc.duration:.1f}s] ({sc.visual_modality}): {sc.visual_subject[:60]}...")

    # Save planned scenes to project
    plan_out_path = Path("projects/Dorothea_Dix_1841/storyboard_plan.json")
    with open(plan_out_path, "w", encoding="utf-8") as f:
        json.dump([s.model_dump() for s in scenes], f, indent=2)
    print(f"\nSaved storyboard plan to: {plan_out_path}")


if __name__ == "__main__":
    run_planning()
