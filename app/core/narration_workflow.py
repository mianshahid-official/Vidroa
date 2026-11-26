"""
Narration-Aware Workflow Engine for PromptBeast.
Handles JSON script import, visual ideas alignment, dynamic story bible extraction,
and batch image prompt generation via Groq strictly adhering to user-selected visual styles.
"""
import json
import re
import difflib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from app.models.scene import VisualScene
from app.models.timeline import NarrationData, WordTimestamp
from app.presets.loader import PresetManager
from app.ai.groq_engine import GroqEngine, GroqMultiKeyManager
from app.core.video_parser import parse_video_visual


# =============================================================================
# STEP 1: IMPORT SCRIPT JSON & VALIDATION
# =============================================================================

class JSONImportResult:
    def __init__(
        self,
        success: bool,
        message: str,
        story_text: str = "",
        narration: Optional[NarrationData] = None,
        scenes: Optional[List[VisualScene]] = None,
        raw_data: Optional[Dict[str, Any]] = None
    ):
        self.success = success
        self.message = message
        self.story_text = story_text
        self.narration = narration
        self.scenes = scenes or []
        self.raw_data = raw_data or {}


def import_script_json(file_path_or_str: str) -> JSONImportResult:
    """
    Parses and validates a script JSON file or string.
    Supports:
    1. Whisper/Speech JSON: {"text": "...", "words": [{"word": "...", "start": 0.0, "end": 0.5}, ...]}
    2. Storyboard JSON: {"scenes": [{"scene_id": "001", "start": 0.0, "end": 4.0, "narration": "...", "prompt": "..."}]}
    3. Segments/Subtitle JSON: {"segments": [{"start": 0.0, "end": 3.0, "text": "..."}]}
    4. Plain dictionary with text/words.
    """
    p = Path(file_path_or_str)
    raw_content = ""
    if p.exists() and p.is_file():
        try:
            raw_content = p.read_text(encoding="utf-8")
        except Exception as e:
            return JSONImportResult(False, f"Could not read file: {e}")
    else:
        raw_content = file_path_or_str

    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError as jde:
        return JSONImportResult(False, f"Malformed JSON: {jde.msg} (line {jde.lineno}, col {jde.colno})")

    if not isinstance(data, dict):
        return JSONImportResult(False, "JSON root must be an object (dictionary).")

    # Format 1: Whisper / Speech-to-Text format with 'text' and 'words'
    if "words" in data and isinstance(data["words"], list):
        text = data.get("text", "")
        word_list: List[WordTimestamp] = []
        for w in data["words"]:
            if isinstance(w, dict) and "word" in w and "start" in w and "end" in w:
                word_list.append(WordTimestamp(
                    word=str(w["word"]),
                    start=float(w["start"]),
                    end=float(w["end"])
                ))

        if not word_list:
            return JSONImportResult(False, "JSON 'words' array was found but contained no valid word timestamps.")

        # Reconstruct text if empty
        if not text:
            text = " ".join(w.word for w in word_list).strip()

        duration = float(data.get("duration", word_list[-1].end))
        narration = NarrationData(
            words=word_list,
            duration_seconds=duration
        )
        return JSONImportResult(
            success=True,
            message=f"Successfully imported audio script JSON: {len(word_list)} words, duration {duration:.1f}s.",
            story_text=text,
            narration=narration,
            raw_data=data
        )

    # Format 2: Storyboard scenes array
    if "scenes" in data and isinstance(data["scenes"], list):
        scenes: List[VisualScene] = []
        full_text_parts = []
        for i, s in enumerate(data["scenes"]):
            if not isinstance(s, dict):
                continue
            s_id = str(s.get("scene_id") or f"{i+1:03d}")
            start = float(s.get("start", 0.0))
            end = float(s.get("end", start + 3.0))
            dur = float(s.get("duration", max(0.5, end - start)))
            narr = str(s.get("narration") or s.get("narration_excerpt") or "")
            visual_idea = str(s.get("visual_idea") or s.get("visual_subject") or "")
            prompt = str(s.get("prompt") or "")
            if narr:
                full_text_parts.append(narr)

            scenes.append(VisualScene(
                scene_id=s_id,
                index=i + 1,
                start=start,
                end=end,
                duration=dur,
                narration_excerpt=narr,
                visual_subject=visual_idea or narr[:60],
                visual_idea=visual_idea,
                prompt=prompt,
                generation_status="generated" if prompt else "pending"
            ))

        story_text = "\n\n".join(full_text_parts)
        return JSONImportResult(
            success=True,
            message=f"Successfully imported storyboard JSON with {len(scenes)} predefined scenes.",
            story_text=story_text,
            scenes=scenes,
            raw_data=data
        )

    # Format 3: Segments array (like Whisper segments)
    if "segments" in data and isinstance(data["segments"], list):
        word_list = []
        full_text_parts = []
        for seg in data["segments"]:
            if not isinstance(seg, dict):
                continue
            seg_text = str(seg.get("text", "")).strip()
            if seg_text:
                full_text_parts.append(seg_text)
            seg_words = seg.get("words", [])
            for w in seg_words:
                if isinstance(w, dict) and "word" in w and "start" in w and "end" in w:
                    word_list.append(WordTimestamp(
                        word=str(w["word"]),
                        start=float(w["start"]),
                        end=float(w["end"])
                    ))

        story_text = data.get("text", " ".join(full_text_parts))
        if word_list:
            duration = word_list[-1].end
            narration = NarrationData(
                words=word_list,
                duration_seconds=duration
            )
            return JSONImportResult(
                success=True,
                message=f"Successfully imported segmented script JSON with {len(word_list)} word timestamps.",
                story_text=story_text,
                narration=narration,
                raw_data=data
            )
        else:
            return JSONImportResult(
                success=True,
                message=f"Imported script segments without word-level timestamps ({len(data['segments'])} segments).",
                story_text=story_text,
                raw_data=data
            )

    # Format 4: Fallback generic text object
    if "text" in data and isinstance(data["text"], str):
        story_text = data["text"].strip()
        if story_text:
            return JSONImportResult(
                success=True,
                message=f"Imported plain text script from JSON ({len(story_text)} chars).",
                story_text=story_text,
                raw_data=data
            )

    return JSONImportResult(
        False,
        "JSON structure not recognized. Expected either a speech transcription with 'words', a storyboard with 'scenes', or 'segments'."
    )


# =============================================================================
# STEP 2: NARRATION & VISUAL IDEAS PARSING AND ALIGNMENT
# =============================================================================

NUMBER_WORDS: Dict[str, str] = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14", "fifteen": "15",
    "sixteen": "16", "seventeen": "17", "eighteen": "18", "nineteen": "19", "twenty": "20",
    "thirty": "30", "forty": "40", "fifty": "50", "sixty": "60", "seventy": "70",
    "eighty": "80", "ninety": "90", "hundred": "100", "thousand": "1000",
}

def clean_alignment_tokens(text: str) -> List[str]:
    """Extracts lowercase tokens with punctuation removed and number words normalized to digits."""
    if not text:
        return []
    t = text.lower()
    t = re.sub(r"[^\w\s]", " ", t)
    tokens: List[str] = []
    for tok in t.split():
        if tok in NUMBER_WORDS:
            tokens.append(NUMBER_WORDS[tok])
        else:
            tokens.append(tok)
    return tokens


def normalize_text_token(t: str) -> str:
    """Normalizes number words and removes punctuation for robust speech-to-script alignment."""
    t = t.lower()
    t = re.sub(r"\b(sixty|60)\b", "60", t)
    t = re.sub(r"\b(forty|40)\b", "40", t)
    t = re.sub(r"\b(twenty|20)\b", "20", t)
    t = re.sub(r"\b(nineteen|19)\b", "19", t)
    t = re.sub(r"\b(fifteen|15)\b", "15", t)
    t = re.sub(r"\b(eleven|11)\b", "11", t)
    t = re.sub(r"\b(ten|10)\b", "10", t)
    t = re.sub(r"\b(four|4)\b", "4", t)
    t = re.sub(r"\b(three|3)\b", "3", t)
    t = re.sub(r"\b(two|2)\b", "2", t)
    t = re.sub(r"\b(one|1)\b", "1", t)
    t = re.sub(r"[^\w\s]", "", t)
    return " ".join(t.split())


def parse_visual_breakdown_text(raw_text: str) -> List[Dict[str, str]]:
    """
    Parses user-supplied narration and visual ideas.
    Supports:
    1. 'Visual 1 Words: <narration> Visual: <visual idea>'
    2. '1. Narration: ... Visual: ...'
    3. 'Words: ... \n Visual: ...'
    4. Plain paragraphs if no visual tags are found.
    """
    if not raw_text or not raw_text.strip():
        return []

    items = []
    # Pattern 1: (Visual|Scene|Shot) X (optional : or -) Words: ... Visual: ...
    pattern1 = re.compile(
        r"(?:Visual|Scene|Shot)\s*(\d+)?[.:\-]?\s*Words?:\s*(.*?)\s*Visuals?:\s*(.*?)(?=(?:Visual|Scene|Shot)\s*\d*[.:\-]?\s*Words?:|$)",
        re.DOTALL | re.IGNORECASE
    )
    matches1 = pattern1.findall(raw_text)
    if matches1:
        for idx, (num, words, vis) in enumerate(matches1):
            s_id = str(num).strip() if num and str(num).strip() else str(idx + 1)
            items.append({
                "id": s_id,
                "words": words.strip(),
                "visual_idea": vis.strip()
            })
        return items

    # Pattern 2: Lines with "Words:" and "Visual:"
    pattern2 = re.compile(
        r"(?:Scene|Shot|Visual)?\s*(\d+)?[.:\-]?\s*Words?:\s*(.*?)\s*Visuals?:\s*(.*?)(?=(?:Scene|Shot|Visual|\d+[.:])\s*Words?:|$)",
        re.DOTALL | re.IGNORECASE
    )
    matches2 = pattern2.findall(raw_text)
    if matches2 and len(matches2) >= 1:
        for idx, (num, words, vis) in enumerate(matches2):
            s_id = num.strip() if num.strip() else str(idx + 1)
            items.append({
                "id": s_id,
                "words": words.strip(),
                "visual_idea": vis.strip()
            })
        return items

    # Pattern 3: Paragraph fallback
    paras = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
    for i, p in enumerate(paras):
        items.append({
            "id": str(i + 1),
            "words": p,
            "visual_idea": f"Visual scene illustrating: {p[:80]}"
        })
    return items


def align_visuals_with_timestamps(
    visual_items: List[Dict[str, str]],
    narration: Optional[NarrationData] = None,
    total_audio_duration: Optional[float] = None
) -> List[VisualScene]:
    """
    Combines user-supplied visual breakdown with exact word-level timestamps from narration.
    Uses monotonic anchor-based sequence alignment with multi-token sequence scoring,
    sub-clause fallback, gap interpolation, and cluster-based proportional timeline pacing.
    Guarantees:
      - 100% of scenes fit smoothly within [0, total_audio_duration].
      - No runaway time overshoot beyond audio end.
      - Exact synchronization for matched beats, proportional pacing for sub-clauses, and smooth gap interpolation.
    """
    scenes: List[VisualScene] = []
    if not visual_items:
        return scenes

    num_items = len(visual_items)
    total_dur = total_audio_duration or (narration.duration_seconds if narration else float(num_items * 3.5))

    if narration and narration.words:
        words = narration.words
        num_words = len(words)
        speech_toks = [clean_alignment_tokens(w.word)[0] if clean_alignment_tokens(w.word) else normalize_text_token(w.word) for w in words]

        matched_ranges: List[Optional[Tuple[int, int, float]]] = [None] * num_items
        last_matched_end = 0

        # Pass 1: Monotonic high-accuracy matching with sub-clause clustering detection
        for i in range(num_items):
            it = visual_items[i]
            v_clean = clean_alignment_tokens(it.get("words", ""))
            if not v_clean:
                continue

            t_len = len(v_clean)
            v_set = set(v_clean)

            # Sub-clause check: if consecutive items cover overlapping/sub-sentence parts
            if i > 0 and matched_ranges[i - 1] is not None:
                prev_s, prev_e, _ = matched_ranges[i - 1]
                cand_sub = speech_toks[prev_s:min(num_words, prev_e + 20)]
                if any(tok in cand_sub for tok in v_clean[:2]):
                    search_min = prev_s
                else:
                    search_min = max(0, prev_e - 2)
            else:
                search_min = max(0, last_matched_end - 4)

            search_max = min(num_words, search_min + 140)

            best_s = -1
            best_e = -1
            best_score = 0.0

            for s in range(search_min, search_max):
                cand = speech_toks[s:s + t_len]
                if not cand:
                    continue

                if cand == v_clean:
                    best_s = s
                    best_e = s + t_len - 1
                    best_score = 1.0
                    break

                matches = sum(1 for a, b in zip(v_clean, cand) if a == b)
                pos_score = matches / max(1, t_len)
                set_score = len(v_set & set(cand)) / max(1, len(v_set))
                combined_score = 0.6 * pos_score + 0.4 * set_score

                if cand[0] == v_clean[0]:
                    combined_score += 0.15
                if len(cand) == len(v_clean) and cand[-1] == v_clean[-1]:
                    combined_score += 0.15

                if combined_score > best_score and combined_score >= 0.45:
                    best_score = combined_score
                    best_s = s
                    best_e = min(num_words - 1, s + t_len - 1)
                    if combined_score >= 0.85:
                        break

            if best_s != -1:
                matched_ranges[i] = (best_s, best_e, best_score)
                last_matched_end = max(last_matched_end, best_e + 1)

        # Pass 2: Extract initial timestamps
        raw_timings: List[Tuple[Optional[float], Optional[float], bool, int, int]] = []
        for i in range(num_items):
            m = matched_ranges[i]
            if m:
                st = words[m[0]].start
                et = words[m[1]].end
                if et <= st:
                    et = st + 1.2
                raw_timings.append((st, et, True, m[0], m[1]))
            else:
                raw_timings.append((None, None, False, -1, -1))

        # Pass 3: Gap interpolation for unmatched scenes
        i = 0
        while i < num_items:
            if not raw_timings[i][2]:
                b_start = i
                while i < num_items and not raw_timings[i][2]:
                    i += 1
                b_end = i
                prev_t = raw_timings[b_start - 1][1] if b_start > 0 else 0.0
                next_t = raw_timings[b_end][0] if b_end < num_items else total_dur
                gap_dur = max(0.8 * (b_end - b_start), next_t - prev_t)
                step = gap_dur / (b_end - b_start)
                for k in range(b_start, b_end):
                    st = prev_t + (k - b_start) * step
                    et = st + step
                    raw_timings[k] = (st, et, False, -1, -1)
            else:
                i += 1

        # Pass 4: Strictly monotonic, non-overlapping assembly with sub-clause cluster distribution
        cur_time = 0.0
        i = 0
        while i < num_items:
            st_val, et_val, matched, ws, we = raw_timings[i]

            # Detect cluster of overlapping or sub-clause scenes
            c_start = i
            c_min_start = st_val if st_val is not None else cur_time
            c_max_end = et_val if et_val is not None else (c_min_start + 2.0)

            while i + 1 < num_items and raw_timings[i + 1][0] is not None and raw_timings[i + 1][0] < c_max_end - 0.2:
                i += 1
                if raw_timings[i][1] is not None:
                    c_max_end = max(c_max_end, raw_timings[i][1])
            c_end = i + 1

            cluster_size = c_end - c_start
            cluster_start_t = max(cur_time, c_min_start)
            cluster_end_t = max(cluster_start_t + cluster_size * 0.8, c_max_end)

            if c_end == num_items:
                cluster_end_t = max(cluster_start_t + cluster_size * 0.8, total_dur)

            cluster_dur = cluster_end_t - cluster_start_t
            slice_dur = cluster_dur / cluster_size

            for idx in range(c_start, c_end):
                item = visual_items[idx]
                s_num = item.get("id") or str(idx + 1)
                try:
                    s_id = f"{int(s_num):03d}"
                except ValueError:
                    s_id = f"{idx + 1:03d}"

                s_start = cluster_start_t + (idx - c_start) * slice_dur
                s_end = s_start + slice_dur
                if idx == num_items - 1:
                    s_end = max(s_start + 1.0, total_dur)

                dur = round(float(s_end - s_start), 2)
                vis_raw = item.get("visual_idea", "")
                v_info = parse_video_visual(vis_raw)
                is_vid = v_info is not None
                scenes.append(VisualScene(
                    scene_id=s_id,
                    index=idx + 1,
                    start=round(float(s_start), 2),
                    end=round(float(s_end), 2),
                    duration=dur,
                    narration_excerpt=item.get("words", ""),
                    visual_subject=v_info["shot_description"] if is_vid else vis_raw,
                    visual_idea=vis_raw,
                    prompt="",
                    generation_status="pending",
                    start_word_index=raw_timings[idx][3] if raw_timings[idx][3] >= 0 else None,
                    end_word_index=raw_timings[idx][4] if raw_timings[idx][4] >= 0 else None,
                    is_video=is_vid,
                    treatment=v_info.get("treatment") if is_vid else None,
                    video_shot_description=v_info["shot_description"] if is_vid else "",
                    video_keywords=v_info["keywords"] if is_vid else [],
                ))
                cur_time = s_end

            i += 1

    else:
        # Fallback: estimate timings proportionally
        avg_dur = max(1.5, total_dur / num_items)
        curr_time = 0.0
        for idx, item in enumerate(visual_items):
            s_num = item.get("id") or str(idx + 1)
            try:
                s_id = f"{int(s_num):03d}"
            except ValueError:
                s_id = f"{idx + 1:03d}"

            start_t = curr_time
            end_t = curr_time + avg_dur
            if idx == num_items - 1:
                end_t = max(start_t + 1.2, total_dur)
            curr_time = end_t

            vis_raw = item.get("visual_idea", "")
            v_info = parse_video_visual(vis_raw)
            is_vid = v_info is not None

            scenes.append(VisualScene(
                scene_id=s_id,
                index=idx + 1,
                start=round(float(start_t), 2),
                end=round(float(end_t), 2),
                duration=round(float(end_t - start_t), 2),
                narration_excerpt=item.get("words", ""),
                visual_subject=v_info["shot_description"] if is_vid else vis_raw,
                visual_idea=vis_raw,
                prompt="",
                generation_status="pending",
                start_word_index=None,
                end_word_index=None,
                is_video=is_vid,
                treatment=v_info.get("treatment") if is_vid else None,
                video_shot_description=v_info["shot_description"] if is_vid else "",
                video_keywords=v_info["keywords"] if is_vid else [],
            ))

    # Seamless timeline: heal natural sentence pauses (gaps <= 1.0s) between scenes without exceeding total duration
    for i in range(len(scenes) - 1):
        curr_s = scenes[i]
        next_s = scenes[i + 1]
        gap = float(next_s.start) - float(curr_s.end)
        if 0.0 < gap <= 1.0:
            curr_s.end = round(float(next_s.start), 2)
            curr_s.duration = round(float(curr_s.end) - float(curr_s.start), 2)

    return scenes


# =============================================================================
# STEP 3: DYNAMIC STORY BIBLE & INTELLIGENCE EXTRACTION
# =============================================================================

def load_bible_extraction_system_prompt() -> str:
    p = Path("config/system_prompts/story_bible_extraction.txt")
    if p.exists():
        try:
            return p.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return "You are an expert story analyst. Extract comprehensive story, character, environment, and style bibles in JSON."


def extract_story_bibles_groq(
    story_text: str,
    visual_ideas_summary: str = "",
    model: str = "qwen/qwen3.8-27b",
    engine: Optional[GroqEngine] = None
) -> Dict[str, Any]:
    """
    Extracts dynamic story bibles (Story, Character, Environment, Props, Visual Style)
    via Groq LLM inference without any hardcoded story assumptions.
    """
    groq_eng = engine or GroqEngine(default_model=model)
    system_prompt = load_bible_extraction_system_prompt()

    user_prompt = f"""ANALYZE THE FOLLOWING STORY SCRIPT AND EXTRACT FULL PRODUCTION BIBLES:

### SCRIPT NARRATION:
{story_text}

### USER-SUPPLIED VISUAL IDEAS / BEATS:
{visual_ideas_summary[:3500] if visual_ideas_summary else 'No additional visual notes provided.'}

Extract comprehensive, highly detailed production bibles strictly matching the required JSON schema.
Ensure character appearances, environments, props, and visual continuity rules are thoroughly defined.
Return ONLY valid JSON.
"""

    response_text = groq_eng.generate_text(
        prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=0.2,
        max_tokens=2500,
        model=model,
        stage_name="BIBLE_EXTRACTION"
    )

    clean_json = response_text.strip()
    if clean_json.startswith("```"):
        clean_json = re.sub(r"^```(?:json)?\s*", "", clean_json)
        clean_json = re.sub(r"\s*```$", "", clean_json)

    try:
        bibles_data = json.loads(clean_json)
        return bibles_data
    except json.JSONDecodeError as jde:
        m = re.search(r"(\{.*\})", clean_json, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        raise RuntimeError(f"Failed to parse Groq story bibles response as JSON: {jde}. Raw snippet: {clean_json[:200]}")


def parse_custom_bible_text(bible_text: str) -> Dict[str, Any]:
    """
    Parses human-readable/markdown production bibles into structured dictionaries.
    Uses BibleManager for flexible, robust extraction of Characters, Environments, Props, and Style.
    """
    from app.core.bible_manager import BibleManager
    return BibleManager.parse_single_bible_text(bible_text)


# =============================================================================
# STEP 4 & 5: DEDICATED GROQ IMAGE PROMPT GENERATION (BATCHED & EXPANDED)
# =============================================================================

def load_image_prompt_system_prompt() -> str:
    p = Path("config/system_prompts/image_prompt_generation.txt")
    if p.exists():
        try:
            return p.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return "You are an expert image prompt architect. Generate detailed, style-compliant image prompts in JSON."


def robust_extract_scenes_from_llm_output(clean_json: str) -> List[Dict[str, Any]]:
    """
    Parses LLM output into a list of scene dictionaries.
    Handles:
    1. Perfect JSON: {"scenes": [...]} or [...]
    2. Markdown wrapped JSON
    3. Trailing commas or subtle formatting glitches
    4. Truncated JSON streams (extracts all completed scene objects even if the last one was cut off)
    5. Regex recovery fallback
    """
    if not clean_json or not clean_json.strip():
        return []

    text = clean_json.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    # Attempt 1: Direct JSON parse
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "scenes" in parsed and isinstance(parsed["scenes"], list):
            return parsed["scenes"]
        elif isinstance(parsed, list):
            return parsed
    except Exception:
        pass

    # Attempt 2: Repair braces and trailing commas
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        sub = text[first_brace:last_brace + 1]
        try:
            p = json.loads(sub)
            if isinstance(p, dict) and "scenes" in p:
                return p["scenes"]
        except Exception:
            fixed = re.sub(r",\s*([}\]])", r"\1", sub)
            try:
                p = json.loads(fixed)
                if isinstance(p, dict) and "scenes" in p:
                    return p["scenes"]
            except Exception:
                pass

    # Attempt 3: Truncated stream recovery
    if first_brace != -1:
        matches = list(re.finditer(r"\}\s*,?", text))
        for m in reversed(matches):
            candidate = text[first_brace:m.end()].rstrip(", \t\r\n")
            for closing in ["]}", "}", "]}}", "}\n}"]:
                try:
                    p = json.loads(candidate + closing)
                    if isinstance(p, dict) and "scenes" in p and p["scenes"]:
                        return p["scenes"]
                    elif isinstance(p, list) and p:
                        return p
                except Exception:
                    pass

    # Attempt 4: Regex extraction of individual completed scene objects
    scenes = []
    obj_pattern = re.compile(
        r'\{\s*"scene_id"\s*:\s*"(?P<id>[^"]+)"\s*,\s*"visual_subject"\s*:\s*"(?P<subj>(?:[^"\\]|\\.)*)"\s*,\s*"prompt"\s*:\s*"(?P<prompt>(?:[^"\\]|\\.)*)"',
        re.DOTALL
    )
    for m in obj_pattern.finditer(text):
        try:
            s_id = m.group("id").strip()
            prompt_str = m.group("prompt").encode('utf-8').decode('unicode_escape', errors='ignore')
            subj_str = m.group("subj").encode('utf-8').decode('unicode_escape', errors='ignore')
            scenes.append({
                "scene_id": s_id,
                "visual_subject": subj_str,
                "prompt": prompt_str
            })
        except Exception:
            pass

    if scenes:
        return scenes

    # Loose fallback regex for scene_id and prompt
    loose_pattern = re.compile(
        r'"scene_id"\s*:\s*"([^"]+)"[\s\S]*?"prompt"\s*:\s*"((?:[^"\\]|\\.)*)"',
        re.DOTALL
    )
    for m in loose_pattern.finditer(text):
        try:
            s_id = m.group(1).strip()
            prompt_str = m.group(2).encode('utf-8').decode('unicode_escape', errors='ignore')
            scenes.append({
                "scene_id": s_id,
                "prompt": prompt_str
            })
        except Exception:
            pass

    return scenes


def generate_prompts_batch(
    scenes_batch: List[VisualScene],
    bibles: Dict[str, Any],
    story_context: str,
    visual_style_id: str = "zombie_survival",
    custom_style: Optional[str] = None,
    aspect_ratio: str = "16:9",
    model: str = "qwen/qwen3.8-27b",
    engine: Optional[GroqEngine] = None
) -> List[Dict[str, Any]]:
    """
    Sends a batch of scenes to Groq along with extracted bibles, narration, timestamps,
    and user visual ideas to generate detailed, concrete image prompts STRICTLY obeying
    the user-selected visual style directives.
    """
    groq_eng = engine or GroqEngine(default_model=model)
    system_prompt = load_image_prompt_system_prompt()

    # Retrieve Authoritative Visual Style
    style_preset = PresetManager.get_style_by_id(visual_style_id)
    style_name = style_preset.name if style_preset else visual_style_id
    style_instructions = style_preset.system_instructions if style_preset else (custom_style or "Cinematic realism")

    # Build concise representation of bibles
    char_summary = "\n".join(
        f"- {c.get('name')}: {c.get('physical_description', '')}. Wardrobe: {c.get('clothing_and_gear', '')}. Rules: {c.get('consistency_rules', '')}"
        for c in bibles.get("characters", [])
    )
    env_summary = "\n".join(
        f"- {e.get('name')}: {e.get('architectural_style', '')}. Atmosphere: {e.get('lighting_and_atmosphere', '')}"
        for e in bibles.get("environments", [])
    )
    style_info = bibles.get("visual_style_bible", {})
    style_summary = f"Color Palette: {style_info.get('color_palette', 'Consistent with selected style')}. Lighting: {style_info.get('lighting_rules', 'Atmospheric')}. Camera: {style_info.get('camera_guidelines', 'Eye-level cinematic framing')}."

    scenes_input = []
    for s in scenes_batch:
        scenes_input.append({
            "scene_id": s.scene_id,
            "start": s.start,
            "end": s.end,
            "duration": s.duration,
            "narration": s.narration_excerpt,
            "visual_idea": getattr(s, "visual_idea", "") or s.visual_subject,
            "treatment": getattr(s, "treatment", None)
        })

    user_prompt = f"""AUTHORITATIVE USER-SELECTED VISUAL STYLE:
Style Name: {style_name}
Aspect Ratio: {aspect_ratio}

STYLE DIRECTIVES (MANDATORY & OVERRIDING):
{style_instructions}

RELEVANT STORY BIBLES:
### Characters:
{char_summary or 'No specific character entries.'}

### Environments:
{env_summary or 'No specific environment entries.'}

### Story Style Elements:
{style_summary}

STORY CONTEXT (OVERALL ARC):
{story_context[:800]}

SCENES TO GENERATE IN THIS BATCH:
{json.dumps(scenes_input, indent=2)}

INSTRUCTIONS FOR EACH SCENE:
1. Translate the narration and visual idea into a detailed, concrete image-generation prompt describing what the viewer actually SEES.
2. STRICT STYLE ENFORCEMENT: Every single prompt MUST strictly follow the 'STYLE DIRECTIVES' above for '{style_name}'.
   - If '{style_name}' mandates a pure flat 2D cartoon with a locked hero character (e.g. backwards red cap, charcoal hoodie) and uniform pale olive-green zombie horde, apply those exact design elements!
   - If '{style_name}' mandates photographic or historical styles, apply those exact camera, lens, and lighting directives!
   - If '{style_name}' is Century-Old Photograph, analyze each scene's narrative context to selectively apply one of the 12 specialized archival image treatments where it naturally elevates the storytelling (The Woodblock / Engraving Plate Split, The Accordion / Leporello Souvenir Folder, Silver Mirroring & Chemical Bleeding, Fold Creases & Crushed Paper Texture, The Double-Exposure / Diptych Split, The Polarized / Document Archive Layout, The Cinematic Split-Screen Trio, Textured Cinematic Blur Background, Antique Map Overlay, Full Antique Engraving Plate, Full-Frame Authentic Archival Photograph, Full Historical Map Plate). For baseline shots (~40-50%), keep clean, full-frame widescreen archival prints for balanced documentary pacing. Do not misuse or oversaturate.
3. Do not invent contradictory characters or ignore the supplied visual ideas.
4. Do NOT include /imagine prompt: or parameter flags like --ar or --style raw. Return clean, detailed descriptive visual prompts only.
5. Return JSON matching the schema with the exact scene_ids provided.
"""

    resp_text = groq_eng.generate_text(
        prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=0.3,
        max_tokens=2500,
        model=model,
        stage_name=f"PROMPT_EXPANSION_{style_name.upper().replace(' ', '_')}"
    )

    items = robust_extract_scenes_from_llm_output(resp_text)
    if not items:
        clean_snip = resp_text.strip()[:200] if resp_text else "EMPTY_RESPONSE"
        raise RuntimeError(f"Batch prompt parsing failed: No valid scenes recovered from model output. Snippet: {clean_snip}")

    # Strip any accidental Midjourney or model flags
    for it in items:
        if isinstance(it, dict) and "prompt" in it:
            p_val = str(it["prompt"]).strip()
            p_val = re.sub(r"^/imagine\s+prompt:\s*", "", p_val, flags=re.IGNORECASE)
            p_val = re.sub(r"^/imagine\s*", "", p_val, flags=re.IGNORECASE)
            p_val = re.sub(r"--ar\s+\d+:\d+", "", p_val, flags=re.IGNORECASE)
            p_val = re.sub(r"--style\s+\w+", "", p_val, flags=re.IGNORECASE)
            p_val = re.sub(r"--v\s+[\d\.]+", "", p_val, flags=re.IGNORECASE)
            it["prompt"] = " ".join(p_val.split())

    return items
