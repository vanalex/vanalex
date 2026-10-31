"""Convert a portrait to ASCII art for the profile card (run once, output is committed).

Usage: uv run --with pillow scripts/make_ascii.py avatar.png > ascii.txt
"""

import sys

from PIL import Image, ImageEnhance, ImageOps

COLS, ROWS = 70, 46
CHAR_W, LINE = 5.76, 11.2  # art font metrics used in build.py (9.6px font)
# Light to dark. Background (white) becomes blank, dark features become dense characters.
RAMP = " .'`^,:;Il!i~+_-?][}{1)(|tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"


def convert(path: str) -> str:
    img = ImageOps.grayscale(Image.open(path))
    w, h = img.size
    # Character cells are about half as wide as they are tall, so crop to the art's aspect ratio.
    crop_w = int(w * 0.83)
    crop_h = min(h, int(crop_w * (ROWS * LINE) / (COLS * CHAR_W)))
    left = (w - crop_w) // 2
    img = img.crop((left, h - crop_h, left + crop_w, h))
    img = ImageOps.autocontrast(img, cutoff=2)
    img = ImageEnhance.Contrast(img).enhance(1.8)
    img = img.resize((COLS, ROWS), Image.Resampling.LANCZOS)
    lines = []
    for y in range(ROWS):
        row = ""
        for x in range(COLS):
            v = img.getpixel((x, y))
            darkness = 1 - v / 255
            row += RAMP[min(len(RAMP) - 1, int(darkness**1.4 * len(RAMP)))]
        lines.append(row.rstrip())
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.stdout.write(convert(sys.argv[1]))
