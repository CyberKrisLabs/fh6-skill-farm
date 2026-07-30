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
        "this itself at the start of a Remove phase, to set up the next "
        "cycle's challenge — on this first race of a fresh session nothing "
        "has switched it for you yet, so if you're not already driving it, "
        "this run won't get the multiplier and your skill point math will "
        "be off.\n\n"
        "Also check Settings → Difficulty: Steering must NOT be set to "
        '"Auto-Steering" — on this challenge\'s drag strip layout, '
        "auto-steering turns the car into the wall, and the resulting wall "
        "friction slows it down for the rest of the run. Shifting must be set "
        "to Automatic — the throttle hold and timings are tuned for automatic "
        "shifting, and manual changes acceleration behavior enough to throw "
        "them off. No other difficulty/assist settings need to be touched.\n\n"
        "And make sure Auto Drive is turned off — it shows a prompt right at "
        "the start of the challenge and drives the car itself, which "
        "interferes with the farm holding the throttle itself and isn't a "
        "screen the farm knows how to handle.\n\n"
        'Also in Settings → HUD & Gameplay, keep the co-driver name ("Anna") '
        'and the "Link" prompt visible near the minimap — don\'t hide them. '
        "The farm reads that corner of the screen to detect the moment the "
        "car is actually drivable (challenge loading, retrying, and exiting "
        "Remove back into Free Roam) instead of just waiting a fixed number "
        "of seconds. If they're hidden, the farm still works — it falls back "
        "to waiting the full Timings-tab value — just without that extra "
        "responsiveness.\n\n"
        "In the game, while in Free Roam, press Escape to open the Main "
        'Menu. The tab should be on the first tab, "Campaign".\n\n'
        "The tool will navigate from there to the challenge.",
    ),
    "challenge": (
        "Challenge",
        "IMPORTANT: before pressing Start, manually switch your active car to "
        "the 9x multiplier car (configured in Settings). The tool only does "
        "this itself at the start of a Remove phase, to set up the next "
        "cycle's challenge — on this first race of a fresh session nothing "
        "has switched it for you yet, so if you're not already driving it, "
        "this run won't get the multiplier and your skill point math will "
        "be off.\n\n"
        "Also check Settings → Difficulty: Steering must NOT be set to "
        '"Auto-Steering" — on this challenge\'s drag strip layout, '
        "auto-steering turns the car into the wall, and the resulting wall "
        "friction slows it down for the rest of the run. Shifting must be set "
        "to Automatic — the throttle hold and timings are tuned for automatic "
        "shifting, and manual changes acceleration behavior enough to throw "
        "them off. No other difficulty/assist settings need to be touched.\n\n"
        "And make sure Auto Drive is turned off — it shows a prompt right at "
        "the start of the challenge and drives the car itself, which "
        "interferes with the farm holding the throttle itself and isn't a "
        "screen the farm knows how to handle.\n\n"
        'Also in Settings → HUD & Gameplay, keep the co-driver name ("Anna") '
        'and the "Link" prompt visible near the minimap — don\'t hide them. '
        "The farm reads that corner of the screen to detect the moment the "
        "car is actually drivable (challenge loading, retrying, and exiting "
        "Remove back into Free Roam) instead of just waiting a fixed number "
        "of seconds. If they're hidden, the farm still works — it falls back "
        "to waiting the full Timings-tab value — just without that extra "
        "responsiveness.\n\n"
        "The challenge starts driving immediately — there's no Enter press to "
        "kick it off — so you need to already be inside the challenge yourself "
        "before starting here. Enter it manually using the share code from the "
        "Settings tab.\n\n"
        "Once you're at the very start of the challenge, hit Escape to pause "
        "and stop the challenge timer. Click Start here, then try to hit "
        "Escape again (to go back to a drivable state) just as the countdown "
        "gets close to 0.\n\n"
        "Since the challenge is time-based (max 38s), don't start from here if "
        "more than 10 seconds of the challenge have already passed.",
    ),
    "buy": (
        "Buy",
        "Go to the Festival site menu. In the Campaign tab, click Collection "
        'Journal → the right-hand card ("Discover Japan" — labeled with your '
        'current rank, e.g. "Visitor", "Master Explorer", etc.; the rank name '
        "changes as you progress, the card itself doesn't) → Car Collection.\n\n"
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
        "IMPORTANT: don't be actively driving the 9x multiplier car when "
        "you start from here. The Remove phase's first step switches into "
        'the multiplier car, and selecting "Get in Car" on a car you\'re '
        "already in doesn't work the same way — the farm will get stuck. "
        "Switch to any other car first, ideally one that also isn't the "
        "same Performance Class / Car Type as the multiplier car (see the "
        "Position note in Settings for why that matters too).\n\n"
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
        "You don't have to count this yourself: the Setup Wizard's Step 1 has "
        'a "Find Automatically" button that searches Car Collection for the '
        "car by name and records the navigation itself — open Car Collection "
        "in-game first, click the button, and switch back to FH6 during the "
        "5-second countdown. While it searches, a small status HUD appears "
        "over the FH6 window itself so you can follow along without "
        'switching back to this dialog. Once it succeeds, a "Use '
        'Auto-Found Position" checkbox appears (here and in the Wizard) — '
        "ticked by default, it uses the recorded result and grays out the "
        "Row/Column fields below; untick it to go back to manual entry "
        "without losing the recorded result (toggling the checkbox never "
        "discards it, so re-ticking later doesn't require running the "
        "search again). The manual Row/Column fields below are the fallback "
        "for whenever Find Automatically hasn't been run yet, or fails.\n\n"
        'IMPORTANT: clicking "Find Automatically" again — even just to '
        "double-check an already-working result — clears the previously "
        "recorded position the moment the new search commits to running, "
        "before it's found anything. If that new attempt then fails (a bad "
        "screenshot, losing focus, scrolling too far), the old working "
        "result is already gone, not restored — you're left on manual entry "
        "until a search succeeds again. Only re-run it when you actually "
        "suspect it's gone stale (e.g. your garage changed), not just to "
        "confirm it still works.\n\n"
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
    "skip_remove_in_cycle": (
        "Skip Remove in Cycle",
        "Off by default: after Unlock, the farm removes the cars it just "
        "bought (freeing up the wheelspins-only cars for a fresh cycle).\n\n"
        "Tick this if you'd rather keep or gift those cars yourself instead "
        "of having the farm remove them automatically — e.g. FH6's Gift "
        "Drop, which sends a car to a random player as a nice gesture. "
        "(Gift Drop itself can't be automated here: its car list has no "
        '"Recently Added" sort or any way to filter down to just the farm '
        "cars you want to gift, so there's no reliable way for the farm to "
        "pick the right ones.\n\n"
        "This only skips the AUTOMATIC cycle's Remove step. Manually "
        'picking "Remove" as the Start From point on the Farm tab still '
        "actually removes cars regardless of this setting — it's your "
        "on-demand way to clear cars out whenever you decide to.\n\n"
        "IMPORTANT: a Forza Horizon 6 garage caps out at 2000 cars total. "
        "Leave this ticked across enough sessions without ever removing or "
        "gifting anything yourself, and you can hit that cap — the game "
        "will refuse to add more, and the farm's next Buy phase will fail. "
        "Keep an eye on your garage total if you leave this on long-term.",
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
        "You don't have to count either row yourself: the Setup Wizard's "
        'Step 2 has a "Find Automatically" button — pick your Performance '
        "Class from the dropdown and/or type your Car Type, open My Cars "
        "in-game first, click the button, and switch back to FH6 during the "
        "5-second countdown. While it searches, a small status HUD appears "
        "over the FH6 window itself so you can follow along without "
        'switching back to this dialog. Once it succeeds, a "Use '
        'Auto-Found Filter" checkbox appears (here and in the Wizard) — '
        "ticked by default, it uses the recorded result and grays out the "
        "Filter Row fields below; untick it to go back to manual entry "
        "without losing the recorded result (toggling the checkbox never "
        "discards it). The manual Filter Row fields below are the fallback "
        "for whenever Find Automatically hasn't been run yet, or fails.\n\n"
        'IMPORTANT: clicking "Find Automatically" again — even just to '
        "double-check an already-working result — clears the previously "
        "recorded filter the moment the new search commits to running, "
        "before it's found anything. If that new attempt then fails, the "
        "old working result is already gone, not restored — you're left on "
        "manual entry until a search succeeds again. Only re-run it when "
        "you actually suspect it's gone stale, not just to confirm it still "
        "works.\n\n"
        "IMPORTANT: any change to your garage through normal play between "
        "farm sessions — getting, buying, removing, or selling a car, a "
        "wheelspin reward, anything outside the farm itself — can shift "
        "these row numbers, if the filter list only shows categories that "
        "have at least one matching car in it. Removing/selling matters "
        "just as much as acquiring: it can make a category disappear from "
        "the filter list entirely (shifting every row below it up), not "
        "just add one. Note this now includes the farm's own bought cars, "
        "too: the Remove phase switches to the multiplier car FIRST, before "
        "removing this cycle's freshly-bought cars — so if your farm car "
        "shares the same Performance Class and Car Type as the multiplier "
        "car, those still-owned farm cars will appear in this same filtered "
        "list and can shift the position below. (The farm car this tool "
        "ships with, the Lamborghini Revuelto, is Performance Class S2 / "
        "Hypercars — this only matters if your own multiplier car happens "
        "to fall under that same class and type.) Re-check both rows before "
        "starting a new farm run if your garage has changed at all since "
        "you last set this up, rather than assuming it's still accurate.\n\n"
        "IMPORTANT: FH6's own seasonal rotation can add or remove rows here "
        "too, independent of anything in your garage — winter, for example, "
        'adds two extra checkboxes ("Snow Tyres Fitted" / "Snow Tyres Not '
        'Fitted") above Performance Class, pushing every row from Performance '
        "Class down by 2 for as long as that season lasts. This mainly bites "
        "the manual Filter Row fields, since a row number counted before a "
        "season change is no longer where the farm expects it after one — "
        "re-count both rows after any season change, not just a garage "
        'change. "Find Automatically" copes with this on its own (it '
        "re-scans and scrolls to find each one fresh every time it's run), "
        "so re-running it after a season change is the easier fix if you're "
        "using that instead of manual entry.",
    ),
    "multiplier_position": (
        "9x Multiplier Car — Position",
        "After filtering My Cars to your configured Performance Class + Car "
        "Type, this is where the multiplier car sits in the filtered grid: "
        "Row 1–3 (3 rows per column), Column left to right.\n\n"
        "IMPORTANT:\n"
        "• Work this out on My Cars' default sort. Set this up on a "
        "different sort and the row/column you record won't match where "
        "the farm actually finds it once running.\n"
        "• Make sure you're not currently IN a car that matches that same "
        "Performance Class / Car Type — if you are, the order shown won't "
        "match the order the farm will actually see once it's running, and "
        "the position you record here will be wrong.\n"
        "• Re-check this position before starting a new farm run too, for "
        "the same reason as the Filter rows above — any garage change "
        "through normal play between farm sessions (getting, buying, "
        "removing, or selling a car) can shift where your multiplier car "
        "ends up sitting in the filtered grid. Removing/selling a car "
        "shifts positions just as much as acquiring one does. This now "
        "includes the farm's own bought cars too: the Remove phase "
        "switches to the multiplier car FIRST, before removing that "
        "cycle's freshly-bought cars, so they can still shift this "
        "position if they share the multiplier car's Performance Class "
        "and Car Type (see the Filter section above).\n\n"
        "Unlike Car Collection and the Filter rows above, there's no Find "
        "Automatically for this one — matching a specific car by name in a "
        "grid where several cars can share it (and where the name may "
        "scroll/truncate on the card) turned out not to be worth automating. "
        "This position is manual-entry only.",
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
        "This is a fallback, not the primary wait: the farm first polls for "
        'the co-driver name ("Anna") and the "Link" prompt near the minimap '
        "to detect the moment the challenge is actually drivable, checking "
        'every second until it shows up (logged as "[WARN] Drivable HUD not '
        "detected... — proceeding anyway\" if it never does). If you don't "
        "have Anna/Link visible in your own HUD & Gameplay settings, or OCR "
        "has trouble reading them on your PC, this fixed number is what "
        "actually governs the wait — raise it if the challenge doesn't "
        "auto-start driving in time for the throttle hold.\n\n"
        "Too high still has a real cost when this fallback is what's "
        "actually used: this wait doesn't pause the challenge's own "
        "countdown, so once the level has actually finished loading, every "
        "extra second spent still waiting is a second taken off the time "
        "you have to complete it — set much higher than your PC needs, it "
        "can turn an otherwise-completable run into a wasted one. Worth "
        "testing this one down to the lowest value that reliably works on "
        "your PC, not just leaving it generous.",
    ),
    "LOADING_AFTER_CHALLENGE_EXIT_WAIT": (
        "Loading After Challenge Exit Wait",
        "The wait (in seconds) after pressing Continue to exit a finished "
        "challenge, before the next phase's navigation begins.\n\n"
        "This is a fallback, not the primary wait: the farm first polls for "
        'the co-driver name ("Anna") and the "Link" prompt near the minimap '
        "to detect the moment you're actually back in a drivable state, and "
        "only falls back to this fixed number if that detection doesn't "
        "confirm it in time. If you don't have Anna/Link visible in HUD & "
        "Gameplay settings, or OCR has trouble reading them, this is the "
        "value that actually governs the wait — raise it if the farm starts "
        "pressing keys before you're actually back at a menu after finishing "
        "the last challenge of a cycle.",
    ),
    "LOADING_RETRY_WAIT": (
        "Loading Retry Wait",
        "The wait (in seconds) after pressing Retry — whether the run finished "
        "on time (Retry via escape) or timed out (Retry via enter) — until the "
        "next challenge run is actually drivable.\n\n"
        "This is a fallback, not the primary wait: the farm first polls for "
        'the co-driver name ("Anna") and the "Link" prompt near the minimap '
        "to detect the moment the next run is actually drivable, and only "
        "falls back to this fixed number if that detection doesn't confirm "
        "it in time. If you don't have Anna/Link visible in HUD & Gameplay "
        "settings, or OCR has trouble reading them, this is the value that "
        "actually governs the wait — raise it if the farm starts holding W "
        "for the next run before the car is actually loaded in and "
        "controllable.",
    ),
    "LOADING_EXIT_TO_GAME_WAIT": (
        "Loading Exit To Game Wait",
        "The wait (in seconds), during the Remove phase, after escaping the car "
        "menu back into Free Roam, before navigating to the main menu.\n\n"
        "This is a fallback, not the primary wait: the farm first polls for "
        'the co-driver name ("Anna") and the "Link" prompt near the minimap '
        "to detect the moment you're actually back in Free Roam, and only "
        "falls back to this fixed number if that detection doesn't confirm "
        "it in time. If you don't have Anna/Link visible in HUD & Gameplay "
        "settings, or OCR has trouble reading them, this is the value that "
        "actually governs the wait — raise it if the farm tries to open the "
        "main menu before you're actually back in Free Roam.",
    ),
}
