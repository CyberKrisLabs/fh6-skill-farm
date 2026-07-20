"""Phase: Challenge.

Challenges are found by share-code search (config.CFG.challenge_share_code).
The 9x multiplier car must be the active car BEFORE joining — its skill-tree
perks apply even though the challenge forces its own car while driving.

The challenge auto-starts after loading (no enter needed) and always ends by
~45s — either finished early, or forced to stop by the timer. Since the end
time is known, we poll for an early "finished" (CONTINUE) detection every
CHALLENGE_POLL_INTERVAL secs instead of always waiting the full
CHALLENGE_CHECK_DELAY — most runs finish well before the hard cap. Polling
stops CHALLENGE_POLL_MARGIN secs before the ~48s mark so it doesn't race the
final check there, which still runs as a fallback (unchanged from before).
The two possible end screens have SWAPPED key mappings:
  finished on time: Continue (enter) | Retry (escape) — Retry grants SP
  timed out:        Retry (enter)    | Quit (escape)
Timing out is treated like a failed run: always retry (never Quit), even on
the final run of a phase — so the phase only ever exits via Continue, on a
screen farm_core.buy.transition_to_buy already assumes.
Use --skill-points N to run just enough challenges to reach ~999; otherwise loops forever.
"""

import pyautogui

from farm_core import config, keys, vision

CHALLENGE_HOLD_SECONDS = 27  # hold W this long — challenge typically finishes around here
CHALLENGE_CHECK_DELAY = 12  # additional wait after release before the final check (~48s total; hard 45s cap)
CHALLENGE_POLL_INTERVAL = 1  # early-finish poll cadence during CHALLENGE_CHECK_DELAY
CHALLENGE_POLL_MARGIN = 3  # stop early polling this long before the final ~48s check (avoid racing it)

# ⚠ TUNING: flooring W solid from the start overshoots an early jump (~5-10s
# in). Ease in with a short hold, then a stutter of taps, before the main
# hold below. Adjust these until the car clears the jump at a sane speed.
CHALLENGE_START_HOLD_SECONDS = 1  # initial solid W hold
CHALLENGE_START_TAP_HOLD = 1  # each stutter tap's hold duration
CHALLENGE_START_TAP_PAUSE = 1  # released pause between stutter taps
CHALLENGE_START_TAP_COUNT = 2  # number of stutter taps
CHALLENGE_START_LAST_TAP_PAUSE = 1.5  # longer released pause after the final tap, before the main hold

# FH6 bug: after certain mid-run restarts the car can spawn facing the wrong
# way — throttle does nothing, and previously we'd only find out ~45s later
# when the challenge times out. STUCK_CHECK_DELAY_SECONDS after the challenge
# starts, we OCR the speedometer; "000" means stuck, and we restart right away
# instead of waiting out the timer. Only checked on a retry following a
# previous failure — a clean first run has never shown this bug.
STUCK_CHECK_DELAY_SECONDS = 5
# A single OCR read can misread a bad frame and miss a real stuck start (no
# retry to fall back on, unlike the end-of-race detection). Take a few samples
# instead — any one reading near-zero is enough to call it stuck.
STUCK_CHECK_POLL_COUNT = 3
STUCK_CHECK_POLL_INTERVAL = 1

# Set by run_challenge_iteration when it just fixed a stuck start via restart.
# The restart itself reliably re-orients the car (confirmed in testing), so
# farm_core.orchestrator.run_phase uses this to skip the stuck check on the
# very next run instead of re-checking a run that's already known-good.
_last_run_was_stuck_restart = False


def _reset_challenge() -> None:
    """Recover after a failed challenge run (car off-track / didn't finish)."""
    keys.mp("escape")
    keys._sleep(1)
    keys.mp("left", wait=config.NAV_WAIT)
    keys._sleep(config.MENU_WAIT)
    keys.mp("enter")
    keys._sleep(1)
    keys.mp("enter")
    keys._sleep(config.LOADING_RESET_WAIT)


def run_challenge_iteration(final: bool = False, label: str = "", check_stuck_start: bool = False) -> bool:
    """Run one challenge. Returns True on success, False if it needs to be retried (no SP earned).

    final: on the last run of the phase, press enter (Continue) to exit the
    challenge once it finishes on time, instead of escape (Retry). A timed-out
    run is always retried regardless of `final`, so exit only ever happens via
    Continue — never Quit (its post-exit screen isn't confirmed).
    label: the "N/total" (or "N") text already printed for this run, echoed
    back in the finish/timeout log lines so they're identifiable.
    check_stuck_start: pass True when this run follows a failed one — polls the
    speedometer (up to STUCK_CHECK_POLL_COUNT samples) starting at
    STUCK_CHECK_DELAY_SECONDS in, and restarts immediately if any sample reads
    near-zero (wrong-direction spawn bug) instead of waiting out the full
    challenge timer. Sets the module-level _last_run_was_stuck_restart flag
    when it does so — callers should skip the check on the next run rather
    than passing check_stuck_start again (the restart already fixes the
    direction, confirmed in testing).
    """
    global _last_run_was_stuck_restart
    _last_run_was_stuck_restart = False
    tag = f"Challenge {label}" if label else "Challenge"
    ease_in_elapsed = 0.0

    # Ease in instead of flooring it — avoids overshooting the early jump.
    pyautogui.keyDown("w")
    keys._sleep(CHALLENGE_START_HOLD_SECONDS)
    pyautogui.keyUp("w")
    ease_in_elapsed += CHALLENGE_START_HOLD_SECONDS
    if keys._stop_event.is_set():
        return False
    for tap in range(1, CHALLENGE_START_TAP_COUNT + 1):
        pyautogui.keyDown("w")
        keys._sleep(CHALLENGE_START_TAP_HOLD)
        pyautogui.keyUp("w")
        ease_in_elapsed += CHALLENGE_START_TAP_HOLD
        is_last_tap = tap == CHALLENGE_START_TAP_COUNT
        pause = CHALLENGE_START_LAST_TAP_PAUSE if is_last_tap else CHALLENGE_START_TAP_PAUSE
        keys._sleep(pause)
        ease_in_elapsed += pause
        if keys._stop_event.is_set():
            return False

    if check_stuck_start:
        remaining = STUCK_CHECK_DELAY_SECONDS - ease_in_elapsed
        if remaining > 0:
            keys._sleep(remaining)
        if keys._stop_event.is_set():
            return False
        stuck = False
        speed_text = ""
        for sample in range(STUCK_CHECK_POLL_COUNT):
            speed_text = vision._read_speedometer_text()
            if vision._is_speed_zero(speed_text):
                stuck = True
                break
            if sample < STUCK_CHECK_POLL_COUNT - 1:
                keys._sleep(STUCK_CHECK_POLL_INTERVAL)
                if keys._stop_event.is_set():
                    return False
        if stuck:
            print(f"  [WARN] {tag} appears stuck (wrong-direction start) — restarting now")
            _reset_challenge()
            _last_run_was_stuck_restart = True
            return False
        print(f"  [INFO] {tag} stuck-check: moving normally (speed read {speed_text!r})")

    pyautogui.keyDown("w")
    keys._sleep(CHALLENGE_HOLD_SECONDS)
    pyautogui.keyUp("w")
    if keys._stop_event.is_set():
        return False

    # Poll for an early finish instead of always waiting the full delay — check
    # immediately on release, then every CHALLENGE_POLL_INTERVAL secs.
    finished_early = False
    elapsed = 0.0
    poll_deadline = CHALLENGE_CHECK_DELAY - CHALLENGE_POLL_MARGIN
    if "CONTINUE" in vision._read_challenge_end_text():
        print(f"  [INFO] {tag} finished successfully")
        finished_early = True
    while not finished_early and elapsed < poll_deadline:
        step = min(CHALLENGE_POLL_INTERVAL, poll_deadline - elapsed)
        keys._sleep(step)
        elapsed += step
        if keys._stop_event.is_set():
            return False
        if "CONTINUE" in vision._read_challenge_end_text():
            print(f"  [INFO] {tag} finished successfully")
            finished_early = True
            break

    if not finished_early:
        remaining = CHALLENGE_CHECK_DELAY - elapsed
        if remaining > 0:
            keys._sleep(remaining)
        if keys._stop_event.is_set():
            return False

    text = "CONTINUE" if finished_early else vision._read_challenge_end_text()
    if not any(kw in text for kw in vision.CHALLENGE_END_KEYWORDS):
        if keys._stop_event.is_set():
            return False
        print("  [WARN] End screen not visible yet — waiting 5s and rechecking...")
        keys._sleep(5)
        if keys._stop_event.is_set():
            return False
        text = vision._read_challenge_end_text()

    timed_out = "QUIT" in text
    finished = "CONTINUE" in text
    if not timed_out and not finished:
        if "RETRY" in text:
            # RETRY is common to both end screens; CONTINUE/QUIT distinguish
            # them but weren't caught here. A failed run (crashed, didn't
            # finish) shows the same Retry(enter)/Quit(escape) layout as a
            # timeout, so assume that — NOT the pause menu, whose first press
            # (escape) would hit Quit on this screen instead of restarting.
            print(f"  [WARN] {tag} end screen ambiguous (RETRY only) — assuming failed run, retrying")
            keys._press_key("enter")  # Retry
            keys._sleep(config.LOADING_RETRY_WAIT)
            return False
        print("  [WARN] End screen not detected — resetting")
        _reset_challenge()
        return False

    if timed_out:
        print(f"  [WARN] {tag} did not finish in time - not counted")
        keys._press_key("enter")  # Retry (timeout screen)
        keys._sleep(config.LOADING_RETRY_WAIT)
        return False

    if not finished_early:
        print(f"  [INFO] {tag} finished successfully")

    if final:
        keys._press_key("enter")  # Continue — exit the challenge
        keys._sleep(config.LOADING_AFTER_CHALLENGE_EXIT_WAIT)
    else:
        keys._press_key("escape")  # Retry (on-time screen) — SP granted, reloads into the next run
        keys._sleep(config.LOADING_RETRY_WAIT)
    return True


def _search_challenge() -> bool:
    """Type the challenge share code, select the first result, and poll for the
    found screen every 1s for up to 5s. Returns True if found within that window.
    """
    keys.mp("backspace")
    keys.mp("up", wait=config.NAV_WAIT)
    keys.mp("enter")  # enter search / share code field
    pyautogui.typewrite(config.CFG.challenge_share_code, interval=config.TYPING_WAIT)
    keys.mp("enter")
    keys.mp("down", wait=config.NAV_WAIT)
    keys.mp("enter")
    print("  Early poll: checking every 1s for up to 5s while the track loads...")
    for _ in range(5):
        keys._sleep(1)
        if keys._stop_event.is_set():
            return False
        if vision._detect_challenge_found_screen():
            return True
    return False


def transition_to_challenge():
    """Navigate from the main menu to the challenge start screen.

    Starting point: main menu (any tab).
    End point: challenge countdown / ready to press enter to start.
    """
    keys._sleep(1)
    keys.mp("pageup", 2, config.PAGE_WAIT)  # navigate right to Creative Hub tab
    keys.mp("enter")  # open Creative Hub
    keys.mp("down", wait=config.NAV_WAIT)  # move to challenges entry
    keys.mp("enter", wait=2)  # menu settle

    for attempt in range(1, 4):
        # Detection is OCR-only: the challenge result screen has no unique
        # template button (old creator-info.png was Eventlab), only the
        # Select button distinguishes found from not found.
        _detected = _search_challenge()  # polls every 1s for up to 5s
        if keys._stop_event.is_set():
            return
        if _detected:
            print("  [INFO] Challenge found via early poll")

        if not _detected and not keys._stop_event.is_set():
            # Not visible yet — wait 10s more (15s total since search)
            print("  [WARN] Challenge not visible at 5s — waiting 10s more...")
            keys._sleep(10)
            # Rounds 2 and 3: 5s between each
            for _label in ("OCR #2", "OCR #3"):
                if keys._stop_event.is_set():
                    return
                if vision._detect_challenge_found_screen():
                    print(f"  [INFO] Challenge found via {_label}")
                    _detected = True
                    break
                keys._sleep(5)

        if keys._stop_event.is_set():
            return
        if _detected:
            break
        if attempt < 3:
            print(f"  [WARN] Challenge not detected — retrying search (attempt {attempt + 1}/3)...")
        else:
            print("  [ERROR] Challenge not found after 3 search attempts — stopping farm.")
            keys._stop_event.set()
            return

    keys.mp("enter", wait=config.LOADING_CHALLENGE_WAIT)  # select challenge → loading screen
    keys._sleep(1)
