"""Low-level key-press helpers, the stop event, and the crash watchdog.

Named `keys` (not `input`) to avoid shadowing the builtin.
"""

import random
import threading
import time

import pyautogui

from farm_core import config, vision

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.01

# The game samples keyboard input once per rendered frame. pyautogui.press()
# releases the key almost instantly — shorter than a frame at low fps — so the
# game can miss the press entirely. Holding each key down for a short random
# span makes every press reliably span at least one input sample.
KEY_HOLD_MIN_S = 0.05
KEY_HOLD_MAX_S = 0.10


def _press_key(key: str) -> None:
    """Press a key with a short held duration instead of an instant tap."""
    pyautogui.keyDown(key)
    time.sleep(random.uniform(KEY_HOLD_MIN_S, KEY_HOLD_MAX_S))
    pyautogui.keyUp(key)


_stop_event = threading.Event()  # set to stop the farm between iterations
_sleep = _stop_event.wait  # like _sleep() but returns early when stop is requested

_WATCHDOG_INTERVAL = 5  # seconds between window-presence checks
_WATCHDOG_MISSES = 3  # consecutive misses before declaring crash (~15 s total)


def _fh6_focused() -> bool:
    """True if the FH6 window is currently the OS foreground window.

    Uses GetForegroundWindow directly rather than vision._get_fh6_window_region()
    (which enumerates via pygetwindow and does DPI-scaling math) — this needs
    to be cheap enough to call before every single key press in mp(), unlike
    the watchdog's once-per-5s crash check. Fails open (returns True) on any
    lookup error, matching this codebase's existing preference for not
    stopping a run over a transient OS-call hiccup (see e.g.
    vision._read_challenge_end_text's "assume success" fallback).
    """
    try:
        import ctypes

        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return "forza horizon 6" in buf.value.lower()
    except Exception:
        return True


def _watchdog_thread() -> None:
    """Background thread: stops the farm if the FH6 window vanishes (crash/close)."""
    misses = 0
    while not _stop_event.is_set():
        _stop_event.wait(_WATCHDOG_INTERVAL)
        if _stop_event.is_set():
            break
        if vision._get_fh6_window_region() is None:
            misses += 1
            if misses >= _WATCHDOG_MISSES:
                print(
                    f"\n[WATCHDOG] FH6 window not found for "
                    f"{misses * _WATCHDOG_INTERVAL}s — game may have crashed. Stopping farm."
                )
                _stop_event.set()
        else:
            misses = 0


def mp(key, count=1, wait=None):
    """Press key with `wait` seconds after each press (menu press helper).

    wait defaults to the current config.MENU_WAIT — looked up at call time (not
    baked in as a stale default) so Timings changes take effect immediately.

    Checks the stop event before every press, not just once per call — so a
    single mp("down", 64, ...) (a real Car Collection row depth) bails
    immediately mid-loop instead of finishing all 64 presses once Stop is
    clicked. Since virtually every key press in this codebase goes through
    mp()/_press_key() (see CLAUDE.md's Performance/Input Rules), this one
    check is what makes Stop responsive across the many ad hoc, unguarded
    transition functions elsewhere — once the stop event is set, every
    subsequent mp() call anywhere becomes a no-op instead of pressing keys.

    Also checks FH6 is still the focused window before every press, same
    granularity as the stop check — if the user tabs away mid-run (e.g.
    during the Remove -> Main Menu transition), further presses would go to
    whatever app they switched to instead. Treated the same as clicking
    Stop (sets _stop_event) rather than pausing/auto-resuming — this
    codebase's transitions are scripted key sequences, not a simple retry
    loop, so resuming mid-sequence later could leave things in a
    half-finished state; a hard stop is the safer behavior.
    """
    if wait is None:
        wait = config.MENU_WAIT
    for _ in range(count):
        if _stop_event.is_set():
            return
        if not _fh6_focused():
            print("[WARN] FH6 lost focus — stopping the farm (same as clicking Stop)")
            _stop_event.set()
            return
        _press_key(key)
        _sleep(wait)


def _run_key_sequence(seq) -> None:
    """Run a sequence of (key, press_count) via mp(), or ("wait", seconds) to pause.

    Arrow keys use config.NAV_WAIT, everything else the default (config.MENU_WAIT).
    """
    for action, val in seq:
        if _stop_event.is_set():
            return
        if action == "wait":
            _sleep(val)
        elif action in ("up", "down", "left", "right"):
            mp(action, val, config.NAV_WAIT)
        else:
            mp(action, val)
