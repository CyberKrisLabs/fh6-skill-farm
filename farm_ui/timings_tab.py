"""Timings tab: user-editable wait constants, grouped by when they're used."""

from PySide6.QtCore import QTimer
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
        # Guards _load_timings_fields()'s/_on_reset_timings()'s own bulk
        # setValue() calls from being mistaken for user edits — same pattern
        # as SettingsTabMixin._loading_settings.
        self._loading_timings = False

        def _timing_row(parent_layout, key: str) -> None:
            label, _ = _TIMING_INFO[key]
            row = QHBoxLayout()
            row.addWidget(_fixed_label(label, 240))
            spin = QDoubleSpinBox()
            # Floor at 1/5 of the default — low enough to tune, but not so low
            # the game reliably drops the input (e.g. 0s waits, instant taps).
            min_wait = round(farm_settings.TIMING_DEFAULTS[key] / 5, 2)
            spin.setRange(min_wait, 120.0)
            spin.setDecimals(2)
            spin.setSingleStep(0.05)
            spin.setFixedWidth(90)
            spin.setSuffix(" s")
            spin.valueChanged.connect(self._on_timing_value_changed)
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

        fallback_box = QGroupBox("FALLBACK TIMINGS  (used only if drivable-HUD detection doesn't confirm in time)")
        fallback_col = QVBoxLayout(fallback_box)
        fallback_col.setSpacing(8)
        for key in (
            "LOADING_CHALLENGE_WAIT",
            "LOADING_AFTER_CHALLENGE_EXIT_WAIT",
            "LOADING_RETRY_WAIT",
            "LOADING_EXIT_TO_GAME_WAIT",
        ):
            _timing_row(fallback_col, key)
        vbox.addWidget(fallback_box)

        save_row = QHBoxLayout()
        self._timings_reset_btn = QPushButton("RESET TO DEFAULT")
        self._timings_reset_btn.setMinimumHeight(36)
        self._timings_status = QLabel("Changes save automatically")
        self._timings_status.setProperty("class", "small-label")
        save_row.addWidget(self._timings_reset_btn)
        save_row.addWidget(self._timings_status)
        vbox.addLayout(save_row)
        vbox.addStretch()

        # Every spin auto-saves — no Save button to miss. Debounced so a
        # typed/dragged value doesn't write the settings file on every
        # single keystroke; Reset saves immediately instead, since that's
        # already one deliberate, discrete action.
        self._timings_autosave_timer = QTimer(self)
        self._timings_autosave_timer.setSingleShot(True)
        self._timings_autosave_timer.timeout.connect(self._on_save_timings)

        self._timings_reset_btn.clicked.connect(self._on_reset_timings)

        self._load_timings_fields()
        return self._timings_root

    def _load_timings_fields(self) -> None:
        self._loading_timings = True
        try:
            for key, spin in self._timing_spins.items():
                spin.setValue(config.CFG.timings.get(key, farm_settings.TIMING_DEFAULTS[key]))
        finally:
            self._loading_timings = False

    def _on_reset_timings(self) -> None:
        self._loading_timings = True
        try:
            for key, spin in self._timing_spins.items():
                spin.setValue(farm_settings.TIMING_DEFAULTS[key])
        finally:
            self._loading_timings = False
        self._on_save_timings()
        self._timings_status.setText("Reset to defaults and saved ✓")

    def _on_save_timings(self) -> None:
        for key, spin in self._timing_spins.items():
            config.CFG.timings[key] = spin.value()
        farm_settings.save(config.CFG)
        config.refresh_timings()
        self._timings_status.setText("Saved ✓")

    def _on_timing_value_changed(self) -> None:
        if not self._loading_timings:
            self._timings_autosave_timer.start(400)

    def _show_timing_info(self, key: str) -> None:
        label, text = _TIMING_INFO[key]
        dlg = QMessageBox(self)
        dlg.setWindowTitle(label)
        dlg.setText(f"<b>{label}</b>")
        dlg.setInformativeText(text)
        dlg.setIcon(QMessageBox.Icon.Information)
        dlg.exec()
