"""
OmniVoice Cloud Gateway Integration
Connects PromptBeast directly to Modal Cloud GPU T4 running k2-fsa/OmniVoice & Faster-Whisper.
"""
import os
import json
import base64
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from app.models.timeline import NarrationData, WordTimestamp
from app.core.timestamp_parser import TimestampParser


DEFAULT_MODAL_URL = "https://joybenny3333--omnivoice-studio-fastapi-app.modal.run"


class OmniVoiceClient:
    """Production client for OmniVoice T4 Modal Cloud TTS & Whisper engine."""

    def __init__(self, base_url: Optional[str] = None):
        raw = (base_url or "").strip().rstrip("/")
        if not raw or not raw.startswith("http") or raw.lower() in ("groq", "none", "null"):
            raw = DEFAULT_MODAL_URL
        if not raw.endswith(".run") and ".modal" in raw:
            raw += ".run"
        self.base_url = raw

    @classmethod
    def get_presets(cls) -> List[Dict[str, Any]]:
        """Loads voice presets from local presets/presets.json or app/presets/presets.json."""
        candidates = [
            Path("presets/presets.json"),
            Path("app/presets/presets.json"),
            Path(__file__).resolve().parent.parent / "presets" / "presets.json"
        ]
        for c in candidates:
            if c.exists():
                try:
                    with open(c, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        return data
                except Exception as e:
                    print(f"Notice loading presets from {c}: {e}")
        return []

    def synthesize_script(
        self,
        text: str,
        voice_id: str = "narrator-deep-en",
        speed: float = 1.0,
        language: str = "en",
        output_dir: Optional[str] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Synthesizes narration script on Modal Cloud GPU.
        Handles both fast-path (<400 chars) and async polling for long scripts.
        Saves speech.mp3, speech.json, and speech.srt to output_dir.
        """
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("Narration script text cannot be empty.")

        if progress_callback:
            progress_callback(10.0, "Sending script to Modal Cloud GPU...")

        payload = {
            "text": clean_text,
            "presetId": voice_id,
            "speed": float(speed),
            "language": language
        }
        payload_bytes = json.dumps(payload).encode("utf-8")

        start_time = time.time()
        data = None

        if len(clean_text) > 400:
            # Long script async path: immune to 150s gateway timeouts
            async_url = f"{self.base_url}/api/tts/generate_async"
            req = urllib.request.Request(
                async_url,
                data=payload_bytes,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                spawn_res = json.loads(resp.read().decode("utf-8"))

            job_id = spawn_res.get("job_id")
            if not job_id:
                raise RuntimeError(f"Modal did not return job_id: {spawn_res}")

            completed = False
            for poll in range(500):
                time.sleep(1.8)
                elapsed = time.time() - start_time
                pct = min(90.0, 20.0 + (elapsed * 0.45))
                if progress_callback:
                    progress_callback(pct, f"Synthesizing voice on T4 GPU ({elapsed:.1f}s)...")

                try:
                    status_url = f"{self.base_url}/api/tts/status/{job_id}"
                    with urllib.request.urlopen(status_url, timeout=15) as s_resp:
                        s_data = json.loads(s_resp.read().decode("utf-8"))

                    st = s_data.get("status")
                    if st == "completed":
                        completed = True
                        data = s_data.get("result", s_data)
                        break
                    elif st == "failed":
                        raise RuntimeError(s_data.get("error", "Modal cloud synthesis failed."))
                except urllib.error.HTTPError as he:
                    print(f"Status poll warning: {he}")
                except Exception as pe:
                    print(f"Status poll note: {pe}")

            if not completed or not data:
                raise TimeoutError("Modal Cloud TTS synthesis timed out.")
        else:
            # Fast path
            gen_url = f"{self.base_url}/api/tts/generate"
            req = urllib.request.Request(
                gen_url,
                data=payload_bytes,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8"))

        if progress_callback:
            progress_callback(95.0, "Extracting audio and word timestamps...")

        # Setup output destination
        out_path = Path(output_dir) if output_dir else Path.cwd() / "output" / f"voice_{int(time.time())}"
        out_path.mkdir(parents=True, exist_ok=True)

        audio_file = out_path / "speech.mp3"
        json_file = out_path / "speech.json"
        srt_file = out_path / "speech.srt"

        # 1. Save MP3
        if data.get("mp3_b64"):
            b64_str = data["mp3_b64"]
            if "," in b64_str:
                b64_str = b64_str.split(",", 1)[1]
            audio_file.write_bytes(base64.b64decode(b64_str))
        elif data.get("audioUrl"):
            audio_url = data["audioUrl"]
            if not audio_url.startswith("http"):
                audio_url = f"{self.base_url}{audio_url}"
            with urllib.request.urlopen(audio_url) as a_resp:
                audio_file.write_bytes(a_resp.read())

        # 2. Save SRT
        if data.get("srt_content"):
            srt_file.write_text(data["srt_content"], encoding="utf-8")

        # 3. Save JSON and parse NarrationData
        narration: Optional[NarrationData] = None
        if data.get("json_content"):
            raw_j = data["json_content"]
            if isinstance(raw_j, str):
                json_file.write_text(raw_j, encoding="utf-8")
            else:
                json_file.write_text(json.dumps(raw_j, indent=2), encoding="utf-8")
            try:
                narration = TimestampParser.load_from_json(str(json_file))
            except Exception as j_err:
                print(f"Notice loading parsed JSON: {j_err}")
        elif data.get("words"):
            raw_words = data["words"]
            dur = raw_words[-1].get("end", 0.0) if raw_words else 0.0
            json_file.write_text(json.dumps({"duration": dur, "words": raw_words}, indent=2), encoding="utf-8")
            try:
                narration = TimestampParser.load_from_json(str(json_file))
            except Exception:
                pass

        if progress_callback:
            progress_callback(100.0, "Voiceover synthesis complete!")

        return {
            "audio_path": str(audio_file.resolve()),
            "json_path": str(json_file.resolve()) if json_file.exists() else None,
            "srt_path": str(srt_file.resolve()) if srt_file.exists() else None,
            "narration": narration
        }

