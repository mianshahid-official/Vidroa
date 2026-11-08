"""
Local Multi-Engine Text-to-Speech Engine.
Exclusively powered by local neural models:
1. Kokoro TTS (Native ONNX from models/kokoro/)
2. Piper TTS (Native ONNX from models/piper/)
"""
import asyncio
import io
import os
import re
import wave
import shutil
import tempfile
from pathlib import Path
from typing import List, Tuple, Optional, Callable, Dict

import soundfile as sf

from app.models.timeline import WordTimestamp, NarrationData
from app.models.video_config import TTSVoice, TTSConfig, TTSEngineType


# Models base directory
MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models"
KOKORO_DIR = MODELS_DIR / "kokoro"
PIPER_DIR = MODELS_DIR / "piper"


POPULAR_LANGUAGES = [
    ("all", "🌐 All Available Languages"),
    ("en-US", "🇺🇸 English (United States)"),
    ("en-GB", "🇬🇧 English (United Kingdom)"),
    ("es-ES", "🇪🇸 Spanish (Spain)"),
    ("fr-FR", "🇫🇷 French (France)"),
    ("de-DE", "🇩🇪 German (Germany)"),
    ("it-IT", "🇮🇹 Italian (Italy)"),
    ("pt-BR", "🇧🇷 Portuguese (Brazil)"),
]

VOICE_REGISTRY: List[TTSVoice] = [
    # -------------------------------------------------------------------------
    # KOKORO TTS VOICES (Local ONNX models/kokoro/)
    # -------------------------------------------------------------------------
    TTSVoice(voice_id="kokoro:af", name="Heart (US Female - Flagship Natural)", gender="Female", locale="en-US", language_name="English (United States)", engine=TTSEngineType.KOKORO, description="Kokoro flagship voice. Warm, expressive, human-like narration."),
    TTSVoice(voice_id="kokoro:af_bella", name="Bella (US Female - Soft & Expressive)", gender="Female", locale="en-US", language_name="English (United States)", engine=TTSEngineType.KOKORO, description="Kokoro expressive, soft emotional storytelling."),
    TTSVoice(voice_id="kokoro:af_nicole", name="Nicole (US Female - Clear Narrative)", gender="Female", locale="en-US", language_name="English (United States)", engine=TTSEngineType.KOKORO, description="Kokoro clear modern narrative tone for explainers."),
    TTSVoice(voice_id="kokoro:af_sarah", name="Sarah (US Female - Warm Professional)", gender="Female", locale="en-US", language_name="English (United States)", engine=TTSEngineType.KOKORO, description="Kokoro professional corporate & documentary voice."),
    TTSVoice(voice_id="kokoro:af_sky", name="Sky (US Female - Bright & Dynamic)", gender="Female", locale="en-US", language_name="English (United States)", engine=TTSEngineType.KOKORO, description="Kokoro upbeat, modern storytelling voice."),
    TTSVoice(voice_id="kokoro:am_adam", name="Adam (US Male - Deep Flagship)", gender="Male", locale="en-US", language_name="English (United States)", engine=TTSEngineType.KOKORO, description="Kokoro flagship male. Deep, rich, authoritative documentary narrator."),
    TTSVoice(voice_id="kokoro:am_michael", name="Michael (US Male - Cinematic)", gender="Male", locale="en-US", language_name="English (United States)", engine=TTSEngineType.KOKORO, description="Kokoro cinematic narrative voice."),
    TTSVoice(voice_id="kokoro:bf_emma", name="Emma (UK Female - Classic British)", gender="Female", locale="en-GB", language_name="English (United Kingdom)", engine=TTSEngineType.KOKORO, description="Kokoro graceful British female storytelling."),
    TTSVoice(voice_id="kokoro:bf_isabella", name="Isabella (UK Female - British Elegance)", gender="Female", locale="en-GB", language_name="English (United Kingdom)", engine=TTSEngineType.KOKORO, description="Kokoro sophisticated British RP female."),
    TTSVoice(voice_id="kokoro:bm_george", name="George (UK Male - BBC Documentary)", gender="Male", locale="en-GB", language_name="English (United Kingdom)", engine=TTSEngineType.KOKORO, description="Kokoro classic British documentary voice."),
    TTSVoice(voice_id="kokoro:bm_lewis", name="Lewis (UK Male - Refined Narrator)", gender="Male", locale="en-GB", language_name="English (United Kingdom)", engine=TTSEngineType.KOKORO, description="Kokoro refined British male narrator."),

    # -------------------------------------------------------------------------
    # PIPER TTS VOICES (Local ONNX models/piper/)
    # -------------------------------------------------------------------------
    TTSVoice(voice_id="piper:en_US-lessac-medium", name="Lessac (US Female - High Clarity)", gender="Female", locale="en-US", language_name="English (United States)", engine=TTSEngineType.PIPER, description="Piper lightweight US English female."),
    TTSVoice(voice_id="piper:en_US-libritts_r-medium", name="LibriTTS-R (US Natural Narrator)", gender="Male", locale="en-US", language_name="English (United States)", engine=TTSEngineType.PIPER, description="Piper high quality multi-speaker audiobook voice."),
    TTSVoice(voice_id="piper:en_GB-alan-medium", name="Alan (UK Male - British Voice)", gender="Male", locale="en-GB", language_name="English (United Kingdom)", engine=TTSEngineType.PIPER, description="Piper British English male voice."),
    TTSVoice(voice_id="piper:es_ES-davefx-medium", name="DaveFX (Spanish Male)", gender="Male", locale="es-ES", language_name="Spanish (Spain)", engine=TTSEngineType.PIPER, description="Piper Castilian Spanish male voice."),
    TTSVoice(voice_id="piper:fr_FR-siwis-medium", name="Siwis (French Female)", gender="Female", locale="fr-FR", language_name="French (France)", engine=TTSEngineType.PIPER, description="Piper French neural voice."),
    TTSVoice(voice_id="piper:de_DE-thorsten-medium", name="Thorsten (German Male)", gender="Male", locale="de-DE", language_name="German (Germany)", engine=TTSEngineType.PIPER, description="Piper German neural narrator."),
    TTSVoice(voice_id="piper:it_IT-paola-medium", name="Paola (Italian Female)", gender="Female", locale="it-IT", language_name="Italian (Italy)", engine=TTSEngineType.PIPER, description="Piper Italian neural voice."),
    TTSVoice(voice_id="piper:pt_BR-faber-medium", name="Faber (Brazilian Portuguese Male)", gender="Male", locale="pt-BR", language_name="Portuguese (Brazil)", engine=TTSEngineType.PIPER, description="Piper Brazilian Portuguese voice."),
]


class TTSEngine:
    """Multi-Engine Text-to-Speech synthesis and timestamp engine."""

    _kokoro_instance = None

    @staticmethod
    def get_languages() -> List[Tuple[str, str]]:
        return list(POPULAR_LANGUAGES)

    @staticmethod
    def get_voices(
        locale: Optional[str] = None,
        engine: Optional[TTSEngineType] = None
    ) -> List[TTSVoice]:
        results = []
        for v in VOICE_REGISTRY:
            if locale and locale != "all" and v.locale != locale:
                continue
            if engine and v.engine != engine:
                continue
            results.append(v)
        return results

    @classmethod
    def _estimate_word_timestamps(cls, text: str, total_duration: float) -> List[WordTimestamp]:
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

    @classmethod
    async def synthesize_speech_async(
        cls,
        text: str,
        output_audio_path: str,
        config: Optional[TTSConfig] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Tuple[str, NarrationData]:
        cfg = config or TTSConfig()
        out_path = Path(output_audio_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if cfg.engine == TTSEngineType.PIPER:
            return await cls._synthesize_piper(text, out_path, cfg, progress_callback)
        else:
            return await cls._synthesize_kokoro(text, out_path, cfg, progress_callback)

    @classmethod
    async def _synthesize_kokoro(
        cls,
        text: str,
        out_path: Path,
        cfg: TTSConfig,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Tuple[str, NarrationData]:
        """Native local Kokoro ONNX chunked synthesis from models/kokoro/."""
        from app.core.kokoro_engine import KokoroTTSEngine

        engine = KokoroTTSEngine.get_instance()
        speed = round(1.0 + (cfg.rate_percentage / 100.0), 2)
        speed = max(0.5, min(2.0, speed))

        return engine.synthesize_to_file(
            text=text,
            output_path=str(out_path),
            voice=cfg.voice_id,
            speed=speed,
            progress_callback=progress_callback
        )

    @classmethod
    async def _synthesize_piper(
        cls,
        text: str,
        out_path: Path,
        cfg: TTSConfig,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Tuple[str, NarrationData]:
        """Native local Piper ONNX synthesis from models/piper/."""
        voice_key = cfg.voice_id.replace("piper:", "").strip()
        voice_onnx = PIPER_DIR / f"{voice_key}.onnx"
        voice_json = PIPER_DIR / f"{voice_key}.onnx.json"

        if not voice_onnx.exists():
            matches = list(PIPER_DIR.glob(f"*{voice_key}*.onnx"))
            if matches:
                voice_onnx = matches[0]
                voice_json = voice_onnx.with_suffix(".onnx.json")

        if not voice_onnx.exists():
            raise FileNotFoundError(f"Piper ONNX model not found for '{voice_key}' in {PIPER_DIR}")

        if progress_callback:
            progress_callback(15.0, f"Loading Piper model ({voice_onnx.stem})...")

        import piper

        voice = piper.PiperVoice.load(str(voice_onnx), config_path=str(voice_json))

        if progress_callback:
            progress_callback(40.0, "Synthesizing Piper audio...")

        temp_wav = out_path.with_suffix(".temp.wav")
        with wave.open(str(temp_wav), "wb") as wav_f:
            voice.synthesize_wav(text, wav_f)

        data, sr = sf.read(str(temp_wav))
        sf.write(str(out_path), data, sr)
        if temp_wav.exists():
            temp_wav.unlink()

        total_dur = len(data) / float(sr)

        # Real waveform-level acoustic alignment against synthesized Piper audio
        try:
            from app.core.audio_alignment_engine import AudioAlignmentEngine
            if progress_callback:
                progress_callback(85.0, "Aligning word timestamps to synthesized audio waveform...")
            align_engine = AudioAlignmentEngine()
            narration = align_engine.align_generated_script(
                audio_path=out_path,
                script_text=text,
                engine="auto"
            )
        except Exception as align_err:
            words = cls._estimate_word_timestamps(text, total_dur)
            narration = NarrationData(duration_seconds=round(total_dur, 3), words=words)

        if progress_callback:
            progress_callback(100.0, f"Piper Voiceover complete ({narration.duration_seconds:.1f}s, {len(narration.words)} words) • {narration.alignment_status}")

        return str(out_path.resolve()), narration

    @classmethod
    def synthesize_speech_sync(
        cls,
        text: str,
        output_audio_path: str,
        config: Optional[TTSConfig] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Tuple[str, NarrationData]:
        return asyncio.run(cls.synthesize_speech_async(text, output_audio_path, config, progress_callback))

    @classmethod
    def synthesize_preview_sync(
        cls,
        voice_id: str,
        engine: TTSEngineType,
        output_preview_path: str
    ) -> str:
        """Generates a fast ~1-second voice sample preview."""
        # Find voice name
        v_name = "narrator"
        for v in VOICE_REGISTRY:
            if v.voice_id == voice_id:
                v_name = v.name.split("(")[0].strip()
                break

        preview_text = f"Hello! This is a preview of the {v_name} voice."
        cfg = TTSConfig(engine=engine, voice_id=voice_id)
        out_file, _ = cls.synthesize_speech_sync(preview_text, output_preview_path, cfg)
        return out_file
