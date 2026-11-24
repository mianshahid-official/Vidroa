"""
Viral YouTube Thumbnail Prompt Builder.
Crafts style-compliant visual composition prompts with embedded headline typography
designed for direct batch generation in Gemini, Midjourney, Flux, and SDXL.
"""
import re
from typing import Optional, List, Any

STOP_WORDS = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "up", "about", "into", "over", "after", "beneath", "under", "above", "this",
    "that", "these", "those", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "can", "could", "will", "would",
    "shall", "should", "it", "its", "then", "and", "or", "but", "so", "visual",
    "words", "scene", "project", "untitled"
}


def is_valid_thumbnail_headline(text: str) -> bool:
    """
    Validates that a thumbnail headline is 2-5 punchy words and not a project folder name,
    question fragment, or filler.
    """
    if not text or len(text.strip()) < 3:
        return False

    clean = re.sub(r"[^\w\s]", " ", text).strip()
    upper = clean.upper()

    # Reject project folder names, timestamps, and untitled placeholders
    if any(bad in upper for bad in ("PROJECT 202", "PROJECT_", "UNTITLED", "DEFAULT PROJECT")):
        return False
    if re.search(r"\d{6,}", text):  # Reject timestamp digits like 20261110
        return False

    words = [w for w in clean.split() if w]
    if len(words) < 2 or len(words) > 5:
        return False

    first = words[0].upper()
    second = words[1].upper() if len(words) > 1 else ""

    if first in ("HOW", "WHY", "WHAT", "WHERE", "WHEN", "WHO", "WHICH", "DID", "DO", "DOES", "IS", "WAS", "ARE", "WERE"):
        return False
    if f"{first} {second}" in ("HOW DID", "WHY DID", "WHAT WAS", "WHERE DID", "IN THE", "ONCE UPON", "UNTITLED PROJECT"):
        return False

    return True


def derive_story_thumbnail_headline(
    headline: Optional[str] = None,
    story_text: str = "",
    scenes: Optional[List[Any]] = None,
    style_id: str = "zombie_survival"
) -> str:
    """
    Derives an authoritative, high-CTR 2-4 word uppercase headline from the story.
    Strictly never falls back to timestamped project names.
    """
    if headline and is_valid_thumbnail_headline(headline):
        clean_h = " ".join(headline.strip().split()).upper()
        return clean_h

    # Attempt extraction from scenes narration or visual ideas
    candidates_text = ""
    if scenes:
        for sc in scenes[:3]:
            narr = getattr(sc, "narration_excerpt", "") or ""
            subj = getattr(sc, "visual_subject", "") or ""
            candidates_text += f" {narr} {subj}"

    if not candidates_text and story_text:
        candidates_text = story_text[:1200]

    if candidates_text:
        raw_words = re.findall(r"[A-Za-z0-9]+", candidates_text)
        content_words = [
            w.upper() for w in raw_words
            if len(w) > 2 and w.lower() not in STOP_WORDS and not w.isdigit()
        ]
        if len(content_words) >= 3:
            return " ".join(content_words[:3])
        elif len(content_words) >= 2:
            return " ".join(content_words[:2])

    # Style-specific punchy default headlines
    sid = (style_id or "").lower()
    if "zombie" in sid:
        return "SURVIVE THE NIGHT"
    elif "whatif" in sid or "vector" in sid:
        return "WHAT HAPPENS NEXT"
    elif "century" in sid or "vintage" in sid or "bw_" in sid:
        return "THE FORGOTTEN WAR"
    elif "stickman" in sid:
        return "THE FINAL STAND"
    elif "paper" in sid:
        return "LEGEND OF TIME"
    else:
        return "THE UNTOLD STORY"


def build_viral_thumbnail_prompt(
    headline: str,
    style_id: str = "zombie_survival",
    story_context: str = "",
    era_or_setting: str = ""
) -> str:
    """
    Constructs an arresting, high-CTR YouTube thumbnail prompt that explicitly instructs
    the image generation model to render the headline text in prominent, stylized typography,
    while strictly complying with the chosen visual art style.
    """
    clean_hl = headline.strip().upper() if headline and headline.strip() else "THE UNTOLD STORY"
    sid = (style_id or "").lower()

    if "zombie" in sid:
        return (
            f'High-CTR YouTube thumbnail cover in 2D flat cartoon zombie survival illustration aesthetic. '
            f'Features monumental distressed graphic typography text rendered directly in the image reading: "{clean_hl}" '
            f'in massive high-contrast apocalyptic lettering with dark drop shadow across the top frame. '
            f'Dynamic dramatic composition: the stylized locked hero (backwards dark red cap, charcoal hoodie, white t-shirt, brown crossbody strap) '
            f'stands in a tense focal stance gripping a survival tool, facing an encroaching horde of stylized green-skinned infected survivors with hollow white eyes in an abandoned derelict shopping mall at night. '
            f'Flat cel-shaded comic book art style, clean thick solid black outlines (#1A1A1A), vivid contrast, dramatic flashlight rim lighting, deep shadows. '
            f'STRICT NEGATIVE: photorealism, realistic human skin texture, realistic eyes, live-action photography, 3D CGI plastic render, blood, gore.'
        )
    elif "whatif" in sid or "what_if" in sid or "vector" in sid:
        return (
            f'A high-CTR YouTube thumbnail visual centerpiece in minimalist What-If flat vector illustration aesthetic. '
            f'Features bold, monumental modern sans-serif typography text rendered directly in the scene reading: "{clean_hl}" '
            f'in large stylized flat typography with subtle geometric drop shadow. '
            f'Arresting high-concept minimalist composition, bold high-contrast color palette, clean vector silhouettes, dramatic perspective and visual intrigue. '
            f'STRICT NEGATIVE: photorealism, 3D CGI render, realistic human skin, complex noise, textures.'
        )
    elif "2d_stickman" in sid:
        return (
            f'A high-CTR YouTube thumbnail cover in expressive 2D cartoon stickman animation aesthetic. '
            f'Features large bold graphic typography text rendered directly in the image reading: "{clean_hl}" '
            f'in playful high-contrast block lettering with crisp drop shadow. '
            f'Dynamic composition: stylized 2D stickman hero in an intense action stance with bold clean outlines, vibrant colorful backdrop, cinematic visual storytelling. '
            f'STRICT NEGATIVE: photorealism, 3D CGI plastic render, realistic human face, textures.'
        )
    elif "stickman" in sid or "3d_red_blue" in sid:
        return (
            f'YouTube thumbnail cover in 3D stylized CGI animated stickman aesthetic. '
            f'Features large bold 3D extruded typography text rendered directly in the scene reading: "{clean_hl}" '
            f'prominently across the upper-third in stylized high-contrast lettering with dramatic rim lighting. '
            f'Dynamic epic wide composition: the bright red 3D stickman commander stands in a commanding focal hero stance, '
            f'overlooking a massive stylized 3D siege battlefield with blue stickman defenders on fortress walls and red stickman forces outside. '
            f'Stylized toy CGI render, smooth matte plastic surfaces, cinematic volumetric lighting, rich visual depth. '
            f'STRICT NEGATIVE: human face, realistic eyes, nose, mouth, human skin texture, realistic fabric, photorealism, live-action.'
        )
    elif "paper_cutout" in sid:
        return (
            f'A high-CTR YouTube thumbnail visual centerpiece in handcrafted layered paper-cutout 2D illustration aesthetic. '
            f'Features bold, prominent stylized paper typography text rendered directly in the image reading: "{clean_hl}" '
            f'in large dimensional cut-paper lettering with delicate drop shadows and visible paper texture. '
            f'Arresting multi-layered cardstock composition with distinct physical paper depth, simple expressive silhouettes, '
            f'warm parchment and muted historical color palette, soft dramatic studio lighting. '
            f'STRICT NEGATIVE: photorealism, modern 3D plastic render, glossy surfaces.'
        )
    elif "paper_quilling" in sid:
        return (
            f'A high-CTR YouTube thumbnail visual centerpiece in intricate handcrafted paper-quilling art aesthetic. '
            f'Features bold, prominent stylized typography text rendered directly in the image reading: "{clean_hl}" '
            f'crafted from coiled, folded, and shaped colored paper strips with physical dimensionality. '
            f'Intricate rolled paper centerpiece, tactile craft relief, elegant studio rim lighting, and clean decorative borders. '
            f'STRICT NEGATIVE: photorealism, digital blur, flat digital vector.'
        )
    elif "mixed_media" in sid:
        return (
            f'A high-CTR YouTube thumbnail visual centerpiece in expressive mixed media collage art aesthetic. '
            f'Features bold, prominent graphic typography text rendered directly in the image reading: "{clean_hl}" '
            f'in large high-contrast poster lettering. Dynamic layered archival documents, textured newspaper fragments, '
            f'bold acrylic brushstrokes, and striking high-impact graphic design composition. '
            f'STRICT NEGATIVE: photorealism, modern 3D plastic render.'
        )
    elif "century" in sid or "vintage" in sid or "photo" in sid or "bw_" in sid:
        era_txt = era_or_setting or "historical era"
        return (
            f'A high-CTR YouTube thumbnail visual centerpiece capturing the high stakes of {era_txt}. '
            f'Features bold, prominent monumental typography text rendered directly in the image reading: "{clean_hl}" '
            f'in large dramatic uppercase lettering with sharp edge contrast and cinematic composition. '
            f'An arresting historical focal centerpiece, extreme chiaroscuro contrast casting deep dramatic shadows, '
            f'authentic period textures, antique camera optics with sharp foreground clarity, and rich archival tones with authentic historical grain. '
            f'STRICT NEGATIVE: 3D CGI plastic render, modern neon, digital stickers.'
        )
    else:
        # High-impact universal thumbnail prompt
        return (
            f'A high-CTR YouTube thumbnail visual centerpiece. '
            f'Features bold, monumental typography text rendered directly in the image reading: "{clean_hl}" '
            f'in massive dramatic uppercase lettering with sharp specular highlights and rim lighting. '
            f'Arresting dramatic focal subject, extreme visual contrast, deep atmospheric perspective, and cinematic lighting.'
        )
