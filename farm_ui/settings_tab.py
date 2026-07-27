"""Settings tab: farm car, Car Collection position, challenge share code,
9x multiplier car filter + position.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import farm_settings
from farm_core import config
from farm_ui.guide_content import SETTINGS_INFO
from farm_ui.widgets import _fixed_label, _info_button, _required_label, _sep, _show_info_popup, _small
from farm_ui.wizard import SetupWizardDialog


class SettingsTabMixin:
    """Mixed into SkillFarmWindow. Expects self._have_spin/self._have_range_lbl,
    self._update_fields/self._update_summary (from FarmTabMixin) to exist.
    """

    def _build_settings_tab(self) -> QWidget:
        self._settings_root = QWidget()
        vbox = QVBoxLayout(self._settings_root)
        vbox.setContentsMargins(16, 16, 16, 12)
        vbox.setSpacing(10)

        def _row(parent_layout, label: str, widget, hint: str = "") -> list:
            """Returns the widgets it created, so callers that need to show/hide
            the whole row per selected car (e.g. Super Wheelspins) can group them."""
            row = QHBoxLayout()
            lbl = _fixed_label(label, 160)
            row.addWidget(lbl)
            row.addWidget(widget)
            widgets = [lbl, widget]
            if hint:
                hint_lbl = _small(hint)
                row.addWidget(hint_lbl)
                widgets.append(hint_lbl)
            row.addStretch()
            parent_layout.addLayout(row)
            return widgets

        # ── Setup Wizard ─────────────────────────────────────────────────────
        wizard_row = QHBoxLayout()
        wizard_row.addWidget(_small("New here? Get step-by-step help setting up below."), 1)
        wizard_btn = QPushButton("Setup Wizard")
        wizard_btn.setProperty("class", "primary-btn")
        wizard_btn.clicked.connect(self._open_setup_wizard)
        wizard_row.addWidget(wizard_btn)
        vbox.addLayout(wizard_row)
        vbox.addWidget(_sep())

        # ── Farm car ──────────────────────────────────────────────────────────
        car_box = QGroupBox("FARM CAR")
        car_col = QVBoxLayout(car_box)
        car_col.setSpacing(8)

        self._set_car_combo = QComboBox()
        for car_id, info in farm_settings.CAR_CATALOG.items():
            self._set_car_combo.addItem(info.name, car_id)
        self._set_car_combo.setFixedWidth(200)
        _row(car_col, "Car", self._set_car_combo)

        # "Use Auto-Found Position" — lets a user keep a Setup-Wizard-recorded
        # navigation sequence on file but still choose manual Row/Column
        # instead, without losing it (see
        # farm_settings.CarConfig.car_collection_auto_found/
        # car_collection_use_auto_find and
        # farm_core.buy._navigate_car_collection_to_car). Only enabled once a
        # sequence actually exists for the selected car — see
        # _update_cc_mode_ui. Same checkbox/wording as the Setup Wizard's
        # Step 1, kept in sync so the two can't drift.
        self._set_cc_use_auto_chk = QCheckBox("Use Auto-Found Position")
        self._set_cc_use_auto_chk.toggled.connect(self._on_cc_use_auto_toggled)
        car_col.addWidget(self._set_cc_use_auto_chk)

        self._set_cc_mode_label = _small("")
        car_col.addWidget(self._set_cc_mode_label)

        # Wrapped in one container so _refresh_cc_mode_display can disable BOTH
        # rows (labels included — a disabled QWidget dims every descendant via Qt's
        # normal disabled palette) in a single call, instead of disabling just the
        # QSpinBoxes and leaving their labels/hints looking fully active/editable.
        self._cc_fields_frame = QFrame()
        cc_fields_col = QVBoxLayout(self._cc_fields_frame)
        cc_fields_col.setContentsMargins(0, 0, 0, 0)
        cc_fields_col.setSpacing(8)

        # Shown 1-based (row 1 = top car, counting down the list); stored 0-based as down presses.
        self._set_shop_row = QSpinBox()
        self._set_shop_row.setRange(1, 999)
        self._set_shop_row.setFixedWidth(80)
        row_row = QHBoxLayout()
        row_row.addWidget(_required_label("Car Collection Row", 160))
        row_row.addWidget(self._set_shop_row)
        row_row.addWidget(_small("the car's row, from the top"))
        row_row.addWidget(_info_button(self._show_car_collection_info))
        row_row.addStretch()
        cc_fields_col.addLayout(row_row)

        # Shown 1-based (column 1–5, left → right); stored 0-based as right presses.
        self._set_shop_col = QSpinBox()
        self._set_shop_col.setRange(1, 5)
        self._set_shop_col.setFixedWidth(80)
        col_row = QHBoxLayout()
        col_row.addWidget(_required_label("Car Collection Column", 160))
        col_row.addWidget(self._set_shop_col)
        col_row.addWidget(_small("the car's column, 1–5"))
        col_row.addWidget(_info_button(self._show_car_collection_info))
        col_row.addStretch()
        cc_fields_col.addLayout(col_row)

        car_col.addWidget(self._cc_fields_frame)

        def _readonly_spin(max_value: int) -> QSpinBox:
            """setReadOnly(True) alone prevents editing but doesn't dim the
            field's appearance, misleadingly looking just as editable as a
            real input — setEnabled(False) makes it LOOK non-interactive too
            (theme.py's QSpinBox:disabled rule), on top of the read-only/
            no-buttons/no-focus behavior kept here for defense in depth."""
            spin = QSpinBox()
            spin.setRange(0, max_value)
            spin.setFixedWidth(120)
            spin.setGroupSeparatorShown(True)
            spin.setReadOnly(True)
            spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            spin.setFocusPolicy(Qt.NoFocus)
            spin.setEnabled(False)
            return spin

        self._set_price = _readonly_spin(99_999_999)
        _row(car_col, "Price (CR)", self._set_price)

        self._set_soko78_chk = QCheckBox('"Soko 78" House Owned (5% Autoshow Discount)')
        soko78_row = QHBoxLayout()
        soko78_row.addWidget(self._set_soko78_chk)
        soko78_row.addWidget(_info_button(self._show_soko78_info))
        soko78_row.addStretch()
        car_col.addLayout(soko78_row)

        self._set_sp = _readonly_spin(config.SKILL_POINTS_CAP)
        _row(car_col, "SP to Unlock", self._set_sp, "skill points per car")

        # Super Wheelspins / Wheelspins / CR Reward: not every car grants all
        # three (some grant CR instead of wheelspins, or a mix) — each row
        # hides itself in _load_car_fields() when that car's yield is 0,
        # rather than showing a permanent "0" for a reward type it doesn't have.
        self._set_sws = _readonly_spin(20)
        self._sws_widgets = _row(car_col, "Super Wheelspins", self._set_sws, "yield per car")

        self._set_ws = _readonly_spin(20)
        self._ws_widgets = _row(car_col, "Wheelspins", self._set_ws, "yield per car")

        self._set_cr_reward = _readonly_spin(99_999_999)
        self._cr_reward_widgets = _row(car_col, "CR Reward", self._set_cr_reward, "CR yield per car")

        vbox.addWidget(car_box)

        # ── Challenge ─────────────────────────────────────────────────────────
        ch_box = QGroupBox("CHALLENGE")
        ch_col = QVBoxLayout(ch_box)
        ch_col.setSpacing(8)

        self._set_code = QLineEdit()
        self._set_code.setFixedWidth(120)
        self._set_code.setReadOnly(True)
        self._copy_code_btn = QPushButton("Copy")
        self._copy_code_btn.setFixedWidth(60)
        code_row = QHBoxLayout()
        code_row.addWidget(_fixed_label("Share Code", 160))
        code_row.addWidget(self._set_code)
        code_row.addWidget(self._copy_code_btn)
        code_row.addStretch()
        ch_col.addLayout(code_row)

        vbox.addWidget(ch_box)

        # ── Multiplier car filter ─────────────────────────────────────────────
        # All rows/columns below are shown 1-based, stored 0-based (press counts).
        filter_box = QGroupBox("9X MULTIPLIER CAR — FILTER  (checkbox list, rows from the top)")
        filter_col = QVBoxLayout(filter_box)
        filter_col.setSpacing(8)

        # "Use Auto-Found Filter" — same idea as Car Collection's checkbox
        # above, for the Setup Wizard Step 2's recorded sequence (see
        # farm_settings.Settings.filter_auto_found/filter_use_auto_find and
        # farm_core.remove._switch_to_multiplier_car). Only enabled once a
        # sequence actually exists — see _update_filter_mode_ui.
        self._set_filter_use_auto_chk = QCheckBox("Use Auto-Found Filter")
        self._set_filter_use_auto_chk.toggled.connect(self._on_filter_use_auto_toggled)
        filter_col.addWidget(self._set_filter_use_auto_chk)

        self._set_filter_mode_label = _small("")
        filter_col.addWidget(self._set_filter_mode_label)

        # Wrapped in one container so _refresh_filter_mode_display can disable BOTH
        # rows (labels included) in a single call — see the identical reasoning on
        # self._cc_fields_frame above.
        self._filter_fields_frame = QFrame()
        filter_fields_col = QVBoxLayout(self._filter_fields_frame)
        filter_fields_col.setContentsMargins(0, 0, 0, 0)
        filter_fields_col.setSpacing(8)

        self._set_filter_perf = QSpinBox()
        self._set_filter_perf.setRange(1, 99)
        self._set_filter_perf.setFixedWidth(80)
        filter_perf_row = QHBoxLayout()
        filter_perf_row.addWidget(_required_label("Performance Class Row", 160))
        filter_perf_row.addWidget(self._set_filter_perf)
        filter_perf_row.addWidget(_small("row in the filter list"))
        filter_perf_row.addWidget(_info_button(self._show_multiplier_filter_info))
        filter_perf_row.addStretch()
        filter_fields_col.addLayout(filter_perf_row)

        self._set_filter_type = QSpinBox()
        self._set_filter_type.setRange(1, 99)
        self._set_filter_type.setFixedWidth(80)
        filter_type_row = QHBoxLayout()
        filter_type_row.addWidget(_required_label("Car Type Row", 160))
        filter_type_row.addWidget(self._set_filter_type)
        filter_type_row.addWidget(_small("row in the filter list"))
        filter_type_row.addWidget(_info_button(self._show_multiplier_filter_info))
        filter_type_row.addStretch()
        filter_fields_col.addLayout(filter_type_row)

        filter_col.addWidget(self._filter_fields_frame)
        vbox.addWidget(filter_box)

        # ── Multiplier car position ───────────────────────────────────────────
        mult_box = QGroupBox("9X MULTIPLIER CAR — POSITION  (in the filtered My Cars grid)")
        mult_col = QVBoxLayout(mult_box)
        mult_col.setSpacing(8)

        self._set_mult_row = QSpinBox()
        self._set_mult_row.setRange(1, 3)
        self._set_mult_row.setFixedWidth(80)
        mult_row_row = QHBoxLayout()
        mult_row_row.addWidget(_required_label("Car Row", 160))
        mult_row_row.addWidget(self._set_mult_row)
        mult_row_row.addWidget(_small("1–3 (3 rows per column)"))
        mult_row_row.addWidget(_info_button(self._show_multiplier_position_info))
        mult_row_row.addStretch()
        mult_col.addLayout(mult_row_row)

        self._set_mult_col = QSpinBox()
        self._set_mult_col.setRange(1, 99)
        self._set_mult_col.setFixedWidth(80)
        mult_col_row = QHBoxLayout()
        mult_col_row.addWidget(_required_label("Car Column", 160))
        mult_col_row.addWidget(self._set_mult_col)
        mult_col_row.addWidget(_small("dynamic — depends on cars owned"))
        mult_col_row.addWidget(_info_button(self._show_multiplier_position_info))
        mult_col_row.addStretch()
        mult_col.addLayout(mult_col_row)

        vbox.addWidget(mult_box)

        # ── Remove / cycle behavior ────────────────────────────────────────────
        remove_box = QGroupBox("REMOVE")
        remove_col = QVBoxLayout(remove_box)
        remove_col.setSpacing(8)

        self._set_skip_remove_chk = QCheckBox("Skip Remove in Cycle")
        skip_remove_row = QHBoxLayout()
        skip_remove_row.addWidget(self._set_skip_remove_chk)
        skip_remove_row.addWidget(_info_button(self._show_skip_remove_info))
        skip_remove_row.addStretch()
        remove_col.addLayout(skip_remove_row)

        vbox.addWidget(remove_box)

        # ── In-game overlay ────────────────────────────────────────────────────
        overlay_box = QGroupBox("IN-GAME OVERLAY")
        overlay_col = QVBoxLayout(overlay_box)
        overlay_col.setSpacing(8)

        self._set_overlay_chk = QCheckBox("Show In-Game Overlay")
        overlay_row = QHBoxLayout()
        overlay_row.addWidget(self._set_overlay_chk)
        overlay_row.addWidget(_info_button(self._show_overlay_info))
        overlay_row.addStretch()
        overlay_col.addLayout(overlay_row)

        vbox.addWidget(overlay_box)

        # Derived economics preview
        self._settings_econ = QLabel()
        self._settings_econ.setProperty("class", "status-label")
        self._settings_econ.setWordWrap(True)
        vbox.addWidget(self._settings_econ)

        self._settings_status = QLabel("Changes save automatically")
        self._settings_status.setProperty("class", "small-label")
        vbox.addWidget(self._settings_status)
        vbox.addStretch()

        # Every editable field auto-saves — no Save button to miss while
        # scrolled down a long tab. Debounced so a spinbox drag/typed number
        # doesn't write the settings file on every single keystroke.
        self._settings_autosave_timer = QTimer(self)
        self._settings_autosave_timer.setSingleShot(True)
        self._settings_autosave_timer.timeout.connect(self._save_settings)
        # Guards _load_settings_fields()'s own setValue()/setChecked() calls
        # from being mistaken for user edits — otherwise just opening this
        # tab would immediately autosave car_collection_configured=True /
        # multiplier_car_configured=True with whatever default values happen
        # to be sitting in the spinboxes, before the user has set up anything.
        self._loading_settings = False

        self._set_car_combo.currentIndexChanged.connect(lambda _i: self._load_car_fields())
        self._set_soko78_chk.toggled.connect(lambda _checked: self._load_car_fields())
        self._set_overlay_chk.toggled.connect(self.set_overlay_enabled)
        for _signal in (
            self._set_car_combo.currentIndexChanged,
            self._set_shop_row.valueChanged,
            self._set_shop_col.valueChanged,
            self._set_soko78_chk.toggled,
            self._set_filter_perf.valueChanged,
            self._set_filter_type.valueChanged,
            self._set_mult_row.valueChanged,
            self._set_mult_col.valueChanged,
            self._set_skip_remove_chk.toggled,
            self._set_overlay_chk.toggled,
        ):
            _signal.connect(lambda *_: self._schedule_autosave())
        self._copy_code_btn.clicked.connect(self._on_copy_share_code)

        self._load_settings_fields()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self._settings_root)
        return scroll

    def _load_settings_fields(self) -> None:
        self._loading_settings = True
        try:
            cfg = config.CFG
            idx = self._set_car_combo.findData(cfg.selected_car)
            if idx >= 0:
                self._set_car_combo.setCurrentIndex(idx)
            # Set before _load_car_fields() so the Price preview reflects it on first load.
            self._set_soko78_chk.setChecked(cfg.soko78_house_owned)
            self._load_car_fields()
            self._set_code.setText(config.CHALLENGE_SHARE_CODE)
            self._set_filter_perf.setValue(cfg.filter_performance_class_row + 1)
            self._set_filter_type.setValue(cfg.filter_car_type_row + 1)
            self._update_filter_mode_ui()
            self._set_mult_col.setValue(cfg.multiplier_car_col + 1)
            self._set_mult_row.setValue(cfg.multiplier_car_row + 1)
            self._set_skip_remove_chk.setChecked(cfg.skip_remove_in_cycle)
            self._set_overlay_chk.setChecked(cfg.show_ingame_overlay)
            self._update_settings_econ()
        finally:
            self._loading_settings = False

    def _load_car_fields(self) -> None:
        car_id = self._set_car_combo.currentData()
        if car_id is None:
            return
        info = farm_settings.CAR_CATALOG[car_id]
        user = config.CFG.cars[car_id]
        # Live preview: reflects the checkbox's current (possibly unsaved) state,
        # not just the last-saved cfg.soko78_house_owned.
        self._set_price.setValue(farm_settings.effective_price_cr(info.price_cr, self._set_soko78_chk.isChecked()))
        self._set_sp.setValue(info.sp_to_unlock)
        self._set_sws.setValue(info.super_wheelspins)
        self._set_ws.setValue(info.wheelspins)
        self._set_cr_reward.setValue(info.cr_reward)
        for w in self._sws_widgets:
            w.setVisible(info.super_wheelspins > 0)
        for w in self._ws_widgets:
            w.setVisible(info.wheelspins > 0)
        for w in self._cr_reward_widgets:
            w.setVisible(info.cr_reward > 0)
        self._set_shop_col.setValue(user.car_collection_col + 1)  # stored 0-based, shown 1-based
        self._set_shop_row.setValue(user.car_collection_row + 1)
        self._update_cc_mode_ui()

    # ── Use Auto-Found Position/Filter ───────────────────────────────────────

    def _refresh_cc_mode_display(self) -> None:
        """Given the checkbox's CURRENT state, updates the manual fields'
        enabled state and the mode label to match. Called on every toggle;
        see _update_cc_mode_ui for the car-switch/reload path that also
        reloads the checkbox's own state first."""
        car_id = self._set_car_combo.currentData()
        if car_id is None:
            return
        user = config.CFG.cars[car_id]
        use_auto = self._set_cc_use_auto_chk.isChecked()
        self._cc_fields_frame.setEnabled(not use_auto)
        if not user.car_collection_auto_found:
            self._set_cc_mode_label.setText("No position found automatically yet — using the manual Row/Column below.")
        elif use_auto:
            self._set_cc_mode_label.setText("Using the automatically found position — Row/Column below are disabled.")
        else:
            self._set_cc_mode_label.setText(
                "Using the manual Row/Column below (an auto-found position is saved but not in use)."
            )

    def _on_cc_use_auto_toggled(self, _checked: bool) -> None:
        self._refresh_cc_mode_display()
        self._schedule_autosave()

    def _update_cc_mode_ui(self) -> None:
        """Reloads the checkbox's checked/enabled state for whichever car is
        now selected, then refreshes the fields/label to match. Called on
        tab build and whenever the Car dropdown changes."""
        car_id = self._set_car_combo.currentData()
        if car_id is None:
            return
        user = config.CFG.cars[car_id]
        self._set_cc_use_auto_chk.blockSignals(True)
        self._set_cc_use_auto_chk.setEnabled(user.car_collection_auto_found)
        self._set_cc_use_auto_chk.setChecked(user.car_collection_auto_found and user.car_collection_use_auto_find)
        self._set_cc_use_auto_chk.blockSignals(False)
        self._refresh_cc_mode_display()

    def _refresh_filter_mode_display(self) -> None:
        cfg = config.CFG
        use_auto = self._set_filter_use_auto_chk.isChecked()
        self._filter_fields_frame.setEnabled(not use_auto)
        if not cfg.filter_auto_found:
            self._set_filter_mode_label.setText(
                "No filter found automatically yet — using the manual Filter Rows below."
            )
        elif use_auto:
            self._set_filter_mode_label.setText(
                "Using the automatically found filter — Filter Rows below are disabled."
            )
        else:
            self._set_filter_mode_label.setText(
                "Using the manual Filter Rows below (an auto-found filter is saved but not in use)."
            )

    def _on_filter_use_auto_toggled(self, _checked: bool) -> None:
        self._refresh_filter_mode_display()
        self._schedule_autosave()

    def _update_filter_mode_ui(self) -> None:
        cfg = config.CFG
        self._set_filter_use_auto_chk.blockSignals(True)
        self._set_filter_use_auto_chk.setEnabled(cfg.filter_auto_found)
        self._set_filter_use_auto_chk.setChecked(cfg.filter_auto_found and cfg.filter_use_auto_find)
        self._set_filter_use_auto_chk.blockSignals(False)
        self._refresh_filter_mode_display()

    def _on_copy_share_code(self) -> None:
        QApplication.clipboard().setText(self._set_code.text())
        self._settings_status.setText("Share code copied ✓")

    def _show_car_collection_info(self) -> None:
        self._show_settings_info("car_collection")

    def _show_soko78_info(self) -> None:
        self._show_settings_info("soko78")

    def _show_multiplier_filter_info(self) -> None:
        self._show_settings_info("multiplier_filter")

    def _show_multiplier_position_info(self) -> None:
        self._show_settings_info("multiplier_position")

    def _show_skip_remove_info(self) -> None:
        self._show_settings_info("skip_remove_in_cycle")

    def _show_overlay_info(self) -> None:
        self._show_settings_info("overlay")

    def _show_settings_info(self, key: str) -> None:
        title, text = SETTINGS_INFO[key]
        _show_info_popup(self, title, text)

    def _open_setup_wizard(self) -> None:
        SetupWizardDialog(self).exec()
        # The wizard saves via farm_settings.save()/config.refresh_config() itself
        # (same as _save_settings below) — just reload this tab + the Farm tab's
        # fields/summary so they reflect whatever it saved.
        self._load_settings_fields()
        self._update_fields()
        self._update_summary()

    def _update_settings_econ(self) -> None:
        car = config.CFG.car
        # Not every car grants all three reward types — build the yield
        # clause from whichever ones this car actually has (see the Super
        # Wheelspins/Wheelspins/CR Reward row visibility in _load_car_fields).
        yield_parts = []
        if car.super_wheelspins > 0:
            yield_parts.append(f"{config.NUM_CARS * car.super_wheelspins} Super WS")
        if car.wheelspins > 0:
            yield_parts.append(f"{config.NUM_CARS * car.wheelspins} WS")
        if car.cr_reward > 0:
            yield_parts.append(f"{config.NUM_CARS * car.cr_reward:,} CR")
        yield_txt = " + ".join(yield_parts) if yield_parts else "no reward configured"
        self._settings_econ.setText(
            f"{config.NUM_CARS} cars × {config.CAR_PRICE_CR:,} CR = {config.TOTAL_COST_CR:,} CR/cycle"
            f"  →  {yield_txt}"
            f"  →  {config.CHALLENGES_SUBSEQUENT} challenges/cycle"
        )

    def _schedule_autosave(self) -> None:
        if self._loading_settings:
            return
        self._settings_autosave_timer.start(400)

    def _save_settings(self) -> None:
        cfg = config.CFG
        car_id = self._set_car_combo.currentData()
        car = cfg.cars[car_id]
        car.car_collection_col = self._set_shop_col.value() - 1  # shown 1-based, stored 0-based
        car.car_collection_row = self._set_shop_row.value() - 1
        car.car_collection_configured = True
        car.car_collection_use_auto_find = self._set_cc_use_auto_chk.isChecked()
        cfg.selected_car = car_id
        cfg.soko78_house_owned = self._set_soko78_chk.isChecked()
        cfg.filter_performance_class_row = self._set_filter_perf.value() - 1
        cfg.filter_car_type_row = self._set_filter_type.value() - 1
        cfg.filter_use_auto_find = self._set_filter_use_auto_chk.isChecked()
        cfg.multiplier_car_col = self._set_mult_col.value() - 1
        cfg.multiplier_car_row = self._set_mult_row.value() - 1
        cfg.multiplier_car_configured = True
        cfg.skip_remove_in_cycle = self._set_skip_remove_chk.isChecked()
        cfg.show_ingame_overlay = self._set_overlay_chk.isChecked()

        farm_settings.save(cfg)
        config.refresh_config()

        self._have_spin.setRange(0, config.NUM_CARS)
        self._have_range_lbl.setText(f"0 – {config.NUM_CARS}  (optional)")
        self._update_fields()
        self._update_summary()
        self._update_settings_econ()
        self._settings_status.setText("Saved ✓")
