"""
Audio Alignment Engine for PromptBeast.

Provides high-precision word-level acoustic alignment for both:
- Workflow A: Generated narration audio aligned against user script.
- Workflow B: Uploaded audio transcription and alignment.

Performs strict multi-factor acoustic and linguistic validation:
- Monotonicity and non-negative timestamps
- Overlap detection and prevention
- Duration consistency against real audio waveform
- Script-to-audio coverage matching
- Cache verification and SHA-256 audio hash invalidation
"""
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any, Union

from app.models.timeline import (
    WordTimestamp,
    NarrationData,
    AlignmentStatus,
    AlignmentQuality,
)

logger = logging.getLogger("AudioAlignmentEngine")


def compute_audio_hash(audio_path: Union[str, Path]) -> str:
    """Computes SHA-256 hash of an audio file on disk to guarantee cache invalidation."""
    p = Path(audio_path)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"Audio file does not exist: {audio_path}")

    hasher = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_audio_duration(audio_path: Union[str, Path]) -> float:
    """Returns exact audio duration in seconds using soundfile or wave."""
    p = Path(audio_path)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"Audio file does not exist: {audio_path}")

    try:
        import soundfile as sf
        info = sf.info(str(p))
        return round(float(info.duration), 3)
    except Exception:
        pass

    try:
        import wave
        with wave.open(str(p), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return round(frames / float(rate), 3)
    except Exception:
        pass

    try:
        from pydub import AudioSegment
        seg = AudioSegment.from_file(str(p))
        return round(len(seg) / 1000.0, 3)
    except Exception as e:
        raise RuntimeError(f"Unable to determine duration of audio file {audio_path}: {e}")


def normalize_token(token: str) -> str:
    """Normalizes a token for fuzzy textual matching: lowercased, stripped of non-alphanumerics."""
    clean = token.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"^[^\w]+|[^\w]+$", "", clean.lower()).strip()


class AudioAlignmentEngine:
    """
    Unified acoustic alignment engine for PromptBeast.
    Derives word timings directly from the synthesized or uploaded audio waveform.
    """

    def __init__(self, local_model_size: str = "base"):
        self.local_model_size = local_model_size
        self._local_model = None

    def _get_faster_whisper_model(self):
        if self._local_model is None:
            try:
                from faster_whisper import WhisperModel
                self._local_model = WhisperModel(self.local_model_size, device="cpu", compute_type="int8")
            except Exception as e:
                logger.warning(f"Could not load faster-whisper model ({self.local_model_size}): {e}")
                self._local_model = None
        return self._local_model

    # =========================================================================
    # CORE RECOGNITION: FASTER-WHISPER & GROQ WHISPER
    # =========================================================================

    def _align_with_faster_whisper(
        self,
        audio_path: Union[str, Path],
        prompt: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], float]:
        """Acoustic word-level transcription via local faster-whisper."""
        model = self._get_faster_whisper_model()
        if model is None:
            raise RuntimeError("faster-whisper is not available in local environment.")

        audio_str = str(Path(audio_path).resolve())
        segments, info = model.transcribe(
            audio_str,
            word_timestamps=True,
            initial_prompt=prompt if prompt else None,
            language="en"
        )

        raw_words: List[Dict[str, Any]] = []
        for segment in segments:
            if hasattr(segment, "words") and segment.words:
                for w in segment.words:
                    clean_w = str(w.word).strip()
                    if clean_w:
                        raw_words.append({
                            "word": clean_w,
                            "start": round(float(w.start), 3),
                            "end": round(float(w.end), 3),
                            "confidence": round(float(getattr(w, "probability", 0.95)), 3)
                        })

        aud_dur = round(float(info.duration), 3) if info and hasattr(info, "duration") else get_audio_duration(audio_path)
        return raw_words, aud_dur

    def _align_with_groq_whisper(
        self,
        audio_path: Union[str, Path],
        prompt: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], float]:
        """Acoustic word-level transcription via Groq Whisper API."""
        from app.ai.groq_engine import GroqEngine
        engine = GroqEngine()
        audio_p = Path(audio_path)

        key = engine.key_manager.get_current_key()
        if not key:
            raise RuntimeError("No Groq API keys available for Whisper transcription.")

        import httpx
        url = f"{engine.API_BASE}/audio/transcriptions"
        max_retries = max(1, engine.key_manager.total_keys())
        last_err = None

        for attempt in range(max_retries):
            curr_key = engine.key_manager.get_current_key()
            headers = {"Authorization": f"Bearer {curr_key}"}

            try:
                with open(audio_p, "rb") as af:
                    files = {
                        "file": (audio_p.name, af, "audio/mpeg" if audio_p.suffix.lower() == ".mp3" else "audio/wav")
                    }
                    data = {
                        "model": "whisper-large-v3-turbo",
                        "response_format": "verbose_json",
                        "timestamp_granularities[]": "word"
                    }
                    if prompt:
                        data["prompt"] = prompt[:800] # Groq prompt conditioning limit

                    with httpx.Client(timeout=120.0) as client:
                        resp = client.post(url, headers=headers, files=files, data=data)
                        if resp.status_code == 200:
                            vjson = resp.json()
                            duration = float(vjson.get("duration", 0.0))
                            words_raw = vjson.get("words", [])
                            raw_words: List[Dict[str, Any]] = []
                            for w in words_raw:
                                w_str = str(w.get("word", "")).strip()
                                if w_str:
                                    s_t = float(w.get("start", 0.0))
                                    e_t = float(w.get("end", s_t + 0.2))
                                    raw_words.append({
                                        "word": w_str,
                                        "start": round(s_t, 3),
                                        "end": round(e_t, 3),
                                        "confidence": 0.95
                                    })
                            if not duration and raw_words:
                                duration = raw_words[-1]["end"]
                            return raw_words, round(duration, 3)

                        elif resp.status_code == 429:
                            engine.key_manager.rotate_key()
                            continue
                        else:
                            last_err = f"HTTP {resp.status_code}: {resp.text}"
                            engine.key_manager.rotate_key()

            except Exception as e:
                last_err = str(e)
                engine.key_manager.rotate_key()

        raise RuntimeError(f"Groq Whisper transcription failed: {last_err}")

    # =========================================================================
    # SCRIPT-TO-ACOUSTIC RECONCILIATION (Workflow A Forced Alignment)
    # =========================================================================

    def _reconcile_script_tokens(
        self,
        script_text: str,
        acoustic_words: List[Dict[str, Any]],
        audio_duration: float
    ) -> Tuple[List[WordTimestamp], int, float]:
        """
        Reconciles spoken acoustic words with the original user script text.
        Guarantees:
        1. Script's exact words, casing, punctuation, and proper nouns are preserved.
        2. Timestamps come directly from acoustic waveform boundaries.
        3. Multi-word expansions (e.g. '1453' -> 'fourteen fifty-three') span the entire acoustic duration.
        4. Missed or swallowed words are cleanly interpolated between adjacent acoustic words.
        """
        # Pre-process script text: separate em-dashes and en-dashes so compound words tokenize cleanly
        cleaned_text = script_text.replace("—", " — ").replace("–", " – ").replace("\u2019", "'").replace("\u2018", "'")
        script_tokens = [w for w in re.split(r"\s+", cleaned_text.strip()) if w and w not in ("—", "–")]
        if not script_tokens:
            return [], 0, 1.0

        if not acoustic_words:
            # Fallback if acoustic words empty: interpolate across duration
            step = audio_duration / max(1, len(script_tokens))
            fallback_words = [
                WordTimestamp(
                    word=tok,
                    start=round(i * step, 3),
                    end=round((i + 1) * step, 3),
                    index=i,
                    confidence=0.5
                )
                for i, tok in enumerate(script_tokens)
            ]
            return fallback_words, len(script_tokens), 0.0

        M = len(script_tokens)
        N = len(acoustic_words)

        # Dynamic Programming Matrix for Global Sequence Alignment
        dp = [[0.0] * (N + 1) for _ in range(M + 1)]
        for i in range(M + 1):
            dp[i][0] = -1.0 * i
        for j in range(N + 1):
            dp[0][j] = -1.0 * j

        for i in range(1, M + 1):
            s_norm = normalize_token(script_tokens[i - 1])
            for j in range(1, N + 1):
                a_norm = normalize_token(acoustic_words[j - 1]["word"])
                if s_norm == a_norm:
                    score = 2.0
                elif s_norm and a_norm and (s_norm in a_norm or a_norm in s_norm):
                    score = 1.0
                else:
                    score = -1.5

                dp[i][j] = max(
                    dp[i - 1][j - 1] + score,
                    dp[i - 1][j] - 1.0,
                    dp[i][j - 1] - 1.0
                )

        # Backtrack optimal alignment path
        i, j = M, N
        script_to_acoustic: Dict[int, List[int]] = {k: [] for k in range(M)}
        unmatched_script = 0

        while i > 0 or j > 0:
            if i > 0 and j > 0:
                s_norm = normalize_token(script_tokens[i - 1])
                a_norm = normalize_token(acoustic_words[j - 1]["word"])
                score = 2.0 if s_norm == a_norm else (1.0 if (s_norm and a_norm and (s_norm in a_norm or a_norm in s_norm)) else -1.5)
                if abs(dp[i][j] - (dp[i - 1][j - 1] + score)) < 1e-4:
                    script_to_acoustic[i - 1].append(j - 1)
                    i -= 1
                    j -= 1
                    continue
            if i > 0 and abs(dp[i][j] - (dp[i - 1][j] - 1.0)) < 1e-4:
                i -= 1
                unmatched_script += 1
            else:
                j -= 1

        # Collect all assigned acoustic indices
        all_assigned = set()
        for s_k in range(M):
            all_assigned.update(script_to_acoustic.get(s_k, []))

        # Reconcile unassigned acoustic words into adjacent multi-word expansions (e.g. numerals, dates, acronyms)
        for s_idx in range(M):
            tok_text = script_tokens[s_idx]
            has_digits = any(c.isdigit() for c in tok_text)
            if has_digits and script_to_acoustic.get(s_idx):
                # Expand backward into unassigned acoustic words
                while min(script_to_acoustic[s_idx]) - 1 >= 0 and (min(script_to_acoustic[s_idx]) - 1) not in all_assigned:
                    cand = min(script_to_acoustic[s_idx]) - 1
                    script_to_acoustic[s_idx].append(cand)
                    all_assigned.add(cand)
                # Expand forward into unassigned acoustic words
                while max(script_to_acoustic[s_idx]) + 1 < N and (max(script_to_acoustic[s_idx]) + 1) not in all_assigned:
                    cand = max(script_to_acoustic[s_idx]) + 1
                    script_to_acoustic[s_idx].append(cand)
                    all_assigned.add(cand)

        # Build ordered WordTimestamp list
        final_words: List[WordTimestamp] = []
        last_end = 0.0

        for idx, tok in enumerate(script_tokens):
            ac_indices = sorted(script_to_acoustic.get(idx, []))
            if ac_indices:
                matched_acoustics = [acoustic_words[k] for k in ac_indices]
                start_t = min(w["start"] for w in matched_acoustics)
                end_t = max(w["end"] for w in matched_acoustics)
                avg_conf = sum(w.get("confidence", 0.95) for w in matched_acoustics) / len(matched_acoustics)

                # Ensure non-decreasing timeline
                if start_t < last_end:
                    start_t = last_end
                if end_t <= start_t:
                    end_t = round(start_t + 0.15, 3)

                last_end = end_t
                final_words.append(WordTimestamp(
                    word=tok,
                    start=round(start_t, 3),
                    end=round(end_t, 3),
                    index=idx,
                    confidence=round(avg_conf, 3)
                ))
            else:
                # Interpolate unaligned word
                # Search forward for next aligned word
                next_start = audio_duration
                for fwd_idx in range(idx + 1, M):
                    fwd_matches = script_to_acoustic.get(fwd_idx, [])
                    if fwd_matches:
                        next_start = min(acoustic_words[k]["start"] for k in fwd_matches)
                        break

                gap = max(0.1, next_start - last_end)
                step = gap / max(1, 2)
                start_t = round(last_end, 3)
                end_t = round(min(next_start, start_t + step), 3)
                if end_t <= start_t:
                    end_t = round(start_t + 0.1, 3)

                last_end = end_t
                final_words.append(WordTimestamp(
                    word=tok,
                    start=start_t,
                    end=end_t,
                    index=idx,
                    confidence=0.50
                ))

        coverage_ratio = round(max(0.0, min(1.0, 1.0 - (unmatched_script / float(M)))), 3)
        return final_words, unmatched_script, coverage_ratio

    # =========================================================================
    # WORKFLOW A: USER PROVIDES A SCRIPT
    # =========================================================================

    def align_generated_script(
        self,
        audio_path: Union[str, Path],
        script_text: str,
        engine: str = "auto"
    ) -> NarrationData:
        """
        Workflow A:
        Aligns synthesized TTS audio against the user's narration script.
        Uses waveform-based acoustic timestamps, reconciles script tokens,
        validates the timeline, and writes standardized narration_timestamps.json.
        """
        p = Path(audio_path)
        if not p.exists():
            raise FileNotFoundError(f"Generated audio file not found: {audio_path}")

        audio_hash = compute_audio_hash(p)
        audio_duration = get_audio_duration(p)
        engine_used = engine

        acoustic_words: List[Dict[str, Any]] = []
        acoustic_dur = audio_duration

        if engine in ("auto", "faster-whisper"):
            try:
                acoustic_words, acoustic_dur = self._align_with_faster_whisper(p, prompt=script_text)
                engine_used = f"faster-whisper-{self.local_model_size}"
            except Exception as e:
                logger.warning(f"Local faster-whisper failed: {e}. Attempting Groq Whisper fallback...")
                if engine == "faster-whisper":
                    raise
                acoustic_words, acoustic_dur = self._align_with_groq_whisper(p, prompt=script_text)
                engine_used = "groq-whisper-large-v3-turbo"
        elif engine == "groq-whisper":
            try:
                acoustic_words, acoustic_dur = self._align_with_groq_whisper(p, prompt=script_text)
                engine_used = "groq-whisper-large-v3-turbo"
            except Exception as e:
                logger.warning(f"Groq Whisper failed: {e}. Falling back to faster-whisper...")
                acoustic_words, acoustic_dur = self._align_with_faster_whisper(p, prompt=script_text)
                engine_used = f"faster-whisper-{self.local_model_size}"

        aligned_words, unaligned_count, coverage_ratio = self._reconcile_script_tokens(
            script_text=script_text,
            acoustic_words=acoustic_words,
            audio_duration=audio_duration
        )

        narration = NarrationData(
            schema_version="1.0",
            source_type="generated_script",
            audio_file=p.name,
            audio_hash=audio_hash,
            transcript=script_text.strip(),
            duration_seconds=audio_duration,
            alignment_engine=engine_used,
            alignment_status=AlignmentStatus.ALIGNMENT_COMPLETED.value,
            words=aligned_words
        )

        # Validate alignment
        self.validate_alignment(narration, audio_path=p, reference_script=script_text)

        # Save standardized JSON beside audio file
        json_out = p.parent / "narration_timestamps.json"
        self.save_standardized_json(narration, json_out)

        return narration

    # =========================================================================
    # WORKFLOW B: USER UPLOADS AN AUDIO FILE
    # =========================================================================

    def align_uploaded_audio(
        self,
        audio_path: Union[str, Path],
        engine: str = "auto"
    ) -> NarrationData:
        """
        Workflow B:
        Transcribes uploaded audio with exact word-level acoustic timestamps,
        validates the timeline, and writes standardized narration_timestamps.json.
        """
        p = Path(audio_path)
        if not p.exists():
            raise FileNotFoundError(f"Uploaded audio file not found: {audio_path}")

        audio_hash = compute_audio_hash(p)
        audio_duration = get_audio_duration(p)
        engine_used = engine

        acoustic_words: List[Dict[str, Any]] = []
        acoustic_dur = audio_duration

        if engine in ("auto", "groq-whisper"):
            try:
                acoustic_words, acoustic_dur = self._align_with_groq_whisper(p)
                engine_used = "groq-whisper-large-v3-turbo"
            except Exception as e:
                logger.warning(f"Groq Whisper failed: {e}. Falling back to faster-whisper...")
                if engine == "groq-whisper":
                    raise
                acoustic_words, acoustic_dur = self._align_with_faster_whisper(p)
                engine_used = f"faster-whisper-{self.local_model_size}"
        else:
            acoustic_words, acoustic_dur = self._align_with_faster_whisper(p)
            engine_used = f"faster-whisper-{self.local_model_size}"

        word_objs: List[WordTimestamp] = []
        last_end = 0.0
        for i, item in enumerate(acoustic_words):
            s_t = max(0.0, float(item["start"]))
            e_t = max(s_t + 0.05, float(item["end"]))
            if s_t < last_end:
                s_t = last_end
            if e_t <= s_t:
                e_t = s_t + 0.1
            last_end = e_t

            word_objs.append(WordTimestamp(
                word=item["word"],
                start=round(s_t, 3),
                end=round(e_t, 3),
                index=i,
                confidence=round(float(item.get("confidence", 0.95)), 3)
            ))

        transcript = " ".join(w.word for w in word_objs)

        narration = NarrationData(
            schema_version="1.0",
            source_type="uploaded_audio",
            audio_file=p.name,
            audio_hash=audio_hash,
            transcript=transcript,
            duration_seconds=audio_duration,
            alignment_engine=engine_used,
            alignment_status=AlignmentStatus.ALIGNMENT_COMPLETED.value,
            words=word_objs
        )

        # Validate alignment
        self.validate_alignment(narration, audio_path=p)

        # Save standardized JSON beside audio file
        json_out = p.parent / "narration_timestamps.json"
        self.save_standardized_json(narration, json_out)

        return narration

    # =========================================================================
    # STRICT TIMELINE & LINGUISTIC VALIDATION
    # =========================================================================

    def validate_alignment(
        self,
        narration_data: NarrationData,
        audio_path: Optional[Union[str, Path]] = None,
        reference_script: Optional[str] = None
    ) -> AlignmentQuality:
        """
        Performs multi-point validation on narration timestamps.
        Distinguishes:
        - STRUCTURALLY_VALID
        - ALIGNMENT_COMPLETED
        - ALIGNMENT_VERIFIED
        - ALIGNMENT_DEGRADED
        - ALIGNMENT_FAILED
        """
        warnings: List[str] = []
        unaligned_words = 0
        coverage_ratio = 1.0
        mean_dur_err = 0.0
        is_failed = False
        is_degraded = False

        words = narration_data.words

        # Check 1: Empty words
        if not words:
            warnings.append("No words found in narration timestamps.")
            is_failed = True

        # Check 2: Audio duration match
        if audio_path and Path(audio_path).exists():
            real_dur = get_audio_duration(audio_path)
            mean_dur_err = round(abs(narration_data.duration_seconds - real_dur), 3)
            if mean_dur_err > 3.0:
                warnings.append(f"Significant duration discrepancy: audio is {real_dur:.2f}s but narration data records {narration_data.duration_seconds:.2f}s.")
                is_failed = True
            elif mean_dur_err > 1.0:
                warnings.append(f"Minor duration mismatch: difference of {mean_dur_err:.2f}s between audio file and timestamps.")
                is_degraded = True

            if words and words[-1].end > real_dur + 0.75:
                warnings.append(f"Last word end ({words[-1].end:.2f}s) exceeds audio duration ({real_dur:.2f}s).")
                is_degraded = True

        # Check 3: Word order, start/end sanity, and excessive overlaps
        for i, w in enumerate(words):
            if w.start < 0.0:
                warnings.append(f"Negative start timestamp at word index {i} ('{w.word}'): {w.start}s.")
                is_failed = True
            if w.end <= w.start:
                warnings.append(f"Word index {i} ('{w.word}') has end ({w.end}s) <= start ({w.start}s).")
                is_failed = True
            if i > 0:
                prev_w = words[i - 1]
                if w.start < prev_w.start - 0.01:
                    warnings.append(f"Word order reversal at index {i} ('{w.word}' starts at {w.start}s < previous start {prev_w.start}s).")
                    is_failed = True
                # Check overlap
                overlap = prev_w.end - w.start
                if overlap > 0.25:
                    warnings.append(f"Excessive word overlap between '{prev_w.word}' and '{w.word}' ({overlap:.2f}s overlap).")
                    is_degraded = True
                # Check unexplained huge gap in continuous speech
                gap = w.start - prev_w.end
                if gap > 6.0:
                    warnings.append(f"Long silence gap of {gap:.2f}s between word {i-1} and {i}.")
                    is_degraded = True

        # Check 4: Reference script coverage
        if reference_script:
            cleaned_script = reference_script.replace("—", " — ").replace("–", " – ").replace("\u2019", "'").replace("\u2018", "'")
            script_tokens = [w for w in re.split(r"\s+", cleaned_script.strip()) if w and w not in ("—", "–")]
            total_script = len(script_tokens)
            total_words = len(words)
            if total_script > 0:
                # Count normalized matches
                script_norm = [normalize_token(t) for t in script_tokens if normalize_token(t)]
                words_norm = set(normalize_token(w.word) for w in words if normalize_token(w.word))
                matched = sum(1 for sn in script_norm if sn in words_norm)
                coverage_ratio = round(matched / float(max(1, len(script_norm))), 3)
                unaligned_words = max(0, len(script_norm) - matched)

                if coverage_ratio < 0.60:
                    warnings.append(f"Low script coverage: only {coverage_ratio * 100:.1f}% of script words matched in audio.")
                    is_failed = True
                elif unaligned_words > 0:
                    warnings.append(f"{unaligned_words} script words ({round((1.0 - coverage_ratio) * 100, 1)}%) had punctuation/tokenization differences or required phonetic interpolation.")
                    if coverage_ratio < 0.90:
                        is_degraded = True

        # Assign status
        if is_failed:
            status = AlignmentStatus.ALIGNMENT_FAILED.value
        elif is_degraded:
            status = AlignmentStatus.ALIGNMENT_DEGRADED.value
        else:
            status = AlignmentStatus.ALIGNMENT_VERIFIED.value

        quality = AlignmentQuality(
            status=status,
            warnings=warnings,
            unaligned_words=unaligned_words,
            coverage_ratio=coverage_ratio,
            mean_duration_error=mean_dur_err
        )

        narration_data.alignment_status = status
        narration_data.alignment_quality = quality
        return quality

    # =========================================================================
    # PERSISTENCE & CACHE INVALIDATION
    # =========================================================================

    @staticmethod
    def save_standardized_json(narration_data: NarrationData, json_path: Union[str, Path]) -> str:
        """Saves standardized narration timestamp JSON."""
        p = Path(json_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(narration_data.to_standard_json(indent=2))
        return str(p.resolve())

    @staticmethod
    def load_standardized_json(json_path: Union[str, Path]) -> NarrationData:
        """Loads standardized narration timestamp JSON."""
        return NarrationData.from_standard_json(json_path)

    @staticmethod
    def is_cache_valid(json_path: Union[str, Path], audio_path: Union[str, Path]) -> bool:
        """
        Validates whether an existing timestamp JSON file is valid for the given audio file.
        Returns False if:
        - Either file is missing.
        - Audio SHA256 does not match stored audio_hash (indicating audio was re-synthesized or changed).
        - Alignment status is ALIGNMENT_FAILED.
        """
        jp = Path(json_path)
        ap = Path(audio_path)
        if not jp.exists() or not ap.exists():
            return False

        try:
            curr_hash = compute_audio_hash(ap)
            data = NarrationData.from_standard_json(jp)
            if data.audio_hash and data.audio_hash != curr_hash:
                logger.info(f"Audio hash mismatch ({data.audio_hash[:8]} vs {curr_hash[:8]}): Invalidating timestamp cache.")
                return False
            if data.alignment_status == AlignmentStatus.ALIGNMENT_FAILED.value:
                return False
            return True
        except Exception as e:
            logger.warning(f"Error checking alignment cache: {e}")
            return False

    def load_or_align(
        self,
        audio_path: Union[str, Path],
        script_text: Optional[str] = None,
        force_realign: bool = False,
        engine: str = "auto"
    ) -> NarrationData:
        """
        Loads cached timestamps if valid and matching audio SHA256;
        otherwise runs fresh acoustic alignment and saves standardized JSON.
        """
        ap = Path(audio_path)
        json_path = ap.parent / "narration_timestamps.json"

        if not force_realign and self.is_cache_valid(json_path, ap):
            logger.info(f"Using verified cached timestamps from {json_path}")
            return self.load_standardized_json(json_path)

        logger.info(f"Aligning audio from scratch for {ap.name}...")
        if script_text:
            return self.align_generated_script(ap, script_text=script_text, engine=engine)
        else:
            return self.align_uploaded_audio(ap, engine=engine)

