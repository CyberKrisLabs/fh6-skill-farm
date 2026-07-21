"""Timings tab: user-editable wait constants, grouped by when they're used."""

from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import farm_settings
from farm_core import config
from farm_ui.guide_content import TIMING_INFO as _TIMING_INFO
from farm_ui.widgets import _fixed_label, _info_button, _small


class TimingsTabMixin:
    """Mixed into SkillFarmWindow."""

    def _build_timings_tab(self) -> QWidget:
        self._timings_root = QWidget()
        vbox = QVBoxLayout(self._timings_root)
        vbox.setContentsMargins(16, 16, 16, 12)
        vbox.setSpacing(10)

        self._timing_spins: dict[str, QDoubleSpinBox] = {}

        def _timing_row(parent_layout, key: str) -> None:
            label, _ = _TIMING_INFO[key]
            row = QHBoxLayout()
            row.addWidget(_fixed_label(label, 240))
            spin = QDoubleSpinBox()
            # Floor at 1/5 of the default — low enough to tune, but not so low
            # the game reliably drops the input (e.g. 0s waits, instant taps).
            min_wait = round(farm_settings.TIMING_DEFAULTS[key] / 5, 3)
            spin.setRange(min_wait, 120.0)
            spin.setDecimals(3)
            spin.setSingleStep(0.05)
            spin.setFixedWidth(90)
            spin.setSuffix(" s")
            self._timing_spins[key] = spin
            row.addWidget(spin)
            row.addWidget(_small(f"min {min_wait}s"))
            row.addWidget(_info_button(lambda: self._show_timing_info(key)))
            row.addStretch()
            parent_layout.addLayout(row)

        nav_box = QGroupBox("MENU NAVIGATION")
        nav_col = QVBoxLayout(nav_box)
        nav_col.setSpacing(8)
        for key in ("MENU_WAIT", "NAV_WAIT", "PAGE_WAIT", "TYPING_WAIT"):
            _timing_row(nav_col, key)
        vbox.addWidget(nav_box)

        challenge_box = QGroupBox("CHALLENGE  (main menu → challenge → back)")
        challenge_col = QVBoxLayout(challenge_box)
        challenge_col.setSpacing(8)
        for key in (
            "LOADING_CHALLENGE_WAIT",
            "LOADING_AFTER_CHALLENGE_EXIT_WAIT",
            "LOADING_TRAVEL_WAIT",
            "LOADING_RETRY_WAIT",
            "LOADING_RESET_WAIT",
        ):
            _timing_row(challenge_col, key)
        vbox.addWidget(challenge_box)

        unlock_remove_box = QGroupBox("UNLOCK / REMOVE")
        unlock_remove_col = QVBoxLayout(unlock_remove_box)
        unlock_remove_col.setSpacing(8)
        for key in ("LOADING_NON_PRELOADED_CAR_WAIT", "LOADING_EXIT_TO_GAME_WAIT"):
            _timing_row(unlock_remove_col, key)
        vbox.addWidget(unlock_remove_box)

        save_row = QHBoxLayout()
        self._timings_save_btn = QPushButton("SAVE TIMINGS")
        self._timings_save_btn.setProperty("class", "primary-btn")
        self._timings_save_btn.setMinimumHeight(36)
        self._timings_reset_btn = QPushButton("RESET TO DEFAULT")
        self._timings_reset_btn.setMinimumHeight(36)
        self._timings_status = QLabel("")
        self._timings_status.setProperty("class", "small-label")
        save_row.addWidget(self._timings_save_btn, 1)
        save_row.addWidget(self._timings_reset_btn)
        save_row.addWidget(self._timings_status)
        vbox.addLayout(save_row)
        vbox.addStretch()

        self._timings_save_btn.clicked.connect(self._on_save_timings)
        self._timings_reset_btn.clicked.connect(self._on_reset_timings)

        self._load_timings_fields()
        return self._timings_root

    def _load_timings_fields(self) -> None:
        for key, spin in self._timing_spins.items():
            spin.setValue(config.CFG.timings.get(key, farm_settings.TIMING_DEFAULTS[key]))

    def _on_reset_timings(self) -> None:
        for key, spin in self._timing_spins.items():
            spin.setValue(farm_settings.TIMING_DEFAULTS[key])
        self._timings_status.setText("Reset — click Save Timings to apply")

    def _on_save_timings(self) -> None:
        for key, spin in self._timing_spins.items():
            config.CFG.timings[key] = spin.value()
        farm_settings.save(config.CFG)
        config.refresh_timings()
        self._timings_status.setText("Saved ✓")

    def _show_timing_info(self, key: str) -> None:
        label, text = _TIMING_INFO[key]
        dlg = QMessageBox(self)
        dlg.setWindowTitle(label)
        dlg.setText(f"<b>{label}</b>")
        dlg.setInformativeText(text)
        dlg.setIcon(QMessageBox.Icon.Information)
        dlg.exec()
