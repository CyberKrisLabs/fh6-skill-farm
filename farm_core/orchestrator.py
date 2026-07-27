"""Phase orchestration: run_phase, the transitions registry, and run_farm/_run_farm_inner.

Ties together farm_core.challenge/buy/unlock/remove into the full cycle.
"""

import datetime
import math
import sys
import threading
import types

from farm_core import buy, challenge, config, keys, remove, unlock

# Callable hook set by GUI before starting the farm, cleared when done.
# Signature: (base_challenges: int, buffered_challenges: int) -> None
challenge_adjusted_hook = None

# Callable hook set by GUI before starting the farm, cleared when done.
# Signature: (phase: str, current: int, total: int, cycle: int) -> None
# Fired once per phase-iteration (e.g. "Challenge 5/98") so a live UI (the
# in-game overlay) can show progress without scraping log text. total is 0
# for the "run until interrupted" challenge-only path, where there's no fixed
# count to report.
phase_progress_hook = None

# Current cycle number, for phase_progress_hook — reset at the start of every
# run_farm() call and updated at the top of each cycle-mode loop iteration.
_current_cycle = 1


def _report_progress(phase: str, current: int, total: int) -> None:
    if phase_progress_hook:
        phase_progress_hook(phase, current, total, _current_cycle)


# ── Transitions registry ───────────────────────────────────────────────────────
# Maps each phase to the function that navigates there from the previous phase.
# Transitions are only called in cycle mode, never on the first action.
# Add entries here as remaining transitions are defined.

TRANSITIONS = {
    "challenge": challenge.transition_to_challenge,
    "buy": buy.transition_to_buy,
    "unlock": unlock.transition_to_unlock,
}

PHASES = ["challenge", "buy", "unlock", "remove"]

# Settle time after escaping the My Cars list at the end of the Remove phase —
# the default MENU_WAIT (0.5s) isn't enough for this transition to register,
# same reasoning as unlock.CAR_SHOWCASE_EXIT_WAIT for a similar list-closing step.
CAR_LIST_EXIT_WAIT = 2


def _exit_remove_phase_to_game() -> None:
    """Shared tail for both the full Remove loop and the skip-remove path:
    back out of the car list into Free Roam, then reopen the Main Menu for
    the next transition.
    """
    if keys._stop_event.is_set():
        return
    keys.mp("escape", wait=CAR_LIST_EXIT_WAIT)  # Escape out of the car list (My Cars)
    keys.mp("escape")  # Escape out of the car menu to return to the game
    challenge._wait_for_drivable(
        challenge.DRIVABLE_POLL_START_DELAY_SHORT, config.LOADING_EXIT_TO_GAME_WAIT, "remove exit"
    )
    print("  Navigating back to main menu...")
    keys.mp("escape")  # Escape to open the Main Menu


def run_phase(name, args, challenge_iters=None, num_cars=None, expected_sp_hint=None, skip_remove=False):
    if num_cars is None:
        num_cars = config.NUM_CARS
    if name == "challenge":
        if challenge_iters is not None:
            if config.BUFFER_ENABLED:
                _buf = math.ceil(challenge_iters / 26)
                print(
                    f"Phase: CHALLENGE — {challenge_iters - _buf} challenges + {_buf} buffer = {challenge_iters} total"
                )
            else:
                print(f"Phase: CHALLENGE — {challenge_iters} challenges (buffer disabled)")
            completed = 0
            while completed < challenge_iters and not keys._stop_event.is_set():
                _label = f"{completed + 1}/{challenge_iters}"
                print(f"  Challenge {_label}")
                _report_progress("challenge", completed + 1, challenge_iters)
                success = challenge.run_challenge_iteration(final=completed + 1 == challenge_iters, label=_label)
                if success:
                    completed += 1
                else:
                    print("  [RESET] Challenge not counted — retrying")
        elif args.skill_points > 0:
            needed = config.SKILL_POINTS_CAP - args.skill_points
            iterations = math.ceil(needed / config.POINTS_PER_CHALLENGE)
            print(
                f"Phase: CHALLENGE — {args.skill_points} pts already, "
                f"{iterations} challenges to reach {config.SKILL_POINTS_CAP}"
            )
            completed = 0
            while completed < iterations and not keys._stop_event.is_set():
                _label = f"{completed + 1}/{iterations}"
                print(f"  Challenge {_label}")
                _report_progress("challenge", completed + 1, iterations)
                success = challenge.run_challenge_iteration(final=completed + 1 == iterations, label=_label)
                if success:
                    completed += 1
                else:
                    print("  [RESET] Challenge not counted — retrying")
        else:
            print("Phase: CHALLENGE — running until interrupted (Ctrl+C to stop).")
            i = 0
            while not keys._stop_event.is_set():
                i += 1
                print(f"  Challenge {i}")
                _report_progress("challenge", i, 0)
                success = challenge.run_challenge_iteration(label=str(i))
                if not success:
                    print("  [RESET] Challenge not counted")
                    i -= 1

    elif name == "buy":
        cost = num_cars * config.CAR_PRICE_CR
        print(f"Phase: BUY — {num_cars} × {config.CFG.car.name} ({cost:,} CR total)")
        for i in range(1, num_cars + 1):
            if keys._stop_event.is_set():
                break
            print(f"  Buy {i}/{num_cars}")
            _report_progress("buy", i, num_cars)
            buy.run_buy_iteration()

    elif name == "unlock":
        print(f"Phase: UNLOCK — wheelspin skills on {num_cars} cars")
        effective = num_cars
        _ocr_sp = None
        i = 0
        while i < effective and not keys._stop_event.is_set():
            i += 1
            print(f"  Unlock {i}/{effective}")
            _report_progress("unlock", i, effective)
            detected_sp, adjusted = unlock.run_unlock_iteration(
                i,
                expected_cars=effective if i == 1 else None,
                expected_sp_hint=expected_sp_hint if i == 1 else None,
            )
            if i == 1:
                _ocr_sp = detected_sp
                if adjusted is not None:
                    effective = adjusted
        return _ocr_sp, effective

    elif name == "remove":
        if skip_remove:
            print("Phase: REMOVE — skipped (Skip Remove in Cycle enabled), switching to 9x multiplier car")
            _report_progress("remove", 1, 1)
            remove._switch_to_multiplier_car()
            _exit_remove_phase_to_game()
        else:
            print(f"Phase: REMOVE — removing {num_cars} cars")
            remove._switch_to_multiplier_car()
            keys.mp("enter")  # Back into the car list (My Cars), not the game — remove loop runs here
            unlock._open_cars_sorted_by_recent()
            for i in range(1, num_cars + 1):
                if keys._stop_event.is_set():
                    break
                print(f"  Remove {i}/{num_cars}")
                _report_progress("remove", i, num_cars)
                remove.run_remove_iteration()
            _exit_remove_phase_to_game()


class _Tee:
    """Write to both the original stdout and a log file, prepending timestamps per line."""

    def __init__(self, file):
        self._file = file
        self._stdout = sys.stdout
        self._at_line_start = True

    def write(self, data: str) -> None:
        if not data:
            return
        out = []
        for ch in data:
            if self._at_line_start and ch != "\n":
                out.append(datetime.datetime.now().strftime("[%H:%M:%S] "))
                self._at_line_start = False
            out.append(ch)
            if ch == "\n":
                self._at_line_start = True
        text = "".join(out)
        self._stdout.write(text)
        self._file.write(text)

    def flush(self):
        self._stdout.flush()
        self._file.flush()

    def fileno(self):
        return self._stdout.fileno()


def run_farm(
    start: str,
    skill_points: int = 0,
    cars: int = -1,
    cars_have: int = 0,
    cr: int = 0,
    cycle: bool = False,
    challenge_only: bool = False,
) -> None:
    """Run the farm. Blocks until complete or keys._stop_event is set.
    Called by farm_core.cli.main() (CLI) and farm_ui (GUI) alike.
    The caller must clear keys._stop_event before calling.

    cars:
      start="buy":           how many to buy this run (0 = all from skill_points).
      start="unlock"/"remove": how many cars to process (0 = NUM_CARS).
    cars_have (buy start only): farm cars already owned before this run.
      unlock_count = cars_to_buy + cars_have  (you unlock everything you have).
    cr: total Credits available. 0 = unlimited. Caps buy phases in cycle mode.
    challenge_only: run the challenge phase alone, bounded by skill_points
      (same as a normal cycle's first run — enough to reach ~999 SP), and
      never transition to buy/unlock/remove — for users who only want the
      challenge grind, without needing the Car Collection Row/Column
      configured. start must be "main" or "challenge".
    """
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = config.LOGS_DIR / f"{timestamp}.txt"
    _orig_stdout = sys.stdout
    _log_file = open(log_path, "w", encoding="utf-8", buffering=1)
    sys.stdout = _Tee(_log_file)
    print(
        f"=== Session started {timestamp} | start={start} sp={skill_points} cars={cars} "
        f"have={cars_have} cr={cr} cycle={cycle} ==="
    )
    wd = threading.Thread(target=keys._watchdog_thread, daemon=True, name="fh6-watchdog")
    wd.start()
    try:
        _run_farm_inner(start, skill_points, cars, cars_have, cr, cycle, challenge_only)
    finally:
        print(f"=== Session ended {datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')} ===")
        sys.stdout = _orig_stdout
        _log_file.close()


def _run_farm_inner(
    start: str, skill_points: int, cars: int, cars_have: int, cr: int, cycle: bool, challenge_only: bool = False
) -> None:
    global _current_cycle
    _current_cycle = 1
    if challenge_only:
        if start == "main":
            print("Navigating to challenge from main menu...")
            challenge.transition_to_challenge()
        # No car ever gets bought/unlocked in this mode, so cr/cycle don't
        # apply — but it still runs a bounded count computed from
        # skill_points (same formula as the normal cycle's first run), so it
        # stops once SP hits ~999 instead of looping forever uncontrolled.
        if skill_points <= 0:
            iters = config._buffered(math.ceil(config.SKILL_POINTS_CAP / config.POINTS_PER_CHALLENGE))
        else:
            iters = config._buffered(math.ceil((config.SKILL_POINTS_CAP - skill_points) / config.POINTS_PER_CHALLENGE))
        run_phase(
            "challenge",
            types.SimpleNamespace(skill_points=skill_points, cars=cars, cycle=False),
            challenge_iters=iters,
        )
        if not keys._stop_event.is_set():
            print("Challenge Only run complete.")
        return

    if start == "main":
        print("Navigating to challenge from main menu...")
        challenge.transition_to_challenge()
        start = "challenge"

    start_idx = PHASES.index(start)
    phases_to_run = PHASES[start_idx:]

    if start in ("unlock", "remove"):
        buy_count = 0
        unlock_count = cars if cars > 0 else config.NUM_CARS
        sp_spent_unlocking = unlock_count * config.SKILL_POINTS_PER_CAR if start == "unlock" else 0
        sp_before_race = max(0, skill_points - sp_spent_unlocking)
    elif start == "buy":
        total_from_sp = (
            min(skill_points // config.SKILL_POINTS_PER_CAR, config.NUM_CARS) if skill_points > 0 else config.NUM_CARS
        )
        # cars=-1 means "not specified" → use all from SP; cars=0 means "skip buying" (explicit)
        buy_count = total_from_sp if cars < 0 else min(cars, total_from_sp)
        # Cap unlock count by SP actually available
        max_unlockable = (skill_points // config.SKILL_POINTS_PER_CAR) if skill_points > 0 else config.NUM_CARS
        unlock_count = min(buy_count + cars_have, config.NUM_CARS, max_unlockable)
        sp_before_race = skill_points - unlock_count * config.SKILL_POINTS_PER_CAR
    else:  # challenge
        # By the time Buy runs, the preceding challenge phase has already
        # capped skill points (~999), so SP is never the binding constraint
        # here — CR is. Without this, the first buy always attempted the
        # full NUM_CARS regardless of affordability (0 = unlimited CR keeps
        # the full count).
        buy_count = min(cr // config.CAR_PRICE_CR, config.NUM_CARS) if cr > 0 else config.NUM_CARS
        unlock_count = buy_count
        sp_before_race = skill_points

    # First-challenge count adjusted for SP actually remaining after unlock
    if sp_before_race <= 0:
        challenge_iters_first = config._buffered(math.ceil(config.SKILL_POINTS_CAP / config.POINTS_PER_CHALLENGE))
    else:
        challenge_iters_first = config._buffered(
            math.ceil((config.SKILL_POINTS_CAP - sp_before_race) / config.POINTS_PER_CHALLENGE)
        )

    # CR remaining, updated after every cycle's buy (0 = unlimited, tracked as
    # None) — including cycle 1's, subtracted once below by the loop's own
    # post-cycle bookkeeping, not pre-subtracted here too. Each subsequent
    # cycle spends whatever of this is left, capped at NUM_CARS — not "a full
    # NUM_CARS-cycle's cost or nothing" — so e.g. 18M CR after a 9.1M-CR first
    # cycle still buys another ~24 cars on cycle 2, instead of stopping just
    # because a second *full* 25-car cycle (9.1M+) doesn't fit.
    remaining_cr = cr if cr > 0 else None

    args = types.SimpleNamespace(skill_points=skill_points, cars=cars, cycle=cycle)

    def _n(phase, b, u):
        return b if phase == "buy" else u

    if cycle:
        cyc = 0
        first_challenge = True
        is_first_action = True
        _override_challenge_iters = None  # set by unlock OCR when challenges haven't run yet
        # Cars actually unlocked in the most recently completed cycle — used to
        # size the NEXT challenge phase's refill target (see challenges_to_refill).
        # Starts at unlock_count (cycle 1's planned count) since cycle 1 always
        # runs before any "else" branch can be reached.
        last_unlock_count = unlock_count

        while not keys._stop_event.is_set():
            cyc += 1
            _current_cycle = cyc
            is_final = False

            if cyc == 1 and start == "challenge" and remaining_cr is not None and buy_count == 0:
                # Same treatment as the "CR exhausted mid-cycle" branch below, but for CR that
                # was ALREADY insufficient for even one car before cycle 1 even started (only
                # the "else: # challenge" branch above computes buy_count from cr — this can't
                # fire for a buy/unlock/remove start, whose counts come from skill_points/cars
                # instead). Without this, cycle 1 always ran the full phase set regardless,
                # navigating through real Buy/Unlock/Remove transitions for phases that would
                # do nothing (0 cars bought/unlocked/removed) — confirmed in the field with
                # cr=500 (below any real car's price): "Phase: BUY — 0 x ... (0 CR total)" still
                # ran a real in-game transition into Car Collection for zero purchases.
                phases_this_cycle = ["challenge"]
                b, u = 0, config.NUM_CARS
                is_final = True
                print("\nCR insufficient to buy even one car — running challenges only, then stopping.")
            elif cyc == 1:
                phases_this_cycle = phases_to_run
                b, u = buy_count, unlock_count
            elif remaining_cr is not None and remaining_cr < config.CAR_PRICE_CR:
                # Can't even afford one more car — run challenges once more to
                # cap skill points, then stop.
                phases_this_cycle = ["challenge"]
                b, u = 0, config.NUM_CARS
                is_final = True
                print("\nCR exhausted — running final challenges to cap skill points, then stopping.")
            else:
                # Spend as much of whatever CR remains as this cycle can
                # afford — a partial cycle (fewer than NUM_CARS) rather than
                # needing a full cycle's cost to run at all.
                next_buy = (
                    config.NUM_CARS
                    if remaining_cr is None
                    else min(remaining_cr // config.CAR_PRICE_CR, config.NUM_CARS)
                )
                phases_this_cycle = PHASES
                b, u = next_buy, next_buy

            print(f"\n{'=' * 50}\nCycle {cyc}{' (final)' if is_final else ''}\n{'=' * 50}")

            # Best tracked estimate of current SP, for Unlock's SP-check
            # plausibility test (see unlock.run_unlock_iteration). Every
            # challenge phase in this app is sized to bring SP up to the
            # cap, so if one is scheduled this cycle before unlock runs,
            # SP should be at/near SKILL_POINTS_CAP by the time we get
            # there; otherwise (a Buy/Unlock/Remove start whose first cycle
            # skips straight past challenge) nothing has touched SP yet, so
            # the user's own entered starting value is the best estimate.
            expected_sp_hint = config.SKILL_POINTS_CAP if "challenge" in phases_this_cycle else skill_points

            for phase in phases_this_cycle:
                if keys._stop_event.is_set():
                    break
                if phase == "challenge":
                    if _override_challenge_iters is not None:
                        ci = _override_challenge_iters
                        _override_challenge_iters = None
                    elif first_challenge:
                        ci = challenge_iters_first
                    else:
                        # Sized to how many cars the last cycle actually
                        # unlocked, not CHALLENGES_SUBSEQUENT's assumed full
                        # NUM_CARS — a CR-limited partial cycle (or the "CR
                        # exhausted" top-up below) needs far fewer refill
                        # challenges than a full cycle would.
                        ci = config._buffered(config.challenges_to_refill(last_unlock_count))
                    if first_challenge:
                        first_challenge = False
                    if ci <= 0:
                        # Computed before navigating anywhere — no point
                        # entering a challenge just to immediately back out
                        # of it with zero runs.
                        print("Skipping challenge phase — 0 challenges needed.")
                    else:
                        if not is_first_action and phase in TRANSITIONS:
                            print(f"Transition: navigating to {phase}...")
                            TRANSITIONS[phase]()
                        run_phase(phase, args, challenge_iters=ci, num_cars=u)
                elif phase == "unlock":
                    if not is_first_action and phase in TRANSITIONS:
                        print(f"Transition: navigating to {phase}...")
                        TRANSITIONS[phase]()
                    phase_result = run_phase(phase, args, num_cars=_n(phase, b, u), expected_sp_hint=expected_sp_hint)
                    if phase_result is not None:
                        ocr_sp, effective_unlocked = phase_result
                        last_unlock_count = effective_unlocked
                        # Remove runs right after, this same cycle — point it
                        # at how many cars actually got unlocked, not the
                        # original plan, so a car that never got its
                        # wheelspins claimed (SP fell short mid-cycle) isn't
                        # scrapped for nothing along with the ones that did.
                        u = effective_unlocked
                        # Use detected SP to correct the upcoming challenge count
                        # every time Unlock's check reads it, not just the
                        # session's first check — challenges_to_refill()
                        # (used below when this doesn't fire, e.g. a
                        # challenge-only top-up cycle with no unlock in it)
                        # only knows how many cars were unlocked, not whether
                        # SP actually reached the cap beforehand; residual
                        # here is exact, computed from what was actually
                        # read/tracked this check.
                        if ocr_sp is not None:
                            residual = max(0, ocr_sp - effective_unlocked * config.SKILL_POINTS_PER_CAR)
                            base_adj = math.ceil((config.SKILL_POINTS_CAP - residual) / config.POINTS_PER_CHALLENGE)
                            adjusted = config._buffered(base_adj)
                            _override_challenge_iters = adjusted
                            if challenge_adjusted_hook:
                                challenge_adjusted_hook(base_adj, adjusted)
                else:
                    if not is_first_action and phase in TRANSITIONS:
                        print(f"Transition: navigating to {phase}...")
                        TRANSITIONS[phase]()
                    # Skip only applies to the automatic cycle's own remove
                    # step — an explicit "Start From: Remove" (cyc 1) still
                    # actually removes regardless of the setting.
                    skip_remove = (
                        phase == "remove" and config.CFG.skip_remove_in_cycle and not (start == "remove" and cyc == 1)
                    )
                    run_phase(phase, args, num_cars=_n(phase, b, u), skip_remove=skip_remove)
                is_first_action = False

            if "buy" in phases_this_cycle and remaining_cr is not None:
                remaining_cr -= b * config.CAR_PRICE_CR

            if is_final:
                break

    else:
        is_first_action = True
        expected_sp_hint = config.SKILL_POINTS_CAP if "challenge" in phases_to_run else skill_points
        for phase in phases_to_run:
            if keys._stop_event.is_set():
                break
            if not is_first_action and phase in TRANSITIONS:
                print(f"Transition: navigating to {phase}...")
                TRANSITIONS[phase]()
            # Same exception as the cycle-mode dispatch above: an explicit
            # "Start From: Remove" still actually removes regardless of the
            # setting — only a remove reached naturally from another start
            # point is skipped.
            skip_remove = phase == "remove" and config.CFG.skip_remove_in_cycle and start != "remove"
            run_phase(
                phase,
                args,
                num_cars=_n(phase, buy_count, unlock_count),
                expected_sp_hint=expected_sp_hint,
                skip_remove=skip_remove,
            )
            is_first_action = False
        if not keys._stop_event.is_set():
            print("All phases complete.")
