"""OCR-based screen detection. All screen detection is OCR-only — the old cv2
template matching (continue-button.png / creator-info.png) was removed:
post-run backgrounds are dynamic in challenges, so button templates no longer
match reliably.

Captures regions of the FH6 window and uses Windows Runtime OCR to read text.
Falls back gracefully (assume success / return "") if WinRT is unavailable.
"""

import asyncio

import pyautogui

_winrt_ocr_ok: bool | None = None

# The challenge always ends by ~45s (finished early, or forced by the timer) —
# one of two end screens is guaranteed to be showing. "RETRY" is common to
# both; "CONTINUE" / "QUIT" distinguish which one it is (see
# farm_core.challenge.run_challenge_iteration).
CHALLENGE_END_KEYWORDS = {"CONTINUE", "RETRY", "QUIT"}

# Challenge search result button bar:
#   found:     Select | Back | Challenge Options | Search
#   not found:          Back | Challenge Options | Search
# → "Select" is the only button unique to a successful search.
CHALLENGE_FOUND_KEYWORDS = {"SELECT"}

# Selecting a car FH6 hasn't loaded this session lands on the car showcase
# screen instead of the target menu — its button bar is Select | Back |
# Explode | Photo Mode | Hide UI | Drive | Toggle Camera Height, vs.
# Select | Back | Forzavista | Set as Home | Series Update | Drive on the
# target menu for an already-loaded car. How long loading takes isn't known
# up front, so farm_core.remove._select_non_farm_car_as_active polls both
# keyword sets instead of guessing a fixed wait.
CAR_SHOWCASE_KEYWORDS = {"EXPLODE", "PHOTO", "TOGGLE"}
CAR_LOADED_MENU_KEYWORDS = {"FORZAVISTA", "HOME", "UPDATE"}

# The digital speedometer font gets misread as look-alike letters at this
# resolution (observed: "000" → "OOÖ"). Normalize those to "0" before
# checking — a token only counts if it's ALL zero/lookalike chars, so real
# speed values (e.g. "060") are never mistaken for stationary.
_ZERO_LOOKALIKES = str.maketrans({"O": "0", "o": "0", "Ö": "0", "ö": "0", "Q": "0", "D": "0"})

# By STUCK_CHECK_DELAY_SECONDS in (see farm_core.challenge), a car that's
# actually moving has cleared 10+ — so the tens digit is the reliable signal.
# The units digit is noisy (observed misread "000" as "007"), so don't
# require an exact 0 there. Considered whether this needs to differ for a
# speedometer set to MPH instead of KM/H: it doesn't — a genuinely-moving car
# clears 10 in either unit well before this check fires, so one threshold
# covers both.
STUCK_SPEED_THRESHOLD = 10


def _winrt_available() -> bool:
    global _winrt_ocr_ok
    if _winrt_ocr_ok is None:
        try:
            import winrt.windows.graphics.imaging  # noqa: F401
            import winrt.windows.media.ocr  # noqa: F401
            import winrt.windows.storage.streams  # noqa: F401

            _winrt_ocr_ok = True
        except Exception:
            _winrt_ocr_ok = False
            print("[WARN] WinRT OCR unavailable — challenge-end detection disabled")
    return _winrt_ocr_ok


async def _winrt_ocr_async(img_pil) -> str:
    import cv2
    import numpy as np
    import winrt.windows.graphics.imaging as gi
    import winrt.windows.media.ocr as ocr
    import winrt.windows.storage.streams as ss

    engine = ocr.OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        return ""

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
    return result.text if result else ""


def _get_fh6_window_region() -> tuple[int, int, int, int] | None:
    """Return (left, top, width, height) of the FH6 window in physical pixels.

    Uses pygetwindow to find the window by title, then scales from logical
    (DPI-aware) coords to physical pixels using ctypes GetSystemMetrics.
    Returns None if the window is not found.
    """
    try:
        import ctypes

        import pygetwindow as gw

        wins = gw.getWindowsWithTitle("Forza Horizon 6")
        if not wins:
            return None
        win = wins[0]
        logical_sw = ctypes.windll.user32.GetSystemMetrics(0)
        logical_sh = ctypes.windll.user32.GetSystemMetrics(1)
        phys_sw, phys_sh = pyautogui.size()
        sx = phys_sw / logical_sw if logical_sw else 1.0
        sy = phys_sh / logical_sh if logical_sh else 1.0
        return (
            int(win.left * sx),
            int(win.top * sy),
            int(win.width * sx),
            int(win.height * sy),
        )
    except Exception as exc:
        print(f"[WARN] FH6 window lookup failed: {exc}")
        return None


def _read_available_sp() -> int | None:
    """OCR the bottom 20% of the FH6 window to read 'Available Points' from the skill tree.

    The skill tree UI shows two rows in the bottom-left:
        Cost                  1
        Available Points    360
    Returns the integer value, or None if it cannot be determined.
    """
    if not _winrt_available():
        return None
    win = _get_fh6_window_region()
    if win is None:
        pw, ph = pyautogui.size()
        win = (0, 0, pw, ph)
    wx, wy, ww, wh = win
    top = int(wh * 0.80)  # bottom 20%
    img = pyautogui.screenshot(region=(wx, wy + top, ww, wh - top))
    try:
        text = asyncio.run(_winrt_ocr_async(img))
    except Exception as exc:
        print(f"[WARN] OCR error (SP check): {exc}")
        return None
    upper = text.upper()
    tokens = upper.split()
    # WinRT OCR reads the right column (numbers) before the left column (labels),
    # so "360" appears BEFORE "AVAILABLE POINTS" in the token list.
    # The skill-point icon is misread as "0", giving: ... 360 0 AVAILABLE POINTS ...
    # (sometimes there's no space and it fuses onto the number itself instead —
    # "3600" as ONE token — handled below by stripping a trailing zero if the
    # whole-token reading comes out over the 999 cap.)
    # Strategy: find "AVAILABLE", walk backwards skipping the icon "0", return next number.
    try:
        avail_idx = next(i for i, t in enumerate(tokens) if t == "AVAILABLE")
    except StopIteration:
        return None
    found_icon = False
    result = None
    for i in range(avail_idx - 1, -1, -1):
        tok = tokens[i]
        if not tok.isdigit():
            continue
        val = int(tok)
        if val == 0 and not found_icon:
            found_icon = True  # icon "O" read as "0" — skip it
            continue
        result = val
        break
    if result is None:
        # Fallback: number appears after "AVAILABLE POINTS" (normal reading order)
        for i in range(avail_idx + 1, min(avail_idx + 6, len(tokens))):
            if tokens[i].isdigit():
                result = int(tokens[i])
                break
    if result is not None and not (0 <= result <= 999) and result % 10 == 0:
        # Icon fused onto the number as a trailing zero instead of its own
        # token (e.g. "8410" for 841) — strip it if that brings it in range.
        stripped = result // 10
        if 0 <= stripped <= 999:
            result = stripped
    if result is not None and not (0 <= result <= 999):
        print(f"[WARN] SP OCR returned {result} — out of valid range (0–999), ignoring")
        return None
    return result


def _detect_challenge_found_screen() -> bool:
    """Return True if the challenge search result is visible (the Select button is present)."""
    if not _winrt_available():
        return True
    win = _get_fh6_window_region()
    if win is None:
        pw, ph = pyautogui.size()
        win = (0, 0, pw, ph)
    wx, wy, ww, wh = win
    top = int(wh * 0.85)
    img = pyautogui.screenshot(region=(wx, wy + top, ww, wh - top))
    try:
        text = asyncio.run(_winrt_ocr_async(img)).upper()
    except Exception as exc:
        print(f"[WARN] OCR error (challenge found check): {exc}")
        return False
    return any(kw in text for kw in CHALLENGE_FOUND_KEYWORDS)


def _read_car_screen_buttons() -> str:
    """OCR the bottom 20% of the window (button bar). Returns uppercase text ("" on error/no window)."""
    if not _winrt_available():
        return ""
    win = _get_fh6_window_region()
    if win is None:
        pw, ph = pyautogui.size()
        win = (0, 0, pw, ph)
    wx, wy, ww, wh = win
    top = int(wh * 0.80)  # bottom 20% — button bar
    img = pyautogui.screenshot(region=(wx, wy + top, ww, wh - top))
    try:
        return asyncio.run(_winrt_ocr_async(img)).upper()
    except Exception as exc:
        print(f"[WARN] OCR error (car screen check): {exc}")
        return ""


def _read_challenge_end_text() -> str:
    """OCR the bottom 15% of the game window. Returns uppercase text ("" on error/no window).

    The challenge has two possible end screens with SWAPPED key mappings:
      finished on time: Continue (enter) | Retry (escape)
      timed out (45s cap hit without finishing): Retry (enter) | Quit (escape)
    "RETRY" appears on both — only "CONTINUE" / "QUIT" distinguish which screen it is.
    """
    if not _winrt_available():
        return "CONTINUE"  # assume success to avoid spurious resets
    win = _get_fh6_window_region()
    if win is None:
        pw, ph = pyautogui.size()
        win = (0, 0, pw, ph)
    wx, wy, ww, wh = win
    top = int(wh * 0.85)
    img = pyautogui.screenshot(region=(wx, wy + top, ww, wh - top))
    try:
        return asyncio.run(_winrt_ocr_async(img)).upper()
    except Exception as exc:
        print(f"[WARN] OCR error: {exc}")
        return ""


def _read_speedometer_text() -> str:
    """OCR the bottom-right corner of the game window (speedometer area).

    Bottom 20% / right 20% — tight around the speedometer, which sits right
    in the corner. Tighter than SP/challenge-end crops on purpose: less
    surrounding HUD/track clutter in frame improves small-text OCR reliability
    for this particular reading. Used to detect a stuck, wrong-direction start
    (see farm_core.challenge.STUCK_CHECK_DELAY_SECONDS) — speed reads "000"
    while the car isn't moving.
    """
    if not _winrt_available():
        return ""
    win = _get_fh6_window_region()
    if win is None:
        pw, ph = pyautogui.size()
        win = (0, 0, pw, ph)
    wx, wy, ww, wh = win
    top = int(wh * 0.80)  # bottom 20%
    left = int(ww * 0.80)  # right 20%
    region = (wx + left, wy + top, ww - left, wh - top)
    img = pyautogui.screenshot(region=region)
    try:
        text = asyncio.run(_winrt_ocr_async(img)).upper()
    except Exception as exc:
        print(f"[WARN] OCR error (speed check): {exc}")
        return ""
    if not text.strip():
        # Diagnostic for the "reads nothing at all" case — printed instead of
        # silently returning "", so the exact crop box and detected window
        # bounds are in the log the next time this happens (no screenshot
        # needed to debug it — see CLAUDE.md known-behaviors note).
        print(f"[WARN] Speedometer OCR returned nothing — crop region {region}, window {win}")
    return text


def _is_speed_zero(text: str) -> bool:
    """True if the speedometer OCR reads under STUCK_SPEED_THRESHOLD (car effectively stationary)."""
    for tok in text.split():
        normalized = tok.translate(_ZERO_LOOKALIKES)
        if normalized.isdigit() and int(normalized) < STUCK_SPEED_THRESHOLD:
            return True
    return False


def _speed_digit_readable(text: str) -> bool:
    """True if text contains an actual speed digit — as opposed to only the
    unit label (e.g. "MPH"/"KM/H") with no number, which happens when OCR
    misses the digits entirely. Used to tell a confirmed "moving normally"
    reading apart from an inconclusive one that just defaulted to not-stuck.
    """
    return any(tok.translate(_ZERO_LOOKALIKES).isdigit() for tok in text.split())
