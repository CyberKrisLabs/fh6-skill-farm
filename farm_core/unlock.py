"""Phase: Unlock.

Start at the full car collection list. Unlocks the wheelspin skills on one
car per iteration.

Steps are (key, press_count) executed via keys.mp(); ("wait", seconds) pauses.
Arrow keys use config.NAV_WAIT, everything else the default (config.MENU_WAIT).
"""

import math

from farm_core import config, keys, vision

# Entering the skill tree is identical for every car: from inside the car
# (post-loading) to the skill tree, ready for the SP OCR check.
ENTER_SKILL_TREE = [
    ("escape", 1),  # Exit out of showcase view
    ("wait", 1),
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


# A single OCR read can misread a bad frame and miss the available-SP text
# entirely (same reasoning as challenge.STUCK_CHECK_POLL_COUNT) — retry a
# few times before giving up and proceeding without the SP-based correction.
SP_CHECK_POLL_COUNT = 3
SP_CHECK_POLL_INTERVAL = 1


def run_unlock_iteration(iteration, expected_cars: int | None = None) -> tuple[int | None, int | None]:
    """Unlock the wheelspin skills on one car. Uses absolute open on iter 1, relative nav after.

    On iteration 1, OCRs the skill tree and prints the SP check + comparison immediately.
    Returns (detected_sp, adjusted_effective) on iteration 1; (None, None) otherwise.
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
    keys._sleep(config.LOADING_NON_PRELOADED_CAR_WAIT)
    if keys._stop_event.is_set():
        return None, None
    keys._run_key_sequence(ENTER_SKILL_TREE)

    adjusted_effective: int | None = None
    detected_sp: int | None = None
    if iteration == 1 and expected_cars is not None:
        for attempt in range(SP_CHECK_POLL_COUNT):
            detected_sp = vision._read_available_sp()
            if detected_sp is not None:
                break
            if attempt < SP_CHECK_POLL_COUNT - 1:
                keys._sleep(SP_CHECK_POLL_INTERVAL)
                if keys._stop_event.is_set():
                    return None, None
        if detected_sp is not None:
            can_unlock = detected_sp // config.SKILL_POINTS_PER_CAR
            expected_sp_val = expected_cars * config.SKILL_POINTS_PER_CAR
            print(
                f"  [SP CHECK] {detected_sp} SP detected, {expected_sp_val} SP expected for {expected_cars} cars",
                end="",
            )
            if can_unlock < expected_cars:
                print(f" — adjusting unlock count from {expected_cars} to {can_unlock}")
                adjusted_effective = can_unlock
            elif can_unlock > expected_cars:
                print(" — more SP than planned, unlock count unchanged")
                adjusted_effective = expected_cars
            else:
                print(" ✓")
                adjusted_effective = expected_cars
            # Print challenge count adjustment immediately — before any key presses
            residual = max(0, detected_sp - adjusted_effective * config.SKILL_POINTS_PER_CAR)
            base_adj = math.ceil((config.SKILL_POINTS_CAP - residual) / config.POINTS_PER_CHALLENGE)
            new_challenges = config._buffered(base_adj)
            buf_adj = new_challenges - base_adj
            std_challenges = config._buffered(config.CHALLENGES_SUBSEQUENT)
            if new_challenges != std_challenges:
                _buf_txt = f" + {buf_adj} buffer" if config.BUFFER_ENABLED else ""
                print(
                    f"  [SP ADJUST] {residual} SP remaining after unlock — "
                    f"next challenge phase: {base_adj}{_buf_txt} = {new_challenges} challenges (was {std_challenges})"
                )
        else:
            print(
                f"  [SP CHECK] Could not read skill points from screen after {SP_CHECK_POLL_COUNT} "
                "attempts — proceeding as planned"
            )

    keys._run_key_sequence(UNLOCK_SEQUENCES[config.CFG.selected_car])  # car-specific tree walk
    keys._run_key_sequence(EXIT_TO_CAR_LIST)
    return detected_sp, adjusted_effective
