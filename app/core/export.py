"""
Export engine for generating image_prompts.txt, timeline.json, image_prompts.json, and CSV formats.
"""
import csv
import json
import io
import re
import sys
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any
from app.models.scene import VisualScene
from app.models.timeline import NarrationData


def copy_to_system_clipboard(text: str) -> bool:
    """
    Safely copies text to the operating system clipboard using both Qt and
    native OS fallbacks (Windows clip.exe) to guarantee delivery regardless
    of window focus or OLE delays.
    """
    if not text:
        return False

    success = False

    # 1. PySide6 / Qt Clipboard
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QClipboard
        app = QApplication.instance()
        if app:
            cb = app.clipboard()
            cb.setText(text, mode=QClipboard.Mode.Clipboard)
            success = True
    except Exception as e:
        print(f"[Clipboard] Qt copy notice: {e}")

    # 2. Windows native clip.exe fallback (100% reliable on Windows OS)
    if sys.platform == "win32":
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            p = subprocess.Popen(
                ["clip"],
                stdin=subprocess.PIPE,
                shell=False,
                startupinfo=startupinfo,
                creationflags=creationflags
            )
            p.communicate(input=text.encode("utf-16le"))
            if p.returncode == 0:
                success = True
        except Exception as e:
            print(f"[Clipboard] Windows clip.exe notice: {e}")

    return success


class StoryboardExporter:
    """Exports validated timelines and prompts into production-standard file formats."""

    @classmethod
    def export_to_text(cls, scenes: List[VisualScene]) -> str:
        """
        Generates production-standard image_prompts.txt matching the exact format:
        IMAGE 001
        START: 0.20
        END: 3.78
        DURATION: 3.58

        NARRATION:
        [narration excerpt]

        PROMPT:
        [full prompt]

        ---
        """
        blocks = []
        for sc in scenes:
            narration_block = sc.narration_excerpt.strip() if sc.narration_excerpt else "[No spoken narration for this segment]"
            raw_p = sc.prompt.strip() if sc.prompt else "[No prompt defined]"
            prompt_block = cls.clean_prompt_single_line(raw_p) if raw_p != "[No prompt defined]" else raw_p
            block = (
                f"IMAGE {sc.scene_id}\n"
                f"START: {sc.start:.2f}\n"
                f"END: {sc.end:.2f}\n"
                f"DURATION: {sc.duration:.2f}\n\n"
                f"NARRATION:\n"
                f"{narration_block}\n\n"
                f"PROMPT:\n"
                f"{prompt_block}"
            )
            blocks.append(block)

        return "\n\n---\n\n".join(blocks)

    @staticmethod
    def export_to_timeline_json(
        scenes: List[VisualScene],
        narration: Optional[NarrationData] = None,
        total_duration: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Generates timeline.json matching section 24 specifications:
        {
          "duration_seconds": 98.2,
          "images": [
            {
              "image_id": "001",
              "start": 0.2,
              "end": 3.78,
              "duration": 3.58,
              "start_word_index": 0,
              "end_word_index": 5,
              "start_word": "A",
              "end_word": "their",
              "visual_subject": "...",
              "prompt": "..."
            }
          ]
        }
        """
        dur = total_duration
        if dur is None:
            if narration:
                dur = narration.duration_seconds
            elif scenes:
                dur = round(scenes[-1].end - scenes[0].start, 3)
            else:
                dur = 0.0

        images_list = []
        for sc in scenes:
            start_word = sc.start_word
            end_word = sc.end_word
            if narration and narration.words:
                if sc.start_word_index is not None and 0 <= sc.start_word_index < len(narration.words):
                    start_word = narration.words[sc.start_word_index].word
                if sc.end_word_index is not None and 0 <= sc.end_word_index < len(narration.words):
                    end_word = narration.words[sc.end_word_index].word

            img_entry = {
                "image_id": sc.scene_id,
                "start": sc.start,
                "end": sc.end,
                "duration": sc.duration,
                "start_word_index": sc.start_word_index,
                "end_word_index": sc.end_word_index,
                "start_word": start_word,
                "end_word": end_word,
                "visual_subject": sc.visual_subject,
                "visual_purpose": sc.visual_purpose,
                "framing_suggestion": sc.framing_suggestion,
                "prompt": sc.prompt,
                "is_manually_edited": sc.is_manually_edited
            }
            images_list.append(img_entry)

        return {
            "duration_seconds": dur,
            "total_images": len(scenes),
            "images": images_list
        }

    @staticmethod
    def export_to_image_prompts_json(scenes: List[VisualScene]) -> Dict[str, Any]:
        """Generates clean image_prompts.json optimized for direct ingestion by batch image generators."""
        prompts = [
            {
                "scene_id": sc.scene_id,
                "start": sc.start,
                "end": sc.end,
                "duration": sc.duration,
                "prompt": sc.prompt,
                "visual_subject": sc.visual_subject,
                "is_manually_edited": sc.is_manually_edited
            }
            for sc in scenes
        ]
        return {
            "total_prompts": len(prompts),
            "prompts": prompts
        }

    @staticmethod
    def export_to_csv(scenes: List[VisualScene]) -> str:
        """Generates CSV string format of scenes."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Scene ID", "Start (s)", "End (s)", "Duration (s)",
            "Visual Subject", "Narration Excerpt", "Prompt", "Manually Edited"
        ])
        for sc in scenes:
            writer.writerow([
                sc.scene_id,
                f"{sc.start:.2f}",
                f"{sc.end:.2f}",
                f"{sc.duration:.2f}",
                sc.visual_subject,
                sc.narration_excerpt,
                sc.prompt,
                "YES" if sc.is_manually_edited else "NO"
            ])
        return output.getvalue()

    @staticmethod
    def clean_prompt_single_line(raw: str) -> str:
        """
        Collapses a prompt into a strictly single line.
        Strips surrounding wrappers [(Story: ...) ... Scene: <actual prompt>], /imagine prefixes,
        and internal newlines.
        """
        if not raw:
            return ""
        p = raw.strip()
        if "Scene:" in p:
            scene_part = p.split("Scene:", 1)[1].strip()
            if scene_part.endswith("]"):
                scene_part = scene_part[:-1].strip()
            p = scene_part
        elif p.startswith("[") and p.endswith("]"):
            p = p[1:-1].strip()

        # Remove /imagine prefixes and parameter flags
        p = re.sub(r"^/imagine\s+prompt:\s*", "", p, flags=re.IGNORECASE)
        p = re.sub(r"^/imagine\s*", "", p, flags=re.IGNORECASE)
        p = re.sub(r"\[Planned Visual Shot\s*[—-]\s*Awaiting Batch Prompt Gen\]\s*", "", p, flags=re.IGNORECASE)
        p = re.sub(r"--ar\s+\d+:\d+", "", p, flags=re.IGNORECASE)
        p = re.sub(r"--style\s+\w+", "", p, flags=re.IGNORECASE)
        p = re.sub(r"--v\s+[\d\.]+", "", p, flags=re.IGNORECASE)
        p = re.sub(r"--stylize\s+\d+", "", p, flags=re.IGNORECASE)

        return " ".join(p.split())

    @classmethod
    def export_to_prompts_only(cls, scenes: List[VisualScene], thumbnail_prompt: Optional[str] = None) -> str:
        """
        Generates clean prompts_only.txt:
        Each prompt is strictly on a single clean line (1 scene = 1 line), extracting the pure
        visual prompt starting directly from Scene 001. No thumbnail prompt.
        Single batch for all prompts with 2-digit zero-padded numbering: '01 ', '02 ' ... '100 ', '137 '.
        """
        lines = []
        for idx, sc in enumerate(scenes):
            raw = sc.prompt.strip() if sc.prompt else (sc.visual_subject or "")
            clean_p = cls.clean_prompt_single_line(raw)
            # Remove any existing leading numbers or scene prefixes to prevent duplicate numbering
            clean_p = re.sub(r"^(?:scene\s*)?\d+[\.\:\s\-]+", "", clean_p, flags=re.IGNORECASE).strip()
            if clean_p:
                prefix = f"{idx + 1:02d} "
                lines.append(f"{prefix}{clean_p}")
        return "\n".join(lines) + ("\n" if lines else "")

    @classmethod
    def save_all_exports(
        cls,
        output_dir: str,
        scenes: List[VisualScene],
        narration: Optional[NarrationData] = None,
        thumbnail_prompt: Optional[str] = None
    ) -> Dict[str, str]:
        """Saves all export files to the target directory."""
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        txt_file = out_path / "image_prompts.txt"
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write(cls.export_to_text(scenes))

        timeline_json_file = out_path / "timeline.json"
        with open(timeline_json_file, "w", encoding="utf-8") as f:
            json.dump(cls.export_to_timeline_json(scenes, narration), f, indent=2)

        prompts_json_file = out_path / "image_prompts.json"
        with open(prompts_json_file, "w", encoding="utf-8") as f:
            json.dump(cls.export_to_image_prompts_json(scenes), f, indent=2)

        csv_file = out_path / "timeline.csv"
        with open(csv_file, "w", encoding="utf-8") as f:
            f.write(cls.export_to_csv(scenes))

        prompts_only_file = out_path / "prompts_only.txt"
        with open(prompts_only_file, "w", encoding="utf-8") as f:
            f.write(cls.export_to_prompts_only(scenes, thumbnail_prompt=thumbnail_prompt))

        # Also keep a copy in workspace root
        try:
            with open("prompts_only.txt", "w", encoding="utf-8") as f:
                f.write(cls.export_to_prompts_only(scenes, thumbnail_prompt=thumbnail_prompt))
        except Exception:
            pass

        return {
            "text": str(txt_file),
            "timeline_json": str(timeline_json_file),
            "prompts_json": str(prompts_json_file),
            "csv": str(csv_file),
            "prompts_only": str(prompts_only_file)
        }


# Aliases for backwards compatibility and ease of import
ExportManager = StoryboardExporter
save_all_exports = StoryboardExporter.save_all_exports
