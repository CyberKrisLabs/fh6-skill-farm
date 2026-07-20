"""Command-line entry point. Run via the root skill_farm.py launcher:

python skill_farm.py --start challenge                    # farm skill points (infinite)
python skill_farm.py --start challenge --skill-points 500 # farm from 500 to ~999
python skill_farm.py --start buy                          # buy → unlock → remove
python skill_farm.py --start unlock                       # unlock → remove
python skill_farm.py --start remove                       # just remove
"""

import argparse
import sys

import pyautogui

from farm_core import config, keys, orchestrator


def main():
    car = config.CFG.car
    parser = argparse.ArgumentParser(
        description=f"{car.name} skill farm — Wheelspin grind via challenges",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(
            [
                "Phases run in sequence from --start onward:",
                "  main      → navigate from the main menu to challenge, then full flow",
                f"  challenge → farm skill points via challenge (share code: {config.CFG.challenge_share_code})",
                f"  buy       → buy {config.NUM_CARS} × {car.name} ({config.TOTAL_COST_CR:,} CR total)",
                f"  unlock    → unlock the wheelspin skills on each car ({config.SKILL_POINTS_PER_CAR} pts/car, "
                f"{car.super_wheelspins} SWS + {car.wheelspins} WS)",
                "  remove    → remove all unlocked cars",
                "",
                "Car / share code / grid positions: skill_farm_settings.json (GUI Settings tab).",
            ]
        ),
    )
    parser.add_argument(
        "--start",
        choices=["main"] + orchestrator.PHASES,
        default="buy",
        help="Phase to begin from; later phases run automatically (default: buy)",
    )
    parser.add_argument(
        "--skill-points",
        "-s",
        type=int,
        default=0,
        metavar="N",
        help=f"Your current skill points (0–{config.SKILL_POINTS_CAP}). "
        f"Always controls how many challenges to run when the challenge phase is reached "
        f"({config.POINTS_PER_CHALLENGE} pts/challenge). "
        f"Also controls how many cars to buy when starting from buy "
        f"(pts ÷ {config.SKILL_POINTS_PER_CAR}). "
        f"When starting from unlock or remove, use --cars for the car count "
        f"and --skill-points for the eventual challenge phase.",
    )
    parser.add_argument(
        "--cars",
        type=int,
        default=-1,
        metavar="N",
        help=f"When starting from buy: how many to buy this run (omit = all from --skill-points; 0 = skip buying). "
        f"When starting from unlock or remove: how many cars to process. Max {config.NUM_CARS}.",
    )
    parser.add_argument(
        "--cr",
        type=int,
        default=0,
        metavar="N",
        help="Your current Credits (CR). In cycle mode, limits buy phases to what you can afford; "
        "when CR is exhausted runs final challenges to cap skill points then stops. 0 = unlimited.",
    )
    parser.add_argument(
        "--cycle",
        action="store_true",
        help="Repeat the full flow indefinitely. Cycle 1 respects --start and --skill-points; "
        f"cycle 2+ always runs {config.CHALLENGES_SUBSEQUENT} challenges (carryover SP accounted for).",
    )
    parser.add_argument(
        "--countdown",
        "-c",
        type=int,
        default=5,
        help="Seconds to wait before starting (default: 5)",
    )
    parser.add_argument(
        "--no-buffer",
        action="store_true",
        help="Disable the extra buffer challenges normally added to offset runs that yield fewer points.",
    )
    args = parser.parse_args()

    config.BUFFER_ENABLED = not args.no_buffer

    start_idx = orchestrator.PHASES.index(args.start)
    phases_to_run = orchestrator.PHASES[start_idx:]

    # Determine how many cars to buy/unlock/remove this run.
    # Priority: --cars (direct) > --skill-points on buy (derived) > default (NUM_CARS)
    if args.cars > 0:
        cars_this_run = min(args.cars, config.NUM_CARS)
    elif args.start == "buy" and args.skill_points > 0:
        cars_this_run = min(args.skill_points // config.SKILL_POINTS_PER_CAR, config.NUM_CARS)
    else:
        cars_this_run = config.NUM_CARS

    print(f"Skill farm — starting from '{args.start}'" + (" [cycle mode]" if args.cycle else ""))
    print(f"Sequence: {' → '.join(phases_to_run)}")
    if args.cars > 0:
        print(f"Cars this run: {cars_this_run} (--cars)")
    elif args.start == "buy" and args.skill_points > 0:
        print(f"Cars this run: {cars_this_run} ({args.skill_points} pts ÷ {config.SKILL_POINTS_PER_CAR})")
    if not args.cycle and "challenge" in phases_to_run and args.skill_points == 0:
        print("Note: challenge loops forever — Ctrl+C stops script (won't auto-advance to buy).")
    # Countdown runs exactly once — switch to the game now.
    # Once the loop is running the game is already in focus; no further countdowns.
    print(f"\nSwitch to the game — starting in {args.countdown}s. Move mouse to a corner to stop.")

    try:
        for i in range(args.countdown, 0, -1):
            print(i, end="... ", flush=True)
            keys._sleep(1)
        print("GO")

        keys._stop_event.clear()
        orchestrator.run_farm(
            args.start, args.skill_points, args.cars, getattr(args, "cars_have", 0), args.cr, args.cycle
        )

    except KeyboardInterrupt:
        print("\nInterrupted. Exiting.")
        sys.exit(0)
    except pyautogui.FailSafeException:
        print("\nFail-safe triggered (mouse moved to corner). Exiting.")
        sys.exit(0)
