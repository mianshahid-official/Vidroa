"""
Data models for timestamps, narration words, and standardized timeline representations.
"""
import json
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, model_validator


class AlignmentStatus(str, Enum):
    STRUCTURALLY_VALID = "STRUCTURALLY_VALID"
    ALIGNMENT_COMPLETED = "ALIGNMENT_COMPLETED"
    ALIGNMENT_VERIFIED = "ALIGNMENT_VERIFIED"
    ALIGNMENT_DEGRADED = "ALIGNMENT_DEGRADED"
    ALIGNMENT_FAILED = "ALIGNMENT_FAILED"


class AlignmentQuality(BaseModel):
    status: str = Field(AlignmentStatus.STRUCTURALLY_VALID.value, description="Validation summary status")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings encountered during validation")
    unaligned_words: int = Field(0, description="Count of words missing direct acoustic matches")
    coverage_ratio: float = Field(1.0, ge=0.0, le=1.0, description="Ratio of script words matched to acoustic speech (0.0 - 1.0)")
    mean_duration_error: float = Field(0.0, description="Mean difference between speech duration and audio file duration")


class WordTimestamp(BaseModel):
    word: str = Field(..., description="The spoken word text")
    start: float = Field(..., ge=0.0, description="Start timestamp in seconds")
    end: float = Field(..., ge=0.0, description="End timestamp in seconds")
    index: Optional[int] = Field(None, description="0-based sequential word index")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Acoustic alignment confidence score (0.0 - 1.0)")

    @model_validator(mode="after")
    def validate_time_order(self):
        if self.end < self.start:
            raise ValueError(f"Word end timestamp ({self.end}) must be >= start timestamp ({self.start})")
        return self


class NarrationData(BaseModel):
    duration_seconds: float = Field(..., ge=0.0, description="Total narration audio duration in seconds")
    words: List[WordTimestamp] = Field(default_factory=list, description="Ordered list of word-level timestamps")
    schema_version: str = Field("1.0", description="Standardized schema version")
    source_type: str = Field("generated_script", description="Source of narration: 'generated_script' or 'uploaded_audio'")
    audio_file: Optional[str] = Field(None, description="Filename or relative path to the audio file")
    audio_hash: Optional[str] = Field(None, description="SHA256 hash of the audio file")
    transcript: Optional[str] = Field(None, description="Full story or transcription text")
    alignment_engine: Optional[str] = Field(None, description="Name of the alignment engine (e.g., faster-whisper-base, groq-whisper)")
    alignment_status: str = Field(AlignmentStatus.STRUCTURALLY_VALID.value, description="Status of alignment verification")
    alignment_quality: Optional[AlignmentQuality] = Field(None, description="Alignment quality metrics and audit warnings")

    @model_validator(mode="after")
    def ensure_indices_and_transcript(self):
        # Auto-assign 0-based word indices if not populated
        for i, w in enumerate(self.words):
            if w.index is None:
                w.index = i
        # Populate transcript from words if missing
        if not self.transcript and self.words:
            self.transcript = " ".join(w.word for w in self.words)
        return self

    @property
    def total_words(self) -> int:
        return len(self.words)

    @property
    def raw_text(self) -> str:
        if self.transcript:
            return self.transcript
        return " ".join(w.word for w in self.words)

    @property
    def is_verified(self) -> bool:
        return self.alignment_status == AlignmentStatus.ALIGNMENT_VERIFIED.value

    @property
    def is_degraded(self) -> bool:
        return self.alignment_status == AlignmentStatus.ALIGNMENT_DEGRADED.value

    @property
    def is_failed(self) -> bool:
        return self.alignment_status == AlignmentStatus.ALIGNMENT_FAILED.value

    def get_excerpt(self, start_idx: int, end_idx: int) -> str:
        if not self.words:
            return ""
        clamped_start = max(0, min(start_idx, len(self.words) - 1))
        clamped_end = max(clamped_start, min(end_idx, len(self.words) - 1))
        return " ".join(w.word for w in self.words[clamped_start:clamped_end + 1])

    def get_excerpt_by_time(self, start_time: float, end_time: float) -> str:
        """Returns spoken words within or overlapping the given [start_time, end_time] window."""
        if not self.words:
            return ""
        matching = [
            w.word for w in self.words
            if (w.start >= start_time - 0.25 and w.end <= end_time + 0.25) or
               (w.start <= start_time and w.end >= end_time) or
               (w.start < end_time and w.end > start_time)
        ]
        if matching:
            return " ".join(matching)
        # Fallback to nearest word
        for w in self.words:
            if w.end >= start_time:
                return w.word
        return self.words[-1].word if self.words else ""

    def to_standard_dict(self) -> Dict[str, Any]:
        """Exports standardized machine-readable JSON dictionary."""
        quality_dict = None
        if self.alignment_quality:
            quality_dict = self.alignment_quality.model_dump()
        else:
            quality_dict = {
                "status": self.alignment_status,
                "warnings": [],
                "unaligned_words": 0,
                "coverage_ratio": 1.0,
                "mean_duration_error": 0.0
            }

        return {
            "schema_version": self.schema_version,
            "source_type": self.source_type,
            "audio_file": self.audio_file,
            "audio_hash": self.audio_hash,
            "transcript": self.transcript or self.raw_text,
            "duration_seconds": round(float(self.duration_seconds), 3),
            "alignment_engine": self.alignment_engine,
            "alignment_status": self.alignment_status,
            "alignment_quality": quality_dict,
            "words": [
                {
                    "index": i if w.index is None else w.index,
                    "word": w.word,
                    "start": round(float(w.start), 3),
                    "end": round(float(w.end), 3),
                    "confidence": round(float(w.confidence), 3) if w.confidence is not None else None
                }
                for i, w in enumerate(self.words)
            ]
        }

    def to_standard_json(self, indent: int = 2) -> str:
        """Serializes to formatted standardized JSON string."""
        return json.dumps(self.to_standard_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_standard_dict(cls, data: Dict[str, Any]) -> "NarrationData":
        """Reconstructs NarrationData from standardized dictionary or legacy format."""
        raw_words = data.get("words", [])
        if not raw_words and "segments" in data:
            raw_words = []
            for seg in data.get("segments", []):
                raw_words.extend(seg.get("words", []))

        dur = data.get("duration_seconds", data.get("duration", 0.0))
        duration_seconds = float(dur) if dur else 0.0
        if duration_seconds <= 0.0 and raw_words:
            last_item = raw_words[-1]
            if isinstance(last_item, dict) and "end" in last_item:
                duration_seconds = float(last_item["end"])

        word_objs: List[WordTimestamp] = []
        for i, item in enumerate(raw_words):
            if isinstance(item, dict):
                w_str = str(item.get("word", "")).strip()
                s_t = float(item.get("start", 0.0))
                e_t = float(item.get("end", s_t + 0.1))
                idx = item.get("index", i)
                conf = item.get("confidence")
                conf_val = float(conf) if conf is not None else None
                if e_t < s_t:
                    e_t = s_t + 0.1
                word_objs.append(WordTimestamp(
                    word=w_str,
                    start=round(s_t, 3),
                    end=round(e_t, 3),
                    index=idx,
                    confidence=conf_val
                ))

        qual_raw = data.get("alignment_quality")
        quality_obj = None
        if isinstance(qual_raw, dict):
            quality_obj = AlignmentQuality(**qual_raw)

        return cls(
            schema_version=data.get("schema_version", "1.0"),
            source_type=data.get("source_type", "generated_script"),
            audio_file=data.get("audio_file"),
            audio_hash=data.get("audio_hash"),
            transcript=data.get("transcript"),
            duration_seconds=round(duration_seconds, 3),
            alignment_engine=data.get("alignment_engine"),
            alignment_status=data.get("alignment_status", AlignmentStatus.STRUCTURALLY_VALID.value),
            alignment_quality=quality_obj,
            words=word_objs
        )

    @classmethod
    def from_standard_json(cls, json_path_or_str: Union[str, Path]) -> "NarrationData":
        """Loads and parses from a JSON file path or raw JSON string."""
        p = Path(json_path_or_str)
        if p.exists() and p.is_file():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json.loads(str(json_path_or_str))

        return cls.from_standard_dict(data)
