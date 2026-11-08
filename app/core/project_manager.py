"""
Project manager handling creation, loading, persistent serialization, auto-save, and recovery.
"""
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from app.models.project import StoryProject, ProjectConfig, ProjectState
from app.models.scene import VisualScene, StoryAnalysis, StoryContinuity
from app.models.timeline import NarrationData, WordTimestamp
from app.core.export import StoryboardExporter


class ProjectManager:
    """Manages project disk structure, serialization, auto-save, and recovery."""

    @staticmethod
    def create_project(project_name: str, base_dir: str, add_unique_id: bool = False) -> StoryProject:
        sanitized_name = "".join(c for c in project_name if c.isalnum() or c in (" ", "_", "-")).strip()
        if not sanitized_name:
            sanitized_name = "Untitled_Project"

        if add_unique_id:
            short_id = uuid.uuid4().hex[:8]
            folder_name = f"{sanitized_name}_{short_id}"
        else:
            folder_name = sanitized_name

        proj_dir = Path(base_dir) / folder_name
        proj_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)

        project = StoryProject(
            name=sanitized_name,
            project_dir=str(proj_dir.resolve()),
            created_at=now,
            updated_at=now,
            config=ProjectConfig(),
            state=ProjectState()
        )
        ProjectManager.save_project(project)
        return project

    @staticmethod
    def save_project(project: StoryProject) -> None:
        if not project.project_dir:
            raise ValueError("Project directory path is missing.")

        proj_path = Path(project.project_dir)
        proj_path.mkdir(parents=True, exist_ok=True)
        project.updated_at = datetime.now(timezone.utc)

        # 1. Save story.txt
        if project.state.story_raw_text:
            story_file = proj_path / "story.txt"
            with open(story_file, "w", encoding="utf-8") as f:
                f.write(project.state.story_raw_text)

        # 2. Save narration audio file into project directory
        if project.state.audio_file_path and Path(project.state.audio_file_path).exists():
            src_audio = Path(project.state.audio_file_path)
            dest_audio = proj_path / f"narration{src_audio.suffix}"
            if src_audio.resolve() != dest_audio.resolve():
                try:
                    shutil.copy2(src_audio, dest_audio)
                    project.state.audio_file_path = str(dest_audio.resolve())
                except Exception as e:
                    print(f"Notice copying narration audio into project folder: {e}")

        # 3. Save narration_timestamps.json (preserve exact original timestamps)
        if project.state.narration:
            ts_file = proj_path / "narration_timestamps.json"
            with open(ts_file, "w", encoding="utf-8") as f:
                json.dump(project.state.narration.model_dump(), f, indent=2)

        # 4. Save analysis.json
        if project.state.analysis:
            analysis_file = proj_path / "analysis.json"
            with open(analysis_file, "w", encoding="utf-8") as f:
                json.dump(project.state.analysis.model_dump(), f, indent=2)

            # Optional continuity files
            cont = project.state.analysis.continuity
            if cont.character_continuity_needed and cont.characters:
                with open(proj_path / "character_continuity.json", "w", encoding="utf-8") as f:
                    json.dump([c.model_dump() for c in cont.characters], f, indent=2)
            if cont.location_continuity_needed and cont.locations:
                with open(proj_path / "location_continuity.json", "w", encoding="utf-8") as f:
                    json.dump([l.model_dump() for l in cont.locations], f, indent=2)
            if cont.object_continuity_needed and cont.key_objects:
                with open(proj_path / "object_continuity.json", "w", encoding="utf-8") as f:
                    json.dump([o.model_dump() for o in cont.key_objects], f, indent=2)

        # 5. Save exports (timeline.json, image_prompts.txt, image_prompts.json, timeline.csv)
        if project.state.scenes:
            StoryboardExporter.save_all_exports(
                str(proj_path),
                project.state.scenes,
                project.state.narration
            )

        # 6. Save master project.json metadata
        proj_json_data = {
            "name": project.name,
            "version": project.version,
            "created_at": project.created_at.isoformat(),
            "updated_at": project.updated_at.isoformat(),
            "config": project.config.model_dump(),
            "state": {
                "story_file_path": project.state.story_file_path,
                "timestamps_file_path": project.state.timestamps_file_path,
                "audio_file_path": project.state.audio_file_path,
                "last_job_id": project.state.last_job_id,
                "last_generation_status": project.state.last_generation_status,
                "total_scenes": len(project.state.scenes)
            }
        }
        with open(proj_path / "project.json", "w", encoding="utf-8") as f:
            json.dump(proj_json_data, f, indent=2)

        project.state.is_dirty = False

    @staticmethod
    def load_project(project_dir: str) -> StoryProject:
        proj_path = Path(project_dir)
        if not proj_path.exists():
            raise FileNotFoundError(f"Project directory not found: {project_dir}")

        project_json_file = proj_path / "project.json"
        if project_json_file.exists():
            try:
                with open(project_json_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                meta = {}
        else:
            meta = {}

        name = meta.get("name", proj_path.name)
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            created_at = datetime.fromisoformat(meta.get("created_at", now_iso))
        except Exception:
            created_at = datetime.now(timezone.utc)

        try:
            updated_at = datetime.fromisoformat(meta.get("updated_at", now_iso))
        except Exception:
            updated_at = datetime.now(timezone.utc)

        config = ProjectConfig(**meta.get("config", {}))

        state = ProjectState()
        raw_state = meta.get("state", {})
        state.story_file_path = raw_state.get("story_file_path")
        state.timestamps_file_path = raw_state.get("timestamps_file_path")
        state.audio_file_path = raw_state.get("audio_file_path")
        state.last_job_id = raw_state.get("last_job_id")
        state.last_generation_status = raw_state.get("last_generation_status")

        # Fallback check for audio file in project directory
        if not state.audio_file_path or not Path(state.audio_file_path).exists():
            for audio_name in ("narration.wav", "narration.mp3", "voiceover.wav", "voiceover.mp3"):
                candidate = proj_path / audio_name
                if candidate.exists():
                    state.audio_file_path = str(candidate.resolve())
                    break

        # Load story.txt
        story_file = proj_path / "story.txt"
        if story_file.exists():
            try:
                with open(story_file, "r", encoding="utf-8") as f:
                    state.story_raw_text = f.read()
            except Exception as e:
                print(f"Notice reading story.txt: {e}")

        # Load narration_timestamps.json
        ts_file = proj_path / "narration_timestamps.json"
        if ts_file.exists():
            try:
                with open(ts_file, "r", encoding="utf-8") as f:
                    ts_data = json.load(f)
                    state.narration = NarrationData(**ts_data)
            except Exception as e:
                print(f"Notice reading narration_timestamps.json: {e}")

        # Load analysis.json
        analysis_file = proj_path / "analysis.json"
        if analysis_file.exists():
            try:
                with open(analysis_file, "r", encoding="utf-8") as f:
                    analysis_data = json.load(f)
                    state.analysis = StoryAnalysis(**analysis_data)
            except Exception as e:
                print(f"Notice reading analysis.json: {e}")

        # Load storyboard_scenes.json or timeline.json
        scene_files = [proj_path / "storyboard_scenes.json", proj_path / "timeline.json"]
        for sf in scene_files:
            if sf.exists() and not state.scenes:
                try:
                    with open(sf, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    raw_items = []
                    if isinstance(data, list):
                        raw_items = data
                    elif isinstance(data, dict):
                        raw_items = data.get("scenes") or data.get("images") or []

                    scenes = []
                    for item in raw_items:
                        if isinstance(item, dict):
                            sc_id = item.get("scene_id") or item.get("image_id", "001")
                            s = float(item.get("start", 0.0))
                            e = float(item.get("end", 0.0))
                            d = float(item.get("duration", round(e - s, 2)))
                            scene_obj = VisualScene(
                                scene_id=str(sc_id).zfill(3),
                                start=s,
                                end=e,
                                duration=d,
                                start_word_index=item.get("start_word_index"),
                                end_word_index=item.get("end_word_index"),
                                start_word=item.get("start_word"),
                                end_word=item.get("end_word"),
                                narration_excerpt=item.get("narration_excerpt", ""),
                                visual_subject=item.get("visual_subject", ""),
                                visual_purpose=item.get("visual_purpose", ""),
                                framing_suggestion=item.get("framing_suggestion", ""),
                                prompt=item.get("prompt", ""),
                                is_manually_edited=item.get("is_manually_edited", False),
                                is_validated=True
                            )
                            scenes.append(scene_obj)
                    if scenes:
                        state.scenes = scenes
                        break
                except Exception as e:
                    print(f"Notice reading {sf.name}: {e}")

        state.is_dirty = False

        return StoryProject(
            name=name,
            project_dir=str(proj_path.resolve()),
            created_at=created_at,
            updated_at=updated_at,
            config=config,
            state=state
        )

    @staticmethod
    def scan_projects(workspace_dir: str) -> List[Dict[str, Any]]:
        """Scans workspace projects folder and recent history, returning rich summary metadata."""
        p_dir = Path(workspace_dir)
        seen_paths = set()
        projects = []

        dirs_to_check = []
        if p_dir.exists():
            dirs_to_check.append(p_dir)
            for child in p_dir.iterdir():
                if child.is_dir() and child.name not in ("temp", "audio_exports", "__pycache__"):
                    dirs_to_check.append(child)

        # Also check default ./projects folder if workspace_dir differs
        default_p = Path("projects")
        if default_p.resolve() != p_dir.resolve() and default_p.exists():
            for child in default_p.iterdir():
                if child.is_dir() and child.name not in ("temp", "audio_exports", "__pycache__"):
                    dirs_to_check.append(child)

        # Also check recent projects list from Settings
        from app.config.settings import SettingsManager
        settings = SettingsManager.load_settings()
        for rp in settings.recent_projects:
            rp_path = Path(rp)
            if rp_path.exists() and rp_path.is_dir():
                dirs_to_check.append(rp_path)

        for folder in dirs_to_check:
            res_path = str(folder.resolve())
            if res_path in seen_paths or folder.name in ("temp", "audio_exports", "__pycache__"):
                continue
            seen_paths.add(res_path)

            has_proj_json = (folder / "project.json").exists()
            has_story = (folder / "story.txt").exists()
            has_ts = (folder / "narration_timestamps.json").exists()
            has_timeline = (folder / "timeline.json").exists()
            has_unfinished = (folder / ".unfinished_job.json").exists()

            # Check for audio files
            audio_text = "—"
            has_audio = False
            for aname in ("narration.wav", "narration.mp3", "voiceover.wav", "voiceover.mp3"):
                if (folder / aname).exists():
                    has_audio = True
                    break

            # If none of the signature files exist, skip non-project subfolders
            if not (has_proj_json or has_story or has_audio or has_ts or has_timeline or has_unfinished):
                continue

            # Read basic meta
            scene_count = 0
            if has_timeline:
                try:
                    with open(folder / "timeline.json", "r", encoding="utf-8") as f:
                        tl = json.load(f)
                        scene_count = len(tl.get("images", []))
                except Exception:
                    pass

            # Audio info
            if has_ts:
                try:
                    with open(folder / "narration_timestamps.json", "r", encoding="utf-8") as f:
                        ts_info = json.load(f)
                        dur = ts_info.get("duration_seconds", 0.0)
                        wcnt = len(ts_info.get("words", []))
                        audio_text = f"🔊 {dur:.1f}s ({wcnt} w)"
                except Exception:
                    audio_text = "🔊 Available"
            elif has_audio:
                audio_text = "🔊 Audio File"

            # Determine status
            if has_unfinished:
                status_text = "⚠️ Interrupted / Incomplete"
            elif scene_count > 0:
                status_text = f"🟢 Complete ({scene_count} scenes)"
            elif has_audio or has_ts:
                status_text = "🟡 Voiceover Ready (Tab 2)"
            elif has_story:
                status_text = "🔵 Story Ready"
            else:
                status_text = "⚪ Draft"

            # Modified date
            try:
                mtime = folder.stat().st_mtime
                mod_str = datetime.fromtimestamp(mtime).strftime("%b %d, %H:%M")
            except Exception:
                mod_str = "—"

            proj_name = folder.name
            if has_proj_json:
                try:
                    with open(folder / "project.json", "r", encoding="utf-8") as f:
                        p_meta = json.load(f)
                        proj_name = p_meta.get("name", folder.name)
                except Exception:
                    pass

            projects.append({
                "name": proj_name,
                "dir_path": res_path,
                "status_text": status_text,
                "audio_text": audio_text,
                "scene_count": scene_count,
                "modified_str": mod_str,
                "mtime": folder.stat().st_mtime if folder.exists() else 0,
                "has_story": has_story,
                "has_audio": has_audio,
                "has_unfinished": has_unfinished
            })

        # Sort by most recently modified
        projects.sort(key=lambda x: x.get("mtime", 0), reverse=True)
        return projects

    @staticmethod
    def check_for_unfinished_jobs(projects_dir: str) -> List[Tuple[str, str, Dict[str, Any]]]:
        """Scans workspace projects for interrupted/unfinished jobs."""
        p_dir = Path(projects_dir)
        if not p_dir.exists():
            return []

        unfinished = []
        for child in p_dir.iterdir():
            if child.is_dir():
                job_meta_file = child / ".unfinished_job.json"
                if job_meta_file.exists():
                    try:
                        with open(job_meta_file, "r", encoding="utf-8") as f:
                            info = json.load(f)
                        unfinished.append((child.name, str(child.resolve()), info))
                    except Exception:
                        pass
        return unfinished

    @staticmethod
    def mark_job_in_progress(project: StoryProject, job_id: str, stage: str, progress: float) -> None:
        if not project.project_dir:
            return
        meta_file = Path(project.project_dir) / ".unfinished_job.json"
        data = {
            "job_id": job_id,
            "stage": stage,
            "progress": progress,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "project_name": project.name
        }
        try:
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    @staticmethod
    def clear_job_in_progress(project_or_path) -> None:
        if isinstance(project_or_path, StoryProject):
            p_dir = project_or_path.project_dir
        else:
            p_dir = str(project_or_path)

        if not p_dir:
            return

        meta_file = Path(p_dir) / ".unfinished_job.json"
        if meta_file.exists():
            try:
                os.remove(meta_file)
            except Exception:
                pass
