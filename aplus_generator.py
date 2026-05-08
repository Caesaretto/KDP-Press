#!/usr/bin/env python3
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 970, 600
BG = "#FFFFFF"
PLACEHOLDER_BG = "#E8E8E8"
PLACEHOLDER_TEXT_COLOR = "#AAAAAA"
DARK = "#1A1A2E"
LIGHT_TEXT = "#FFFFFF"
BODY_TEXT = "#444444"

LAYOUTS = ["hero", "feature_3col", "comparison", "lifestyle", "closing"]


def _find_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _find_font_regular(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _draw_placeholder(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], label: str = "IMAGE PLACEHOLDER") -> None:
    x0, y0, x1, y1 = rect
    draw.rectangle(rect, fill=PLACEHOLDER_BG)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    font = _find_font_regular(11)
    draw.text((cx, cy), label, fill=PLACEHOLDER_TEXT_COLOR, font=font, anchor="mm")


def _draw_header_band(draw: ImageDraw.ImageDraw, accent: str, title: str, subtitle: str) -> None:
    draw.rectangle([(0, 0), (W, 70)], fill=accent)
    font_title = _find_font(24)
    font_sub = _find_font_regular(13)
    draw.text((30, 35), title.upper(), fill=LIGHT_TEXT, font=font_title, anchor="lm")
    draw.text((W - 30, 35), subtitle, fill=LIGHT_TEXT, font=font_sub, anchor="rm")


def _wrap_text(text: str, font, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_bullets(draw: ImageDraw.ImageDraw, bullets: list[str], x: int, y: int, max_width: int, accent: str) -> int:
    font = _find_font_regular(14)
    line_h = 22
    for bullet in bullets:
        draw.ellipse([(x, y + 5), (x + 8, y + 13)], fill=accent)
        lines = _wrap_text(bullet, font, max_width - 20, draw)
        for line in lines:
            draw.text((x + 16, y), line, fill=BODY_TEXT, font=font, anchor="lt")
            y += line_h
        y += 4
    return y


def _layout_hero(img: Image.Image, title: str, subtitle: str, bullets: list[str], accent: str) -> None:
    draw = ImageDraw.Draw(img)
    _draw_header_band(draw, accent, title, subtitle)

    _draw_placeholder(draw, (30, 90, 420, 570))

    draw.rectangle([(450, 90), (W - 30, 570)], fill="#F9F9F9", outline="#EEEEEE")

    font_h = _find_font(28)
    font_sub = _find_font_regular(15)

    lines = _wrap_text(title, font_h, 470, draw)
    y = 120
    for line in lines:
        draw.text((460, y), line, fill=DARK, font=font_h, anchor="lt")
        y += 36

    y += 8
    sub_lines = _wrap_text(subtitle, font_sub, 470, draw)
    for line in sub_lines:
        draw.text((460, y), line, fill=BODY_TEXT, font=font_sub, anchor="lt")
        y += 22

    draw.line([(460, y + 10), (920, y + 10)], fill=accent, width=2)
    y += 28

    _draw_bullets(draw, bullets[:4], 460, y, 460, accent)


def _layout_feature_3col(img: Image.Image, title: str, subtitle: str, bullets: list[str], accent: str) -> None:
    draw = ImageDraw.Draw(img)
    _draw_header_band(draw, accent, title, subtitle)

    font_h = _find_font(20)
    font_body = _find_font_regular(13)

    col_w = (W - 60) // 3
    col_labels = ["FEATURE 1", "FEATURE 2", "FEATURE 3"]

    for i in range(3):
        cx = 30 + i * (col_w + 10)
        _draw_placeholder(draw, (cx, 90, cx + col_w, 270))
        draw.rectangle([(cx, 275), (cx + col_w, 570)], fill="#F9F9F9", outline="#EEEEEE")

        label = bullets[i] if i < len(bullets) else col_labels[i]
        draw.text((cx + col_w // 2, 295), col_labels[i], fill=accent, font=font_h, anchor="mt")

        body = label if i >= len(bullets) else label
        b_lines = _wrap_text(body, font_body, col_w - 20, draw)
        y = 330
        for line in b_lines:
            draw.text((cx + col_w // 2, y), line, fill=BODY_TEXT, font=font_body, anchor="mt")
            y += 20


def _layout_comparison(img: Image.Image, title: str, subtitle: str, bullets: list[str], accent: str) -> None:
    draw = ImageDraw.Draw(img)
    _draw_header_band(draw, accent, title, subtitle)

    font_h = _find_font(18)
    font_body = _find_font_regular(14)

    mid = W // 2

    draw.rectangle([(0, 70), (mid - 2, H)], fill="#FFF5F5")
    draw.rectangle([(mid + 2, 70), (W, H)], fill="#F5FFF5")

    draw.line([(mid, 70), (mid, H)], fill="#CCCCCC", width=2)

    draw.text((mid // 2, 95), "BEFORE", fill="#CC4444", font=font_h, anchor="mt")
    draw.text((mid + mid // 2, 95), "AFTER", fill="#44AA44", font=font_h, anchor="mt")

    _draw_placeholder(draw, (20, 120, mid - 20, 330))
    _draw_placeholder(draw, (mid + 20, 120, W - 20, 330))

    y = 345
    before_bullets = [f"Without: {b}" for b in bullets[:3]]
    after_bullets = [f"With: {b}" for b in bullets[:3]]

    _draw_bullets(draw, before_bullets, 20, y, mid - 40, "#CC4444")
    _draw_bullets(draw, after_bullets, mid + 20, y, mid - 40, "#44AA44")


def _layout_lifestyle(img: Image.Image, title: str, subtitle: str, bullets: list[str], accent: str) -> None:
    draw = ImageDraw.Draw(img)
    _draw_header_band(draw, accent, title, subtitle)

    _draw_placeholder(draw, (0, 70, W, 380))

    draw.rectangle([(0, 380), (W, H)], fill=DARK)

    font_h = _find_font(22)
    font_body = _find_font_regular(14)

    draw.text((W // 2, 405), title.upper(), fill=LIGHT_TEXT, font=font_h, anchor="mt")

    y = 445
    col_w = (W - 60) // min(len(bullets), 4)
    for i, b in enumerate(bullets[:4]):
        cx = 30 + i * (col_w + 10) + col_w // 2
        draw.ellipse([(cx - 6, y - 6), (cx + 6, y + 6)], fill=accent)
        b_lines = _wrap_text(b, font_body, col_w - 10, draw)
        by = y + 18
        for line in b_lines:
            draw.text((cx, by), line, fill=LIGHT_TEXT, font=font_body, anchor="mt")
            by += 18


def _layout_closing(img: Image.Image, title: str, subtitle: str, bullets: list[str], accent: str) -> None:
    draw = ImageDraw.Draw(img)

    draw.rectangle([(0, 0), (W, H)], fill=DARK)

    draw.rectangle([(0, 0), (W, 8)], fill=accent)
    draw.rectangle([(0, H - 8), (W, H)], fill=accent)

    font_big = _find_font(36)
    font_sub = _find_font_regular(16)
    font_body = _find_font_regular(14)

    draw.text((W // 2, 80), title.upper(), fill=LIGHT_TEXT, font=font_big, anchor="mt")

    sub_lines = _wrap_text(subtitle, font_sub, W - 200, draw)
    y = 140
    for line in sub_lines:
        draw.text((W // 2, y), line, fill=accent, font=font_sub, anchor="mt")
        y += 26

    draw.line([(W // 2 - 150, y + 10), (W // 2 + 150, y + 10)], fill=accent, width=1)
    y += 30

    col_w = (W - 80) // 2
    left_bullets = bullets[:3]
    right_bullets = bullets[3:6]

    _draw_bullets(draw, left_bullets, 40, y, col_w, accent)
    _draw_bullets(draw, right_bullets, W // 2 + 20, y, col_w, accent)

    _draw_placeholder(draw, (W // 2 - 100, H - 120, W // 2 + 100, H - 20))


_LAYOUT_FUNCS = {
    "hero": _layout_hero,
    "feature_3col": _layout_feature_3col,
    "comparison": _layout_comparison,
    "lifestyle": _layout_lifestyle,
    "closing": _layout_closing,
}


def generate_aplus_set(
    book_title: str,
    subtitle: str,
    bullets: list[str],
    accent_color: str = "#E94560",
    output_dir: str = "output/aplus",
) -> list[str]:
    if not book_title or not subtitle:
        raise ValueError("book_title and subtitle are required")
    if not isinstance(bullets, list) or len(bullets) == 0:
        raise ValueError("bullets must be a non-empty list")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    generated = []
    for idx, layout_name in enumerate(LAYOUTS, start=1):
        img = Image.new("RGB", (W, H), BG)
        img.info["dpi"] = (72, 72)

        fn = _LAYOUT_FUNCS[layout_name]
        fn(img, book_title, subtitle, bullets, accent_color)

        filename = f"{idx:02d}_{layout_name}.png"
        filepath = out / filename
        img.save(str(filepath), "PNG", dpi=(72, 72))
        generated.append(str(filepath))

    return generated


if __name__ == "__main__":
    paths = generate_aplus_set(
        book_title="Zodiaco Esaurito",
        subtitle="Il libro da colorare per chi ha già dato",
        bullets=[
            "12 segni zodiacali kawaii da colorare",
            "Perfetto per adulti che amano l'astrologia",
            "Illustrazioni originali con umorismo burnout",
            "Carta di qualità, formato 8.5x8.5 pollici",
            "Regalo ideale per amici esauriti",
            "By The Daily Burnout Press",
        ],
        accent_color="#E94560",
        output_dir="output/aplus",
    )
    for p in paths:
        print(p)
