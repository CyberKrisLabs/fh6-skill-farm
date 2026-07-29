"""Tests for the cycle-loop/SP-math logic in farm_core/orchestrator.py.

_run_farm_inner is exercised (not run_farm, which additionally touches the real
log directory and spawns keys._watchdog_thread) by monkeypatching
orchestrator.run_phase itself with a fake that records every call and, for the
"unlock" phase, returns a scripted (ocr_sp, effective_unlocked) tuple — the
exact boundary _run_farm_inner talks to. orchestrator.TRANSITIONS is likewise
replaced with fakes that record which phase transitions actually fired.

Each scenario below reproduces a real bug documented in CLAUDE.md's "Known
Behaviors" section, using small hand-computable economics
(NUM_CARS=4, CAR_PRICE_CR=100, SKILL_POINTS_PER_CAR=30, SKILL_POINTS_CAP=120,
POINTS_PER_CHALLENGE=10, BUFFER_ENABLED=False unless a test says otherwise).
"""

import types

import pytest

from farm_core import config, keys, orchestrator


class _FakeRunPhase:
    """Records every run_phase call; returns scripted unlock results in order.

    stop_after, if set, calls keys._stop_event.set() right after recording the
    Nth call — the cycle loop's own stop-event checks then unwind it
    deterministically instead of looping forever on config values (e.g.
    cr=0/"unlimited") that never naturally terminate the loop.
    """

    def __init__(self, unlock_results=None, stop_after=None):
        self.calls = []
        self.unlock_results = list(unlock_results or [])
        self.stop_after = stop_after

    def __call__(self, name, args, challenge_iters=None, num_cars=None, expected_sp_hint=None, skip_remove=False):
        self.calls.append(
            {
                "name": name,
                "challenge_iters": challenge_iters,
                "num_cars": num_cars,
                "expected_sp_hint": expected_sp_hint,
                "skip_remove": skip_remove,
            }
        )
        if self.stop_after is not None and len(self.calls) >= self.stop_after:
            keys._stop_event.set()
        if name == "unlock":
            if self.unlock_results:
                return self.unlock_results.pop(0)
            return None
        return None

    def calls_for(self, name):
        return [c for c in self.calls if c["name"] == name]


@pytest.fixture
def small_economy(monkeypatch):
    """Small, hand-computable economics shared by every cycle-loop test."""
    monkeypatch.setattr(config, "NUM_CARS", 4)
    monkeypatch.setattr(config, "CAR_PRICE_CR", 100)
    monkeypatch.setattr(config, "SKILL_POINTS_PER_CAR", 30)
    monkeypatch.setattr(config, "SKILL_POINTS_CAP", 120)
    monkeypatch.setattr(config, "POINTS_PER_CHALLENGE", 10)
    monkeypatch.setattr(config, "BUFFER_ENABLED", False)
    monkeypatch.setattr(config.CFG, "skip_remove_in_cycle", False)


@pytest.fixture(autouse=True)
def clear_stop_event():
    keys._stop_event.clear()
    yield
    keys._stop_event.clear()


@pytest.fixture
def fake_transitions(monkeypatch):
    calls = []

    def _make(name):
        def _transition():
            calls.append(name)

        return _transition

    monkeypatch.setattr(orchestrator, "TRANSITIONS", {name: _make(name) for name in ("challenge", "buy", "unlock")})
    return calls


def test_cr_insufficient_on_cycle_1_runs_challenge_only(small_economy, fake_transitions, monkeypatch):
    """CLAUDE.md: cr too low for even one car used to still run Buy/Unlock
    transitions for phases that would do nothing (orchestrator.py:346-359)."""
    fake = _FakeRunPhase()
    monkeypatch.setattr(orchestrator, "run_phase", fake)

    orchestrator._run_farm_inner(
        start="challenge", skill_points=0, cars=-1, cars_have=0, cr=50, cycle=True, challenge_only=False
    )

    assert [c["name"] for c in fake.calls] == ["challenge"]
    assert fake.calls[0]["challenge_iters"] == 12  # ceil(120 / 10), no buffer
    assert fake_transitions == []


def test_cr_exhausted_mid_cycle_stops_after_final_challenge(small_economy, fake_transitions, monkeypatch):
    """CLAUDE.md: cycle 2+ already handled CR exhaustion; this is that same
    branch (orchestrator.py:363-369), verified via a real two-cycle run."""
    fake = _FakeRunPhase(unlock_results=[(None, 1)])
    monkeypatch.setattr(orchestrator, "run_phase", fake)

    orchestrator._run_farm_inner(
        start="challenge", skill_points=0, cars=-1, cars_have=0, cr=150, cycle=True, challenge_only=False
    )

    names = [c["name"] for c in fake.calls]
    assert names == ["challenge", "buy", "unlock", "remove", "challenge"]
    assert fake.calls_for("buy")[0]["num_cars"] == 1
    # Only one car was affordable this run, so the top-up challenge is sized
    # off that, not a full-cycle assumption.
    assert fake.calls_for("challenge")[1]["challenge_iters"] == 3  # ceil(1 * 30 / 10)
    assert fake_transitions == ["buy", "unlock", "challenge"]


def test_partial_cr_cycle_buys_fewer_than_num_cars(small_economy, fake_transitions, monkeypatch):
    """CLAUDE.md: a partial cycle should spend whatever CR remains rather than
    needing a full cycle's cost to run at all (orchestrator.py:370-380)."""
    fake = _FakeRunPhase(unlock_results=[(None, 4), (None, 2)])
    monkeypatch.setattr(orchestrator, "run_phase", fake)

    orchestrator._run_farm_inner(
        start="challenge", skill_points=0, cars=-1, cars_have=0, cr=600, cycle=True, challenge_only=False
    )

    buy_counts = [c["num_cars"] for c in fake.calls_for("buy")]
    assert buy_counts == [4, 2]  # cycle 1 full, cycle 2 partial (200 CR left / 100 CR each)


def test_residual_override_recomputed_every_cycle_not_just_first(small_economy, fake_transitions, monkeypatch):
    """CLAUDE.md: the exact residual-based top-up formula used to only fire on
    a session's first Unlock SP check; every cycle after that silently fell
    back to the cruder challenges_to_refill() estimate (orchestrator.py:
    426-451). Cycle 1's unlock reads nothing (ocr_sp=None); cycle 2's unlock
    DOES read SP — assert cycle 3's challenge count comes from that reading."""
    fake = _FakeRunPhase(
        unlock_results=[(None, 4), (80, 4)],
        stop_after=9,  # through cycle 3's challenge call, before its buy
    )
    monkeypatch.setattr(orchestrator, "run_phase", fake)

    orchestrator._run_farm_inner(
        start="challenge", skill_points=0, cars=-1, cars_have=0, cr=0, cycle=True, challenge_only=False
    )

    challenge_iters = [c["challenge_iters"] for c in fake.calls_for("challenge")]
    # cycle 3: residual = max(0, 80 - 4*30) = 0 -> ceil((120 - 0) / 10) = 12
    assert challenge_iters[2] == 12


def test_reduced_unlock_count_propagates_to_remove_and_next_refill(small_economy, fake_transitions, monkeypatch):
    """CLAUDE.md: when Unlock's SP ran out mid-unlock and effective_unlocked
    came back lower than planned, Remove used to still remove the original
    planned count (orchestrator.py:429,435), and the next cycle's refill used
    to inherit the same wrong 0/low count. Cycle 1 unlocks only 3 of a planned
    4 cars, with no OCR reading this time (ocr_sp=None)."""
    fake = _FakeRunPhase(unlock_results=[(None, 3)], stop_after=5)  # through cycle 2's challenge call
    monkeypatch.setattr(orchestrator, "run_phase", fake)

    orchestrator._run_farm_inner(
        start="challenge", skill_points=0, cars=-1, cars_have=0, cr=0, cycle=True, challenge_only=False
    )

    assert fake.calls_for("remove")[0]["num_cars"] == 3
    # cycle 2's challenge: challenges_to_refill(3) = ceil(3 * 30 / 10) = 9
    assert fake.calls_for("challenge")[1]["challenge_iters"] == 9


@pytest.mark.parametrize(
    ("buffer_enabled", "expected_line"),
    [
        (True, "Phase: CHALLENGE — 25 challenges + 1 buffer = 26 total"),
        (False, "Phase: CHALLENGE — 26 challenges (buffer disabled)"),
    ],
)
def test_run_phase_challenge_buffer_formatting(monkeypatch, capsys, buffer_enabled, expected_line):
    """CLAUDE.md: the "25 + 1 = 26" breakdown should only show with the buffer
    on; with it off the redundant "26 = 26" collapsed to a plain count."""
    monkeypatch.setattr(config, "BUFFER_ENABLED", buffer_enabled)
    monkeypatch.setattr("farm_core.challenge.run_challenge_iteration", lambda *a, **k: True)

    args = types.SimpleNamespace(skill_points=0, cars=0, cycle=False)
    orchestrator.run_phase("challenge", args, challenge_iters=26)

    assert expected_line in capsys.readouterr().out
