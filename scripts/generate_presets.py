"""
Script to generate all subject presets and visual style presets for PromptBeast.
"""
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SUBJECTS_DIR = BASE_DIR / "config" / "subjects"
STYLES_DIR = BASE_DIR / "config" / "visual_styles"

SUBJECTS_DIR.mkdir(parents=True, exist_ok=True)
STYLES_DIR.mkdir(parents=True, exist_ok=True)

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

VISUAL_STYLES = [
    {
        "id": "century_old_photograph",
        "name": "Century-Old Photograph",
        "category": "Historical & Archival",
        "description": "Archival photographic appearance with aged physical emulsion, period authenticity and soft grain.",
        "system_instructions": "Create imagery resembling authentic archival photography from the late 19th or early 20th century. The image should feel physically old with aged emulsion, soft photographic detail, subtle gelatin silver or albumen tonal range, minor scratches, worn edges, and gentle vignette. Use historically accurate clothing, architecture, and tools. Avoid modern digital filters, artificial oversaturation, or anachronistic objects."
    },
    {
        "id": "historical_archival_photograph",
        "name": "Historical Archival Photograph",
        "category": "Historical & Archival",
        "description": "Authentic mid-century archival black-and-white documentary photography.",
        "system_instructions": "Render as an authentic black-and-white historical press or government archival photograph from the 1920s-1950s. Natural grain, authentic optical depth of field, silver gelatin print tones, honest photojournalistic framing, period-accurate attire, and candid real-life composition without modern digital retouching."
    },
    {
        "id": "vintage_photograph",
        "name": "Vintage Photograph",
        "category": "Historical & Archival",
        "description": "1960s-1970s analog film aesthetic with warm Kodachrome hues and organic grain.",
        "system_instructions": "Style as authentic 1960s-1970s 35mm color film photography. Warm Kodachrome/Ektachrome color palette, organic medium film grain, slight lens halation, authentic vintage color shift, natural daylight exposure, and era-specific styling."
    },
    {
        "id": "antique_engraving",
        "name": "Antique Engraving",
        "category": "Classical Art & Print",
        "description": "18th-century copperplate or steel-engraved line etching on aged laid paper.",
        "system_instructions": "Render as a masterwork copperplate or steel engraving from the 18th or 19th century. Precise fine cross-hatching, intricate black ink linework, stippling, printed on cream or aged parchment paper with natural plate indentation texture."
    },
    {
        "id": "historical_engraving",
        "name": "Historical Engraving",
        "category": "Classical Art & Print",
        "description": "Detailed 19th-century woodcut and bookplate engraving style.",
        "system_instructions": "Render as a rich 19th-century Victorian woodcut engraving. Bold black ink lines, detailed textural hatching, dramatic contrast, traditional printmaker craft, with crisp historical character and architectural detail."
    },
    {
        "id": "medieval_illustration",
        "name": "Medieval Illustration",
        "category": "Classical Art & Print",
        "description": "Illuminated manuscript miniature with gold leaf accents and flattened medieval perspective.",
        "system_instructions": "Style as a genuine medieval illuminated manuscript miniature from the 13th-15th century. Flat heraldic perspective, tempera and gouache pigments, gold leaf illumination, decorative borders, expressive stylized poses, and authentic medieval period garments and iconography."
    },
    {
        "id": "ancient_history_illustration",
        "name": "Ancient History Illustration",
        "category": "Classical Art & Print",
        "description": "Classical antiquity fresco, mosaic, or papyrus illustration aesthetic.",
        "system_instructions": "Depict in the visual tradition of ancient classical frescoes, Pompeian murals, Greek pottery painting, or ancient papyrus scrolls. Weathered plaster texture, earthy mineral pigments, classical drapery, and authentic ancient architectural elements."
    },
    {
        "id": "old_newspaper_illustration",
        "name": "Old Newspaper Illustration",
        "category": "Classical Art & Print",
        "description": "Turn-of-the-century lithographic newsprint drawing with dot gain and halftone patterns.",
        "system_instructions": "Render as a 1900s broadsheet newspaper illustration. High-contrast black ink crosshatching, coarse halftone screen dots, aged newsprint paper texture, slight ink bleed, and dynamic editorial journalism layout."
    },
    {
        "id": "historical_painting",
        "name": "Historical Painting",
        "category": "Fine Art",
        "description": "Grand academic neoclassical or romantic masterwork oil painting.",
        "system_instructions": "Render as a monumental 19th-century history oil painting in the tradition of Jacques-Louis David or Delacroix. Rich impasto textures, chiaroscuro lighting, grand compositions, theatrical staging, and rich oil glaze depth."
    },
    {
        "id": "oil_painting",
        "name": "Oil Painting",
        "category": "Fine Art",
        "description": "Expressive fine-art canvas with visible brushwork, rich pigment, and glazed layers.",
        "system_instructions": "Depict as a master oil painting on woven linen canvas. Visible directional brushstrokes, rich palette knife impasto, deep luminous shadows, rich layered glazes, and masterful handling of natural light."
    },
    {
        "id": "watercolor",
        "name": "Watercolor",
        "category": "Fine Art",
        "description": "Luminous wet-on-wet watercolor on cold-press textured paper.",
        "system_instructions": "Render in expressive watercolor painting technique. Transparent washes, wet-on-wet blooms, deckled paper grain, soft pigment bleeding, crisp dry-brush details on focal subjects, and glowing atmospheric light."
    },
    {
        "id": "pencil_sketch",
        "name": "Pencil Sketch",
        "category": "Drawing & Illustration",
        "description": "Detailed graphite and charcoal drawing on archival cotton sketch paper.",
        "system_instructions": "Create as a fine graphite and charcoal sketch on heavy textured drawing paper. Expressive tonal smudging, crisp contour lines, crosshatched shading, raw graphite luster, and artistic anatomy/structural precision."
    },
    {
        "id": "ink_illustration",
        "name": "Ink Illustration",
        "category": "Drawing & Illustration",
        "description": "Intricate black Indian ink drawing with dip pen and brushwork.",
        "system_instructions": "Render as a detailed black ink dip-pen illustration. Crisp calligraphic line variation, intricate stippling, rich black ink fills, dynamic brush washes, and striking graphic readability."
    },
    {
        "id": "2d_stick_figure",
        "name": "2D Stick Figure",
        "category": "2D Animation & Minimalist",
        "description": "Clean, highly expressive stick-figure educational explainer with readable silhouettes.",
        "system_instructions": "Create a clean 2D educational explainer illustration using simple stick-figure characters. Highly readable poses, clear dynamic body language, minimal clutter, solid outlines, simple contextual props, and instant visual comprehension within seconds. No photorealism or complex anatomy."
    },
    {
        "id": "2d_explainer",
        "name": "2D Explainer",
        "category": "2D Animation & Minimalist",
        "description": "Modern flat vector explainer graphic with crisp shapes, clear icons, and clean palettes.",
        "system_instructions": "Style as a contemporary premium 2D vector explainer illustration. Clean geometric shapes, harmonious modern color palette, smooth gradients, crisp outlines, visual metaphors, uncluttered composition, and high educational readability."
    },
    {
        "id": "2d_cartoon",
        "name": "2D Cartoon",
        "category": "2D Animation & Minimalist",
        "description": "Vibrant 2D animated cartoon with expressive character acting and bold lines.",
        "system_instructions": "Render as a high-quality 2D animated cartoon frame. Expressive character silhouettes, bold clean outlines, vibrant saturated color fills, dynamic squash-and-stretch posing, and charming animated background art."
    },
    {
        "id": "2d_educational_illustration",
        "name": "2D Educational Illustration",
        "category": "2D Animation & Minimalist",
        "description": "Textbook-grade instructional diagram and clear pictorial breakdown.",
        "system_instructions": "Style as a modern premium educational textbook illustration. Crystal clear visual anatomy/structure, informative color coding, transparent cutaway views where helpful, and clean layout designed for maximum instructional clarity."
    },
    {
        "id": "2d_hand_drawn",
        "name": "2D Hand-Drawn",
        "category": "2D Animation & Minimalist",
        "description": "Organic cel-animation with hand-penciled linework and soft gouache backgrounds.",
        "system_instructions": "Style as traditional hand-drawn 2D feature animation. Organic penciled outlines, painted matte gouache backgrounds, warm textured colors, fluid character posing, and cinematic theatrical staging."
    },
    {
        "id": "3d_cartoon",
        "name": "3D Cartoon",
        "category": "3D & CGI",
        "description": "Pixar/Dreamworks style 3D animated CGI with soft subsurface scattering and vibrant lighting.",
        "system_instructions": "Render as a modern stylized 3D animated feature film still. Appealing stylized proportions, soft subsurface scattering on skin, rich tactile materials (cloth, fur, clay), vibrant cinematic key-to-fill lighting, and clean depth of field."
    },
    {
        "id": "3d_realistic",
        "name": "3D Realistic",
        "category": "3D & CGI",
        "description": "Physically-based 3D CGI rendering with photorealistic shaders and global illumination.",
        "system_instructions": "Produce as high-end physically-based 3D computer graphics. Raytraced global illumination, micro-surface roughness, accurate refractive caustics, volumetric lighting, and hyper-detailed photorealistic asset modeling."
    },
    {
        "id": "3d_stylized",
        "name": "3D Stylized",
        "category": "3D & CGI",
        "description": "Stylized 3D rendering with hand-painted textures and graphic lighting.",
        "system_instructions": "Style as contemporary stylized 3D art (like Arcane or Spider-Verse). Sculptural shapes, visible brush-painted texture maps, graphic rim lights, rim highlights, bold color harmonies, and expressive stylized staging."
    },
    {
        "id": "3d_educational",
        "name": "3D Educational",
        "category": "3D & CGI",
        "description": "Clean 3D medical, scientific, or architectural visualization.",
        "system_instructions": "Render as high-end 3D scientific or technical visualization. Clean studio lighting, glossy and matte material distinction, floating isometric or cutaway perspectives, and precise anatomical or mechanical accuracy."
    },
    {
        "id": "documentary_realism",
        "name": "Documentary Realism",
        "category": "Realism & Photographic",
        "description": "Unvarnished, cinematic photojournalistic realism with natural lighting.",
        "system_instructions": "Capture in authentic photojournalistic documentary realism. Naturalistic lighting, authentic real-world grime and texture, candid un-posed framing, standard documentary focal lengths (35mm / 50mm), and complete absence of artificial glamour."
    },
    {
        "id": "cinematic_realism",
        "name": "Cinematic Realism",
        "category": "Realism & Photographic",
        "description": "High-budget anamorphic cinematic film still with rich color grade and atmospheric depth.",
        "system_instructions": "Render as a frame from a high-budget cinematic motion picture shot on anamorphic lenses. Shallow depth of field, anamorphic bokeh, subtle lens flare, dynamic three-point lighting, atmospheric haze, and deliberate filmic color grading."
    },
    {
        "id": "photorealistic",
        "name": "Photorealistic",
        "category": "Realism & Photographic",
        "description": "Ultra-sharp modern DSLR photography with lifelike optical clarity.",
        "system_instructions": "Produce an ultra-sharp, lifelike modern digital photograph. Precise optical focus, lifelike skin pores and surface micro-textures, balanced dynamic range, natural color rendition, and realistic shutter speed motion capture."
    },
    {
        "id": "comic_book",
        "name": "Comic Book",
        "category": "Comic & Graphic Novel",
        "description": "Classic graphic comic panel with dynamic inking, Ben-Day dots, and dramatic angles.",
        "system_instructions": "Style as a classic printed comic book panel. Bold black brush inking, Ben-Day halftone color dots, dramatic foreshortening, action lines, expressive character faces, and high-impact cinematic staging."
    },
    {
        "id": "graphic_novel",
        "name": "Graphic Novel",
        "category": "Comic & Graphic Novel",
        "description": "Moody, painterly European graphic novel art with sophisticated palettes.",
        "system_instructions": "Render as a frame from a sophisticated European graphic novel (Bande Dessinée). Expressive fine linework, atmospheric watercolor or gouache palettes, deliberate panel composition, and mature narrative tone."
    },
    {
        "id": "paper_cutout",
        "name": "Paper Cutout",
        "category": "Craft & Experimental",
        "description": "Layered dimensional paper craft with physical cast shadows and cardstock textures.",
        "system_instructions": "Style as a tactile layered paper-cutout shadow box. Distinct physical paper layers, subtle paper grain and edge bevels, natural cast shadows between depths, delicate silhouette shapes, and warm studio craft lighting."
    },
    {
        "id": "clay_stop_motion",
        "name": "Clay / Stop Motion Style",
        "category": "Craft & Experimental",
        "description": "Handcrafted plasticine clay animation still with fingerprint textures and miniature lighting.",
        "system_instructions": "Render as a stop-motion animated claymation film still. Subtle fingerprint impressions on sculpted clay surfaces, miniature set depth of field, tactile cloth and wire armatures, and warm physical studio lighting."
    },
    {
        "id": "infographic",
        "name": "Infographic",
        "category": "Data & Graphical",
        "description": "Data-rich, clean isometric or flat infographic diagram layout.",
        "system_instructions": "Design as a clean, highly structured modern visual infographic. Clear visual hierarchy, isometric or flat lay perspective, visual process flows, comparison containers, and crisp communicative iconography."
    },
    {
        "id": "minimalist",
        "name": "Minimalist",
        "category": "2D Animation & Minimalist",
        "description": "Striking negative space, essential silhouettes, and restrained focal color accents.",
        "system_instructions": "Produce a powerful minimalist visual composition. Expansive negative space, razor-sharp focal subject, restrained color palette with single accent color, and absolute elimination of decorative visual clutter."
    },
    {
        "id": "childrens_illustration",
        "name": "Children's Illustration",
        "category": "Drawing & Illustration",
        "description": "Whimsical, heartwarming picture book art with soft pastels and playful shapes.",
        "system_instructions": "Render as an enchanting children's picture book illustration. Friendly rounded shapes, whimsical character designs, soft pastel palette, gentle colored pencil or gouache texture, and heartwarming emotional warmth."
    },
    {
        "id": "storybook_illustration",
        "name": "Storybook Illustration",
        "category": "Drawing & Illustration",
        "description": "Arthur Rackham golden-age fairy tale illustration with delicate pen and sepia wash.",
        "system_instructions": "Style in the Golden Age of illustration tradition (Arthur Rackham, Edmund Dulac). Delicate pen-and-ink contour lines, muted sepia and watercolor washes, gnarled fantasy trees, intricate lace/armor, and timeless fairy tale atmosphere."
    },
    {
        "id": "custom",
        "name": "Custom Style",
        "category": "Custom",
        "description": "User-defined visual style prompt instructions.",
        "system_instructions": "Apply the user's custom style instructions verbatim as the governing artistic guideline."
    }
]

# Write Subject presets
for sub in SUBJECTS:
    filepath = SUBJECTS_DIR / f"{sub['id']}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(sub, f, indent=2)
print(f"Generated {len(SUBJECTS)} subject presets in {SUBJECTS_DIR}")

# Write Style presets
for style in VISUAL_STYLES:
    filepath = STYLES_DIR / f"{style['id']}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(style, f, indent=2)
print(f"Generated {len(VISUAL_STYLES)} visual style presets in {STYLES_DIR}")
