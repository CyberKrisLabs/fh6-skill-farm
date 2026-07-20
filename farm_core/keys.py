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
    """
    if wait is None:
        wait = config.MENU_WAIT
    for _ in range(count):
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
