"""
Data models for video rendering, subtitle styling, motion presets, and multi-engine TTS synthesis.
"""
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AspectRatio(str, Enum):
    LANDSCAPE_16_9 = "16:9"   # 1920x1080 (YouTube, Standard Video)
    VERTICAL_9_16 = "9:16"    # 1080x1920 (TikTok, Shorts, Reels)
    SQUARE_1_1 = "1:1"        # 1080x1080 (Instagram, Square Feed)

    @property
    def dimensions(self) -> tuple[int, int]:
        if self == AspectRatio.VERTICAL_9_16:
            return (1080, 1920)
        elif self == AspectRatio.SQUARE_1_1:
            return (1080, 1080)
        return (1920, 1080)


class MotionPreset(str, Enum):
    ZOOM_IN = "zoom_in"             # Ken Burns: Smooth Slow Zoom In
    ZOOM_OUT = "zoom_out"           # Ken Burns: Smooth Slow Zoom Out
    PAN_LEFT_RIGHT = "pan_lr"       # Pan Left to Right
    PAN_RIGHT_LEFT = "pan_rl"       # Pan Right to Left
    SUBTLE_ALTERNATING = "subtle"   # Alternates zoom in and zoom out per scene
    STATIC = "static"               # Still image with no camera movement


class VideoOverlay(str, Enum):
    NONE = "none"
    SUBTLE_VIGNETTE = "vignette"
    LETTERBOX_CINEMATIC = "letterbox"  # 2.35:1 Cinematic black bars
    FILM_GRAIN = "film_grain"


class SubtitlePreset(str, Enum):
    HORMOZI_KARAOKE = "hormozi_karaoke"       # 🔥 Hormozi: Bold active yellow karaoke word pop, thick outline
    CINEMATIC_GOLD = "cinematic_gold"         # 🎬 Cinematic Gold: Warm gold highlight, soft serif/sans, clean shadow
    NEON_CYBERPUNK = "neon_cyberpunk"         # ⚡ Neon Cyber: Cyan/Lime electric glow, deep dark outline
    MRBEAST_BOLD = "mrbeast_bold"             # 💥 MrBeast Bold: Punchy red & yellow, heavy black stroke
    MINIMALIST_CLEAN = "minimalist_clean"     # ✨ Minimalist: Pure white, clean modern sans, crisp shadow
    BOXED_DARK = "boxed_dark"                 # ⬛ Dark Boxed: Semi-transparent backdrop box, yellow karaoke
    TIKTOK_POP = "tiktok_pop"                 # 🔮 TikTok Pop: Vivid pastel pink highlight, bold rounded font
    DOCUMENTARY_TOP = "documentary_top"       # 📜 Documentary Top: Upper-third gold & white header style
    RETRO_SYNTHWAVE = "retro_synthwave"       # 🚀 Retro Synth: Hot magenta & neon cyan gradient vibe
    CLEAN_STORYTELLER = "clean_storyteller"   # 📖 Storyteller: Warm cream base, amber highlight, elegant
    NONE = "none"                             # 🚫 None: No burned-in subtitles


class SubtitleConfig(BaseModel):
    preset: SubtitlePreset = SubtitlePreset.HORMOZI_KARAOKE
    font_name: str = "Impact"
    font_size: int = 32
    primary_color_hex: str = "#FFFFFF"        # Base text color (White)
    highlight_color_hex: str = "#FFD700"      # Active word karaoke color (Gold/Yellow)
    outline_color_hex: str = "#000000"        # Outline / border color (Black)
    outline_width: int = 3
    shadow_depth: int = 1
    alignment: int = 2                        # ASS alignment: 2 = Bottom Center, 8 = Top Center, 5 = Middle Center
    margin_v: int = 40                        # Vertical margin from screen edge in pixels
    is_karaoke: bool = True                   # Highlight word by word in sync with narration


class TTSEngineType(str, Enum):
    KOKORO = "kokoro"            # Ultra-realistic expressive local neural (models/kokoro/)
    PIPER = "piper"              # Fast lightweight local neural (models/piper/)


class TTSVoice(BaseModel):
    voice_id: str
    name: str
    gender: str
    locale: str = "en-US"
    language_name: str = "English (United States)"
    engine: TTSEngineType = TTSEngineType.KOKORO
    description: str = ""


class TTSConfig(BaseModel):
    engine: TTSEngineType = TTSEngineType.KOKORO
    voice_id: str = "kokoro:af"
    language_locale: str = "en-US"
    rate_percentage: int = 0                  # e.g. +10% or -10%
    pitch_percentage: int = 0                 # e.g. +5% or -5%
    volume_percentage: int = 0


class VideoRenderSettings(BaseModel):
    aspect_ratio: AspectRatio = AspectRatio.LANDSCAPE_16_9
    fps: int = 30
    motion_preset: MotionPreset = MotionPreset.STATIC
    motion_intensity: float = 1.15            # Zoom factor (1.15 = 15% zoom)
    hook_clips_count: int = 3                 # First N scenes rendered with high-retention animated motion / clips
    hook_motion_intensity: float = 1.25       # Dynamic camera intensity for hook scenes
    video_overlay: VideoOverlay = VideoOverlay.SUBTLE_VIGNETTE
    subtitle_config: SubtitleConfig = Field(default_factory=SubtitleConfig)
    tts_config: TTSConfig = Field(default_factory=TTSConfig)
    output_filename: str = "final_video.mp4"
