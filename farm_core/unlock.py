"""Phase: Unlock.

Start at the full car collection list. Unlocks the wheelspin skills on one
car per iteration.

Steps are (key, press_count) executed via keys.mp(); ("wait", seconds) pauses.
Arrow keys use config.NAV_WAIT, everything else the default (config.MENU_WAIT).
"""

import math

from farm_core import config, keys, vision

# Entering the skill tree once the car's own menu is showing (any showcase
# view has already been escaped out of — see _wait_for_car_loaded) is
# identical for every car: starts with the cursor on that menu, ends with
# the tree open and ready for the SP OCR check.
ENTER_SKILL_TREE = [
    ("down", 1),  # Move down to "Upgrades & Tuning"
    ("enter", 1),  # Enter Upgrades & Tuning
    ("down", 7),  # Move down to "Car Mastery"
    ("enter", 1),  # Enter Car Mastery
    ("wait", 0.5),
]

# Leaving is also identical: escape out of the skill tree, escape out of
# Upgrades & Tuning, then up to the "My Cars" button and enter — back at the
# car list.
EXIT_TO_CAR_LIST = [
    ("escape", 1),  # Exit out of skill tree
    ("wait", 1),
    ("escape", 1),  # Exit out of Upgrades & Tuning
    ("wait", 1),
    ("up", 1),  # Move up to "My Cars" button
    ("enter", 1),  # Enter My Cars
]

# Per-car skill-tree walks, keyed by CarConfig.car_id (settings pick the car,
# the walk lives here in code). Only the walk through the tree itself is
# car-specific — it starts with the cursor on the tree root (after
# ENTER_SKILL_TREE) and ends with the wheelspin skills bought.
UNLOCK_SEQUENCES = {
    "lambo_revuelto": [
        ("enter", 1),
        ("wait", 1),
        ("up", 1),
        ("enter", 1),
        ("wait", 1),
        ("up", 1),
        ("enter", 1),
        ("wait", 1),
        ("up", 1),
        ("enter", 1),
        ("wait", 1),
        ("right", 1),
        ("enter", 1),
        ("wait", 1),
        ("right", 1),
        ("enter", 1),
        ("wait", 1),
    ],
}

if config.CFG.selected_car not in UNLOCK_SEQUENCES:
    print(f"[WARN] No unlock walk defined for '{config.CFG.selected_car}' — the unlock phase will fail")


def transition_to_unlock():
    """Navigate from the post-buy screen to the start of the unlock loop.

    Starting point: Car Collection after finishing the buy loop.
    End point: car collection list, ready to start unlock loop.
    """
    keys.mp("escape", 3)
    keys._sleep(1)  # wait for menu to settle after escaping Car Collection
    if keys._stop_event.is_set():
        return
    keys.mp("pagedown", 2, config.PAGE_WAIT)
    keys.mp("enter")


def _open_cars_sorted_by_recent():
    """Open my cars and sort by recently added. Selection lands on Car1 (most recent).

    Must be called while already inside the My Cars list — mp("x") is the Sort
    button there, not a generic key.
    """
    keys._sleep(1)
    if keys._stop_event.is_set():
        return
    keys.mp("x")  # Sort button (My Cars list)
    keys.mp("down", 6, config.NAV_WAIT)  # navigate to sort option
    keys.mp("enter")  # Selects "Recently Added"
    keys.mp("backspace")  # Hotkey to jump to recently added
    keys.mp("enter")  # Selects "All Cars"


def _open_cars_for_unlock_resume():
    """Re-open car list keeping the last selection (sort already set from iter 1).

    Must be called while already inside the My Cars list — mp("x") is the Sort
    button there, not a generic key.
    """
    keys._sleep(1)
    if keys._stop_event.is_set():
        return
    keys.mp("x")  # Sort button (My Cars list)
    keys.mp("down", 6, config.NAV_WAIT)  # Move down to "Recently Added" sort option
    keys.mp("enter")  # Selects "Recently Added"


# run_unlock_iteration can't know in advance whether a car it opens is
# already loaded from earlier this session (lands directly on its own menu)
# or not (lands on the showcase view first) — polls for whichever screen
# shows up instead of guessing a fixed wait, same approach as
# remove._select_non_farm_car_as_active. This also means Unlock no longer
# requires every car to be strictly non-preloaded — either state is now
# detected and handled, not just assumed.
CAR_LOAD_POLL_START_DELAY = 5  # settle time before the first check
CAR_LOAD_POLL_INTERVAL = 1  # poll cadence once polling starts
CAR_LOAD_POLL_MAX_SECONDS = 20  # give up after this long (assume showcase — see give-up case below)
CAR_SHOWCASE_EXIT_WAIT = 2  # settle time after escaping the showcase view


def _wait_for_car_loaded() -> bool:
    """Poll for whichever screen shows up after selecting a car in the list.

    Returns True if the showcase view was detected (not loaded this session
    — caller needs an extra escape before the skill-tree walk), False if the
    already-loaded menu was detected. The give-up case (neither ever
    detected) also returns True: unlike remove._select_non_farm_car_as_active
    (which switches to some *other*, likely-already-driven car and
    reasonably assumes already-loaded on a give-up), Unlock almost always
    processes the farm's own freshly-bought cars, so the showcase view is
    the far more common true state — defaulting to "already loaded" here
    would guess wrong most of the time.
    """
    keys._sleep(CAR_LOAD_POLL_START_DELAY)
    if keys._stop_event.is_set():
        return True

    elapsed = CAR_LOAD_POLL_START_DELAY
    while elapsed < CAR_LOAD_POLL_MAX_SECONDS:
        buttons = vision._read_car_screen_buttons()
        if any(kw in buttons for kw in vision.CAR_SHOWCASE_KEYWORDS):
            return True
        if any(kw in buttons for kw in vision.CAR_LOADED_MENU_KEYWORDS):
            return False
        keys._sleep(CAR_LOAD_POLL_INTERVAL)
        elapsed += CAR_LOAD_POLL_INTERVAL
        if keys._stop_event.is_set():
            return True

    print(f"  [WARN] Neither screen detected after {CAR_LOAD_POLL_MAX_SECONDS}s — assuming showcase view")
    return True


# A single OCR read can misread a bad frame and miss the available-SP text
# entirely (same reasoning as challenge.STUCK_CHECK_POLL_COUNT) — retry a
# few times before giving up and proceeding without the SP-based correction.
# 3 rather than 5: detection got noticeably more reliable once the crop was
# tightened to exclude the "Owned" row (see vision._read_available_sp), and
# the post-spend second-chance check in run_unlock_iteration (see its
# docstring) still covers the case where the pre-spend attempts never pan
# out, so there's less need to lean on this budget alone.
SP_CHECK_POLL_COUNT = 3
SP_CHECK_POLL_INTERVAL = 1


def _sp_reading_plausible(reading: int, hint: int) -> bool:
    """True if `reading` is close enough to `hint` (our own tracked estimate
    of current SP — see run_unlock_iteration's expected_sp_hint) to trust.

    A successful OCR parse isn't automatically a good one — it can misread
    most of the digits (e.g. 999 read as "10"), not just fuse the icon on as
    a trailing zero. That failure mode can't be caught by range-checking the
    reading alone (10 is a perfectly valid-looking SP value on its own), so
    this compares against context the caller already has instead. The
    tolerance is generous (not exact-match) since real per-challenge SP
    gains aren't perfectly deterministic and the hint itself is an estimate,
    not a guarantee.
    """
    tolerance = max(200, hint // 2)
    return abs(reading - hint) <= tolerance


def _fix_icon_fusion(reading: int, hint: int) -> int:
    """If the skill-point icon has fused onto `reading` as a trailing zero
    (e.g. "950" OCR'd for a real 95 — see vision._read_available_sp's
    icon-handling comments), return it stripped; otherwise return `reading`
    unchanged. Only strips when doing so lands meaningfully closer to
    `hint` than the raw reading does — a fusion that still looks plausible
    in-range on its own (950 is a perfectly valid SP value) can't be told
    apart from a genuine reading by magnitude alone, so this needs the
    caller's tracked context to disambiguate.
    """
    if reading % 10 == 0 and reading > 0:
        stripped = reading // 10
        if abs(stripped - hint) < abs(reading - hint):
            return stripped
    return reading


def _poll_sp_check(hint: int | None) -> tuple[int | None, int | None]:
    """Poll vision._read_available_sp() up to SP_CHECK_POLL_COUNT times,
    retrying a reading that doesn't match `hint` instead of accepting it
    outright (see _sp_reading_plausible) — same budget covers both "OCR
    found nothing at all" and "OCR found something implausible". Each
    reading is checked for icon fusion (_fix_icon_fusion) *before* the
    plausibility test, so a fusable-but-wildly-off-looking reading (e.g.
    "810" for a real 81) gets corrected and accepted on this same attempt
    instead of being rejected as implausible and burning through retries
    that can't help anyway (this poll's retries are against genuinely new
    frames; a value that's wrong for a structural reason like fusion won't
    fix itself just because the frame changed).

    Returns (plausible_reading, last_reading): plausible_reading is None if
    nothing plausible ever came back, even if last_reading got some number.
    Caller must check keys._stop_event after calling — a stop mid-poll
    doesn't raise, it just ends polling early (Nones both, or whatever was
    seen last).
    """
    last_reading: int | None = None
    for attempt in range(SP_CHECK_POLL_COUNT):
        reading = vision._read_available_sp()
        if reading is not None:
            if hint is not None:
                fixed = _fix_icon_fusion(reading, hint)
                if fixed != reading:
                    print(
                        f"  [SP CHECK] {reading} looks like the skill-point icon fused onto the "
                        f"number (expected ~{hint}) — using {fixed} instead"
                    )
                    reading = fixed
            last_reading = reading
            if hint is None or _sp_reading_plausible(reading, hint):
                return reading, last_reading
            print(
                f"  [SP CHECK] {reading} looks implausible (expected ~{hint}) — "
                f"retrying ({attempt + 1}/{SP_CHECK_POLL_COUNT})"
            )
        if attempt < SP_CHECK_POLL_COUNT - 1:
            keys._sleep(SP_CHECK_POLL_INTERVAL)
            if keys._stop_event.is_set():
                return None, last_reading
    return None, last_reading


def run_unlock_iteration(
    iteration, expected_cars: int | None = None, expected_sp_hint: int | None = None
) -> tuple[int | None, int | None]:
    """Unlock the wheelspin skills on one car. Uses absolute open on iter 1, relative nav after.

    On iteration 1, OCRs the skill tree and prints the SP check + comparison immediately.
    Returns (detected_sp, adjusted_effective) on iteration 1; (None, None) otherwise.

    expected_sp_hint: the caller's own best tracked estimate of current SP
    (see orchestrator._run_farm_inner) — typically ~SKILL_POINTS_CAP right
    after a challenge phase (every challenge phase in this app is sized to
    reach the cap), or the user-entered starting skill_points if no challenge
    phase has run yet this session. Used to retry a successfully-parsed but
    implausible OCR reading instead of accepting it outright, and as a
    fallback value if no attempt ever produces a plausible one.

    The SP check itself runs in two passes around UNLOCK_SEQUENCES: once
    before spending on this car, and — only if that pass never found a
    plausible reading — once more right after (the skill tree stays open
    the whole time, only closing in EXIT_TO_CAR_LIST). The second pass is a
    genuinely different screen (a real, changed Available Points count),
    not a retry against identical pixels — retrying a static, unchanging
    menu screen never produces a different result, so the pre-spend retries
    alone can't recover from a consistently wrong reading the way this can.
    """
    if iteration == 1:
        _open_cars_sorted_by_recent()
        if keys._stop_event.is_set():
            return None, None
        # Selection is already on Car1 after sort — just select it
        keys._press_key("enter")
    else:
        _open_cars_for_unlock_resume()
        if keys._stop_event.is_set():
            return None, None
        # Navigate relative to previous car. Row cycles 0→1→2→0→1→2...
        # prev_row is the row we were on after the last iteration.
        prev_row = (iteration - 2) % 3
        if prev_row < 2:
            keys.mp("down", wait=config.NAV_WAIT)  # Row 0 or 1 → move down one row
        else:
            keys.mp("right", wait=config.NAV_WAIT)  # Row 2 (bottom) → wrap to top of next column
            keys.mp("up", 2, config.NAV_WAIT)
        keys._press_key("enter")

    keys._sleep(config.MENU_WAIT)
    keys._press_key("enter")  # confirm / enter car
    if keys._stop_event.is_set():
        return None, None
    if _wait_for_car_loaded():
        keys.mp("escape")  # Exit out of showcase view
        keys._sleep(CAR_SHOWCASE_EXIT_WAIT)
    if keys._stop_event.is_set():
        return None, None
    keys._run_key_sequence(ENTER_SKILL_TREE)

    adjusted_effective: int | None = None
    detected_sp: int | None = None
    do_sp_check = iteration == 1 and expected_cars is not None
    if do_sp_check:
        detected_sp, _ = _poll_sp_check(expected_sp_hint)
        if keys._stop_event.is_set():
            return None, None

    keys._run_key_sequence(UNLOCK_SEQUENCES[config.CFG.selected_car])  # car-specific tree walk

    if do_sp_check and detected_sp is None and expected_sp_hint is not None:
        # Nothing plausible before spending on this car — the skill tree
        # (still open; EXIT_TO_CAR_LIST hasn't run yet) now shows a
        # genuinely different Available Points count, not the exact same
        # pixels the first check's retries were. Retrying against a static,
        # unchanging menu screen is pointless — confirmed in the field:
        # 5 retries in a row read the exact same wrong value, across
        # sessions with different true SP totals, meaning the retries
        # weren't giving OCR a fresh chance at anything. This is a real
        # second chance instead: adjust the hint down by one car's spend,
        # and add that same spend back onto whatever comes back.
        post_spend_hint = max(0, expected_sp_hint - config.SKILL_POINTS_PER_CAR)
        post_spend_reading, _ = _poll_sp_check(post_spend_hint)
        if keys._stop_event.is_set():
            return None, None
        if post_spend_reading is not None:
            detected_sp = post_spend_reading + config.SKILL_POINTS_PER_CAR
            print(
                f"  [SP CHECK] No plausible reading before spending, but got one after: "
                f"{post_spend_reading} + {config.SKILL_POINTS_PER_CAR} just spent = {detected_sp} before"
            )

    if do_sp_check:
        if detected_sp is None and expected_sp_hint is not None:
            # Neither check (before or after spending) found anything
            # plausible — don't act on a reading we don't trust. Fall back
            # to what we already know from tracked context (user input /
            # challenges run this session) instead of silently proceeding
            # unadjusted.
            print(
                f"  [SP CHECK] No plausible reading before or after spending on this car — "
                f"using tracked estimate ({expected_sp_hint}) instead"
            )
            detected_sp = expected_sp_hint
        if detected_sp is not None:
            # Icon-fusion correction (see _fix_icon_fusion) already happened
            # inside _poll_sp_check for both the pre- and post-spend checks
            # — the only path detected_sp can reach here without having gone
            # through it is the tracked-estimate fallback just above, which
            # doesn't need it (it's not an OCR reading). A direct call with
            # expected_sp_hint=None would also skip it, same as it always
            # has — that's a decidedly theoretical case in practice, since
            # the orchestrator always provides a hint.
            expected_sp_val = expected_cars * config.SKILL_POINTS_PER_CAR
            can_unlock = detected_sp // config.SKILL_POINTS_PER_CAR
            print(
                f"  [SP CHECK] {detected_sp} SP detected, {expected_sp_val} SP expected for {expected_cars} cars",
                end="",
            )
            if can_unlock < expected_cars:
                # Iteration 1 always spends SP unlocking THIS car regardless
                # of what the SP check finds — we're already deep in its
                # skill tree by this point, so the actual key sequence below
                # runs unconditionally either way. The effective count can
                # therefore never legitimately drop below 1: a bad OCR read
                # (or a genuinely very low SP) should reduce how many FURTHER
                # cars get unlocked, not claim iteration 1's guaranteed
                # unlock never happened.
                adjusted_effective = max(1, can_unlock)
                print(f" — adjusting unlock count from {expected_cars} to {adjusted_effective}")
            elif can_unlock > expected_cars:
                print(f" — more SP than needed for {expected_cars} cars, unlock count unchanged")
                adjusted_effective = expected_cars
            else:
                print(" ✓")
                adjusted_effective = expected_cars
            # Print challenge count adjustment immediately — before any key presses
            residual = max(0, detected_sp - adjusted_effective * config.SKILL_POINTS_PER_CAR)
            base_adj = math.ceil((config.SKILL_POINTS_CAP - residual) / config.POINTS_PER_CHALLENGE)
            new_challenges = config._buffered(base_adj)
            buf_adj = new_challenges - base_adj
            # Compared against what THIS run's own car count would have used
            # without this correction (assumed exactly at cap beforehand),
            # not the generic CHALLENGES_SUBSEQUENT (which assumes a full
            # NUM_CARS cycle) — that was comparing against a number that was
            # never actually going to apply to a smaller run like this one.
            std_challenges = config._buffered(config.challenges_to_refill(adjusted_effective))
            if new_challenges != std_challenges:
                count_txt = f"{base_adj} + {buf_adj} buffer = {new_challenges}" if buf_adj else f"{new_challenges}"
                print(
                    f"  [SP ADJUST] {residual} SP remaining after unlock — "
                    f"next challenge phase: {count_txt} challenges (was {std_challenges})"
                )
        else:
            print(
                f"  [SP CHECK] Could not read skill points from screen after {SP_CHECK_POLL_COUNT} "
                "attempts — proceeding as planned"
            )

    keys._run_key_sequence(EXIT_TO_CAR_LIST)
    return detected_sp, adjusted_effective
