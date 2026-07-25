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
    "LOADING_AFTER_CHALLENGE_EXIT_WAIT": 18,
    "LOADING_TRAVEL_WAIT": 10,
    "LOADING_CHALLENGE_WAIT": 25,
    "LOADING_RETRY_WAIT": 23.5,
    "LOADING_EXIT_TO_GAME_WAIT": 9,
}

# Menu-navigation waits (MENU_WAIT/NAV_WAIT/PAGE_WAIT/TYPING_WAIT) and most
# LOADING_* waits are paced by the game's own menu animations, which measured
# identically on a tested desktop and a tested laptop running FH6 at 1024x768
# for smoothness. The two that DID differ were both genuine asset-loading
# waits: LOADING_TRAVEL_WAIT (Free Roam -> House/Festival fast-travel) and
# LOADING_CHALLENGE_WAIT (challenge search -> loaded into the challenge).
# "Fast" matches the tested desktop; "Slow" matches the tested laptop; "Mid"
# splits the difference for hardware in between. Everything else is left at
# TIMING_DEFAULTS across all three tiers on purpose — there's no measurement
# yet showing those need to vary, and inventing numbers without evidence
# would just be a guess dressed up as a preset.
TIMING_PRESETS: dict[str, dict[str, float]] = {
    "Fast": dict(TIMING_DEFAULTS),
    "Mid": {
        **TIMING_DEFAULTS,
        "LOADING_TRAVEL_WAIT": 11.0,
        "LOADING_CHALLENGE_WAIT": 27.0,
    },
    "Slow": {
        **TIMING_DEFAULTS,
        "LOADING_TRAVEL_WAIT": 12.0,
        "LOADING_CHALLENGE_WAIT": 29.0,
    },
}


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
    sp_to_unlock: int  # skill points spent to reach the wheelspin skills
    super_wheelspins: int  # yield per car
    wheelspins: int  # yield per car


CAR_CATALOG: dict[str, CarInfo] = {
    "lambo_revuelto": CarInfo(
        car_id="lambo_revuelto",
        name="Lamborghini Revuelto",
        price_cr=365_000,
        sp_to_unlock=39,
        super_wheelspins=1,
        wheelspins=3,
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
    car_collection_col: int
    car_collection_row: int
    car_collection_configured: bool


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
    # Position of the multiplier car within the filtered "My Cars" grid
    # (3 rows per column, dynamic columns) — user-specific. Also stored
    # 0-based / shown 1-based in the UI, same as the fields above.
    multiplier_car_col: int
    multiplier_car_row: int
    # True once the user has saved the filter rows + position via the
    # Settings tab — see CarConfig.car_collection_configured for why 0 can't
    # be used as an "unset" sentinel here either.
    multiplier_car_configured: bool
    # Whether the user has FH6's "What's Next" (HUD & Gameplay settings) turned
    # on. When it is, an extra Select/Back screen appears after exiting the
    # challenge, before landing back in Free Roam — see
    # farm_core.challenge.WHATS_NEXT_EXIT_WAIT. Genuinely per-user (depends on
    # the player's own in-game settings), so it belongs here, not in code.
    whats_next_enabled: bool
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
            car_collection_col=user.car_collection_col,
            car_collection_row=user.car_collection_row,
            car_collection_configured=user.car_collection_configured,
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
        multiplier_car_col=0,
        multiplier_car_row=0,
        multiplier_car_configured=False,
        whats_next_enabled=False,
        soko78_house_owned=False,
        show_ingame_overlay=False,
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
        "multiplier_car_col",
        "multiplier_car_row",
        "multiplier_car_configured",
        "whats_next_enabled",
        "soko78_house_owned",
        "show_ingame_overlay",
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
