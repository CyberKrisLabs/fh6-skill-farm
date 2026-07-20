"""Settings load + derived economics + user-editable wait constants.

CFG is the live settings object (see farm_settings.Settings). refresh_config()
recomputes derived economics after CFG changes; refresh_timings() applies
CFG.timings onto the wait constants below.

IMPORTANT: other modules must access the wait constants (and BUFFER_ENABLED)
via `config.NAME` — e.g. `from farm_core import config` then `config.MENU_WAIT`
— never `from farm_core.config import NAME`. refresh_timings()/refresh_config()
rebind these names at runtime (when the user saves Settings/Timings while the
GUI is already running), and a name imported directly would freeze at the
value seen at import time instead of picking up later changes.
"""

import math

import farm_settings

# ── Wait constants ─────────────────────────────────────────────────────────────
# User-editable via the Timings tab (farm_settings.TIMING_DEFAULTS / CFG.timings).
MENU_WAIT = 0.5  # Standard pause between menu navigation presses
NAV_WAIT = 0.05  # Shorter pause for up/down navigation presses
PAGE_WAIT = 2  # pageup/pagedown need more time for tab transitions to register
TYPING_WAIT = 0.2  # Pause between key presses when typing (share codes etc.)
LOADING_AFTER_CHALLENGE_EXIT_WAIT = 18  # Wait after exiting a finished challenge (Continue)
LOADING_CHALLENGE_WAIT = 25  # Wait for challenge to load from Main Menu (longer than normal loading)
LOADING_RETRY_WAIT = 25  # Wait after escape (retry challenge) until the next run is drivable
LOADING_RESET_WAIT = 20  # Wait after a pause-menu restart (failed run recovery)
# Entering a car FH6 hasn't loaded yet this session takes much longer than one
# already loaded — used when unlocking a fresh car. (Switching the active car
# away from the farm cars before removal has its own polling wait in
# farm_core.remove, since there the outcome — loaded or not — isn't known up front.)
LOADING_NON_PRELOADED_CAR_WAIT = 12
LOADING_EXIT_TO_GAME_WAIT = 9  # Wait after escaping the car menu back into free roam

# ── Configuration ──────────────────────────────────────────────────────────────
SKILL_POINTS_CAP = 999  # challenge farm target (game cap)

# Session logs (see orchestrator.run_farm) — same app-data directory as settings,
# for the same reason: must survive past a PyInstaller temp-extraction dir.
LOGS_DIR = farm_settings.APP_DATA_DIR / "logs"

# User-editable settings: selected car (price, SP cost, Car Collection
# position), challenge share code, points per challenge, multiplier-car position.
CFG = farm_settings.load()

# Derived economics — recomputed from CFG by refresh_config(); with Lambo
# defaults: 24 cars, 346,750 CR each, 8,322,000 CR/cycle, 96 challenges/cycle.
NUM_CARS = 0
CAR_PRICE_CR = 0
TOTAL_COST_CR = 0
SKILL_POINTS_PER_CAR = 0
POINTS_PER_CHALLENGE = 0
CHALLENGES_SUBSEQUENT = 0


def refresh_config() -> None:
    """Recompute derived economics from CFG. Call after changing/saving settings."""
    global NUM_CARS, CAR_PRICE_CR, TOTAL_COST_CR, SKILL_POINTS_PER_CAR
    global POINTS_PER_CHALLENGE, CHALLENGES_SUBSEQUENT
    car = CFG.car
    SKILL_POINTS_PER_CAR = car.sp_to_unlock
    NUM_CARS = SKILL_POINTS_CAP // SKILL_POINTS_PER_CAR
    CAR_PRICE_CR = car.price_cr
    TOTAL_COST_CR = NUM_CARS * CAR_PRICE_CR
    POINTS_PER_CHALLENGE = CFG.points_per_challenge
    points_used = NUM_CARS * SKILL_POINTS_PER_CAR
    carryover = SKILL_POINTS_CAP - points_used  # SP left after a full unlock cycle
    CHALLENGES_SUBSEQUENT = math.ceil((SKILL_POINTS_CAP - carryover) / POINTS_PER_CHALLENGE)


refresh_config()


def refresh_timings() -> None:
    """Apply CFG.timings overrides onto the wait constants. Call after changing/saving settings."""
    global MENU_WAIT, NAV_WAIT, PAGE_WAIT, TYPING_WAIT
    global LOADING_AFTER_CHALLENGE_EXIT_WAIT, LOADING_CHALLENGE_WAIT, LOADING_RETRY_WAIT
    global LOADING_RESET_WAIT, LOADING_NON_PRELOADED_CAR_WAIT, LOADING_EXIT_TO_GAME_WAIT
    t = CFG.timings
    MENU_WAIT = t.get("MENU_WAIT", MENU_WAIT)
    NAV_WAIT = t.get("NAV_WAIT", NAV_WAIT)
    PAGE_WAIT = t.get("PAGE_WAIT", PAGE_WAIT)
    TYPING_WAIT = t.get("TYPING_WAIT", TYPING_WAIT)
    LOADING_AFTER_CHALLENGE_EXIT_WAIT = t.get("LOADING_AFTER_CHALLENGE_EXIT_WAIT", LOADING_AFTER_CHALLENGE_EXIT_WAIT)
    LOADING_CHALLENGE_WAIT = t.get("LOADING_CHALLENGE_WAIT", LOADING_CHALLENGE_WAIT)
    LOADING_RETRY_WAIT = t.get("LOADING_RETRY_WAIT", LOADING_RETRY_WAIT)
    LOADING_RESET_WAIT = t.get("LOADING_RESET_WAIT", LOADING_RESET_WAIT)
    LOADING_NON_PRELOADED_CAR_WAIT = t.get("LOADING_NON_PRELOADED_CAR_WAIT", LOADING_NON_PRELOADED_CAR_WAIT)
    LOADING_EXIT_TO_GAME_WAIT = t.get("LOADING_EXIT_TO_GAME_WAIT", LOADING_EXIT_TO_GAME_WAIT)


refresh_timings()

# Buffer: ~4% of challenges yield fewer points than expected. Add ceil(N/25)
# extra to avoid running short. 25→+1  50→+2  75→+3  100→+4
BUFFER_ENABLED = True  # Set False (or --no-buffer) if challenges reliably hit full points.


def _buffer_extra(challenges: int) -> int:
    """Extra buffer challenges for `challenges`, regardless of BUFFER_ENABLED. Shared with farm_ui's preview."""
    return math.ceil(challenges / 25) if challenges > 0 else 0


def _buffered(challenges: int) -> int:
    """Add the extra buffer challenges on top of `challenges`, unless BUFFER_ENABLED is False."""
    if not BUFFER_ENABLED:
        return challenges
    return challenges + _buffer_extra(challenges)
