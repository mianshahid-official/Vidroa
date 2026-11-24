# PromptBeast: Visual Look & Single-Page App (One-Page Dashboard) Blueprint

## 📖 Executive Summary

This document provides a comprehensive breakdown of the visual layout and user experience of **PromptBeast**. It includes:
1. **A detailed visual walkthrough of the entire application across every current page and tab.**
2. **An analysis of UX bottlenecks inherent in the current multi-tab paradigm.**
3. **A complete architectural blueprint to transform PromptBeast into a unified, high-productivity Single-Page Application (One-Page Dashboard) with zero tabs.**

---

## 🎨 Part 1: Current Visual Look & Page Breakdown

PromptBeast utilizes an **Obsidian & Dark Navy** visual language designed for prolonged creative sessions without eye fatigue.

### Global Theme Palette:
- **Base Background**: `#0b0f19` (Deep Obsidian Void)
- **Card / Surface Background**: `#0f172a` (Dark Slate Blue)
- **Hover & Active Borders**: `#1e293b` / `#334155`
- **Primary Accent (Interactive)**: `#38bdf8` (Cyan Neon)
- **Success / Action Accent**: `#10b981` (Emerald Green)
- **Warning / Alert Accent**: `#f59e0b` (Amber Orange)
- **Text Hierarchy**: Primary `#f1f5f9` (Crisp White), Secondary `#94a3b8` (Muted Slate), Monospace `#cbd5e1` (`Consolas`)

---

### Tab 1: Story & Narration Audio (`🎙️ 1. Story & Narration Audio`)
The initial ingestion station where narrative content and voiceovers enter the pipeline.

```
┌───────────────────────────────────────────────────┬───────────────────────────────────────────────────┐
│ 📝 STORY NARRATION SCRIPT                          │ 🎙️ VOICEOVER AUDIO & WORD-LEVEL TIMESTAMPS        │
├───────────────────────────────────────────────────┼───────────────────────────────────────────────────┤
│ [📂 Load Script (.txt/.md)] [💾 Save] [🧹 Clear]   │ [🎵 Browse Voiceover Audio (.mp3/.wav)]            │
│ ───────────────────────────────────────────────── │ File: Pompeii_Narration_2026.mp3 (04:07.45)       │
│ It was the morning of August 24, 79 AD...         │                                                   │
│ Mount Vesuvius loomed silently over the bay...    │ Waveform: [  ▂▃▅▆▇█▇▆▅▃▂ ▂▃▅▆▇█  ] (Seek: 01:23)  │
│ Citizens walked the stone-paved streets of        │ Controls: [▶ Play]  [⏸ Pause]  [⏹ Stop]           │
│ Pompeii, oblivious to the mountain's wrath...     │                                                   │
│                                                   │ Whisper Engine: [⚡ Groq Whisper Cloud (v3-turbo)]│
│                                                   │ [⚡ TRANSCRIBE & GENERATE WORD TIMESTAMPS]         │
│                                                   │ [📂 Import Timestamps JSON]                       │
│                                                   │                                                   │
│                                                   │ Detected Word Boundaries: (2,143 words)           │
│                                                   │ ┌──────┬──────────┬───────────┬─────────┐         │
│                                                   │ │ Word │ Token    │ Start (s) │ End (s) │         │
│                                                   │ ├──────┼──────────┼───────────┼─────────┤         │
│                                                   │ │ #001 │ It       │ 0.20      │ 0.45    │         │
│                                                   │ │ #002 │ was      │ 0.48      │ 0.72    │         │
│                                                   │ │ #003 │ the      │ 0.75      │ 0.88    │         │
│                                                   │ └──────┴──────────┴───────────┴─────────┘         │
│ ───────────────────────────────────────────────── │                                                   │
│ Statistics: 2,143 words | 12,840 characters       │ Status: 🟢 2,143 words synchronized with audio.    │
└───────────────────────────────────────────────────┴───────────────────────────────────────────────────┘
```

**Key Visual Features:**
- **Two-Column Horizontal Splitter**: Allows the user to widen the script editor or the timestamps table dynamically.
- **Waveform Scrub Bar**: Live visual feedback of audio amplitude and playhead position.
- **High-Velocity Transcription Button**: Glowing green call-to-action button that triggers either Groq Cloud LPU transcription (< 2 seconds) or local faster-whisper.

---

### Tab 2: Prompts + Storyboard Studio (`🎨 2. Prompts + Storyboard`)
The primary AI generation workshop structured as a **3-Pane Studio Layout**.

```
┌──────────────────────┬───────────────────────────────────┬───────────────────────────────────┐
│ 🎛️ CONTROLS (280px)   │ 🎬 TIMELINE CARDS (450px)         │ 👁️ PROMPT BLUEPRINT INSPECTOR      │
├──────────────────────┼───────────────────────────────────┼───────────────────────────────────┤
│ Subject Domain:      │ [➕ Add Scene] [✂ Split] [☍ Merge] │ Scene: SCENE 001 (0.00s - 4.25s)  │
│ [ History          ▼]│ ───────────────────────────────── │ ───────────────────────────────── │
│                      │ ┌───────────────────────────────┐ │ Visual Prompt Blueprint:          │
│ Visual Style Preset: │ │ SCENE 001 [⏱ 0.00s - 4.25s]   │ │ "A wide establishing panoramic   │
│ [ 3D Render & CGI  ▼]│ │ "Mount Vesuvius slept under   │ │ shot of the ancient city of       │
│ [👁️ Preview Style]   │ │ morning skies..."             │ │ Pompeii in 79 AD. The towering   │
│                      │ │ Subject: Pompeii Morning      │ │ volcano looms in the hazy       │
│ Timing Rules:        │ └───────────────────────────────┘ │ distance under morning skies.     │
│ Mode: [AI Decides  ▼]│ ┌───────────────────────────────┐ │ Pixar/Octane 3D style, soft clay │
│ Min:  [3.00s]        │ │ SCENE 002 [⏱ 4.25s - 8.10s]   │ │ subsurface scattering on marble, │
│ Pref: [4.50s]        │ │ "Suddenly the earth trembled  │ │ vibrant cinematic lighting."    │
│ Max:  [6.00s]        │ │ beneath their feet..."        │ ───────────────────────────────── │
│                      │ │ Subject: Ground Shaking       │ Composition: Wide Panoramic, Eye  │
│ Count: [● Auto ○ Ex] │ └───────────────────────────────┘ │ Lighting: Golden hour, volumetric│
│                      │ ┌───────────────────────────────┐ │ Mood: Peaceful foreboding         │
│ [🚀 GENERATE STORY-  │ │ SCENE 003 [⏱ 8.10s - 12.05s]  │ ───────────────────────────────── │
│    BOARD + PROMPTS]  │ │ "Black smoke surged high..."  │ [🔄 Regenerate Scene Prompt]      │
│                      │ └───────────────────────────────┘ │ [📋 Copy Prompt]                  │
└──────────────────────┴───────────────────────────────────┴───────────────────────────────────┘
```

**Key Visual Features:**
- **Curated Visual Styles**: Strictly **13 distinct, viral styles** (Stick Figure, History Painting, 2D Vector, 3D Render, Realistic DSLR, Midjourney Hyper-Realism, Anime Ghibli, Isometric 3D, Dark Fantasy, Retro Pop Art, Claymation, Century-Old Photo, Watercolor) + Custom.
- **Strict 3 to 6-Second Pacing**: Hard limits preventing scenes from dragging or rushing.
- **Interactive Storyboard Timeline**: Cards highlight with bright cyan borders when clicked, instantly updating the right inspector.

---

### Tab 3: Images & Asset Manager (`🖼️ 3. Images + Assets`)
The visual synchronization hub where generated AI images are paired with their storyboard scenes.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 📁 BINDING TOOLBAR: [📁 Browse Generated Images Folder] [⚡ Auto-Match Scene Numbers]   │
│ Status: 🟢 59 of 59 Images Assigned (100% Ready) | Output Target: 1920x1080 (16:9)    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│ │ SCENE 001 (4.25s)│  │ SCENE 002 (3.85s)│  │ SCENE 003 (3.95s)│  │ SCENE 004 (4.10s)│ │
│ │ ┌──────────────┐ │  │ ┌──────────────┐ │  │ ┌──────────────┐ │  │ ┌──────────────┐ │ │
│ │ │ [Image 001]  │ │  │ │ [Image 002]  │ │  │ │ [Image 003]  │ │  │ │ [Image 004]  │ │ │
│ │ └──────────────┘ │  │ └──────────────┘ │  │ └──────────────┘ │  │ └──────────────┘ │ │
│ │ img_001.png (OK) │  │ img_002.png (OK) │  │ img_003.png (OK) │  │ img_004.png (OK) │ │
│ └──────────────────┘  └──────────────────┘  └──────────────────┘  └──────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### Tab 4: Subtitles & Video Render Studio (`🎬 4. Subtitles + Video Render`)
The final production hub where subtitles, motion, audio, and images are compiled into a finished video.

```
┌───────────────────────────────────────────────┬───────────────────────────────────────────────┐
│ 🎛️ SUBTITLE & MOTION CONTROLS                 │ 📺 LIVE VIDEO & KARAOKE SUBTITLE PREVIEW      │
├───────────────────────────────────────────────┼───────────────────────────────────────────────┤
│ Subtitle Typography Presets:                  │ ┌───────────────────────────────────────────┐ │
│ [🔥 Hormozi Viral (Active Word Highlight)  ▼] │ │                                           │ │
│ • Font: Impact Bold, 64pt                     │ │                                           │ │
│ • Active Word: Bright Yellow (#FFE600)        │ │                 MOUNT                     │ │
│ • Passive Word: Pure White (#FFFFFF)          │ │                                           │ │
│ • Stroke: Heavy Black 4px                     │ │              VESUVIUS                     │ │
│                                               │ │                                           │ │
│ Motion & Camera Dynamics:                     │ │                                           │ │
│ [🎬 Alternating Ken Burns Zoom (Dynamic)   ▼] │ │        SLEPT UNDER MORNING SKIES          │ │
│ [✔] Add 2.35:1 Cinematic Letterbox Bars       │ │                                           │ │
│ [✔] Add Soft Vignette Lighting                │ └───────────────────────────────────────────┘ │
│                                               │ [ 00:02.15 / 04:07.45 ] [▶ Play] [⏸ Pause]   │
│ Video Output Settings:                        │ ───────────────────────────────────────────── │
│ Resolution: 1920x1080 (1080p Full HD)         │ Subtitle Format: ASS (Advanced SubStation)    │
│ Framerate:  30 FPS | Codec: H.264 / AAC       │ Render Engine: Hardware Accelerated FFmpeg    │
│                                               │                                               │
│ [🚀 RENDER FINAL VIDEO (MP4)]                 │ Status: Ready to compile 59 scenes.           │
└───────────────────────────────────────────────┴───────────────────────────────────────────────┘
```

---

### 👁️ Modal Dialog: Visual Style Gallery & Prompt Previewer
Triggered by clicking **`👁️ Preview Style`**:
- **Interactive Top Selector**: Dropdown + `◀ Prev` and `Next ▶` quick buttons.
- **Large Artwork Box (620x350px)**: Renders high-resolution image artwork representing the style.
- **Artistic Summary**: Title and category badge with descriptive explanation.
- **Prompt Blueprint Code Box**: Monospace box revealing the exact hidden system instructions fed to the AI.
- **Actions**: `📋 Copy Instructions` and `✅ Select & Apply This Style`.

---

## ⚠️ Part 2: The Problems with the Multi-Tab Layout

1. **Information Siloing**: 
   - When editing a prompt on Tab 2, you cannot see what the speaker is saying in Tab 1 without clicking back and forth.
   - When reviewing image matches on Tab 3, you cannot see the prompt blueprint on Tab 2.
2. **Loss of Flow**:
   - Video creation is a continuous left-to-right assembly line (Script ➔ Audio ➔ Storyboard ➔ Images ➔ Video). Tabs break this linear mental model.
3. **Hidden State**:
   - Users frequently forget whether transcription succeeded or whether all images were matched because the status is buried in inactive tabs.

---

## 🚀 Part 3: The Single-Page App (One-Page Dashboard) Blueprint

### Architecture: The 3-Column Studio Console
In the new Single-Page App, all four tabs are eliminated and unified into a responsive **3-Column Studio Layout** that fits completely on one screen.

```
┌───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 🦁 PROMPTBEAST STUDIO  │ Project: "Last_Dawn_of_Pompeii" │ ⚡ Groq LPU Array (11 Keys Active) │ ⚙️ AI Settings │ 📁 Projects History │
├───────────────────────────────────┬───────────────────────────────────────────────┬───────────────────────────────────────────────┤
│ 🎙️ 1. SCRIPT & AUDIO INGESTION    │ 🎬 2. AI STORYBOARD & TIMELINE                │ 👁️ 3. LIVE INSPECTOR & RENDER STUDIO          │
│   (Width: 28% of Screen)          │   (Width: 38% of Screen)                      │   (Width: 34% of Screen)                      │
├───────────────────────────────────┼───────────────────────────────────────────────┼───────────────────────────────────────────────┤
│ 📝 Narration Script Editor:       │ 🎛️ Generation Presets Bar:                    │ 🖼️ Visual Scene Preview Viewport:             │
│ [📂 Open] [💾 Save] [🧹 Clear]     │ Subject: [ History                         ▼] │ ┌───────────────────────────────────────────┐ │
│ ┌───────────────────────────────┐ │ Style:   [ 3D Render & CGI                 ▼] │ │                                           │ │
│ │ It was the morning of August  │ │          [👁️ Preview Style]                  │ │          [IMAGE 001 PREVIEW]              │ │
│ │ 24, 79 AD. Mount Vesuvius     │ │ Timing:  [AI Decides (3.0s - 6.0s)         ▼] │ │                                           │ │
│ │ loomed silently...            │ │ [🚀 GENERATE STORYBOARD + PROMPTS]          │ │              VESUVIUS                     │ │
│ └───────────────────────────────┘ │                                               │ └───────────────────────────────────────────┘ │
│ 2,143 words | 04:07.45 estimated  │ 📋 Storyboard Timeline Matrix (59 Scenes):    │ [ 00:01.85 / 04:07.45 ] [▶ Play] [⏸ Pause]   │
│                                   │ ┌───────────────────────────────────────────┐ │ ───────────────────────────────────────────── │
│ 🎙️ Voiceover Audio Ingestion:     │ │ SCENE 001 [⏱ 0.00s - 4.25s (4.25s)]      │ │ 📝 Prompt Blueprint Editor:                   │
│ [🎵 Browse Voiceover Audio]       │ │ "Mount Vesuvius slept under morning..."   │ │ "A wide establishing panoramic shot of the   │
│ Pompeii_Narration_2026.mp3        │ │ Subject: Pompeii Morning                  │ │ ancient city of Pompeii in 79 AD..."        │
│ [  ▂▃▅▆▇█▇▆▅▃▂  ] (00:00 / 04:07) │ │ [📷 img_001.png] [✂ Split] [☍ Merge]      │ │ [🔄 Regenerate Prompt] [📋 Copy Prompt]      │
│                                   │ ├───────────────────────────────────────────┤ │ ───────────────────────────────────────────── │
│ ⚡ Whisper Transcription:          │ │ SCENE 002 [⏱ 4.25s - 8.10s (3.85s)]      │ │ 🎛️ Subtitles & Video Motion:                │
│ [⚡ TRANSCRIBE WORD TIMESTAMPS]    │ │ "Suddenly the earth trembled..."          │ │ Subtitles: [🔥 Hormozi Viral             ▼] │
│ [📂 Import Timestamps JSON]       │ │ Subject: Ground Shaking                   │ │ Motion:    [🎬 Alternating Ken Burns Zoom ▼] │
│ 🟢 2,143 words aligned (Groq LPU) │ │ [📷 img_002.png] [✂ Split] [☍ Merge]      │ │ [✔] Letterbox [✔] Vignette                  │
│                                   │ └───────────────────────────────────────────┘ │ ───────────────────────────────────────────── │
│                                   │ [➕ Add Scene] [📋 Export TXT/JSON/CSV]      │ [🚀 RENDER FINAL VIDEO (MP4)]                 │
├───────────────────────────────────┴───────────────────────────────────────────────┴───────────────────────────────────────────────┤
│ 🟢 ENGINE: CONNECTED | Active Model: qwen/qwen3.8-27b | Scenes: 59 | Pacing: Strict 3-6s (Avg 4.19s) | Groq LPU Keys: 11 Healthy  │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Part 4: Unified Interaction & Live Bidirectional Syncing

In the Single-Page Architecture, every component reacts simultaneously:
1. **Audio Scrubbing Sync**:
   - Scrubbing the audio player in Column 1 instantly scrolls the timeline in Column 2 to the active scene and updates the image/subtitles in Column 3.
2. **Scene Selection Sync**:
   - Clicking Scene 014 in Column 2 instantly highlights the corresponding sentence in Column 1's script editor, shows Scene 014's prompt and generated image in Column 3, and positions the playhead to that exact timestamp.
3. **Real-time Progress Visibility**:
   - As AI generation runs, users see scenes stream into Column 2 while watching their script in Column 1, with zero tab switching.

---

## 🛠️ Part 5: Code Architecture for Single-Page Refactoring

In `app/ui/main_window.py`:
- Replace `self.tabs = QTabWidget()` with a master horizontal `QSplitter`:
  ```python
  self.master_splitter = QSplitter(Qt.Orientation.Horizontal)
  
  # Column 1: Script & Audio Ingest Panel
  self.col1_ingest_panel = ScriptAudioPanel()
  
  # Column 2: Timeline & Storyboard Matrix
  self.col2_storyboard_panel = StoryboardTimelinePanel()
  
  # Column 3: Live Inspector, Subtitles & Render Hub
  self.col3_inspector_panel = InspectorRenderPanel()
  
  self.master_splitter.addWidget(self.col1_ingest_panel)
  self.master_splitter.addWidget(self.col2_storyboard_panel)
  self.master_splitter.addWidget(self.col3_inspector_panel)
  
  # Set default proportions: 28% | 38% | 34%
  self.master_splitter.setStretchFactor(0, 28)
  self.master_splitter.setStretchFactor(1, 38)
  self.master_splitter.setStretchFactor(2, 34)
  ```
- This keeps the full power of PromptBeast accessible in a single glance!

