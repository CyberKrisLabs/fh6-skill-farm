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

# FH6's HUD & Gameplay "What's Next" setting (off by default, per-user —
# see farm_settings.Settings.whats_next_enabled) shows an extra Select/Back
# screen after the post-challenge loading finishes. Escape (Back) exits it to
# Free Roam same as normal. Only sent if the user has flagged this on in
# Settings — sending it when the screen never appears would misfire into
# whatever's on screen next.
WHATS_NEXT_EXIT_WAIT = 5  # settle time after backing out of the "What's Next" screen

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


def run_challenge_iteration(final: bool = False, label: str = "") -> bool:
    """Run one challenge. Returns True on success, False if it needs to be retried (no SP earned).

    final: on the last run of the phase, press enter (Continue) to exit the
    challenge once it finishes on time, instead of escape (Retry). A timed-out
    run is always retried regardless of `final`, so exit only ever happens via
    Continue — never Quit (its post-exit screen isn't confirmed). Also
    dismisses the "Rate Challenge?" prompt (Like/Dislike/Cancel) that appears
    for anyone other than the challenge's own creator, and — if
    farm_settings.Settings.whats_next_enabled is set — backs out of FH6's
    "What's Next" HUD & Gameplay screen too — and dismisses its own possible
    follow-up "Change What's Next?" nag via No. See RATE_CHALLENGE_PROMPT_WAIT /
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
        keys._sleep(config.LOADING_RETRY_WAIT)
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
        keys._sleep(RATE_CHALLENGE_PROMPT_WAIT)
        if keys._stop_event.is_set():
            return False
        keys.mp("down", 2, config.NAV_WAIT)  # navigate to Cancel (Like / Dislike / Cancel)
        keys._press_key("enter")  # dismiss the "Rate Challenge?" prompt via Cancel
        keys._sleep(config.LOADING_AFTER_CHALLENGE_EXIT_WAIT)
        if config.CFG.whats_next_enabled:
            if keys._stop_event.is_set():
                return False
            keys._press_key("escape")  # Back — exit the "What's Next" HUD & Gameplay screen
            keys._sleep(CHANGE_WHATS_NEXT_PROMPT_WAIT)
            if keys._stop_event.is_set():
                return False
            keys.mp("down", wait=config.NAV_WAIT)  # navigate to "No" (only matters if the nag prompt appeared)
            keys._press_key("enter")  # dismiss "Change What's Next?" via No
            keys._sleep(WHATS_NEXT_EXIT_WAIT)
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
    pyautogui.typewrite(config.CHALLENGE_SHARE_CODE, interval=config.TYPING_WAIT)
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
    if keys._stop_event.is_set():
        return
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
