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
    assert settings.timings == farm_settings.TIMING_DEFAULTS


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    settings = farm_settings.load(path)  # defaults, file doesn't exist yet
    settings.car.car_collection_col = 2
    settings.car.car_collection_row = 64
    settings.car.car_collection_configured = True
    settings.challenge_share_code = "123456789"
    settings.timings["MENU_WAIT"] = 0.77

    farm_settings.save(settings, path)
    assert path.exists()

    reloaded = farm_settings.load(path)
    assert reloaded.car.car_collection_col == 2
    assert reloaded.car.car_collection_row == 64
    assert reloaded.car.car_collection_configured is True
    assert reloaded.challenge_share_code == "123456789"
    assert reloaded.timings["MENU_WAIT"] == 0.77
    # Untouched timing keys still fall back to the default
    assert reloaded.timings["NAV_WAIT"] == farm_settings.TIMING_DEFAULTS["NAV_WAIT"]


def test_load_merges_partial_car_data(tmp_path):
    """A saved car dict missing newer fields still merges over the built-in defaults."""
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"cars": {"lambo_revuelto": {"car_collection_row": 12}}}), encoding="utf-8")

    settings = farm_settings.load(path)
    assert settings.car.car_collection_row == 12
    # Fields not present in the file keep their built-in defaults
    assert settings.car.name == "Lamborghini Revuelto"
    assert settings.car.price_cr == 346_750


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
