"""
Modular prompt builder that dynamically combines base instructions, subject rules,
visual style guidelines, timing rules, and continuity specifications.
"""
from typing import Optional, List, Dict, Any
from app.presets.loader import PresetManager
from app.models.presets import SubjectPreset, VisualStylePreset
from app.models.scene import StoryContinuity, VisualScene
from app.models.project import ProjectConfig, ImageCountMode, TimingMode
from app.config.constants import SYSTEM_PROMPTS_DIR


class PromptBuilder:
    """Constructs modular prompts for each generation stage."""

    @classmethod
    def load_prompt_template(cls, filename: str) -> str:
        filepath = SYSTEM_PROMPTS_DIR / filename
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read().strip()
        return ""

    @classmethod
    def build_stage1_prompt(
        cls,
        story_text: str,
        subject_preset: SubjectPreset,
        custom_subject: Optional[str] = None
    ) -> str:
        base = cls.load_prompt_template("base_system.txt")
        stage1 = cls.load_prompt_template("stage1_analysis.txt")

        subject_rules = custom_subject if (subject_preset.id == "custom" and custom_subject) else subject_preset.system_instructions

        prompt = (
            f"{base}\n\n"
            f"=== DOMAIN SUBJECT CONTEXT ===\n"
            f"Subject: {subject_preset.name}\n"
            f"Subject Rules:\n{subject_rules}\n\n"
            f"=== STAGE 1: STORY ANALYSIS ===\n"
            f"{stage1}\n\n"
            f"=== INPUT STORY NARRATION ===\n"
            f"{story_text}"
        )
        return prompt

    @classmethod
    def build_stage2_prompt(
        cls,
        story_text: str,
        analysis_summary: str,
        config: ProjectConfig,
        subject_preset: SubjectPreset,
        style_preset: VisualStylePreset,
        word_count: int,
        duration_seconds: float,
        has_timestamps: bool
    ) -> str:
        base = cls.load_prompt_template("base_system.txt")
        stage2 = cls.load_prompt_template("stage2_planning.txt")

        # Replace variables safely without breaking JSON braces
        target_count_str = str(config.target_image_count) if config.image_count_mode == ImageCountMode.EXACT else "Auto"
        stage2_formatted = (
            stage2.replace("{min_duration}", str(config.min_duration))
                  .replace("{preferred_duration}", str(config.preferred_duration))
                  .replace("{max_duration}", str(config.max_duration))
                  .replace("{timing_mode}", str(config.timing_mode.value))
                  .replace("{count_mode}", str(config.image_count_mode.value))
                  .replace("{target_count}", target_count_str)
        )

        subject_rules = config.custom_subject if (config.subject_id == "custom" and config.custom_subject) else subject_preset.system_instructions
        style_rules = config.custom_style if (config.visual_style_id == "custom" and config.custom_style) else style_preset.system_instructions

        prompt = (
            f"{base}\n\n"
            f"=== DOMAIN & STYLE CONTEXT ===\n"
            f"Subject: {subject_preset.name} -> {subject_rules}\n"
            f"Visual Style: {style_preset.name} -> {style_rules}\n\n"
            f"=== STORY ANALYSIS SUMMARY ===\n"
            f"{analysis_summary}\n\n"
            f"=== TIMELINE PARAMETERS ===\n"
            f"Total Story Words: {word_count}\n"
            f"Total Narration Duration: {duration_seconds:.2f} seconds\n"
            f"Word-Level Timestamps Provided: {'YES' if has_timestamps else 'NO (Estimate boundaries evenly)'}\n\n"
            f"{stage2_formatted}\n\n"
            f"=== FULL STORY TEXT ===\n"
            f"{story_text}"
        )
        return prompt

    @classmethod
    def build_stage3_batch_prompt(
        cls,
        batch_index: int,
        scenes_batch: List[VisualScene],
        subject_preset: SubjectPreset,
        style_preset: VisualStylePreset,
        custom_subject: Optional[str] = None,
        custom_style: Optional[str] = None,
        continuity: Optional[StoryContinuity] = None
    ) -> str:
        base = cls.load_prompt_template("base_system.txt")
        stage3 = cls.load_prompt_template("stage3_prompts.txt")

        subject_rules = custom_subject if (subject_preset.id == "custom" and custom_subject) else subject_preset.system_instructions
        style_rules = custom_style if (style_preset.id == "custom" and custom_style) else style_preset.system_instructions

        stage3_formatted = (
            stage3.replace("{visual_style}", style_rules)
                  .replace("{subject_rules}", subject_rules)
        )

        continuity_block = ""
        if continuity:
            tp = getattr(continuity, "time_period", None)
            if tp:
                continuity_block += (
                    f"\n--- TIME & PERIOD BIBLE ---\n"
                    f"Era: {tp.era} ({tp.decade_or_year or 'Period authentic'})\n"
                    f"Technology Level: {tp.technology_level}\n"
                    f"Historical Lighting: {tp.lighting_methods}\n"
                    f"Attire Conventions: {tp.wardrobe_norms}\n"
                    f"Atmosphere Patina: {tp.atmosphere_notes}\n"
                )
            if continuity.characters:
                c_details = "\n".join([f"- {c.name} ({getattr(c, 'role', 'Character') or 'Character'}): {c.physical_description} | Attire: {c.clothing or 'Period attire'}" for c in continuity.characters])
                continuity_block += f"\n--- CHARACTER BIBLE (STRICT CONSISTENCY) ---\n{c_details}\n"
            if continuity.locations:
                l_details = "\n".join([f"- {l.name}: {l.environmental_features} | Architecture: {l.architectural_style or 'Period'} | Lighting: {l.lighting_mood or 'Chiaroscuro'}" for l in continuity.locations])
                continuity_block += f"\n--- LOCATION BIBLE (ENVIRONMENTAL CONSISTENCY) ---\n{l_details}\n"
            if continuity.key_objects:
                o_details = "\n".join([f"- {o.name}: {o.visual_description}" for o in continuity.key_objects])
                continuity_block += f"\n--- KEY OBJECT BIBLE ---\n{o_details}\n"

        scenes_context = []
        for s in scenes_batch:
            action_line = f"  Physical Action: {s.action}\n" if getattr(s, "action", "") else ""
            env_line = f"  Environment: {s.environment}\n" if getattr(s, "environment", "") else ""
            comp_line = f"  Composition: {s.composition or s.framing_suggestion}\n" if (getattr(s, "composition", "") or s.framing_suggestion) else ""
            conf_line = f"  Historical Confidence: {s.historical_confidence}\n" if getattr(s, "historical_confidence", "") else ""
            sc_text = (
                f"Scene ID: {s.scene_id} ({s.start:.2f}s - {s.end:.2f}s, duration: {s.duration:.2f}s)\n"
                f"  Narration Excerpt: \"{s.narration_excerpt}\"\n"
                f"  Visual Subject: {s.visual_subject}\n"
                f"{action_line}"
                f"{env_line}"
                f"{comp_line}"
                f"{conf_line}"
                f"  Visual Purpose: {s.visual_purpose}\n"
            )
            scenes_context.append(sc_text)

        scenes_block = "\n".join(scenes_context)

        prompt = (
            f"{base}\n\n"
            f"=== SELECTED VISUAL STYLE (MANDATORY) ===\n"
            f"Style Name: {style_preset.name}\n"
            f"Instructions:\n{style_rules}\n\n"
            f"=== SUBJECT DOMAIN RULES ===\n"
            f"Subject: {subject_preset.name}\n"
            f"Rules:\n{subject_rules}\n"
            f"{continuity_block}\n"
            f"{stage3_formatted}\n\n"
            f"=== BATCH {batch_index + 1} SCENES TO GENERATE ===\n"
            f"{scenes_block}"
        )
        return prompt

    @classmethod
    def build_stage3_single_scene_prompt(
        cls,
        scene,
        subject_preset,
        style_preset,
        custom_subject=None,
        custom_style=None,
        continuity=None,
        story_context: str = "",
        previous_prompt_context: str = ""
    ) -> str:
        """
        Builds a structured contextual image prompt request.
        Produces: [(Story: <story context>) (Previous: <previous context>) (Type: <visual modality>) Scene: <detailed prompt>]
        Supports organic visual modalities: cinematic_scene, infographic_chart, blueprint_schematic, historical_document, tactical_map, data_counter.
        """
        subject_rules = custom_subject if (subject_preset.id == "custom" and custom_subject) else subject_preset.system_instructions
        style_rules = custom_style if (style_preset.id == "custom" and custom_style) else style_preset.system_instructions
        modality = getattr(scene, "visual_modality", "cinematic_scene") or "cinematic_scene"

        continuity_block = ""
        if continuity:
            tp = getattr(continuity, "time_period", None)
            if tp:
                continuity_block += (
                    f"\nTIME & PERIOD BIBLE:\n"
                    f"- Era: {tp.era} ({tp.decade_or_year or 'Period authentic'})\n"
                    f"- Technology Level: {tp.technology_level}\n"
                    f"- Lighting: {tp.lighting_methods}\n"
                    f"- Wardrobe Norms: {tp.wardrobe_norms}\n"
                )
            if continuity.characters:
                c_details = "\n".join([f"- {c.name}: {c.physical_description} | Clothing: {c.clothing or 'Period attire'}" for c in continuity.characters])
                continuity_block += f"\nCHARACTERS (maintain strict visual consistency):\n{c_details}\n"
            if continuity.locations:
                l_details = "\n".join([f"- {l.name}: {l.environmental_features} | Style: {l.architectural_style or 'Period'}" for l in continuity.locations])
                continuity_block += f"\nLOCATIONS:\n{l_details}\n"

        prev_info = f"Previous Frame Context: {previous_prompt_context}\n" if previous_prompt_context else "Previous Frame Context: Opening establishing scene.\n"
        story_info = f"Overarching Narrative Context: {story_context}\n" if story_context else ""

        is_century_old = style_preset.id in ("vintage_photograph", "century_old_photograph") or "century" in style_preset.name.lower() or "vintage" in style_preset.name.lower()
        style_specific_instructions = ""
        if is_century_old:
            style_specific_instructions = (
                "STYLE EXECUTION RULES: AUTHENTIC CENTURY-OLD ARCHIVAL PHOTOGRAPH / DAMAGED ANTIQUE PLATE PRINT:\n"
                "- Timeless warm faded sepia, aged albumen, or rich silver gelatin monochrome tones with deep dynamic range.\n"
                "- STRICTLY FORBIDDEN: NO modern vibrant RGB saturated colors (NO bright modern blue seas, NO vivid digital greens, NO 2024 Hollywood movie color grading).\n"
                "- Physically worn, irregular edges with naturally torn, chipped, and frayed borders.\n"
                "- Authentic photographic plate imperfections: random black dust spots, photographic specks, and thin vertical black scratches across the print.\n"
                "- Central historical subject remains sharp, clear, and legible, with physical damage and wear concentrated around edges and perimeter.\n\n"
            )

        modality_instructions = {
            "infographic_chart": f"Data visualization or chart rendered strictly in the {style_preset.name} visual style (never generic vector). Include legible comparative metrics, trendlines, and authentic medium textures.",
            "blueprint_schematic": f"Technical draft, architectural schematic, or mechanical cross-section rendered in {style_preset.name} style with measurement annotations and drafted structural lines.",
            "historical_document": f"Period document, letter, treaty, or newspaper front-page executed with {style_preset.name} aesthetic, aged tactile surfaces, and authentic typography.",
            "tactical_map": f"Cartographic map with terrain contours and route markings executed in the {style_preset.name} artistic medium.",
            "data_counter": f"Bold numerical callout or dramatic statistical focus integrated seamlessly into {style_preset.name} style.",
            "cinematic_scene": f"Cinematic scene with full character action, environmental depth, lighting direction, and {style_preset.name} visual rendering."
        }.get(modality, f"Full cinematic frame rendered in {style_preset.name} style.")

        action_info = f"- Physical Action: {getattr(scene, 'action', '')}\n" if getattr(scene, 'action', '') else ""
        env_info = f"- Environment: {getattr(scene, 'environment', '')}\n" if getattr(scene, 'environment', '') else ""
        comp_info = f"- Composition & Angle: {getattr(scene, 'composition', '') or scene.framing_suggestion or 'Medium shot'}\n"

        prompt = (
            f"You are an elite AI image prompt writer.\n\n"
            f"MANDATORY VISUAL STYLE: {style_preset.name}\n{style_rules}\n\n"
            f"SUBJECT DOMAIN: {subject_preset.name}\n{subject_rules}\n\n"
            f"{story_info}"
            f"{prev_info}"
            f"{continuity_block}"
            f"CURRENT SCENE TO DESCRIBE:\n"
            f"- Spoken Narration: \"{scene.narration_excerpt}\"\n"
            f"- Visual Subject: {scene.visual_subject}\n"
            f"{action_info}"
            f"{env_info}"
            f"{comp_info}"
            f"- Visual Modality: {modality} -> {modality_instructions}\n\n"
            f"{style_specific_instructions}"
            f"CRITICAL PROMPT REQUIREMENTS:\n"
            f"1. CONCISE LENGTH: Write a concise, high-density prompt of approximately 50 to 90 words for this scene.\n"
            f"2. DETAIL CHECKLIST: Clearly specify the main focal subject, specific physical action underway, setting & materials, composition & camera angle, and natural/dramatic lighting.\n"
            f"3. ZERO FLUFF: Eliminate repetitive filler about sepia tones, silver gelatin grain, scratches, foxing, or chemical stains.\n"
            f"4. UNIFIED ART STYLE: If this scene is a chart, map, or document, it MUST be executed in the appropriate period medium.\n\n"
            f"OUTPUT FORMAT (single continuous block, no linebreaks inside):\n"
            f"[(Story: <core narrative & style context>) (Previous: <previous scene visual continuity>) (Type: {modality}) Scene: <concise 50-90 word detailed visual prompt>]\n"
            f"Return ONLY this structured prompt."
        )
        return prompt

    @classmethod
    def build_single_scene_regenerate_prompt(
        cls,
        scene,
        story_summary: str,
        subject_preset,
        style_preset,
        custom_subject=None,
        custom_style=None,
        continuity=None
    ) -> str:
        return cls.build_stage3_single_scene_prompt(
            scene=scene,
            subject_preset=subject_preset,
            style_preset=style_preset,
            custom_subject=custom_subject,
            custom_style=custom_style,
            continuity=continuity
        )
