"""
Story file loader for plain text and markdown documents.
"""
from pathlib import Path
from typing import Tuple, Dict, Any


class StoryLoader:
    """Reads and validates story narration text from .txt and .md files."""

    @staticmethod
    def load_from_file(file_path: str) -> Tuple[str, Dict[str, Any]]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Story file not found: {file_path}")

        if path.suffix.lower() not in [".txt", ".md", ".text", ".markdown"]:
            raise ValueError(f"Unsupported file format '{path.suffix}'. Please select a .txt or .md file.")

        raw_content = ""
        # Try UTF-8, then UTF-8 with BOM, then Latin-1
        for encoding in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
            try:
                with open(path, "r", encoding=encoding) as f:
                    raw_content = f.read()
                break
            except (UnicodeDecodeError, Exception):
                continue

        if not raw_content.strip():
            raise ValueError(f"Story file '{path.name}' is empty.")

        # Normalize line endings
        normalized_text = raw_content.replace("\r\n", "\n").replace("\r", "\n").strip()
        words = normalized_text.split()

        metadata = {
            "file_name": path.name,
            "file_path": str(path.resolve()),
            "character_count": len(normalized_text),
            "word_count": len(words),
            "estimated_spoken_duration_seconds": round(len(words) / 2.5, 1) # Approx 150 words per minute
        }

        return normalized_text, metadata
