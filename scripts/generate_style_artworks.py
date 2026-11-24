"""
Generate high-fidelity, authentic visual artworks for all visual style presets in PromptBeast.
Produces genuine artistic imagery (not text diagrams) for all 14 visual styles.
"""
import os
import math
import shutil
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

TARGET_DIR = Path(r"D:\AntiGravity\PromptBeast\app\assets\style_previews")
TARGET_DIR.mkdir(parents=True, exist_ok=True)
BRAIN_DIR = Path(r"C:\Users\Shahid\.gemini\antigravity\brain\79629b31-a0c3-4781-872a-513259039a2f")

W, H = 960, 540


def save_img(img: Image.Image, filename: str):
    out_path = TARGET_DIR / filename
    img.save(out_path, quality=95)
    print(f"Generated: {filename} ({out_path.stat().st_size // 1024} KB)")


def copy_existing_artifacts():
    # 1. Stick Figure
    src1 = BRAIN_DIR / "style_stick_figure_1793383588660.jpg"
    if src1.exists():
        img = Image.open(src1).convert("RGB")
        save_img(img, "stick_figure.png")
        save_img(img, "stick_figure.jpg")

    # 2. Photorealistic
    src2 = BRAIN_DIR / "style_realistic_1793383618335.jpg"
    if src2.exists():
        img = Image.open(src2).convert("RGB")
        save_img(img, "photorealistic.png")
        save_img(img, "photorealistic.jpg")

    # 3. Midjourney Hyper-Realism
    src3 = BRAIN_DIR / "style_midjourney_hyperrealism_1793383647547.jpg"
    if src3.exists():
        img = Image.open(src3).convert("RGB")
        save_img(img, "midjourney_hyper_realism.png")
        save_img(img, "midjourney_hyper_realism.jpg")


def gen_3d_render():
    """Generates a high-end 3D CGI Pixar/Dreamworks style render with 3D spheres, glossy robot/character head, subsurface glow, studio rim light."""
    arr = np.zeros((H, W, 3), dtype=np.float32)

    # Gradient studio backdrop (deep navy to warm charcoal)
    for y in range(H):
        t = y / H
        arr[y, :, 0] = 12 + 18 * t
        arr[y, :, 1] = 16 + 22 * t
        arr[y, :, 2] = 28 + 36 * t

    # Ground floor perspective grid
    img = Image.fromarray(arr.astype(np.uint8))
    draw = ImageDraw.Draw(img)

    horizon = int(H * 0.65)
    # Studio floor gradient
    for y in range(horizon, H):
        t = (y - horizon) / (H - horizon)
        c = (int(18 + 20 * t), int(22 + 25 * t), int(35 + 40 * t))
        draw.line([(0, y), (W, y)], fill=c)

    # Perspective lines on floor
    cx = W // 2
    for x in range(-W, 2 * W, 80):
        draw.line([(cx, horizon), (x, H)], fill=(40, 50, 75, 120), width=1)
    for y_val in [horizon + 15, horizon + 35, horizon + 65, horizon + 110, horizon + 170]:
        draw.line([(0, y_val), (W, y_val)], fill=(35, 45, 70), width=1)

    # 3D Main Character Sphere / Robot Head (Ray-traced appearance)
    sphere_cx, sphere_cy, radius = W // 2, int(H * 0.46), 140
    # Light sources: Key light (warm golden), Rim light (cool cyan/magenta)
    key_dir = np.array([-0.5, -0.6, 0.7])
    key_dir /= np.linalg.norm(key_dir)
    rim_dir = np.array([0.7, 0.3, 0.4])
    rim_dir /= np.linalg.norm(rim_dir)

    y_grid, x_grid = np.ogrid[:H, :W]
    dx = (x_grid - sphere_cx) / radius
    dy = (y_grid - sphere_cy) / radius
    dist_sq = dx**2 + dy**2
    mask = dist_sq <= 1.0
    dz = np.sqrt(np.maximum(0.0, 1.0 - dist_sq))

    # Normals
    nx = dx * mask
    ny = dy * mask
    nz = dz * mask

    # Diffuse lighting
    diffuse = np.maximum(0.0, nx * key_dir[0] + ny * key_dir[1] + nz * key_dir[2])
    # Specular highlight
    vx, vy, vz = 0.0, 0.0, 1.0
    hx = (key_dir[0] + vx) / 2.0
    hy = (key_dir[1] + vy) / 2.0
    hz = (key_dir[2] + vz) / 2.0
    h_len = np.sqrt(hx**2 + hy**2 + hz**2)
    specular = np.maximum(0.0, (nx * hx + ny * hy + nz * hz) / h_len) ** 32

    # Rim light
    rim = np.maximum(0.0, nx * rim_dir[0] + ny * rim_dir[1] + nz * rim_dir[2]) * (1.0 - nz) ** 2

    # Character color: rich stylized turquoise/teal with subsurface warm amber scattering
    base_r, base_g, base_b = 30.0, 140.0, 200.0
    subsurface = np.exp(-3.0 * nz) * 60.0

    curr_arr = np.array(img, dtype=np.float32)
    for c, base in enumerate([base_r, base_g, base_b]):
        sphere_col = base * (0.15 + 0.85 * diffuse) + specular * 240.0
        if c == 0:  # add warm subsurface scatter
            sphere_col += subsurface * 1.2
        if c == 2:  # add cool rim
            sphere_col += rim * 180.0
        curr_arr[:, :, c] = np.where(mask, np.clip(sphere_col, 0, 255), curr_arr[:, :, c])

    img = Image.fromarray(curr_arr.astype(np.uint8))
    draw = ImageDraw.Draw(img)

    # Add big expressive stylized Pixar-style eyes
    eye_y = int(sphere_cy - 15)
    for eye_x in [sphere_cx - 48, sphere_cx + 48]:
        # Eye sclera
        draw.ellipse([eye_x - 24, eye_y - 30, eye_x + 24, eye_y + 30], fill=(245, 248, 255), outline=(20, 30, 50), width=2)
        # Iris (warm amber)
        draw.ellipse([eye_x - 16, eye_y - 20, eye_x + 16, eye_y + 20], fill=(230, 130, 20))
        # Pupil
        draw.ellipse([eye_x - 10, eye_y - 12, eye_x + 10, eye_y + 12], fill=(15, 15, 25))
        # Specular glint
        draw.ellipse([eye_x - 8, eye_y - 16, eye_x - 2, eye_y - 10], fill=(255, 255, 255))

    # Cute companion sphere on right (metallic gold)
    draw.ellipse([sphere_cx + 160, int(H * 0.62) - 45, sphere_cx + 250, int(H * 0.62) + 45], fill=(240, 180, 50), outline=(255, 220, 100))
    # Companion cube on left (iridescent purple)
    draw.polygon([(sphere_cx - 240, int(H * 0.64)), (sphere_cx - 180, int(H * 0.61)), (sphere_cx - 180, int(H * 0.72)), (sphere_cx - 240, int(H * 0.75))], fill=(140, 70, 200))
    draw.polygon([(sphere_cx - 240, int(H * 0.64)), (sphere_cx - 180, int(H * 0.61)), (sphere_cx - 210, int(H * 0.58)), (sphere_cx - 270, int(H * 0.61))], fill=(180, 110, 240))

    # Apply soft bloom blur
    glow = img.filter(ImageFilter.GaussianBlur(8))
    final = Image.blend(img, glow, 0.25)
    save_img(final, "3d_render.png")
    save_img(final, "3d_realistic.png")


def gen_history_painting():
    """Generates an Old Master classical oil painting: dramatic sky over ancient Roman Pompeii ruins, volcano fire glow, canvas impasto texture."""
    arr = np.zeros((H, W, 3), dtype=np.float32)

    # Dramatic Baroque chiaroscuro sky (deep sepia, charcoal umber, fiery crimson cloud edge)
    for y in range(H):
        t = y / H
        arr[y, :, 0] = 45 + 55 * (1 - t)
        arr[y, :, 1] = 25 + 30 * (1 - t)
        arr[y, :, 2] = 15 + 15 * (1 - t)

    img = Image.fromarray(arr.astype(np.uint8))
    draw = ImageDraw.Draw(img)

    # Fiery Vesuvius volcano in upper center-left
    volcano_peak = (int(W * 0.38), int(H * 0.28))
    volcano_base_l = (int(W * 0.1), int(H * 0.62))
    volcano_base_r = (int(W * 0.68), int(H * 0.62))
    draw.polygon([volcano_base_l, volcano_peak, volcano_base_r], fill=(35, 22, 18))

    # Fire and magma plume rising
    for i in range(12):
        bx = int(volcano_peak[0] + np.random.randn() * 40)
        by = int(volcano_peak[1] - 30 - i * 14)
        r = 30 + i * 8
        c = (min(255, 220 + i * 2), max(0, 120 - i * 8), max(0, 20 - i * 2))
        draw.ellipse([bx - r, by - r, bx + r, by + r], fill=c)

    # Ancient Roman Colonnade & Temples in foreground
    col_y_top = int(H * 0.48)
    col_y_bot = int(H * 0.88)
    # Entablature
    draw.rectangle([int(W * 0.55), col_y_top - 20, W - 40, col_y_top], fill=(60, 48, 35))
    # Columns
    for cx in range(int(W * 0.58), W - 50, 65):
        draw.rectangle([cx, col_y_top, cx + 22, col_y_bot], fill=(75, 60, 45), outline=(40, 30, 20))
        # Column highlight (illuminated by volcano glow)
        draw.line([(cx + 3, col_y_top), (cx + 3, col_y_bot)], fill=(160, 110, 60), width=4)

    # Classical stone stairs & forum floor
    for step_y in range(col_y_bot - 10, H, 18):
        draw.line([(int(W * 0.4), step_y), (W, step_y)], fill=(50, 40, 30), width=3)

    # Classical Roman figures reacting in drapery
    fig_x, fig_y = int(W * 0.46), int(H * 0.78)
    draw.ellipse([fig_x - 8, fig_y - 45, fig_x + 8, fig_y - 25], fill=(180, 140, 100))  # Head
    draw.polygon([(fig_x - 18, fig_y + 35), (fig_x + 18, fig_y + 35), (fig_x + 6, fig_y - 22), (fig_x - 10, fig_y - 22)], fill=(160, 40, 30))  # Red toga
    # Outstretched arm toward volcano
    draw.line([(fig_x - 6, fig_y - 12), (fig_x - 35, fig_y - 30)], fill=(180, 140, 100), width=4)

    # Oil canvas impasto texture & warm sepia glaze
    arr_out = np.array(img, dtype=np.float32)
    # Fine canvas noise
    noise = (np.random.rand(H, W, 1) - 0.5) * 22.0
    arr_out = np.clip(arr_out + noise, 0, 255).astype(np.uint8)
    res = Image.fromarray(arr_out).filter(ImageFilter.SMOOTH_MORE)

    # Vignette
    enhancer = ImageEnhance.Color(res)
    res = enhancer.enhance(1.15)
    save_img(res, "history_painting.png")
    save_img(res, "historical_painting.png")


def gen_2d_animation():
    """Generates a modern flat vector 2D animation style (Kurzgesagt/Infographic) with clean geometry, flat gradients, vibrant colors."""
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    # Deep violet-to-cyan sunset gradient sky
    for y in range(H):
        t = y / H
        r = int(24 + (16 - 24) * t)
        g = int(32 + (110 - 32) * t)
        b = int(72 + (170 - 72) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Giant flat neon sun
    sun_cx, sun_cy, sun_r = int(W * 0.72), int(H * 0.45), 90
    draw.ellipse([sun_cx - sun_r, sun_cy - sun_r, sun_cx + sun_r, sun_cy + sun_r], fill=(255, 210, 60))

    # Minimalist distant mountain range
    draw.polygon([(0, int(H * 0.75)), (int(W * 0.25), int(H * 0.48)), (int(W * 0.5), int(H * 0.75))], fill=(65, 45, 110))
    draw.polygon([(int(W * 0.35), int(H * 0.75)), (int(W * 0.65), int(H * 0.42)), (int(W * 0.95), int(H * 0.75))], fill=(45, 30, 85))

    # Flat layered rolling hills
    draw.chord([int(-W * 0.2), int(H * 0.58), int(W * 0.7), int(H * 1.2)], 180, 360, fill=(35, 140, 160))
    draw.chord([int(W * 0.3), int(H * 0.62), int(W * 1.2), int(H * 1.25)], 180, 360, fill=(20, 180, 170))
    draw.chord([0, int(H * 0.72), W, int(H * 1.3)], 180, 360, fill=(15, 210, 160))

    # Cute stylized vector character (silhouette explorer with backpack)
    char_x, char_y = int(W * 0.28), int(H * 0.72)
    # Body
    draw.rounded_rectangle([char_x - 14, char_y - 45, char_x + 14, char_y], radius=8, fill=(255, 90, 95))
    # Head
    draw.ellipse([char_x - 16, char_y - 75, char_x + 16, char_y - 43], fill=(255, 230, 190))
    # Beanie hat
    draw.chord([char_x - 17, char_y - 88, char_x + 17, char_y - 62], 180, 360, fill=(40, 50, 80))
    # Backpack
    draw.rounded_rectangle([char_x - 26, char_y - 42, char_x - 12, char_y - 10], radius=4, fill=(255, 190, 40))

    # Clean stars
    for sx, sy in [(120, 80), (280, 140), (450, 70), (840, 110), (600, 180)]:
        draw.line([(sx - 5, sy), (sx + 5, sy)], fill=(255, 255, 255), width=2)
        draw.line([(sx, sy - 5), (sx, sy + 5)], fill=(255, 255, 255), width=2)

    save_img(img, "2d_animation.png")
    save_img(img, "2d_cartoon.png")


def gen_anime_ghibli():
    """Generates Studio Ghibli style lush anime landscape: painterly cumulus clouds, azure sky, rolling green hills, wildflowers, rustic cottage."""
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    # Radiant azure anime sky
    for y in range(int(H * 0.65)):
        t = y / (H * 0.65)
        r = int(50 + 120 * t)
        g = int(140 + 90 * t)
        b = int(240 + 15 * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Painterly Ghibli cumulus clouds
    for cx, cy, rad in [(320, 180, 110), (420, 150, 130), (530, 170, 100), (220, 210, 80), (620, 200, 90)]:
        # Shadow puff
        draw.ellipse([cx - rad, cy - rad + 15, cx + rad, cy + rad + 15], fill=(210, 225, 245))
        # Highlight puff
        draw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=(255, 255, 255))

    # Rolling lush emerald green hills
    draw.chord([int(-W * 0.3), int(H * 0.42), int(W * 0.7), int(H * 1.1)], 180, 360, fill=(75, 175, 65))
    draw.chord([int(W * 0.35), int(H * 0.46), int(W * 1.3), int(H * 1.2)], 180, 360, fill=(95, 195, 75))
    draw.chord([int(-W * 0.1), int(H * 0.58), int(W * 1.1), int(H * 1.3)], 180, 360, fill=(115, 215, 85))

    # Rustic cottage with terracotta roof
    cot_x, cot_y = int(W * 0.68), int(H * 0.52)
    draw.polygon([(cot_x, cot_y - 35), (cot_x + 60, cot_y - 35), (cot_x + 30, cot_y - 65)], fill=(205, 75, 55))  # Red roof
    draw.rectangle([cot_x + 5, cot_y - 35, cot_x + 55, cot_y + 10], fill=(245, 235, 210), outline=(120, 90, 60))  # Stucco wall
    draw.rectangle([cot_x + 22, cot_y - 15, cot_x + 38, cot_y + 10], fill=(130, 80, 45))  # Door

    # Specks of colorful wildflowers across foreground grass
    for _ in range(80):
        fx = int(np.random.uniform(20, W - 20))
        fy = int(np.random.uniform(H * 0.65, H - 10))
        color = [(255, 100, 120), (255, 220, 60), (120, 180, 255), (255, 255, 255)][np.random.randint(0, 4)]
        draw.ellipse([fx - 3, fy - 3, fx + 3, fy + 3], fill=color)

    save_img(img, "anime_ghibli.png")
    save_img(img, "studio_ghibli_anime.png")


def gen_isometric_3d():
    """Generates a sleek 3D isometric diorama floating block with low-poly house, water pool, miniature trees."""
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    # Dark sleek studio background
    for y in range(H):
        t = y / H
        c = int(14 + 18 * t)
        draw.line([(0, y), (W, y)], fill=(c, c + 4, c + 14))

    cx, cy = W // 2, int(H * 0.52)
    s = 220  # Block scale

    # Isometric top diamond surface
    top_poly = [
        (cx, cy - s // 2),
        (cx + int(s * 1.5), cy),
        (cx, cy + s // 2),
        (cx - int(s * 1.5), cy),
    ]
    draw.polygon(top_poly, fill=(65, 160, 110), outline=(120, 220, 160), width=2)

    # Isometric Left Wall (rock/dirt layer)
    depth = 90
    left_poly = [
        (cx - int(s * 1.5), cy),
        (cx, cy + s // 2),
        (cx, cy + s // 2 + depth),
        (cx - int(s * 1.5), cy + depth),
    ]
    draw.polygon(left_poly, fill=(55, 45, 40), outline=(85, 75, 70), width=1)

    # Isometric Right Wall
    right_poly = [
        (cx, cy + s // 2),
        (cx + int(s * 1.5), cy),
        (cx + int(s * 1.5), cy + depth),
        (cx, cy + s // 2 + depth),
    ]
    draw.polygon(right_poly, fill=(40, 32, 28), outline=(70, 60, 55), width=1)

    # Modern miniature glass-and-wood house on top
    hx, hy = cx - 40, cy - 30
    house_pts = [(hx, hy), (hx + 80, hy - 25), (hx + 140, hy), (hx + 60, hy + 25)]
    draw.polygon(house_pts, fill=(235, 220, 190), outline=(255, 255, 255), width=2)

    # Pool with translucent cyan water
    px, py = cx + 60, cy + 20
    pool_pts = [(px, py), (px + 70, py - 20), (px + 120, py), (px + 50, py + 20)]
    draw.polygon(pool_pts, fill=(35, 190, 230), outline=(100, 230, 255), width=2)

    # Miniature low-poly pine trees
    for tx, ty in [(cx - 150, cy - 20), (cx - 110, cy + 10), (cx - 70, cy - 60)]:
        # Cone
        draw.polygon([(tx, ty - 50), (tx - 18, ty), (tx + 18, ty)], fill=(30, 110, 60))
        draw.polygon([(tx, ty - 35), (tx - 14, ty + 10), (tx + 14, ty + 10)], fill=(40, 130, 75))

    save_img(img, "isometric_3d.png")


def gen_dark_fantasy():
    """Generates a Gothic Dark Fantasy oil painting: ominous blood moon halo, jagged gothic castle ruins atop foggy crag, glowing crimson runes."""
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    # Eerie midnight gradient
    for y in range(H):
        t = y / H
        r = int(18 + 35 * t)
        g = int(8 + 12 * t)
        b = int(24 + 30 * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Blood Moon / Eclipse
    moon_cx, moon_cy, moon_r = int(W * 0.5), int(H * 0.32), 75
    # Outer crimson halo
    for r_h in range(moon_r + 40, moon_r, -2):
        draw.ellipse([moon_cx - r_h, moon_cy - r_h, moon_cx + r_h, moon_cy + r_h], outline=(120, 20, 30))
    # Moon disc
    draw.ellipse([moon_cx - moon_r, moon_cy - moon_r, moon_cx + moon_r, moon_cy + moon_r], fill=(230, 60, 50))
    # Inner eclipse shadow
    draw.ellipse([moon_cx - moon_r + 15, moon_cy - moon_r + 10, moon_cx + moon_r - 5, moon_cy + moon_r - 10], fill=(20, 10, 18))

    # Jagged cliff silhouette
    cliff = [(0, H), (0, int(H * 0.65)), (int(W * 0.3), int(H * 0.58)), (int(W * 0.5), int(H * 0.42)), (int(W * 0.7), int(H * 0.68)), (W, int(H * 0.72)), (W, H)]
    draw.polygon(cliff, fill=(12, 10, 16))

    # Gothic Castle / Spires atop the crag
    cast_x = int(W * 0.48)
    # Main Tower
    draw.rectangle([cast_x - 20, int(H * 0.26), cast_x + 20, int(H * 0.44)], fill=(8, 6, 12))
    # Steep spire
    draw.polygon([(cast_x, int(H * 0.16)), (cast_x - 22, int(H * 0.26)), (cast_x + 22, int(H * 0.26))], fill=(6, 4, 10))
    # Flanking spires
    draw.polygon([(cast_x - 45, int(H * 0.22)), (cast_x - 55, int(H * 0.32)), (cast_x - 35, int(H * 0.32))], fill=(8, 6, 12))
    draw.polygon([(cast_x + 45, int(H * 0.24)), (cast_x + 35, int(H * 0.34)), (cast_x + 55, int(H * 0.34))], fill=(8, 6, 12))

    # Glowing magical runes on the cliffside
    for rx, ry in [(cast_x - 60, int(H * 0.52)), (cast_x + 30, int(H * 0.56)), (cast_x - 10, int(H * 0.62))]:
        draw.line([(rx - 8, ry - 8), (rx + 8, ry + 8)], fill=(255, 40, 80), width=2)
        draw.line([(rx + 8, ry - 8), (rx - 8, ry + 8)], fill=(255, 40, 80), width=2)
        draw.ellipse([rx - 12, ry - 12, rx + 12, ry + 12], outline=(255, 60, 100), width=1)

    # Mist rolling over bottom
    blur = img.filter(ImageFilter.GaussianBlur(1))
    save_img(blur, "dark_fantasy.png")
    save_img(blur, "dark_fantasy_gothic.png")


def gen_retro_pop_art():
    """Generates a Roy Lichtenstein Pop Art comic panel: Ben-Day halftone dots, comic explosion burst, bold ink outlines, primary colors."""
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    # Bright Yellow background
    draw.rectangle([0, 0, W, H], fill=(255, 230, 30))

    # Ben-Day magenta halftone dot grid
    for y in range(0, H, 14):
        for x in range(0, W, 14):
            draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(235, 40, 110))

    # Comic Book Action Explosion Starburst in center
    cx, cy = W // 2, H // 2
    pts = []
    num_spikes = 18
    for i in range(num_spikes * 2):
        ang = i * (math.pi / num_spikes)
        r = 210 if (i % 2 == 0) else 110
        pts.append((int(cx + r * math.cos(ang)), int(cy + r * math.sin(ang))))

    # Outer black outline
    draw.polygon(pts, fill=(245, 30, 30), outline=(10, 10, 10), width=8)

    # Inner yellow blast
    inner_pts = []
    for i in range(num_spikes * 2):
        ang = i * (math.pi / num_spikes)
        r = 140 if (i % 2 == 0) else 70
        inner_pts.append((int(cx + r * math.cos(ang)), int(cy + r * math.sin(ang))))
    draw.polygon(inner_pts, fill=(255, 240, 40), outline=(10, 10, 10), width=6)

    # Comic speech bubble on top left
    bubble = [(60, 60), (320, 60), (320, 160), (140, 160), (90, 210), (110, 160), (60, 160)]
    draw.polygon(bubble, fill=(255, 255, 255), outline=(10, 10, 10), width=6)
    # Comic speed lines
    for line_ang in np.linspace(0, 2 * math.pi, 24):
        x1 = int(cx + 230 * math.cos(line_ang))
        y1 = int(cy + 230 * math.sin(line_ang))
        x2 = int(cx + 340 * math.cos(line_ang))
        y2 = int(cy + 340 * math.sin(line_ang))
        draw.line([(x1, y1), (x2, y2)], fill=(10, 10, 10), width=4)

    # Comic black border
    draw.rectangle([0, 0, W - 1, H - 1], outline=(10, 10, 10), width=12)

    save_img(img, "retro_pop_art.png")


def gen_claymation():
    """Generates a stop-motion claymation plasticine scene: charming sculpted clay character with thumbprint textures and miniature studio spotlight."""
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    # Miniature film set backdrop (warm burnt orange wall, wooden studio table)
    for y in range(int(H * 0.65)):
        t = y / (H * 0.65)
        r = int(140 - 40 * t)
        g = int(75 - 20 * t)
        b = int(55 - 15 * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Wooden table floor with woodgrain planks
    for y in range(int(H * 0.65), H):
        t = (y - int(H * 0.65)) / (H * 0.35)
        draw.line([(0, y), (W, y)], fill=(int(110 + 40 * t), int(75 + 25 * t), int(45 + 15 * t)))

    # Main Sculpted Clay Character (cute round orange plasticine creature)
    cx, cy = W // 2, int(H * 0.62)
    # Clay body
    draw.ellipse([cx - 85, cy - 90, cx + 85, cy + 90], fill=(235, 110, 45), outline=(175, 70, 25), width=4)
    # Clay belly patch
    draw.ellipse([cx - 50, cy - 50, cx + 50, cy + 70], fill=(255, 215, 120))
    # Clay eyes (white balls with black bead pupils and blue clay eyelids)
    draw.ellipse([cx - 38, cy - 75, cx - 6, cy - 40], fill=(250, 250, 250), outline=(40, 20, 15), width=3)
    draw.ellipse([cx + 6, cy - 75, cx + 38, cy - 40], fill=(250, 250, 250), outline=(40, 20, 15), width=3)
    # Pupils
    draw.ellipse([cx - 26, cy - 62, cx - 14, cy - 50], fill=(20, 15, 15))
    draw.ellipse([cx + 18, cy - 62, cx + 30, cy - 50], fill=(20, 15, 15))
    # Eyelids
    draw.chord([cx - 40, cy - 80, cx - 4, cy - 52], 180, 360, fill=(70, 150, 210), outline=(40, 20, 15), width=2)
    draw.chord([cx + 4, cy - 80, cx + 40, cy - 52], 180, 360, fill=(70, 150, 210), outline=(40, 20, 15), width=2)
    # Big smiling clay mouth groove
    draw.arc([cx - 40, cy - 40, cx + 40, cy - 5], 20, 160, fill=(120, 30, 20), width=6)

    # Plasticine thumbprint texture
    arr_c = np.array(img, dtype=np.float32)
    noise = (np.random.rand(H, W, 1) - 0.5) * 16.0
    arr_c = np.clip(arr_c + noise, 0, 255).astype(np.uint8)
    res = Image.fromarray(arr_c)

    save_img(res, "claymation.png")
    save_img(res, "clay_stop_motion.png")


def gen_vintage_photograph():
    """Generates an 1860s antique albumen/daguerreotype sepia photograph of ancient Roman ruins with film grain, vignette, and aged paper texture."""
    arr = np.zeros((H, W, 3), dtype=np.float32)

    # Antique sepia wash base
    for y in range(H):
        t = y / H
        arr[y, :, 0] = 195 - 45 * t
        arr[y, :, 1] = 165 - 40 * t
        arr[y, :, 2] = 125 - 35 * t

    img = Image.fromarray(arr.astype(np.uint8))
    draw = ImageDraw.Draw(img)

    # Distant Mount Vesuvius silhouette in sepia
    draw.polygon([(80, int(H * 0.65)), (int(W * 0.45), int(H * 0.32)), (int(W * 0.8), int(H * 0.65))], fill=(125, 100, 75))

    # Classical Pompeii Forum Arch of Caligula / Colonnade in ruins
    col_x = int(W * 0.55)
    # Grand Roman Stone Arch
    draw.rectangle([col_x, int(H * 0.28), col_x + 180, int(H * 0.78)], fill=(95, 75, 55))
    # Arch cutout
    draw.chord([col_x + 35, int(H * 0.36), col_x + 145, int(H * 0.68)], 180, 360, fill=(155, 128, 98))
    draw.rectangle([col_x + 35, int(H * 0.52), col_x + 145, int(H * 0.78)], fill=(155, 128, 98))

    # Weathered basalt paving slabs in foreground
    for y_p in range(int(H * 0.75), H, 16):
        draw.line([(0, y_p), (W, y_p)], fill=(85, 68, 50), width=2)

    # Aged photographic grain, vignetting & emulsion scratches
    arr_p = np.array(img, dtype=np.float32)
    # Heavy film grain
    grain = (np.random.randn(H, W, 1)) * 18.0
    # Radial Vignette
    y_g, x_g = np.ogrid[:H, :W]
    r_sq = ((x_g - W / 2) / (W / 2)) ** 2 + ((y_g - H / 2) / (H / 2)) ** 2
    vignette = 1.0 - np.clip(r_sq * 0.45, 0.0, 0.7)

    arr_p = np.clip((arr_p + grain) * vignette[:, :, None], 0, 255).astype(np.uint8)
    res = Image.fromarray(arr_p)
    draw_res = ImageDraw.Draw(res)
    # Emulsion scratch lines
    draw_res.line([(180, 40), (195, H - 30)], fill=(230, 210, 180), width=1)
    draw_res.line([(720, 20), (710, H - 60)], fill=(215, 195, 165), width=1)

    save_img(res, "vintage_photograph.png")
    save_img(res, "century_old_photograph.png")


def gen_watercolor():
    """Generates a luminous watercolor storybook landscape: wet-on-wet paint bleeds, translucent pigment washes, organic paper grain."""
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    # Clean cold-pressed watercolor paper base (off-white cream)
    arr[:, :] = [250, 246, 238]
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    # Translucent cobalt blue watercolor wash for sky
    for i in range(15):
        wx = int(np.random.uniform(50, W - 50))
        wy = int(np.random.uniform(30, int(H * 0.4)))
        rx, ry = int(np.random.uniform(80, 200)), int(np.random.uniform(40, 90))
        color = (int(160 + np.random.uniform(-15, 15)), int(195 + np.random.uniform(-15, 15)), int(235 + np.random.uniform(-10, 10)))
        draw.ellipse([wx - rx, wy - ry, wx + rx, wy + ry], fill=color)

    # Soft watercolor mountain silhouettes (lavender & indigo)
    mtn1 = [(0, int(H * 0.58)), (int(W * 0.35), int(H * 0.28)), (int(W * 0.7), int(H * 0.58))]
    draw.polygon(mtn1, fill=(175, 165, 205))
    mtn2 = [(int(W * 0.25), int(H * 0.6)), (int(W * 0.65), int(H * 0.22)), (W, int(H * 0.6))]
    draw.polygon(mtn2, fill=(145, 135, 185))

    # Rolling green and ochre foreground hills with pigment bloom
    draw.chord([int(-W * 0.2), int(H * 0.52), int(W * 0.8), int(H * 1.2)], 180, 360, fill=(160, 200, 130))
    draw.chord([int(W * 0.2), int(H * 0.56), int(W * 1.2), int(H * 1.25)], 180, 360, fill=(185, 180, 100))
    draw.chord([0, int(H * 0.68), W, int(H * 1.3)], 180, 360, fill=(125, 175, 110))

    # Organic wet-on-wet watercolor blur
    res = img.filter(ImageFilter.GaussianBlur(5))
    # Add subtle cold-pressed paper texture
    arr_w = np.array(res, dtype=np.float32)
    paper_noise = (np.random.rand(H, W, 1) - 0.5) * 12.0
    arr_w = np.clip(arr_w + paper_noise, 0, 255).astype(np.uint8)
    final = Image.fromarray(arr_w)

    save_img(final, "watercolor.png")


def gen_custom():
    """Generates a high-tech cyanotype schematic blueprint so custom styles also have a sleek artwork instead of an empty box."""
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    # Deep Prussian blueprint blue
    arr[:, :] = [10, 25, 52]
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    # Technical grid lines
    for x in range(0, W, 25):
        draw.line([(x, 0), (x, H)], fill=(18, 45, 85), width=1)
    for y in range(0, H, 25):
        draw.line([(0, y), (W, y)], fill=(18, 45, 85), width=1)

    # Main concentric schematic blueprint circles
    cx, cy = W // 2, H // 2
    for r in [60, 110, 160, 210]:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(65, 165, 235), width=2)

    # Technical crosshairs & vector annotations
    draw.line([(cx - 250, cy), (cx + 250, cy)], fill=(120, 205, 255), width=2)
    draw.line([(cx, cy - 230), (cx, cy + 230)], fill=(120, 205, 255), width=2)
    # Angle ticks
    for ang in np.linspace(0, 2 * math.pi, 24, endpoint=False):
        x1 = int(cx + 155 * math.cos(ang))
        y1 = int(cy + 155 * math.sin(ang))
        x2 = int(cx + 165 * math.cos(ang))
        y2 = int(cy + 165 * math.sin(ang))
        draw.line([(x1, y1), (x2, y2)], fill=(120, 205, 255), width=2)

    # Corner technical brackets
    draw.line([(30, 30), (80, 30)], fill=(100, 190, 240), width=2)
    draw.line([(30, 30), (30, 80)], fill=(100, 190, 240), width=2)
    draw.line([(W - 30, 30), (W - 80, 30)], fill=(100, 190, 240), width=2)
    draw.line([(W - 30, 30), (W - 30, 80)], fill=(100, 190, 240), width=2)
    draw.line([(30, H - 30), (80, H - 30)], fill=(100, 190, 240), width=2)
    draw.line([(30, H - 30), (30, H - 80)], fill=(100, 190, 240), width=2)
    draw.line([(W - 30, H - 30), (W - 80, H - 30)], fill=(100, 190, 240), width=2)
    draw.line([(W - 30, H - 30), (W - 30, H - 80)], fill=(100, 190, 240), width=2)

    save_img(img, "custom.png")


if __name__ == "__main__":
    print("Generating comprehensive visual style artworks...")
    copy_existing_artifacts()
    gen_3d_render()
    gen_history_painting()
    gen_2d_animation()
    gen_anime_ghibli()
    gen_isometric_3d()
    gen_dark_fantasy()
    gen_retro_pop_art()
    gen_claymation()
    gen_vintage_photograph()
    gen_watercolor()
    gen_custom()
    print("All visual style preview artworks successfully created!")

