"""Farm tab: Start From / Options / Summary / Start-Stop / Log."""

import math
import sys
import threading

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCursor
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from farm_core import config, keys, orchestrator
from farm_ui.guide_content import START_FROM_INFO as _START_FROM_INFO
from farm_ui.widgets import _CRSpinBox, _fixed_label, _info_button, _log_bridge, _sep, _small, _StdoutCapture

# Starting from Main/Challenge always drives at least one fresh, undriven
# challenge before any other phase runs. Entering the full SKILL_POINTS_CAP
# there computes 0 challenges needed, which skips the race entirely and still
# fires the challenge->buy transition — which assumes you already exited a
# finished race, not that you're sitting paused in an undriven one. Capping
# the input below the cap guarantees at least 1 challenge always runs first.
_CHALLENGE_START_SP_CAP = 990

# ── Timing constants (re-measured from a full 100-challenge cycle log,
# 2026-07-20, post-tuning race flow — CHALLENGE_HOLD_SECONDS=27 + ease-in taps).
# _SECS_TRANS_INIT has no fresh data (that run started from "buy", not "main")
# and is left at its prior estimate.
_SECS_PER_CHALLENGE = 59.5  # one challenge run — ~90 clean samples, tight 58-63s band
_SECS_PER_BUY = 2.5  # one car purchase
_SECS_PER_UNLOCK = 39.0  # one car skill unlock — exact every steady-state iteration
_SECS_PER_REMOVE = 3.0  # one car removal — exact every iteration
_SECS_REMOVE_FIXED = 38  # safety switch + navigate back (not per-car)
_SECS_TRANS_INIT = 46  # main menu → challenge (search + load) — not re-measured
_SECS_TRANS_CHALLENGE = 40  # remove done → challenge start (cycle 2+) — varies with search poll luck
_SECS_TRANS_BUY = 46  # challenge end → auto show
_SECS_TRANS_UNLOCK = 7  # buy done → car list — exact


def _fmt_time(secs: float) -> str:
    m = round(secs) // 60
    h, m = divmod(m, 60)
    return f"{h}h {m}m" if h else f"{m}m"


def _noncycle_secs(n: int) -> int:
    """Buy+unlock+remove time for n cars including transitions."""
    return int(
        _SECS_TRANS_BUY
        + n * _SECS_PER_BUY
        + _SECS_TRANS_UNLOCK
        + n * _SECS_PER_UNLOCK
        + _SECS_REMOVE_FIXED
        + n * _SECS_PER_REMOVE
    )


class FarmTabMixin:
    """Mixed into SkillFarmWindow — expects self._settings_root/self._timings_root
    (from SettingsTabMixin/TimingsTabMixin) to exist by the time _set_controls runs.
    """

    def _build_farm_tab(self) -> QWidget:
        root = QWidget()
        vbox = QVBoxLayout(root)
        vbox.setContentsMargins(16, 16, 16, 12)
        vbox.setSpacing(10)

        # Title
        title = QLabel("FH6 SKILL FARM")
        title.setProperty("class", "app-title")
        title.setAlignment(Qt.AlignCenter)
        sub = QLabel("WHEELSPIN GRIND — CHALLENGE FARM")
        sub.setProperty("class", "app-subtitle")
        sub.setAlignment(Qt.AlignCenter)
        vbox.addWidget(title)
        vbox.addWidget(sub)
        vbox.addWidget(_sep())

        # ── Start From ────────────────────────────────────────────────────────
        phase_box = QGroupBox("START FROM")
        phase_col = QVBoxLayout(phase_box)
        phase_col.setSpacing(6)
        phase_row = QHBoxLayout()
        phase_row.setSpacing(16)
        self._phase_group = QButtonGroup(self)
        self._radios: dict[str, QRadioButton] = {}
        for key, label in [
            ("main", "Main Menu"),
            ("challenge", "Challenge"),
            ("buy", "Buy"),
            ("unlock", "Unlock"),
            ("remove", "Remove"),
        ]:
            rb = QRadioButton(label)
            self._radios[key] = rb
            self._phase_group.addButton(rb)
            pair = QHBoxLayout()
            pair.setSpacing(2)
            pair.addWidget(rb)
            pair.addWidget(_info_button(lambda checked=False, k=key: self._show_start_from_info(k)))
            phase_row.addLayout(pair)
        phase_row.addStretch()
        self._radios["main"].setChecked(True)
        phase_col.addLayout(phase_row)

        self._challenge_only_chk = QCheckBox("Challenge Only")
        phase_col.addWidget(self._challenge_only_chk)
        self._challenge_only_hint = _small(
            "runs just the challenge until Skill Points reaches ~999 — all other starting points disabled"
        )
        phase_col.addWidget(self._challenge_only_hint)
        vbox.addWidget(phase_box)

        # ── Options ───────────────────────────────────────────────────────────
        opts_box = QGroupBox("OPTIONS")
        opts = QVBoxLayout(opts_box)
        opts.setSpacing(8)

        # Skill Points
        sp_row = QHBoxLayout()
        sp_row.addWidget(_fixed_label("Current Skill Points", 160))
        self._sp_spin = QSpinBox()
        self._sp_spin.setRange(0, config.SKILL_POINTS_CAP)
        self._sp_spin.setValue(0)
        self._sp_spin.setFixedWidth(80)
        sp_row.addWidget(self._sp_spin)
        self._sp_range_lbl = _small(f"0 – {config.SKILL_POINTS_CAP}")
        sp_row.addWidget(self._sp_range_lbl)
        sp_row.addStretch()
        opts.addLayout(sp_row)

        # Cars already have (buy start only) — hidden otherwise
        self._have_lbl = _fixed_label("Cars Owned", 160)
        self._have_spin = QSpinBox()
        self._have_spin.setRange(0, config.NUM_CARS)
        self._have_spin.setValue(0)
        self._have_spin.setFixedWidth(80)
        self._have_range_lbl = _small(f"0 – {config.NUM_CARS}  (optional)")
        have_row = QHBoxLayout()
        have_row.addWidget(self._have_lbl)
        have_row.addWidget(self._have_spin)
        have_row.addWidget(self._have_range_lbl)
        have_row.addStretch()
        self._have_widgets = [self._have_lbl, self._have_spin, self._have_range_lbl]
        opts.addLayout(have_row)

        # Cars — label/range change per phase:
        #   buy:          "Cars to Buy"  (0..sp//30, auto-filled from SP)
        #   unlock/remove: "Cars Owned" (1..NUM_CARS, direct count)
        self._cars_lbl = _fixed_label("Cars to Buy", 160)
        self._cars_spin = QSpinBox()
        self._cars_spin.setRange(0, config.NUM_CARS)
        self._cars_spin.setValue(config.NUM_CARS)
        self._cars_spin.setFixedWidth(80)
        self._cars_range_lbl = _small(f"0 – {config.NUM_CARS}")
        cars_row = QHBoxLayout()
        cars_row.addWidget(self._cars_lbl)
        cars_row.addWidget(self._cars_spin)
        cars_row.addWidget(self._cars_range_lbl)
        cars_row.addStretch()
        self._cars_widgets = [self._cars_lbl, self._cars_spin, self._cars_range_lbl]
        opts.addLayout(cars_row)

        # Credits
        cr_row = QHBoxLayout()
        cr_row.addWidget(_fixed_label("Current CR", 160))
        self._cr_spin = _CRSpinBox()
        self._cr_spin.setRange(0, 999_999_999)
        self._cr_spin.setValue(0)
        self._cr_spin.setSingleStep(100_000)
        self._cr_spin.setFixedWidth(120)
        cr_row.addWidget(self._cr_spin)
        cr_row.addWidget(_small("0 = cycle forever"))
        cr_row.addStretch()
        opts.addLayout(cr_row)

        # Countdown
        cd_row = QHBoxLayout()
        cd_row.addWidget(_fixed_label("Countdown", 160))
        self._cd_spin = QSpinBox()
        self._cd_spin.setRange(1, 30)
        self._cd_spin.setValue(5)
        self._cd_spin.setFixedWidth(80)
        cd_row.addWidget(self._cd_spin)
        cd_row.addWidget(_small("seconds before start"))
        cd_row.addStretch()
        opts.addLayout(cd_row)

        # Challenge buffer
        buf_row = QHBoxLayout()
        self._buffer_chk = QCheckBox("Challenge Buffer")
        self._buffer_chk.setChecked(False)
        buf_row.addWidget(self._buffer_chk)
        buf_row.addWidget(_small("adds ~4% extra challenges to offset low-point runs"))
        buf_row.addStretch()
        opts.addLayout(buf_row)

        vbox.addWidget(opts_box)

        # ── Summary ───────────────────────────────────────────────────────────
        self._summary = QLabel()
        self._summary.setProperty("class", "status-label")
        self._summary.setWordWrap(True)
        self._summary.setMinimumHeight(40)
        vbox.addWidget(self._summary)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("START")
        self._start_btn.setProperty("class", "primary-btn")
        self._start_btn.setMinimumHeight(40)
        self._stop_btn = QPushButton("STOP")
        self._stop_btn.setProperty("class", "danger-btn")
        self._stop_btn.setMinimumHeight(40)
        self._stop_btn.setEnabled(False)  # enabled when farm is running or counting down
        btn_row.addWidget(self._start_btn, 3)
        btn_row.addWidget(self._stop_btn, 1)
        vbox.addLayout(btn_row)

        # Status line
        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setProperty("class", "small-label")
        vbox.addWidget(self._status)

        vbox.addWidget(_sep())

        log_header_row = QHBoxLayout()
        log_hdr = QLabel("LOG")
        log_hdr.setProperty("class", "section-label")
        log_header_row.addWidget(log_hdr)
        log_header_row.addStretch()
        self._elapsed_lbl = QLabel("")
        self._elapsed_lbl.setProperty("class", "small-label")
        self._elapsed_lbl.setAlignment(Qt.AlignRight)
        log_header_row.addWidget(self._elapsed_lbl)
        vbox.addLayout(log_header_row)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        vbox.addWidget(self._log, 1)

        # Wire signals
        self._phase_group.buttonToggled.connect(
            lambda _btn, checked: (self._update_fields(), self._update_summary()) if checked else None
        )
        self._sp_spin.valueChanged.connect(self._on_sp_changed)
        self._have_spin.valueChanged.connect(self._on_have_changed)
        self._cars_spin.valueChanged.connect(self._update_summary)
        self._cr_spin.valueChanged.connect(self._update_summary)
        self._buffer_chk.toggled.connect(self._update_summary)
        self._challenge_only_chk.toggled.connect(self._on_challenge_only_toggled)
        self._start_btn.clicked.connect(self._on_start)
        self._stop_btn.clicked.connect(self._on_stop)

        return root

    # ── Dynamic visibility ─────────────────────────────────────────────────────

    def _phase(self) -> str:
        for k, rb in self._radios.items():
            if rb.isChecked():
                return k
        return "buy"

    def _show_start_from_info(self, key: str) -> None:
        label, text = _START_FROM_INFO[key]
        dlg = QMessageBox(self)
        dlg.setWindowTitle(f"Start From: {label}")
        dlg.setText(f"<b>Start From: {label}</b>")
        dlg.setInformativeText(text)
        dlg.setIcon(QMessageBox.Icon.Information)
        dlg.exec()

    def _on_challenge_only_toggled(self, checked: bool) -> None:
        for key in ("main", "buy", "unlock", "remove"):
            self._radios[key].setEnabled(not checked)
        self._update_fields()
        self._update_summary()

    def _update_fields(self) -> None:
        phase = self._phase()
        is_challenge = phase == "challenge"
        self._challenge_only_chk.setVisible(is_challenge)
        self._challenge_only_hint.setVisible(is_challenge)
        if not is_challenge and self._challenge_only_chk.isChecked():
            self._challenge_only_chk.setChecked(False)

        sp_cap = _CHALLENGE_START_SP_CAP if phase in ("main", "challenge") else config.SKILL_POINTS_CAP
        self._sp_spin.setRange(0, sp_cap)
        self._sp_range_lbl.setText(f"0 – {sp_cap}")

        if phase in ("main", "challenge"):
            for w in self._have_widgets:
                w.setVisible(False)
            for w in self._cars_widgets:
                w.setVisible(False)
        elif phase == "buy":
            for w in self._have_widgets:
                w.setVisible(True)
            self._cars_lbl.setText("Cars to Buy")
            self._update_buy_cars_range()
            for w in self._cars_widgets:
                w.setVisible(True)
        else:  # unlock / remove
            for w in self._have_widgets:
                w.setVisible(False)
            self._cars_lbl.setText("Cars Owned" if phase == "unlock" else "Cars to Remove")
            self._cars_spin.blockSignals(True)
            self._cars_spin.setRange(1, config.NUM_CARS)
            if self._cars_spin.value() < 1:
                self._cars_spin.setValue(config.NUM_CARS)
            self._cars_spin.blockSignals(False)
            self._cars_range_lbl.setText(f"1 – {config.NUM_CARS}")
            for w in self._cars_widgets:
                w.setVisible(True)

    def _update_buy_cars_range(self) -> None:
        sp = self._sp_spin.value()
        have = self._have_spin.value()
        total_from_sp = min(sp // config.SKILL_POINTS_PER_CAR, config.NUM_CARS) if sp > 0 else config.NUM_CARS
        max_buy = max(0, total_from_sp - have)
        self._cars_spin.blockSignals(True)
        self._cars_spin.setRange(0, max_buy)
        self._cars_spin.setValue(max_buy)
        self._cars_spin.blockSignals(False)
        self._cars_range_lbl.setText(f"0 – {max_buy}  (0 = skip buy)")

    def _on_sp_changed(self) -> None:
        if self._phase() == "buy":
            self._update_buy_cars_range()
        self._update_summary()

    def _on_have_changed(self) -> None:
        if self._phase() == "buy":
            self._update_buy_cars_range()
        self._update_summary()

    # ── Summary line ───────────────────────────────────────────────────────────

    def _update_summary(self) -> None:
        phase = self._phase()
        sp = self._sp_spin.value()
        cr = self._cr_spin.value()
        parts: list[str] = []

        def _buf(challenges: int) -> int:
            if not self._buffer_chk.isChecked():
                return challenges
            return challenges + config._buffer_extra(challenges)

        # ── time estimate helpers ───────────────────────────────────────────
        def _simulate_subsequent_cycles(first_buy_count: int, initial_last_unlock: int, first_subsequent_ci=None):
            """Per-cycle (buy_count, challenge_count_before_it) for cycle 2
            onward, mirroring orchestrator.py's cycle loop exactly: subsequent
            cycles can be partial (not "a full NUM_CARS cycle or nothing" —
            e.g. leftover CR after a full cycle still buys however many more
            cars it affords), and each cycle's challenge phase is sized to
            whatever the PREVIOUS cycle actually unlocked
            (config.challenges_to_refill), not a fixed constant — EXCEPT the
            very first subsequent cycle when starting from Buy/Unlock/Remove:
            cycle 1 never runs a challenge phase there, so cycle 2's challenge
            is the session's true first one (challenge_iters_first, passed in
            as first_subsequent_ci), not a refill of an already-capped SP
            total. first_buy_count is cycle 1's actual buy count (0 for
            Unlock/Remove starts, which never buy in cycle 1) — used only to
            compute CR spent; initial_last_unlock is cycle 1's actual unlock
            count (matches orchestrator.py's own last_unlock_count seed) and
            can differ from first_buy_count (e.g. Buy start's cars_have).
            Returns (cycles, final_top_up); cr must be > 0 (caller handles
            cr<=0).
            """
            cycles = []
            remaining = cr - first_buy_count * config.CAR_PRICE_CR
            last_unlock = initial_last_unlock
            first_iteration = True
            while remaining >= config.CAR_PRICE_CR:
                if first_iteration and first_subsequent_ci is not None:
                    ci = first_subsequent_ci
                else:
                    ci = _buf(config.challenges_to_refill(last_unlock))
                first_iteration = False
                n = min(remaining // config.CAR_PRICE_CR, config.NUM_CARS)
                cycles.append((n, ci))
                remaining -= n * config.CAR_PRICE_CR
                last_unlock = n
            final_top_up = _buf(config.challenges_to_refill(last_unlock))
            return cycles, final_top_up

        def _cycle_tag(first_buy_count: int, initial_last_unlock: int, first_subsequent_ci=None) -> str:
            if cr <= 0:
                return "↺ forever"
            sim_cycles, _ = _simulate_subsequent_cycles(first_buy_count, initial_last_unlock, first_subsequent_ci)
            # Only count cycle 1 as a "loop" if it actually buys something —
            # Unlock/Remove starts never buy in cycle 1 (first_buy_count is
            # always 0 there), and an explicit "Buy 0" skip shouldn't count
            # as a loop either.
            loops = (1 if first_buy_count > 0 else 0) + len(sim_cycles)
            return f"↺ {loops} loop{'s' if loops != 1 else ''}  ({cr:,} CR)"

        def _time_main_challenge(init_secs: int, first_challenges: int, first_buy_count: int) -> str:
            t1 = init_secs + first_challenges * _SECS_PER_CHALLENGE + _noncycle_secs(first_buy_count)
            if cr <= 0:
                return f"~{_fmt_time(t1)}/cycle"
            sim_cycles, final_top_up = _simulate_subsequent_cycles(first_buy_count, first_buy_count)
            t = t1
            for n, ci in sim_cycles:
                t += _SECS_TRANS_CHALLENGE + ci * _SECS_PER_CHALLENGE + _noncycle_secs(n)
            # CR always runs out eventually here — once the last affordable
            # buy/unlock/remove cycle finishes, the farm runs one more
            # challenge-only top-up to cap skill points before stopping
            # (orchestrator.py's "CR exhausted" branch), sized to whatever SP
            # that last cycle's unlock actually spent.
            t += _SECS_TRANS_CHALLENGE + final_top_up * _SECS_PER_CHALLENGE
            return f"~{_fmt_time(t)} total"

        def _time_buy(to_buy: int, unlock_n: int, first_challenges: int) -> str:
            t_partial = int(
                to_buy * _SECS_PER_BUY
                + _SECS_TRANS_UNLOCK
                + unlock_n * _SECS_PER_UNLOCK
                + _SECS_REMOVE_FIXED
                + unlock_n * _SECS_PER_REMOVE
            )
            if cr <= 0:
                tn = (
                    _SECS_TRANS_CHALLENGE
                    + _buf(config.CHALLENGES_SUBSEQUENT) * _SECS_PER_CHALLENGE
                    + _noncycle_secs(config.NUM_CARS)
                )
                return f"~{_fmt_time(t_partial)}, then ~{_fmt_time(tn)}/cycle"
            sim_cycles, final_top_up = _simulate_subsequent_cycles(
                to_buy, unlock_n, first_subsequent_ci=first_challenges
            )
            t = t_partial
            for n, ci in sim_cycles:
                t += _SECS_TRANS_CHALLENGE + ci * _SECS_PER_CHALLENGE + _noncycle_secs(n)
            t += _SECS_TRANS_CHALLENGE + final_top_up * _SECS_PER_CHALLENGE
            return f"~{_fmt_time(t)} total"

        def _time_unlock_remove(phase: str, n: int, first_challenges: int) -> str:
            if phase == "unlock":
                t_partial = int(n * _SECS_PER_UNLOCK + _SECS_REMOVE_FIXED + n * _SECS_PER_REMOVE)
            else:
                t_partial = int(_SECS_REMOVE_FIXED + n * _SECS_PER_REMOVE)
            if cr <= 0:
                tn = (
                    _SECS_TRANS_CHALLENGE
                    + _buf(config.CHALLENGES_SUBSEQUENT) * _SECS_PER_CHALLENGE
                    + _noncycle_secs(config.NUM_CARS)
                )
                return f"~{_fmt_time(t_partial + first_challenges * _SECS_PER_CHALLENGE)}, then ~{_fmt_time(tn)}/cycle"
            # Unlock/Remove starts never buy in cycle 1 (first_buy_count=0);
            # initial_last_unlock=n matches orchestrator.py's own seed.
            sim_cycles, final_top_up = _simulate_subsequent_cycles(0, n, first_subsequent_ci=first_challenges)
            t = t_partial + int(first_challenges * _SECS_PER_CHALLENGE)
            for cn, ci in sim_cycles:
                t += _SECS_TRANS_CHALLENGE + ci * _SECS_PER_CHALLENGE + _noncycle_secs(cn)
            t += _SECS_TRANS_CHALLENGE + final_top_up * _SECS_PER_CHALLENGE
            return f"~{_fmt_time(t)} total"

        # ── per-phase summary + time ────────────────────────────────────────
        def _buf_suffix(buf_r: int) -> str:
            return f" + {buf_r} buffer" if buf_r > 0 else ""

        def _challenge_lbl(base_c: int, buf_c: int) -> str:
            if base_c == 0:
                return "Challenge 0×"
            return f"Challenge {base_c}{_buf_suffix(buf_c)} = {base_c + buf_c}×"

        if phase in ("main", "challenge"):
            if phase == "main":
                parts.append("Navigate to challenge")
            base = (
                math.ceil((config.SKILL_POINTS_CAP - sp) / config.POINTS_PER_CHALLENGE)
                if sp < config.SKILL_POINTS_CAP
                else 0
            )
            challenges = _buf(base)
            init_secs = _SECS_TRANS_INIT if phase == "main" else 0
            if self._challenge_only_chk.isChecked():
                parts.append(_challenge_lbl(base, challenges - base))
                parts.append(f"~{_fmt_time(init_secs + challenges * _SECS_PER_CHALLENGE)} total")
            else:
                # By the time Buy runs, the preceding challenge phase has
                # already capped skill points, so CR — not SP — is what
                # actually limits the first buy. Mirrors orchestrator.py's
                # _run_farm_inner "else: # challenge" branch exactly.
                buy_count = min(cr // config.CAR_PRICE_CR, config.NUM_CARS) if cr > 0 else config.NUM_CARS
                first_cost = buy_count * config.CAR_PRICE_CR
                parts += [
                    _challenge_lbl(base, challenges - base),
                    f"Buy {buy_count} ({first_cost:,} CR)",
                    f"Unlock {buy_count}",
                    f"Remove {buy_count}",
                ]
                parts.append(_cycle_tag(buy_count, buy_count))
                parts.append(_time_main_challenge(init_secs, challenges, buy_count))

        elif phase == "buy":
            to_buy = self._cars_spin.value()
            have = self._have_spin.value()
            max_unlockable = sp // config.SKILL_POINTS_PER_CAR if sp > 0 else config.NUM_CARS
            unlock_count = min(to_buy + have, config.NUM_CARS, max_unlockable)
            sp_remaining = sp - unlock_count * config.SKILL_POINTS_PER_CAR
            if to_buy == 0:
                parts.append("Buy 0  (skip)")
            else:
                parts.append(f"Buy {to_buy}  ({to_buy * config.CAR_PRICE_CR:,} CR)")
            unlock_lbl = f"Unlock {unlock_count}" + (f"  ({have}+{to_buy})" if have > 0 and to_buy > 0 else "")
            parts += [unlock_lbl, f"Remove {unlock_count}"]
            if sp_remaining > 0:
                base_c = math.ceil((config.SKILL_POINTS_CAP - sp_remaining) / config.POINTS_PER_CHALLENGE)
                first_challenges = _buf(base_c)
                parts.append(
                    f"↺ challenge {base_c}{_buf_suffix(first_challenges - base_c)} = {first_challenges}× first, "
                    f"then {config.CHALLENGES_SUBSEQUENT}×/cycle"
                )
            else:
                first_challenges = _buf(math.ceil(config.SKILL_POINTS_CAP / config.POINTS_PER_CHALLENGE))
                parts.append(_cycle_tag(to_buy, unlock_count, first_subsequent_ci=first_challenges))
            parts.append(_time_buy(to_buy, unlock_count, first_challenges))

        elif phase in ("unlock", "remove"):
            n = self._cars_spin.value()
            if phase == "unlock":
                sp_after_unlock = max(0, sp - n * config.SKILL_POINTS_PER_CAR)
                parts += [f"Unlock {n}", f"Remove {n}"]
            else:
                sp_after_unlock = sp
                parts.append(f"Remove {n}")
            if self._ocr_challenge_override is not None:
                base_c, first_challenges = self._ocr_challenge_override
                challenge_tag = (
                    f"challenge {base_c}{_buf_suffix(first_challenges - base_c)} = {first_challenges}× first [OCR adj.]"
                )
            else:
                base_c = (
                    math.ceil((config.SKILL_POINTS_CAP - sp_after_unlock) / config.POINTS_PER_CHALLENGE)
                    if sp_after_unlock < config.SKILL_POINTS_CAP
                    else 0
                )
                first_challenges = _buf(base_c)
                challenge_tag = (
                    f"challenge {base_c}{_buf_suffix(first_challenges - base_c)} = {first_challenges}× first"
                )
            parts.append(challenge_tag + "  →  " + _cycle_tag(0, n, first_subsequent_ci=first_challenges))
            parts.append(_time_unlock_remove(phase, n, first_challenges))

        self._summary.setText("  →  ".join(parts))

    # ── Start / Stop ───────────────────────────────────────────────────────────

    def _on_challenge_adjusted(self, base: int, buffered: int) -> None:
        self._ocr_challenge_override = (base, buffered)
        self._update_summary()

    def _on_start(self) -> None:
        if self._farm_thread and self._farm_thread.is_alive():
            return
        if not self._challenge_only_chk.isChecked():
            car = config.CFG.car
            cfg = config.CFG
            missing = []
            if not car.car_collection_configured:
                missing.append("Car Collection Row / Column")
            if not cfg.multiplier_car_configured:
                missing.append("9x Multiplier Car Filter (Performance Class / Car Type Row) and Position")
            if missing:
                QMessageBox.warning(
                    self,
                    "Setup required",
                    "The following aren't set up yet (Settings tab):\n\n"
                    + "\n".join(f"• {m}" for m in missing)
                    + "\n\nThese are required so the farm can find your cars for Buy/Unlock/"
                    "Remove and switch to the 9x multiplier car. Set them in Settings, or "
                    'tick "Challenge Only" on this tab to skip all car setup and just loop '
                    "the challenge.",
                )
                return
        keys._stop_event.clear()
        self._ocr_challenge_override = None
        self._log.clear()
        self._set_controls(False)
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)  # allow cancelling during countdown

        self._countdown_remaining = self._cd_spin.value()
        self._status.setText(f"Switch to game — starting in {self._countdown_remaining}s...")
        self._countdown_timer.start(1000)

    def _tick(self) -> None:
        self._countdown_remaining -= 1
        if self._countdown_remaining > 0:
            self._status.setText(f"Switch to game — starting in {self._countdown_remaining}s...")
        else:
            self._countdown_timer.stop()
            self._status.setText("Running")
            self._launch()

    def _launch(self) -> None:
        phase = self._phase()
        sp = self._sp_spin.value()
        cr = self._cr_spin.value()
        cars = self._cars_spin.value() if phase in ("buy", "unlock", "remove") else 0
        cars_have = self._have_spin.value() if phase == "buy" else 0
        challenge_only = self._challenge_only_chk.isChecked()
        config.BUFFER_ENABLED = self._buffer_chk.isChecked()

        def _run() -> None:
            orig = sys.stdout
            orchestrator.challenge_adjusted_hook = lambda b, t: _log_bridge.challenge_adjusted.emit(b, t)
            sys.stdout = _StdoutCapture()
            try:
                orchestrator.run_farm(
                    start=phase,
                    skill_points=sp,
                    cars=cars,
                    cars_have=cars_have,
                    cr=cr,
                    cycle=True,
                    challenge_only=challenge_only,
                )
            except Exception as exc:
                _log_bridge.message.emit(f"Error: {exc}")
            finally:
                orchestrator.challenge_adjusted_hook = None
                sys.stdout = orig
            _log_bridge.message.emit("\x00DONE")

        self._elapsed_seconds = 0
        self._elapsed_lbl.setText("00:00:00")
        self._elapsed_timer.start()
        self._farm_thread = threading.Thread(target=_run, daemon=True)
        self._farm_thread.start()

    def _on_stop(self) -> None:
        if self._countdown_timer.isActive():
            # cancel during countdown — farm hasn't started yet
            self._countdown_timer.stop()
            self._elapsed_timer.stop()
            self._elapsed_lbl.setText("")
            self._start_btn.setEnabled(True)
            self._stop_btn.setEnabled(False)
            self._set_controls(True)
            self._status.setText("Cancelled.")
            return
        keys._stop_event.set()
        self._stop_btn.setEnabled(False)
        self._status.setText("Stopping after current iteration...")

    def _set_controls(self, enabled: bool) -> None:
        challenge_only = self._challenge_only_chk.isChecked()
        for key, rb in self._radios.items():
            rb.setEnabled(enabled and not (challenge_only and key != "challenge"))
        self._sp_spin.setEnabled(enabled)
        self._have_spin.setEnabled(enabled)
        self._cars_spin.setEnabled(enabled)
        self._cr_spin.setEnabled(enabled)
        self._cd_spin.setEnabled(enabled)
        self._buffer_chk.setEnabled(enabled)
        self._challenge_only_chk.setEnabled(enabled)
        self._settings_root.setEnabled(enabled)
        self._timings_root.setEnabled(enabled)
        if enabled:
            self._settings_status.setText("")
            self._timings_status.setText("")

    # ── Log ────────────────────────────────────────────────────────────────────

    def _tick_elapsed(self) -> None:
        self._elapsed_seconds += 1
        h, rem = divmod(self._elapsed_seconds, 3600)
        m, s = divmod(rem, 60)
        self._elapsed_lbl.setText(f"{h:02d}:{m:02d}:{s:02d}")

    def _on_log(self, text: str) -> None:
        if text == "\x00DONE":
            self._elapsed_timer.stop()
            self._start_btn.setEnabled(True)
            self._stop_btn.setEnabled(False)
            self._set_controls(True)
            self._status.setText("Done.")
            return

        if text.startswith("Phase:"):
            color = "#FF6B1A"  # orange
        elif text.startswith("Cycle"):
            color = "#1A6AFF"  # blue
        elif text.startswith("Transition:"):
            color = "#888899"  # muted
        elif "complete" in text.lower() or "done" in text.lower():
            color = "#4CAF50"  # green
        elif any(w in text.lower() for w in ("error", "fail", "stop")):
            color = "#FF6666"  # red
        else:
            color = "#C8C8D8"  # default

        cursor = self._log.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = cursor.charFormat()
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.insertText(text + "\n")
        self._log.setTextCursor(cursor)
        self._log.ensureCursorVisible()

        if self._log.document().blockCount() > 5000:
            c = self._log.textCursor()
            c.movePosition(QTextCursor.Start)
            c.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor, 500)
            c.removeSelectedText()
