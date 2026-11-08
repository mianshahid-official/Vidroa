"""
Parser and estimator for word-level narration timestamps.
"""
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from app.models.timeline import WordTimestamp, NarrationData, AlignmentStatus, AlignmentQuality


class TimestampParser:
    """Parses and validates word-level narration timestamp JSON files and provides fallback estimation."""

    @staticmethod
    def load_from_json(file_path: str) -> NarrationData:
        """Loads and parses word timestamps from JSON file (standardized or legacy)."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Timestamp file not found: {file_path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError("Timestamp JSON root must be an object containing word timestamps.")

        # Check if it has standardized fields
        if "schema_version" in data or "words" in data:
            return NarrationData.from_standard_dict(data)

        # Support 'segments' containing words
        raw_words = data.get("words", [])
        if not raw_words and "segments" in data:
            raw_words = []
            for seg in data["segments"]:
                raw_words.extend(seg.get("words", []))

        if not isinstance(raw_words, list) or not raw_words:
            raise ValueError("Timestamp JSON missing valid 'words' array.")

        raw_dur = data.get("duration_seconds", data.get("duration", 0.0))
        duration_seconds = float(raw_dur) if raw_dur else 0.0
        if duration_seconds <= 0.0 and raw_words:
            last_w = raw_words[-1]
            if isinstance(last_w, dict) and "end" in last_w:
                duration_seconds = float(last_w["end"])

        words: List[WordTimestamp] = []
        last_end = 0.0

        for i, item in enumerate(raw_words):
            if not isinstance(item, dict) or "word" not in item or "start" not in item or "end" not in item:
                raise ValueError(f"Word entry at index {i} is malformed: {item}")

            word_text = str(item["word"]).strip()
            start_t = float(item["start"])
            end_t = float(item["end"])

            # Safety checks for monotonicity
            if end_t < start_t:
                end_t = start_t + 0.1
            if start_t < last_end:
                start_t = max(0.0, last_end)
                if end_t <= start_t:
                    end_t = start_t + 0.1

            last_end = end_t
            words.append(WordTimestamp(
                word=word_text,
                start=round(start_t, 3),
                end=round(end_t, 3),
                index=item.get("index", i),
                confidence=float(item["confidence"]) if "confidence" in item and item["confidence"] is not None else None
            ))

        if words and words[-1].end > duration_seconds:
            duration_seconds = words[-1].end

        return NarrationData(
            duration_seconds=round(duration_seconds, 3),
            words=words,
            alignment_status=data.get("alignment_status", AlignmentStatus.STRUCTURALLY_VALID.value)
        )

    @staticmethod
    def save_to_json(narration: NarrationData, file_path: str) -> str:
        """Saves NarrationData to standardized JSON format."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(narration.to_standard_json(indent=2))
        return str(path.resolve())

    @staticmethod
    def estimate_from_text(story_text: str, words_per_minute: float = 145.0) -> NarrationData:
        """
        Generates estimated word-level timestamps from raw story text ONLY as a preview fallback
        when no audio file has been generated or uploaded.
        """
        tokens = story_text.split()
        if not tokens:
            return NarrationData(duration_seconds=0.0, words=[])

        base_word_duration = 60.0 / words_per_minute  # ~0.414 seconds per word
        current_time = 0.2  # Small initial silence
        words: List[WordTimestamp] = []

        for i, token in enumerate(tokens):
            clean_word = token.strip()
            if not clean_word:
                continue

            char_len = len(clean_word)
            duration_factor = 0.85 if char_len <= 3 else (1.2 if char_len >= 8 else 1.0)
            word_duration = base_word_duration * duration_factor

            start_t = current_time
            end_t = start_t + word_duration

            words.append(WordTimestamp(
                word=clean_word,
                start=round(start_t, 3),
                end=round(end_t, 3),
                index=i,
                confidence=0.5
            ))

            pause = 0.05
            if clean_word.endswith((".", "!", "?")):
                pause = 0.45
            elif clean_word.endswith((",", ";", ":", "—", "-")):
                pause = 0.25

            current_time = end_t + pause

        total_duration = round(current_time, 3)
        quality = AlignmentQuality(
            status=AlignmentStatus.ALIGNMENT_DEGRADED.value,
            warnings=["Timestamps estimated from text token duration; synthesize voiceover or upload audio for true waveform alignment."],
            unaligned_words=0,
            coverage_ratio=1.0,
            mean_duration_error=0.0
        )
        return NarrationData(
            duration_seconds=total_duration,
            words=words,
            source_type="generated_script",
            alignment_engine="text-cadence-estimator",
            alignment_status=AlignmentStatus.ALIGNMENT_DEGRADED.value,
            alignment_quality=quality
        )
