"""Phase: Remove.

Start by switching the active car to the 9x multiplier car (also doubles as
the safety step that gets off the farm cars before removing them — see
_switch_to_multiplier_car), then sort by recently added. Removing a car
causes the next one to slide into position automatically.
"""

from farm_core import config, keys, vision

# _switch_to_multiplier_car's "Get in Car" can land on either the car
# showcase view (not loaded this session) or its own menu (already loaded) —
# same fork as unlock._wait_for_car_loaded. Falls back to proceeding anyway
# after CAR_LOAD_POLL_MAX_SECONDS if neither is ever detected, rather than
# hanging — see docs/state-detection-plan.md's guidance on not trusting an
# anchor blindly.
CAR_LOAD_POLL_START_DELAY = 5  # settle time before the first check (was the old fixed wait)
CAR_LOAD_POLL_INTERVAL = 1  # poll cadence once polling starts
CAR_LOAD_POLL_MAX_SECONDS = 20  # give up after this long (assume already-loaded menu)
# Backing out of the showcase settles on the same menu the already-loaded
# case lands on directly — matches unlock.CAR_SHOWCASE_EXIT_WAIT's reasoning
# for the same transition.
CAR_SHOWCASE_EXIT_WAIT = 2


def _wait_for_multiplier_car_loaded() -> bool:
    """Poll for whichever screen shows up after "Get in Car".

    Returns True if the showcase view was detected (caller needs an extra
    escape to land on the same menu the already-loaded case reaches
    directly), False if the already-loaded menu was detected. The give-up
    case (neither ever detected) also returns False: unlike Unlock (which
    almost always processes freshly-bought, never-driven cars, so assumes
    showcase on a give-up), this is the multiplier car — driven every single
    cycle — so already-loaded is overwhelmingly the more likely true state
    here; defaulting to showcase would guess wrong most of the time.
    """
    keys._sleep(CAR_LOAD_POLL_START_DELAY)
    if keys._stop_event.is_set():
        return False
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
            return False
    print(f"  [WARN] Neither car screen detected after {CAR_LOAD_POLL_MAX_SECONDS}s — assuming already-loaded menu")
    return False


def run_remove_iteration():
    keys.mp("enter")  # Open action menu for the selected car
    keys.mp("down", 4, config.NAV_WAIT)  # Navigate to remove option
    keys.mp("enter")  # Select Remove car from garage
    keys.mp("down", wait=config.NAV_WAIT)  # Move down to "Yes" on the confirmation dialog
    keys.mp("enter")  # Confirm remove
    keys._sleep(0.5)


def _switch_to_multiplier_car() -> None:
    """Switch active car to the 9x skill-multiplier car, before the remove loop.

    Doubles as the safety step that gets the active car off of a farm car
    before removing it — previously a separate step done afterward instead
    (see git history), until it was folded into this one call: the
    multiplier car is never one of the cars being removed, so switching to
    it up front covers both jobs and removes the need to switch again once
    the remove loop finishes.

    Must be called while already at the car list in default sort order
    (before farm_core.unlock._open_cars_sorted_by_recent) — the multiplier
    car's configured Position (Settings tab) is recorded against that sort,
    not "Recently Added".

    Opens the car filter list and checks the multiplier car's Performance
    Class and Car Type (both configured in Settings — a stock Subaru 22B is
    Performance Class B / Retro Rally, but the multiplier car and its class
    aren't fixed to that one, so both are user-specific) — it's a checkbox
    list, so enter toggles a box without closing it, and both rows are
    counted as down presses from the TOP of the list (both absolute, not
    relative to each other; Performance Class is always a section above Car
    Type in the list, so its row is always the smaller of the two). The
    single escape afterward closes the filter list and applies it. Then
    navigates the filtered "My Cars" grid (3 rows per column, dynamic
    columns) to the configured car and selects it. All four positions are
    user-specific — set in settings.
    """
    print("  Switching to the 9x multiplier car...")
    # Settle time for the My Cars list to finish rendering after Unlock just
    # re-entered it — the default MENU_WAIT (0.5s) isn't enough for this
    # transition to register on a slower PC (field-confirmed: the "y" press
    # below got dropped entirely on a laptop), same reasoning as
    # unlock._open_cars_sorted_by_recent's own settle before its first press.
    keys._sleep(1)
    keys.mp("y")
    perf_row = config.CFG.filter_performance_class_row
    type_row = config.CFG.filter_car_type_row
    if perf_row:
        keys.mp("down", perf_row, config.NAV_WAIT)
    keys.mp("enter")  # check performance class
    if type_row > perf_row:
        keys.mp("down", type_row - perf_row, config.NAV_WAIT)
    keys.mp("enter")  # check car type
    keys.mp("escape", wait=config.MENU_WAIT)  # close filter list, apply

    if config.CFG.multiplier_car_col:
        keys.mp("right", config.CFG.multiplier_car_col, config.NAV_WAIT)
    if config.CFG.multiplier_car_row:
        keys.mp("down", config.CFG.multiplier_car_row, config.NAV_WAIT)
    keys.mp("enter")  # Open action menu for the selected car
    keys.mp("enter")  # Get in Car
    if _wait_for_multiplier_car_loaded():
        keys.mp("escape")  # Exit out of showcase view
        keys._sleep(CAR_SHOWCASE_EXIT_WAIT)
