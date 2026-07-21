"""Tests for farm_settings.py — pure load/save logic, isolated from the real
%APPDATA%\\FH6SkillFarm\\ settings file via an explicit tmp_path.
"""

import json

import farm_settings


def test_default_settings_when_file_missing(tmp_path):
    settings = farm_settings.load(tmp_path / "does_not_exist.json")
    assert settings.selected_car == "lambo_revuelto"
    assert settings.car.car_collection_configured is False
    assert settings.multiplier_car_configured is False
    assert settings.whats_next_enabled is False
    assert settings.soko78_house_owned is False
    assert settings.car.price_cr == 365_000  # base price, no discount by default
    assert settings.timings == farm_settings.TIMING_DEFAULTS


def test_effective_price_cr_no_discount():
    assert farm_settings.effective_price_cr(365_000, False) == 365_000


def test_effective_price_cr_with_soko78_discount():
    assert farm_settings.effective_price_cr(365_000, True) == 346_750


def test_settings_car_price_reflects_soko78_house_owned(tmp_path):
    settings = farm_settings.load(tmp_path / "does_not_exist.json")
    assert settings.car.price_cr == 365_000
    settings.soko78_house_owned = True
    assert settings.car.price_cr == 346_750


def test_whats_next_enabled_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"whats_next_enabled": True}), encoding="utf-8")

    settings = farm_settings.load(path)
    assert settings.whats_next_enabled is True


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    settings = farm_settings.load(path)  # defaults, file doesn't exist yet
    car = settings.cars[settings.selected_car]  # mutable per-car user settings; settings.car is read-only
    car.car_collection_col = 2
    car.car_collection_row = 64
    car.car_collection_configured = True
    settings.filter_performance_class_row = 7
    settings.timings["MENU_WAIT"] = 0.77

    farm_settings.save(settings, path)
    assert path.exists()

    reloaded = farm_settings.load(path)
    assert reloaded.car.car_collection_col == 2
    assert reloaded.car.car_collection_row == 64
    assert reloaded.car.car_collection_configured is True
    assert reloaded.filter_performance_class_row == 7
    assert reloaded.timings["MENU_WAIT"] == 0.77
    # Untouched timing keys still fall back to the default
    assert reloaded.timings["NAV_WAIT"] == farm_settings.TIMING_DEFAULTS["NAV_WAIT"]


def test_load_merges_partial_car_data(tmp_path):
    """A saved car dict only overrides user fields (car_collection_row); catalog
    facts (name, price_cr) always come from CAR_CATALOG in code, never the file.
    """
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"cars": {"lambo_revuelto": {"car_collection_row": 12}}}), encoding="utf-8")

    settings = farm_settings.load(path)
    assert settings.car.car_collection_row == 12
    assert settings.car.name == "Lamborghini Revuelto"
    assert settings.car.price_cr == 365_000  # base price — no Soko 78 discount by default


def test_load_ignores_catalog_fields_in_saved_car_data(tmp_path):
    """Catalog facts stored in an old settings file (e.g. a stale sp_to_unlock)
    never override CAR_CATALOG — only user fields are read back from the file.
    """
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"cars": {"lambo_revuelto": {"sp_to_unlock": 999, "price_cr": 1}}}), encoding="utf-8")

    settings = farm_settings.load(path)
    assert settings.car.sp_to_unlock == farm_settings.CAR_CATALOG["lambo_revuelto"].sp_to_unlock
    assert settings.car.price_cr == farm_settings.CAR_CATALOG["lambo_revuelto"].price_cr


def test_load_skips_unknown_car(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"cars": {"some_removed_car": {"car_collection_row": 5}}}), encoding="utf-8")

    settings = farm_settings.load(path)
    assert "some_removed_car" not in settings.cars


def test_load_falls_back_on_bad_json(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{ this is not valid json", encoding="utf-8")

    settings = farm_settings.load(path)
    assert settings.selected_car == "lambo_revuelto"


def test_load_falls_back_when_selected_car_unknown(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"selected_car": "some_car_that_does_not_exist"}), encoding="utf-8")

    settings = farm_settings.load(path)
    assert settings.selected_car == "lambo_revuelto"


def test_timings_partial_merge(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"timings": {"MENU_WAIT": 1.5}}), encoding="utf-8")

    settings = farm_settings.load(path)
    assert settings.timings["MENU_WAIT"] == 1.5
    for key, default in farm_settings.TIMING_DEFAULTS.items():
        if key != "MENU_WAIT":
            assert settings.timings[key] == default


def test_timings_unknown_key_ignored(tmp_path):
    """Unknown timing keys in the file are dropped, not merged in."""
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"timings": {"NOT_A_REAL_TIMING": 5.0}}), encoding="utf-8")

    settings = farm_settings.load(path)
    assert "NOT_A_REAL_TIMING" not in settings.timings
