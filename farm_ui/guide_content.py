"""Shared explanatory text — single source of truth for both the in-place ⓘ
info popups (Farm/Settings/Timings tabs) and the standalone Guide tab, so the
two never drift out of sync.
"""

# ── Start From — (label, explanation) per starting point ──────────────────────
START_FROM_INFO: dict[str, tuple[str, str]] = {
    "main": (
        "Main Menu",
        "IMPORTANT: before pressing Start, manually switch your active car to "
        "the 9x multiplier car (configured in Settings). The tool only does "
        "this itself at the end of a Remove phase, to set up the next cycle's "
        "challenge — on this first race of a fresh session nothing has "
        "switched it for you yet, so if you're not already driving it, this "
        "run won't get the multiplier and your skill point math will be "
        "off.\n\n"
        "Also make sure Transmission is set to Automatic — the ease-in "
        "throttle sequence and hold timings are tuned for automatic "
        "shifting, and manual changes acceleration behavior enough to throw "
        "them off.\n\n"
        "And make sure Auto Drive is turned off — it shows a prompt right at "
        "the start of the challenge and drives the car itself, which "
        "interferes with the ease-in throttle sequence and isn't a screen "
        "the farm knows how to handle.\n\n"
        "In the game, while in Free Roam, press Escape to open the Main "
        'Menu. The tab should be on the first tab, "Campaign".\n\n'
        "The tool will navigate from there to the challenge.",
    ),
    "challenge": (
        "Challenge",
        "IMPORTANT: before pressing Start, manually switch your active car to "
        "the 9x multiplier car (configured in Settings). The tool only does "
        "this itself at the end of a Remove phase, to set up the next cycle's "
        "challenge — on this first race of a fresh session nothing has "
        "switched it for you yet, so if you're not already driving it, this "
        "run won't get the multiplier and your skill point math will be "
        "off.\n\n"
        "Also make sure Transmission is set to Automatic — the ease-in "
        "throttle sequence and hold timings are tuned for automatic "
        "shifting, and manual changes acceleration behavior enough to throw "
        "them off.\n\n"
        "And make sure Auto Drive is turned off — it shows a prompt right at "
        "the start of the challenge and drives the car itself, which "
        "interferes with the ease-in throttle sequence and isn't a screen "
        "the farm knows how to handle.\n\n"
        "The challenge starts driving immediately — there's no Enter press to "
        "kick it off — so you need to already be inside the challenge yourself "
        "before starting here. Enter it manually using the share code from the "
        "Settings tab.\n\n"
        "Once you're at the very start of the challenge, hit Escape to pause "
        "and stop the challenge timer. Click Start here, then try to hit "
        "Escape again (to go back to a drivable state) just as the countdown "
        "gets close to 0.\n\n"
        "Since the challenge is time-based (max 45s), don't start from here if "
        "more than 15 seconds of the challenge have already passed.",
    ),
    "buy": (
        "Buy",
        "Go to the Festival site menu. In the Campaign tab, click Collection "
        "Journal → Master Explorer → Car Collection.\n\n"
        "Once inside the Car Collection, navigate exactly to the "
        "car the farm should buy (e.g. Lamborghini Revuelto), then click "
        "Start.",
    ),
    "unlock": (
        "Unlock",
        'Go to the Festival site menu. In the Cars tab, click "My Cars".\n\n'
        "To start from here you should have already bought the cars you want "
        "wheelspins unlocked from — enter your current skill points and how "
        "many cars you've bought.\n\n"
        "IMPORTANT: don't have any cars newer than the ones you just bought — "
        "this farm sorts by recently added, so acquiring any other car "
        "afterward breaks it. Whether the cars you're unlocking are still "
        '"New" (never entered) or already loaded from earlier this session '
        "doesn't matter — the farm detects which screen it lands on after "
        "selecting each car and adjusts automatically either way.",
    ),
    "remove": (
        "Remove",
        'Go to the Festival site menu. In the Cars tab, click "My Cars".\n\n'
        "Before starting, enter how many cars you want to remove (that "
        "you've already unlocked). Same requirement as Unlock: they need to "
        "be the most recently added cars, or the farm will remove cars you "
        "didn't intend to remove.\n\n"
        "Run this directly after unlocking the cars you want removed.",
    ),
}

# ── Settings tab — (title, explanation) per required field group ──────────────
SETTINGS_INFO: dict[str, tuple[str, str]] = {
    "car_collection": (
        "Car Collection Row / Column",
        "The position of your farm car in the Car Collection list (5 columns "
        "wide, dynamic rows, left at its default sort — manufacturer name) — "
        "where the farm navigates to before buying and unlocking each cycle.\n\n"
        "Row 1 = the top of the list; Column 1–5, left to right. This "
        "depends entirely on which cars your account has access to, so it "
        "has to be set per account.\n\n"
        "Required before starting the farm, unless Challenge Only is ticked "
        "on the Farm tab — that mode never buys/unlocks/removes cars, so "
        "this position is never used.",
    ),
    "soko78": (
        '"Soko 78" House Owned',
        "Owning the Soko 78 house in-game grants a 5% discount on Autoshow "
        "car prices. Tick this if your account owns it — the Price (CR) "
        "field above, and all cost/CR-affordability math in the farm, will "
        "use the discounted price instead of the full Autoshow price.\n\n"
        "Off by default: not every account owns this house, and assuming "
        "the discount when you don't would undercount the real cost, "
        "potentially causing the farm to attempt buying more cars than your "
        "CR can actually afford.",
    ),
    "whats_next": (
        '"What\'s Next" (HUD & Gameplay)',
        "FH6's HUD & Gameplay settings has a \"What's Next\" option that, when "
        "turned on, shows an extra screen after finishing an activity — a "
        "Select (Enter, picks a proposed activity) / Back (Escape, exits to "
        "Free Roam) choice — instead of dropping you straight into Free Roam "
        "like normal.\n\n"
        "Tick this box if you have that setting turned on in your own game. "
        "The farm will send an extra Escape (Back) and wait a few seconds "
        "after exiting the challenge to get past that screen before "
        "continuing to Buy.\n\n"
        "Leave it unticked if you don't have \"What's Next\" enabled — sending "
        "that extra Escape when the screen never appears would misfire into "
        "whatever's on screen next instead.",
    ),
    "overlay": (
        "In-Game Overlay",
        "Shows a small always-on-top HUD over the FH6 window itself, with "
        "Start / Stop, the elapsed run time, current cycle/phase progress "
        '(e.g. "Cycle 2 · Buy 14/25"), and the latest log line — so you can '
        "check status or hit Stop without alt-tabbing back to this app.\n\n"
        "It only appears while FH6 has focus, and hides itself again if you "
        "switch away — it won't linger over other windows. Its own Hide "
        "button turns this setting back off immediately (no need to come "
        "back here and save).\n\n"
        "Off by default — it's an optional convenience, not everyone wants "
        "an extra HUD element on top of the game.",
    ),
    "multiplier_filter": (
        "9x Multiplier Car — Filter",
        "In the My Cars list, press Y to open Filter. It's one long "
        "vertical checkbox list split into sections — Performance Class is "
        "one section, Car Type is another, further down.\n\n"
        "Find your own 9x multiplier car's Performance Class and Car Type in "
        "that list, and check both boxes. These two rows tell the farm how "
        "far down that single-column list each checkbox is, counted from the "
        "very top of the whole filter list (both counted independently from "
        "the top, not relative to each other).\n\n"
        "Example: a non-tuned (stock) Subaru 22B is Performance Class B, Car "
        "Type Retro Rally. If yours is tuned into a different class, or "
        "you're using a different multiplier car entirely, enter whichever "
        "Performance Class and Car Type it actually falls under instead — "
        "the multiplier isn't limited to one specific car or class.\n\n"
        "Both boxes get checked to narrow My Cars down to just your "
        "multiplier car before finding its position — see the Position "
        "section below.\n\n"
        "IMPORTANT: any change to your garage through normal play between "
        "farm sessions — getting, buying, removing, or selling a car, a "
        "wheelspin reward, anything outside the farm itself — can shift "
        "these row numbers, if the filter list only shows categories that "
        "have at least one matching car in it. Removing/selling matters "
        "just as much as acquiring: it can make a category disappear from "
        "the filter list entirely (shifting every row below it up), not "
        "just add one. (The cars this farm buys don't cause this — they're "
        "always removed again before it switches to the multiplier car, so "
        "they never linger in My Cars.) Re-check both rows before starting "
        "a new farm run if your garage has changed at all since you last "
        "set this up, rather than assuming it's still accurate.",
    ),
    "multiplier_position": (
        "9x Multiplier Car — Position",
        "After filtering My Cars to your configured Performance Class + Car "
        "Type, this is where the multiplier car sits in the filtered grid: "
        "Row 1–3 (3 rows per column), Column left to right.\n\n"
        'IMPORTANT: sort My Cars by "Recently Added" before you work this '
        "out — not whatever sort the list happens to already be on. During "
        "the Remove phase, the farm opens My Cars sorted by Recently Added "
        "(it needs that sort to find the cars it just bought) and never "
        "changes the sort back before switching to the multiplier car "
        "right after — so that's the sort order actually active in the "
        "filtered grid when the position you set here gets used live. Set "
        "this up on any other sort and the row/column you record won't "
        "match where the farm actually finds it once running.\n\n"
        "Important: when you work this out, make sure you're not currently "
        "IN a car that matches that same Performance Class / Car Type — if "
        "you are, the order shown won't match the order the farm will "
        "actually see once it's running, and the position you record here "
        "will be wrong.\n\n"
        "IMPORTANT: re-check this position before starting a new farm run "
        "too, for the same reason as the Filter rows above — any garage "
        "change through normal play between farm sessions (getting, buying, "
        "removing, or selling a car) can shift where your multiplier car "
        "ends up sitting in the filtered grid. Removing/selling a car "
        "shifts positions just as much as acquiring one does. (Cars the "
        "farm buys itself don't cause this — they're removed again before "
        "it switches to the multiplier car.)",
    ),
}

# ── Timings tab — (label, explanation) per user-editable wait constant ────────
# Keys must match farm_settings.TIMING_DEFAULTS / farm_core.config's wait constants.
TIMING_INFO: dict[str, tuple[str, str]] = {
    "MENU_WAIT": (
        "Menu Wait",
        "The default pause (in seconds) after most menu key presses — anything "
        "that isn't up/down navigation or typing. Used throughout every phase "
        "(challenge, buy, unlock, remove) for confirmations, opening menus, and "
        "screen transitions.\n\n"
        "Lower = faster overall navigation, but too low and presses may register "
        "before the menu has caught up, causing missed inputs or wrong "
        "selections. Raise it if you see the farm clicking into the wrong option.",
    ),
    "NAV_WAIT": (
        "Nav Wait",
        "The pause (in seconds) between up/down/left/right presses when moving "
        "the cursor within an already-open list or menu (car lists, sort menus, "
        "filter checkboxes, Car Collection grid).\n\n"
        "Since these are just cursor moves within a menu that's already open, "
        "this can usually be much shorter than Menu Wait. Raise it if the "
        "cursor seems to skip rows or land on the wrong item.",
    ),
    "PAGE_WAIT": (
        "Page Wait",
        "The pause (in seconds) after Page Up/Page Down presses, used to switch "
        "between main-menu tabs (e.g. Creative Hub) during the challenge/buy/"
        "unlock transitions.\n\n"
        "Tab transitions have their own animation, so this is set higher than "
        "Menu Wait. Raise it if a tab switch doesn't register before the next "
        "key press.",
    ),
    "TYPING_WAIT": (
        "Typing Wait",
        "The pause (in seconds) between each character when typing the "
        "challenge share code into the search field.\n\n"
        "Lower = faster typing, but too low and characters can be dropped or "
        "arrive out of order. Raise it if the share code sometimes comes out "
        "wrong or search fails to find the challenge.",
    ),
    "LOADING_CHALLENGE_WAIT": (
        "Loading Challenge Wait",
        "The wait (in seconds) after selecting the challenge from the search "
        "results, while it loads — the Main Menu → Challenge transition.\n\n"
        "One of the longest waits in the farm, since it covers an actual level "
        "load rather than a menu animation. Raise it if the challenge doesn't "
        "auto-start driving in time for the ease-in sequence.\n\n"
        "Too high has a real cost, not just wasted time: this wait doesn't "
        "pause the challenge's own countdown, so once the level has actually "
        "finished loading, every extra second spent still waiting is a second "
        "taken off the time you have to complete it — set much higher than "
        "your PC needs, it can turn an otherwise-completable run into a wasted "
        "one. Worth testing this one down to the lowest value that reliably "
        "works on your PC, not just leaving it generous.",
    ),
    "LOADING_AFTER_CHALLENGE_EXIT_WAIT": (
        "Loading After Challenge Exit Wait",
        "The wait (in seconds) after pressing Continue to exit a finished "
        "challenge, before the next phase's navigation begins.\n\n"
        "Raise it if the farm starts pressing keys before you're actually back "
        "at a menu after finishing the last challenge of a cycle.",
    ),
    "LOADING_TRAVEL_WAIT": (
        "Loading Travel Wait",
        "The wait (in seconds) for the fast-travel loading screen from Free "
        "Roam into the House or the Festival site — whichever fast-travel "
        "destination your account has unlocked (both land on the same menus "
        "afterward, so it doesn't matter which) — during the challenge → buy "
        "transition. The farm navigates on to the Car Collection afterward, "
        "once this loading screen has finished.\n\n"
        "This varies more by PC than most loading waits. Raise it if the farm "
        "starts navigating menus before the destination has actually finished "
        "loading.",
    ),
    "LOADING_RETRY_WAIT": (
        "Loading Retry Wait",
        "The wait (in seconds) after pressing Retry — whether the run finished "
        "on time (Retry via escape) or timed out (Retry via enter) — until the "
        "next challenge run is actually drivable.\n\n"
        "Raise it if the ease-in W-taps at the start of the next run seem to "
        "fire before the car is actually loaded in and controllable.",
    ),
    "LOADING_RESET_WAIT": (
        "Loading Reset Wait",
        "The wait (in seconds) after a manual pause-menu restart — the fallback "
        "recovery used when the end-of-challenge screen can't be identified at "
        "all (not even a Retry button).\n\n"
        "A rare path, but since it involves a fuller reload than a normal Retry, "
        "it gets a longer wait. Raise it if runs recovered this way come out "
        "stuck or in a bad state.",
    ),
    "LOADING_EXIT_TO_GAME_WAIT": (
        "Loading Exit To Game Wait",
        "The wait (in seconds), during the Remove phase, after escaping the car "
        "menu back into Free Roam, before navigating to the main menu.\n\n"
        "How long this takes can vary by PC. Raise it if the farm tries to open "
        "the main menu before you're actually back in Free Roam.",
    ),
}
