"""Generates the FH6 Skill Farm app icon from code.

Usage:
    python tools/make_icon.py                   # write candidate PNGs to tools/icon_candidates/ for review
    python tools/make_icon.py --finalize wheel   # build assets/skillfarm.ico from the "wheel" candidate

Keeping this as code (not a hand-edited image) means the icon can be tweaked
and regenerated instead of maintained as an opaque binary. Commit the new
.ico after finalizing.
"""

import argparse
import math
import pathlib

from PIL import Image, ImageDraw, ImageFilter

SIZE = 1024
ORANGE = (255, 107, 26)  # #FF6B1A — the app's accent color
BG = (18, 18, 26, 255)  # #12121A — the app's window background

OUT_DIR = pathlib.Path(__file__).parent / "icon_candidates"
ASSETS_DIR = pathlib.Path(__file__).parent.parent / "assets"


def _radial_glow(
    size: int,
    color: tuple[int, int, int],
    radius_frac: float = 0.34,
    blur_frac: float = 0.07,
    alpha: int = 130,
):
    """Soft blurred glow disc behind the main emblem — subtle, not a dominant blob."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r = size * radius_frac
    cx = cy = size / 2
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*color, alpha))
    return img.filter(ImageFilter.GaussianBlur(size * blur_frac))


def _base_canvas(transparent: bool = True) -> Image.Image:
    """Transparent (or dark-filled) background + a subtle orange glow."""
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0) if transparent else BG)
    glow = _radial_glow(SIZE, ORANGE)
    return Image.alpha_composite(img, glow)


def _draw_wheel(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float) -> None:
    """Segmented prize wheel (the in-game Wheelspin) with a pointer at top."""
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=ORANGE, width=int(r * 0.09))
    spokes = 8
    for i in range(spokes):
        angle = math.radians(360 / spokes * i)
        x2 = cx + r * math.sin(angle)
        y2 = cy - r * math.cos(angle)
        draw.line([cx, cy, x2, y2], fill=ORANGE, width=int(r * 0.06))
    hub_r = r * 0.12
    draw.ellipse([cx - hub_r, cy - hub_r, cx + hub_r, cy + hub_r], fill=ORANGE)
    # Pointer at top, like the wheel's prize indicator
    pw, ph = r * 0.16, r * 0.22
    top = cy - r - r * 0.06
    draw.polygon([(cx - pw, top - ph), (cx + pw, top - ph), (cx, top + ph * 0.3)], fill=ORANGE)


def _draw_gear(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float) -> None:
    """Mechanical gear/cog — skill tree / car mastery theme."""
    teeth = 10
    inner_r = r * 0.72
    pts = []
    for i in range(teeth * 2):
        angle = math.radians(360 / (teeth * 2) * i)
        rad = r if i % 2 == 0 else inner_r
        pts.append((cx + rad * math.sin(angle), cy - rad * math.cos(angle)))
    draw.polygon(pts, fill=ORANGE)
    hole_r = r * 0.38
    draw.ellipse([cx - hole_r, cy - hole_r, cx + hole_r, cy + hole_r], fill=BG)
    hub_r = r * 0.16
    draw.ellipse([cx - hub_r, cy - hub_r, cx + hub_r, cy + hub_r], fill=ORANGE)


def _draw_spark(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float) -> None:
    """Skill-point spark / eight-point star burst."""
    outer, inner = r, r * 0.35
    pts = []
    for i in range(8):
        angle = math.radians(360 / 8 * i)
        rad = outer if i % 2 == 0 else inner
        pts.append((cx + rad * math.sin(angle), cy - rad * math.cos(angle)))
    draw.polygon(pts, fill=ORANGE)


VARIANTS = {
    "wheel": _draw_wheel,
    "gear": _draw_gear,
    "spark": _draw_spark,
}


def make_candidate(name: str, transparent: bool = True) -> Image.Image:
    img = _base_canvas(transparent)
    draw = ImageDraw.Draw(img)
    cx = cy = SIZE / 2
    r = SIZE * 0.30
    VARIANTS[name](draw, cx, cy, r)
    return img


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate FH6 Skill Farm icon candidates / final .ico")
    parser.add_argument("--finalize", choices=list(VARIANTS), help="Build assets/skillfarm.ico from this candidate")
    args = parser.parse_args()

    if args.finalize:
        img = make_candidate(args.finalize)
        ASSETS_DIR.mkdir(exist_ok=True)
        ico_path = ASSETS_DIR / "skillfarm.ico"
        img.save(ico_path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        print(f"Wrote {ico_path}")
        return

    OUT_DIR.mkdir(exist_ok=True)
    for name in VARIANTS:
        preview = make_candidate(name).resize((256, 256), Image.LANCZOS)
        path = OUT_DIR / f"{name}.png"
        preview.save(path)
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
