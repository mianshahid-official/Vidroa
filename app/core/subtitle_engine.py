"""
Advanced SubStation Alpha (ASS) and SRT subtitle generation engine with word-level karaoke timing.
"""
import re
import shutil
from pathlib import Path
from typing import List, Optional, Any
from app.models.timeline import NarrationData, WordTimestamp
from app.models.video_config import SubtitleConfig, SubtitlePreset


class SubtitleEngine:
    """Generates styled ASS and SRT subtitle files from word timestamps."""

    @staticmethod
    def _hex_to_ass_color(hex_str: str) -> str:
        """Converts #RRGGBB hex color to ASS &H00BBGGRR format."""
        clean = hex_str.lstrip("#")
        if len(clean) != 6:
            return "&H00FFFFFF"
        r = clean[0:2]
        g = clean[2:4]
        b = clean[4:6]
        return f"&H00{b}{g}{r}".upper()

    @staticmethod
    def _format_ass_time(seconds: float) -> str:
        """Formats seconds into ASS timestamp: H:MM:SS.cs (centiseconds)."""
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centis = int(round((seconds - int(seconds)) * 100))
        if centis >= 100:
            centis = 99
        return f"{hours}:{mins:02d}:{secs:02d}.{centis:02d}"

    @staticmethod
    def _format_srt_time(seconds: float) -> str:
        """Formats seconds into SRT timestamp: HH:MM:SS,mmm."""
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int(round((seconds - int(seconds)) * 1000))
        if millis >= 1000:
            millis = 999
        return f"{hours:02d}:{mins:02d}:{secs:02d},{millis:03d}"

    @classmethod
    def generate_ass_subtitles(
        cls,
        narration: NarrationData,
        output_ass_path: str,
        config: Optional[SubtitleConfig] = None,
        words_per_line: int = 5,
        target_w: int = 1920,
        target_h: int = 1080
    ) -> str:
        """
        Generates an Advanced SubStation Alpha (.ass) file with word-by-word karaoke highlight timing.
        """
        cfg = config or SubtitleConfig()
        out_p = Path(output_ass_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        # In ASS karaoke, words start in SecondaryColour and highlight to PrimaryColour
        if cfg.is_karaoke:
            primary_ass = cls._hex_to_ass_color(cfg.highlight_color_hex)
            secondary_ass = cls._hex_to_ass_color(cfg.primary_color_hex)
        else:
            primary_ass = cls._hex_to_ass_color(cfg.primary_color_hex)
            secondary_ass = cls._hex_to_ass_color(cfg.highlight_color_hex)
        outline_ass = cls._hex_to_ass_color(cfg.outline_color_hex)

        is_bold = -1 if cfg.preset in (
            SubtitlePreset.HORMOZI_KARAOKE,
            SubtitlePreset.MRBEAST_BOLD,
            SubtitlePreset.NEON_CYBERPUNK,
            SubtitlePreset.TIKTOK_POP,
            SubtitlePreset.RETRO_SYNTHWAVE,
            SubtitlePreset.DOCUMENTARY_TOP
        ) else 0

        border_style = 3 if cfg.preset == SubtitlePreset.BOXED_DARK else 1

        # Scale font size so subtitles are prominently visible on 1080p+ canvas
        effective_font_size = cfg.font_size
        if effective_font_size < 40:
            effective_font_size = int(round(effective_font_size * 1.8))
        effective_font_size = max(42, min(effective_font_size, 96))

        # Clean font name (strictly NO commas - commas violate ASS V4+ Styles column format and corrupt parsing)
        raw_font = (cfg.font_name or "Arial").split(",")[0].strip()
        font_family = raw_font if raw_font else "Arial"

        res_x = max(720, target_w)
        res_y = max(480, target_h)

        effective_margin_v = int(round(cfg.margin_v * (res_y / 1080.0)))

        header = f"""[Script Info]
Title: PromptBeast Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: {res_x}
PlayResY: {res_y}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_family},{effective_font_size},{primary_ass},{secondary_ass},{outline_ass},&H80000000,{is_bold},0,0,0,100,100,0,0,{border_style},{max(2, cfg.outline_width)},{cfg.shadow_depth},{cfg.alignment},20,20,{effective_margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        events = []
        words = narration.words
        if not words:
            with open(out_p, "w", encoding="utf-8") as f:
                f.write(header)
            return str(out_p.resolve())

        # Group words into short punchy chunks
        chunk_size = 3 if cfg.is_karaoke else words_per_line
        i = 0

        while i < len(words):
            chunk = words[i:i + chunk_size]

            if cfg.is_karaoke:
                # Dynamic Spoken Word Zoom (Hormozi / MrBeast 150% Zoom Pop effect):
                # For each spoken word in the chunk, generate an active Dialogue event where
                # the spoken word scales to 150% (\fscx150\fscy150) with the highlight color,
                # while other words remain at 100% scale in the base color.
                for target_idx, active_w in enumerate(chunk):
                    w_start = active_w.start
                    w_end = active_w.end
                    # Smoothly bridge gaps between words in the same chunk
                    if target_idx + 1 < len(chunk):
                        next_start = chunk[target_idx + 1].start
                        if next_start > w_start:
                            w_end = min(next_start, max(w_end, next_start - 0.02))
                    if w_end <= w_start:
                        w_end = w_start + 0.15

                    word_tokens = []
                    for w_i, w in enumerate(chunk):
                        w_text = w.word
                        if is_bold:
                            w_text = w_text.upper()
                        if w_i == target_idx:
                            # 150% enlarged spoken word with active highlight color
                            word_tokens.append(f"{{\\fscx150\\fscy150\\c{primary_ass}}}{w_text}{{\\fscx100\\fscy100\\c{secondary_ass}}}")
                        else:
                            # Inactive surrounding word in base color at 100%
                            word_tokens.append(f"{{\\fscx100\\fscy100\\c{secondary_ass}}}{w_text}")

                    line_text = " ".join(word_tokens)
                    start_fmt = cls._format_ass_time(w_start)
                    end_fmt = cls._format_ass_time(w_end)
                    event_line = f"Dialogue: 0,{start_fmt},{end_fmt},Default,,0,0,0,,{line_text}"
                    events.append(event_line)
            else:
                line_start = chunk[0].start
                line_end = chunk[-1].end
                line_text = " ".join(w.word for w in chunk)
                start_fmt = cls._format_ass_time(line_start)
                end_fmt = cls._format_ass_time(line_end)
                event_line = f"Dialogue: 0,{start_fmt},{end_fmt},Default,,0,0,0,,{line_text}"
                events.append(event_line)

            i += chunk_size

        full_content = header + "\n".join(events) + "\n"
        with open(out_p, "w", encoding="utf-8") as f:
            f.write(full_content)

        return str(out_p.resolve())

    @classmethod
    def synthesize_narration_from_scenes(cls, scenes: List[Any]) -> NarrationData:
        """
        Synthesizes word-level timestamps from visual scenes when dedicated
        Whisper or narration_timestamps.json data is absent.
        Guarantees subtitles are never dropped or omitted during video rendering.
        """
        words: List[WordTimestamp] = []
        full_text_parts: List[str] = []

        for sc in scenes:
            raw_text = (getattr(sc, "narration_excerpt", "") or getattr(sc, "visual_subject", "") or "").strip()
            # Clean outer quotes and excess whitespace
            cleaned = re.sub(r'[\r\n"]+', " ", raw_text).strip()
            tokens = [t for t in cleaned.split() if t]
            if not tokens:
                continue

            full_text_parts.append(cleaned)
            start_t = float(getattr(sc, "start", 0.0))
            end_t = float(getattr(sc, "end", start_t + 4.0))
            dur = max(0.4, end_t - start_t)
            word_dur = dur / float(len(tokens))

            for idx, token in enumerate(tokens):
                w_start = round(start_t + (idx * word_dur), 2)
                w_end = round(start_t + ((idx + 1) * word_dur), 2)
                words.append(WordTimestamp(word=token, start=w_start, end=w_end))

        total_dur = max([float(getattr(sc, "end", 0.0)) for sc in scenes], default=0.0) if scenes else 0.0

        return NarrationData(
            full_text=" ".join(full_text_parts),
            duration_seconds=total_dur,
            words=words
        )

    @classmethod
    def generate_srt_subtitles(
        cls,
        narration: NarrationData,
        output_srt_path: str,
        words_per_line: int = 6
    ) -> str:
        """Generates standard .srt format subtitles."""
        out_p = Path(output_srt_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        lines = []
        words = narration.words
        i = 0
        idx = 1

        while i < len(words):
            chunk = words[i:i + words_per_line]
            start_fmt = cls._format_srt_time(chunk[0].start)
            end_fmt = cls._format_srt_time(chunk[-1].end)
            text = " ".join(w.word for w in chunk)

            lines.append(f"{idx}\n{start_fmt} --> {end_fmt}\n{text}\n")
            idx += 1
            i += words_per_line

        full_content = "\n".join(lines)
        with open(out_p, "w", encoding="utf-8") as f:
            f.write(full_content)

        return str(out_p.resolve())
