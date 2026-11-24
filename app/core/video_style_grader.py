"""
Style Grading Engine for B-Roll Stock Video Footage in PromptBeast / Vidroa.
Processes every accepted video clip toward the target visual style before rendering:
  - Century-old style: sepia grade + animated grain + subtle flicker + vignette
  - Flat 2D cartoon styles: cartoonize pass (posterize + edge detect)
  - General styles: subtle cinematic tone grade
Never leaves a clip raw and ungraded.
"""
import subprocess
from pathlib import Path
from typing import Optional


# FFmpeg filtergraph definitions for style grading
CENTURY_OLD_FILTER = (
    "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131,"
    "vignette=PI/4,"
    "noise=alls=15:allf=t+u,"
    "eq=brightness='0.03*sin(16*PI*t)'"
)

# Authentic Archival Photography: same sepia grade as century-old
ARCHIVAL_PHOTOGRAPHY_FILTER = CENTURY_OLD_FILTER

# Antique Engraving: high-contrast ink-like grade for footage
ANTIQUE_ENGRAVING_FILTER = (
    "format=gray,"
    "eq=contrast=1.75:brightness=-0.05,"
    "colorchannelmixer=.92:.92:.92:0:.88:.88:.88:0:.80:.80:.80"
)

# Historical Maps: light sepia grade, footage used with antique warm parchment tone
HISTORICAL_MAPS_FILTER = (
    "colorchannelmixer=.5:.5:0:0:.4:.5:.1:0:.3:.4:.3:0,"
    "eq=contrast=1.05:saturation=0.8"
)

FLAT_2D_CARTOON_FILTER = (
    "lutrgb=r='trunc(val/64)*64':g='trunc(val/64)*64':b='trunc(val/64)*64',"
    "smartblur=lr=2.0:ls=-0.5,"
    "edgedetect=low=0.1:high=0.3:mode=colormix"
)

GENERAL_CINEMATIC_FILTER = "eq=contrast=1.06:saturation=1.05:gamma=0.98"


def get_style_filter(style_id: str = "century_old_photograph", treatment: Optional[str] = None) -> str:
    """
    Returns the appropriate FFmpeg grading filter chain for the given style and treatment.
    For Century-Old Photograph style:
      - treatment="antique_engraving" (or containing engraving): returns ANTIQUE_ENGRAVING_FILTER
      - treatment="authentic_archival" (or containing archival): returns ARCHIVAL_PHOTOGRAPHY_FILTER
      - treatment="historical_maps" (or containing map): returns HISTORICAL_MAPS_FILTER
      - default (no treatment): returns CENTURY_OLD_FILTER (sepia + grain + flicker + vignette)
    """
    s = (style_id or "").lower().strip()
    t = (treatment or "").lower().strip()

    if any(k in s for k in ["century_old", "vintage", "archival", "sepia", "history"]):
        if any(k in t for k in ["antique_engraving", "engraving", "copperplate", "etching", "10"]):
            return ANTIQUE_ENGRAVING_FILTER
        elif any(k in t for k in ["historical_maps", "map", "maps", "cartography", "12"]):
            return HISTORICAL_MAPS_FILTER
        elif any(k in t for k in ["authentic_archival", "archival_photography", "archival_photo", "11"]):
            return ARCHIVAL_PHOTOGRAPHY_FILTER
        else:
            return CENTURY_OLD_FILTER

    if any(k in s for k in ["flat", "2d", "cartoon", "vector", "stickman", "anime"]):
        return FLAT_2D_CARTOON_FILTER
    else:
        return GENERAL_CINEMATIC_FILTER


def grade_video_clip(
    input_path: str,
    output_path: str,
    style_id: str = "century_old_photograph",
    treatment: Optional[str] = None,
) -> str:
    """
    Applies style and treatment grading to an input video clip using FFmpeg.
    Ensures the clip is never used raw.
    """
    filter_chain = get_style_filter(style_id=style_id, treatment=treatment)
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", filter_chain,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-an",
        str(out_p.resolve())
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg style grading failed on {input_path}:\n{proc.stderr}")

    return str(out_p.resolve())
