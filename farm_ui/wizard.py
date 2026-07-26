"""Setup Wizard: a 3-step guided walkthrough for the two settings groups that
gate whether the farm can start (see farm_tab.FarmTabMixin._on_start's
"Setup required" check) — Car Collection Row/Column, then the 9x Multiplier
Car Filter (Performance Class/Car Type Row) and Position (Row/Column).

Each step's screenshots + captions come from wizard_content.WIZARD_STEPS —
its own copy, deliberately not the Settings tab's SETTINGS_INFO (see that
module's docstring for why). Every step's Next/Finish button saves
immediately (same save()/refresh_config() calls _save_settings uses),
matching this app's save-as-you-go philosophy elsewhere, so closing the
dialog partway through never loses whatever step was already confirmed.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import farm_settings
from farm_core import config
from farm_ui.paths import resource_path
from farm_ui.widgets import _fixed_label, _small
from farm_ui.wizard_content import WIZARD_STEPS


class _SlideStrip(QWidget):
    """Pages through a step's (image_filename, caption) slides one at a time,
    with Prev/Next + a counter when there's more than one. Falls back to a
    plain caption (no image, no nav) when the step has no slides defined yet
    — see wizard_content.py.
    """

    def __init__(
        self, folder: str, slides: list[tuple[str, str]], fallback_text: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._folder = folder
        self._slides = slides
        self._index = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._picture = QLabel()
        self._picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._picture)

        self._caption = QLabel()
        self._caption.setWordWrap(True)
        layout.addWidget(self._caption)

        nav_row = QHBoxLayout()
        self._prev_btn = QPushButton("< Prev")
        self._prev_btn.setFixedWidth(70)
        self._prev_btn.clicked.connect(self._prev)
        self._counter = QLabel()
        self._counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._next_btn = QPushButton("Next >")
        self._next_btn.setFixedWidth(70)
        self._next_btn.clicked.connect(self._next)
        nav_row.addWidget(self._prev_btn)
        nav_row.addWidget(self._counter, 1)
        nav_row.addWidget(self._next_btn)
        layout.addLayout(nav_row)

        if not self._slides:
            self._picture.setVisible(False)
            self._caption.setText(fallback_text)
            self._prev_btn.setVisible(False)
            self._next_btn.setVisible(False)
            self._counter.setVisible(False)
            return
        if len(self._slides) == 1:
            self._prev_btn.setVisible(False)
            self._next_btn.setVisible(False)
            self._counter.setVisible(False)
        self._render()

    def _render(self) -> None:
        filename, caption = self._slides[self._index]
        path = resource_path(f"assets/wizard/{self._folder}/{filename}")
        pixmap = QPixmap(str(path)) if path.is_file() else QPixmap()
        self._picture.setVisible(not pixmap.isNull())
        if not pixmap.isNull():
            self._picture.setPixmap(pixmap.scaledToWidth(540, Qt.TransformationMode.SmoothTransformation))
        self._caption.setText(caption)
        if len(self._slides) > 1:
            self._counter.setText(f"Step {self._index + 1} / {len(self._slides)}")
        self._prev_btn.setEnabled(self._index > 0)
        self._next_btn.setEnabled(self._index < len(self._slides) - 1)

    def _prev(self) -> None:
        self._index = max(0, self._index - 1)
        self._render()

    def _next(self) -> None:
        self._index = min(len(self._slides) - 1, self._index + 1)
        self._render()


def _field_row(parent_layout: QVBoxLayout, label: str, widget: QWidget, hint: str = "") -> None:
    row = QHBoxLayout()
    row.addWidget(_fixed_label(label, 180))
    row.addWidget(widget)
    if hint:
        row.addWidget(_small(hint))
    row.addStretch()
    parent_layout.addLayout(row)


def _build_step_page(title: str, folder: str, field_rows) -> QWidget:
    """field_rows: list of (label, spin, hint) tuples already-created by the caller,
    so the caller keeps the QSpinBox instances to read back on Next/Finish."""
    step = WIZARD_STEPS[folder]
    content = QWidget()
    col = QVBoxLayout(content)
    col.setSpacing(10)

    title_lbl = QLabel(title)
    title_lbl.setProperty("class", "section-label")
    col.addWidget(title_lbl)

    col.addWidget(_SlideStrip(folder, step["slides"], step["fallback_text"]))

    fields_frame = QFrame()
    fields_col = QVBoxLayout(fields_frame)
    fields_col.setSpacing(8)
    for label, spin, hint in field_rows:
        _field_row(fields_col, label, spin, hint)
    col.addWidget(fields_frame)
    col.addStretch()

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidget(content)
    return scroll


class SetupWizardDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Setup Wizard")
        self.setFixedSize(640, 680)

        cfg = config.CFG

        # ── Step 1: Car Collection ──────────────────────────────────────────
        self._cc_car_combo = QComboBox()
        for car_id, info in farm_settings.CAR_CATALOG.items():
            self._cc_car_combo.addItem(info.name, car_id)
        self._cc_car_combo.setFixedWidth(200)
        idx = self._cc_car_combo.findData(cfg.selected_car)
        if idx >= 0:
            self._cc_car_combo.setCurrentIndex(idx)

        self._cc_row = QSpinBox()
        self._cc_row.setRange(1, 999)
        self._cc_row.setFixedWidth(80)
        self._cc_col = QSpinBox()
        self._cc_col.setRange(1, 5)
        self._cc_col.setFixedWidth(80)
        self._reload_car_collection_fields()
        self._cc_car_combo.currentIndexChanged.connect(lambda _i: self._reload_car_collection_fields())

        step1 = _build_step_page(
            "Step 1 of 3 — Car Collection Position",
            "car_collection",
            [
                ("Car", self._cc_car_combo, "which farm car this position is for"),
                ("Car Collection Row", self._cc_row, "the car's row, from the top"),
                ("Car Collection Column", self._cc_col, "the car's column, 1–5"),
            ],
        )

        # ── Step 2: 9x Multiplier Car — Filter ──────────────────────────────
        self._filter_perf = QSpinBox()
        self._filter_perf.setRange(1, 99)
        self._filter_perf.setFixedWidth(80)
        self._filter_perf.setValue(cfg.filter_performance_class_row + 1)
        self._filter_type = QSpinBox()
        self._filter_type.setRange(1, 99)
        self._filter_type.setFixedWidth(80)
        self._filter_type.setValue(cfg.filter_car_type_row + 1)
        step2 = _build_step_page(
            "Step 2 of 3 — 9x Multiplier Car Filter",
            "multiplier_filter",
            [
                ("Performance Class Row", self._filter_perf, "row in the filter list"),
                ("Car Type Row", self._filter_type, "row in the filter list"),
            ],
        )

        # ── Step 3: 9x Multiplier Car — Position ────────────────────────────
        self._mult_row = QSpinBox()
        self._mult_row.setRange(1, 3)
        self._mult_row.setFixedWidth(80)
        self._mult_row.setValue(cfg.multiplier_car_row + 1)
        self._mult_col = QSpinBox()
        self._mult_col.setRange(1, 99)
        self._mult_col.setFixedWidth(80)
        self._mult_col.setValue(cfg.multiplier_car_col + 1)
        step3 = _build_step_page(
            "Step 3 of 3 — 9x Multiplier Car Position",
            "multiplier_position",
            [
                ("Car Row", self._mult_row, "1–3 (3 rows per column)"),
                ("Car Column", self._mult_col, "dynamic — depends on cars owned"),
            ],
        )

        self._stack = QStackedWidget()
        for page in (step1, step2, step3):
            self._stack.addWidget(page)

        outer = QVBoxLayout(self)
        outer.addWidget(self._stack)

        nav_row = QHBoxLayout()
        self._back_btn = QPushButton("< Back")
        self._back_btn.clicked.connect(self._on_back)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        self._next_btn = QPushButton("Next Step >")
        self._next_btn.setProperty("class", "primary-btn")
        self._next_btn.clicked.connect(self._on_next)
        nav_row.addWidget(self._back_btn)
        nav_row.addStretch()
        nav_row.addWidget(self._cancel_btn)
        nav_row.addWidget(self._next_btn)
        outer.addLayout(nav_row)

        self._update_nav()

    def _update_nav(self) -> None:
        index = self._stack.currentIndex()
        self._back_btn.setEnabled(index > 0)
        self._next_btn.setText("Finish" if index == self._stack.count() - 1 else "Next Step >")

    def _on_back(self) -> None:
        self._stack.setCurrentIndex(self._stack.currentIndex() - 1)
        self._update_nav()

    def _on_next(self) -> None:
        index = self._stack.currentIndex()
        if index == 0:
            self._save_car_collection()
        elif index == 1:
            self._save_multiplier_filter()
        else:
            self._save_multiplier_position()
            self.accept()
            return
        self._stack.setCurrentIndex(index + 1)
        self._update_nav()

    def _reload_car_collection_fields(self) -> None:
        """Fires on dialog build and whenever the Car dropdown changes — loads that
        car's already-saved Row/Column instead of leaving the previous car's values
        sitting in the fields."""
        car_id = self._cc_car_combo.currentData()
        user = config.CFG.cars[car_id]
        self._cc_row.setValue(user.car_collection_row + 1)
        self._cc_col.setValue(user.car_collection_col + 1)

    def _save_car_collection(self) -> None:
        cfg = config.CFG
        car_id = self._cc_car_combo.currentData()
        car = cfg.cars[car_id]
        car.car_collection_row = self._cc_row.value() - 1  # shown 1-based, stored 0-based
        car.car_collection_col = self._cc_col.value() - 1
        car.car_collection_configured = True
        # The wizard's Car dropdown doubles as "pick your farm car" — same as the
        # Settings tab's own Car combo (settings_tab._save_settings).
        cfg.selected_car = car_id
        farm_settings.save(cfg)
        config.refresh_config()

    def _save_multiplier_filter(self) -> None:
        cfg = config.CFG
        cfg.filter_performance_class_row = self._filter_perf.value() - 1
        cfg.filter_car_type_row = self._filter_type.value() - 1
        # multiplier_car_configured isn't set true here — Position (step 3)
        # hasn't been confirmed yet, and that flag gates both together.
        farm_settings.save(cfg)
        config.refresh_config()

    def _save_multiplier_position(self) -> None:
        cfg = config.CFG
        cfg.multiplier_car_row = self._mult_row.value() - 1
        cfg.multiplier_car_col = self._mult_col.value() - 1
        cfg.multiplier_car_configured = True
        farm_settings.save(cfg)
        config.refresh_config()
