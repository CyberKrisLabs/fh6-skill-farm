"""Setup Wizard step content — deliberately separate from guide_content.py's
SETTINGS_INFO. SETTINGS_INFO is reference text for someone who already knows
the app (the ⓘ popups, the Guide tab); the wizard walks a first-timer through
the exact in-game clicks, so it gets its own, more procedural copy instead of
reusing that text verbatim.

Each step is a list of (image_filename, caption) slides, paged one at a time
in the wizard — image files live alongside this at
assets/wizard/<folder>/<image_filename> (folder == this dict's key). A step
with an empty `slides` list falls back to showing `fallback_text` instead, so
the wizard has something to say before screenshots/captions are filled in.
"""

WIZARD_STEPS: dict[str, dict] = {
    "car_collection": {
        "title": "Car Collection Position",
        "fallback_text": (
            "Go to the Festival menu → Campaign tab → Collection Journal → "
            'the right-hand card ("Discover Japan" — labeled with your current '
            'rank, e.g. "Visitor", "Master Explorer", etc.; the rank name '
            "changes as you progress, the card itself doesn't) → Car Collection, "
            "and find your farm car in the list. Enter its row (from the top) "
            "and column (1-5) below."
        ),
        "slides": [
            ("01.png", "Go to the Festival Site (or your House), then the Campaign tab, and click Collection Journal."),
            (
                "02.png",
                'Click the right-hand card ("Discover Japan"). It\'s labeled with your '
                'current rank at the bottom — here it\'s "Master Explorer", but yours '
                'might say "Visitor" or anything in between; that\'s normal.',
            ),
            ("03.png", "Click Car Collection."),
            (
                "04.png",
                "Don't change the sort — just start counting rows from the top until "
                "you reach the car you've chosen. Pick that car from the dropdown "
                "below first.",
            ),
            (
                "05.png",
                "Once you find the car — here, the Lamborghini Revuelto — fill in "
                "its Row and Column below. In this example: Column 3, Row 65.",
            ),
        ],
    },
    "multiplier_filter": {
        "title": "9x Multiplier Car — Filter",
        "fallback_text": (
            "In the My Cars list, press Y to open Filter, then find your 9x "
            "multiplier car's Performance Class and Car Type in the checkbox "
            "list and check both. Enter how far down the filter list each one "
            "is, counted from the very top.\n\n"
            "Note: FH6's seasonal rotation can add or remove rows here (e.g. "
            'winter adds "Snow Tyres Fitted" / "Snow Tyres Not Fitted" above '
            "Performance Class) — re-count both rows after a season change, "
            "not just after a garage change."
        ),
        "slides": [
            ("01.png", 'Go to the Festival Site (or your House), then the "Cars" tab, and click My Cars.'),
            ("02.png", "Open the Filter options (press Y)."),
            (
                "03.png",
                "Count the rows from the very top of the filter list until you reach "
                "your 9x multiplier car's Performance Class and check it. In this "
                "example: row 10.\n\n"
                "Note: FH6's seasonal rotation can add rows above this one (e.g. "
                'winter adds "Snow Tyres Fitted" / "Snow Tyres Not Fitted"), '
                "shifting this count — re-check it after any season change, not "
                "just a garage change.",
            ),
            (
                "04.png",
                "Keep counting down from the very top until you reach your 9x "
                "multiplier car's Car Type and check it. In this example: row 36.\n\n"
                "Same seasonal caveat as Performance Class above applies here too, "
                "since it's counted from the same top of the list.",
            ),
        ],
    },
    "multiplier_position": {
        "title": "9x Multiplier Car — Position",
        "fallback_text": (
            "With that filter applied, find your multiplier car in the "
            "filtered grid (3 rows per column) and enter its row and column."
        ),
        "slides": [
            (
                "01.png",
                "Follow the filtering steps as described in step 2 of the wizard to "
                "bring your x9 multiplier car up in the filtered My Cars grid (3 rows "
                "per column), then check which Row and Column it sits in. In this "
                "example: Row 1, Column 1.\n\n"
                "IMPORTANT: don't be currently driving your multiplier car — or any "
                "other car sharing that exact Performance Class / Car Type — while "
                "checking this. The order shown won't match what the farm sees once "
                "it's actually running, and will throw off the position you record here.",
            ),
        ],
    },
}
