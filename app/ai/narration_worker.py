"""
Background QThread Workers for Narration-Aware Story Bible Extraction and Batch Prompt Generation.
"""
from typing import List, Dict, Any, Optional
from PySide6.QtCore import QThread, Signal

from app.models.scene import VisualScene
from app.ai.groq_engine import GroqEngine
from app.core.narration_workflow import (
    extract_story_bibles_groq,
    generate_prompts_batch
)


class BibleExtractionWorker(QThread):
    """Asynchronously extracts dynamic story bibles via Groq."""
    extraction_finished = Signal(dict)
    extraction_failed = Signal(str)
    status_updated = Signal(str)

    def __init__(
        self,
        story_text: str,
        visual_ideas_summary: str = "",
        model: str = "qwen/qwen3.8-27b",
        parent=None
    ):
        super().__init__(parent)
        self.story_text = story_text
        self.visual_ideas_summary = visual_ideas_summary
        self.model = model
        self.engine = GroqEngine(default_model=model)

    def run(self):
        try:
            self.status_updated.emit("Contacting Groq AI to extract dynamic story bibles...")
            bibles = extract_story_bibles_groq(
                story_text=self.story_text,
                visual_ideas_summary=self.visual_ideas_summary,
                model=self.model,
                engine=self.engine
            )
            self.extraction_finished.emit(bibles)
        except Exception as e:
            self.extraction_failed.emit(str(e))


class BatchPromptGenerationWorker(QThread):
    """
    Asynchronously expands scenes into detailed image generation prompts in configurable batches,
    utilizing multi-key Groq rotation, rate-limit cooldowns, and retry logic.
    """
    progress_updated = Signal(int, int, str)  # (current_scenes_done, total_scenes, status_msg)
    batch_completed = Signal(list)            # (List of updated VisualScene)
    generation_finished = Signal(list)       # (Full list of VisualScene)
    generation_failed = Signal(str)
    scene_error = Signal(str, str)            # (scene_id, error_msg)

    def __init__(
        self,
        scenes: List[VisualScene],
        bibles: Dict[str, Any],
        story_context: str,
        visual_style_id: str = "zombie_survival",
        custom_style: Optional[str] = None,
        aspect_ratio: str = "16:9",
        model: str = "qwen/qwen3.8-27b",
        batch_size: int = 10,
        force_regenerate: bool = False,
        parent=None
    ):
        super().__init__(parent)
        self.scenes = scenes
        self.bibles = bibles
        self.story_context = story_context
        self.visual_style_id = visual_style_id
        self.custom_style = custom_style
        self.aspect_ratio = aspect_ratio
        self.model = model
        # Safe batch size clamp: 1 to 4 scenes per call prevents Groq token overflow and truncation
        self.batch_size = max(1, min(batch_size, 4))
        self.force_regenerate = force_regenerate
        self.engine = GroqEngine(default_model=model)
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        # Identify scenes that need generation
        scenes_to_process: List[VisualScene] = []
        for s in self.scenes:
            if self.force_regenerate:
                scenes_to_process.append(s)
            elif getattr(s, "is_approved", False):
                # Preserve approved prompts unless force_regenerate is requested
                continue
            elif not s.prompt or s.prompt.startswith("[Planned Visual"):
                scenes_to_process.append(s)
            else:
                scenes_to_process.append(s)

        total_to_gen = len(scenes_to_process)
        if total_to_gen == 0:
            self.progress_updated.emit(len(self.scenes), len(self.scenes), "All scenes are already generated or approved.")
            self.generation_finished.emit(self.scenes)
            return

        completed_count = 0
        scene_map = {s.scene_id: s for s in self.scenes}

        # Process in batches
        for i in range(0, total_to_gen, self.batch_size):
            if self._is_cancelled:
                break

            batch = scenes_to_process[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            total_batches = (total_to_gen + self.batch_size - 1) // self.batch_size

            self.progress_updated.emit(
                completed_count,
                total_to_gen,
                f"Generating Batch {batch_num}/{total_batches} (Scenes {batch[0].scene_id} - {batch[-1].scene_id}) via Groq..."
            )

            # Attempt batch generation with retry
            max_retries = 3
            batch_success = False
            items = []

            for attempt in range(max_retries):
                if self._is_cancelled:
                    break
                try:
                    items = generate_prompts_batch(
                        scenes_batch=batch,
                        bibles=self.bibles,
                        story_context=self.story_context,
                        visual_style_id=self.visual_style_id,
                        custom_style=self.custom_style,
                        aspect_ratio=self.aspect_ratio,
                        model=self.model,
                        engine=self.engine
                    )
                    if items:
                        batch_success = True
                        break
                except Exception as e:
                    print(f"[BatchPromptWorker] Batch {batch_num} attempt {attempt+1} error: {e}")
                    if attempt < max_retries - 1:
                        self.engine.key_manager.rotate_key()

            if batch_success and items:
                updated_in_batch = []
                for item in items:
                    raw_id = str(item.get("scene_id") or "").strip()
                    target_sc = None
                    if raw_id in scene_map:
                        target_sc = scene_map[raw_id]
                    elif raw_id.zfill(3) in scene_map:
                        target_sc = scene_map[raw_id.zfill(3)]
                    elif raw_id.lstrip("0") in scene_map:
                        target_sc = scene_map[raw_id.lstrip("0")]
                    else:
                        for sid, sc_obj in scene_map.items():
                            if sid.isdigit() and raw_id.isdigit() and int(sid) == int(raw_id):
                                target_sc = sc_obj
                                break

                    if target_sc:
                        target_sc.prompt = item.get("prompt", target_sc.prompt)
                        if item.get("visual_subject"):
                            target_sc.visual_subject = item["visual_subject"]
                        target_sc.character_ids = item.get("characters", target_sc.character_ids)
                        target_sc.location_id = item.get("location", target_sc.location_id)
                        target_sc.continuity_tags = item.get("continuity_references", target_sc.continuity_tags)
                        target_sc.generation_status = "generated"
                        target_sc.is_validated = True
                        if target_sc not in updated_in_batch:
                            updated_in_batch.append(target_sc)

                # Recover any missed scenes in the batch
                missed = [s for s in batch if s not in updated_in_batch]
                if missed and not self._is_cancelled:
                    try:
                        missed_items = generate_prompts_batch(
                            scenes_batch=missed,
                            bibles=self.bibles,
                            story_context=self.story_context,
                            visual_style_id=self.visual_style_id,
                            custom_style=self.custom_style,
                            aspect_ratio=self.aspect_ratio,
                            model=self.model,
                            engine=self.engine
                        )
                        for it in missed_items:
                            rid = str(it.get("scene_id") or "").strip()
                            for m_sc in missed:
                                if m_sc.scene_id in (rid, rid.zfill(3), rid.lstrip("0")):
                                    m_sc.prompt = it.get("prompt", m_sc.prompt)
                                    m_sc.generation_status = "generated"
                                    m_sc.is_validated = True
                                    if m_sc not in updated_in_batch:
                                        updated_in_batch.append(m_sc)
                                    break
                    except Exception as me:
                        print(f"[BatchPromptWorker] Retry for {len(missed)} missed scenes notice: {me}")

                completed_count += len(batch)
                self.batch_completed.emit(updated_in_batch)
                self.progress_updated.emit(
                    completed_count,
                    total_to_gen,
                    f"Completed {completed_count}/{total_to_gen} scenes."
                )
            else:
                # Mark failed for this batch
                for b_scene in batch:
                    b_scene.generation_status = "failed"
                    self.scene_error.emit(b_scene.scene_id, "Failed after retries")
                completed_count += len(batch)

        self.progress_updated.emit(total_to_gen, total_to_gen, "Prompt expansion completed.")
        self.generation_finished.emit(self.scenes)

