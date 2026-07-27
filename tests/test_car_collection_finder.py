"""compress_sequence() and _looks_like_numeric_decoration_row() are pure
logic (no keys, no OCR, no game dependency) — TDD-able like
farm_settings.py/config.py, per this project's testing philosophy for pure
functions.
"""

from farm_core.car_collection_finder import _looks_like_numeric_decoration_row, compress_sequence


def _row(*texts):
    return [{"text": t, "box": (0, 0, 1, 1) if t else None} for t in texts]


def test_collapses_burst_and_overshoot_correction():
    # A burst-scan that overshot by 6 and corrected — should collapse to the net delta.
    seq = [["down", 8], ["down", 8], ["down", 8], ["down", 8], ["up", 6]]
    assert compress_sequence(seq) == [["down", 26]]


def test_collapses_mixed_axes_independently():
    seq = [["down", 2], ["up", 1], ["left", 2]]
    assert compress_sequence(seq) == [["down", 1], ["left", 2]]


def test_zero_net_movement_on_an_axis_is_omitted():
    seq = [["down", 3], ["up", 3]]
    assert compress_sequence(seq) == []


def test_does_not_merge_across_non_navigation_actions():
    seq = [["backspace", 1], ["down", 11], ["down", 11], ["enter", 1], ["down", 2], ["left", 2]]
    assert compress_sequence(seq) == [["backspace", 1], ["down", 22], ["enter", 1], ["down", 2], ["left", 2]]


def test_real_multiplier_filter_sequence_shape():
    # Field-recorded shape (Performance Class delta, then a Car Type burst-scan
    # that overshot and corrected) — see farm_core.multiplier_filter_finder.
    seq = [
        ["y", 1],
        ["down", 9],
        ["enter", 1],
        ["down", 8],
        ["down", 8],
        ["down", 8],
        ["down", 8],
        ["up", 6],
        ["enter", 1],
        ["escape", 1],
    ]
    assert compress_sequence(seq) == [
        ["y", 1],
        ["down", 9],
        ["enter", 1],
        ["down", 26],
        ["enter", 1],
        ["escape", 1],
    ]


def test_empty_sequence():
    assert compress_sequence([]) == []


def test_sequence_with_no_navigation_is_unchanged():
    seq = [["enter", 1], ["escape", 1]]
    assert compress_sequence(seq) == [["enter", 1], ["escape", 1]]


def test_numeric_decoration_row_detected():
    # Field-recorded shape (2026-07-27): FH6's floating per-card CR-cost
    # overlay, sitting between two real car rows and inflating the
    # grid-row distance between them — see build_grid()'s docstring.
    assert _looks_like_numeric_decoration_row(_row("50 59", "", "", "109", "59"))
    assert _looks_like_numeric_decoration_row(_row("109", "", "", "509,", "10 9r"))
    assert _looks_like_numeric_decoration_row(_row("", "", "", "59", "59"))


def test_real_car_row_is_not_numeric_decoration():
    assert not _looks_like_numeric_decoration_row(
        _row("2020 Huracán Lamborghini EVO Aventador", "2021 LP Lamborghini 780-4 Ultimae")
    )


def test_empty_row_is_not_numeric_decoration():
    assert not _looks_like_numeric_decoration_row(_row("", "", "", "", ""))
