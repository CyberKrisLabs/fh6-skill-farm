"""Automated Car Collection position finder — the shared find logic behind
the Setup Wizard's "Find Automatically" button (farm_ui/wizard.py) and the
standalone tools/car_collection_finder.py CLI. See docs/car-position-autodetect-plan.md
for the full design writeup and field-testing history behind every constant
and workaround below — this module is the result of that investigation,
promoted out of the tools/ prototype now that it's proven out.

PRECONDITION (the caller's job, not this module's): Car Collection must
already be open in-game, and FH6 must have focus, before calling find_car().
This module doesn't prompt or wait for that itself — a CLI script and a Qt
dialog need very different ways to ask for it (blocking input() + sleep vs.
a QTimer countdown), so that's left to each caller.

Every real key press goes through farm_core.keys.mp() — the same
hold-timing + FH6-focus + stop-event safety every other automation path in
this app uses, not a bespoke input loop. If FH6 loses focus mid-search, mp()
itself sets the stop event and find_car() returns a failed FindResult rather
than continuing to press keys into the wrong window.
"""

import asyncio
import dataclasses
from collections.abc import Callable
from typing import Any

import pyautogui
from PIL import Image

from farm_core import config, keys
from farm_core.vision import _get_fh6_window_region

# ── OCR + perception helpers ────────────────────────────────────────────────


async def ocr_with_boxes(img_pil: Image.Image) -> tuple[list, Image.Image | None]:
    """Same WinRT recognition vision._winrt_ocr_async() uses, but keeps each
    word's bounding box instead of collapsing everything to a flat string.
    Returns (lines, upscaled_image) — lines is [] and upscaled_image is None
    if the OCR engine itself is unavailable.

    lines: [{"text": <line text>, "words": [{"text": ..., "rect": (x,y,w,h)}, ...]}, ...]
    Boxes are in the 2x-upscaled image's coordinate space (upscaled_image),
    same as vision._winrt_ocr_async()'s internal upscale — not the original
    screenshot's resolution.
    """
    import cv2
    import numpy as np
    import winrt.windows.graphics.imaging as gi
    import winrt.windows.media.ocr as ocr
    import winrt.windows.storage.streams as ss

    engine = ocr.OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        return [], None

    img_bgr = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    h, w = img_bgr.shape[:2]
    img_up = cv2.resize(img_bgr, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
    h2, w2 = img_up.shape[:2]
    rgba = cv2.cvtColor(img_up, cv2.COLOR_BGR2RGBA)

    writer = ss.DataWriter()
    writer.write_bytes(rgba.flatten().tobytes())
    buf = writer.detach_buffer()
    bitmap = gi.SoftwareBitmap(gi.BitmapPixelFormat.RGBA8, w2, h2, gi.BitmapAlphaMode.STRAIGHT)
    bitmap.copy_from_buffer(buf)

    result = await engine.recognize_async(bitmap)
    lines = []
    if result:
        for line in result.lines:
            words = []
            for word in line.words:
                r = word.bounding_rect
                words.append({"text": word.text, "rect": (r.x, r.y, r.width, r.height)})
            lines.append({"text": line.text, "words": words})

    upscaled = Image.fromarray(cv2.cvtColor(img_up, cv2.COLOR_BGR2RGB))
    return lines, upscaled


# FH6's selection highlight — a bright lime/yellow-green border around
# whatever's currently selected (visible on Car Collection, My Cars, and the
# Manufacturers/filter checkbox lists).
# Measured directly from a real Manufacturers-list screenshot (2026-07-26):
# the selection border samples at HSV ~= (36, 227-253, 227-255) — a narrow,
# very saturated/bright lime green.
HIGHLIGHT_HSV_LOW = (30, 200, 200)
HIGHLIGHT_HSV_HIGH = (45, 255, 255)
HIGHLIGHT_MIN_AREA = 400  # discard tiny stray-pixel matches
# The "Manufacturers" screen title is ALSO a big green bar — lime-green text
# on a lime-green background, stretching ~73% of the window width in that
# same real screenshot — and it turns out to be the EXACT SAME color as the
# selection highlight (also measured at HSV ~= (36, ...)). Color alone can
# never tell these two apart; width is the only thing that does; a single
# grid cell measured ~19% of the window width in that same screenshot, vs.
# the title bar's ~73% — comfortably separated by this threshold.
HIGHLIGHT_MAX_WIDTH_FRAC = 0.5


def find_highlight_box(img_pil: Image.Image) -> tuple[int, int, int, int] | None:
    """Locate FH6's selection highlight via color thresholding, not OCR — the
    one thing text-reading alone can't tell us: WHICH cell is currently
    selected, as opposed to merely visible on screen. Returns (x, y, w, h) in
    img_pil's own pixel space, or None if nothing plausible is found.
    """
    import cv2
    import numpy as np

    img_bgr = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    img_w = img_bgr.shape[1]
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, HIGHLIGHT_HSV_LOW, HIGHLIGHT_HSV_HIGH)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w * h < HIGHLIGHT_MIN_AREA:
            continue
        if w > img_w * HIGHLIGHT_MAX_WIDTH_FRAC:
            continue  # too wide to be one grid cell — almost certainly the screen title bar
        candidates.append((cv2.contourArea(c), (x, y, w, h)))
    if not candidates:
        return None
    return max(candidates, key=lambda t: t[0])[1]


def words_near_box(lines: list, box: tuple[int, int, int, int], margin: int = 20) -> list[str]:
    """Words whose center falls within `box` (padded by `margin` px) — a
    rough "what text belongs to this highlighted cell" lookup. Not used by
    find_car() itself (which uses the more precise highlight_cell() + grid
    combination below) — kept for tools/ocr_debug.py's inspector output."""
    hx, hy, hw, hh = box
    x0, y0, x1, y1 = hx - margin, hy - margin, hx + hw + margin, hy + hh + margin
    near = []
    for line in lines:
        for word in line["words"]:
            wx, wy, ww, wh = word["rect"]
            cx, cy = wx + ww / 2, wy + wh / 2
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                near.append(word["text"])
    return near


def _cluster_rows(all_words: list) -> list:
    """Group words into rows by a GAP in y-center, calibrated against the
    words' own HEIGHT — not against other gaps. Adaptive so it works whether
    a "row" is one line of text (Manufacturers list entries) or two (Car
    Collection cards: model name, then "year manufacturer" just below it —
    those two lines must land in the SAME row-group, since they're one car,
    not two).

    Measured directly (center-to-center, not edge-to-edge — the year line's
    text is visibly shorter than the model-name line's, which throws off any
    edge-based measurement) against a real Car Collection screenshot: the
    full sorted list of real (non-near-zero) gaps was
    [4-27 (word-to-word within one line), 48.5, 67.5, 74, 74.5,
    115, 115, 143, 144.5, 164.5, 165, 176, 221.5 (assorted header/next-row
    gaps), 405, 405, 520 (badge-to-model, spans the picture)] — a clean,
    wide natural break between 74.5 (model-to-year: must MERGE) and 115
    (year-to-next-badge and others: must NOT merge).

    Word HEIGHT is the right reference unit (scales with font/window size
    the way real row spacing does, unlike a fixed pixel gap): median word
    height in that screenshot was 58px, and 1.6x that (~93px) lands in the
    middle of the natural break above. Returns rows top-to-bottom, each a
    list of words sorted left-to-right.
    """
    if not all_words:
        return []
    words = sorted(all_words, key=lambda w: w["rect"][1] + w["rect"][3] / 2)
    if len(words) == 1:
        return [words]
    heights = sorted(w["rect"][3] for w in words)
    median_height = heights[len(heights) // 2] or 1
    threshold = median_height * 1.6
    centers = [w["rect"][1] + w["rect"][3] / 2 for w in words]
    gaps = [centers[i + 1] - centers[i] for i in range(len(centers) - 1)]
    rows = [[words[0]]]
    for i, w in enumerate(words[1:], start=1):
        if gaps[i - 1] > threshold:
            rows.append([w])
        else:
            rows[-1].append(w)
    for row in rows:
        row.sort(key=lambda w: w["rect"][0])
    return rows


def build_grid(lines: list, n_cols: int) -> list:
    """Reconstruct a row/column grid straight from OCR word positions.

    `n_cols` (the number of columns actually visible — 4 for the
    Manufacturers list, 5 for Car Collection — confirmed field values) must
    be passed in rather than inferred: a row of all-single-word names (e.g.
    "Bentley BMW Buick Cadillac") has no small intra-name gap to contrast
    against the inter-column gap, so a "big gap = new column" rule has
    nothing to calibrate against and merges the whole row into one cell.
    Instead, the OVERALL x-extent of every word on the page is divided into
    n_cols equal bands, and each word is assigned to whichever band its
    center falls in — using the whole page's extent (not each row's own)
    keeps band boundaries consistent even if one row is missing a word in
    some column.

    Returns a list of rows (top-to-bottom), each exactly n_cols cells
    (left-to-right); an empty column in a row gets {"text": "", "box": None}:
        [{"text": "LAMBORGHINI", "box": (x, y, w, h)}, ...]
    `box` is the union of all words merged into that cell, in the same
    (2x-upscaled) coordinate space ocr_with_boxes()/find_highlight_box() use
    — so a highlight box and a grid cell box are directly comparable.
    """
    all_words = [w for line in lines for w in line["words"]]
    if not all_words:
        return []

    rows = _cluster_rows(all_words)

    # The table's real x-extent, needed to place column bands — but the
    # naive min/max over EVERY word on screen gets skewed by rows that
    # aren't really part of the table at all (a HUD element in the top-right
    # corner, footer button hints, the screen title) and don't span the same
    # width as the actual grid. A field test against a real Manufacturers
    # screenshot showed exactly this: those outlier rows shifted the last
    # column's band boundary enough to split a two-word entry ("Land Rover")
    # across two cells. Use the MEDIAN row's own left/right extent instead —
    # robust to the handful of non-table rows, since most rows here really
    # are full-width table rows.
    row_extents = [
        (min(w["rect"][0] for w in row), max(w["rect"][0] + w["rect"][2] for w in row)) for row in rows if row
    ]
    if row_extents:
        x_min = sorted(e[0] for e in row_extents)[len(row_extents) // 2]
        x_max = sorted(e[1] for e in row_extents)[len(row_extents) // 2]
    else:
        x_min = min(w["rect"][0] for w in all_words)
        x_max = max(w["rect"][0] + w["rect"][2] for w in all_words)
    band_width = (x_max - x_min) / n_cols if n_cols else (x_max - x_min) or 1

    def _col_of(word: dict) -> int:
        cx = word["rect"][0] + word["rect"][2] / 2
        return min(n_cols - 1, max(0, int((cx - x_min) / band_width)))

    grid = []
    for row_words in rows:
        buckets: list[list] = [[] for _ in range(n_cols)]
        for w in row_words:
            buckets[_col_of(w)].append(w)
        cells = []
        for bucket in buckets:
            if not bucket:
                cells.append({"text": "", "box": None})
                continue
            bucket.sort(key=lambda w: w["rect"][0])
            text = " ".join(w["text"] for w in bucket)
            xs = [w["rect"][0] for w in bucket]
            ys = [w["rect"][1] for w in bucket]
            x2s = [w["rect"][0] + w["rect"][2] for w in bucket]
            y2s = [w["rect"][1] + w["rect"][3] for w in bucket]
            box = (min(xs), min(ys), max(x2s) - min(xs), max(y2s) - min(ys))
            cells.append({"text": text, "box": box})
        grid.append(cells)

    # Drop rows that aren't really part of the table — a HUD element in a
    # corner, the screen title, a footer button-hint bar — each of which
    # lands in only ONE of the n_cols bands (a real table row should mostly
    # fill across all of them). A field test found these rows made row
    # indices not match what's actually on screen: with 2 non-table rows
    # (title + a HUD element) ahead of the real first row, "row 9" in the
    # array was actually the 8th real, visible manufacturer row. That offset
    # happens to cancel out of a pure delta between two rows in the SAME
    # array, but it breaks the "assume the cursor starts at row 0" fallback
    # (row 0 wouldn't be a real, selectable row at all) and makes the
    # printed row numbers not match what a human counts on screen.
    #
    # Also drop Car Collection's rarity-badge rows (LEGENDARY/RARE/EPIC/...)
    # — a live run found these sit between one card's model+year row and the
    # NEXT card's, and can never be merged into either by proximity: the
    # badge-to-model gap (spans the whole picture, ~400-500px measured) is
    # actually BIGGER than the year-to-next-badge gap (~176-220px), so no
    # single distance threshold could ever cluster "badge+model+year" as one
    # row without also wrongly merging across real row boundaries. A badge
    # isn't a separate cursor position anyway — it's a label floating over
    # part of one card, never something Down/Up lands on by itself — so
    # counting it as its own grid row inflated the row-distance between two
    # real cards by one extra step per card in between (confirmed in the
    # field: a 1-visual-row gap was computed as 2 grid-rows, overshooting the
    # target by one row).
    #
    # Also drop the CR-cost overlay number FH6 floats in that same spot on
    # each card ("59", "109", "50 59", ...) — not a badge word, so the check
    # above lets it through untouched; see
    # _looks_like_numeric_decoration_row()'s docstring for the field case
    # this was found from (same one-extra-row-of-inflation symptom, this
    # time from the cost number's row rather than a badge row).
    return [
        row
        for row in grid
        if sum(1 for cell in row if cell["text"]) >= 2
        and not _looks_like_badge_row(row)
        and not _looks_like_numeric_decoration_row(row)
    ]


# FH6's rarity/acquisition badges — the small label on each car card ("EPIC",
# "LEGENDARY", ...). A closed, short, game-defined vocabulary, so matching
# against it directly is safe (no real car model/manufacturer name is going
# to end with one of these words). endswith() rather than equality to
# tolerate stray OCR noise prefixed onto the text (observed in the field:
# "i LEGENDARY", "I LEGENDARY" — likely a misread icon glyph).
_BADGE_WORDS = {
    "COMMON",
    "RARE",
    "EPIC",
    "LEGENDARY",
    "TREASURE CAR",
    "BARN FIND",
    "FORZA EDITION",
    "UNIQUE",
}


def _looks_like_badge_row(row: list) -> bool:
    """A field run caught a real gap here: one cell OCR'd "COMMON" as
    "coMM0N" (a zero instead of the letter O — a common OCR confusion), which
    failed an exact endswith() check and let the whole row slip through the
    filter (requiring ALL cells to match), reproducing the exact "target
    landed one row off" bug this filter exists to prevent. Two independent
    tolerances now, either one covering for the other: normalize the 0/O
    mixup before matching, and only require a MAJORITY of non-empty cells to
    match rather than every single one, so a lone unrelated OCR garble on
    one cell doesn't unmask an otherwise-obvious badge row.
    """
    non_empty = [cell["text"].strip().upper().replace("0", "O") for cell in row if cell["text"]]
    if not non_empty:
        return False
    matches = sum(1 for text in non_empty if any(text.endswith(word) for word in _BADGE_WORDS))
    return matches / len(non_empty) >= 0.6


def _looks_like_numeric_decoration_row(row: list) -> bool:
    """FH6 overlays each car card's CR cost as a small floating number
    ("59", "109", "50 59", ...) that lands BETWEEN two real card rows —
    field-confirmed (2026-07-27) sitting between one card's badge/picture
    area and the next's model+year text, same physical layout slot
    _looks_like_badge_row() already covers for rarity words, but these
    aren't badge words so that filter lets them through untouched. A field
    run showed the real consequence: one such row sitting between the
    cursor's real row and the target's real row inflated the grid-row
    distance between them by one (a 1-visual-row gap computed as 2 grid-
    rows), overshooting the target by exactly one row on the final move.
    Same majority-vote tolerance as _looks_like_badge_row (a single stray
    non-numeric OCR token — a misread currency glyph, say — doesn't unmask
    an otherwise-numeric row) rather than requiring every cell to match.
    """
    non_empty = [cell["text"].strip() for cell in row if cell["text"]]
    if not non_empty:
        return False

    def _is_numericish(text: str) -> bool:
        compact = text.replace(" ", "")
        if not compact:
            return False
        digits = sum(1 for c in compact if c.isdigit())
        return digits / len(compact) >= 0.5

    matches = sum(1 for text in non_empty if _is_numericish(text))
    return matches / len(non_empty) >= 0.6


def find_in_grid(grid: list, needle: str) -> tuple[int, int] | None:
    """First (row, col) whose cell text contains `needle` (case-insensitive), or None."""
    needle_u = needle.upper()
    for r, row in enumerate(grid):
        for c, cell in enumerate(row):
            if needle_u in cell["text"].upper():
                return (r, c)
    return None


def find_car_in_grid(grid: list, model: str, year: str) -> tuple[int, int] | None:
    """First (row, col) whose cell text contains every individual word of
    `model` PLUS `year`, all as substrings ANYWHERE in the cell — not `model`
    as one contiguous phrase.

    A field run showed why the naive full-phrase version (find_in_grid) isn't
    enough for a multi-word model name: for "Viper GTS ACR" (1999), the
    year's own text sorted in BETWEEN two of the model's words ("Viper 1999
    GTS ...") since it comes from a physically different source line merged
    into the same cell, and WinRT itself fused "Dodge"+"ACR" into one token
    with no space ("...GTS DodgeACR") — a single-word model like "Revuelto"
    survives both of these unscathed (there's nothing to interleave or fuse
    apart), but a multi-word one doesn't. Checking each word independently
    still finds "VIPER", "GTS", and "ACR" (as a substring of "DODGEACR")
    wherever they land, regardless of order or fused spacing. The year is
    required too — Dodge alone has three different Viper/ACR trims (1999,
    2008, 2016) that "VIPER" and "ACR" alone can't tell apart.
    """
    model_words = model.upper().split()
    year_u = year.upper()
    for r, row in enumerate(grid):
        for c, cell in enumerate(row):
            text_u = cell["text"].upper()
            if year_u in text_u and all(word in text_u for word in model_words):
                return (r, c)
    return None


def highlight_cell(
    grid: list, highlight_box: tuple[int, int, int, int] | None, margin_frac: float = 0.03
) -> tuple[int, int] | None:
    """Which grid cell the highlight covers — i.e. where the cursor currently
    is, in the same (row, col) coordinates find_in_grid() returns. None if no
    highlight, or no cell falls inside it.

    Checks whether each CELL's center falls inside the highlight box (padded
    by `margin_frac` of the highlight's own size — a fraction, not a fixed
    pixel count, so it scales with resolution like everything else here) —
    not the other way around. An earlier version checked whether the
    highlight's center fell inside a cell's box, which works when a cell is
    bigger than the highlight, but FH6's Car Collection highlight surrounds
    an entire card (badge + picture + both text lines), while a text cell's
    own box only covers its text — much smaller. The highlight's center then
    lands in the picture area between cells, matching nothing. Checking the
    smaller thing's center against the bigger box is the correct direction
    regardless of which one happens to be bigger.

    Multiple rows can be inside one highlight this way (e.g. a badge row
    sitting just above the model+year row of the same card, both within the
    same tall highlight) — picks the LOWEST (bottom-most) match, since the
    identifying text (model+year) always sits below any badge/rarity line in
    this layout, matching what find_in_grid() actually searches for.

    margin_frac defaults small (3%): a field test found the real cells always
    sit comfortably WITHIN the highlight's own un-padded box already (a
    highlight 775px tall, cells at y-offsets entirely inside that range) — a
    generous margin (an earlier attempt used 15%) doesn't help matching, it
    only risks reaching far enough past the highlight's true edge to
    incorrectly catch an unrelated row (that same test caught the footer
    button-hint bar, ~72px below the highlight's bottom edge, when 15% of a
    775px-tall highlight added ~116px of padding — comfortably past that gap).
    """
    if highlight_box is None:
        return None
    hx, hy, hw, hh = highlight_box
    margin_x, margin_y = hw * margin_frac, hh * margin_frac
    x0, x1 = hx - margin_x, hx + hw + margin_x
    y0, y1 = hy - margin_y, hy + hh + margin_y
    matches = []
    for r, row in enumerate(grid):
        for c, cell in enumerate(row):
            if cell["box"] is None:  # empty column in this row — nothing to compare against
                continue
            bx, by, bw, bh = cell["box"]
            bcx, bcy = bx + bw / 2, by + bh / 2
            if x0 <= bcx <= x1 and y0 <= bcy <= y1:
                matches.append((r, c))
    if not matches:
        return None
    return max(matches, key=lambda rc: grid[rc[0]][rc[1]]["box"][1])


# ── The actual search ───────────────────────────────────────────────────────

# Confirmed viewport sizes (see docs/car-position-autodetect-plan.md).
MANUFACTURER_COLS = 4
MANUFACTURER_BURST = 11  # one-row overlap out of 12 visible rows
MAX_MANUFACTURER_BURSTS = 30  # ~330 rows ceiling — no on-screen total to bound against for this list
CAR_COLLECTION_COLS = 5
CAR_BURST = 2  # one-row overlap out of 3 visible rows
MAX_CAR_BURSTS = 40  # generous ceiling for one manufacturer's own (usually small) block

EMPTY_READ_RETRIES = 2  # extra attempts to re-read the SAME position before giving up and
# pressing forward blindly — see farm_core.multiplier_filter_finder's identical constant for
# the field-confirmed reasoning (a transient empty OCR read used to silently double the burst
# distance instead of being retried).
EMPTY_READ_RETRY_WAIT = 0.3


class _SearchAborted(Exception):
    """Internal control-flow signal — caught by find_car() and turned into a
    failed FindResult. Never escapes this module."""


@dataclasses.dataclass
class FindResult:
    success: bool
    message: str
    # Combined [key, count] steps — manufacturer jump, then Car Collection
    # local offset, in that order. Empty on failure. Matches the shape
    # farm_settings.CarConfig.car_collection_find_sequence stores and
    # farm_core.keys.mp() takes as its own (key, count) arguments, so a
    # caller can replay it directly with no translation.
    sequence: list = dataclasses.field(default_factory=list)


def _screenshot_fh6() -> Image.Image:
    win = _get_fh6_window_region()
    if win is None:
        raise _SearchAborted("FH6 window not found — is the game running?")
    return pyautogui.screenshot(region=win)


def _read_grid(n_cols: int) -> tuple[list, tuple[int, int, int, int] | None]:
    """One full-window OCR + highlight-detect pass, bundled into a grid plus
    the raw highlight box (still in the grid's own coordinate space)."""
    img = _screenshot_fh6()
    lines, upscaled = asyncio.run(ocr_with_boxes(img))
    grid = build_grid(lines, n_cols)
    box = find_highlight_box(upscaled) if upscaled is not None else None
    return grid, box


def _grid_texts(grid: list) -> list[str]:
    return [cell["text"] for row in grid for cell in row]


def _read_grid_retrying_empty(
    n_cols: int, label: str, burst_i: int, log: Callable[[str], None], min_rows: int = 1
) -> tuple[list, tuple[int, int, int, int] | None]:
    """_read_grid(), but retries in place (no keys pressed) up to
    EMPTY_READ_RETRIES times if the grid comes back suspiciously thin — a
    transient OCR miss, not "burst-scanned into blank space", so the right
    response is to re-check the SAME position rather than blindly pressing
    another burst on top of a read that never actually happened.

    `min_rows` covers a variant of this same failure that a plain emptiness
    check (the original `not grid`, still the default via min_rows=1) can
    miss: field-confirmed (2026-07-27) a screenshot taken mid-scroll-
    animation caught the screen's OWN fixed header/title text ("Car
    Collection", the points counter, etc. — present in EVERY real capture
    too) while the actual car grid beneath it was still blank, producing a
    technically-non-empty grid with far fewer real rows than this viewport
    ever legitimately shows. Callers pass a rough floor for their own
    viewport (e.g. Car Collection shows ~3 rows at once, Manufacturers ~12)
    — comfortably below what a real read normally shows, so this only
    catches genuinely thin reads, not a legitimate near-the-end-of-the-list
    page that happens to have fewer rows than usual.
    """
    grid, box = _read_grid(n_cols)
    for retry in range(EMPTY_READ_RETRIES):
        if len(grid) >= min_rows:
            break
        log(
            f"  [{label}] burst {burst_i}: thin/empty OCR read ({len(grid)} row(s)) — "
            f"retrying same position ({retry + 1}/{EMPTY_READ_RETRIES})..."
        )
        keys._sleep(EMPTY_READ_RETRY_WAIT)
        grid, box = _read_grid(n_cols)
    return grid, box


def _press(key: str, count: int = 1) -> None:
    """Same arrow-keys-get-NAV_WAIT/everything-else-gets-the-default split
    keys._run_key_sequence() uses elsewhere in this app — config.NAV_WAIT is
    10x faster than the default config.MENU_WAIT (0.05s vs 0.5s). Used for
    the final, precise _move_delta onto an already-located target — NOT for
    burst-scanning (see _burst_press below), which needs the slower cadence.
    """
    wait = config.NAV_WAIT if key in ("up", "down", "left", "right") else None
    keys.mp(key, count, wait)
    if keys._stop_event.is_set():
        raise _SearchAborted(
            "Stopped mid-sequence (lost FH6 focus, or Stop requested) — recorded sequence is incomplete."
        )


def _burst_press(key: str, count: int) -> None:
    """Back to config.NAV_WAIT (2026-07-27) — see
    multiplier_filter_finder._burst_press()'s docstring for the full field
    investigation this mirrors: a burst-scan skip initially looked like fast
    presses confusing FH6's own navigation, but the more likely real cause
    was simpler (the burst loop reads before pressing, so one transient
    empty OCR read let an entire burst's worth of movement go unverified —
    the arithmetic lined up exactly with the gap that went missing, no
    accelerated scrolling required). Now that _read_grid_retrying_empty
    exists, re-trying the fast cadence for bursts too, on the theory the
    retry alone is the real fix — needs field re-verification. If a skip
    like the original one ever recurs WITH the retry active, revert to
    keys.mp(key, count) with no wait override, same as _press()'s
    non-arrow-key default.
    """
    keys.mp(key, count, config.NAV_WAIT if key in ("up", "down", "left", "right") else None)
    if keys._stop_event.is_set():
        raise _SearchAborted(
            "Stopped mid-sequence (lost FH6 focus, or Stop requested) — recorded sequence is incomplete."
        )


def _move_delta(cursor_rc: tuple[int, int], target_rc: tuple[int, int]) -> list:
    """Press Down/Up/Right/Left to cover (target_rc - cursor_rc) in one
    batch per axis. Returns the recorded [key, count] sequence."""
    seq = []
    dr = target_rc[0] - cursor_rc[0]
    dc = target_rc[1] - cursor_rc[1]
    if dr > 0:
        _press("down", dr)
        seq.append(["down", dr])
    elif dr < 0:
        _press("up", -dr)
        seq.append(["up", -dr])
    if dc > 0:
        _press("right", dc)
        seq.append(["right", dc])
    elif dc < 0:
        _press("left", -dc)
        seq.append(["left", -dc])
    return seq


def _locate_cursor(
    grid: list, box: tuple[int, int, int, int] | None, label: str, log: Callable[[str], None]
) -> tuple[int, int]:
    """Map the highlight box onto the grid; falls back to assuming (0, 0)
    (top-left of whatever's currently visible) if detection fails — a real
    assumption, not a guarantee, since burst-navigation only ever presses
    Down (column should stay 0), and the *first* page after opening/jumping
    is assumed to show the cursor at its own top — see the plan doc.
    """
    rc = highlight_cell(grid, box)
    if rc is None:
        log(f"  [{label}] highlight not detected/matched — assuming cursor at (0, 0) of this page")
        return (0, 0)
    log(f"  [{label}] cursor detected at grid {rc}: {grid[rc[0]][rc[1]]['text']!r}")
    return rc


def _find_manufacturer(target: dict, log: Callable[[str], None]) -> list:
    _press("backspace")
    sequence = [["backspace", 1]]
    keys._sleep(1.0)  # menu-open settle

    previous_texts = None  # see the stuck-at-the-end check below
    for burst_i in range(MAX_MANUFACTURER_BURSTS):
        grid, box = _read_grid_retrying_empty(MANUFACTURER_COLS, "manufacturers", burst_i, log)
        current_texts = _grid_texts(grid)
        log(f"  [manufacturers] burst {burst_i}: {current_texts}")
        # If the screen reads IDENTICAL to the previous burst, further Down presses aren't
        # revealing anything new — the list has genuinely hit its bottom. An empty read (already
        # retried above) doesn't count as "stuck" — only two genuinely matching, non-empty reads
        # in a row do.
        if current_texts and current_texts == previous_texts:
            raise _SearchAborted(
                f"Reached the end of the Manufacturers list without finding {target['manufacturer']!r} "
                f"(screen stopped changing after burst {burst_i - 1}) — giving up."
            )
        previous_texts = current_texts
        target_rc = find_in_grid(grid, target["manufacturer"])
        if target_rc is not None:
            cursor_rc = _locate_cursor(grid, box, "manufacturers", log)
            log(f"  [manufacturers] target at grid {target_rc} — moving...")
            sequence.extend(_move_delta(cursor_rc, target_rc))
            break
        _burst_press("down", MANUFACTURER_BURST)
        sequence.append(["down", MANUFACTURER_BURST])
    else:
        raise _SearchAborted(
            f"Manufacturer {target['manufacturer']!r} not found after {MAX_MANUFACTURER_BURSTS} bursts — giving up."
        )

    grid, box = _read_grid(MANUFACTURER_COLS)
    cursor_rc = highlight_cell(grid, box)
    cell_text = grid[cursor_rc[0]][cursor_rc[1]]["text"] if cursor_rc else "?"
    log(f"  [manufacturers] after move, highlighted cell: {cell_text!r}")
    if target["manufacturer"].upper() not in cell_text.upper():
        raise _SearchAborted(f"Landed on {cell_text!r}, not {target['manufacturer']!r} — aborting before Enter.")

    log(f"  Pressing Enter on {target['manufacturer']!r}...")
    _press("enter")
    sequence.append(["enter", 1])
    keys._sleep(1.0)
    return sequence


def _car_matches(cell_text: str, target: dict) -> bool:
    text_u = cell_text.upper()
    return target["year"] in text_u and all(w in text_u for w in target["model"].upper().split())


def _find_car_in_collection(target: dict, log: Callable[[str], None]) -> list:
    sequence = []
    manufacturer_seen = False
    previous_texts = None  # see the stuck-at-the-end check below
    for burst_i in range(MAX_CAR_BURSTS):
        grid, box = _read_grid_retrying_empty(CAR_COLLECTION_COLS, "car_collection", burst_i, log)
        current_texts = _grid_texts(grid)
        log(f"  [car_collection] burst {burst_i}: {current_texts}")

        # If the screen reads IDENTICAL to the previous burst, further Down presses aren't
        # revealing anything new — genuinely hit the bottom of the whole Car Collection (the
        # manufacturer-boundary check below covers the far more common "scrolled into the next
        # manufacturer" case; this is a backstop for the rarer "target's manufacturer is the very
        # last one in the account's whole collection" case that check can't catch). An empty read
        # (already retried above) doesn't count as "stuck" — only two genuinely matching,
        # non-empty reads in a row do.
        if current_texts and current_texts == previous_texts:
            raise _SearchAborted(
                f"Reached the end of Car Collection without finding {target['model']!r} "
                f"({target['year']}) — screen stopped changing after burst {burst_i - 1} — giving up."
            )
        previous_texts = current_texts

        # Match model words + year independently, not "model" as one
        # contiguous phrase — see find_car_in_grid()'s docstring.
        target_rc = find_car_in_grid(grid, target["model"], target["year"])
        if target_rc is not None:
            cursor_rc = _locate_cursor(grid, box, "car_collection", log)
            if cursor_rc == target_rc:
                log("  [car_collection] already on the target car.")
            else:
                log(f"  [car_collection] target at grid {target_rc} — moving...")
                sequence.extend(_move_delta(cursor_rc, target_rc))
            break

        # Bail out the moment the target's manufacturer is no longer visible
        # anywhere on screen, rather than scrolling all the way to
        # MAX_CAR_BURSTS — once we've scrolled past this manufacturer's whole
        # block into the next one, the target is never going to appear no
        # matter how many more bursts run. Only fires after having actually
        # seen the manufacturer at least once (the jump should land right at
        # the start of its block, but give it a burst or two of margin before
        # trusting an absence).
        manufacturer_here = target["manufacturer"] in " ".join(current_texts).upper()
        if manufacturer_here:
            manufacturer_seen = True
        elif manufacturer_seen:
            raise _SearchAborted(
                f"Scrolled past every {target['manufacturer']} car without finding "
                f"{target['model']!r} ({target['year']}) — giving up rather than continuing "
                "into the next manufacturer's cars."
            )

        _burst_press("down", CAR_BURST)
        sequence.append(["down", CAR_BURST])
    else:
        raise _SearchAborted(f"Car {target['model']!r} not found after {MAX_CAR_BURSTS} bursts — giving up.")

    grid, box = _read_grid(CAR_COLLECTION_COLS)
    cursor_rc = highlight_cell(grid, box)
    cell_text = grid[cursor_rc[0]][cursor_rc[1]]["text"] if cursor_rc else "?"
    log(f"  [car_collection] final highlighted cell: {cell_text!r}")
    if not _car_matches(cell_text, target):
        raise _SearchAborted(f"Landed on {cell_text!r}, not {target['model']!r} — recorded sequence is wrong.")
    return sequence


_NAV_AXES = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


def compress_sequence(sequence: list) -> list:
    """Collapses consecutive navigation presses (up/down/left/right) into
    their NET per-axis delta, without crossing any non-navigation action
    (enter/escape/y/backspace) — e.g. a burst-scan that overshot and
    corrected, recorded verbatim as
    [["down", 8], ["down", 8], ["down", 8], ["down", 8], ["up", 6]], becomes
    just [["down", 26]].

    This only simplifies the SEQUENCE after a search completes, for a
    faster/cleaner replay later (farm_core.buy/remove) — the search itself
    is unaffected, since it still needs to burst-scan/explore to actually
    find the target in the first place; only the recorded PATH is
    compressed afterward, not how it was found. Safe because navigation
    presses between two non-navigation actions are always relative to the
    SAME starting position (nothing else happened in between to change
    what "down"/"up" mean) — never merges ACROSS a non-navigation action,
    since that marks a genuine state change (e.g. a menu jump, a checkbox
    toggle) that the moves before/after are relative to different things.
    """
    compressed = []
    i = 0
    while i < len(sequence):
        key, count = sequence[i]
        if key not in _NAV_AXES:
            compressed.append([key, count])
            i += 1
            continue
        dx, dy = 0, 0
        while i < len(sequence) and sequence[i][0] in _NAV_AXES:
            k, c = sequence[i]
            ax, ay = _NAV_AXES[k]
            dx += ax * c
            dy += ay * c
            i += 1
        if dy > 0:
            compressed.append(["down", dy])
        elif dy < 0:
            compressed.append(["up", -dy])
        if dx > 0:
            compressed.append(["right", dx])
        elif dx < 0:
            compressed.append(["left", -dx])
    return compressed


def find_car(
    target: dict[str, Any],
    log: Callable[[str], None] = print,
    on_status: Callable[[str], None] = lambda _msg: None,
) -> FindResult:
    """Run the full automated search: jump to the target's manufacturer in
    the Manufacturers list, then locate the exact car within Car Collection.

    `target`: {"manufacturer": ..., "model": ..., "year": ...} (matching
    farm_settings.CarInfo's own fields — build with
    `{"manufacturer": car.manufacturer, "model": car.model, "year": car.year}`
    from a farm_settings.Car).

    `log`: receives progress lines as they happen — defaults to print() for
    CLI use; the Setup Wizard passes something that emits a Qt signal
    instead, so this never touches Qt directly.

    `on_status` is a SEPARATE, deliberately curated channel from `log` — same
    split as farm_core.multiplier_filter_finder.find_multiplier_filter(): `log`
    carries every verbose diagnostic line (burst dumps, grid contents —
    useful in a terminal, unreadable on a game overlay), `on_status` carries
    only the big-picture phase transitions a GUI can show on top of the FH6
    window while this runs. Left as a no-op by default so existing callers
    (the CLI) are unaffected.

    PRECONDITION: caller has already confirmed Car Collection is open and
    FH6 has focus — see module docstring.
    """
    log(f"Target: {target}")
    on_status(f"Searching for manufacturer '{target['manufacturer']}'...")
    try:
        manufacturer_sequence = _find_manufacturer(target, log)
        on_status(f"Manufacturer '{target['manufacturer']}' found — searching for {target['model']}...")
        car_sequence = _find_car_in_collection(target, log)
    except _SearchAborted as exc:
        on_status(f"Not found: {exc}")
        return FindResult(success=False, message=str(exc), sequence=[])

    sequence = compress_sequence(manufacturer_sequence + car_sequence)
    log(f"Found it. Compressed replay sequence: {sequence}")
    on_status(f"Found {target['model']} ({target['year']})!")
    return FindResult(success=True, message=f"Found {target['model']} ({target['year']}).", sequence=sequence)
