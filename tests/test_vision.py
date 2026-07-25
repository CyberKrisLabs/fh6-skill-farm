"""Tests for farm_core/vision.py's SP OCR parsing — fixture-based, no real OCR
or screenshots (see CLAUDE.md testing philosophy: monkeypatch pyautogui.screenshot).
"""

from farm_core import vision


def _patch_ocr(monkeypatch, text: str) -> None:
    monkeypatch.setattr(vision, "_winrt_available", lambda: True)
    monkeypatch.setattr(vision, "_get_fh6_window_region", lambda: (0, 0, 800, 600))
    monkeypatch.setattr(vision.pyautogui, "screenshot", lambda region=None: object())

    async def _fake_ocr(img):
        return text

    monkeypatch.setattr(vision, "_winrt_ocr_async", _fake_ocr)


def test_read_available_sp_normal(monkeypatch):
    _patch_ocr(monkeypatch, "COST 1 360 0 AVAILABLE POINTS")
    assert vision._read_available_sp() == 360


def test_read_available_sp_icon_fused_as_trailing_zero(monkeypatch):
    """The skill-point icon is normally its own '0' token, skipped by the
    backward walk — but sometimes fuses onto the number instead of getting
    its own token (841 read as "8410"). That should still resolve to 841,
    not get discarded as out-of-range.
    """
    _patch_ocr(monkeypatch, "COST 1 8410 AVAILABLE POINTS")
    assert vision._read_available_sp() == 841


def test_read_available_sp_out_of_range_without_trailing_zero_stays_none(monkeypatch):
    """A bogus reading that doesn't end in 0 isn't "fixed" by stripping a digit —
    it's genuinely unreadable and should be ignored.
    """
    _patch_ocr(monkeypatch, "COST 1 1234 AVAILABLE POINTS")
    assert vision._read_available_sp() is None


def test_read_available_sp_missing_available_token_returns_none(monkeypatch):
    _patch_ocr(monkeypatch, "SOME UNRELATED SCREEN TEXT")
    assert vision._read_available_sp() is None
