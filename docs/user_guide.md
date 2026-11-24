# PromptBeast User Guide

A step-by-step workflow guide for creating visual storyboards with PromptBeast.

---

## Complete Generation Workflow

1. **Create / Name Project**: Enter a project name in the left panel (e.g. `Blackwood_Ridge_1888`).
2. **Load Story**: Click **Browse...** under Story Narration Input and select your `.txt` or `.md` story file.
3. **Load Narration Timestamps (Optional)**: Click **Browse...** under Word Timestamps and select your word-level JSON timestamps file.
   - *Note*: If omitted, PromptBeast automatically estimates natural word timing based on speech cadence and punctuation pauses.
4. **Choose Subject & Visual Style**: Select the domain (e.g. `History`) and artistic style (e.g. `Century-Old Photograph`).
5. **Configure Timing**:
   - Set **Timing Mode** (`AI Decides`, `Target Duration`, or `Fixed Duration Intervals`).
   - Adjust Minimum, Preferred, and Maximum scene durations (e.g. Min 3s, Pref 5s, Max 8s).
6. **Start Generation**: Click **🚀 START STORYBOARD GENERATION**.
7. **Monitor Real-Time Progress**: Watch the right panel progress breakdown:
   - Story Analysis ✓
   - Visual Scene Planning ✓
   - Batched Prompt Generation (`10 / 30`, `20 / 30`, ...)
   - Validation & Repair
8. **Inspect & Edit Scenes**:
   - Click any scene block on the interactive visual timeline or from the scene list.
   - Edit timestamps, visual subject, or prompt text directly.
   - Manually edited scenes are automatically tagged with a yellow `[EDITED]` badge.
9. **Split / Merge / Regenerate**:
   - **Split**: Click **✂ Split Scene** to subdivide a long sequence at a specific timestamp.
   - **Merge**: Click **☍ Merge Next** to combine two adjacent scenes.
   - **Regenerate**: Click **⚡ Regenerate Scene** to generate a fresh prompt from the cloud AI.
10. **Export Storyboard**:
    - Click **File -> Export Storyboard...** (or `Ctrl+E`).
    - Preview or copy `image_prompts.txt`, `timeline.json`, `image_prompts.json`, or `timeline.csv`.
    - Click **Export All Files to Folder...** to save all formats to your desired destination.
