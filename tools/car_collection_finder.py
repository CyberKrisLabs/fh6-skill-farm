"""Standalone CLI wrapper around farm_core.car_collection_finder.find_car() — given a
target car (--car lambo / --car viper), this drives the actual in-game
navigation (Backspace -> Manufacturers list -> jump -> local scan) and
prints the exact key-press sequence it took to reach it, instead of you
doing the navigating.

PRECONDITION: Car Collection must already be open in-game (the main grid,
cursor anywhere) before running this.

This is a first working prototype of the Option B approach from
docs/car-position-autodetect-plan.md: rather than computing an absolute
row/column (the game never displays one anywhere), it records the literal
navigation it performed. See that doc for why an absolute count isn't
recoverable once a manufacturer jump is involved, and see
farm_core/car_collection_finder.py for the actual search logic (shared with the Setup
Wizard's "Find Automatically" button) — this script only owns the
CLI-specific bits: argument parsing, the initial confirmation prompt, and
the pre-search countdown.

Usage:
    python tools/car_collection_finder.py --car lambo
    python tools/car_collection_finder.py --car viper --yes      # skip the initial confirmation prompt
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for farm_core/farm_settings imports

import farm_settings  # noqa: E402
from farm_core import car_collection_finder, keys  # noqa: E402
from farm_core.vision import _winrt_available  # noqa: E402


def _resolve_target(car_arg: str) -> dict:
    """Loosely match --car against CAR_CATALOG's car_id/name/model (case-insensitive
    substring) — CAR_CATALOG is the single source of truth for manufacturer/model/year,
    not a separate list here."""
    key = car_arg.strip().upper()
    for info in farm_settings.CAR_CATALOG.values():
        if key in info.car_id.upper() or key in info.name.upper() or key in info.model.upper():
            return {"manufacturer": info.manufacturer, "model": info.model, "year": info.year}
    known = ", ".join(sorted(info.car_id for info in farm_settings.CAR_CATALOG.values()))
    raise SystemExit(f"Unknown --car {car_arg!r}. Known: {known}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--car", required=True, help="a car_id, name, or model substring from farm_settings.CAR_CATALOG"
    )
    parser.add_argument("--yes", "-y", action="store_true", help="skip the initial confirmation prompt")
    args = parser.parse_args()

    if not _winrt_available():
        raise SystemExit("[ERROR] WinRT OCR is unavailable on this machine.")

    target = _resolve_target(args.car)

    if not args.yes:
        input(
            f"About to search for {target['manufacturer']} {target['model']} ({target['year']}). "
            "Make sure Car Collection is already open in FH6, then press Enter here..."
        )
    print("Switching to FH6 in 3 seconds — alt-tab now if you haven't already...")
    time.sleep(3)

    if not keys._fh6_focused():
        raise SystemExit("[ERROR] FH6 is not the focused window — switch to it and try again.")

    try:
        result = car_collection_finder.find_car(target, log=print)
    except KeyboardInterrupt:
        print("\nStopped.")
        return

    print("\n=== Result ===")
    print(f"  success: {result.success}")
    print(f"  message: {result.message}")
    if result.success:
        print(f"  sequence: {result.sequence}")
        print(
            "\nThis is the literal press sequence needed to reach this car next time — "
            "not a row/column number (see docs/car-position-autodetect-plan.md for why "
            "the manufacturer jump makes an absolute count unrecoverable)."
        )
    else:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
