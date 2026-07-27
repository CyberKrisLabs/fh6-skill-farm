"""Standalone CLI wrapper around
farm_core.multiplier_filter_finder.find_multiplier_filter() — given a
Performance Class and/or Car Type, opens My Cars' Filter list (Y), finds and
checks the matching row(s), then applies the filter (Esc), printing the
exact key-press sequence it took.

PRECONDITION: My Cars must already be open in-game (cursor anywhere) before
running this — the script itself presses Y to open the Filter list.

See farm_core/multiplier_filter_finder.py for the actual search logic
(template matching for Performance Class, OCR burst-scan for Car Type) —
this script only owns the CLI-specific bits: argument parsing, the initial
confirmation prompt, and the pre-search countdown, mirroring
tools/car_collection_finder.py.

Usage:
    python tools/multiplier_filter_finder.py --performance-class R
    python tools/multiplier_filter_finder.py --car-type "Classic Rally"
    python tools/multiplier_filter_finder.py --performance-class R --car-type "Classic Rally"
    python tools/multiplier_filter_finder.py --performance-class R --yes      # skip the initial confirmation prompt
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for farm_core imports

from farm_core import keys, multiplier_filter_finder  # noqa: E402
from farm_core.vision import _winrt_available  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--performance-class", choices=multiplier_filter_finder.PERFORMANCE_CLASSES, help="e.g. R, S1, D"
    )
    parser.add_argument("--car-type", help="e.g. 'Classic Rally', 'GT Cars' — must match the in-game label exactly")
    parser.add_argument("--yes", "-y", action="store_true", help="skip the initial confirmation prompt")
    args = parser.parse_args()

    if not args.performance_class and not args.car_type:
        raise SystemExit("Nothing to search for — pass --performance-class and/or --car-type.")

    if not _winrt_available():
        raise SystemExit("[ERROR] WinRT OCR is unavailable on this machine.")

    if not args.yes:
        input(
            f"About to search for performance_class={args.performance_class!r} car_type={args.car_type!r}. "
            "Make sure My Cars is already open in FH6, then press Enter here..."
        )
    print("Switching to FH6 in 3 seconds — alt-tab now if you haven't already...")
    time.sleep(3)

    if not keys._fh6_focused():
        raise SystemExit("[ERROR] FH6 is not the focused window — switch to it and try again.")

    try:
        result = multiplier_filter_finder.find_multiplier_filter(
            performance_class=args.performance_class, car_type=args.car_type, log=print
        )
    except KeyboardInterrupt:
        print("\nStopped.")
        return

    print("\n=== Result ===")
    print(f"  success: {result.success}")
    print(f"  message: {result.message}")
    if result.success:
        print(f"  sequence: {result.sequence}")
    else:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
