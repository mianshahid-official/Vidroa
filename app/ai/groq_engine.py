"""
Groq AI & Whisper Engine for PromptBeast.
Provides ultra-fast local LLM inference with multi-key rotation and audio transcription with word-level timestamps.
"""
import json
import os
import re
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import httpx

from app.models.timeline import NarrationData, WordTimestamp
from backend.inference.engine import BaseInferenceEngine, JSONParseError


DEFAULT_GROQ_MODELS = [
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b"
]


def _parse_duration_string(val: str) -> Optional[float]:
    """Parses duration strings like '202ms', '17.4s', '7m12s', or '15' into seconds."""
    if not val:
        return None
    val = val.strip()
    try:
        return float(val)
    except ValueError:
        pass
    total = 0.0
    matched = False
    m = re.search(r'([\d\.]+)\s*m(?:in)?(?![a-z])', val, re.IGNORECASE)
    if m:
        total += float(m.group(1)) * 60.0
        matched = True
    s = re.search(r'([\d\.]+)\s*s(?:ec)?(?![a-z])', val, re.IGNORECASE)
    if s:
        total += float(s.group(1))
        matched = True
    ms = re.search(r'([\d\.]+)\s*ms', val, re.IGNORECASE)
    if ms:
        total += float(ms.group(1)) / 1000.0
        matched = True
    return total if matched else None


def parse_groq_retry_after(headers: Optional[Dict[str, str]] = None, text: Optional[str] = None) -> float:
    """
    Extracts the real wait time in seconds from Groq rate limit responses.
    Checks explicit error body ('try again in Xs' or 'try again in Xms') or HTTP 'retry-after' header.
    Does NOT use x-ratelimit-reset-tokens (which is rolling 60s quota window, not retry delay).
    """
    if text:
        m_s = re.search(r'try again in ([\d\.]+)\s*s', text, re.IGNORECASE)
        if m_s:
            return max(0.5, float(m_s.group(1)))
        m_ms = re.search(r'try again in ([\d\.]+)\s*ms', text, re.IGNORECASE)
        if m_ms:
            return max(0.5, float(m_ms.group(1)) / 1000.0)

    if headers:
        ra = headers.get("retry-after") or headers.get("Retry-After")
        if ra:
            try:
                return max(0.5, float(ra))
            except ValueError:
                pass
        reset_req = headers.get("x-ratelimit-reset-requests") or headers.get("X-RateLimit-Reset-Requests")
        if reset_req:
            dur = _parse_duration_string(reset_req)
            if dur is not None and dur > 0:
                return max(0.5, dur)

    return 2.0


class GroqMultiKeyManager:
    """Manages a pool of Groq API keys with cooldown tracking and rate-limit rotation."""

    def __init__(self, keys: Optional[List[str]] = None):
        self.keys: List[str] = []
        if keys:
            self.keys = [k.strip() for k in keys if k and k.strip().startswith("gsk_")]

        # If no keys provided, attempt to auto-discover from groq api.txt or env
        if not self.keys:
            self._auto_load_keys()

        self._current_index = 0
        self._cooldowns: Dict[str, float] = {}

    def mark_key_cooldown(self, key: str, wait_seconds: float):
        """Marks a key in temporary cooldown according to Groq's real retry-after."""
        self._cooldowns[key] = time.time() + max(1.0, wait_seconds)

    def mark_key_invalid(self, key: str):
        """Marks key as invalid (auth error) for 24 hours."""
        self._cooldowns[key] = time.time() + 86400.0

    def get_current_key(self) -> str:
        if not self.keys:
            return ""
        return self.keys[self._current_index % len(self.keys)]

    def get_available_key(self) -> Tuple[str, float]:
        """
        Finds the next key ready for use.
        Returns (key, wait_seconds_needed).
        If an available key is found immediately, wait_seconds_needed is 0.0.
        If all keys are in cooldown, returns the key that will become ready earliest,
        along with the remaining seconds to wait.
        """
        if not self.keys:
            return ("", 0.0)

        now = time.time()
        num_keys = len(self.keys)

        # 1. Search for any key that is not in cooldown
        for i in range(num_keys):
            idx = (self._current_index + i) % num_keys
            candidate = self.keys[idx]
            ready_at = self._cooldowns.get(candidate, 0.0)
            if now >= ready_at:
                self._current_index = idx
                return (candidate, 0.0)

        # 2. All keys in cooldown. Find the one with earliest ready_at
        best_idx = self._current_index
        min_ready = float("inf")
        for i, candidate in enumerate(self.keys):
            ready_at = self._cooldowns.get(candidate, 0.0)
            if ready_at < min_ready:
                min_ready = ready_at
                best_idx = i

        self._current_index = best_idx
        best_key = self.keys[best_idx]
        wait_needed = max(0.1, min_ready - now)
        return (best_key, wait_needed)

    def _auto_load_keys(self):
        # 1. Check environment variables
        env_keys = os.environ.get("GROQ_API_KEYS") or os.environ.get("GROQ_API_KEY")
        if env_keys:
            for k in env_keys.split(","):
                k = k.strip()
                if k.startswith("gsk_") and k not in self.keys:
                    self.keys.append(k)

        # 2. Check known text files in workspace and parent folders
        candidate_files = [
            Path("groq api.txt"),
            Path("../groq api.txt"),
            Path("d:/AntiGravity/groq api.txt"),
            Path("d:/AntiGravity/Prompts Beast/groq api.txt"),
        ]
        for cf in candidate_files:
            if cf.exists():
                try:
                    with open(cf, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("gsk_") and line not in self.keys:
                                self.keys.append(line)
                except Exception:
                    pass

    def rotate_key(self) -> str:
        """Rotates to the next available API key in the pool."""
        if not self.keys:
            return ""
        self._current_index = (self._current_index + 1) % len(self.keys)
        return self.get_current_key()

    def total_keys(self) -> int:
        return len(self.keys)


class GroqEngine(BaseInferenceEngine):
    """
    Production-grade Groq Inference & Whisper Audio Engine.
    Exposes OpenAI-compatible LLM text completion and word-timestamped audio transcription.
    """

    API_BASE = "https://api.groq.com/openai/v1"

    def __init__(
        self,
        key_manager: Optional[GroqMultiKeyManager] = None,
        default_model: str = "qwen/qwen3.8-27b",
        timeout: float = 60.0
    ):
        self.key_manager = key_manager or GroqMultiKeyManager()
        self.default_model = default_model
        self.timeout = timeout
        self.request_logs: List[Dict[str, Any]] = []

    @property
    def api_keys(self) -> List[str]:
        return self.key_manager.keys

    @property
    def current_key(self) -> str:
        return self.key_manager.get_current_key()

    def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.request_logs[-limit:]

    # =========================================================================
    # LLM INFERENCE (OpenAI-Compatible Chat Completions)
    # =========================================================================

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = 0.3,
        max_tokens: Optional[int] = 2000,
        model: Optional[str] = None,
        stage_name: Optional[str] = None
    ) -> str:
        import uuid
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        stage = stage_name or "INFERENCE"
        target_model = model or self.default_model
        temp = temperature if temperature is not None else 0.3
        max_tok = max_tokens if max_tokens is not None else 2500

        # Enforce OTPM safety ceiling for on-demand models (Qwen OTPM limit is 1000)
        if "qwen" in target_model.lower():
            max_tok = min(max_tok, 950)

        input_tok_est = len(prompt.split()) + (len(system_prompt.split()) if system_prompt else 0)
        num_keys = max(1, self.key_manager.total_keys())
        max_attempts = max(15, num_keys * 3)
        max_wait_budget = 120.0  # Allow waiting up to 120 seconds total for rate limit resets
        accumulated_wait = 0.0
        last_error = None

        for attempt in range(max_attempts):
            key, wait_needed = self.key_manager.get_available_key()
            if not key:
                self.request_logs.append({
                    "stage_name": stage,
                    "request_id": request_id,
                    "selected_key_identifier": "none",
                    "model_name": target_model,
                    "attempt_number": attempt + 1,
                    "request_duration": 0.0,
                    "input_token_estimate": input_tok_est,
                    "output_token_estimate": 0,
                    "response_status": "NO_KEYS",
                    "retry_reason": "No keys available",
                    "validation_status": "FAILED",
                    "error_type": "KeyExhaustionError",
                    "response_parse_status": "N/A"
                })
                raise RuntimeError("No Groq API keys available. Please check groq api.txt or settings.")

            key_id = f"...{key[-6:]}"

            # If all keys were in cooldown, wait the real remaining time for earliest key
            if wait_needed > 0.0:
                if accumulated_wait + wait_needed > max_wait_budget:
                    print(f"[GroqEngine] Rate limit wait budget ({max_wait_budget}s) exceeded. Proceeding to fallback.")
                    break
                print(f"[GroqEngine] All {self.key_manager.total_keys()} keys in cooldown. Waiting {wait_needed:.1f}s for key {key_id} to become available (real-time Groq retry)...")
                time.sleep(wait_needed)
                accumulated_wait += wait_needed

            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            }
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": target_model,
                "messages": messages,
                "temperature": temp,
                "max_tokens": max_tok
            }

            req_start = time.perf_counter()
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(
                        f"{self.API_BASE}/chat/completions",
                        headers=headers,
                        json=payload
                    )
                    dur = round(time.perf_counter() - req_start, 3)

                    # Success
                    if resp.status_code == 200:
                        data = resp.json()
                        choices = data.get("choices", [])
                        content = choices[0].get("message", {}).get("content", "") if choices else ""
                        out_tok_est = len(content.split())
                        self.request_logs.append({
                            "stage_name": stage,
                            "request_id": request_id,
                            "selected_key_identifier": key_id,
                            "model_name": target_model,
                            "attempt_number": attempt + 1,
                            "request_duration": dur,
                            "input_token_estimate": input_tok_est,
                            "output_token_estimate": out_tok_est,
                            "response_status": "200_OK",
                            "retry_reason": None,
                            "validation_status": "SUCCESS",
                            "error_type": None,
                            "response_parse_status": "OK"
                        })
                        return content

                    # Rate limit or quota exhausted (429) -> Parse real wait time & cooldown key
                    elif resp.status_code == 429:
                        # If Groq specifically asks to reduce max_tokens (OTPM limit)
                        if "reduce max_tokens" in resp.text.lower() or "otpm" in resp.text.lower():
                            max_tok = min(max_tok, 800)
                            print(f"[GroqEngine] Reduced max_tokens to {max_tok} per Groq OTPM directive.")
                        wait_sec = parse_groq_retry_after(dict(resp.headers), resp.text)
                        self.key_manager.mark_key_cooldown(key, wait_sec)
                        last_error = f"HTTP 429: {resp.text}"
                        self.request_logs.append({
                            "stage_name": stage,
                            "request_id": request_id,
                            "selected_key_identifier": key_id,
                            "model_name": target_model,
                            "attempt_number": attempt + 1,
                            "request_duration": dur,
                            "input_token_estimate": input_tok_est,
                            "output_token_estimate": 0,
                            "response_status": "HTTP_429",
                            "retry_reason": f"Rate limit; wait {wait_sec:.1f}s",
                            "validation_status": "RETRYING",
                            "error_type": "RateLimitError",
                            "response_parse_status": "N/A"
                        })
                        print(f"[GroqEngine] Key {key_id} rate-limited (HTTP 429). Groq requested wait: {wait_sec:.1f}s. Switching to next key in pool... (Attempt {attempt+1}/{max_attempts})")
                        self.key_manager.rotate_key()
                        continue

                    # Authentication error (401, 403)
                    elif resp.status_code in (401, 403):
                        self.key_manager.mark_key_invalid(key)
                        last_error = f"HTTP {resp.status_code}: {resp.text}"
                        self.request_logs.append({
                            "stage_name": stage,
                            "request_id": request_id,
                            "selected_key_identifier": key_id,
                            "model_name": target_model,
                            "attempt_number": attempt + 1,
                            "request_duration": dur,
                            "input_token_estimate": input_tok_est,
                            "output_token_estimate": 0,
                            "response_status": f"HTTP_{resp.status_code}",
                            "retry_reason": "Authentication failed",
                            "validation_status": "RETRYING",
                            "error_type": "AuthError",
                            "response_parse_status": "N/A"
                        })
                        print(f"[GroqEngine] Key {key_id} invalid (HTTP {resp.status_code}). Marking disabled.")
                        self.key_manager.rotate_key()
                        continue

                    else:
                        last_error = f"Groq API returned HTTP {resp.status_code}: {resp.text}"
                        self.request_logs.append({
                            "stage_name": stage,
                            "request_id": request_id,
                            "selected_key_identifier": key_id,
                            "model_name": target_model,
                            "attempt_number": attempt + 1,
                            "request_duration": dur,
                            "input_token_estimate": input_tok_est,
                            "output_token_estimate": 0,
                            "response_status": f"HTTP_{resp.status_code}",
                            "retry_reason": f"Server error {resp.status_code}",
                            "validation_status": "RETRYING",
                            "error_type": "HTTPError",
                            "response_parse_status": "N/A"
                        })
                        self.key_manager.rotate_key()
                        time.sleep(1.0)
                        continue

            except (httpx.TimeoutException, httpx.NetworkError) as ne:
                dur = round(time.perf_counter() - req_start, 3)
                last_error = f"Groq Network Error: {ne}"
                self.request_logs.append({
                    "stage_name": stage,
                    "request_id": request_id,
                    "selected_key_identifier": key_id,
                    "model_name": target_model,
                    "attempt_number": attempt + 1,
                    "request_duration": dur,
                    "input_token_estimate": input_tok_est,
                    "output_token_estimate": 0,
                    "response_status": "NETWORK_ERROR",
                    "retry_reason": str(ne),
                    "validation_status": "RETRYING",
                    "error_type": type(ne).__name__,
                    "response_parse_status": "N/A"
                })
                self.key_manager.rotate_key()
                time.sleep(1.0)

        # Resilient fallback: If qwen hits quota across all keys, attempt real Groq fallback models
        if "qwen" in target_model.lower() and stage != "FALLBACK_RETRY":
            for fallback_model in ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]:
                try:
                    print(f"[GroqEngine] Retrying with available fallback model: {fallback_model}...")
                    return self.generate_text(
                        prompt,
                        system_prompt=system_prompt,
                        temperature=temp,
                        max_tokens=min(max_tokens or 2048, 2048),
                        model=fallback_model,
                        stage_name="FALLBACK_RETRY"
                    )
                except Exception as fb_err:
                    last_error = f"{last_error} | Fallback {fallback_model} failed: {fb_err}"

        raise RuntimeError(f"All Groq API keys failed or were rate-limited. Last error: {last_error}")

    # =========================================================================
    # AUDIO TRANSCRIPTION WITH WORD TIMESTAMPS (Groq Whisper)
    # =========================================================================

    def transcribe_audio_groq(
        self,
        audio_file_path: str,
        model: str = "whisper-large-v3-turbo"
    ) -> NarrationData:
        """
        Transcribes audio via Groq Whisper API returning exact word timestamps.
        Uses response_format="verbose_json" and timestamp_granularities[]="word".
        """
        p = Path(audio_file_path)
        if not p.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

        key = self.key_manager.get_current_key()
        if not key:
            raise RuntimeError("No Groq API keys available for Whisper transcription.")

        url = f"{self.API_BASE}/audio/transcriptions"
        headers = {"Authorization": f"Bearer {key}"}

        max_retries = max(1, self.key_manager.total_keys())
        last_err = None

        for attempt in range(max_retries):
            key = self.key_manager.get_current_key()
            headers["Authorization"] = f"Bearer {key}"

            try:
                with open(p, "rb") as af:
                    files = {
                        "file": (p.name, af, "audio/mpeg" if p.suffix.lower() == ".mp3" else "audio/wav")
                    }
                    data = {
                        "model": model,
                        "response_format": "verbose_json",
                        "timestamp_granularities[]": "word"
                    }

                    with httpx.Client(timeout=120.0) as client:
                        resp = client.post(url, headers=headers, files=files, data=data)

                        if resp.status_code == 200:
                            vjson = resp.json()
                            duration = float(vjson.get("duration", 0.0))
                            words_raw = vjson.get("words", [])

                            word_objects: List[WordTimestamp] = []
                            for w in words_raw:
                                word_str = str(w.get("word", "")).strip()
                                if not word_str:
                                    continue
                                start_s = float(w.get("start", 0.0))
                                end_s = float(w.get("end", start_s + 0.3))
                                word_objects.append(WordTimestamp(
                                    word=word_str,
                                    start=round(start_s, 3),
                                    end=round(end_s, 3)
                                ))

                            if not duration and word_objects:
                                duration = word_objects[-1].end

                            return NarrationData(
                                duration_seconds=round(duration, 3),
                                words=word_objects
                            )

                        elif resp.status_code == 429:
                            self.key_manager.rotate_key()
                            continue
                        else:
                            last_err = f"HTTP {resp.status_code}: {resp.text}"
                            self.key_manager.rotate_key()

            except Exception as e:
                last_err = str(e)
                self.key_manager.rotate_key()

        raise RuntimeError(f"Whisper transcription failed across all keys: {last_err}")

    # =========================================================================
    # LOCAL FASTER-WHISPER FALLBACK (100% Offline)
    # =========================================================================

    def transcribe_audio_local(
        self,
        audio_file_path: str,
        model_size: str = "base"
    ) -> NarrationData:
        """Transcribes audio using local faster-whisper without any internet connection."""
        p = Path(audio_file_path)
        if not p.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise RuntimeError("faster-whisper is not installed. Please install faster-whisper or use Groq Whisper.")

        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, info = model.transcribe(str(p.resolve()), word_timestamps=True)

        word_objects: List[WordTimestamp] = []
        for segment in segments:
            if hasattr(segment, "words") and segment.words:
                for w in segment.words:
                    clean_w = w.word.strip()
                    if clean_w:
                        word_objects.append(WordTimestamp(
                            word=clean_w,
                            start=round(float(w.start), 3),
                            end=round(float(w.end), 3)
                        ))

        return NarrationData(
            duration_seconds=round(float(info.duration), 3),
            words=word_objects
        )

    # =========================================================================
    # HEALTH / CONNECTIVITY TEST
    # =========================================================================

    def test_connection(self) -> Dict[str, Any]:
        """Tests connectivity to Groq API and returns latency and available models."""
        key = self.key_manager.get_current_key()
        if not key:
            return {
                "status": "error",
                "connected": False,
                "latency_ms": 0.0,
                "message": "No Groq API keys found in pool."
            }

        start_t = time.perf_counter()
        try:
            headers = {"Authorization": f"Bearer {key}"}
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{self.API_BASE}/models", headers=headers)
                latency = round((time.perf_counter() - start_t) * 1000, 1)

                if resp.status_code == 200:
                    data = resp.json()
                    models = [m["id"] for m in data.get("data", []) if "whisper" not in m.get("id", "")]
                    return {
                        "status": "ok",
                        "connected": True,
                        "latency_ms": latency,
                        "message": f"Connected to Groq ({len(models)} models available, {self.key_manager.total_keys()} keys active)",
                        "models": models,
                        "active_key_preview": f"{key[:8]}...{key[-4:]}"
                    }
                elif resp.status_code in (401, 403):
                    return {
                        "status": "error",
                        "connected": False,
                        "latency_ms": latency,
                        "message": "Groq authentication failed. Please check your API keys."
                    }
                else:
                    return {
                        "status": "error",
                        "connected": False,
                        "latency_ms": latency,
                        "message": f"Groq returned HTTP {resp.status_code}: {resp.text}"
                    }
        except Exception as e:
            return {
                "status": "error",
                "connected": False,
                "latency_ms": round((time.perf_counter() - start_t) * 1000, 1),
                "message": f"Connection error: {str(e)}"
            }


_global_groq_engine: Optional[GroqEngine] = None

def get_groq_engine() -> GroqEngine:
    global _global_groq_engine
    if _global_groq_engine is None:
        _global_groq_engine = GroqEngine()
    return _global_groq_engine
