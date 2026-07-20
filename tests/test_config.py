"""Tests for the pure buffer-math helpers in farm_core/config.py.

Everything else in config.py (CFG load, refresh_config/refresh_timings) touches
the real %APPDATA%\\FH6SkillFarm\\ settings file as a side effect of import, so
it's exercised via farm_settings' own tests instead of duplicated here.
"""

import pytest

from farm_core import config


@pytest.mark.parametrize(
    ("challenges", "expected_extra"),
    [
        (0, 0),
        (1, 1),
        (24, 1),
        (25, 1),
        (26, 2),
        (50, 2),
        (75, 3),
        (100, 4),
    ],
)
def test_buffer_extra(challenges, expected_extra):
    assert config._buffer_extra(challenges) == expected_extra


def test_buffered_adds_extra_when_enabled(monkeypatch):
    monkeypatch.setattr(config, "BUFFER_ENABLED", True)
    assert config._buffered(25) == 26
    assert config._buffered(100) == 104


def test_buffered_passthrough_when_disabled(monkeypatch):
    monkeypatch.setattr(config, "BUFFER_ENABLED", False)
    assert config._buffered(25) == 25
    assert config._buffered(100) == 100


def test_buffered_zero_is_unaffected(monkeypatch):
    monkeypatch.setattr(config, "BUFFER_ENABLED", True)
    assert config._buffered(0) == 0
