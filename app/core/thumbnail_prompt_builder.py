"""
Viral YouTube Thumbnail Prompt Builder.
Crafts style-compliant visual composition prompts with embedded headline typography
designed for direct batch generation in Gemini, Midjourney, Flux, and SDXL.
"""
from typing import Optional


def build_viral_thumbnail_prompt(
    headline: str,
    style_id: str = "3d_red_blue_stickman",
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

    if "stickman" in sid or "3d_red_blue" in sid:
        setting_desc = story_context.strip() if story_context and story_context.strip() else (era_or_setting.strip() if era_or_setting and era_or_setting.strip() else "stylized environment")
        return (
            f'YouTube thumbnail cover in 3D stylized CGI animated stickman aesthetic. '
            f'Features large bold 3D extruded typography text rendered directly in the scene reading: "{clean_hl}" '
            f"prominently across the upper-third in stylized high-contrast lettering with dramatic rim lighting. "
            f"Dynamic epic wide composition: a bright red 3D stickman focal figure stands in an intense dynamic stance "
            f"within a stylized 3D {setting_desc} with supporting blue 3D stickman figures in the midground. "
            f"Stylized toy CGI render, smooth matte plastic surfaces, cinematic volumetric lighting, rich visual depth. "
            f"STRICT NEGATIVE: human face, realistic eyes, nose, mouth, human skin texture, realistic fabric, photorealism, live-action."
        )
    elif "paper_cutout" in sid:
        return (
            f"A high-CTR YouTube thumbnail visual centerpiece in handcrafted layered paper-cutout 2D illustration aesthetic. "
            f'Features bold, prominent stylized paper typography text rendered directly in the image reading: "{clean_hl}" '
            f"in large dimensional cut-paper lettering with delicate drop shadows and visible paper texture. "
            f"Arresting multi-layered cardstock composition with distinct physical paper depth, simple expressive silhouettes, "
            f"warm parchment and muted complementary color palette, soft dramatic studio lighting. "
            f"STRICT NEGATIVE: photorealism, modern 3D plastic render, glossy surfaces."
        )
    elif "paper_quilling" in sid:
        return (
            f"A high-CTR YouTube thumbnail visual centerpiece in intricate handcrafted paper-quilling art aesthetic. "
            f'Features bold, prominent stylized typography text rendered directly in the image reading: "{clean_hl}" '
            f"crafted from coiled, folded, and shaped colored paper strips with physical dimensionality. "
            f"Intricate rolled paper centerpiece, tactile craft relief, elegant studio rim lighting, and clean decorative borders. "
            f"STRICT NEGATIVE: photorealism, digital blur, flat digital vector."
        )
    elif "mixed_media" in sid:
        return (
            f"A high-CTR YouTube thumbnail visual centerpiece in expressive mixed media collage art aesthetic. "
            f'Features bold, prominent graphic typography text rendered directly in the image reading: "{clean_hl}" '
            f"in large high-contrast poster lettering. Dynamic layered archival documents, textured newspaper fragments, "
            f"bold acrylic brushstrokes, and striking high-impact graphic design composition."
        )
    elif "century" in sid or "vintage" in sid or "photo" in sid or "bw_" in sid:
        era_txt = era_or_setting or "the story's setting"
        return (
            f"A high-CTR YouTube thumbnail visual centerpiece capturing the high stakes of {era_txt}. "
            f'Features bold, prominent monumental typography text rendered directly in the image reading: "{clean_hl}" '
            f"in large dramatic uppercase lettering with sharp edge contrast and cinematic composition. "
            f"An arresting focal centerpiece, extreme chiaroscuro contrast casting deep dramatic shadows, "
            f"authentic setting textures, antique camera optics with sharp foreground clarity, and rich archival tones with authentic grain."
        )
    else:
        # High-impact universal thumbnail prompt
        return (
            f"A high-CTR YouTube thumbnail visual centerpiece. "
            f'Features bold, monumental typography text rendered directly in the image reading: "{clean_hl}" '
            f"in massive dramatic uppercase lettering with sharp specular highlights and rim lighting. "
            f"Arresting dramatic focal subject, extreme visual contrast, deep atmospheric perspective, and cinematic lighting."
        )

