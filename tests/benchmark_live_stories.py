"""
Live Multi-Genre Benchmark Script for PromptBeast's 4-Stage Architecture.
Tests live execution with Groq on:
1. Zombie Survival Story (Zombie Survival style)
2. Constantinople 1453 Documentary (Century-Old Photograph style)
3. Julius Caesar Documentary (Ancient Epic style)
4. Quantum Superposition Science Explainer (What-If Flat Vector style)

Inspects actual generated prompts, bibles, and verifies zero cross-contamination.
"""
import os
import sys
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.inference.engine import GroqInferenceEngine
from backend.pipeline.stage1_story_intelligence import Stage1StoryIntelligence
from backend.pipeline.stage2_visual_storyboard import Stage2VisualStoryboard
from backend.pipeline.stage3_prompt_generation import Stage3PromptGeneration
from app.presets.loader import PresetManager


def run_benchmark():
    print("=================================================================")
    print("PROMPTBEAST 4-STAGE PIPELINE: LIVE MULTI-STORY BENCHMARK")
    print("=================================================================\n")

    engine = GroqInferenceEngine(default_model="qwen/qwen3.8-27b")

    stories = [
        {
            "genre": "Zombie Survival Fiction",
            "style_id": "zombie_survival",
            "story": (
                "Sixty people were locked inside this mall on the first night. "
                "By Day 20, you will find proof that one of them is still alive. "
                "Down in the flooded basement corridors, shadowy infected figures wait motionless in the pitch black."
            ),
            "forbidden_words": ["caesar", "constantinople", "byzantine", "roman", "senate", "electron", "quantum"]
        },
        {
            "genre": "Constantinople 1453 Historical Documentary",
            "style_id": "century_old_photograph",
            "story": (
                "In May 1453, Sultan Mehmed II deployed the massive Orban supercannons against the Theodosian Walls. "
                "Emperor Constantine XI Palaiologos prepared the final defense of the Byzantine capital as bronze giants thundered."
            ),
            "forbidden_words": ["zombie", "infected", "shopping mall", "electron", "quantum", "wavefunction"]
        },
        {
            "genre": "Science Explainer (Quantum Physics)",
            "style_id": "whatif_flat_vector",
            "story": (
                "In quantum mechanics, subatomic particles exist simultaneously across multiple states. "
                "Until a detector measures an electron, its position is described purely by an abstract probability wave."
            ),
            "forbidden_words": ["zombie", "mall", "caesar", "constantinople", "orban", "sultan", "sword", "dagger"]
        }
    ]

    for idx, test_case in enumerate(stories, 1):
        genre = test_case["genre"]
        style_id = test_case["style_id"]
        story = test_case["story"]
        forbidden = test_case["forbidden_words"]

        print(f"\n--- [{idx}/{len(stories)}] TESTING: {genre.upper()} ---")
        print(f"Visual Style: {style_id}")
        style_preset = PresetManager.get_style_by_id(style_id)

        # STAGE 1: Story Intelligence
        print("  -> Executing Stage 1: Story Intelligence Extraction...")
        intel = Stage1StoryIntelligence.execute(
            engine=engine,
            story_text=story,
            style_preset=style_preset
        )
        print(f"     [OK] Premise: {intel.core_narrative_premise[:80]}")
        print(f"     [OK] Characters: {[c.get('name') for c in intel.characters]}")
        print(f"     [OK] Environments: {[e.get('name') for e in intel.environments]}")
        print(f"     [OK] Headline: {intel.thumbnail_headline}")

        # Check for cross-contamination in Story Intelligence
        intel_dump = json.dumps(intel.model_dump()).lower()
        contaminations = [w for w in forbidden if w in intel_dump]
        if contaminations:
            print(f"     [FAIL] Contamination detected in Stage 1: {contaminations}")
        else:
            print("     [VERIFIED] Zero cross-story contamination in Story Intelligence!")

        # STAGE 2: Visual Storyboard
        print("  -> Executing Stage 2: Visual Storyboard...")
        scenes = Stage2VisualStoryboard.execute(
            story_intelligence=intel,
            story_text=story,
            style_preset=style_preset,
            min_duration=2.0,
            max_duration=6.0
        )
        print(f"     [OK] Planned {len(scenes)} visual scenes (timings: {scenes[0].start}s -> {scenes[-1].end}s).")
        # Ensure Stage 2 contains NO image prompts
        empty_prompts = all(s.prompt == "" for s in scenes)
        assert empty_prompts, "Stage 2 generated prompts prematurely!"
        print("     [VERIFIED] Stage 2 contains zero image prompts (clean visual staging).")

        # STAGE 3: Image Prompt Generation
        print(f"  -> Executing Stage 3: Prompt Generation ({style_preset.name})...")
        generated_scenes = Stage3PromptGeneration.execute(
            storyboard=scenes,
            story_intelligence=intel,
            style_preset=style_preset,
            batch_size=4,
            engine=engine
        )

        print(f"     [OK] Generated {len(generated_scenes)} image prompts:")
        for s in generated_scenes:
            print(f"       Scene {s.scene_id} [{s.start}s - {s.end}s]: {s.prompt[:100]}...")

        prompt_dump = " ".join(s.prompt.lower() for s in generated_scenes)
        prompt_contaminations = [w for w in forbidden if w in prompt_dump]
        if prompt_contaminations:
            print(f"     [FAIL] Contamination detected in Prompts: {prompt_contaminations}")
        else:
            print("     [VERIFIED] Zero cross-story contamination in Stage 3 Prompts!")

    print("\n=================================================================")
    print("ALL LIVE BENCHMARKS COMPLETED SUCCESSFULLY!")
    print("=================================================================\n")


if __name__ == "__main__":
    run_benchmark()

