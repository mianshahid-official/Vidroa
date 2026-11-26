# Preset System & Visual Style Guide

Vidroa (PromptBeast) comes pre-packaged with **21 Subject Domains** and **4 Visual Styles**, each configured with domain-specific hidden prompt instructions.

---

## 1. Subject Domains (`config/subjects/`)

| Subject ID | Display Name | Focus |
|---|---|---|
| `biography` | Biography | Intimate human portraits, personal milestones, psychological depth, and lived environments |
| `business` | Business | Corporate boardrooms, entrepreneurship, strategic planning, and modern industry |
| `custom` | Custom Subject | User-defined subject guidance and custom domain rules |
| `economics` | Economics | Macro and microeconomic concepts, supply chains, trade, labor, and market forces |
| `educational_explainer` | Educational Explainer | Immediate comprehension, visual clarity, uncluttered composition, and direct concept representation |
| `fantasy` | Fantasy | Mythical realms, ancient magic, enchanted flora/fauna, and epic architecture |
| `fiction` | Fiction | Evocative narrative worldbuilding, dramatic character interactions, and story tension |
| `finance` | Finance | Clear visual metaphors for money flows, financial institutions, banking, and market dynamics |
| `general_documentary` | General Documentary | Informative visual storytelling, realistic environments, and clear visual communication |
| `geography` | Geography | Topographical landscapes, climate zones, cartography, borders, and natural formations |
| `historical_documentary` | Historical Documentary | Evidence-oriented, archival realism and authentic archival reconstructions |
| `history` | History | Historical accuracy, period-appropriate environments, clothing, tools, and social context |
| `horror` | Horror | Dread, eerie environments, sinister shadows, and psychological tension |
| `mystery` | Mystery | Shadowy environments, hidden clues, suspenseful angles, and investigative tension |
| `news_current_events` | News / Current Events | Contemporary photojournalism, press conferences, field reporting, and modern events |
| `philosophy` | Philosophy | Abstract thought experiments, allegory, philosophical dialogues, and symbolic compositions |
| `politics` | Politics | Government institutions, legislative chambers, rallies, diplomacy, and political negotiations |
| `psychology` | Psychology | Cognitive metaphors, human emotions, brain processes, and behavioral insights |
| `science` | Science | Scientific phenomena, laboratories, microscopic details, cosmos, and physical laws |
| `story` | Story / General Narrative | Balanced, versatile narrative storytelling suited for general story arcs |
| `technology` | Technology | Hardware, computing systems, software architectures, robotics, and digital infrastructure |

---

## 2. Visual Styles (`config/visual_styles/`)

- **Zombie Survival (`zombie_survival`)**: Pure flat 2D cartoon illustration style with heavy dark outlines (`#1A1A1A`), locked hero character design, and uniform pale olive-green zombie horde.
- **What-If Flat Vector (`whatif_flat_vector`)**: Bold minimalist flat 2D vector illustration in night-world navy tones (`#12182E`), featuring a solid black stickman protagonist in a locked bright red hoodie (`#FF0000`).
- **Century-Old Photograph (`century_old_photograph`)**: Museum-grade historical documentary archival print aesthetic featuring 12 specialized archival image treatments (including Woodblock/Engraving Split, Leporello Folder, Silver Bleeding, Fold Creases, Diptych Split, Document Archive, Split-Screen Trio, Textured Blur, Antique Map Overlay, Full Antique Engraving Plate, Full-Frame Authentic Archival Photograph, and Full Historical Map Plate).
- **3D Red & Blue Stickman Animation (`3d_red_blue_stickman`)**: Stylized 3D CGI toy stickman universe enforcing strict Red vs. Blue faction separation.

---

## 3. Creating Custom Presets

1. Open **Presets -> Preset and Visual Style Manager...** in the application menu.
2. Click **+ New Custom Style**.
3. Enter Name, User-Facing Description, and detailed System Instructions.
4. Click **Save Visual Style**.
The new preset is saved to `config/visual_styles/custom_<name>.json` and is immediately available in the dropdown.
