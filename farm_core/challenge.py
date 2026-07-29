"""Phase: Challenge.

Challenges are found by share-code search (config.CHALLENGE_SHARE_CODE).
The 9x multiplier car must be the active car BEFORE joining — its skill-tree
perks apply even though the challenge forces its own car while driving.

The challenge auto-starts after loading (no enter needed) and always ends by
~38s — either finished early (typically ~21-23s in), or forced to stop by the
timer. W is held solid from the start (no jump on this track, so no ease-in
needed) through CHALLENGE_POLL_START_DELAY, then polled for an early
"finished" (CONTINUE) detection every CHALLENGE_POLL_INTERVAL secs — while
still holding W — up to CHALLENGE_HOLD_SECONDS, and again after release for up
to CHALLENGE_CHECK_DELAY more before the final check, which still runs as a
fallback. The two possible end screens have SWAPPED key mappings:
  finished on time: Continue (enter) | Retry (escape) — Retry grants SP
  timed out:        Retry (enter)    | Quit (escape)
Timing out is treated like a failed run: always retry (never Quit), even on
the final run of a phase — so the phase only ever exits via Continue, on a
screen farm_core.buy.transition_to_buy already assumes.
Use --skill-points N to run just enough challenges to reach ~999; otherwise loops forever.
"""

import pyautogui

from farm_core import config, keys, vision

CHALLENGE_POLL_START_DELAY = (
    20  # start polling for early finish this long into the hold (typically finishes ~21-23s in)
)
# 12-14s of slack past the typical ~21-23s finish — mainly for wall-hit runs
# (friction from clipping the wall slows the car enough to delay finishing).
CHALLENGE_HOLD_SECONDS = 35  # max time to hold W before releasing regardless of poll result
CHALLENGE_CHECK_DELAY = 5  # additional wait/poll after release before the final check (~40s total; hard 38s cap)
CHALLENGE_POLL_INTERVAL = 1  # poll cadence, both during the hold (after CHALLENGE_POLL_START_DELAY) and after release

# FH6 shows a "Rate Challenge?" (Like / Dislike / Cancel) prompt after
# Continue-ing out of a challenge you didn't create yourself — i.e. for every
# user of this tool except whoever's account owns config.CHALLENGE_SHARE_CODE.
# Down, Down, Enter lands on Cancel regardless of which option was last
# selected. Sent unconditionally on the final exit (not per-cycle-run) since
# it's harmless when the prompt doesn't appear: on the creator's own account
# the game is already past this into a loading screen by the time these fire,
# where input is a no-op.
RATE_CHALLENGE_PROMPT_WAIT = 1  # settle time before checking for the prompt

# FH6's HUD & Gameplay "What's Next" setting shows an extra Select/Back
# screen after the post-challenge loading finishes, instead of dropping
# straight into Free Roam. Used to be gated behind a user-configured
# Settings checkbox (Settings.whats_next_enabled, since removed) since the
# farm couldn't tell whether it was actually showing — replaced with direct
# detection (vision.WHATS_NEXT_KEYWORDS via _wait_for_drivable_or_whats_next
# below), so it no longer matters whether the user remembers to flag this,
# or toggles the game setting mid-session. Escape (Back) exits it to Free
# Roam same as normal.
# Poll ceiling for the drivable-HUD check after backing out of "What's Next"
# (was a flat 5s wait) — settles DRIVABLE_POLL_START_DELAY_SHORT (5s) first,
# then polls up to this before giving up and proceeding anyway.
WHATS_NEXT_EXIT_WAIT = 20

# Backing out of "What's Next" repeatedly without picking a suggested event
# sometimes triggers a follow-up nag: "Change What's Next? You're often
# returning to Free Roam without selecting a suggested Event. Would you like
# to skip these prompts?" — Yes / No / No, and don't ask me again. Down once
# (from the default Yes) + Enter selects plain "No": the user has What's Next
# on by choice, so we keep asking (never "don't ask me again", which would
# permanently change that game setting) without also picking Yes and
# launching some random event. Sent unconditionally after the Back press,
# same reasoning as RATE_CHALLENGE_PROMPT_WAIT above — harmless no-op if the
# nag never appears, since the game's already past this into a loading screen.
CHANGE_WHATS_NEXT_PROMPT_WAIT = 1  # settle time before checking for the nag prompt

# Shared anchor for every "wait until the car is actually drivable" spot in
# this app (main menu -> challenge load, challenge retry and final-exit here,
# and orchestrator._exit_remove_phase_to_game's remove -> Free Roam wait) —
# see vision.DRIVABLE_HUD_KEYWORDS / docs/state-detection-plan.md #2/#3/#4/#5.
# This lives here (not vision.py) since it needs keys._sleep/_stop_event, and here
# rather than duplicated per call site since orchestrator.py already imports
# this module. Each call site keeps its own existing Timings-tab wait
# constant as the poll ceiling/fallback (unlike buy._wait_for_travel_loaded's
# LOADING_TRAVEL_WAIT, this anchor hasn't been field-verified across
# multiple loading scenarios yet, so — per this doc's general guidance —
# nothing gets deleted here).
# Settle time before the first check, scaled to how long each transition
# typically takes before the HUD could plausibly appear at all — checking
# earlier than that just spends OCR calls on a screen that's still
# definitely loading.
# Short: orchestrator._exit_remove_phase_to_game's remove -> Free Roam wait
#   (LOADING_EXIT_TO_GAME_WAIT ceiling).
# Medium: the challenge-exit wait below (LOADING_AFTER_CHALLENGE_EXIT_WAIT
#   ceiling).
# Long: challenge load and retry below (LOADING_CHALLENGE_WAIT /
#   LOADING_RETRY_WAIT ceilings) — these never finish faster than 20s.
# See farm_settings.TIMING_DEFAULTS for the current ceiling values.
DRIVABLE_POLL_START_DELAY_SHORT = 5
DRIVABLE_POLL_START_DELAY_MEDIUM = 15
DRIVABLE_POLL_START_DELAY_LONG = 20
DRIVABLE_POLL_INTERVAL = 1  # poll cadence once polling starts

# Field-confirmed (2026-07-29): Anna/Link render on the minimap HUD ~2s
# before the game actually starts accepting input again. What that costs
# depends on what kind of input follows, not whether it's held vs tapped: W
# is continuous throttle — if the first instant of it doesn't register, the
# car just starts accelerating a beat late, which is harmless and
# self-correcting. An Escape into a menu is a discrete state transition —
# if THAT press is dropped, the code's assumption "I'm now in menu X" is
# simply wrong, and every subsequent press in the sequence fires at the
# wrong screen, desyncing the whole flow. So `settle_after=True` (this
# settle sleep) is only passed by callers about to fire a menu-opening
# Escape — buy.transition_to_buy's opening Escape,
# orchestrator._exit_remove_phase_to_game's Escape to the Main Menu — not by
# challenge load or any challenge retry, whose next action is just the next
# race's throttle.
DRIVABLE_SETTLE_WAIT = 1.5


def _wait_for_drivable(settle: float, max_seconds: float, warn_label: str, *, settle_after: bool = False) -> None:
    """Poll for the minimap HUD (vision.DRIVABLE_HUD_KEYWORDS) confirming the
    car is drivable, instead of a blind fixed wait. Settles `settle` seconds
    first (loading can't plausibly finish before then; clamped to
    `max_seconds` in case a user has tuned that call site's Timings-tab
    value below the settle), then polls every DRIVABLE_POLL_INTERVAL up to
    `max_seconds` before giving up and proceeding anyway. On detection, also
    waits DRIVABLE_SETTLE_WAIT before returning if `settle_after` — pass this
    only when the caller's very next action is a menu-opening key press, not
    a continuous control like throttle (see DRIVABLE_SETTLE_WAIT's comment).
    """
    settle = min(settle, max_seconds)
    keys._sleep(settle)
    if keys._stop_event.is_set():
        return
    elapsed = settle
    while elapsed < max_seconds:
        if any(kw in vision._read_minimap_hud_text() for kw in vision.DRIVABLE_HUD_KEYWORDS):
            if settle_after:
                keys._sleep(DRIVABLE_SETTLE_WAIT)
            return
        keys._sleep(DRIVABLE_POLL_INTERVAL)
        elapsed += DRIVABLE_POLL_INTERVAL
        if keys._stop_event.is_set():
            return
    print(f"  [WARN] Drivable HUD not detected after {max_seconds}s ({warn_label}) — proceeding anyway")


def _wait_for_drivable_or_whats_next(settle: float, max_seconds: float) -> bool:
    """Poll after exiting a challenge for either the drivable HUD (already
    in Free Roam, nothing further to do) or FH6's "What's Next" screen (see
    vision.WHATS_NEXT_KEYWORDS). Returns True if "What's Next" was detected
    (caller should back out of it), False otherwise — including the give-up
    case, since landing directly in Free Roam is the far more common outcome
    ("What's Next" is an opt-in game setting). Waits DRIVABLE_SETTLE_WAIT
    before returning on either detected outcome — see its comment; both
    outcomes lead straight into a key press from the caller.
    """
    settle = min(settle, max_seconds)
    keys._sleep(settle)
    if keys._stop_event.is_set():
        return False
    elapsed = settle
    while elapsed < max_seconds:
        if any(kw in vision._read_minimap_hud_text() for kw in vision.DRIVABLE_HUD_KEYWORDS):
            keys._sleep(DRIVABLE_SETTLE_WAIT)
            return False
        if all(kw in vision._read_car_screen_buttons() for kw in vision.WHATS_NEXT_KEYWORDS):
            keys._sleep(DRIVABLE_SETTLE_WAIT)
            return True
        keys._sleep(DRIVABLE_POLL_INTERVAL)
        elapsed += DRIVABLE_POLL_INTERVAL
        if keys._stop_event.is_set():
            return False
    print(f"  [WARN] Neither drivable HUD nor What's Next screen detected after {max_seconds}s — assuming Free Roam")
    return False


def run_challenge_iteration(final: bool = False, label: str = "") -> bool:
    """Run one challenge. Returns True on success, False if it needs to be retried (no SP earned).

    final: on the last run of the phase, press enter (Continue) to exit the
    challenge once it finishes on time, instead of escape (Retry). A timed-out
    run is always retried regardless of `final`, so exit only ever happens via
    Continue — never Quit (its post-exit screen isn't confirmed). Also
    dismisses the "Rate Challenge?" prompt (Like/Dislike/Cancel) that appears
    for anyone other than the challenge's own creator, and — if FH6's
    "What's Next" HUD & Gameplay screen is detected (vision.WHATS_NEXT_KEYWORDS)
    — backs out of it too, and dismisses its own possible follow-up "Change
    What's Next?" nag via No. See RATE_CHALLENGE_PROMPT_WAIT /
    WHATS_NEXT_EXIT_WAIT / CHANGE_WHATS_NEXT_PROMPT_WAIT above.
    label: the "N/total" (or "N") text already printed for this run, echoed
    back in the finish/timeout log lines so they're identifiable.
    """
    tag = f"Challenge {label}" if label else "Challenge"

    # No early jump on this track — floor it straight from the start instead
    # of easing in. Hold through CHALLENGE_POLL_START_DELAY untouched (the
    # challenge can't finish before then), then keep holding while polling for
    # an early finish so accelerating isn't interrupted mid-poll.
    pyautogui.keyDown("w")
    elapsed = 0.0
    while elapsed < CHALLENGE_POLL_START_DELAY:
        step = min(CHALLENGE_POLL_INTERVAL, CHALLENGE_POLL_START_DELAY - elapsed)
        keys._sleep(step)
        elapsed += step
        if keys._stop_event.is_set():
            pyautogui.keyUp("w")
            return False

    finished_early = False
    while elapsed < CHALLENGE_HOLD_SECONDS:
        if "CONTINUE" in vision._read_challenge_end_text():
            finished_early = True
            break
        step = min(CHALLENGE_POLL_INTERVAL, CHALLENGE_HOLD_SECONDS - elapsed)
        keys._sleep(step)
        elapsed += step
        if keys._stop_event.is_set():
            pyautogui.keyUp("w")
            return False
    pyautogui.keyUp("w")
    if finished_early:
        print(f"  [INFO] {tag} finished successfully")

    # Still not finished by CHALLENGE_HOLD_SECONDS — keep polling a bit longer
    # after release before the final check (~CHALLENGE_HOLD_SECONDS +
    # CHALLENGE_CHECK_DELAY total; hard 38s cap on this track).
    if not finished_early:
        check_elapsed = 0.0
        while not finished_early and check_elapsed < CHALLENGE_CHECK_DELAY:
            step = min(CHALLENGE_POLL_INTERVAL, CHALLENGE_CHECK_DELAY - check_elapsed)
            keys._sleep(step)
            check_elapsed += step
            if keys._stop_event.is_set():
                return False
            if "CONTINUE" in vision._read_challenge_end_text():
                print(f"  [INFO] {tag} finished successfully")
                finished_early = True
                break

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
        # By this point CHALLENGE_HOLD_SECONDS + CHALLENGE_CHECK_DELAY (~40s)
        # plus a 5s recheck have elapsed — the ~38s challenge timer has almost
        # certainly already ended, so this is some end screen OCR just failed
        # to read cleanly, not free-roam or a still-active race. Whether OCR
        # caught "RETRY" alone or nothing at all, assume the failed/timed-out
        # Retry(enter)/Quit(escape) layout and press Enter — NOT a pause-menu
        # escape-first recovery sequence, which would hit Quit on this screen
        # and exit the challenge entirely instead of retrying (confirmed
        # happening in the field, back when this used a stuck-start recovery
        # path that opened with Escape).
        if "RETRY" in text:
            print(f"  [WARN] {tag} end screen ambiguous (RETRY only) — assuming failed run, retrying")
        else:
            print(f"  [WARN] {tag} end screen not detected at all — assuming failed run, retrying")
        keys._press_key("enter")  # Retry
        _wait_for_drivable(DRIVABLE_POLL_START_DELAY_LONG, config.LOADING_RETRY_WAIT, "retry")
        return False

    if timed_out:
        print(f"  [WARN] {tag} did not finish in time - not counted")
        keys._press_key("enter")  # Retry (timeout screen)
        _wait_for_drivable(DRIVABLE_POLL_START_DELAY_LONG, config.LOADING_RETRY_WAIT, "retry")
        return False

    if not finished_early:
        print(f"  [INFO] {tag} finished successfully")

    if final:
        keys._press_key("enter")  # Continue — exit the challenge
        keys._sleep(RATE_CHALLENGE_PROMPT_WAIT)
        if keys._stop_event.is_set():
            return False
        keys.mp("down", 2, config.NAV_WAIT)  # navigate to Cancel (Like / Dislike / Cancel)
        keys._press_key("enter")  # dismiss the "Rate Challenge?" prompt via Cancel
        if _wait_for_drivable_or_whats_next(DRIVABLE_POLL_START_DELAY_MEDIUM, config.LOADING_AFTER_CHALLENGE_EXIT_WAIT):
            print("  [INFO] What's Next screen detected — exiting out of it")
            if keys._stop_event.is_set():
                return False
            keys._press_key("escape")  # Back — exit the "What's Next" HUD & Gameplay screen
            keys._sleep(CHANGE_WHATS_NEXT_PROMPT_WAIT)
            if keys._stop_event.is_set():
                return False
            keys.mp("down", wait=config.NAV_WAIT)  # navigate to "No" (only matters if the nag prompt appeared)
            keys._press_key("enter")  # dismiss "Change What's Next?" via No
            _wait_for_drivable(
                DRIVABLE_POLL_START_DELAY_SHORT, WHATS_NEXT_EXIT_WAIT, "what's next exit", settle_after=True
            )
    else:
        keys._press_key("escape")  # Retry (on-time screen) — SP granted, reloads into the next run
        _wait_for_drivable(DRIVABLE_POLL_START_DELAY_LONG, config.LOADING_RETRY_WAIT, "retry")
    return True


def _search_challenge() -> bool:
    """Type the challenge share code, select the first result, and poll for the
    found screen every 1s for up to 5s. Returns True if found within that window.
    """
    keys.mp("backspace")
    keys.mp("up", wait=config.NAV_WAIT)
    keys.mp("enter")  # enter search / share code field
    pyautogui.typewrite(config.CHALLENGE_SHARE_CODE, interval=config.TYPING_WAIT)
    keys.mp("enter")
    keys.mp("down", wait=config.NAV_WAIT)
    keys.mp("enter")
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
    if keys._stop_event.is_set():
        return
    keys.mp("pageup", 2, config.PAGE_WAIT)  # navigate right to Creative Hub tab
    keys.mp("enter", wait=1)  # open Creative Hub
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
            print("  [INFO] Found challenge")

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

    keys.mp("enter")  # select challenge → loading screen
    _wait_for_drivable(DRIVABLE_POLL_START_DELAY_LONG, config.LOADING_CHALLENGE_WAIT, "challenge load")
    keys._sleep(1)
