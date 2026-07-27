#!/usr/bin/env python3
"""Persistent user settings for the FH6 skill farm.

Stored in skill_farm_settings.json under APP_DATA_DIR — but only genuine user
input: grid positions (Car Collection / owned-car list) differ per user
account, so those live here instead of in code. Fixed facts about a car
(name, price, SP to unlock, wheelspin yield) are NOT user input — they live in
CAR_CATALOG below, in code, same as UNLOCK_SEQUENCES in farm_core/unlock.py.
New cars are added by editing CAR_CATALOG (+ UNLOCK_SEQUENCES), not through
the UI. Keeping catalog facts out of the settings file means a data fix (e.g.
a corrected SP cost after a game patch) always takes effect immediately,
instead of being silently overridden by whatever an existing settings file
already has saved for that field.
"""

from __future__ import annotations

import dataclasses
import json
import os
import pathlib


def _app_data_dir() -> pathlib.Path:
    """Return %APPDATA%\\FH6SkillFarm (creating it if needed), or a fallback.

    Settings/logs must live in a stable, user-writable location rather than
    next to the script: under a PyInstaller exe, __file__ resolves inside a
    temp extraction folder that's deleted on exit, so anything written there
    wouldn't persist between runs. Mirrors FH6 Sniper's window_utils.get_config_file().
    """
    try:
        app_data = os.environ.get("APPDATA")
        base = pathlib.Path(app_data) / "FH6SkillFarm" if app_data else pathlib.Path.home() / ".fh6skillfarm"
        base.mkdir(parents=True, exist_ok=True)
        return base
    except OSError as exc:
        print(f"[WARN] Could not create app data directory ({exc}) — using local directory")
        return pathlib.Path(__file__).parent


APP_DATA_DIR = _app_data_dir()
SETTINGS_PATH = APP_DATA_DIR / "skill_farm_settings.json"

# User-editable wait constants (Timings tab). Keys match the module-level
# constant names in skill_farm.py, which refresh_timings() overwrites from
# these values after load/save. Anything not listed here (e.g. the challenge
# hold/poll tuning knobs) is code-only, not exposed to the user.
TIMING_DEFAULTS: dict[str, float] = {
    "MENU_WAIT": 0.5,
    "NAV_WAIT": 0.05,
    "PAGE_WAIT": 2,
    "TYPING_WAIT": 0.2,
    "LOADING_AFTER_CHALLENGE_EXIT_WAIT": 20,
    "LOADING_CHALLENGE_WAIT": 30,
    "LOADING_RETRY_WAIT": 30,
    "LOADING_EXIT_TO_GAME_WAIT": 15,
}

# Fast/Mid/Slow presets used to live here, varying LOADING_CHALLENGE_WAIT
# (and, before it was removed, LOADING_TRAVEL_WAIT — see
# docs/state-detection-plan.md #1) between hardware tiers. Removed once all
# four LOADING_* waits became fallback-only ceilings behind drivable-HUD
# detection (docs/state-detection-plan.md #2/#3/#4/#5): most users now rarely
# hit these at all, so a hardware-tier preset for them stopped pulling its
# weight — tune them individually in the Timings tab if the fallback ever
# actually fires for you.


@dataclasses.dataclass(frozen=True)
class CarInfo:
    """Fixed facts about a farm car — from the game itself, not user input.

    Add new cars here (and a matching UNLOCK_SEQUENCES entry in
    farm_core/unlock.py) — never persisted to settings, so these values
    always come from the running code, immune to whatever an older settings
    file has saved.
    """

    car_id: str  # keys UNLOCK_SEQUENCES in farm_core/unlock.py
    name: str
    price_cr: int  # base Autoshow price — full price, before the Soko 78 discount
    sp_to_unlock: int  # skill points spent to reach the wheelspin skills (or CR reward)
    super_wheelspins: int  # yield per car
    wheelspins: int  # yield per car
    # CR granted per car instead of/alongside wheelspins — some cars' skill
    # trees unlock a straight Credits reward at this node rather than (or in
    # addition to) wheelspins. 0 for cars that don't have one. Defaults to 0
    # so existing wheelspin-only entries don't need to spell it out.
    cr_reward: int = 0
    # Split out from the combined `name` above specifically for the Setup
    # Wizard's "Find Automatically" search (farm_core/car_collection_finder.py) — the
    # Car Collection card shows model name on one line, then "year
    # manufacturer" on the next, and matching needs each piece on its own
    # (a combined "Lamborghini Revuelto" string can't be matched against
    # that two-line layout the same way — see
    # docs/car-position-autodetect-plan.md's Data gap section). `name`
    # remains the single display string used everywhere else in the UI;
    # these three are ONLY for that search. Uppercase, matching how OCR text
    # gets compared (case-insensitive in practice, but stored upper here to
    # make that visible).
    manufacturer: str = ""
    model: str = ""
    year: str = ""


CAR_CATALOG: dict[str, CarInfo] = {
    "lambo_revuelto": CarInfo(
        car_id="lambo_revuelto",
        name="Lamborghini Revuelto",
        price_cr=365_000,
        sp_to_unlock=39,
        super_wheelspins=1,
        wheelspins=3,
        manufacturer="LAMBORGHINI",
        model="REVUELTO",
        year="2024",
    ),
    "dodge_viper_gts_acr": CarInfo(
        car_id="dodge_viper_gts_acr",
        name="Dodge Viper GTS ACR",
        price_cr=68_000,  # 64,600 CR with the Soko 78 discount
        sp_to_unlock=30,
        super_wheelspins=0,
        wheelspins=0,
        cr_reward=150_000,
        manufacturer="DODGE",
        model="VIPER GTS ACR",
        year="1999",
    ),
}

# Owning the "Soko 78" house grants a 5% discount on Autoshow car prices.
# Off by default — not every account owns it, and assuming it silently (as
# CAR_CATALOG prices used to, baked in as if everyone had it) undercounts the
# real cost for anyone who doesn't.
SOKO78_DISCOUNT = 0.05


def effective_price_cr(base_price_cr: int, soko78_house_owned: bool) -> int:
    """Car price after the Soko 78 house's 5% Autoshow discount, if owned."""
    return round(base_price_cr * (1 - SOKO78_DISCOUNT)) if soko78_house_owned else base_price_cr


@dataclasses.dataclass
class CarConfig:
    """User-specific data for one car — its position in the Car Collection
    list. Everything else about the car (name, price, SP cost, wheelspin
    yield) comes from CAR_CATALOG; see Settings.car for the combined view.
    """

    car_id: str  # keys CAR_CATALOG and UNLOCK_SEQUENCES
    # Position of the car in the Car Collection list — user-specific (depends
    # on which cars are available to the account). The list is always 5
    # columns wide, rows are dynamic, default sort = manufacturer name.
    # Navigation goes from the top car: row = down presses first, then
    # column = right presses (0–4). Required before starting the farm unless
    # Challenge Only mode is used.
    car_collection_col: int
    car_collection_row: int
    # True once the user has saved Car Collection Row/Column via the Settings
    # tab. The stored row/col are 0-based but the UI is 1-based (minimum
    # input is 1, i.e. stored 0) — so 0 is a legitimate real position, not a
    # usable "unset" sentinel. This flag is the actual source of truth for
    # whether the farm can be started (see skill_farm_ui._on_start).
    car_collection_configured: bool
    # Recorded by the Setup Wizard's "Find Automatically" tool: a full
    # navigation sequence (Backspace to open the Manufacturers list, Down/
    # Right to the target manufacturer, Enter to jump, then a small local
    # Down/Up/Left/Right offset within Car Collection to land on the exact
    # car) — see docs/car-position-autodetect-plan.md and
    # farm_core/car_collection_finder.py. Each entry is [key, count], the same shape
    # farm_core.keys.mp() takes as its own (key, count) arguments, so
    # buy.py can replay the list directly. Only meaningful when
    # car_collection_auto_found is True below; car_collection_row/col above
    # remain the manual fallback whenever this hasn't been recorded, or a
    # later Find Automatically run fails — never both active at once, see
    # the Settings/Wizard "currently active" display.
    car_collection_find_sequence: list = dataclasses.field(default_factory=list)
    # True once Find Automatically has successfully located and recorded
    # this car's position. Same reasoning as car_collection_configured
    # above for why this needs its own explicit flag rather than checking
    # whether car_collection_find_sequence is non-empty: an empty list is
    # ambiguous (never recorded vs. a genuine zero-press offset), so this
    # flag is the real source of truth for which navigation method buy.py
    # replays.
    car_collection_auto_found: bool = False
    # User's preference for WHICH method to actually use, independent of whether an auto-found
    # sequence exists (car_collection_auto_found above) — lets a user keep a successfully-recorded
    # sequence on file but still choose manual Row/Column instead (Settings tab / Wizard checkbox),
    # without losing the recorded sequence. Defaults True: once a fresh Find Automatically run
    # succeeds, using it immediately is the sensible default. Runtime check is always BOTH flags
    # together — see buy._navigate_car_collection_to_car.
    car_collection_use_auto_find: bool = True


@dataclasses.dataclass(frozen=True)
class Car:
    """Combined view of a car's CAR_CATALOG facts + its CarConfig user
    settings — what Settings.car returns for convenient, read-only access.
    """

    car_id: str
    name: str
    price_cr: int
    sp_to_unlock: int
    super_wheelspins: int
    wheelspins: int
    cr_reward: int
    manufacturer: str
    model: str
    year: str
    car_collection_col: int
    car_collection_row: int
    car_collection_configured: bool
    car_collection_find_sequence: list
    car_collection_auto_found: bool
    car_collection_use_auto_find: bool


@dataclasses.dataclass
class Settings:
    selected_car: str
    cars: dict[str, CarConfig]
    # The 9x multiplier car is found by filtering the owned-car list to its
    # Performance Class + Car Type (e.g. a stock Subaru 22B is Performance
    # Class B / Retro Rally — but the multiplier isn't limited to that one
    # car or class, so both are user-configured). The filter is a checkbox
    # list — enter toggles a box without closing the list — so both rows are
    # counted as down presses from the TOP of the filter list (absolute, not
    # relative to each other). User-specific: depends on how many categories
    # precede these two. Stored 0-based like car_collection_col/row above —
    # the Settings tab shows these as (this value + 1); if hand-editing this
    # file, subtract 1 from whatever row/column the UI would show you.
    filter_performance_class_row: int
    filter_car_type_row: int
    # "Find Automatically" (farm_core.multiplier_filter_finder, Setup Wizard Step 2) — mirrors
    # CarConfig.car_collection_auto_found's auto-vs-manual fallback semantics, but lives at the top
    # level rather than per-car, since the multiplier car filter isn't tied to which farm car is
    # selected. filter_performance_class/filter_car_type record WHAT was searched for (shown back
    # in the wizard, and reused if the user re-runs Find Automatically later); filter_find_sequence
    # is the recorded [key, count] navigation replayed by remove.py instead of the manual row counts
    # above when filter_auto_found is True — see remove._replay_filter_find_sequence.
    filter_performance_class: str
    filter_car_type: str
    filter_auto_found: bool
    filter_find_sequence: list
    # Same "use this even though it exists" preference toggle as
    # CarConfig.car_collection_use_auto_find above, for this filter's own auto-found sequence.
    filter_use_auto_find: bool
    # Position of the multiplier car within the filtered "My Cars" grid
    # (3 rows per column, dynamic columns) — user-specific. Also stored
    # 0-based / shown 1-based in the UI, same as the fields above.
    multiplier_car_col: int
    multiplier_car_row: int
    # True once the user has saved the filter rows + position via the
    # Settings tab — see CarConfig.car_collection_configured for why 0 can't
    # be used as an "unset" sentinel here either.
    multiplier_car_configured: bool
    # Whether the account owns the "Soko 78" house — grants a 5% discount on
    # Autoshow car prices (see CarInfo.price_cr / effective_price_cr above).
    # Off by default: not every account owns it, so assuming it would
    # undercount the real cost for anyone who doesn't.
    soko78_house_owned: bool
    # Whether the in-game overlay (Start/Stop/phase progress/log line, shown
    # over the FH6 window itself) is enabled. Off by default — it's an
    # optional convenience, not everyone wants an extra HUD element on top
    # of the game.
    show_ingame_overlay: bool
    # Whether the automatic buy/unlock/remove cycle should skip the Remove
    # step entirely (for users who'd rather keep or gift the cars themselves
    # — e.g. FH6's Gift Drop, which has no way to sort/filter down to just
    # the farm's own cars, so the farm can't drive that flow itself). Off by
    # default — removing is the farm's normal behavior. Only gates the
    # AUTOMATIC cycle: manually picking "Remove" as the Start From point
    # still actually removes regardless of this setting — see
    # farm_core.orchestrator._run_farm_inner. Doesn't affect Buy/Unlock; if
    # left on across many sessions, the garage's 2000-car cap becomes the
    # user's own responsibility to manage (see the Settings ⓘ info).
    skip_remove_in_cycle: bool
    # User-editable wait constants (Timings tab) — see TIMING_DEFAULTS.
    timings: dict[str, float]

    @property
    def car(self) -> Car:
        info = CAR_CATALOG[self.selected_car]
        user = self.cars[self.selected_car]
        return Car(
            car_id=info.car_id,
            name=info.name,
            price_cr=effective_price_cr(info.price_cr, self.soko78_house_owned),
            sp_to_unlock=info.sp_to_unlock,
            super_wheelspins=info.super_wheelspins,
            wheelspins=info.wheelspins,
            cr_reward=info.cr_reward,
            manufacturer=info.manufacturer,
            model=info.model,
            year=info.year,
            car_collection_col=user.car_collection_col,
            car_collection_row=user.car_collection_row,
            car_collection_configured=user.car_collection_configured,
            car_collection_find_sequence=user.car_collection_find_sequence,
            car_collection_auto_found=user.car_collection_auto_found,
            car_collection_use_auto_find=user.car_collection_use_auto_find,
        )


def _default_settings() -> Settings:
    cars = {
        car_id: CarConfig(
            car_id=car_id,
            car_collection_col=0,  # TODO: set per account (Settings tab)
            car_collection_row=0,
            car_collection_configured=False,
        )
        for car_id in CAR_CATALOG
    }
    return Settings(
        selected_car="lambo_revuelto",
        cars=cars,
        filter_performance_class_row=0,  # TODO: set per account (Settings tab)
        filter_car_type_row=0,
        filter_performance_class="",
        filter_car_type="",
        filter_auto_found=False,
        filter_find_sequence=[],
        filter_use_auto_find=True,
        multiplier_car_col=0,
        multiplier_car_row=0,
        multiplier_car_configured=False,
        soko78_house_owned=False,
        show_ingame_overlay=False,
        skip_remove_in_cycle=False,
        timings=dict(TIMING_DEFAULTS),
    )


def load(path: pathlib.Path = SETTINGS_PATH) -> Settings:
    """Load settings, merging over defaults so files from older versions keep working."""
    settings = _default_settings()
    if not path.exists():
        return settings
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[WARN] Could not read {path.name} ({exc}) — using defaults")
        return settings

    car_fields = {f.name for f in dataclasses.fields(CarConfig)}
    for car_id, car_data in data.get("cars", {}).items():
        if car_id not in CAR_CATALOG:
            print(f"[WARN] Skipping unknown car '{car_id}' in settings (not in CAR_CATALOG)")
            continue
        base = settings.cars[car_id]
        merged = dataclasses.asdict(base)
        merged.update({k: v for k, v in car_data.items() if k in car_fields})
        try:
            settings.cars[car_id] = CarConfig(**merged)
        except TypeError as exc:
            print(f"[WARN] Skipping malformed car '{car_id}' in settings: {exc}")

    for field in (
        "selected_car",
        "filter_performance_class_row",
        "filter_car_type_row",
        "filter_performance_class",
        "filter_car_type",
        "filter_auto_found",
        "filter_find_sequence",
        "filter_use_auto_find",
        "multiplier_car_col",
        "multiplier_car_row",
        "multiplier_car_configured",
        "soko78_house_owned",
        "show_ingame_overlay",
        "skip_remove_in_cycle",
    ):
        if field in data:
            setattr(settings, field, data[field])

    settings.timings.update({k: v for k, v in data.get("timings", {}).items() if k in TIMING_DEFAULTS})
    if settings.selected_car not in settings.cars:
        print(f"[WARN] Selected car '{settings.selected_car}' not in settings — falling back to default")
        settings.selected_car = _default_settings().selected_car
    return settings


def save(settings: Settings, path: pathlib.Path = SETTINGS_PATH) -> None:
    data = dataclasses.asdict(settings)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
