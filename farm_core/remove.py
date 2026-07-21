"""Phase: Remove.

Start positioned at car 1 (most recently added) after sorting by recently
added. Removing a car causes the next one to slide into position automatically.
"""

from farm_core import config, keys, vision

# _select_non_farm_car_as_active can't know in advance whether the car it
# switches to is already loaded, so it polls for whichever screen shows up
# instead of guessing a fixed wait.
CAR_SWITCH_POLL_START_DELAY = 5  # settle time before the first check
CAR_SWITCH_POLL_INTERVAL = 1  # poll cadence once polling starts
CAR_SWITCH_POLL_MAX_SECONDS = 20  # give up after this long (assume already-loaded menu)
# Backing out of the showcase lands on the Cars hub tab bar, one level above
# My Cars — the default MENU_WAIT between escape and the next enter wasn't
# enough for that transition to settle, so it needs its own longer wait.
CAR_SHOWCASE_EXIT_WAIT = 2


def run_remove_iteration():
    keys.mp("enter")  # Open action menu for the selected car
    keys.mp("down", 4, config.NAV_WAIT)  # Navigate to remove option
    keys.mp("enter")  # Select Remove car from garage
    keys.mp("down", wait=config.NAV_WAIT)  # Move down to "Yes" on the confirmation dialog
    keys.mp("enter")  # Confirm remove
    keys._sleep(0.5)


def _select_non_farm_car_as_active() -> None:
    """Switch active car away from the farm cars before the remove loop.

    Must be called while already at the car list in default sort order (before
    farm_core.unlock._open_cars_sorted_by_recent), so that right navigates to
    a non-farm car.
    """
    print("  [Safety] Switching to a non-farm car to avoid trying to remove an active car")
    keys._sleep(1)
    if keys._stop_event.is_set():
        return
    keys.mp("right", wait=config.NAV_WAIT)
    keys.mp("enter")
    keys.mp("enter")

    print(f"  [Safety] Waiting {CAR_SWITCH_POLL_START_DELAY}s, then polling for which screen loads...")
    keys._sleep(CAR_SWITCH_POLL_START_DELAY)
    if keys._stop_event.is_set():
        return

    is_showcase = False
    detected = False
    elapsed = CAR_SWITCH_POLL_START_DELAY
    while elapsed < CAR_SWITCH_POLL_MAX_SECONDS:
        buttons = vision._read_car_screen_buttons()
        if any(kw in buttons for kw in vision.CAR_SHOWCASE_KEYWORDS):
            is_showcase = True
            detected = True
            break
        if any(kw in buttons for kw in vision.CAR_LOADED_MENU_KEYWORDS):
            detected = True
            break
        keys._sleep(CAR_SWITCH_POLL_INTERVAL)
        elapsed += CAR_SWITCH_POLL_INTERVAL
        if keys._stop_event.is_set():
            return

    if not detected:
        print(f"  [WARN] Neither screen detected after {CAR_SWITCH_POLL_MAX_SECONDS}s — assuming already-loaded menu")
    elif is_showcase:
        print(f"  [Safety] Car hasn't been loaded before ({elapsed}s) — backing out of the showcase screen")
        keys.mp("escape")
        keys._sleep(CAR_SHOWCASE_EXIT_WAIT)
    keys.mp("enter")


def _switch_to_multiplier_car() -> None:
    """Switch active car to the 9x skill-multiplier car after the remove loop.

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
    keys.mp("enter", wait=5)  # Get in Car, then wait for the "Car" tab menu to load
