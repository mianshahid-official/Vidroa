# Preset System & Visual Style Guide

PromptBeast comes pre-packaged with **21 Subject Domains** and **34 Visual Styles**, each configured with domain-specific hidden prompt instructions.

---

## 1. Subject Domains (`config/subjects/`)

| Subject ID | Display Name | Focus |
|---|---|---|
| `history` | History | Period-accurate architecture, garments, tools, cultural context |
| `historical_documentary` | Historical Documentary | Archival realism, museum-grade evidence, unvarnished texture |
| `educational_explainer` | Educational Explainer | Immediate clarity, clean focal subjects, uncluttered layout |
| `finance` | Finance | Money flows, banking halls, ledgers, economic visual metaphors |
| `economics` | Economics | Trade routes, container shipping, factory labor, inflation dynamics |
| `science` | Science | Natural phenomena, laboratory optics, cosmic and microscopic depth |
| `technology` | Technology | Cleanrooms, circuit boards, server architecture, robotics |
| `biography` | Biography | Character milestones, intimate workspaces, evolving likeness |
| `mystery` | Mystery | Chiaroscuro lighting, case files, subtle clues, atmospheric tension |
| `fantasy` | Fantasy | Mythical architecture, magical auras, legendary artifacts |
| `philosophy` | Philosophy | Visual allegories, thought experiments, classical courtyards |
| `custom` | Custom Subject | Fully user-defined guidance |

---

## 2. Visual Styles (`config/visual_styles/`)

Includes:
- **Century-Old Photograph**: Late 19th / early 20th century silver gelatin archival photograph with natural aged emulsion, worn edges, and soft detail.
- **2D Stick Figure**: Ultra-clean educational explainer with readable silhouettes and intuitive body language.
- **Antique Engraving**: 18th-century copperplate crosshatch line etching on laid paper.
- **Medieval Illustration**: Illuminated manuscript tempera painting with gold leaf accents.
- **Historical Painting**: Grand 19th-century academic oil painting (Delacroix / David).
- **2D Vector Explainer**: Contemporary flat geometric vectors with modern color palettes.
- **3D Cartoon**: Stylized feature CGI animation (Pixar/Dreamworks style).
- **3D Realistic**: Physically-based CGI rendering with raytraced lighting and surface roughness.
- **Cinematic Realism**: High-budget anamorphic 35mm film still with shallow depth of field.
- **Comic Book**: Classic printed comic panel with bold brush inking and Ben-Day dots.
- **Watercolor**: Luminous wet-on-wet watercolor washes on heavy cold-press cotton paper.
- **Paper Cutout**: Multi-layered tactile cardstock shadowbox with real cast shadows.

---

## 3. Creating Custom Presets

1. Open **Presets -> Preset & Visual Style Manager...** in the application menu.
2. Click **+ New Custom Style**.
3. Enter Name, User-Facing Description, and detailed System Instructions.
4. Click **Save Visual Style**.
The new preset is saved to `config/visual_styles/custom_<name>.json` and is immediately available in the dropdown.
