#!/usr/bin/env python3
"""Persistent user settings for the FH6 skill farm.

Stored in skill_farm_settings.json under APP_DATA_DIR. Grid positions (Car
Collection / owned-car list) differ per user account, so they live here
instead of in code. Per-car unlock key sequences stay in farm_core/unlock.py
(UNLOCK_SEQUENCES), keyed by CarConfig.car_id.
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
    "LOADING_CHALLENGE_WAIT": 25,
    "LOADING_RETRY_WAIT": 25,
    "LOADING_RESET_WAIT": 20,
    "LOADING_NON_PRELOADED_CAR_WAIT": 12,
    "LOADING_EXIT_TO_GAME_WAIT": 9,
}


@dataclasses.dataclass
class CarConfig:
    car_id: str  # keys UNLOCK_SEQUENCES in skill_farm.py
    name: str
    price_cr: int
    sp_to_unlock: int  # skill points spent to reach the wheelspin skills
    super_wheelspins: int  # yield per car
    wheelspins: int  # yield per car
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


@dataclasses.dataclass
class Settings:
    selected_car: str
    cars: dict[str, CarConfig]
    challenge_share_code: str
    points_per_challenge: int  # with the 9x multiplier car active
    # The 9x multiplier car is found by filtering the owned-car list to R
    # class + Retro Rally. The filter is a checkbox list — enter toggles a
    # box without closing the list — so both rows are counted as down presses
    # from the TOP of the filter list (absolute, not relative to each other).
    # User-specific: depends on how many categories precede these two.
    filter_r_class_row: int
    filter_retro_rally_row: int
    # Position of the multiplier car within the filtered "My Cars" grid
    # (3 rows per column, dynamic columns) — user-specific.
    multiplier_car_col: int
    multiplier_car_row: int
    # True once the user has saved the filter rows + position via the
    # Settings tab — see CarConfig.car_collection_configured for why 0 can't
    # be used as an "unset" sentinel here either.
    multiplier_car_configured: bool
    # User-editable wait constants (Timings tab) — see TIMING_DEFAULTS.
    timings: dict[str, float]

    @property
    def car(self) -> CarConfig:
        return self.cars[self.selected_car]


def _default_settings() -> Settings:
    lambo = CarConfig(
        car_id="lambo_revuelto",
        name="Lamborghini Revuelto",
        price_cr=346_750,
        sp_to_unlock=40,
        super_wheelspins=1,
        wheelspins=3,
        car_collection_col=0,  # TODO: set per account (Settings tab)
        car_collection_row=0,
        car_collection_configured=False,
    )
    return Settings(
        selected_car="lambo_revuelto",
        cars={lambo.car_id: lambo},
        challenge_share_code="661885885",
        points_per_challenge=10,  # working number — verify in-game
        filter_r_class_row=0,  # TODO: set per account (Settings tab)
        filter_retro_rally_row=0,
        multiplier_car_col=0,
        multiplier_car_row=0,
        multiplier_car_configured=False,
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
        base = settings.cars.get(car_id)
        merged = dataclasses.asdict(base) if base else {"car_id": car_id}
        merged.update({k: v for k, v in car_data.items() if k in car_fields})
        try:
            settings.cars[car_id] = CarConfig(**merged)
        except TypeError as exc:
            print(f"[WARN] Skipping malformed car '{car_id}' in settings: {exc}")

    for field in (
        "selected_car",
        "challenge_share_code",
        "points_per_challenge",
        "filter_r_class_row",
        "filter_retro_rally_row",
        "multiplier_car_col",
        "multiplier_car_row",
        "multiplier_car_configured",
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
