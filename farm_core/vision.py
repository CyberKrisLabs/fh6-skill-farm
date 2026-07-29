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

# The challenge always ends by ~38s (finished early, or forced by the timer) —
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
# up front, so farm_core.unlock._wait_for_car_loaded polls both keyword sets
# instead of guessing a fixed wait.
CAR_SHOWCASE_KEYWORDS = {"EXPLODE", "PHOTO", "TOGGLE"}
CAR_LOADED_MENU_KEYWORDS = {"FORZAVISTA", "HOME", "UPDATE"}


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


def _get_fh6_client_size() -> tuple[int, int] | None:
    """Return the FH6 window's actual renderable client area (width, height,
    physical pixels) — excludes the title bar and borders that
    _get_fh6_window_region()'s GetWindowRect includes. Needed specifically
    for aspect-ratio checks: a windowed (non-fullscreen) game's OUTER window
    rect is taller than its real internal resolution by the title bar's
    height, which skews the ratio away from the game's actual setting.
    Field-confirmed: a real 1024x768 windowed session measured client
    2145x1609 physical (ratio 1.3331, ~exact 4:3) but outer window rect
    1622x1256 (ratio 1.2914) — enough to miss check_window_size_ok()'s 4:3
    check entirely. Returns None if the window can't be found.
    """
    try:
        import ctypes

        import pygetwindow as gw

        wins = gw.getWindowsWithTitle("Forza Horizon 6")
        if not wins:
            return None
        hwnd = wins[0]._hWnd

        class _RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        rect = _RECT()
        if not ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect)):
            return None
        logical_sw = ctypes.windll.user32.GetSystemMetrics(0)
        logical_sh = ctypes.windll.user32.GetSystemMetrics(1)
        phys_sw, phys_sh = pyautogui.size()
        sx = phys_sw / logical_sw if logical_sw else 1.0
        sy = phys_sh / logical_sh if logical_sh else 1.0
        return (int((rect.right - rect.left) * sx), int((rect.bottom - rect.top) * sy))
    except Exception as exc:
        print(f"[WARN] FH6 client size lookup failed: {exc}")
        return None


def check_window_size_ok() -> str | None:
    """Advisory pre-flight check for the one FH6 window trait actually backed
    by solid field data (Guide tab's Timings page / README's resolution note):
    4:3 resolutions test unreliably for skill-point OCR at every size tried.
    Returns a warning message if the window looks 4:3, or None if the window
    can't be found (a separate, already-handled case) or looks fine.

    Deliberately does NOT also flag a "small" window by comparing its height
    to the monitor's — field-tested, dropped: on a large/high-res monitor, a
    perfectly good windowed size (e.g. 2528x1466, ~68% of a 4K monitor's
    height) still falls well short of that monitor's own height, producing a
    false positive with no reliable absolute-pixel threshold to fall back on
    (the only two real data points, ~1185px tall = bad and ~1620px tall =
    fine, don't pin one down). The Guide tab's qualitative "prefer fullscreen
    or a large window" text still covers this, just not as a blocking check.
    """
    region = _get_fh6_window_region()
    if region is None:
        return None
    _left, _top, width, height = region
    # A minimized window reports a tiny/garbage size (Windows moves it to
    # -32000,-32000 with a near-zero width/height) — field-confirmed via this
    # exact check returning (237, 39) for a minimized FH6. This check runs the
    # instant Start is clicked, before the "switch to game" countdown, so FH6
    # being minimized/not-yet-focused at that moment is normal, not small.
    if width < 100 or height < 100:
        return None

    # Use the client (render) area for the ratio, not the outer window rect
    # above — see _get_fh6_client_size()'s comment. Falls back to the outer
    # rect if the client-rect lookup itself fails for any reason.
    client_size = _get_fh6_client_size()
    check_w, check_h = client_size if client_size else (width, height)
    if abs(check_w / check_h - 4 / 3) < 0.02:
        return (
            "4:3 resolutions (e.g. 1024x768) have tested unreliably for skill-point OCR in both "
            "windowed and fullscreen — avoid that regardless of window size."
        )
    return None


def _get_display_dpr() -> float:
    """Device pixel ratio for the primary monitor (e.g. 1.5 for 150% scaling).

    GetDpiForMonitor returns the true effective DPI regardless of this
    process's own DPI-awareness mode — unlike the GetSystemMetrics-based
    ratio in _get_fh6_window_region(), which converts pygetwindow's raw
    values to physical pixels for pyautogui but isn't the right ratio to
    convert back to the logical space Qt widget positioning expects. Ported
    from FH6-Sniper's window_utils._get_display_dpr, which solved the same
    in-game overlay positioning problem there. Falls back to Qt's own
    devicePixelRatio(), then to 1.0.
    """
    try:
        import ctypes
        import ctypes.wintypes

        pt = ctypes.wintypes.POINT(0, 0)
        monitor = ctypes.windll.user32.MonitorFromPoint(pt, 1)  # MONITOR_DEFAULTTOPRIMARY
        dpi_x = ctypes.c_uint(96)
        dpi_y = ctypes.c_uint(96)
        hr = ctypes.windll.shcore.GetDpiForMonitor(monitor, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y))
        if hr == 0:
            return dpi_x.value / 96.0
    except Exception:
        pass
    try:
        from PySide6.QtGui import QGuiApplication

        screen = QGuiApplication.primaryScreen()
        if screen:
            return float(screen.devicePixelRatio())
    except Exception:
        pass
    return 1.0


def get_fh6_window_logical_region() -> tuple[int, int, int, int] | None:
    """Return (left, top, width, height) of the FH6 window in the logical
    coordinate space Qt widget positioning expects — used by farm_ui.overlay
    to center the in-game overlay over the FH6 window.

    All four values are derived from the physical-pixel region (already
    correct for pyautogui) divided by _get_display_dpr(). Field-tested on a
    laptop with real DPI scaling (2026-07-21): pygetwindow's raw win.top/
    win.height, used unscaled at first (matching FH6-Sniper's positioning
    approach, which only round-trips the horizontal axis), produced a
    reported window height (1276) taller than the logical screen height
    (900) and a top offset (278) that landed the overlay ~31% down the
    window — both consistent with raw values being in a larger, unscaled
    space. Scaling all four axes the same way resolved it; deviate from
    Sniper's partial approach here since this is real measured data, not
    theory. Returns None if the window is not found.
    """
    try:
        import pygetwindow as gw

        wins = gw.getWindowsWithTitle("Forza Horizon 6")
        if not wins:
            return None
        win = wins[0]
        phys = _get_fh6_window_region()
        if phys is not None:
            phys_left, phys_top, phys_w, phys_h = phys
            dpr = _get_display_dpr()
            left = int(phys_left / dpr)
            top = int(phys_top / dpr)
            width = int(phys_w / dpr)
            height = int(phys_h / dpr)
        else:
            left, top, width, height = win.left, win.top, win.width, win.height
        return (left, top, width, height)
    except Exception as exc:
        print(f"[WARN] FH6 window lookup failed: {exc}")
        return None


def _read_available_sp() -> int | None:
    """OCR a tight band of the FH6 window to read 'Available Points' from the skill tree.

    The skill tree UI shows two rows stacked in the bottom-left:
        Owned                  10
        Available Points      999
    The crop used to be the whole bottom 20% (both rows plus the button bar
    below), which caused a real parsing bug, not just an OCR-quality one:
    the code assumed OCR always reads numbers before labels for this pair of
    rows (true sometimes, giving tokens like "960 0 OWNED AVAILABLE POINTS"),
    but field-observed OCR text just as often reads labels first ("OWNED
    AVAILABLE POINTS 10 999 0") — and in that order, walking backward from
    "AVAILABLE" hits nothing, falls through to the "next digit forward"
    fallback, and grabs Owned's number (10) instead of Available Points'
    (999). Pixel-measured from a field screenshot (2026-07-22): Owned spans
    ~81.6-83.2% of window height, Available Points ~85.5-87.6%, the Back/
    Unlock All button row starts ~91.9% — SP_ROW_TOP_FRAC/SP_ROW_HEIGHT_FRAC
    below isolate just the Available Points band, with margin on both
    sides, so this row-confusion can't happen regardless of which order OCR
    returns tokens in. Percentage-based (like the other OCR crops here), so
    it should scale with window size the same way; a game update that
    relayouts this panel would need these refit again.
    Returns the integer value, or None if it cannot be determined.
    """
    if not _winrt_available():
        return None
    win = _get_fh6_window_region()
    if win is None:
        pw, ph = pyautogui.size()
        win = (0, 0, pw, ph)
    wx, wy, ww, wh = win
    SP_ROW_TOP_FRAC = 0.843
    SP_ROW_HEIGHT_FRAC = 0.047
    top = int(wh * SP_ROW_TOP_FRAC)
    height = int(wh * SP_ROW_HEIGHT_FRAC)
    region = (wx, wy + top, ww, height)
    img = pyautogui.screenshot(region=region)
    try:
        text = asyncio.run(_winrt_ocr_async(img))
    except Exception as exc:
        print(f"[WARN] OCR error (SP check): {exc}")
        return None
    upper = text.upper()
    tokens = upper.split()
    # WinRT OCR's reading order for this row isn't consistent between calls —
    # field-observed both "360 0 AVAILABLE POINTS" (number, then icon-as-"0",
    # then labels) and "AVAILABLE POINTS 360 0" (labels first, then number,
    # then icon). The backward-walk-from-"AVAILABLE" below handles the first
    # order; the forward fallback after it handles the second. (Previously,
    # with a wider crop that also included the "Owned" row above, an
    # inconsistent order could make the backward walk latch onto Owned's
    # number instead of Available Points' — that's why the crop is tight
    # enough now to contain only this one row's own number + icon.)
    # The icon sometimes fuses onto the number instead of its own token
    # ("3600" as one token) — handled below by stripping a trailing zero if
    # the whole-token reading comes out over the 999 cap.
    try:
        avail_idx = next(i for i, t in enumerate(tokens) if t == "AVAILABLE")
    except StopIteration:
        print("[WARN] SP check: could not find 'Available Points' in the OCR text")
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


_BUTTON_BAR_SLICE_COUNT = 4  # see _read_car_screen_buttons' docstring — 2 wasn't narrow enough
_BUTTON_BAR_SLICE_OVERLAP_FRAC = 0.08


def _button_bar_slices(wx: int, ww: int) -> list:
    """N evenly-sized, overlapping horizontal slices covering [wx, wx+ww).
    Returns [(left, width), ...] in absolute x coordinates. Overlap (as a
    fraction of the total width) keeps a button-hint group straddling a
    slice boundary from being cut in half."""
    n = _BUTTON_BAR_SLICE_COUNT
    nominal = ww / n
    overlap = ww * _BUTTON_BAR_SLICE_OVERLAP_FRAC
    slices = []
    for i in range(n):
        left = max(0.0, i * nominal - overlap)
        right = min(float(ww), (i + 1) * nominal + overlap)
        slices.append((wx + int(left), int(right - left)))
    return slices


def _read_car_screen_buttons() -> str:
    """OCR the bottom 20% of the window (button bar), split into several
    overlapping horizontal slices and OCR'd separately rather than one pass
    over the whole crop.

    Field-confirmed (2026-07-27, via debug screenshots) this isn't a
    crop-width or image-quality problem — a crop of just the left half of
    this bar showed X Explode / Y Photo Mode / BACKSTEG Hide UI fully
    legible, sharp, un-dimmed, yet OCR still dropped all three from that
    half's own text. The real issue is WinRT OCR dropping whole clusters
    when too many small bordered badge+label pairs sit on one line — a
    cousin of the already-documented "isolated single/double-char string
    treated as noise" limitation (multiplier_filter_finder.py's Performance
    Class letters), just for rows of them rather than single isolated ones.
    Slicing narrowly enough that at most ~2 button-hint groups land in any
    one OCR call is the mitigation — _BUTTON_BAR_SLICE_COUNT is deliberately
    a tunable module constant since the right number is empirical/
    field-tuned (2 wasn't enough; 4 was, on the field setup this was
    diagnosed against), not derivable up front. Returns uppercase text
    ("" on error/no window).
    """
    if not _winrt_available():
        return ""
    win = _get_fh6_window_region()
    if win is None:
        pw, ph = pyautogui.size()
        win = (0, 0, pw, ph)
    wx, wy, ww, wh = win
    top = int(wh * 0.80)  # bottom 20% — button bar
    region_y, region_h = wy + top, wh - top
    slices = _button_bar_slices(wx, ww)
    texts = []
    for i, (sx, sw) in enumerate(slices):
        img = pyautogui.screenshot(region=(sx, region_y, sw, region_h))
        try:
            texts.append(asyncio.run(_winrt_ocr_async(img)))
        except Exception as exc:
            print(f"[WARN] OCR error (car screen check, slice {i}): {exc}")
    return " ".join(texts).upper()


# The minimap HUD (bottom-left corner) shows the co-driver's name and a
# "Link" prompt whenever the car is in a drivable state (Free Roam, or an
# active challenge run) — but not during a loading screen. Field-confirmed
# anchor for "is the car actually drivable yet", reusable everywhere a wait
# is really "wait until Free Roam/the challenge is drivable" — main menu ->
# challenge, challenge retry, remove -> Free Roam (see
# farm_core.challenge._wait_for_drivable). "Link" can appear grayed out, but
# it's still real text WinRT OCR should be able to pick up.
DRIVABLE_HUD_KEYWORDS = {"ANNA", "LINK"}

# FH6's "What's Next" (HUD & Gameplay setting) shows a Select/Back button bar
# after exiting a challenge, instead of dropping straight into Free Roam —
# read from the same crop as _read_car_screen_buttons(). "SELECT" alone is
# also used elsewhere (CHALLENGE_FOUND_KEYWORDS, a completely different
# screen/code path) and "BACK" appears on plenty of menus in general, so
# neither is unique on its own — but requiring both together is safe here
# specifically because farm_core.challenge._wait_for_drivable_or_whats_next
# only ever polls this in the narrow post-challenge-exit window, where the
# only two possible outcomes are Free Roam (DRIVABLE_HUD_KEYWORDS) or this
# screen, not an unconstrained global check.
WHATS_NEXT_KEYWORDS = {"SELECT", "BACK"}


def _read_minimap_hud_text() -> str:
    """OCR the bottom-left 20%x20% corner of the window (minimap HUD labels).
    Returns uppercase text ("" on error/no window)."""
    if not _winrt_available():
        return ""
    win = _get_fh6_window_region()
    if win is None:
        pw, ph = pyautogui.size()
        win = (0, 0, pw, ph)
    wx, wy, ww, wh = win
    top = int(wh * 0.80)  # bottom 20%
    width = int(ww * 0.20)  # left 20%
    img = pyautogui.screenshot(region=(wx, wy + top, width, wh - top))
    try:
        return asyncio.run(_winrt_ocr_async(img)).upper()
    except Exception as exc:
        print(f"[WARN] OCR error (drivable HUD check): {exc}")
        return ""


def _read_challenge_end_text() -> str:
    """OCR the bottom 15% of the game window. Returns uppercase text ("" on error/no window).

    The challenge has two possible end screens with SWAPPED key mappings:
      finished on time: Continue (enter) | Retry (escape)
      timed out (38s cap hit without finishing): Retry (enter) | Quit (escape)
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
