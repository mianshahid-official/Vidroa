"""
Video visual parser for PromptBeast / Vidroa.
Parses machine-parseable video visual descriptions from storyboards:
Format:
  Visual: VIDEO of <shot description> KEYWORDS <keyword 1>, <keyword 2>, ...
"""
import re
from typing import Optional, Dict, Any, List


def parse_video_visual(visual_text: str) -> Optional[Dict[str, Any]]:
    """
    Parses a visual description string.
    If it starts with 'VIDEO of', extracts:
      - is_video: True
      - shot_description: str
      - keywords: List[str]
    If it is a normal image visual, returns None.
    """
    if not visual_text:
        return None

    cleaned = visual_text.strip()
    # Check if starts with "VIDEO of" (case-insensitive check for robustness)
    pattern = re.compile(r"^VIDEO\s+of\s+(.*)", re.IGNORECASE | re.DOTALL)
    match = pattern.match(cleaned)
    if not match:
        return None

    rest = match.group(1).strip()
    shot_desc = rest
    keywords: List[str] = []

    # Look for "KEYWORDS" selector
    kw_match = re.search(r"(?:^|\s+)KEYWORDS\s*[:\s]\s*(.*)$", rest, re.IGNORECASE | re.DOTALL)
    if kw_match:
        shot_desc = rest[:kw_match.start()].strip()
        raw_keywords = kw_match.group(1).strip()
        # Split by comma
        for k in raw_keywords.split(","):
            kw = k.strip().rstrip(".").strip()
            if kw:
                keywords.append(kw)
    else:
        # Check if KEYWORDS appears without colon
        kw_match2 = re.search(r"(?:^|\s+)KEYWORDS\s+(.*)$", rest, re.IGNORECASE | re.DOTALL)
        if kw_match2:
            shot_desc = rest[:kw_match2.start()].strip()
            raw_keywords = kw_match2.group(1).strip()
            for k in raw_keywords.split(","):
                kw = k.strip().rstrip(".").strip()
                if kw:
                    keywords.append(kw)

    # Clean up trailing period from shot description if needed
    shot_desc = shot_desc.strip()

    # Detect optional archival image treatment from shot description
    treatment = None
    lower_desc = shot_desc.lower()
    if any(k in lower_desc for k in ["antique engraving", "engraving plate", "copperplate", "etching", "treatment 10"]):
        treatment = "antique_engraving"
    elif any(k in lower_desc for k in ["authentic archival", "archival photograph", "silver gelatin", "treatment 11"]):
        treatment = "authentic_archival"
    elif any(k in lower_desc for k in ["historical map", "map plate", "cartography", "period map", "treatment 12"]):
        treatment = "historical_maps"

    return {
        "is_video": True,
        "shot_description": shot_desc,
        "keywords": keywords,
        "treatment": treatment,
    }


def is_video_visual(visual_text: str) -> bool:
    """Returns True if the visual text represents a video visual beat."""
    return parse_video_visual(visual_text) is not None
