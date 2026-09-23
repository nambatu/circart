#!/usr/bin/env python3
"""
Generate the CIRCArt app icons.

    pip install pillow
    python make_icons.py

Writes www/icons/{icon-192,icon-512,icon-maskable-512}.png — the
wordmark stacked, in the site's cream/black/wine palette.

The maskable variant keeps everything inside the central 80% circle,
because Android crops icons to whatever shape the launcher uses and
anything outside that zone can be cut off.

The bundled font is DejaVu Serif Bold. To match the site exactly,
drop PlayfairDisplay-Bold.ttf beside this script and it is picked up
automatically.
"""

import os
from PIL import Image, ImageDraw, ImageFont

BG    = (252, 251, 249)     # --bg-color
INK   = (0, 0, 0)           # "CIRC"
WINE  = (114, 47, 55)       # "Art"  (--wine-red)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "icons")

FONT_CANDIDATES = [
    os.path.join(HERE, "PlayfairDisplay-Bold.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
    "C:\\Windows\\Fonts\\georgiab.ttf",
]


def pick_font_path():
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    raise SystemExit("No serif font found. Put PlayfairDisplay-Bold.ttf next to this script.")


FONT_PATH = pick_font_path()


def fit_font(text, target_px):
    """Largest size whose rendered width fits target_px."""
    size = 10
    while size < 800:
        f = ImageFont.truetype(FONT_PATH, size + 4)
        if f.getbbox(text)[2] - f.getbbox(text)[0] > target_px:
            break
        size += 4
    return ImageFont.truetype(FONT_PATH, size)


def draw_icon(px, safe_ratio=0.92):
    """safe_ratio 0.92 = edge to edge; 0.62 keeps clear of a maskable crop."""
    img = Image.new("RGB", (px, px), BG)
    d = ImageDraw.Draw(img)

    content_w = px * safe_ratio
    top, bottom = "CIRC", "Art"

    f_top = fit_font(top, content_w)
    f_bot = fit_font(bottom, content_w * 0.72)

    def size_of(txt, font):
        b = d.textbbox((0, 0), txt, font=font)
        return b[2] - b[0], b[3] - b[1], b[0], b[1]

    tw, th, tox, toy = size_of(top, f_top)
    bw, bh, box, boy = size_of(bottom, f_bot)

    gap = px * 0.02
    block_h = th + gap + bh
    y = (px - block_h) / 2

    d.text(((px - tw) / 2 - tox, y - toy), top, font=f_top, fill=INK)
    d.text(((px - bw) / 2 - box, y + th + gap - boy), bottom, font=f_bot, fill=WINE)

    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    jobs = [
        ("icon-192.png", 192, 0.92),
        ("icon-512.png", 512, 0.92),
        ("icon-maskable-512.png", 512, 0.62),   # inside the safe circle
    ]
    for name, px, ratio in jobs:
        img = draw_icon(px, ratio)
        path = os.path.join(OUT, name)
        img.save(path, "PNG", optimize=True)
        print(f"  + {name}  ({px}x{px}, {os.path.getsize(path)} bytes)")

    print(f"\nFont used: {FONT_PATH}")


if __name__ == "__main__":
    main()
