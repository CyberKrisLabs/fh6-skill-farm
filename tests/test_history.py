"""Tests for farm_core/history.py — pure load/save/append logic, isolated from
the real %APPDATA%\\FH6SkillFarm\\ history file via an explicit tmp_path.
"""

import json

from farm_core import history


def _make_record(**overrides):
    defaults = dict(
        timestamp="2026-07-29_12-00-00",
        duration_seconds=120,
        car_name="Lamborghini Revuelto",
        start_phase="challenge",
        wheelspins=6,
        super_wheelspins=0,
        cr_gained=0,
        xp_gained=20000,
        cars_bought=2,
        cr_spent=730_000,
    )
    defaults.update(overrides)
    return history.HistoryRecord(**defaults)


def test_load_history_missing_file_returns_empty(tmp_path):
    assert history.load_history(tmp_path / "does_not_exist.json") == []


def test_append_and_load_roundtrip(tmp_path):
    path = tmp_path / "history.json"
    record = _make_record()
    history.append_record(record, path)

    loaded = history.load_history(path)
    assert loaded == [record]


def test_append_preserves_order_oldest_first(tmp_path):
    path = tmp_path / "history.json"
    first = _make_record(timestamp="2026-07-29_10-00-00")
    second = _make_record(timestamp="2026-07-29_11-00-00")
    history.append_record(first, path)
    history.append_record(second, path)

    loaded = history.load_history(path)
    assert [r.timestamp for r in loaded] == [first.timestamp, second.timestamp]


def test_append_trims_to_max_keep(tmp_path):
    path = tmp_path / "history.json"
    for i in range(5):
        history.append_record(_make_record(timestamp=f"run-{i}"), path, max_keep=3)

    loaded = history.load_history(path)
    assert [r.timestamp for r in loaded] == ["run-2", "run-3", "run-4"]


def test_load_history_skips_malformed_entry(tmp_path):
    path = tmp_path / "history.json"
    path.write_text(
        json.dumps(
            [
                {"timestamp": "bad-entry"},  # missing required fields
                {
                    "timestamp": "2026-07-29_12-00-00",
                    "duration_seconds": 60,
                    "car_name": "Lamborghini Revuelto",
                    "start_phase": "buy",
                    "wheelspins": 3,
                    "super_wheelspins": 0,
                    "cr_gained": 0,
                    "xp_gained": 10000,
                    "cars_bought": 1,
                    "cr_spent": 365_000,
                },
            ]
        ),
        encoding="utf-8",
    )

    loaded = history.load_history(path)
    assert len(loaded) == 1
    assert loaded[0].start_phase == "buy"


def test_load_history_tolerates_unparseable_json(tmp_path):
    path = tmp_path / "history.json"
    path.write_text("not valid json", encoding="utf-8")
    assert history.load_history(path) == []


def test_save_history_overwrites_existing_file(tmp_path):
    path = tmp_path / "history.json"
    history.append_record(_make_record(), path)
    history.save_history([], path)
    assert history.load_history(path) == []
