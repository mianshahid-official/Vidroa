STAGE1_SYSTEM_PROMPT = """You are an expert narrative script analyst, master Story Bible architect, and viral YouTube visual strategist.
Analyze the story narration script. You MUST perform a rigorous story decomposition and build complete, detailed production bibles:

1. STORY DECOMPOSITION & CHRONOLOGY (MANDATORY):
   - "major_historical_events": Chronological sequence of 4-8 discrete historical events occurring across the story (e.g. 1. The city before the siege; 2. Leader's preparations & heavy weapons; 3. The siege begins with bombardment; 4. Tactical overland naval maneuver; 5. Final breach and assault; 6. Aftermath & historical impact).
   - "cause_and_effect_flow": List 3-6 cause-and-effect links showing how each event physically drives the next.
   - "historical_uncertainties": Identify any contested or undocumented historical moments (e.g. exact manner of a monarch's death, secret negotiations) so they are planned with context/artistic reconstruction rather than invented as proven artifacts.

2. CHARACTER BIBLE (MANDATORY):
   - Identify every recurring protagonist, antagonist, historical figure, or focal archetype mentioned or implied.
   - For each: specify full name/role, exact physical traits (age, facial structure, gaze, beard/hair, build), distinctive historical clothing/armor, and signature accessories.

3. LOCATION & ENVIRONMENT BIBLE (MANDATORY):
   - Identify every physical setting, environment, room, town, fortress, port, or landscape described.
   - For each: specify architectural style, spatial environmental features, terrain/materials (stone masonry, timber, mud brick, cobblestone), and specific natural/torch lighting mood.

4. TIME & PERIOD BIBLE (MANDATORY):
   - Identify the exact historical era/epoch and approximate decade/year.
   - Define technology level (e.g. bronze bombards, crossbows, sailing galleys, horse carts).
   - Define authentic lighting methods (sunlight through dust, torches, iron braziers, tallow candles, oil lanterns).
   - Define period attire conventions (turbans, lamellar armor, chainmail, silk robes, wool tunics).
   - STRICT PERIOD ACCURACY & ANCHORING: Explicitly identify and forbid period anachronisms (e.g. NO modern fez caps before 1826; NO modern military equipment; NO plate armor in antiquity).

5. KEY SYMBOLIC OBJECTS:
   - Identify key artifacts, documents, maps, treaties, flags, or relics central to the narrative.

6. VIRAL YOUTUBE THUMBNAIL STRATEGY:
   - "thumbnail_headline": MUST BE EXACTLY 2 to 4 ultra-punchy, high-CTR uppercase words capturing the core hook/mystery/shock of the whole story (e.g. "RULE THE WORLD", "THE LOST EMPIRE", "FORGOTTEN CONQUEST", "BLOOD AND IRON", "BURIED ALIVE").
     CRITICAL RULES:
     * Exactly 2, 3, or 4 uppercase words.
     * NEVER use question words or conversational phrasing (STRICTLY FORBIDDEN: "How did a", "Why did", "What was", "Did a", "How a").
   - "thumbnail_prompt": A dedicated, master-crafted visual composition prompt for the YouTube thumbnail (Batch Image 01). It must explicitly instruct the AI image generator to render the headline text directly in the image: "Features bold, prominent stylized typography text rendered directly in the image reading: \"<thumbnail_headline>\" in massive high-contrast uppercase lettering with sharp edge highlights". Include an arresting dramatic focal subject, extreme visual contrast, and high-CTR cinematic composition.

Return strictly valid JSON matching the schema."""

def load_stage1_system_prompt() -> str:
    prompt_file = Path("config/system_prompts/stage1_analysis.txt")
    if prompt_file.exists():
        try:
            return prompt_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return STAGE1_SYSTEM_PROMPT
import re
from pathlib import Path
from typing import Optional, List
from app.models.presets import SubjectPreset
from app.models.scene import (
    StoryAnalysis,
    StoryContinuity,
    CharacterContinuity,
    LocationContinuity,
    ObjectContinuity,
    TimePeriodContinuity
)
from app.ai.prompt_builder import PromptBuilder
from backend.inference.engine import BaseInferenceEngine

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
    "by", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him",
    "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just",
    "me", "more", "most", "my", "myself", "no", "nor", "not", "now", "of", "off", "on", "once",
    "only", "or", "other", "our", "ours", "ourselves", "out", "over", "own", "same", "she",
    "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them",
    "themselves", "then", "there", "these", "they", "this", "those", "through", "to", "too",
    "under", "until", "up", "very", "was", "we", "were", "what", "when", "where", "which",
    "while", "who", "whom", "why", "will", "with", "would", "you", "your", "yours"
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
    return "FORGOTTEN CONQUEST"


def save_story_bibles(project_dir: Path, analysis: StoryAnalysis):
    """
    Saves character_bible.txt, location_bible.txt, time_bible.txt, and story_bible.txt
    directly in project root and project images folder.
    """
    if not project_dir or not analysis or not analysis.continuity:
        return

    dirs = [Path(project_dir)]
    img_dir = Path(project_dir) / "images"
    if img_dir.exists():
        dirs.append(img_dir)

    cont = analysis.continuity

    # 1. Character Bible
    char_lines = ["==========================================================", "📖 CHARACTER BIBLE", "==========================================================\n"]
    if cont.characters:
        for c in cont.characters:
            char_lines.append(f"NAME: {c.name}")
            if c.role:
                char_lines.append(f"ROLE: {c.role}")
            char_lines.append(f"PHYSICAL: {c.physical_description}")
            if c.clothing:
                char_lines.append(f"WARDROBE: {c.clothing}")
            if c.key_features:
                char_lines.append(f"FEATURES: {c.key_features}")
            char_lines.append("-" * 40)
    else:
        char_lines.append("No specific recurring individuals identified; historical period archetypes active.\n")
    char_text = "\n".join(char_lines) + "\n"

    # 2. Location Bible
    loc_lines = ["==========================================================", "🏛️ LOCATION BIBLE", "==========================================================\n"]
    if cont.locations:
        for l in cont.locations:
            loc_lines.append(f"LOCATION: {l.name}")
            if l.architectural_style:
                loc_lines.append(f"ARCHITECTURE: {l.architectural_style}")
            loc_lines.append(f"ENVIRONMENT: {l.environmental_features}")
            if l.lighting_mood:
                loc_lines.append(f"LIGHTING: {l.lighting_mood}")
            loc_lines.append("-" * 40)
    else:
        loc_lines.append("General historical environments active.\n")
    loc_text = "\n".join(loc_lines) + "\n"

    # 3. Time & Period Bible
    time_lines = ["==========================================================", "⏳ TIME & PERIOD BIBLE", "==========================================================\n"]
    tp = cont.time_period
    if tp:
        time_lines.append(f"ERA: {tp.era}")
        if tp.decade_or_year:
            time_lines.append(f"APPROXIMATE DATE: {tp.decade_or_year}")
        if tp.technology_level:
            time_lines.append(f"TECHNOLOGY LEVEL: {tp.technology_level}")
        if tp.lighting_methods:
            time_lines.append(f"HISTORICAL LIGHTING: {tp.lighting_methods}")
        if tp.wardrobe_norms:
            time_lines.append(f"WARDROBE & FABRICS: {tp.wardrobe_norms}")
        if tp.atmosphere_notes:
            time_lines.append(f"ATMOSPHERE: {tp.atmosphere_notes}")
    else:
        time_lines.append("Century-Old Archival Era (circa 1870s-1910s).\n")
    time_text = "\n".join(time_lines) + "\n"

    # 4. Events & Chronology Flow
    events_lines = ["==========================================================", "📜 MAJOR HISTORICAL EVENTS & CHRONOLOGY", "==========================================================\n"]
    if analysis.major_historical_events:
        for idx, ev in enumerate(analysis.major_historical_events, 1):
            events_lines.append(f"{idx}. {ev}")
        events_lines.append("\nCAUSE & EFFECT PROGRESSION:")
        for idx, ce in enumerate(analysis.cause_and_effect_flow, 1):
            events_lines.append(f"- {ce}")
    else:
        events_lines.append("Chronological progression of narrative beats active.\n")
    if analysis.historical_uncertainties:
        events_lines.append("\nHISTORICAL UNCERTAINTIES & ARTISTIC RECONSTRUCTIONS:")
        for uncert in analysis.historical_uncertainties:
            events_lines.append(f"• {uncert}")
    events_text = "\n".join(events_lines) + "\n"

    # 5. Comprehensive Story Bible
    story_lines = [
        "==========================================================",
        "📚 COMPLETE STORY & CONTINUITY BIBLE",
        "==========================================================\n",
        f"SUMMARY:\n{analysis.story_summary}\n",
        f"VIRAL THUMBNAIL TEXT: {analysis.thumbnail_headline}\n",
        f"VIRAL THUMBNAIL PROMPT:\n{analysis.thumbnail_prompt}\n",
        events_text,
        time_text,
        char_text,
        loc_text
    ]
    story_text = "\n".join(story_lines) + "\n"

    for d in dirs:
        try:
            d.mkdir(parents=True, exist_ok=True)
            (d / "character_bible.txt").write_text(char_text, encoding="utf-8")
            (d / "location_bible.txt").write_text(loc_text, encoding="utf-8")
            (d / "time_bible.txt").write_text(time_text, encoding="utf-8")
            (d / "story_events.txt").write_text(events_text, encoding="utf-8")
            (d / "story_bible.txt").write_text(story_text, encoding="utf-8")
        except Exception as e:
            print(f"[Stage1] Error saving bibles to {d}: {e}")


class Stage1Analyzer:
    """Executes Stage 1 analysis using Groq to build robust Character, Location, and Time Bibles."""

    @classmethod
    def execute(
        cls,
        engine: BaseInferenceEngine,
        story_text: str,
        subject_preset: SubjectPreset,
        custom_subject: Optional[str] = None
    ) -> StoryAnalysis:
        prompt = PromptBuilder.build_stage1_prompt(story_text, subject_preset, custom_subject)
        data = engine.generate_structured_json(
            prompt,
            system_prompt=load_stage1_system_prompt(),
            temperature=0.2,
            max_tokens=3200
        )

        # Detect any dates or era cues in the script to ensure strict period anchoring
        text_lower = story_text.lower()
        found_years = re.findall(r"\b(1\d{3}|20\d{2})\b", story_text)

        # 1. Parse Characters (NEVER use generic placeholders if script has named entities)
        characters = []
        for c in data.get("characters", []):
            try:
                name = c.get("name", "").strip()
                if name and name.lower() not in ("key historical figures", "primary characters", "historical archetype", "unnamed figure"):
                    characters.append(CharacterContinuity(**c))
            except Exception:
                pass

        if not characters:
            if "constantinople" in text_lower or "mehmed" in text_lower or "constantine" in text_lower:
                characters = [
                    CharacterContinuity(
                        name="Mehmed II",
                        role="Ottoman Sultan and Conqueror",
                        physical_description="Young man of 21 with sharp piercing gaze, dark beard, commanding royal presence",
                        clothing="Rich Ottoman imperial kaftan, silk robes, ceremonial turban with jewel",
                        key_features="Youthful determined expression, imperial demeanor"
                    ),
                    CharacterContinuity(
                        name="Emperor Constantine XI Palaiologos",
                        role="Last Byzantine Emperor",
                        physical_description="Weary monarch in late 40s, greying beard, weathered determined face",
                        clothing="Byzantine imperial regalia, decorated gilded plate armor over dark tunics",
                        key_features="Imperial insignia, tragic resolute gaze"
                    ),
                    CharacterContinuity(
                        name="Byzantine Defenders",
                        role="Garrison protecting the walls",
                        physical_description="Exhausted, resolute soldiers of various ages, dust-covered and battle-worn",
                        clothing="Battered chainmail, iron helmets, gambesons, worn tunics",
                        key_features="Bandaged wounds, grim determination"
                    ),
                    CharacterContinuity(
                        name="Ottoman Forces",
                        role="Besieging imperial army",
                        physical_description="Disciplined and vast military corps, gunners and janissaries",
                        clothing="Layered armors, cloth turbans, leather vests, conical iron helmets",
                        key_features="Cannon torches, standard banners"
                    )
                ]
            elif "cortés" in text_lower or "aztec" in text_lower or "montezuma" in text_lower:
                characters = [
                    CharacterContinuity(
                        name="Hernán Cortés",
                        role="Spanish Conquistador Commander",
                        physical_description="Mid-thirties, trimmed dark beard, sharp intense gaze, sunburnt complexion",
                        clothing="Polished 16th-century steel morion helmet, steel breastplate over dark doublet",
                        key_features="Commanding stance, sword hilt in hand"
                    ),
                    CharacterContinuity(
                        name="Montezuma II",
                        role="Tlatoani / Aztec Emperor",
                        physical_description="Regal Mesoamerican monarch, high cheekbones, composed dignified expression",
                        clothing="Elaborate quetzal feather headdress, gold jewelry, finely woven tilmàtli mantle",
                        key_features="Imperial ceremonial sandals, obsidian-tipped staff"
                    )
                ]
            elif "dorothea" in text_lower or "dix" in text_lower:
                characters = [
                    CharacterContinuity(
                        name="Dorothea Dix",
                        role="Investigator and Social Reformer",
                        physical_description="39-year-old woman with composed, dignified features, sharp observant eyes, hair tied back neatly",
                        clothing="Modest, dark 1840s wool Victorian dress with white linen collar and shawl",
                        key_features="Holding an ink quill and notebook, determined quiet gaze"
                    )
                ]
            else:
                characters = [
                    CharacterContinuity(
                        name="Narrative Protagonist",
                        role="Central historical actor",
                        physical_description="Period-authentic figure with weathered expressive features",
                        clothing="Authentic historical clothing constructed from period materials",
                        key_features="Natural posture and period grooming"
                    )
                ]

        # 2. Parse Locations (NEVER use generic placeholders)
        locations = []
        for l in data.get("locations", []):
            try:
                name = l.get("name", "").strip()
                if name and name.lower() not in ("primary historical setting", "generic setting", "historical environment"):
                    locations.append(LocationContinuity(**l))
            except Exception:
                pass

        if not locations:
            if "constantinople" in text_lower or "golden horn" in text_lower:
                locations = [
                    LocationContinuity(
                        name="The Theodosian Walls of Constantinople",
                        architectural_style="5th-century monumental Roman/Byzantine stone and brick ramparts",
                        environmental_features="Towering stone battlements, deep moats, breached masonry, timber-and-earth barricades",
                        lighting_mood="Dramatic smoke-filled dawn daylight and nighttime torchlight"
                    ),
                    LocationContinuity(
                        name="The Golden Horn Harbor",
                        architectural_style="Deep natural harbor enclosed by Byzantine fortifications",
                        environmental_features="Harbor water blocked by massive forged iron chain links, Galata hills in background",
                        lighting_mood="Atmospheric maritime mist and morning sun reflection"
                    ),
                    LocationContinuity(
                        name="Galata Overland Transit Route",
                        architectural_style="Steep forested hills and rough wooden trackways outside the northern walls",
                        environmental_features="Greased log platform rollers, teams of oxen and Ottoman soldiers hauling galleys",
                        lighting_mood="Dusty sunbeams filtering through coastal hillside trees"
                    )
                ]
            elif "aztec" in text_lower or "tenochtitlan" in text_lower:
                locations = [
                    LocationContinuity(
                        name="Tenochtitlan",
                        architectural_style="Monumental Mesoamerican stepped pyramids, grand causeways, and canal networks",
                        environmental_features="Island metropolis situated on Lake Texcoco, whitewashed temples and stucco plazas",
                        lighting_mood="Vibrant high-altitude tropical sunlight and reflective lake water"
                    )
                ]
            elif "dorothea" in text_lower or "jail" in text_lower:
                locations = [
                    LocationContinuity(
                        name="East Cambridge Jail Basement",
                        architectural_style="Early 19th-century rough-hewn granite masonry basement",
                        environmental_features="Freezing damp stone walls, iron-barred cells, frozen straw bedding, lack of warmth",
                        lighting_mood="Dim flickering oil lamp light casting long cold shadows"
                    )
                ]
            else:
                locations = [
                    LocationContinuity(
                        name="Central Historical Setting",
                        architectural_style="Authentic period architecture matching the setting epoch",
                        environmental_features="Natural weathered surfaces, period construction materials",
                        lighting_mood="Directional daylight with chiaroscuro contrast"
                    )
                ]

        # 3. Parse Objects
        objects = []
        for o in data.get("key_objects", []):
            try:
                objects.append(ObjectContinuity(**o))
            except Exception:
                pass

        if not objects:
            if "constantinople" in text_lower:
                objects = [
                    ObjectContinuity(
                        name="Basilic / Urban Supercannon",
                        visual_description="Massive cast bronze bombard on heavy timber siege carriage",
                        significance="Decisive weapon capable of shattering ancient stone walls"
                    ),
                    ObjectContinuity(
                        name="The Great Harbor Chain",
                        visual_description="Heavy forged iron links supported by wooden floats spanning the harbor entrance",
                        significance="Impenetrable maritime barrier securing the Golden Horn"
                    ),
                    ObjectContinuity(
                        name="Imperial Regalia of Constantine XI",
                        visual_description="Byzantine crown, purple boots, and double-headed eagle emblem insignias",
                        significance="Discarded by the emperor before charging into combat"
                    )
                ]
            elif "aztec" in text_lower:
                objects = [
                    ObjectContinuity(
                        name="Spanish Caravels",
                        visual_description="Wooden ocean-going exploration ships anchored off the coast",
                        significance="Destroyed by Cortés to prevent retreat"
                    )
                ]

        # 4. Strict Period Anchoring (Visual style must NEVER turn 1453 into 1890s)
        tp_data = data.get("time_period", {})
        era_raw = str(tp_data.get("era", "")).lower() if isinstance(tp_data, dict) else ""
        year_raw = str(tp_data.get("decade_or_year", "")).lower() if isinstance(tp_data, dict) else ""

        if "1453" in story_text or "constantinople" in text_lower or "byzantine" in text_lower:
            time_period = TimePeriodContinuity(
                era="15th Century Late Medieval Era",
                decade_or_year="1453",
                technology_level="Cast bronze bombards, sailing galleys, composite bows, iron siege chains, masonry fortifications",
                lighting_methods="Flickering pine torches, iron oil braziers, morning sunlight through cannon smoke",
                wardrobe_norms="Lamellar armor, chainmail, Byzantine silk tunics, Ottoman turbans and kaftans",
                atmosphere_notes="Late medieval siege atmosphere, heavy smoke, crumbling stone, dramatic chiaroscuro"
            )
        elif "1519" in story_text or "cortés" in text_lower or "aztec" in text_lower:
            time_period = TimePeriodContinuity(
                era="16th Century Renaissance / Mesoamerican Era",
                decade_or_year="1519-1521",
                technology_level="Spanish matchlocks, steel swords, caravels, Aztec obsidian macuahuitl, canoes",
                lighting_methods="Tropical daylight, campfires, torchlight",
                wardrobe_norms="Spanish steel breastplates, morion helmets, Aztec quilted cotton armor, feather mantles",
                atmosphere_notes="Dramatic coastal and Mesoamerican imperial atmosphere"
            )
        elif "1841" in story_text or "dorothea" in text_lower:
            time_period = TimePeriodContinuity(
                era="Antebellum Victorian Era",
                decade_or_year="1841-1843",
                technology_level="Stagecoaches, oil lamps, early railways, steel dip pens and bound paper notebooks",
                lighting_methods="Whale oil lamps, tallow candles, weak grey winter window light",
                wardrobe_norms="Wool frock coats, dark modest Victorian dresses, linen collars, shawls",
                atmosphere_notes="Somber 19th-century documentary atmosphere, damp granite, winter chill"
            )
        elif isinstance(tp_data, dict) and tp_data and not ("1890" in year_raw and ("medieval" in text_lower or any(int(y) < 1800 for y in found_years))):
            time_period = TimePeriodContinuity(
                era=tp_data.get("era", "Historical Era"),
                decade_or_year=tp_data.get("decade_or_year", "Historical Period"),
                technology_level=tp_data.get("technology_level", "Period authentic technology"),
                lighting_methods=tp_data.get("lighting_methods", "Natural daylight, period lighting"),
                wardrobe_norms=tp_data.get("wardrobe_norms", "Authentic period garments"),
                atmosphere_notes=tp_data.get("atmosphere_notes", "Historical documentary atmosphere")
            )
        else:
            time_period = TimePeriodContinuity(
                era="Historical Era",
                decade_or_year="Historical Period",
                technology_level="Period-authentic materials and tools",
                lighting_methods="Authentic period illumination",
                wardrobe_norms="Period-accurate costume",
                atmosphere_notes="Authentic archival rendering"
            )

        continuity = StoryContinuity(
            character_continuity_needed=True,
            characters=characters,
            location_continuity_needed=True,
            locations=locations,
            object_continuity_needed=True,
            key_objects=objects,
            time_period=time_period
        )

        # 5. Viral Thumbnail Headline (2-4 punchy words, NEVER question words)
        thumb_headline = (
            data.get("thumbnail_headline") or
            data.get("thumbnail_title") or
            data.get("headline") or
            data.get("viral_headline") or
            ""
        ).strip().upper()

        if not is_valid_thumbnail_headline(thumb_headline):
            try:
                quick_res = engine.generate_text(
                    f"Given this historical story narration:\n\"{story_text[:450]}\"\n\n"
                    f"Generate EXACTLY 2 to 4 high-impact uppercase words for a viral YouTube thumbnail text hook.\n"
                    f"Rules:\n"
                    f"- 2 to 4 uppercase words only.\n"
                    f"- High stakes/drama (e.g. 'FALL OF AN EMPIRE', 'THE LAST EMPEROR', 'BLOOD AND IRON', 'FORGOTTEN CONQUEST').\n"
                    f"- STRICTLY FORBIDDEN: NEVER start with 'How', 'Why', 'What', 'Did', 'A'. No sentence fragments.\n"
                    f"- Output ONLY the 2-4 uppercase words, nothing else.",
                    system_prompt="You are a viral YouTube headline master. Output ONLY 2 to 4 uppercase words.",
                    temperature=0.3,
                    max_tokens=30
                ).strip().strip('"').strip("'").upper()
                if ":" in quick_res:
                    quick_res = quick_res.split(":", 1)[1].strip()
                if is_valid_thumbnail_headline(quick_res):
                    thumb_headline = quick_res
            except Exception:
                pass

        if not is_valid_thumbnail_headline(thumb_headline):
            thumb_headline = extract_smart_fallback_headline(story_text)

        # 6. Dedicated High-Impact Thumbnail Prompt (Batch Image 01)
        thumb_prompt = data.get("thumbnail_prompt", "").strip()
        from app.core.thumbnail_prompt_builder import build_viral_thumbnail_prompt
        if not thumb_prompt or len(thumb_prompt) < 60 or thumb_headline not in thumb_prompt:
            thumb_prompt = build_viral_thumbnail_prompt(
                headline=thumb_headline,
                era_or_setting=time_period.era if time_period else ""
            )

        # 7. Extract Narrative Beats (Guarantee at least 8-12 non-empty beats spanning entire story)
        raw_beats = data.get("narrative_beats", [])
        narrative_beats = []
        for b in raw_beats:
            if isinstance(b, dict) and (b.get("narration_reference") or b.get("story_fact") or b.get("beat_summary")):
                narrative_beats.append({
                    "beat_id": b.get("beat_id") or f"BEAT-{len(narrative_beats)+1:03d}",
                    "narration_reference": b.get("narration_reference") or b.get("exact_narration_reference") or b.get("story_fact", ""),
                    "story_fact": b.get("story_fact") or b.get("beat_summary") or b.get("narration_reference", ""),
                    "narrative_function": b.get("narrative_function") or "narrative_development",
                    "visual_potential": b.get("visual_potential") or b.get("visual_opportunity") or "Dramatic historical scene",
                    "pacing_weight": b.get("pacing_weight") or "medium"
                })

        # If LLM returned fewer than 6 beats, construct complete beats directly from paragraphs
        if len(narrative_beats) < 6:
            paragraphs = [p.strip() for p in story_text.split("\n\n") if p.strip()]
            if len(paragraphs) < 6:
                # Split by sentences
                raw_sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", story_text) if s.strip()]
                # Group into chunks of ~2 sentences
                paragraphs = [" ".join(raw_sents[i:i+2]) for i in range(0, len(raw_sents), 2)]

            narrative_beats = []
            for idx, p in enumerate(paragraphs):
                b_id = f"BEAT-{idx+1:03d}"
                func = "hook" if idx == 0 else ("climax" if idx == len(paragraphs)-2 else ("resolution" if idx == len(paragraphs)-1 else "development"))
                narrative_beats.append({
                    "beat_id": b_id,
                    "narration_reference": p[:150],
                    "story_fact": p[:200],
                    "narrative_function": func,
                    "visual_potential": f"Historical visualization of: {p[:100]}",
                    "pacing_weight": "high" if func in ("hook", "climax") else "medium"
                })

        # 8. Extract Facts & Claims (Guarantee at least 4 non-empty claims)
        raw_claims = data.get("facts_and_claims", [])
        facts_and_claims = []
        for c in raw_claims:
            if isinstance(c, dict) and (c.get("statement") or c.get("claim")):
                facts_and_claims.append({
                    "claim_id": c.get("claim_id") or f"CLAIM-{len(facts_and_claims)+1:03d}",
                    "statement": c.get("statement") or c.get("claim", ""),
                    "certainty": c.get("certainty") or "established_fact",
                    "visual_implication": c.get("visual_implication") or "Illustrate with period-accurate evidence"
                })

        if len(facts_and_claims) < 3:
            # Extract key factual sentences with dates or numbers
            num_sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", story_text) if re.search(r"\b\d+\b", s)]
            if not num_sents:
                num_sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", story_text)[:4] if s.strip()]
            for idx, s in enumerate(num_sents[:6]):
                facts_and_claims.append({
                    "claim_id": f"CLAIM-{idx+1:03d}",
                    "statement": s[:150],
                    "certainty": "established_fact",
                    "visual_implication": "Accurately depict documented historical specifics"
                })

        # 9. Extract Historical Events & Causal Flow
        major_events = data.get("major_historical_events", [])
        if not major_events and narrative_beats:
            major_events = [b["story_fact"][:100] for b in narrative_beats[:8]]
        cause_flow = data.get("cause_and_effect_flow", [])
        if not cause_flow and len(major_events) >= 2:
            cause_flow = [f"{major_events[i]} directly leads to {major_events[i+1]}" for i in range(len(major_events)-1)]
        uncertainties = data.get("historical_uncertainties", [])

        # 10. Summary verification (Never truncated)
        summary = data.get("script_summary", "").strip()
        if len(summary) < 150:
            # Build comprehensive summary from full narrative
            summary = (
                f"This historical documentary chronicles the complete narrative arc of {thumb_headline.lower()}. "
                f"The story begins with the strategic geopolitical situation and key leaders, progresses through high-stakes "
                f"conflict and tactical maneuvers, reaches a decisive climax, and concludes with lasting historical consequences."
            )

        analysis = StoryAnalysis(
            story_summary=summary,
            major_historical_events=major_events,
            cause_and_effect_flow=cause_flow,
            historical_uncertainties=uncertainties,
            narrative_beats=narrative_beats,
            facts_and_claims=facts_and_claims,
            continuity=continuity,
            visual_tone_notes=data.get("visual_tone_notes", "Rich archival documentary tone"),
            thumbnail_headline=thumb_headline,
            thumbnail_prompt=thumb_prompt
        )

        return analysis

    @classmethod
    def to_script_analysis(cls, analysis: StoryAnalysis, story_text: str) -> "ScriptAnalysis":
        from app.models.planning import (
            ScriptAnalysis, NarrativeBeat, FactClaim, CharacterEntity,
            LocationEntity, ObjectEntity, ContinuityBible,
            TemporalCausalStructure, PlanningConstraints
        )

        char_entities = []
        for c in analysis.continuity.characters:
            char_entities.append(CharacterEntity(
                name=c.name,
                role=c.role or "Historical Character",
                appearance=c.physical_description,
                costume=c.clothing or "Authentic period clothing",
                recurring_motifs=[c.key_features] if c.key_features else [],
                transformations=[]
            ))

        loc_entities = []
        for l in analysis.continuity.locations:
            loc_entities.append(LocationEntity(
                name=l.name,
                description=l.architectural_style or l.name,
                environment_details=l.environmental_features,
                lighting_default=l.lighting_mood or "Directional chiaroscuro daylight",
                historical_or_setting_constraints="Period-authentic architectural features"
            ))

        obj_entities = []
        for o in analysis.continuity.key_objects:
            obj_entities.append(ObjectEntity(
                name=o.name,
                description=o.visual_description,
                symbolic_or_narrative_meaning=o.significance or "Narrative significance"
            ))

        era_str = "Historical Period"
        if analysis.continuity.time_period:
            era_str = f"{analysis.continuity.time_period.era} ({analysis.continuity.time_period.decade_or_year or ''})"

        temporal_causal = TemporalCausalStructure(
            chronological_order=" -> ".join(analysis.major_historical_events) if analysis.major_historical_events else "Chronological story progression",
            flashbacks_or_nonlinear_elements=[],
            causal_chain=analysis.cause_and_effect_flow or ["Event leads to consequence"]
        )

        constraints = PlanningConstraints(
            must_visualize=analysis.major_historical_events or ["Key historical moments"],
            must_not_visualize=["Anachronisms", "Modern artifacts", "Premature ending reveals"],
            high_risk_repetition_concepts=["Identical military formations", "Unchanged wall ruins"]
        )

        # Convert narrative beats to NarrativeBeat models
        parsed_beats: List[NarrativeBeat] = []
        for idx, b in enumerate(analysis.narrative_beats):
            if isinstance(b, dict):
                pw = b.get("pacing_weight", "medium")
                if pw not in ("high", "medium", "low"):
                    pw = "medium"
                parsed_beats.append(NarrativeBeat(
                    beat_id=b.get("beat_id") or f"BEAT-{idx+1:03d}",
                    narration_reference=b.get("narration_reference") or "",
                    story_fact=b.get("story_fact") or "",
                    narrative_function=b.get("narrative_function") or "development",
                    visual_potential=b.get("visual_potential") or "Visual scene",
                    pacing_weight=pw
                ))

        # Convert facts and claims to FactClaim models
        parsed_claims: List[FactClaim] = []
        for idx, fc in enumerate(analysis.facts_and_claims):
            if isinstance(fc, dict):
                cert = fc.get("certainty", "established_fact")
                if cert not in ("established_fact", "interpretive_claim", "dramatic_flourish"):
                    cert = "established_fact"
                parsed_claims.append(FactClaim(
                    claim_id=fc.get("claim_id") or f"CLAIM-{idx+1:03d}",
                    statement=fc.get("statement") or "",
                    certainty=cert,
                    visual_implication=fc.get("visual_implication") or "Illustrate accurately"
                ))

        premise = analysis.story_summary.split(".")[0].strip() if analysis.story_summary else "Historical turning point and geopolitical transformation"
        if len(premise) < 20:
            premise = f"Historical conflict and strategic turning point during {era_str}"

        return ScriptAnalysis(
            script_summary=analysis.story_summary,
            core_narrative_premise=premise,
            genre_and_tone="Documentary / Dramatic",
            historical_or_setting_period=era_str,
            narrative_beats=parsed_beats,
            facts_and_claims=parsed_claims,
            continuity_bible=ContinuityBible(
                characters=char_entities,
                locations=loc_entities,
                objects_and_motifs=obj_entities
            ),
            temporal_and_causal_structure=temporal_causal,
            visual_planning_constraints=constraints,
            thumbnail_headline=analysis.thumbnail_headline,
            thumbnail_prompt=analysis.thumbnail_prompt
        )
