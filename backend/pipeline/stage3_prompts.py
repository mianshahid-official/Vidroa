STAGE3_SYSTEM_PROMPT = """You are an elite master cinematographic prompt engineer for Google Gemini, Midjourney, FLUX, and SDXL.
Your task is to write concise, high-density, action-first 50 to 90 word image generation prompts for the provided batch of scenes.

MANDATORY GUIDELINES:
1. CONCISE PROMPT LENGTH (50-90 WORDS TARGET):
   - Every prompt must be approximately 50 to 90 words of pure visual instruction.
   - STRICTLY ELIMINATE FLUFF & BLOAT: Do NOT waste words repeating sepia tones, silver gelatin grain, scratches, foxing, chemical stains, or museum discovery clichés.
   - Prioritize actual scene action, physical interactions, and concrete visual information over aesthetic filler.

2. ACTION-FIRST NARRATION FIDELITY (MANDATORY):
   - The prompt MUST directly, vividly depict the tangible physical action, characters, objects, and setting described in the scene's narration excerpt.
   - Incorporate the Character Bible for recurring people, the Location Bible for environments, and the Time Bible for period authenticity.

3. STYLISTIC EXECUTION & HISTORICAL PATINA (MANDATORY):
   - STRICTLY HONOR THE CHOSEN VISUAL STYLE:
     * When the selected style is "Century-Old Photograph" / "Vintage Photograph": Render as an authentic damaged, physically aged archival photograph: warm faded sepia, aged albumen, or rich silver gelatin monochrome tones. Naturally torn, chipped, and frayed borders with irregular edges, random black dust spots, and thin vertical black scratches across the print. Central subject remains sharp, clear, and legible. STRICTLY FORBIDDEN: NO modern vibrant RGB saturated colors (no bright modern blue oceans, no vivid digital greens, no 2024 movie color grading).
     * When another style is selected (e.g. Cinematic Photorealism, 2D Vector): Execute in that designated medium.
   - PERIOD-AUTHENTIC DETAILS & HISTORICAL FIDELITY:
     * Keep historical period and visual rendering aesthetic completely separate. Period accuracy in architecture, armor, weaponry, and textiles (e.g. 15th-century Byzantine/Ottoman armor and bombards, or 16th-century steel morions and caravels).
     * The photographic rendering aesthetic must NEVER alter the story's actual historical epoch, clothing, or weapons.

4. 6-POINT DETAIL CHECKLIST:
   Every prompt must seamlessly weave together:
   1) Main subject (anchored to Character Bible).
   2) Specific physical action / event happening in frame right now.
   3) Physical environment & architectural materials (anchored to Location Bible).
   4) Composition & camera angle.
   5) Natural / dramatic lighting & color palette.
   6) Period authenticity & clean rendering (clean, sharp, no fake damage).

OUTPUT SCHEMA:
Return a strictly valid JSON object with the following structure:
{
  "batch_index": <int>,
  "prompts": [
    {
      "scene_id": "001",
      "visual_subject": "...",
      "prompt": "Action-first, concise 50-90 word visual prompt vividly describing subject, physical action, environment, composition, lighting, period accuracy, and clean rendering..."
    }
  ]
}"""

"""
Pipeline Stage 3: Per-scene image prompt generation.

Strategy: Generate ONE scene prompt per API call with rich contextual architecture:
[(Story: <story context>) (Previous: <previous context>) (Type: <visual modality>) Scene: <detailed visual prompt>]
Supports organic mixed visual modalities (cinematic_scene, infographic_chart, blueprint_schematic, historical_document, tactical_map, data_counter).
"""
import re
from typing import List, Optional
from app.models.presets import SubjectPreset, VisualStylePreset
from app.models.scene import VisualScene, StoryContinuity
from app.ai.prompt_builder import PromptBuilder
from backend.inference.engine import BaseInferenceEngine


_TOKENS_PER_SCENE = 950


class Stage3PromptGenerator:
    """Generates detailed, structured contextual image prompts scene-by-scene."""

    @classmethod
    def generate_batch(
        cls,
        engine: BaseInferenceEngine,
        batch_index: int,
        scenes_batch: List[VisualScene],
        subject_preset: SubjectPreset,
        style_preset: VisualStylePreset,
        custom_subject: Optional[str] = None,
        custom_style: Optional[str] = None,
        continuity: Optional[StoryContinuity] = None,
        story_context: str = "",
        previous_prompt_context: str = ""
    ) -> List[VisualScene]:
        """
        Executes Stage 3 prompt generation for a batch of up to 10 scenes in a single LLM call.
        Ensures strict visual variety, dynamic camera transitions, and authentic style execution.
        Falls back to per-scene generation if the batch call fails or returns partial scenes.
        """
        if not scenes_batch:
            return []

        batch_prompt = PromptBuilder.build_stage3_batch_prompt(
            batch_index=batch_index,
            scenes_batch=scenes_batch,
            subject_preset=subject_preset,
            style_preset=style_preset,
            custom_subject=custom_subject,
            custom_style=custom_style,
            continuity=continuity
        )

        prompts_by_id = {}
        raw_prompts = []
        try:
            batch_data = engine.generate_structured_json(
                prompt=batch_prompt,
                system_prompt=STAGE3_SYSTEM_PROMPT,
                temperature=0.35,
                max_tokens=4000
            )
            raw_prompts = batch_data.get("prompts", [])
            for p_item in raw_prompts:
                sid = str(p_item.get("scene_id", "")).strip()
                p_text = p_item.get("prompt", "").strip()
                if sid and p_text:
                    prompts_by_id[sid] = p_text
            print(f"[Stage3] Batch {batch_index + 1}: Generated {len(prompts_by_id)}/{len(scenes_batch)} prompts in 1 batched call.")
        except Exception as e:
            print(f"[Stage3] Batch {batch_index + 1} structured call failed: {e}. Falling back to individual processing.")

        updated_scenes = []
        cur_prev_context = previous_prompt_context

        for idx, scene in enumerate(scenes_batch):
            sc_id = str(scene.scene_id).strip()
            prompt_text = prompts_by_id.get(sc_id) or prompts_by_id.get(f"{int(sc_id):03d}" if sc_id.isdigit() else "")

            # Also check by index if LLM returned sequential list without exact scene_id
            if not prompt_text and idx < len(raw_prompts):
                cand = raw_prompts[idx].get("prompt", "").strip()
                if cand:
                    prompt_text = cand

            if prompt_text:
                s_copy = scene.model_copy(deep=True)
                modality = getattr(scene, "visual_modality", "cinematic_scene") or "cinematic_scene"
                # Ensure [(Story: ...) (Previous: ...) (Type: ...) Scene: ...] format
                if not prompt_text.startswith("[(") and not prompt_text.startswith("["):
                    story_str = story_context[:80] if story_context else f"{subject_preset.name}, {style_preset.name} style"
                    prev_str = cur_prev_context[:60] if cur_prev_context else "Opening establishing shot"
                    prompt_text = f"[(Story: {story_str}) (Previous: {prev_str}) (Type: {modality}) Scene: {prompt_text}]"
                prompt_text = " ".join(prompt_text.split())
                s_copy.prompt = prompt_text
                updated_scenes.append(s_copy)
                cur_prev_context = f"{s_copy.visual_subject} ({s_copy.framing_suggestion or 'Framed shot'})"
            else:
                # Per-scene fallback if missed in batch
                single_result = cls._generate_single(
                    engine=engine,
                    scene=scene,
                    subject_preset=subject_preset,
                    style_preset=style_preset,
                    custom_subject=custom_subject,
                    custom_style=custom_style,
                    continuity=continuity,
                    story_context=story_context,
                    previous_prompt_context=cur_prev_context
                )
                updated_scenes.append(single_result)
                cur_prev_context = f"{single_result.visual_subject} ({single_result.framing_suggestion or 'Framed shot'})"

        return updated_scenes

    @classmethod
    def _generate_single(
        cls,
        engine: BaseInferenceEngine,
        scene: VisualScene,
        subject_preset: SubjectPreset,
        style_preset: VisualStylePreset,
        custom_subject: Optional[str] = None,
        custom_style: Optional[str] = None,
        continuity: Optional[StoryContinuity] = None,
        story_context: str = "",
        previous_prompt_context: str = ""
    ) -> VisualScene:
        """Generates one rich contextual image prompt for a single scene via LLM."""
        prompt = PromptBuilder.build_stage3_single_scene_prompt(
            scene=scene,
            subject_preset=subject_preset,
            style_preset=style_preset,
            custom_subject=custom_subject,
            custom_style=custom_style,
            continuity=continuity,
            story_context=story_context,
            previous_prompt_context=previous_prompt_context
        )

        modality = getattr(scene, "visual_modality", "cinematic_scene") or "cinematic_scene"
        s_copy = scene.model_copy(deep=True)

        try:
            raw = engine.generate_text(prompt, system_prompt=STAGE3_SYSTEM_PROMPT, temperature=0.35, max_tokens=_TOKENS_PER_SCENE)
            generated_prompt = raw.strip()
            if generated_prompt.startswith("```"):
                m = re.search(r"```(?:\w+)?\s*([\s\S]+?)\s*```", generated_prompt)
                if m:
                    generated_prompt = m.group(1).strip()

            if generated_prompt:
                # Format check: ensure [(Story: ...) (Previous: ...) (Type: ...) Scene: ...] format
                if not generated_prompt.startswith("[(") and not generated_prompt.startswith("["):
                    story_str = story_context[:80] if story_context else f"{subject_preset.name}, {style_preset.name} style"
                    prev_str = previous_prompt_context[:60] if previous_prompt_context else "Opening establishing shot"
                    generated_prompt = f"[(Story: {story_str}) (Previous: {prev_str}) (Type: {modality}) Scene: {generated_prompt}]"

                # Replace internal linebreaks so it is clean single-line per scene
                generated_prompt = " ".join(generated_prompt.split())
                s_copy.prompt = generated_prompt
                return s_copy

        except Exception as e:
            print(f"[Stage3] Scene {scene.scene_id} generation failed: {e}. Using structured fallback.")

        # Structured rich fallback adhering strictly to the user requested format
        style_desc = custom_style if custom_style else style_preset.name
        subj_desc = custom_subject if custom_subject else subject_preset.system_instructions
        story_str = story_context[:80] if story_context else f"{style_desc} narrative"
        prev_str = previous_prompt_context[:60] if previous_prompt_context else "Opening visual scene"

        is_photo_era = continuity.time_period.is_photographic_era if (continuity and continuity.time_period) else False
        is_century_old_style = style_preset.id in ("vintage_photograph", "century_old_photograph") or "century" in style_desc.lower() or "vintage" in style_desc.lower()

        if is_century_old_style:
            fallback_scene = (
                f"Authentic damaged, physically aged archival photograph of {scene.visual_subject}. "
                f"Action: {scene.action or 'Significant historical event underway'}. "
                f"Setting: {scene.environment or 'Authentic period setting'} with realistic stone, metal, wood, and cloth textures. "
                f"Composition: {scene.composition or scene.framing_suggestion or 'Cinematic medium shot'}, dramatic chiaroscuro lighting, "
                f"warm faded sepia or silver gelatin monochrome tones, naturally torn, chipped, and frayed borders, "
                f"random black dust spots and thin vertical black scratches across the print, central historical subject sharp and legible, "
                f"authentically preserving period-accurate historical attire and artifacts."
            )
        else:
            fallback_scene = (
                f"Masterfully composed {style_desc} depicting {scene.visual_subject}. "
                f"Action: {scene.action or 'Central dramatic action underway'}. "
                f"Setting: {scene.environment or 'Rich atmospheric setting'} with authentic material surfaces. "
                f"Composition: {scene.composition or scene.framing_suggestion or 'Cinematic framing'}, directional lighting, "
                f"clean high-resolution rendering, and authentic {style_desc} aesthetic."
            )

        s_copy.prompt = f"[(Story: {story_str}) (Previous: {prev_str}) (Type: {modality}) Scene: {fallback_scene}]"
        return s_copy

    @classmethod
    def regenerate_single_scene(
        cls,
        engine: BaseInferenceEngine,
        scene: VisualScene,
        story_summary: str,
        subject_preset: SubjectPreset,
        style_preset: VisualStylePreset,
        custom_subject: Optional[str] = None,
        custom_style: Optional[str] = None,
        continuity: Optional[StoryContinuity] = None
    ) -> VisualScene:
        """Regenerates a single scene prompt."""
        return cls._generate_single(
            engine=engine,
            scene=scene,
            subject_preset=subject_preset,
            style_preset=style_preset,
            custom_subject=custom_subject,
            custom_style=custom_style,
            continuity=continuity,
            story_context=story_summary
        )
