"""Standalone OCR/screenshot inspector — run outside the main farm app to see
exactly what a WinRT OCR pass reads off the FH6 window (or any screen
region), including each recognized word's bounding box. Built to prototype
the Car Collection position auto-detect idea (see
docs/car-position-autodetect-plan.md) without needing to run the actual farm.

Usage:
    python tools/ocr_debug.py                        # one-shot: full FH6 window
    python tools/ocr_debug.py --watch                 # repeat every --interval seconds until Ctrl+C
    python tools/ocr_debug.py --region 0,0.8,1,0.2     # crop as window-relative fractions left,top,width,height
                                                        # (0,0.8,1,0.2 = bottom 20%, matches
                                                        # vision._read_car_screen_buttons's crop)
    python tools/ocr_debug.py --fullscreen             # capture the whole desktop instead of the FH6 window
    python tools/ocr_debug.py --watch --interval 2

Every capture is saved to %APPDATA%\\FH6SkillFarm\\ocr_debug\\:
    NN_raw.png          the plain screenshot, at screen resolution
    NN_annotated.png    the 2x-upscaled image WinRT OCR actually reads, with
                        every recognized word boxed + numbered (orange) so
                        the console output ("word 3: ...") lines up with the
                        picture, plus FH6's lime-green selection highlight
                        boxed in blue if one was found
and prints each recognized line's text plus its words' bounding boxes, and
whichever word(s) sit inside the detected highlight box (if any) — this is
testing whether color-based highlight detection can tell us WHICH cell is
currently selected, something OCR text-position alone can't answer (needed
for the car-position auto-detect idea's "where did the manufacturer jump
land" step — see docs/car-position-autodetect-plan.md).

The actual perception code (OCR-with-boxes, highlight detection) lives in
farm_core/car_collection_finder.py, shared with tools/car_collection_finder.py
(the automated version built on top of this same detection).
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

import pyautogui
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for farm_core/farm_settings imports

import farm_settings  # noqa: E402
from farm_core.car_collection_finder import find_highlight_box, ocr_with_boxes, words_near_box  # noqa: E402
from farm_core.vision import _get_fh6_window_region, _winrt_available  # noqa: E402


def _parse_region(spec: str) -> tuple[float, float, float, float]:
    parts = [float(p) for p in spec.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("--region needs 4 comma-separated fractions: left,top,width,height")
    return tuple(parts)


def _capture(args: argparse.Namespace) -> Image.Image:
    if args.fullscreen:
        left, top, width, height = 0, 0, *pyautogui.size()
    else:
        win = _get_fh6_window_region()
        if win is None:
            print("[WARN] FH6 window not found — falling back to full screen")
            left, top, width, height = 0, 0, *pyautogui.size()
        else:
            left, top, width, height = win

    if args.region:
        frac_left, frac_top, frac_width, frac_height = args.region
        left, top = left + int(width * frac_left), top + int(height * frac_top)
        width, height = int(width * frac_width), int(height * frac_height)

    return pyautogui.screenshot(region=(left, top, width, height))


def _run_once(args: argparse.Namespace, out_dir: Path, index: int) -> None:
    img = _capture(args)
    raw_path = out_dir / f"{index:02d}_raw.png"
    img.save(raw_path)

    if not _winrt_available():
        print(f"[{index:02d}] [WARN] WinRT OCR unavailable on this machine — screenshot saved, no text read")
        return

    lines, upscaled = asyncio.run(ocr_with_boxes(img))
    print(f"\n=== Capture {index:02d} — {len(lines)} line(s) ===")

    draw = ImageDraw.Draw(upscaled) if upscaled is not None else None
    word_i = 0
    for line in lines:
        print(f"  LINE: {line['text']!r}")
        for word in line["words"]:
            x, y, w, h = word["rect"]
            print(f"    word {word_i}: {word['text']!r}  box=({x:.0f},{y:.0f},{w:.0f},{h:.0f})")
            if draw is not None:
                draw.rectangle([x, y, x + w, y + h], outline=(255, 60, 20), width=2)
                draw.text((x, max(0, y - 14)), str(word_i), fill=(255, 60, 20))
            word_i += 1

    highlight = find_highlight_box(upscaled) if upscaled is not None else None
    if highlight is not None:
        hx, hy, hw, hh = highlight
        near_text = words_near_box(lines, highlight)
        print(f"  HIGHLIGHT box=({hx},{hy},{hw},{hh})  nearby text: {near_text}")
        if draw is not None:
            draw.rectangle([hx, hy, hx + hw, hy + hh], outline=(40, 120, 255), width=3)
    else:
        print("  HIGHLIGHT: none detected")

    if upscaled is not None:
        annotated_path = out_dir / f"{index:02d}_annotated.png"
        upscaled.save(annotated_path)
        print(f"  saved: {raw_path.name}, {annotated_path.name}")
    else:
        print(f"  saved: {raw_path.name} (OCR returned nothing to annotate)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--watch", action="store_true", help="repeat capture+OCR every --interval seconds until Ctrl+C")
    parser.add_argument(
        "--interval", type=float, default=1.5, help="seconds between captures with --watch (default 1.5)"
    )
    parser.add_argument("--fullscreen", action="store_true", help="capture the whole desktop instead of the FH6 window")
    parser.add_argument(
        "--region",
        type=_parse_region,
        default=None,
        help="crop as window-relative fractions 'left,top,width,height', e.g. '0,0.8,1,0.2' for the bottom 20%%",
    )
    parser.add_argument(
        "--countdown",
        type=float,
        default=5.0,
        help="seconds to wait before the first capture, so you can alt-tab into FH6 first (default 5, 0 to disable)",
    )
    args = parser.parse_args()

    out_dir = farm_settings.APP_DATA_DIR / "ocr_debug"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Saving captures to {out_dir}")

    if args.countdown > 0:
        print(f"Switching to FH6 in {args.countdown:.0f} seconds — alt-tab now if you haven't already...")
        time.sleep(args.countdown)

    index = 0
    try:
        while True:
            _run_once(args, out_dir, index)
            index += 1
            if not args.watch:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
