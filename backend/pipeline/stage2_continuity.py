"""
Stage 2: Continuity Bible Management and Serialization.
Validates, organizes, and persists Character, Location, Object, and Time Period bibles.
"""
from pathlib import Path
from typing import Optional, List, Dict, Any
from app.models.planning import ContinuityBible, CharacterEntity, LocationEntity, ObjectEntity
from app.models.scene import StoryContinuity, CharacterContinuity, LocationContinuity, ObjectContinuity, TimePeriodContinuity


class Stage2ContinuityManager:
    """Manages continuity entities and disk persistence for visual planning."""

    @classmethod
    def save_bibles_to_disk(
        cls,
        project_dir: Path,
        continuity_bible: ContinuityBible,
        time_period_summary: str = "",
        script_summary: str = "",
        thumbnail_headline: str = "",
        thumbnail_prompt: str = ""
    ) -> Dict[str, str]:
        """
        Saves character_bible.txt, location_bible.txt, time_bible.txt,
        story_events.txt, and story_bible.txt to project root and images subfolder.
        """
        if not project_dir:
            return {}

        project_dir = Path(project_dir)
        dirs = [project_dir]
        img_dir = project_dir / "images"
        if img_dir.exists():
            dirs.append(img_dir)

        # 1. Character Bible Text
        char_lines = [
            "==========================================================",
            "📖 CHARACTER CONTINUITY BIBLE",
            "==========================================================\n"
        ]
        if continuity_bible.characters:
            for c in continuity_bible.characters:
                char_lines.append(f"NAME: {c.name}")
                char_lines.append(f"ROLE: {c.role}")
                char_lines.append(f"APPEARANCE: {c.appearance}")
                char_lines.append(f"WARDROBE/ARMOR: {c.costume}")
                if c.recurring_motifs:
                    char_lines.append(f"RECURRING MOTIFS: {', '.join(c.recurring_motifs)}")
                if c.transformations:
                    char_lines.append(f"TRANSFORMATIONS: {', '.join(c.transformations)}")
                char_lines.append("-" * 40)
        else:
            char_lines.append("No specific recurring individuals identified; historical period archetypes active.\n")
        char_text = "\n".join(char_lines) + "\n"

        # 2. Location Bible Text
        loc_lines = [
            "==========================================================",
            "🏛️ LOCATION CONTINUITY BIBLE",
            "==========================================================\n"
        ]
        if continuity_bible.locations:
            for l in continuity_bible.locations:
                loc_lines.append(f"LOCATION: {l.name}")
                loc_lines.append(f"DESCRIPTION: {l.description}")
                loc_lines.append(f"ENVIRONMENT: {l.environment_details}")
                loc_lines.append(f"LIGHTING: {l.lighting_default}")
                loc_lines.append(f"CONSTRAINTS: {l.historical_or_setting_constraints}")
                loc_lines.append("-" * 40)
        else:
            loc_lines.append("General historical environments active.\n")
        loc_text = "\n".join(loc_lines) + "\n"

        # 3. Object & Time Period Bible Text
        time_lines = [
            "==========================================================",
            "⏳ TIME & PERIOD CONTINUITY BIBLE",
            "==========================================================\n"
        ]
        if time_period_summary:
            time_lines.append(f"HISTORICAL / SETTING PERIOD:\n{time_period_summary}\n")
        if continuity_bible.objects_and_motifs:
            time_lines.append("\nKEY ARTIFACTS & SYMBOLIC OBJECTS:")
            for o in continuity_bible.objects_and_motifs:
                time_lines.append(f"• {o.name}: {o.description} ({o.symbolic_or_narrative_meaning})")
        time_text = "\n".join(time_lines) + "\n"

        # 4. Master Story Bible Text
        master_lines = [
            "==========================================================",
            "📚 MASTER STORY & VISUAL CONTINUITY BIBLE",
            "==========================================================\n",
            f"SUMMARY:\n{script_summary}\n",
            f"VIRAL THUMBNAIL HOOK: {thumbnail_headline}\n",
            f"VIRAL THUMBNAIL PROMPT:\n{thumbnail_prompt}\n",
            time_text,
            char_text,
            loc_text
        ]
        master_text = "\n".join(master_lines) + "\n"

        for d in dirs:
            try:
                d.mkdir(parents=True, exist_ok=True)
                (d / "character_bible.txt").write_text(char_text, encoding="utf-8")
                (d / "location_bible.txt").write_text(loc_text, encoding="utf-8")
                (d / "time_bible.txt").write_text(time_text, encoding="utf-8")
                (d / "story_bible.txt").write_text(master_text, encoding="utf-8")
            except Exception as e:
                print(f"[Stage2Continuity] Notice writing bibles to {d}: {e}")

        return {
            "character_bible": char_text,
            "location_bible": loc_text,
            "time_bible": time_text,
            "master_bible": master_text
        }

