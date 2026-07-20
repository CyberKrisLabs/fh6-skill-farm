"""Phase: Buy.

Start with cursor on the configured farm car in the Car Collection
(see _navigate_car_collection_to_car). Runs config.NUM_CARS times.
"""

from farm_core import config, keys


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
    """
    keys.mp("escape")
    keys._sleep(1)  # wait for menu to settle after escaping open world
    keys.mp("pagedown", 1, config.PAGE_WAIT)
    keys.mp("left", wait=config.NAV_WAIT)
    keys.mp("enter")
    keys._press_key("enter")
    keys._sleep(7)  # menu settle
    keys.mp("pageup", 1, config.PAGE_WAIT)
    keys.mp("down", wait=config.NAV_WAIT)
    keys.mp("enter")
    keys._sleep(1)  # menu settle
    keys.mp("right", wait=config.NAV_WAIT)
    keys.mp("enter")
    keys._sleep(0.5)  # menu settle
    keys.mp("down", wait=config.NAV_WAIT)
    keys.mp("enter")
    _navigate_car_collection_to_car()  # cursor now on the farm car — ready for buy loop
