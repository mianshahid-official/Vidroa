"""
Negation Beat Detector & Comic Red Cross Overlay Engine for PromptBeast.
Detects negative narration beats ('not', 'never', 'fail', 'wrong', 'don't')
and renders a bold cartoon red cross (❌) over the frame for high viral retention.
"""

import re
from typing import List, Tuple
from PIL import Image, ImageDraw


NEGATION_KEYWORDS = {
    "not", "never", "no", "neither", "nor", "nothing", "nowhere", "none",
    "stop", "wrong", "fail", "failed", "failing", "mistake", "fatal", "ruined",
    "broke", "scam", "false", "destroy", "destroyed", "disaster", "trap",
    "cannot", "can't", "don't", "doesn't", "didn't", "won't", "wouldn't",
}


class NegationDetector:
    """Identifies negation beats in scene narration and provides graphic overlays."""

    @classmethod
    def is_negation_beat(cls, text: str) -> bool:
        """Returns True if the scene dialogue or narration contains a strong negative beat."""
        words = re.findall(r"\b[a-zA-Z']+\b", text.lower())
        for w in words:
            clean = w.strip("'")
            if clean in NEGATION_KEYWORDS:
                return True
        return False

    @classmethod
    def apply_red_cross_overlay(cls, image: Image.Image) -> Image.Image:
        """
        Draws a thick, bold cartoon red cross (❌) with white comic border over the image.
        """
        img = image.convert("RGBA")
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        w, h = img.size
        cx, cy = w // 2, h // 2
        size = int(min(w, h) * 0.35)
        thickness = int(size * 0.22)
        border_thick = int(thickness * 0.35)

        # Diagonal line 1: top-left to bottom-right
        pt1_a = (cx - size, cy - size)
        pt1_b = (cx + size, cy + size)

        # Diagonal line 2: bottom-left to top-right
        pt2_a = (cx - size, cy + size)
        pt2_b = (cx + size, cy - size)

        # Draw white comic outer border first
        outer_w = thickness + border_thick * 2
        draw.line([pt1_a, pt1_b], fill=(255, 255, 255, 255), width=outer_w)
        draw.line([pt2_a, pt2_b], fill=(255, 255, 255, 255), width=outer_w)

        # Draw intense red cross on top (#EF4444)
        draw.line([pt1_a, pt1_b], fill=(239, 68, 68, 255), width=thickness)
        draw.line([pt2_a, pt2_b], fill=(239, 68, 68, 255), width=thickness)

        return Image.alpha_composite(img, overlay).convert("RGB")
