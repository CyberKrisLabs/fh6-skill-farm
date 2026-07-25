"""Phase: Buy.

Start with cursor on the configured farm car in the Car Collection
(see _navigate_car_collection_to_car). Runs config.NUM_CARS times.
"""

from farm_core import config, keys, vision

# transition_to_buy's fast-travel lands on the Buy & Sell tab of the
# House/Festival site menu, not a specific car's own screen — there's no
# showcase-vs-loaded fork here like unlock._wait_for_car_loaded /
# remove._wait_for_multiplier_car_loaded (those are "Get in Car" on one
# specific car; this is arriving at a menu tab). It just happens to share the
# same button bar text (Select | Back | Forzavista | Set as Home | Series
# Update | Drive — vision.CAR_LOADED_MENU_KEYWORDS) FH6 shows for whichever
# car is highlighted on any car-browsing screen, which doubles as a fine
# anchor for "the tab has finished loading" here too.
#
# Not user-tunable in Timings, unlike most other waits in this codebase —
# this replaces LOADING_TRAVEL_WAIT (removed entirely, see
# docs/state-detection-plan.md #1) rather than keeping it as a poll ceiling:
# the anchor is solid (reused, not new/unverified) and the 30s ceiling has
# generous margin over every measured LOADING_TRAVEL_WAIT value (10-12s), so
# there's nothing left for a user to usefully tune here.
TRAVEL_LOAD_POLL_START_DELAY = 5  # settle time before the first check
TRAVEL_LOAD_POLL_INTERVAL = 1  # poll cadence once polling starts
TRAVEL_LOAD_POLL_MAX_SECONDS = 30  # give up after this long and proceed anyway


def _wait_for_travel_loaded() -> None:
    """Poll for the Buy & Sell tab's button bar after the fast-travel loading
    screen, instead of a blind fixed wait. Gives up and proceeds anyway after
    TRAVEL_LOAD_POLL_MAX_SECONDS if it's never detected.
    """
    keys._sleep(TRAVEL_LOAD_POLL_START_DELAY)
    if keys._stop_event.is_set():
        return
    elapsed = TRAVEL_LOAD_POLL_START_DELAY
    while elapsed < TRAVEL_LOAD_POLL_MAX_SECONDS:
        buttons = vision._read_car_screen_buttons()
        if any(kw in buttons for kw in vision.CAR_LOADED_MENU_KEYWORDS):
            return
        keys._sleep(TRAVEL_LOAD_POLL_INTERVAL)
        elapsed += TRAVEL_LOAD_POLL_INTERVAL
        if keys._stop_event.is_set():
            return
    print(f"  [WARN] Buy & Sell tab not detected after {TRAVEL_LOAD_POLL_MAX_SECONDS}s — proceeding anyway")


def run_buy_iteration():
    keys.mp("space")  # Clicks the Purchase button on current car
    keys.mp("down", wait=config.NAV_WAIT)  # Move down to select "Yes" on the confirmation dialog
    keys.mp("enter")  # Select "Yes" to confirm buy from Car Collection
    keys.mp("enter")  # Select "Buy" to confirm purchase
    keys.mp("enter")  # Confirm after the purchase dialog


def _navigate_car_collection_to_car() -> None:
    """Navigate from the top of the Car Collection list to the configured car position.

    The list is always 5 columns wide with a dynamic number of rows, sorted by
    manufacturer name (default sort). Flow is top → down first, then right:
    row = down presses, column = right presses (0–4). The position is
    user-specific (depends on the cars available to the account) — set in
    settings. Cursor is assumed to start on the FIRST car (top-left).
    """
    car = config.CFG.car
    if car.car_collection_row:
        keys.mp("down", car.car_collection_row, config.NAV_WAIT)
    if car.car_collection_col:
        keys.mp("right", car.car_collection_col, config.NAV_WAIT)


def transition_to_buy():
    """Navigate from the challenge exit to the farm car in the Car Collection.

    Starting point: the final run_challenge_iteration pressed enter (Continue),
    exiting the challenge like the old race exit — same screen as before.
    End point: cursor on the configured farm car in the Car Collection, ready to start buy loop.

    Mid-way, this fast-travels from Free Roam into the House or the Festival
    site — whichever fast-travel destination the account has unlocked, both
    land on the same Buy & Sell tab — and polls for that loading screen to
    finish (see _wait_for_travel_loaded) before paging over to the Campaign
    tab and navigating on to the Car Collection.
    """
    keys.mp("escape")
    keys._sleep(1)  # wait for menu to settle after escaping open world
    if keys._stop_event.is_set():
        return
    keys.mp("pagedown", 1, config.PAGE_WAIT)
    keys.mp("left", wait=config.NAV_WAIT)
    keys.mp("enter")
    if keys._stop_event.is_set():
        return
    keys._press_key("enter")  # fast-travel: Free Roam -> House/Festival site
    _wait_for_travel_loaded()
    if keys._stop_event.is_set():
        return
    keys.mp("pageup", 1, config.PAGE_WAIT)
    keys.mp("down", wait=config.NAV_WAIT)
    keys.mp("enter")
    keys._sleep(1)  # menu settle
    if keys._stop_event.is_set():
        return
    keys.mp("right", wait=config.NAV_WAIT)
    keys.mp("enter")
    keys._sleep(0.5)  # menu settle
    if keys._stop_event.is_set():
        return
    keys.mp("down", wait=config.NAV_WAIT)
    keys.mp("enter")
    _navigate_car_collection_to_car()  # cursor now on the farm car — ready for buy loop
