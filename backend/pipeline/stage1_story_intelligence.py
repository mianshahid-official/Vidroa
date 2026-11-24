"""
Stage 1: Story Intelligence Module for PromptBeast.
Extracts comprehensive story, character, environment, and visual continuity bibles
dynamically from the script and user ideas without any hardcoded assumptions.
"""
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, List

from app.models.planning import StoryIntelligence, ScriptAnalysis
from app.models.presets import SubjectPreset, VisualStylePreset
from app.models.timeline import NarrationData
from backend.inference.engine import BaseInferenceEngine, GroqInferenceEngine


STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "up", "about", "into", "over", "after",
    "beneath", "under", "above", "this", "that", "these", "those", "is",
    "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "can", "could", "will", "would", "shall", "should"
}


def is_valid_thumbnail_headline(text: str) -> bool:
    """Validates that a thumbnail headline is 2-4 punchy words and not a question/filler fragment."""
    if not text or len(text.strip()) < 3:
        return False
    words = [w for w in text.strip().split() if w]
    if len(words) < 2 or len(words) > 5:
        return False
    first = words[0].upper()
    second = words[1].upper() if len(words) > 1 else ""
    if first in ("HOW", "WHY", "WHAT", "WHERE", "WHEN", "WHO", "WHICH", "DID", "DO", "DOES", "IS", "WAS", "ARE", "WERE"):
        return False
    if f"{first} {second}" in ("HOW DID", "WHY DID", "WHAT WAS", "WHERE DID", "IN THE", "ONCE UPON", "UNTITLED PROJECT"):
        return False
    return True


def extract_smart_fallback_headline(story_text: str) -> str:
    """Extracts 2-3 substantive, high-impact uppercase keywords from story text without stop words."""
    clean_words = [re.sub(r"[^\w]", "", w).upper() for w in story_text.split() if w.strip()]
    content_words = [w for w in clean_words if w and w.lower() not in STOP_WORDS and len(w) > 2]
    if len(content_words) >= 3:
        return " ".join(content_words[:3])
    elif len(content_words) >= 2:
        return " ".join(content_words[:2])
    return "UNTITLED STORY"


def load_story_bible_system_prompt() -> str:
    prompt_file = Path("config/system_prompts/story_bible_extraction.txt")
    if prompt_file.exists():
        try:
            return prompt_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return "You are an expert story analyst. Extract comprehensive story, character, environment, and style bibles in JSON."


def save_story_bibles(project_dir: Path, analysis: Any):
    """
    Saves character_bible.txt, location_bible.txt, time_bible.txt, and story_bible.txt
    directly in project root and project images folder.
    Accepts StoryIntelligence, StoryAnalysis, or ScriptAnalysis.
    """
    if not project_dir:
        return

    p_dir = Path(project_dir)
    p_dir.mkdir(parents=True, exist_ok=True)
    dirs = [p_dir]
    img_dir = p_dir / "images"
    if img_dir.exists():
        dirs.append(img_dir)

    # Convert to StoryIntelligence or dict representation
    intel: Optional[StoryIntelligence] = None
    if isinstance(analysis, StoryIntelligence):
        intel = analysis
    elif hasattr(analysis, "to_script_analysis"):
        try:
            sa = analysis.to_script_analysis()
            intel = StoryIntelligence(
                story_summary=sa.script_summary,
                historical_or_setting_period=sa.historical_or_setting_period,
                thumbnail_headline=sa.thumbnail_headline,
                thumbnail_prompt=sa.thumbnail_prompt
            )
        except Exception:
            pass

    # Extract character, environment, object strings
    if intel:
        char_text = "\n\n".join(
            f"=== {c.get('name', 'Character')} ===\n"
            f"Role: {c.get('role', '')}\n"
            f"Physical Description: {c.get('physical_description', c.get('appearance', ''))}\n"
            f"Clothing & Gear: {c.get('clothing_and_gear', c.get('costume', ''))}\n"
            f"Consistency Rules: {c.get('consistency_rules', '')}"
            for c in intel.characters
        )
        env_text = "\n\n".join(
            f"=== {e.get('name', 'Location')} ===\n"
            f"Architectural Style: {e.get('architectural_style', e.get('description', ''))}\n"
            f"Environmental Features: {e.get('environmental_features', e.get('environment_details', ''))}\n"
            f"Lighting & Atmosphere: {e.get('lighting_and_atmosphere', e.get('lighting_default', ''))}\n"
            f"Constraints: {e.get('setting_constraints', '')}"
            for e in intel.environments
        )
        obj_text = "\n\n".join(
            f"=== {o.get('name', 'Object')} ===\n"
            f"Description: {o.get('visual_description', o.get('description', ''))}\n"
            f"Significance: {o.get('significance', '')}"
            for o in intel.objects_and_props
        )
        story_text = (
            f"STORY PREMISE: {intel.core_narrative_premise}\n"
            f"GENRE & TONE: {intel.genre_and_tone}\n"
            f"SETTING PERIOD: {intel.historical_or_setting_period}\n\n"
            f"SUMMARY:\n{intel.story_summary}\n\n"
            f"CHRONOLOGY:\n" + "\n".join(f"- {ev}" for ev in intel.chronological_events)
        )
    elif hasattr(analysis, "continuity") and analysis.continuity:
        cont = analysis.continuity
        char_text = "\n\n".join(
            f"=== {c.name} ===\nRole: {c.role or ''}\nDescription: {c.physical_description}\nClothing: {c.clothing or ''}"
            for c in cont.characters
        )
        env_text = "\n\n".join(
            f"=== {l.name} ===\nArchitecture: {l.architectural_style or ''}\nDetails: {l.environmental_features}\nLighting: {l.lighting_mood or ''}"
            for l in cont.locations
        )
        obj_text = "\n\n".join(
            f"=== {o.name} ===\nDescription: {o.visual_description}\nSignificance: {o.significance or ''}"
            for o in cont.key_objects
        )
        story_text = getattr(analysis, "story_summary", "")
    else:
        char_text = ""
        env_text = ""
        obj_text = ""
        story_text = str(analysis)

    for d in dirs:
        try:
            (d / "character_bible.txt").write_text(char_text or "No specific characters defined.", encoding="utf-8")
            (d / "location_bible.txt").write_text(env_text or "No specific locations defined.", encoding="utf-8")
            (d / "object_bible.txt").write_text(obj_text or "No specific objects defined.", encoding="utf-8")
            (d / "story_bible.txt").write_text(story_text or "No summary available.", encoding="utf-8")
            if intel and intel.raw_response:
                (d / "story_intelligence.json").write_text(json.dumps(intel.model_dump(), indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[Stage1] Warning saving bible files to {d}: {e}")


class Stage1StoryIntelligence:
    """
    Stage 1: Extracts comprehensive Story Intelligence dynamically from
    the script narration, timestamps, user-supplied visual notes, and presets.
    """

    @classmethod
    def execute(
        cls,
        engine: Optional[BaseInferenceEngine] = None,
        story_text: str = "",
        narration: Optional[NarrationData] = None,
        user_visual_ideas: Optional[str] = None,
        subject_preset: Optional[SubjectPreset] = None,
        custom_subject: Optional[str] = None,
        style_preset: Optional[VisualStylePreset] = None,
        custom_style: Optional[str] = None,
        project_instructions: Optional[str] = None,
        project_dir: Optional[Path] = None,
        model: str = "qwen/qwen3.8-27b"
    ) -> StoryIntelligence:
        """
        Executes dynamic story intelligence extraction.
        """
        if not story_text and narration:
            story_text = narration.text

        story_text = story_text.strip() if story_text else ""
        if not story_text:
            raise ValueError("Stage 1 Error: No script or story text provided for extraction.")

        system_prompt = load_story_bible_system_prompt()

        subj_name = subject_preset.name if subject_preset else "General Story"
        subj_instr = subject_preset.system_instructions if subject_preset else (custom_subject or "")
        style_name = style_preset.name if style_preset else "Authoritative Visual Style"
        style_instr = style_preset.system_instructions if style_preset else (custom_style or "")

        user_prompt = f"""ANALYZE THE FOLLOWING STORY SCRIPT AND EXTRACT PRODUCTION BIBLES:

### SCRIPT NARRATION:
{story_text}

### USER-SUPPLIED VISUAL IDEAS / BEATS:
{user_visual_ideas[:4000] if user_visual_ideas else 'No pre-planned visual ideas provided.'}

### PROJECT & PRESET GUIDELINES:
Subject: {subj_name}
{subj_instr}

Target Visual Style: {style_name}
{style_instr}
{f"Additional Project Instructions: {project_instructions}" if project_instructions else ""}

Extract complete production bibles strictly matching the required JSON schema.
- Dynamically extract real characters, outfits, physical traits, and consistency rules from THIS story.
- Dynamically extract environments, architecture, lighting, and environmental rules.
- Dynamically extract key props and objects.
- Establish visual continuity and visual constraints.
- Provide a punchy 2-4 word uppercase thumbnail headline and a high-CTR thumbnail prompt.
Return ONLY valid JSON.
"""

        if engine is None:
            engine = GroqInferenceEngine(default_model=model)

        raw_response = engine.generate_text(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=3500
        )

        clean_json = raw_response.strip()
        if clean_json.startswith("```"):
            clean_json = re.sub(r"^```(?:json)?\s*", "", clean_json)
            clean_json = re.sub(r"\s*```$", "", clean_json)

        parsed: Dict[str, Any] = {}
        try:
            parsed = json.loads(clean_json)
        except Exception:
            try:
                parsed = BaseInferenceEngine.repair_and_parse_json(clean_json)
            except Exception as e:
                m = re.search(r"(\{.*\})", clean_json, re.DOTALL)
                if m:
                    try:
                        parsed = json.loads(m.group(1))
                    except Exception:
                        pass
                if not parsed:
                    raise RuntimeError(f"Stage 1 Story Intelligence JSON parsing failed: {e}. Raw snippet: {clean_json[:250]}")

        # Parse thumbnail headline & fallback
        headline = parsed.get("thumbnail_headline") or parsed.get("thumbnail", {}).get("headline", "")
        if not is_valid_thumbnail_headline(headline):
            headline = extract_smart_fallback_headline(story_text)

        thumb_prompt = parsed.get("thumbnail_prompt") or parsed.get("thumbnail", {}).get("prompt", "")

        story_bible = parsed.get("story_bible", {})
        characters = parsed.get("characters") or parsed.get("character_bible", [])
        environments = parsed.get("environments") or parsed.get("environment_bible", []) or parsed.get("locations", [])
        objects = parsed.get("objects_and_props") or parsed.get("props", []) or parsed.get("key_objects", [])
        visual_style_bible = parsed.get("visual_style_bible", {})
        continuity_rules = parsed.get("visual_continuity_rules") or parsed.get("continuity_rules", [])
        constraints = parsed.get("visual_constraints", {})
        beats = parsed.get("narrative_beats", [])

        # Ensure characters is a list of dicts
        if isinstance(characters, dict):
            characters = [v if isinstance(v, dict) else {"name": k, "description": str(v)} for k, v in characters.items()]
        if isinstance(environments, dict):
            environments = [v if isinstance(v, dict) else {"name": k, "description": str(v)} for k, v in environments.items()]
        if isinstance(objects, dict):
            objects = [v if isinstance(v, dict) else {"name": k, "description": str(v)} for k, v in objects.items()]

        intel = StoryIntelligence(
            story_summary=story_bible.get("summary") or parsed.get("story_summary", story_text[:300]),
            core_narrative_premise=story_bible.get("premise") or parsed.get("core_narrative_premise", ""),
            genre_and_tone=story_bible.get("genre_and_tone") or parsed.get("genre_and_tone", "Dramatic Cinematic"),
            historical_or_setting_period=story_bible.get("setting_period") or parsed.get("historical_or_setting_period", "Present"),
            chronological_events=story_bible.get("chronological_events") or parsed.get("chronological_events", []),
            cause_and_effect_flow=story_bible.get("cause_and_effect_flow") or parsed.get("cause_and_effect_flow", []),
            characters=characters,
            environments=environments,
            objects_and_props=objects,
            visual_style_bible=visual_style_bible,
            visual_continuity_rules=continuity_rules,
            visual_constraints=constraints,
            narrative_beats=beats,
            thumbnail_headline=headline,
            thumbnail_prompt=thumb_prompt,
            raw_response=parsed
        )

        if project_dir:
            save_story_bibles(Path(project_dir), intel)

        return intel

    @classmethod
    def to_script_analysis(cls, analysis: Any, story_text: str = "") -> ScriptAnalysis:
        """Compatibility bridge returning ScriptAnalysis."""
        if isinstance(analysis, StoryIntelligence):
            return analysis.to_script_analysis(story_text)
        if hasattr(analysis, "to_script_analysis"):
            return analysis.to_script_analysis()
        if isinstance(analysis, ScriptAnalysis):
            return analysis
        # Fallback empty
        return StoryIntelligence(story_summary=str(analysis)).to_script_analysis(story_text)


# Backwards compatibility alias for code that imported Stage1Analyzer
Stage1Analyzer = Stage1StoryIntelligence

