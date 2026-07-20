"""Settings tab: farm car, Car Collection position, challenge share code,
9x multiplier car filter + position.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import farm_settings
from farm_core import config
from farm_ui.guide_content import SETTINGS_INFO
from farm_ui.widgets import _fixed_label, _info_button, _required_label, _small


class SettingsTabMixin:
    """Mixed into SkillFarmWindow. Expects self._have_spin/self._have_range_lbl,
    self._update_fields/self._update_summary (from FarmTabMixin) to exist.
    """

    def _build_settings_tab(self) -> QWidget:
        self._settings_root = QWidget()
        vbox = QVBoxLayout(self._settings_root)
        vbox.setContentsMargins(16, 16, 16, 12)
        vbox.setSpacing(10)

        def _row(parent_layout, label: str, widget, hint: str = "") -> None:
            row = QHBoxLayout()
            row.addWidget(_fixed_label(label, 160))
            row.addWidget(widget)
            if hint:
                row.addWidget(_small(hint))
            row.addStretch()
            parent_layout.addLayout(row)

        # ── Farm car ──────────────────────────────────────────────────────────
        car_box = QGroupBox("FARM CAR")
        car_col = QVBoxLayout(car_box)
        car_col.setSpacing(8)

        self._set_car_combo = QComboBox()
        for car_id, car in config.CFG.cars.items():
            self._set_car_combo.addItem(car.name, car_id)
        self._set_car_combo.setFixedWidth(200)
        _row(car_col, "Car", self._set_car_combo)

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
        car_col.addLayout(row_row)

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
        car_col.addLayout(col_row)

        def _readonly_spin(max_value: int) -> QSpinBox:
            spin = QSpinBox()
            spin.setRange(0, max_value)
            spin.setFixedWidth(120)
            spin.setGroupSeparatorShown(True)
            spin.setReadOnly(True)
            spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            spin.setFocusPolicy(Qt.NoFocus)
            return spin

        self._set_price = _readonly_spin(99_999_999)
        _row(car_col, "Price (CR)", self._set_price)

        self._set_sp = _readonly_spin(config.SKILL_POINTS_CAP)
        _row(car_col, "SP to Unlock", self._set_sp, "skill points per car")

        self._set_sws = _readonly_spin(20)
        _row(car_col, "Super Wheelspins", self._set_sws, "yield per car")

        self._set_ws = _readonly_spin(20)
        _row(car_col, "Wheelspins", self._set_ws, "yield per car")

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

        self._set_filter_r = QSpinBox()
        self._set_filter_r.setRange(1, 99)
        self._set_filter_r.setFixedWidth(80)
        filter_r_row = QHBoxLayout()
        filter_r_row.addWidget(_required_label('"R class" Row', 160))
        filter_r_row.addWidget(self._set_filter_r)
        filter_r_row.addWidget(_small("row in the filter list"))
        filter_r_row.addWidget(_info_button(self._show_multiplier_filter_info))
        filter_r_row.addStretch()
        filter_col.addLayout(filter_r_row)

        self._set_filter_rr = QSpinBox()
        self._set_filter_rr.setRange(1, 99)
        self._set_filter_rr.setFixedWidth(80)
        filter_rr_row = QHBoxLayout()
        filter_rr_row.addWidget(_required_label('"Retro Rally" Row', 160))
        filter_rr_row.addWidget(self._set_filter_rr)
        filter_rr_row.addWidget(_small("row in the filter list"))
        filter_rr_row.addWidget(_info_button(self._show_multiplier_filter_info))
        filter_rr_row.addStretch()
        filter_col.addLayout(filter_rr_row)

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

        # Derived economics preview
        self._settings_econ = QLabel()
        self._settings_econ.setProperty("class", "status-label")
        self._settings_econ.setWordWrap(True)
        vbox.addWidget(self._settings_econ)

        save_row = QHBoxLayout()
        self._settings_save_btn = QPushButton("SAVE SETTINGS")
        self._settings_save_btn.setProperty("class", "primary-btn")
        self._settings_save_btn.setMinimumHeight(36)
        self._settings_status = QLabel("")
        self._settings_status.setProperty("class", "small-label")
        save_row.addWidget(self._settings_save_btn, 1)
        save_row.addWidget(self._settings_status)
        vbox.addLayout(save_row)
        vbox.addStretch()

        self._set_car_combo.currentIndexChanged.connect(lambda _i: self._load_car_fields())
        self._settings_save_btn.clicked.connect(self._on_save_settings)
        self._copy_code_btn.clicked.connect(self._on_copy_share_code)

        self._load_settings_fields()
        return self._settings_root

    def _load_settings_fields(self) -> None:
        cfg = config.CFG
        idx = self._set_car_combo.findData(cfg.selected_car)
        if idx >= 0:
            self._set_car_combo.setCurrentIndex(idx)
        self._load_car_fields()
        self._set_code.setText(cfg.challenge_share_code)
        self._set_filter_r.setValue(cfg.filter_r_class_row + 1)
        self._set_filter_rr.setValue(cfg.filter_retro_rally_row + 1)
        self._set_mult_col.setValue(cfg.multiplier_car_col + 1)
        self._set_mult_row.setValue(cfg.multiplier_car_row + 1)
        self._update_settings_econ()

    def _load_car_fields(self) -> None:
        car_id = self._set_car_combo.currentData()
        if car_id is None:
            return
        car = config.CFG.cars[car_id]
        self._set_price.setValue(car.price_cr)
        self._set_sp.setValue(car.sp_to_unlock)
        self._set_sws.setValue(car.super_wheelspins)
        self._set_ws.setValue(car.wheelspins)
        self._set_shop_col.setValue(car.car_collection_col + 1)  # stored 0-based, shown 1-based
        self._set_shop_row.setValue(car.car_collection_row + 1)

    def _on_copy_share_code(self) -> None:
        QApplication.clipboard().setText(self._set_code.text())
        self._settings_status.setText("Share code copied ✓")

    def _show_car_collection_info(self) -> None:
        self._show_settings_info("car_collection")

    def _show_multiplier_filter_info(self) -> None:
        self._show_settings_info("multiplier_filter")

    def _show_multiplier_position_info(self) -> None:
        self._show_settings_info("multiplier_position")

    def _show_settings_info(self, key: str) -> None:
        title, text = SETTINGS_INFO[key]
        dlg = QMessageBox(self)
        dlg.setWindowTitle(title)
        dlg.setText(f"<b>{title}</b>")
        dlg.setInformativeText(text)
        dlg.setIcon(QMessageBox.Icon.Information)
        dlg.exec()

    def _update_settings_econ(self) -> None:
        car = config.CFG.car
        self._settings_econ.setText(
            f"{config.NUM_CARS} cars × {config.CAR_PRICE_CR:,} CR = {config.TOTAL_COST_CR:,} CR/cycle"
            f"  →  {config.NUM_CARS * car.super_wheelspins} Super WS + {config.NUM_CARS * car.wheelspins} WS"
            f"  →  {config.CHALLENGES_SUBSEQUENT} challenges/cycle"
        )

    def _on_save_settings(self) -> None:
        cfg = config.CFG
        car_id = self._set_car_combo.currentData()
        car = cfg.cars[car_id]
        car.car_collection_col = self._set_shop_col.value() - 1  # shown 1-based, stored 0-based
        car.car_collection_row = self._set_shop_row.value() - 1
        car.car_collection_configured = True
        cfg.selected_car = car_id
        cfg.filter_r_class_row = self._set_filter_r.value() - 1
        cfg.filter_retro_rally_row = self._set_filter_rr.value() - 1
        cfg.multiplier_car_col = self._set_mult_col.value() - 1
        cfg.multiplier_car_row = self._set_mult_row.value() - 1
        cfg.multiplier_car_configured = True

        farm_settings.save(cfg)
        config.refresh_config()

        self._have_spin.setRange(0, config.NUM_CARS)
        self._have_range_lbl.setText(f"0 – {config.NUM_CARS}  (optional)")
        self._update_fields()
        self._update_summary()
        self._update_settings_econ()
        self._settings_status.setText("Saved ✓")
