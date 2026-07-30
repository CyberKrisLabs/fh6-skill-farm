"""Automated 9x Multiplier Car — Filter finder: locates and checks the
Performance Class and/or Car Type checkboxes in My Cars' Filter list (Y from
My Cars), the same idea as farm_core/car_collection_finder.py but for a
different screen with different mechanics. See
docs/car-position-autodetect-plan.md for the Car Collection design this
builds on, and the conversation history around this module's creation for
why it needed a genuinely different technique for half of it.

PRECONDITION (the caller's job, not this module's): My Cars must already be
open in-game, and FH6 must have focus, before calling find_multiplier_filter().

Two different techniques for two different problems on the SAME screen:

- **Performance Class** (D, C, B, A, S1, S2, R, X): WinRT OCR cannot read
  these at all — confirmed by direct testing (a live capture of a crisp,
  isolated "D" on a plain white background still returns nothing; this is
  not an image-quality problem, it's the OCR engine treating an isolated
  single/double-character string as noise rather than text). Found via
  TEMPLATE MATCHING instead (cv2.matchTemplate, multi-scale, against PNGs
  cropped from a real screenshot — see assets/perf_class_templates/).
- **Car Type** (e.g. "GT Cars", "Retro Rally"): normal words, OCR reads
  these perfectly — found the same way car_collection_finder.py finds
  Manufacturers: burst-scan + OCR substring search.

Both need to know how many keypresses separate the current cursor position
from the target row — including the game's own "hop over section headers"
behavior (a header like "Performance Class" occupies a visual row but is
never a landable cursor position; Up/Down skips it in a single press). See
_press_delta_between() for how that's computed directly from OCR-detected
header positions, without needing to enumerate every row.

Every real key press goes through farm_core.keys.mp() — the same safety
every other automation path in this app uses.
"""

import asyncio
import dataclasses
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np
import pyautogui
from PIL import Image

from farm_core import config, keys
from farm_core.car_collection_finder import compress_sequence, ocr_with_boxes
from farm_core.vision import _get_fh6_window_region

# Confirmed order — Performance Class is always sorted by this fixed,
# game-defined PI ranking whenever a given class is present at all (the
# actual SET shown is dynamic, depending on which cars the account owns —
# see the module docstring — but the RELATIVE ORDER of whichever classes
# do appear never changes). Needed for nothing computational here (the
# geometry approach below doesn't assume a fixed slot-to-letter mapping),
# just documents the assumption the template set itself is built on.
PERFORMANCE_CLASSES = ["D", "C", "B", "A", "S1", "S2", "R", "X"]

# Car Type labels observed live across one account's own filter list (see this module's
# live-testing history) — NOT a confirmed-exhaustive list of every category FH6 defines. The list
# itself only ever shows categories that account owns at least one car in (see the module
# docstring), so a category could be legitimately missing here just because that account has none.
# Purely a UI convenience for farm_ui.wizard's Car Type dropdown (pre-fill suggestions, editable) —
# _find_car_type_row() itself does a live OCR text match and doesn't care whether a value came from
# this list or was typed in by hand. Spellings/spacing here are deliberately the ones actually seen
# in-game via OCR (e.g. "Off-Road", "Modern Supercars", "Rods and Customs"), NOT necessarily matching
# fan-wiki page-title conventions for the same category (e.g. "Offroad", "Modern Super Cars", "Rods &
# Customs") — since this list only exists to be typed into a field that gets OCR-matched exactly,
# the real in-game text is what matters here. "Vintage Racers" is the one exception: added from a
# wiki category list (2026-07-27) with no live OCR capture of our own yet to confirm its exact
# in-game spelling, since the account tested against so far apparently owns none.
KNOWN_CAR_TYPES = [
    "Buggies",
    "Classic Muscle",
    "Classic Racers",
    "Classic Rally",
    "Classic Sports Cars",
    "Cult Cars",
    "Drift Cars",
    "Eclectic Domestics",
    "Extreme Track Toys",
    "GT Cars",
    "Hot Hatch",
    "Hypercars",
    "Modern Muscle",
    "Modern Rally",
    "Modern Sports Cars",
    "Modern Super Saloons",
    "Modern Supercars",
    "Off-Road",
    "Pickups & 4x4s",
    "Rally Monsters",
    "Rare Classics",
    "Retro Hot Hatch",
    "Retro Muscle",
    "Retro Racers",
    "Retro Rally",
    "Retro Sports Cars",
    "Retro Super Saloons",
    "Retro Supercars",
    "Rods and Customs",
    "Sports Utility Heroes",
    "Super GT",
    "Super Hot Hatch",
    "Track Toys",
    "UTVs",
    "Unlimited Buggies",
    "Unlimited Off-Road",
    "Utility Heroes",
    "Vintage Racers",
]

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "assets" / "perf_class_templates"

_MATCH_SCALES = np.linspace(0.5, 2.5, 17)  # coarsened from an original 41 steps — field-measured
# match scores for a correct letter are 0.96-1.00 against an 0.85 confidence floor, comfortable
# margin for a coarser scale step to still land close enough. 41 steps over a multi-megapixel crop,
# repeated once per scale, was the actual cause of Performance Class searches taking ~10s to even
# start moving — see the module's live-testing history.
_MATCH_CONFIDENCE = 0.85  # scores observed: correct matches 0.96-1.00, one false-positive (color-inverted highlighted row) at 0.82 — see module docstring. Set above that gap.

MAX_CAR_TYPE_BURSTS = 40
CAR_TYPE_BURST = 8  # one-row overlap out of ~9-10 rows usably visible under the header

PERF_CLASS_MAX_BURSTS = 8  # Performance Class is a short, fixed-length section (at most 8
# letters) compared to Car Type's dozens of possible categories — nowhere near
# MAX_CAR_TYPE_BURSTS=40 is needed to sweep it, even with a couple of extra rows (e.g. a
# season's Snow Tyres filters, see _find_performance_class_row's docstring) pushing it
# further down than a single screen shows.

EMPTY_READ_RETRIES = 2  # extra attempts to re-read the SAME position before giving up and
# pressing forward blindly. Field-confirmed (2026-07-27): an empty OCR read (a transient miss,
# not the end of the list — the very next burst read normal content again) used to fall straight
# through to pressing another full burst on top, meaning a single bad frame silently doubled the
# distance moved without ever successfully reading what was actually on screen in between —
# a real contributing factor (alongside the burst-speed fix above) in a search that skipped past
# its target. Retrying the READ costs nothing pressed, so it's tried first.
EMPTY_READ_RETRY_WAIT = 0.3


class _SearchAborted(Exception):
    """Internal control-flow signal — caught by find_multiplier_filter() and
    turned into a failed FindResult. Never escapes this module."""


@dataclasses.dataclass
class FindResult:
    success: bool
    message: str
    sequence: list = dataclasses.field(default_factory=list)


def _load_template(label: str) -> np.ndarray:
    path = _TEMPLATE_DIR / f"{label}.png"
    img = cv2.imread(str(path))
    if img is None:
        raise _SearchAborted(f"Template image missing or unreadable: {path}")
    return img


def _match_template_multiscale(
    screen_bgr: np.ndarray, template_bgr: np.ndarray, exclude_y_range: tuple[float, float] | None
) -> tuple[float, tuple[int, int, int, int]]:
    """Best (score, (x, y, w, h)) match of template_bgr anywhere in screen_bgr,
    searching across _MATCH_SCALES for scale-independence (the template was
    captured at one specific window size; a live screenshot may be at a
    different one). exclude_y_range, if given, is blanked out of the search
    first — used to mask out the currently-highlighted row, which renders
    color-inverted (white-on-black instead of black-on-white) and would
    otherwise produce a deceptively confident false match against a
    normal-orientation template — see module docstring.
    """
    screen_gray = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2GRAY)
    if exclude_y_range is not None:
        y0, y1 = int(exclude_y_range[0]), int(exclude_y_range[1])
        screen_gray = screen_gray.copy()
        screen_gray[max(0, y0) : min(screen_gray.shape[0], y1), :] = 255
    template_gray = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2GRAY)

    best_score, best_box = -1.0, None
    for scale in _MATCH_SCALES:
        tw = max(1, int(template_gray.shape[1] * scale))
        th = max(1, int(template_gray.shape[0] * scale))
        if tw < 5 or th < 5 or tw > screen_gray.shape[1] or th > screen_gray.shape[0]:
            continue
        resized = cv2.resize(template_gray, (tw, th), interpolation=cv2.INTER_AREA)
        result = cv2.matchTemplate(screen_gray, resized, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val > best_score:
            best_score, best_box = max_val, (max_loc[0], max_loc[1], tw, th)
    return best_score, best_box


_TOP_CROP_FRAC = 0.10  # trims third-party overlay clutter (FPS/GPU counters, watermarks) near the
# top of the window — well clear of the "Filter" title, which sits ~20%+ down on every screen this
# module reads. Cropping pixels (rather than text-matching this text out afterward) is the only
# option here since overlay content varies per user/software and can't be matched by a fixed string.

# Same lime-green FH6 uses for car_collection_finder.find_highlight_box()'s solid-filled
# highlight — but on THIS screen, that exact hue is ALSO used by the "Filter" title bar and each
# section header ("Performance Class", "Car Type"), which render as solid fills too. The real
# per-row cursor here is visually different: a thin lime-green BORDER around an otherwise
# black-filled row (confirmed via a field screenshot, tools/ocr_debug.py's annotated capture) —
# not a solid fill. find_highlight_box() can't tell these apart (it only checks area + width), so
# it kept locking onto the static title/header bars instead of the real, moving cursor. Fixed here
# with a dedicated detector that also checks FILL RATIO: a solid bar's bounding box is almost
# entirely the matched color; a hollow border's bounding box is mostly black inside.
_CURSOR_HSV_LOW = (30, 200, 200)
_CURSOR_HSV_HIGH = (45, 255, 255)
_CURSOR_MIN_AREA = 400
_CURSOR_MAX_WIDTH_FRAC = 0.5
_CURSOR_MAX_FILL_RATIO = 0.5  # real borders measured well under this (thin ring vs full box); solid
# title/header bars sit near 1.0 — comfortable margin either side of this cutoff.


def _find_cursor_box(img_pil: Image.Image) -> tuple[int, int, int, int] | None:
    """Locate the per-row selection cursor on My Cars' Filter list. Returns
    (x, y, w, h) in img_pil's own pixel space, or None if nothing plausible
    is found. See the constants above for why this needs its own detector
    instead of reusing car_collection_finder.find_highlight_box()."""
    img_bgr = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    img_w = img_bgr.shape[1]
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, _CURSOR_HSV_LOW, _CURSOR_HSV_HIGH)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w * h < _CURSOR_MIN_AREA:
            continue
        if w > img_w * _CURSOR_MAX_WIDTH_FRAC:
            continue
        fill_ratio = cv2.countNonZero(mask[y : y + h, x : x + w]) / (w * h)
        if fill_ratio > _CURSOR_MAX_FILL_RATIO:
            continue  # solid-filled title/header bar, not the hollow cursor border
        candidates.append((w * h, (x, y, w, h)))
    if not candidates:
        return None
    return max(candidates, key=lambda t: t[0])[1]


def _screenshot_fh6() -> Image.Image:
    win = _get_fh6_window_region()
    if win is None:
        raise _SearchAborted("FH6 window not found — is the game running?")
    left, top, width, height = win
    crop_top = int(height * _TOP_CROP_FRAC)
    return pyautogui.screenshot(region=(left, top + crop_top, width, height - crop_top))


def _read_screen() -> tuple[list, np.ndarray, tuple]:
    """One full-window OCR + cursor-detect pass. Returns (ocr_lines,
    screen_bgr_for_cv2, cursor_box_or_None) — all in the same (2x
    upscaled) coordinate space, since that's what both ocr_with_boxes() and
    _find_cursor_box() already operate in."""
    img = _screenshot_fh6()
    lines, upscaled = asyncio.run(ocr_with_boxes(img))
    if upscaled is None:
        raise _SearchAborted("OCR unavailable — cannot read the screen.")
    screen_bgr = cv2.cvtColor(np.array(upscaled), cv2.COLOR_RGB2BGR)
    highlight = _find_cursor_box(upscaled)
    return lines, screen_bgr, highlight


# The fixed button-bar labels FH6 always shows at the bottom of this screen
# (ESC to Back, B to Reset, Enter/Toggle) — these render as several separate
# OCR lines that are all on the SAME visual row, just a few px apart
# vertically (word-height jitter, not real row spacing). Left in, they badly
# skew _estimate_row_height's gap-based median (confirmed in the field: 0/1/7px
# "gaps" between these). Dropped outright rather than cropped out of the
# screenshot — unlike the top overlay (_TOP_CROP_FRAC), this text is fixed
# and safe to match exactly, and the button bar's actual on-screen position
# sits close enough to the lowest real list rows (e.g. Performance Class "X")
# that a blind bottom-% crop risks clipping real content instead.
_IGNORED_LINE_TEXTS = {"ESC : .", "BACK", "B RESET", "TOGGLE"}


def _line_positions(lines: list) -> list[dict]:
    """[{"text", "y0", "y1", "yc"}] for each OCR line with at least one word
    that isn't the fixed button-bar text (_IGNORED_LINE_TEXTS), sorted top-to-bottom."""
    out = []
    for line in lines:
        words = line["words"]
        if not words:
            continue
        text = line["text"]
        if text.strip().upper() in _IGNORED_LINE_TEXTS:
            continue
        y0 = min(w["rect"][1] for w in words)
        y1 = max(w["rect"][1] + w["rect"][3] for w in words)
        out.append({"text": text, "y0": y0, "y1": y1, "yc": (y0 + y1) / 2})
    out.sort(key=lambda d: d["yc"])
    return out


def _text_x_range(lines: list) -> tuple[float, float] | None:
    """Horizontal extent (min_x, max_x) of every OCR word across all lines,
    or None if nothing was read. Used to crop the Performance Class template
    search down to where this screen's actual list content renders — the
    full window width includes blurred background scenery and HUD elements
    that the 41-scale multiscale search would otherwise waste most of its
    time scanning."""
    xs0 = [word["rect"][0] for line in lines for word in line["words"]]
    xs1 = [word["rect"][0] + word["rect"][2] for line in lines for word in line["words"]]
    if not xs0:
        return None
    return min(xs0), max(xs1)


def _estimate_row_height(positions: list[dict]) -> float:
    """Median gap between vertically-ADJACENT OCR lines, restricted to
    plausible single-row gaps — a big gap means one or more rows in between
    weren't OCR-readable (the Performance Class entries) and shouldn't
    pollute the estimate. 300px (in the 2x-upscaled space) is comfortably
    above every real single-row gap measured (~150-190px) and comfortably
    below the smallest observed multi-row gap.
    """
    ys = [p["yc"] for p in positions]
    gaps = sorted(g for g in (ys[i + 1] - ys[i] for i in range(len(ys) - 1)) if g < 300)
    if not gaps:
        raise _SearchAborted("Could not estimate row height — no two adjacent readable rows found.")
    return gaps[len(gaps) // 2]


def _press(key: str, count: int = 1) -> None:
    """Same arrow-keys-get-NAV_WAIT/everything-else-gets-the-default split
    keys._run_key_sequence() uses elsewhere in this app — see
    car_collection_finder._press()'s identical docstring for why. Used for
    the final, precise delta-move onto an already-located target — NOT for
    burst-scanning (see _burst_press below), which needs the slower cadence."""
    wait = config.NAV_WAIT if key in ("up", "down", "left", "right") else None
    keys.mp(key, count, wait)
    if keys._stop_event.is_set():
        raise _SearchAborted(
            "Stopped mid-sequence (lost FH6 focus, or Stop requested) — recorded sequence is incomplete."
        )


def _burst_press(key: str, count: int) -> None:
    """Back to config.NAV_WAIT (2026-07-27) — see EMPTY_READ_RETRIES above
    for the real story: a burst-scan skip that initially looked like fast
    presses confusing FH6's own navigation turned out to more likely be a
    simpler bug (the burst loop reads before pressing, so one transient
    empty OCR read let an entire burst's worth of movement go unverified —
    the arithmetic of two bursts' movement lined up exactly with the gap
    that went missing, no accelerated scrolling required to explain it).
    Now that retry logic is in place, re-trying the fast NAV_WAIT cadence
    for bursts too, on the theory the retry alone is the real fix and the
    burst-speed reversion was never actually necessary — needs field
    re-verification. If a skip like the original one ever recurs WITH the
    retry logic active, that would disprove this theory and point back to
    something burst-speed-specific after all; revert to keys.mp(key, count)
    with no wait override in that case, same as _press()'s non-arrow-key
    default.
    """
    keys.mp(key, count, config.NAV_WAIT if key in ("up", "down", "left", "right") else None)
    if keys._stop_event.is_set():
        raise _SearchAborted(
            "Stopped mid-sequence (lost FH6 focus, or Stop requested) — recorded sequence is incomplete."
        )


def _press_delta_between(y_from: float, y_to: float, row_height: float, header_ys: list[float]) -> int:
    """Down-press count to move from a row at y_from to a row at y_to, in
    the SAME units row_height is measured in. Naively this is just
    round((y_to - y_from) / row_height), but every section header strictly
    between the two (a header occupies a visual row's worth of space but is
    never itself a landable cursor position — Up/Down hops over it in a
    single press) makes that overcount by one per header crossed, so each
    one found in header_ys gets subtracted back out.
    """
    raw_steps = round((y_to - y_from) / row_height)
    lo, hi = (y_from, y_to) if y_from <= y_to else (y_to, y_from)
    headers_between = sum(1 for hy in header_ys if lo < hy < hi)
    # Subtract the correction from the MAGNITUDE, preserving direction — raw_steps
    # is already signed (negative means "target is above"), so a flat
    # `raw_steps - headers_between` would incorrectly push a negative value
    # further negative (larger upward count) instead of shrinking it.
    return raw_steps - headers_between if raw_steps >= 0 else raw_steps + headers_between


# The two section headers this screen can show. "Filter" itself is the
# screen's own title bar, not a list row, and is filtered out alongside
# these wherever we pick a fallback "first selectable row" position.
_SECTION_HEADERS = {"PERFORMANCE CLASS", "CAR TYPE"}
_NON_SELECTABLE = _SECTION_HEADERS | {"FILTER"}


def _header_y(positions: list[dict], name: str) -> tuple[float, float] | None:
    """(y0, y1) of the OCR line exactly matching `name` (case-insensitive), or None if not on screen."""
    name_u = name.upper()
    for p in positions:
        if p["text"].strip().upper() == name_u:
            return (p["y0"], p["y1"])
    return None


def _first_selectable(positions: list[dict]) -> dict | None:
    """Topmost OCR line that isn't a header/title — the cursor's real
    starting position right after opening the filter, before any searching
    has moved it."""
    for p in positions:
        if p["text"].strip().upper() not in _NON_SELECTABLE:
            return p
    return None


def _first_selectable_y(positions: list[dict]) -> float | None:
    """Fallback cursor-position estimate for when _find_cursor_box() finds
    nothing (or finds something implausible — see _current_cursor_y)."""
    first = _first_selectable(positions)
    return first["yc"] if first is not None else None


def _current_cursor_y(highlight_box: tuple[int, int, int, int] | None, positions: list[dict]) -> float | None:
    """Y-center of the detected selection cursor, or None if none was found
    OR the detected box can't actually be a per-row cursor because it sits
    above the topmost selectable row — impossible for a real selection. Kept
    as a defense-in-depth sanity check even after _find_cursor_box() was
    fixed to tell the real (hollow-border) cursor apart from this screen's
    solid-filled title/header bars — see that function's docstring.
    """
    if highlight_box is None:
        return None
    _, hy, _, hh = highlight_box
    yc = hy + hh / 2
    first = _first_selectable(positions)
    if first is not None and yc < first["y0"]:
        return None
    return yc


def _find_performance_class_row(target_letter: str, log: Callable[[str], None]) -> list:
    """Moves the cursor onto the target Performance Class row via template
    matching. Returns the recorded [key, count] sequence (empty if the
    cursor was already there). Does not press Enter — the caller decides
    when to check the box.

    Bursts down (same burst size as _find_car_type_row — it's the same
    scrollable list, same row height) whenever the target letter isn't
    visible in the current viewport, instead of giving up after a single
    read. Added 2026-07-30: FH6's seasonal filter rows (winter adds "Snow
    Tyres Fitted"/"Snow Tyres Not Fitted" above Performance Class) can push
    this section low enough that the very first screen no longer shows
    every letter — confirmed in the field as a search for 'X' (the last,
    lowest class) failing outright instead of scrolling to look further,
    something _find_car_type_row already did correctly for its own section.
    On a screen where the whole section fits in one read (no extra rows,
    or a class near the top), this still matches on the very first
    iteration with zero bursts pressed — unchanged from before.
    """
    sequence = []
    previous_texts = None
    for burst_i in range(PERF_CLASS_MAX_BURSTS):
        lines, screen_bgr, highlight = _read_screen()
        positions = _line_positions(lines)
        current_texts = [p["text"] for p in positions]
        for retry in range(EMPTY_READ_RETRIES):
            if current_texts:
                break
            log(
                f"  [performance_class] burst {burst_i}: empty OCR read — retrying same position "
                f"({retry + 1}/{EMPTY_READ_RETRIES})..."
            )
            keys._sleep(EMPTY_READ_RETRY_WAIT)
            lines, screen_bgr, highlight = _read_screen()
            positions = _line_positions(lines)
            current_texts = [p["text"] for p in positions]
        log(f"  [performance_class] burst {burst_i}: OCR lines: {[(p['text'], round(p['yc'])) for p in positions]}")
        log(f"  [performance_class] highlight box: {highlight}")
        # Same "screen stopped changing" stuck-detection as _find_car_type_row — if two
        # consecutive non-empty reads are identical, the last burst had no effect (genuinely
        # reached the bottom of the scrollable list), not just a bad frame.
        if current_texts and current_texts == previous_texts:
            raise _SearchAborted(
                f"Reached the end of the list without finding Performance Class {target_letter!r} "
                f"(screen stopped changing after burst {burst_i - 1}) — giving up."
            )
        previous_texts = current_texts

        pc_header = _header_y(positions, "Performance Class")
        ct_header = _header_y(positions, "Car Type")
        if burst_i == 0 and pc_header is None:
            raise _SearchAborted("'Performance Class' header not found on screen — is My Cars' Filter list open?")
        row_height = _estimate_row_height(positions)

        if pc_header is not None:
            section_top = pc_header[1]  # header's bottom edge = top of its first entry
        else:
            section_top = 0  # header has scrolled off the top of the viewport already
        if ct_header is not None:
            section_bottom = ct_header[0]
        elif pc_header is not None:
            # Fallback bound (neither "Car Type" nor a scrolled-off header) is the real known
            # max — PERFORMANCE_CLASSES has exactly 8 entries — not an arbitrary guess, and
            # tighter than the +1 buffer might suggest is needed; kept +1 purely for
            # row-height measurement slop.
            section_bottom = section_top + row_height * (len(PERFORMANCE_CLASSES) + 1)
        else:
            section_bottom = screen_bgr.shape[0]
        log(
            f"  [performance_class] burst {burst_i}: pc_header={pc_header} ct_header={ct_header} row_height={row_height:.1f}"
        )

        # Crop horizontally to where this screen's list text actually renders (plus a generous
        # margin), not the full window width — the Performance Class letter shares that same
        # column across every row (same as every Car Type label), so this is a safe, "free"
        # narrowing of the search area rather than a guess at the letter's specific position.
        x_range = _text_x_range(lines)
        img_w = screen_bgr.shape[1]
        if x_range is not None:
            x0, x1 = x_range
            margin = (x1 - x0) * 0.3
            x_lo, x_hi = max(0, int(x0 - margin)), min(img_w, int(x1 + margin))
        else:
            x_lo, x_hi = 0, img_w
        log(
            f"  [performance_class] burst {burst_i}: search crop y=[{section_top:.0f}, {section_bottom:.0f}] "
            f"x=[{x_lo}, {x_hi}] of {img_w}px window width"
        )

        crop = screen_bgr[int(section_top) : int(section_bottom), x_lo:x_hi]
        if crop.shape[0] < 5:
            raise _SearchAborted("Performance Class section appears empty — nothing to search.")

        cursor_y = _current_cursor_y(highlight, positions)
        exclude = None
        if cursor_y is not None and section_top <= cursor_y <= section_bottom:
            exclude = (cursor_y - section_top - row_height * 0.5, cursor_y - section_top + row_height * 0.5)

        template = _load_template(target_letter.upper())
        score, box = _match_template_multiscale(crop, template, exclude)
        if box is not None:
            log(
                f"  [performance_class] burst {burst_i}: best match for {target_letter!r}: "
                f"score={score:.3f} box_x={x_lo + box[0]}"
            )
        else:
            log(f"  [performance_class] burst {burst_i}: best match for {target_letter!r}: score={score:.3f}")

        if score >= _MATCH_CONFIDENCE:
            _, by, _, bh = box
            target_yc = section_top + by + bh / 2

            cursor_source = "highlight"
            if cursor_y is None:
                cursor_source = "fallback:first_selectable"
                cursor_y = _first_selectable_y(positions)
                if cursor_y is None:
                    cursor_source = "fallback:section_top"
                    cursor_y = section_top

            header_ys = [h[0] + (h[1] - h[0]) / 2 for h in (pc_header, ct_header) if h is not None]
            raw_steps = round((target_yc - cursor_y) / row_height)
            headers_between = sum(1 for hy in header_ys if min(cursor_y, target_yc) < hy < max(cursor_y, target_yc))
            log(
                f"  [performance_class] cursor_y={cursor_y:.1f} (source={cursor_source}) target_yc={target_yc:.1f} "
                f"raw_steps={raw_steps} headers_between={headers_between} header_ys={[round(h) for h in header_ys]}"
            )
            delta = _press_delta_between(cursor_y, target_yc, row_height, header_ys)
            log(f"  [performance_class] moving {delta:+d} row(s) to reach {target_letter!r}")
            if delta == 0:
                return sequence
            key = "down" if delta > 0 else "up"
            _press(key, abs(delta))
            sequence.append([key, abs(delta)])
            return sequence

        # Not found in the current viewport. If we've already scrolled past the entire section
        # (Car Type's header now visible, Performance Class's no longer is) there's nowhere left
        # to look — the section only ever lists classes the account owns at least one car in
        # (see module docstring), so this class genuinely isn't present, not just off-screen.
        if ct_header is not None and pc_header is None:
            raise _SearchAborted(
                f"Performance Class {target_letter!r} not found (best score {score:.3f}) — "
                "may not be present in this account's filter list."
            )
        _burst_press("down", CAR_TYPE_BURST)
        sequence.append(["down", CAR_TYPE_BURST])
    raise _SearchAborted(
        f"Performance Class {target_letter!r} not found after {PERF_CLASS_MAX_BURSTS} bursts — giving up."
    )


def _find_car_type_row(target_name: str, log: Callable[[str], None]) -> list:
    """Bursts down (like car_collection_finder's manufacturer search) until
    target_name is OCR-readable on screen, then fine-tunes onto its exact
    row. Returns the recorded [key, count] sequence. Does not press Enter."""
    sequence = []
    total_presses = 0  # cursor's landable-row-index relative to Favourites=0 — every burst press
    # moves exactly 1 landable row per press (header hops are automatic in-game behavior), so this
    # running total IS the cursor's true position, independent of whether the on-screen highlight
    # can be visually detected on this particular read.
    previous_texts = None  # see the stuck-at-the-end check below
    for burst_i in range(MAX_CAR_TYPE_BURSTS):
        lines, _screen_bgr, highlight = _read_screen()
        positions = _line_positions(lines)
        current_texts = [p["text"] for p in positions]
        for retry in range(EMPTY_READ_RETRIES):
            if current_texts:
                break
            log(
                f"  [car_type] burst {burst_i}: empty OCR read — retrying same position ({retry + 1}/{EMPTY_READ_RETRIES})..."
            )
            keys._sleep(EMPTY_READ_RETRY_WAIT)
            lines, _screen_bgr, highlight = _read_screen()
            positions = _line_positions(lines)
            current_texts = [p["text"] for p in positions]
        log(f"  [car_type] burst {burst_i}: {current_texts}")
        log(f"  [car_type] highlight box: {highlight}")
        # If the screen reads IDENTICAL to the previous burst, further Down presses aren't
        # revealing anything new — the list has genuinely hit its bottom (confirmed in the
        # field: a stuck search kept re-reading the exact same 12 lines for 6+ bursts in a row
        # without this check, burning through the whole MAX_CAR_TYPE_BURSTS budget and never
        # stopping on its own). An empty read (a transient OCR miss) doesn't count as "stuck" —
        # only two genuinely matching, non-empty reads in a row do.
        if current_texts and current_texts == previous_texts:
            raise _SearchAborted(
                f"Reached the end of the Car Type list without finding {target_name!r} "
                f"(screen stopped changing after burst {burst_i - 1}) — giving up."
            )
        previous_texts = current_texts
        target_pos = next((p for p in positions if p["text"].strip().upper() == target_name.upper()), None)
        if target_pos is not None:
            cursor_source = "highlight"
            cursor_y = _current_cursor_y(highlight, positions)
            if cursor_y is None:
                cursor_source = "fallback:first_selectable"
                cursor_y = _first_selectable_y(positions)
                if cursor_y is None:
                    cursor_source = "fallback:target_itself"
                    cursor_y = target_pos["yc"]
            row_height = _estimate_row_height(positions)
            header_ys = [p["yc"] for p in positions if p["text"].strip().upper() in _SECTION_HEADERS]
            raw_steps = round((target_pos["yc"] - cursor_y) / row_height)
            headers_between = sum(
                1 for hy in header_ys if min(cursor_y, target_pos["yc"]) < hy < max(cursor_y, target_pos["yc"])
            )
            log(
                f"  [car_type] total_presses_so_far={total_presses} cursor_y={cursor_y:.1f} "
                f"(source={cursor_source}) target_yc={target_pos['yc']:.1f} row_height={row_height:.1f} "
                f"raw_steps={raw_steps} headers_between={headers_between} header_ys={[round(h) for h in header_ys]}"
            )
            delta = _press_delta_between(cursor_y, target_pos["yc"], row_height, header_ys)
            log(f"  [car_type] moving {delta:+d} row(s) to reach {target_name!r}")
            if delta != 0:
                key = "down" if delta > 0 else "up"
                _press(key, abs(delta))
                sequence.append([key, abs(delta)])
            return sequence
        _burst_press("down", CAR_TYPE_BURST)
        sequence.append(["down", CAR_TYPE_BURST])
        total_presses += CAR_TYPE_BURST
    raise _SearchAborted(f"Car Type {target_name!r} not found after {MAX_CAR_TYPE_BURSTS} bursts — giving up.")


def find_multiplier_filter(
    performance_class: str | None = None,
    car_type: str | None = None,
    log: Callable[[str], None] = print,
    on_status: Callable[[str], None] = lambda _msg: None,
) -> FindResult:
    """Opens the Filter list (Y) from My Cars, checks whichever of
    performance_class/car_type are given, then closes it (Esc) — applying
    the filter. At least one of the two must be given.

    PRECONDITION (the caller's job): My Cars is already open and FH6 has
    focus — see module docstring.

    on_status is a SEPARATE, deliberately curated channel from log: log
    carries every verbose diagnostic line (OCR dumps, per-burst scores, the
    press-delta breakdown — useful in a terminal, unreadable on a game
    overlay); on_status carries only the big-picture phase transitions
    ("Scanning for Performance Class 'R'...", "Performance Class 'R'
    found") a GUI can show on top of the FH6 window while this runs. Left
    as a no-op by default so existing callers (the CLI) are unaffected.
    """
    if not performance_class and not car_type:
        return FindResult(success=False, message="Nothing to search for — pass performance_class and/or car_type.")

    log(f"Opening Filter list — target: performance_class={performance_class!r} car_type={car_type!r}")
    on_status("Opening Filter list...")
    sequence = []
    try:
        _press("y")
        sequence.append(["y", 1])
        keys._sleep(1.0)

        if performance_class:
            on_status(f"Scanning for Performance Class '{performance_class}'...")
            sequence.extend(_find_performance_class_row(performance_class, log))
            log(f"  Pressing Enter to check {performance_class!r}...")
            _press("enter")
            sequence.append(["enter", 1])
            on_status(f"Performance Class '{performance_class}' found")

        if car_type:
            on_status(f"Scanning for Car Type '{car_type}'...")
            sequence.extend(_find_car_type_row(car_type, log))
            log(f"  Pressing Enter to check {car_type!r}...")
            _press("enter")
            sequence.append(["enter", 1])
            on_status(f"Car Type '{car_type}' found")

        on_status("Applying filter...")
        _press("escape")
        sequence.append(["escape", 1])
    except _SearchAborted as exc:
        on_status(f"Not found: {exc}")
        return FindResult(success=False, message=str(exc), sequence=[])

    sequence = compress_sequence(sequence)
    log(f"Done. Compressed replay sequence: {sequence}")
    on_status("Done.")
    return FindResult(success=True, message="Filter applied.", sequence=sequence)
