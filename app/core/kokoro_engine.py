"""
PromptBeast - Local Kokoro-82M High-Fidelity Neural TTS Engine.
Runs 100% locally on CPU / DirectML using ONNX Runtime.
Features intelligent sentence-level chunking, acoustic pause smoothing, and timestamp alignment.
Zero Modal calls required.
"""

import os
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Callable
import numpy as np
import soundfile as sf

from app.models.timeline import WordTimestamp, NarrationData

logger = logging.getLogger("PromptBeast.Kokoro")

MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models" / "kokoro"
KOKORO_SAMPLE_RATE = 24000


class KokoroTTSEngine:
    """High-performance local Kokoro TTS engine with smart chunking."""

    _instance: Optional["KokoroTTSEngine"] = None
    _kokoro_model = None

    def __init__(self):
        self.model_path = MODELS_DIR / "kokoro-v0_19.onnx"
        self.voices_path = MODELS_DIR / "voices.bin"
        if not self.voices_path.exists():
            self.voices_path = MODELS_DIR / "voices-v1.0.bin"

    @classmethod
    def get_instance(cls) -> "KokoroTTSEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_available(self) -> bool:
        """Checks if local Kokoro model files are installed on disk."""
        return self.model_path.exists() and self.voices_path.exists()

    def _ensure_loaded(self):
        """Lazy loads Kokoro-ONNX session."""
        if self._kokoro_model is None:
            if not self.is_available():
                raise FileNotFoundError(
                    f"Kokoro model not found in {MODELS_DIR}. Please ensure kokoro-v0_19.onnx and voices.bin are present."
                )
            import kokoro_onnx
            logger.info(f"Loading local Kokoro ONNX model from {self.model_path}...")
            self._kokoro_model = kokoro_onnx.Kokoro(str(self.model_path), str(self.voices_path))

    @staticmethod
    def chunk_text(text: str, max_chars: int = 220) -> List[str]:
        """
        Splits long narrative scripts into human-sounding sentence chunks <= max_chars.
        Preserves natural prosody and prevents Kokoro ONNX buffer limits.
        """
        cleaned = text.strip()
        if not cleaned:
            return []

        # Split by paragraph first
        paragraphs = [p.strip() for p in cleaned.split("\n") if p.strip()]
        chunks: List[str] = []

        for para in paragraphs:
            # Split paragraph into sentences on punctuation (. ! ?)
            sentences = re.split(r"(?<=[.!?])\s+", para)
            curr_chunk = ""

            for s in sentences:
                s = s.strip()
                if not s:
                    continue

                # If sentence itself exceeds max_chars, split on sub-clauses (, ; :)
                if len(s) > max_chars:
                    if curr_chunk:
                        chunks.append(curr_chunk)
                        curr_chunk = ""

                    clauses = re.split(r"(?<=[,;:\u2014])\s+", s)
                    sub_chunk = ""
                    for c in clauses:
                        if len(sub_chunk) + len(c) + 1 <= max_chars:
                            sub_chunk = f"{sub_chunk} {c}".strip() if sub_chunk else c
                        else:
                            if sub_chunk:
                                chunks.append(sub_chunk)
                            sub_chunk = c
                    if sub_chunk:
                        chunks.append(sub_chunk)
                    continue

                if len(curr_chunk) + len(s) + 1 <= max_chars:
                    curr_chunk = f"{curr_chunk} {s}".strip() if curr_chunk else s
                else:
                    if curr_chunk:
                        chunks.append(curr_chunk)
                    curr_chunk = s

            if curr_chunk:
                chunks.append(curr_chunk)

        return chunks if chunks else [cleaned]

    def synthesize(
        self,
        text: str,
        voice: str = "am_adam",
        speed: float = 1.0,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> Tuple[np.ndarray, int, NarrationData]:
        """
        Synthesizes speech from text locally using sentence chunking.
        Returns (audio_samples, sample_rate, narration_data).
        """
        self._ensure_loaded()

        # Clean voice key
        v_key = voice.replace("kokoro:", "").strip()
        if not v_key:
            v_key = "am_adam"

        # Determine language code
        lang = "en-us"
        if v_key.startswith("ef_") or v_key.startswith("em_"):
            lang = "es"
        elif v_key.startswith("ff_"):
            lang = "fr"
        elif v_key.startswith("hf_") or v_key.startswith("hm_"):
            lang = "hi"
        elif v_key.startswith("bf_") or v_key.startswith("bm_"):
            lang = "en-gb"

        chunks = self.chunk_text(text, max_chars=220)
        total_chunks = len(chunks)

        if total_chunks == 0:
            empty = np.zeros(0, dtype=np.float32)
            return empty, KOKORO_SAMPLE_RATE, NarrationData(duration_seconds=0.0, words=[])

        all_samples = []
        pause_samples = np.zeros(int(KOKORO_SAMPLE_RATE * 0.18), dtype=np.float32)

        for idx, chunk in enumerate(chunks):
            if progress_callback:
                pct = 10.0 + ((idx / total_chunks) * 80.0)
                progress_callback(pct, f"Synthesizing Kokoro chunk {idx+1}/{total_chunks} ({v_key})...")

            samples, sr = self._kokoro_model.create(
                text=chunk,
                voice=v_key,
                speed=max(0.5, min(2.0, speed)),
                lang=lang
            )
            all_samples.append(samples.astype(np.float32))

            # Add acoustic pause between chunks
            if idx < total_chunks - 1:
                all_samples.append(pause_samples)

        combined_audio = np.concatenate(all_samples)
        total_duration = len(combined_audio) / float(KOKORO_SAMPLE_RATE)

        # Word-level timestamp estimation across entire narration
        words = self._estimate_word_timestamps(text, total_duration)
        narration = NarrationData(
            duration_seconds=round(total_duration, 3),
            words=words
        )

        if progress_callback:
            progress_callback(100.0, f"Kokoro synthesis complete ({total_duration:.1f}s, {len(words)} words)")

        return combined_audio, KOKORO_SAMPLE_RATE, narration

    def synthesize_to_file(
        self,
        text: str,
        output_path: str,
        voice: str = "am_adam",
        speed: float = 1.0,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> Tuple[str, NarrationData]:
        """Synthesizes text directly to a target audio file on disk."""
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        samples, sr, narration = self.synthesize(
            text=text,
            voice=voice,
            speed=speed,
            progress_callback=progress_callback
        )

        sf.write(str(out_p), samples, sr)

        # Real waveform-level acoustic alignment against synthesized audio
        try:
            from app.core.audio_alignment_engine import AudioAlignmentEngine
            if progress_callback:
                progress_callback(92.0, "Aligning word timestamps to synthesized audio waveform...")
            align_engine = AudioAlignmentEngine()
            aligned_narration = align_engine.align_generated_script(
                audio_path=out_p,
                script_text=text,
                engine="auto"
            )
            narration = aligned_narration
        except Exception as align_err:
            logger.warning(f"Acoustic alignment fallback to preliminary estimation: {align_err}")

        if progress_callback:
            progress_callback(100.0, f"Kokoro synthesis complete ({narration.duration_seconds:.1f}s, {len(narration.words)} words) • {narration.alignment_status}")

        return str(out_p.resolve()), narration

    def get_supported_voices(self) -> List[Dict[str, str]]:
        """Curated list of premium Kokoro voices."""
        return [
            {"id": "am_adam", "name": "Adam (US Male - Deep Authoritative Documentary)", "gender": "Male", "accent": "US Documentary"},
            {"id": "am_michael", "name": "Michael (US Male - Cinematic Storytelling)", "gender": "Male", "accent": "US Cinematic"},
            {"id": "am_fenrir", "name": "Fenrir (US Male - Intense Narrative)", "gender": "Male", "accent": "US Deep"},
            {"id": "am_echo", "name": "Echo (US Male - Modern Warm Explainer)", "gender": "Male", "accent": "US Explainer"},
            {"id": "am_eric", "name": "Eric (US Male - Clear Announcer)", "gender": "Male", "accent": "US Announcer"},
            {"id": "am_liam", "name": "Liam (US Male - Conversational Youth)", "gender": "Male", "accent": "US Conversational"},
            {"id": "am_onyx", "name": "Onyx (US Male - Deep Bass Narration)", "gender": "Male", "accent": "US Bass"},
            {"id": "af_bella", "name": "Bella (US Female - Warm & Expressive)", "gender": "Female", "accent": "US Warm"},
            {"id": "af_sarah", "name": "Sarah (US Female - Professional Corporate)", "gender": "Female", "accent": "US Corporate"},
            {"id": "af_nicole", "name": "Nicole (US Female - Clear Narrative)", "gender": "Female", "accent": "US Narrative"},
            {"id": "af_sky", "name": "Sky (US Female - Bright & Dynamic)", "gender": "Female", "accent": "US Upbeat"},
            {"id": "af_heart", "name": "Heart (US Female - Flagship Natural)", "gender": "Female", "accent": "US Flagship"},
            {"id": "af_alloy", "name": "Alloy (US Female - Balanced Explainer)", "gender": "Female", "accent": "US Explainer"},
            {"id": "ef_dora", "name": "Dora (Spanish Female)", "gender": "Female", "accent": "Spanish"},
            {"id": "em_alex", "name": "Alex (Spanish Male)", "gender": "Male", "accent": "Spanish"},
            {"id": "ff_siwis", "name": "Siwis (French Female)", "gender": "Female", "accent": "French"},
            {"id": "hf_alpha", "name": "Alpha (Hindi Female)", "gender": "Female", "accent": "Hindi"},
            {"id": "hm_omega", "name": "Omega (Hindi Male)", "gender": "Male", "accent": "Hindi"},
        ]

    @staticmethod
    def _estimate_word_timestamps(text: str, total_duration: float) -> List[WordTimestamp]:
        """Calculates proportional word timestamps based on character lengths."""
        words = [w for w in re.split(r"\s+", text.strip()) if w]
        if not words:
            return []

        weights = []
        for w in words:
            weight = len(w) + (2.0 if w[-1] in ".,!?;:" else 0.0)
            weights.append(max(1.0, weight))

        total_weight = sum(weights)
        current_t = 0.0
        result: List[WordTimestamp] = []

        for w, weight in zip(words, weights):
            dur = (weight / total_weight) * total_duration
            start_t = current_t
            end_t = current_t + dur
            result.append(WordTimestamp(
                word=w,
                start=round(start_t, 3),
                end=round(end_t, 3)
            ))
            current_t = end_t

        return result

