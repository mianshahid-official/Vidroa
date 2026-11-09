"""
High-CTR YouTube Thumbnail Generator for PromptBeast.
Generates viral YouTube thumbnails with punchy dual-tone text,
bold comic outlines, drop shadows, and visual focal popout.
"""

import os
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance


class ThumbnailGenerator:
    """Generates high-retention, viral YouTube thumbnails from project assets."""

    @classmethod
    def generate_thumbnail(
        cls,
        background_image_path: str,
        headline_text: str,
        output_path: str,
        character_image_path: Optional[str] = None,
        subtext: Optional[str] = None,
        width: int = 1920,
        height: int = 1080
    ) -> str:
        """
        Creates a high-impact YouTube thumbnail (16:9 1920x1080).
        """
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        # 1. Base Image
        if background_image_path and Path(background_image_path).is_file():
            base = Image.open(background_image_path).convert("RGBA")
            base = base.resize((width, height), Image.Resampling.LANCZOS)
            # Slight dark contrast boost for text readability
            enhancer = ImageEnhance.Brightness(base)
            base = enhancer.enhance(0.75)
            sat = ImageEnhance.Color(base)
            base = sat.enhance(1.2)
        else:
            base = Image.new("RGBA", (width, height), (15, 23, 42, 255))

        # 2. Radial vignette dark gradient
        vignette = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw_vig = ImageDraw.Draw(vignette)
        margin = int(width * 0.1)
        draw_vig.rectangle([0, 0, width, height], fill=(0, 0, 0, 60))
        base = Image.alpha_composite(base, vignette)

        # 3. Optional Character Image Overlay
        if character_image_path and Path(character_image_path).exists():
            try:
                char_img = Image.open(character_image_path).convert("RGBA")
                char_h = int(height * 0.90)
                char_w = int(char_img.width * (char_h / char_img.height))
                char_img = char_img.resize((char_w, char_h), Image.Resampling.LANCZOS)

                # Paste character on right or left
                pos_x = width - char_w - int(width * 0.05)
                pos_y = height - char_h
                base.paste(char_img, (pos_x, pos_y), char_img)
            except Exception:
                pass

        # 4. Text Render with Bold Comic Stroke & Drop Shadow
        draw = ImageDraw.Draw(base)
        font_size = int(height * 0.12)
        font = cls._load_font("impact.ttf", font_size)

        words = headline_text.strip().split()
        if len(words) > 4:
            line1 = " ".join(words[: len(words)//2]).upper()
            line2 = " ".join(words[len(words)//2 :]).upper()
        else:
            line1 = headline_text.upper()
            line2 = (subtext or "").upper()

        text_x = int(width * 0.08)
        text_y = int(height * 0.28)

        # Draw Line 1 (Bright Yellow #FFD700)
        cls._draw_stroked_text(draw, (text_x, text_y), line1, font, fill_color="#FFD700", stroke_color="#000000", stroke_w=12)

        # Draw Line 2 (Pure White #FFFFFF)
        if line2:
            cls._draw_stroked_text(
                draw,
                (text_x, text_y + int(font_size * 1.25)),
                line2,
                font,
                fill_color="#FFFFFF",
                stroke_color="#000000",
                stroke_w=12
            )

        # Save as RGB JPEG / PNG
        final_img = base.convert("RGB")
        final_img.save(str(out_p.resolve()), quality=95)
        return str(out_p.resolve())

    @classmethod
    def overlay_headline_on_image(
        cls,
        image_path: str,
        headline_text: str,
        output_path: Optional[str] = None,
        subtext: Optional[str] = None
    ) -> str:
        """
        Renders dependable, large, bold, high-contrast typography directly onto
        a thumbnail image using PIL/Pillow.
        Words (e.g. 'THE FINAL STORM' or 'INTO THE DEEP') appear visibly
        in high-impact typography with bold contrasting outlines and drop shadows,
        ensuring 100% legibility over any background.
        """
        in_p = Path(image_path)
        if not in_p.exists():
            raise FileNotFoundError(f"Input image not found: {image_path}")

        out_p = Path(output_path) if output_path else in_p
        out_p.parent.mkdir(parents=True, exist_ok=True)

        base = Image.open(str(in_p.resolve())).convert("RGBA")
        width, height = base.size

        # Dynamic font sizing based on image dimensions
        font_size = max(32, int(height * 0.11))
        font = cls._load_font("impact.ttf", font_size)

        draw = ImageDraw.Draw(base)

        clean_text = headline_text.strip().upper()
        words = clean_text.split()
        if len(words) > 4:
            split_idx = len(words) // 2
            line1 = " ".join(words[:split_idx])
            line2 = " ".join(words[split_idx:])
        else:
            line1 = clean_text
            line2 = subtext.strip().upper() if subtext else ""

        stroke_w = max(6, int(font_size * 0.12))

        # Position in upper third with clean padding
        pad_x = int(width * 0.07)
        pad_y = int(height * 0.18)

        # Draw semi-transparent dark backing ribbon for flawless contrast
        bbox1 = draw.textbbox((pad_x, pad_y), line1, font=font, stroke_width=stroke_w)
        ribbon_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        r_draw = ImageDraw.Draw(ribbon_layer)
        r_margin = int(font_size * 0.25)
        r_draw.rectangle(
            [pad_x - r_margin, pad_y - r_margin, bbox1[2] + r_margin, bbox1[3] + r_margin],
            fill=(0, 0, 0, 140)
        )
        if line2:
            y2 = pad_y + int(font_size * 1.25)
            bbox2 = draw.textbbox((pad_x, y2), line2, font=font, stroke_width=stroke_w)
            r_draw.rectangle(
                [pad_x - r_margin, y2 - r_margin, bbox2[2] + r_margin, bbox2[3] + r_margin],
                fill=(0, 0, 0, 140)
            )

        base = Image.alpha_composite(base, ribbon_layer)
        draw = ImageDraw.Draw(base)

        # Draw Line 1 (Vibrant Gold #FFD700)
        cls._draw_stroked_text(draw, (pad_x, pad_y), line1, font, fill_color="#FFD700", stroke_color="#000000", stroke_w=stroke_w)

        # Draw Line 2 (Pure White #FFFFFF)
        if line2:
            y2 = pad_y + int(font_size * 1.25)
            cls._draw_stroked_text(draw, (pad_x, y2), line2, font, fill_color="#FFFFFF", stroke_color="#000000", stroke_w=stroke_w)

        final_img = base.convert("RGB")
        final_img.save(str(out_p.resolve()), quality=95)
        return str(out_p.resolve())

    @classmethod
    def _draw_stroked_text(cls, draw: ImageDraw.ImageDraw, pos: Tuple[int, int], text: str, font, fill_color: str, stroke_color: str, stroke_w: int):
        x, y = pos
        # Drop shadow
        draw.text((x + 8, y + 8), text, font=font, fill="#000000")
        # Bold outline stroke
        draw.text(pos, text, font=font, fill=fill_color, stroke_width=stroke_w, stroke_fill=stroke_color)

    @classmethod
    def _load_font(cls, font_name: str, size: int):
        font_candidates = [
            font_name,
            r"C:\Windows\Fonts\impact.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
            r"C:\Windows\Fonts\arial.ttf",
        ]
        for f in font_candidates:
            try:
                return ImageFont.truetype(f, size)
            except Exception:
                continue
        return ImageFont.load_default()
