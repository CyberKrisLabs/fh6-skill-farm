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

import threading

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import farm_settings
from farm_core import car_collection_finder, config, keys, multiplier_filter_finder
from farm_ui.finder_overlay import FinderStatusOverlay
from farm_ui.paths import resource_path
from farm_ui.widgets import _find_car_collection_bridge, _find_multiplier_filter_bridge, _fixed_label, _small
from farm_ui.wizard_content import WIZARD_STEPS


class _SlideStrip(QWidget):
    """Pages through a step's (image_filename, caption) slides one at a time,
    with Prev/Next + a counter when there's more than one. Falls back to a
    plain caption (no image, no nav) when the step has no slides defined yet
    — see wizard_content.py.
    """

    # Ceiling on the displayed width regardless of how wide the dialog gets resized —
    # source screenshots can be native desktop resolution (observed: ~3600px wide on a 4K
    # capture), and scaling all the way up to that on a large/4K monitor would make a single
    # slide dominate the screen. Comfortably above the original fixed 540px (so resizing the
    # dialog up still helps readability) without ever ballooning to "the image is the window".
    _MAX_IMAGE_WIDTH = 800

    def __init__(
        self, folder: str, slides: list[tuple[str, str]], fallback_text: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._folder = folder
        self._slides = slides
        self._index = 0
        self._original_pixmap = QPixmap()  # the current slide's un-scaled image — see _rescale_picture

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._picture = QLabel()
        self._picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Without this, a QLabel showing a pixmap (setScaledContents is off — we rescale the
        # pixmap ourselves in _rescale_picture) reports minimumSizeHint() == that pixmap's own
        # size, since Qt won't shrink a label below what's needed to show its pixmap unclipped.
        # That makes the label (and everything containing it) a one-way ratchet: once it grows to
        # show a wider pixmap, nothing can ever shrink it back below that width again, since a
        # smaller resize is never even offered to the layout in the first place. Overriding the
        # floor to near-zero hands ALL sizing control to _rescale_picture()/resizeEvent instead.
        self._picture.setMinimumSize(1, 1)
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
        self._original_pixmap = QPixmap(str(path)) if path.is_file() else QPixmap()
        self._picture.setVisible(not self._original_pixmap.isNull())
        self._rescale_picture()
        self._caption.setText(caption)
        if len(self._slides) > 1:
            self._counter.setText(f"Step {self._index + 1} / {len(self._slides)}")
        self._prev_btn.setEnabled(self._index > 0)
        self._next_btn.setEnabled(self._index < len(self._slides) - 1)

    def _rescale_picture(self) -> None:
        """Rescales the current slide's image to fit the strip's current
        width, capped at both the image's own native width (never upscaled
        past its real resolution — would just look blurry) and
        _MAX_IMAGE_WIDTH (never grows past a sane display size, however wide
        the dialog gets resized). Re-run on every resize (see resizeEvent)
        so images track the now-resizable Setup Wizard dialog instead of
        staying fixed at the old hardcoded 540px."""
        if self._original_pixmap.isNull() or self.width() <= 0:
            return
        target_width = min(self.width(), self._original_pixmap.width(), self._MAX_IMAGE_WIDTH)
        self._picture.setPixmap(
            self._original_pixmap.scaledToWidth(target_width, Qt.TransformationMode.SmoothTransformation)
        )

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._rescale_picture()

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


def _build_step_page(
    title: str, folder: str, field_rows, extra_widget: QWidget | None = None
) -> tuple[QWidget, QFrame]:
    """field_rows: list of (label, spin, hint) tuples already-created by the caller,
    so the caller keeps the QSpinBox instances to read back on Next/Finish.
    extra_widget: optional extra content (e.g. Step 1/2's "Find
    Automatically" section) — rendered BEFORE the manual fields, so "Find
    Automatically" is always what a user sees first; the manual fields are
    the fallback path, not the primary one.

    Returns (scroll_area, fields_frame) — the caller keeps fields_frame too
    so it can toggle the WHOLE manual-fields section's enabled state in one
    call (see _refresh_cc_mode_display/_refresh_filter_mode_display) rather
    than each field individually: a disabled QWidget dims every descendant
    (labels included) via Qt's normal disabled palette, whereas disabling
    just the QSpinBoxes left their labels/hints looking fully active,
    confusingly implying they were still editable.
    """
    step = WIZARD_STEPS[folder]
    content = QWidget()
    col = QVBoxLayout(content)
    col.setSpacing(10)

    title_lbl = QLabel(title)
    title_lbl.setProperty("class", "section-label")
    col.addWidget(title_lbl)

    col.addWidget(_SlideStrip(folder, step["slides"], step["fallback_text"]))

    if extra_widget is not None:
        col.addWidget(extra_widget)

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
    return scroll, fields_frame


class SetupWizardDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Setup Wizard")
        self.setMinimumSize(500, 420)
        self.resize(640, 680)

        cfg = config.CFG

        # Shared across Step 1 and Step 2 — only one search is ever reachable
        # at a time from this modal dialog (nav buttons, the only way to
        # reach the other step, are disabled for the whole duration of
        # either one), so one flag/overlay instance covers both.
        self._searching = False
        self._search_overlay = None

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

        # "Find Automatically" — runs farm_core.car_collection_finder.find_car() on a
        # background thread (see _on_find_automatically) instead of the user
        # manually counting Row/Column. "Use Auto-Found Position" (checked
        # automatically after a successful run) lets the user keep a
        # recorded sequence on file but still choose manual Row/Column
        # instead, without losing it — see _refresh_cc_mode_display.
        #
        # The Car dropdown itself stays OUTSIDE _build_step_page's field_rows
        # (rendered separately, in step1_extra below) — it must stay enabled
        # regardless of the auto-find checkbox, since it's how the user picks
        # WHICH car's settings they're looking at, not a position input.
        car_row_widget = QWidget()
        car_row_layout = QVBoxLayout(car_row_widget)
        car_row_layout.setContentsMargins(0, 0, 0, 0)
        _field_row(car_row_layout, "Car", self._cc_car_combo, "which farm car this position is for")

        find_box = QWidget()
        find_col = QVBoxLayout(find_box)
        find_col.setContentsMargins(0, 0, 0, 0)
        find_col.setSpacing(6)

        find_btn_row = QHBoxLayout()
        self._find_btn = QPushButton("Find Automatically")
        self._find_btn.clicked.connect(self._on_find_automatically)
        find_btn_row.addWidget(self._find_btn)
        find_btn_row.addStretch()
        find_col.addLayout(find_btn_row)

        self._cc_use_auto_chk = QCheckBox("Use Auto-Found Position")
        self._cc_use_auto_chk.toggled.connect(self._on_cc_use_auto_toggled)
        find_col.addWidget(self._cc_use_auto_chk)

        self._cc_mode_label = QLabel()
        self._cc_mode_label.setWordWrap(True)
        self._cc_mode_label.setProperty("class", "small-label")
        find_col.addWidget(self._cc_mode_label)

        self._find_status_label = QLabel()
        self._find_status_label.setWordWrap(True)
        self._find_status_label.setProperty("class", "small-label")
        find_col.addWidget(self._find_status_label)

        step1_extra = QWidget()
        step1_extra_layout = QVBoxLayout(step1_extra)
        step1_extra_layout.setContentsMargins(0, 0, 0, 0)
        step1_extra_layout.setSpacing(10)
        step1_extra_layout.addWidget(car_row_widget)
        step1_extra_layout.addWidget(find_box)

        step1, self._cc_fields_frame = _build_step_page(
            "Step 1 of 3 — Car Collection Position",
            "car_collection",
            [
                ("Car Collection Row", self._cc_row, "the car's row, from the top"),
                ("Car Collection Column", self._cc_col, "the car's column, 1–5"),
            ],
            extra_widget=step1_extra,
        )
        self._reload_car_collection_fields()
        self._cc_car_combo.currentIndexChanged.connect(lambda _i: self._reload_car_collection_fields())

        # ── Step 2: 9x Multiplier Car — Filter ──────────────────────────────
        self._filter_perf = QSpinBox()
        self._filter_perf.setRange(1, 99)
        self._filter_perf.setFixedWidth(80)
        self._filter_perf.setValue(cfg.filter_performance_class_row + 1)
        self._filter_type = QSpinBox()
        self._filter_type.setRange(1, 99)
        self._filter_type.setFixedWidth(80)
        self._filter_type.setValue(cfg.filter_car_type_row + 1)

        # "Find Automatically" — same idea as Step 1's (see its comment
        # above), but searches for a Performance Class letter (template
        # matching) and/or Car Type label (OCR) instead of a specific car.
        self._filter_perf_combo = QComboBox()
        self._filter_perf_combo.addItems(multiplier_filter_finder.PERFORMANCE_CLASSES)
        perf_idx = (
            self._filter_perf_combo.findText(cfg.filter_performance_class) if cfg.filter_performance_class else -1
        )
        self._filter_perf_combo.setCurrentIndex(perf_idx)

        self._filter_type_combo = QComboBox()
        self._filter_type_combo.setEditable(True)
        self._filter_type_combo.addItems(multiplier_filter_finder.KNOWN_CAR_TYPES)
        type_idx = self._filter_type_combo.findText(cfg.filter_car_type) if cfg.filter_car_type else -1
        self._filter_type_combo.setCurrentIndex(type_idx)
        if type_idx < 0:
            self._filter_type_combo.setEditText(cfg.filter_car_type)

        filter_find_box = QWidget()
        filter_find_col = QVBoxLayout(filter_find_box)
        filter_find_col.setContentsMargins(0, 0, 0, 0)
        filter_find_col.setSpacing(6)

        filter_pick_row = QHBoxLayout()
        filter_pick_row.addWidget(_fixed_label("Performance Class", 130))
        filter_pick_row.addWidget(self._filter_perf_combo)
        filter_pick_row.addWidget(_fixed_label("Car Type", 70))
        filter_pick_row.addWidget(self._filter_type_combo, 1)
        filter_find_col.addLayout(filter_pick_row)

        filter_find_btn_row = QHBoxLayout()
        self._filter_find_btn = QPushButton("Find Automatically")
        self._filter_find_btn.clicked.connect(self._on_find_filter_automatically)
        filter_find_btn_row.addWidget(self._filter_find_btn)
        filter_find_btn_row.addStretch()
        filter_find_col.addLayout(filter_find_btn_row)

        self._filter_use_auto_chk = QCheckBox("Use Auto-Found Filter")
        self._filter_use_auto_chk.toggled.connect(self._on_filter_use_auto_toggled)
        filter_find_col.addWidget(self._filter_use_auto_chk)

        self._filter_mode_label = QLabel()
        self._filter_mode_label.setWordWrap(True)
        self._filter_mode_label.setProperty("class", "small-label")
        filter_find_col.addWidget(self._filter_mode_label)

        self._filter_find_status_label = QLabel()
        self._filter_find_status_label.setWordWrap(True)
        self._filter_find_status_label.setProperty("class", "small-label")
        filter_find_col.addWidget(self._filter_find_status_label)

        step2, self._filter_fields_frame = _build_step_page(
            "Step 2 of 3 — 9x Multiplier Car Filter",
            "multiplier_filter",
            [
                ("Performance Class Row", self._filter_perf, "row in the filter list"),
                ("Car Type Row", self._filter_type, "row in the filter list"),
            ],
            extra_widget=filter_find_box,
        )
        self._update_filter_mode_ui()

        # ── Step 3: 9x Multiplier Car — Position ────────────────────────────
        self._mult_row = QSpinBox()
        self._mult_row.setRange(1, 3)
        self._mult_row.setFixedWidth(80)
        self._mult_row.setValue(cfg.multiplier_car_row + 1)
        self._mult_col = QSpinBox()
        self._mult_col.setRange(1, 99)
        self._mult_col.setFixedWidth(80)
        self._mult_col.setValue(cfg.multiplier_car_col + 1)
        step3, _step3_fields_frame = _build_step_page(
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
        self._update_cc_mode_ui()
        self._find_status_label.setText("")

    def _save_car_collection(self) -> None:
        cfg = config.CFG
        car_id = self._cc_car_combo.currentData()
        car = cfg.cars[car_id]
        car.car_collection_row = self._cc_row.value() - 1  # shown 1-based, stored 0-based
        car.car_collection_col = self._cc_col.value() - 1
        car.car_collection_configured = True
        car.car_collection_use_auto_find = self._cc_use_auto_chk.isChecked()
        # The wizard's Car dropdown doubles as "pick your farm car" — same as the
        # Settings tab's own Car combo (settings_tab._save_settings).
        cfg.selected_car = car_id
        farm_settings.save(cfg)
        config.refresh_config()

    # ── Find Automatically (Car Collection) ─────────────────────────────────

    def _refresh_cc_mode_display(self) -> None:
        """Given the checkbox's CURRENT state, updates the manual fields'
        enabled state and the mode label to match. Called on every toggle;
        see _update_cc_mode_ui for the car-switch/post-search reload that
        also reloads the checkbox's own state first."""
        car_id = self._cc_car_combo.currentData()
        user = config.CFG.cars[car_id]
        use_auto = self._cc_use_auto_chk.isChecked()
        self._cc_fields_frame.setEnabled(not use_auto)
        if not user.car_collection_auto_found:
            self._cc_mode_label.setText("No position found automatically yet — using the manual Row/Column below.")
        elif use_auto:
            self._cc_mode_label.setText("Using the automatically found position — Row/Column below are disabled.")
        else:
            self._cc_mode_label.setText(
                "Using the manual Row/Column below (an auto-found position is saved but not in use)."
            )

    def _on_cc_use_auto_toggled(self, _checked: bool) -> None:
        self._refresh_cc_mode_display()

    def _update_cc_mode_ui(self) -> None:
        """Reloads the checkbox's checked/enabled state for whichever car is
        now selected, then refreshes the fields/label to match. Called on
        dialog build, car-combo change, and after a successful Find
        Automatically run."""
        car_id = self._cc_car_combo.currentData()
        user = config.CFG.cars[car_id]
        self._cc_use_auto_chk.blockSignals(True)
        self._cc_use_auto_chk.setEnabled(user.car_collection_auto_found)
        self._cc_use_auto_chk.setChecked(user.car_collection_auto_found and user.car_collection_use_auto_find)
        self._cc_use_auto_chk.blockSignals(False)
        self._refresh_cc_mode_display()

    def _set_find_controls_enabled(self, enabled: bool) -> None:
        self._find_btn.setEnabled(enabled)
        self._cc_car_combo.setEnabled(enabled)
        car_id = self._cc_car_combo.currentData()
        self._cc_use_auto_chk.setEnabled(enabled and config.CFG.cars[car_id].car_collection_auto_found)
        self._back_btn.setEnabled(enabled and self._stack.currentIndex() > 0)
        self._cancel_btn.setEnabled(enabled)
        self._next_btn.setEnabled(enabled)

    def _on_find_automatically(self) -> None:
        car_id = self._cc_car_combo.currentData()
        info = farm_settings.CAR_CATALOG[car_id]
        target = {"manufacturer": info.manufacturer, "model": info.model, "year": info.year}

        reply = QMessageBox.question(
            self,
            "Find Automatically",
            f"About to search for {info.manufacturer} {info.model} ({info.year}).\n\n"
            "Make sure Car Collection is already open in FH6 (see this step's "
            "screenshots above), then click Yes — you'll have 5 seconds to switch "
            "to the game before it starts.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._find_target = target
        self._find_car_id = car_id
        self._searching = True
        self._set_find_controls_enabled(False)
        self._find_countdown_remaining = 5
        self._find_status_label.setText(f"Switch to FH6 now — starting in {self._find_countdown_remaining}s...")

        _find_car_collection_bridge.progress.connect(self._on_find_progress)
        _find_car_collection_bridge.status.connect(self._on_find_status)
        _find_car_collection_bridge.done.connect(self._on_find_done)

        self._find_countdown_timer = QTimer(self)
        self._find_countdown_timer.timeout.connect(self._find_countdown_tick)
        self._find_countdown_timer.start(1000)

    def _find_countdown_tick(self) -> None:
        self._find_countdown_remaining -= 1
        if self._find_countdown_remaining > 0:
            self._find_status_label.setText(f"Switch to FH6 now — starting in {self._find_countdown_remaining}s...")
            return
        self._find_countdown_timer.stop()
        if not keys._fh6_focused():
            self._find_status_label.setText("FH6 is not focused — aborted. Click Find Automatically to try again.")
            self._abort_find_connections()
            return
        self._find_status_label.setText("Searching...")
        self._clear_cc_auto_find()
        # A prior Farm Stop (or a prior search that itself lost focus
        # momentarily) leaves this set — see the identical comment on
        # keys.mp() itself. Only farm_tab._on_start() and the CLI ever
        # cleared it before now, so the Wizard's OWN "FH6 is focused" check
        # right above this line could pass while every keys.mp() call the
        # search makes still silently no-ops on its very first iteration
        # (car_collection_finder._press/_burst_press then immediately raise
        # _SearchAborted("... lost FH6 focus ...") from that stale state,
        # not a real new focus loss) — field-confirmed 2026-07-29: this made
        # every Find Automatically attempt after the first real Stop (Farm
        # tab, or an earlier search that itself tripped this) fail instantly
        # with a focus-sounding error even though FH6 genuinely was focused.
        keys._stop_event.clear()
        self._search_overlay = FinderStatusOverlay()
        thread = threading.Thread(target=self._run_find_thread, args=(self._find_target,), daemon=True)
        thread.start()

    def _clear_cc_auto_find(self) -> None:
        """Clears any previously-recorded auto-found sequence for this car
        the moment a new search actually commits to running (FH6 focus
        confirmed, about to press keys) — not merely when the button is
        clicked or the countdown starts, since an aborted-before-running
        attempt shouldn't disturb a perfectly good existing result. Without
        this, a re-run that FAILS would leave the old sequence/flag/checkbox
        looking exactly as "active" as a fresh success, which is misleading
        — the UI would keep saying "Using the automatically found position"
        even though what's actually on file is now stale relative to
        whatever the user just tried to re-find.
        """
        cfg = config.CFG
        car = cfg.cars[self._find_car_id]
        car.car_collection_auto_found = False
        car.car_collection_find_sequence = []
        farm_settings.save(cfg)
        config.refresh_config()
        self._update_cc_mode_ui()

    def _run_find_thread(self, target: dict) -> None:
        """Runs on a background thread — never touch Qt widgets directly here,
        only emit through _find_car_collection_bridge (queued automatically onto the Qt
        thread, same pattern farm_tab.py's farm run uses for _log_bridge)."""
        result = car_collection_finder.find_car(
            target,
            log=lambda msg: _find_car_collection_bridge.progress.emit(msg),
            on_status=lambda msg: _find_car_collection_bridge.status.emit(msg),
        )
        _find_car_collection_bridge.done.emit(result.success, result.message, result.sequence)

    def _on_find_progress(self, message: str) -> None:
        # Also printed to console (if one's attached — e.g. running via
        # `python skill_farm_ui.py`) since the dialog's status label only
        # ever shows the LATEST line, unlike tools/car_collection_finder.py's
        # CLI, which prints the full verbose history — useful for anything
        # beyond "did it eventually succeed or fail".
        print(message)
        self._find_status_label.setText(message)

    def _on_find_status(self, message: str) -> None:
        if self._search_overlay is not None:
            self._search_overlay.update_status(message)

    def _close_search_overlay(self) -> None:
        if self._search_overlay is not None:
            self._search_overlay.close()
            self._search_overlay = None

    def _abort_find_connections(self) -> None:
        self._searching = False
        self._set_find_controls_enabled(True)
        _find_car_collection_bridge.progress.disconnect(self._on_find_progress)
        _find_car_collection_bridge.status.disconnect(self._on_find_status)
        _find_car_collection_bridge.done.disconnect(self._on_find_done)

    def _on_find_done(self, success: bool, message: str, sequence: list) -> None:
        self._abort_find_connections()
        # Leave the overlay up briefly so the user (watching the game, not
        # this dialog) actually gets to read the final status instead of it
        # vanishing the instant the search thread returns.
        QTimer.singleShot(2000, self._close_search_overlay)
        if not success:
            # Also printed (see _on_find_progress's comment) — otherwise a failed run's ONLY
            # visible trace is this dialog's own label, easy to miss if you're watching the
            # console instead (field-confirmed: looked like the search silently hung).
            print(f"Not found: {message}")
            self._find_status_label.setText(f"Not found: {message} (falling back to manual Row/Column below)")
            return
        cfg = config.CFG
        car = cfg.cars[self._find_car_id]
        car.car_collection_find_sequence = sequence
        car.car_collection_auto_found = True
        car.car_collection_use_auto_find = True
        car.car_collection_configured = True
        farm_settings.save(cfg)
        config.refresh_config()
        print(f"Found it: {message}")
        self._find_status_label.setText(f"Found it: {message}")
        self._update_cc_mode_ui()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if self._searching:
            event.ignore()
            return
        self._close_search_overlay()
        super().closeEvent(event)

    def _save_multiplier_filter(self) -> None:
        cfg = config.CFG
        cfg.filter_performance_class_row = self._filter_perf.value() - 1
        cfg.filter_car_type_row = self._filter_type.value() - 1
        cfg.filter_use_auto_find = self._filter_use_auto_chk.isChecked()
        # multiplier_car_configured isn't set true here — Position (step 3)
        # hasn't been confirmed yet, and that flag gates both together.
        farm_settings.save(cfg)
        config.refresh_config()

    # ── Find Automatically (9x Multiplier Car Filter) ───────────────────────

    def _refresh_filter_mode_display(self) -> None:
        cfg = config.CFG
        use_auto = self._filter_use_auto_chk.isChecked()
        self._filter_fields_frame.setEnabled(not use_auto)
        if not cfg.filter_auto_found:
            self._filter_mode_label.setText("No filter found automatically yet — using the manual Filter Rows below.")
        elif use_auto:
            self._filter_mode_label.setText("Using the automatically found filter — Filter Rows below are disabled.")
        else:
            self._filter_mode_label.setText(
                "Using the manual Filter Rows below (an auto-found filter is saved but not in use)."
            )

    def _on_filter_use_auto_toggled(self, _checked: bool) -> None:
        self._refresh_filter_mode_display()

    def _update_filter_mode_ui(self) -> None:
        """Reloads the checkbox's checked/enabled state, then refreshes the
        fields/label to match. Called on dialog build and after a
        successful Find Automatically run."""
        cfg = config.CFG
        self._filter_use_auto_chk.blockSignals(True)
        self._filter_use_auto_chk.setEnabled(cfg.filter_auto_found)
        self._filter_use_auto_chk.setChecked(cfg.filter_auto_found and cfg.filter_use_auto_find)
        self._filter_use_auto_chk.blockSignals(False)
        self._refresh_filter_mode_display()

    def _set_find_filter_controls_enabled(self, enabled: bool) -> None:
        self._filter_find_btn.setEnabled(enabled)
        self._filter_perf_combo.setEnabled(enabled)
        self._filter_type_combo.setEnabled(enabled)
        self._filter_use_auto_chk.setEnabled(enabled and config.CFG.filter_auto_found)
        self._back_btn.setEnabled(enabled and self._stack.currentIndex() > 0)
        self._cancel_btn.setEnabled(enabled)
        self._next_btn.setEnabled(enabled)

    def _on_find_filter_automatically(self) -> None:
        performance_class = self._filter_perf_combo.currentText().strip()
        car_type = self._filter_type_combo.currentText().strip()
        if not performance_class and not car_type:
            QMessageBox.warning(self, "Find Automatically", "Pick a Performance Class and/or enter a Car Type first.")
            return

        reply = QMessageBox.question(
            self,
            "Find Automatically",
            f"About to search for Performance Class {performance_class!r} / Car Type {car_type!r}.\n\n"
            "Make sure My Cars is already open in FH6 (cursor anywhere), then click Yes — "
            "you'll have 5 seconds to switch to the game before it starts.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._filter_find_target = {"performance_class": performance_class or None, "car_type": car_type or None}
        self._searching = True
        self._set_find_filter_controls_enabled(False)
        self._filter_find_countdown_remaining = 5
        self._filter_find_status_label.setText(
            f"Switch to FH6 now — starting in {self._filter_find_countdown_remaining}s..."
        )

        _find_multiplier_filter_bridge.progress.connect(self._on_find_filter_progress)
        _find_multiplier_filter_bridge.status.connect(self._on_find_filter_status)
        _find_multiplier_filter_bridge.done.connect(self._on_find_filter_done)

        self._filter_find_countdown_timer = QTimer(self)
        self._filter_find_countdown_timer.timeout.connect(self._filter_find_countdown_tick)
        self._filter_find_countdown_timer.start(1000)

    def _filter_find_countdown_tick(self) -> None:
        self._filter_find_countdown_remaining -= 1
        if self._filter_find_countdown_remaining > 0:
            self._filter_find_status_label.setText(
                f"Switch to FH6 now — starting in {self._filter_find_countdown_remaining}s..."
            )
            return
        self._filter_find_countdown_timer.stop()
        if not keys._fh6_focused():
            self._filter_find_status_label.setText(
                "FH6 is not focused — aborted. Click Find Automatically to try again."
            )
            self._abort_find_filter_connections()
            return
        self._filter_find_status_label.setText("Searching...")
        self._clear_filter_auto_find()
        # See the identical comment in _find_countdown_tick above — same bug,
        # same fix, for Step 2's search.
        keys._stop_event.clear()
        self._search_overlay = FinderStatusOverlay()
        thread = threading.Thread(target=self._run_find_filter_thread, args=(self._filter_find_target,), daemon=True)
        thread.start()

    def _clear_filter_auto_find(self) -> None:
        """Same reasoning as _clear_cc_auto_find — clears the previously
        recorded sequence the moment this run actually commits, so a FAILED
        re-run doesn't leave the old one looking just as "active" as a
        fresh success."""
        cfg = config.CFG
        cfg.filter_auto_found = False
        cfg.filter_find_sequence = []
        farm_settings.save(cfg)
        config.refresh_config()
        self._update_filter_mode_ui()

    def _run_find_filter_thread(self, target: dict) -> None:
        """Runs on a background thread — never touch Qt widgets directly
        here, only emit through _find_multiplier_filter_bridge (queued
        automatically onto the Qt thread, same pattern as
        _find_car_collection_bridge)."""
        result = multiplier_filter_finder.find_multiplier_filter(
            performance_class=target["performance_class"],
            car_type=target["car_type"],
            log=lambda msg: _find_multiplier_filter_bridge.progress.emit(msg),
            on_status=lambda msg: _find_multiplier_filter_bridge.status.emit(msg),
        )
        _find_multiplier_filter_bridge.done.emit(result.success, result.message, result.sequence)

    def _on_find_filter_progress(self, message: str) -> None:
        # See _on_find_progress's comment above — same reasoning.
        print(message)
        self._filter_find_status_label.setText(message)

    def _on_find_filter_status(self, message: str) -> None:
        if self._search_overlay is not None:
            self._search_overlay.update_status(message)

    def _abort_find_filter_connections(self) -> None:
        self._searching = False
        self._set_find_filter_controls_enabled(True)
        _find_multiplier_filter_bridge.progress.disconnect(self._on_find_filter_progress)
        _find_multiplier_filter_bridge.status.disconnect(self._on_find_filter_status)
        _find_multiplier_filter_bridge.done.disconnect(self._on_find_filter_done)

    def _on_find_filter_done(self, success: bool, message: str, sequence: list) -> None:
        self._abort_find_filter_connections()
        # Leave the overlay up briefly so the user (watching the game, not
        # this dialog) actually gets to read the final status instead of it
        # vanishing the instant the search thread returns.
        QTimer.singleShot(2000, self._close_search_overlay)
        if not success:
            # Also printed (see _on_find_filter_progress's comment) — otherwise a failed run's
            # ONLY visible trace is this dialog's own label, easy to miss if you're watching the
            # console instead.
            print(f"Not found: {message}")
            self._filter_find_status_label.setText(f"Not found: {message} (falling back to manual Filter Rows below)")
            return
        cfg = config.CFG
        cfg.filter_performance_class = self._filter_perf_combo.currentText().strip()
        cfg.filter_car_type = self._filter_type_combo.currentText().strip()
        cfg.filter_find_sequence = sequence
        cfg.filter_auto_found = True
        cfg.filter_use_auto_find = True
        farm_settings.save(cfg)
        config.refresh_config()
        print(f"Found it: {message}")
        self._filter_find_status_label.setText(f"Found it: {message}")
        self._update_filter_mode_ui()

    def _save_multiplier_position(self) -> None:
        cfg = config.CFG
        cfg.multiplier_car_row = self._mult_row.value() - 1
        cfg.multiplier_car_col = self._mult_col.value() - 1
        cfg.multiplier_car_configured = True
        farm_settings.save(cfg)
        config.refresh_config()
