"""
Script to generate all 21 subject presets for Vidroa.
Visual style presets in config/visual_styles/ are maintained directly alongside config/ai_prompts/.
"""
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SUBJECTS_DIR = BASE_DIR / "config" / "subjects"

SUBJECTS = [
    {
        "id": "history",
        "name": "History",
        "category": "Historical & Documentary",
        "description": "Historical accuracy, period-appropriate environments, clothing, tools, and social context.",
        "system_instructions": "Focus strictly on historical accuracy, period-appropriate environments, architecture, clothing, hairstyles, tools, transportation, social context, geography, and material culture. Do not introduce modern or anachronistic objects unless explicitly commanded. Emphasize physical realism and cultural authenticity appropriate to the era."
    },
    {
        "id": "historical_documentary",
        "name": "Historical Documentary",
        "category": "Historical & Documentary",
        "description": "Evidence-oriented, archival realism and authentic archival reconstructions.",
        "system_instructions": "Favor informative visual storytelling, realistic historical environments, artifact and evidence-oriented imagery, and museum-grade documentary framing. Capture genuine historical texture, architectural ruins, primary documents, and authentic reenactments without Hollywood melodrama."
    },
    {
        "id": "general_documentary",
        "name": "General Documentary",
        "category": "Historical & Documentary",
        "description": "Informative visual storytelling, realistic environments, and clear visual communication.",
        "system_instructions": "Prioritize informative visual storytelling, authentic real-world environments, photojournalistic compositions, and clear visual communication. Capture unvarnished reality, natural lighting, and candid moments that explain and validate the narration."
    },
    {
        "id": "educational_explainer",
        "name": "Educational Explainer",
        "category": "Explainer & Conceptual",
        "description": "Immediate comprehension, visual clarity, uncluttered composition, and direct concept representation.",
        "system_instructions": "Prioritize immediate viewer comprehension, visual simplicity, focal clarity, uncluttered compositions, and direct pictorial representation of concepts. Minimize background noise and extraneous details so the core educational concept is unmistakable within milliseconds."
    },
    {
        "id": "finance",
        "name": "Finance",
        "category": "Explainer & Conceptual",
        "description": "Clear visual metaphors for money flows, financial institutions, banking, and market dynamics.",
        "system_instructions": "Prioritize powerful, intuitive visual metaphors for financial systems, capital flows, banking halls, trading desks, stock tickers, ledgers, currency, and economic transactions. Turn abstract balance sheets and financial events into dynamic, concrete visual scenes."
    },
    {
        "id": "economics",
        "name": "Economics",
        "category": "Explainer & Conceptual",
        "description": "Macro and microeconomic concepts, supply chains, trade, labor, and market forces.",
        "system_instructions": "Translate economic theories, supply-and-demand dynamics, global trade routes, container shipping, factory floors, labor forces, inflation impacts, and resource scarcity into lucid, visually compelling environments and intuitive metaphorical compositions."
    },
    {
        "id": "science",
        "name": "Science",
        "category": "Explainer & Conceptual",
        "description": "Scientific phenomena, laboratories, microscopic details, cosmos, and physical laws.",
        "system_instructions": "Depict scientific accuracy, research environments, clean laboratory equipment, natural phenomena, cellular and molecular structures, astronomical bodies, and physical mechanics. Highlight clear cause-and-effect relationships and empirical beauty."
    },
    {
        "id": "technology",
        "name": "Technology",
        "category": "Explainer & Conceptual",
        "description": "Hardware, computing systems, software architectures, robotics, and digital infrastructure.",
        "system_instructions": "Focus on high-tech engineering, server architecture, circuit boards, microchips, data centers, robotics, fiber optics, cleanroom environments, and sleek user interfaces. Convey cutting-edge precision and technological scale."
    },
    {
        "id": "biography",
        "name": "Biography",
        "category": "Narrative & People",
        "description": "Intimate human portraits, personal milestones, psychological depth, and lived environments.",
        "system_instructions": "Emphasize character-driven visual storytelling, expressive human portraits, personal workshops, writing desks, intimate pivotal moments, and the evolving physical appearance of historical figures throughout their lifespan."
    },
    {
        "id": "politics",
        "name": "Politics",
        "category": "Narrative & People",
        "description": "Government institutions, legislative chambers, rallies, diplomacy, and political negotiations.",
        "system_instructions": "Capture political tension, parliament/congressional chambers, press conferences, treaty signings, diplomatic halls, campaign crowds, state banquets, and smoke-filled backrooms with dynamic framing and psychological gravitas."
    },
    {
        "id": "geography",
        "name": "Geography",
        "category": "World & Nature",
        "description": "Topographical landscapes, climate zones, cartography, borders, and natural formations.",
        "system_instructions": "Focus on wide-angle topographical fidelity, mountain ranges, river basins, tectonic formations, aerial map perspectives, biomes, and human settlements integrated into distinct geographical landscapes."
    },
    {
        "id": "mystery",
        "name": "Mystery",
        "category": "Narrative & Drama",
        "description": "Shadowy environments, hidden clues, suspenseful angles, and investigative tension.",
        "system_instructions": "Cultivate investigative intrigue, atmospheric chiaroscuro lighting, forensic clues, magnifying glasses, open case files, shadowy silhouettes, rain-slicked alleys, and suspenseful perspective angles."
    },
    {
        "id": "fiction",
        "name": "Fiction",
        "category": "Narrative & Drama",
        "description": "Evocative narrative worldbuilding, dramatic character interactions, and story tension.",
        "system_instructions": "Prioritize narrative drama, expressive character gestures, cinematic scene staging, rich environmental storytelling, and vivid visual hooks that heighten the fictional narrative."
    },
    {
        "id": "fantasy",
        "name": "Fantasy",
        "category": "Narrative & Drama",
        "description": "Mythical realms, ancient magic, enchanted flora/fauna, and epic architecture.",
        "system_instructions": "Design imaginative mythical worlds, magical auras, legendary artifacts, castle spires, ancient ruins overgrown with luminous flora, strange creatures, and otherworldly atmospheric lighting while maintaining internal visual logic."
    },
    {
        "id": "horror",
        "name": "Horror",
        "category": "Narrative & Drama",
        "description": "Dread, eerie environments, sinister shadows, and psychological tension.",
        "system_instructions": "Elicit psychological dread and atmospheric tension through deep shadows, abandoned dilapidated spaces, uneasy camera angles, subtle eerie anomalies, fog, and unsettling environmental decay. Avoid cheap gore; favor pervasive atmospheric unease."
    },
    {
        "id": "story",
        "name": "Story / General Narrative",
        "category": "Narrative & Drama",
        "description": "Balanced, versatile narrative storytelling suited for general story arcs.",
        "system_instructions": "Focus on clear narrative progression, expressive characters, dynamic camera blocking, and contextual environmental details that mirror the emotional arc of the storytelling."
    },
    {
        "id": "news_current_events",
        "name": "News / Current Events",
        "category": "Journalism & Media",
        "description": "Contemporary photojournalism, press conferences, field reporting, and modern events.",
        "system_instructions": "Employ urgent, photojournalistic realism, broadcast framing, newsroom backdrops, on-the-ground field reporting perspectives, press microphones, and contemporary streetscapes."
    },
    {
        "id": "business",
        "name": "Business",
        "category": "Commercial & Strategy",
        "description": "Corporate boardrooms, entrepreneurship, strategic planning, and modern industry.",
        "system_instructions": "Depict modern corporate spaces, glass skyscraper offices, whiteboard brainstorming sessions, logistics centers, client negotiations, and crisp professional attire."
    },
    {
        "id": "psychology",
        "name": "Psychology",
        "category": "Human & Mind",
        "description": "Cognitive metaphors, human emotions, brain processes, and behavioral insights.",
        "system_instructions": "Translate mental states, cognitive biases, neural pathways, emotional dilemmas, therapy settings, and behavioral experiments into striking, thoughtful visual compositions."
    },
    {
        "id": "philosophy",
        "name": "Philosophy",
        "category": "Human & Mind",
        "description": "Abstract thought experiments, allegory, philosophical dialogues, and symbolic compositions.",
        "system_instructions": "Construct contemplative visual allegories (e.g., Plato's cave, ship of Theseus, trolley dilemma), classical courtyards, scholars in debate, and symbolic compositions representing existential, moral, and metaphysical questions."
    },
    {
        "id": "custom",
        "name": "Custom Subject",
        "category": "Custom",
        "description": "User-defined subject guidance and custom domain rules.",
        "system_instructions": "Follow user-provided custom subject instructions precisely, adapting tone, accuracy, and framing accordingly."
    }
]


def main():
    SUBJECTS_DIR.mkdir(parents=True, exist_ok=True)
    for sub in SUBJECTS:
        filepath = SUBJECTS_DIR / f"{sub['id']}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(sub, f, indent=2)
    print(f"Generated {len(SUBJECTS)} subject presets in {SUBJECTS_DIR}")


if __name__ == "__main__":
    main()
