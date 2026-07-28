"""Small reusable widgets, the log bridge, and generic widget-builder helpers."""

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QFrame, QLabel, QMessageBox, QPushButton, QSpinBox, QWidget


def _is_subsequence(sub: str, full: str) -> bool:
    """True if sub's characters appear in full, in order (not necessarily contiguous) —
    i.e. sub is reachable by deleting characters out of full without reordering it.
    """
    it = iter(full)
    return all(ch in it for ch in sub)


class _CRSpinBox(QSpinBox):
    """QSpinBox that displays values with thousands separators; 0 shows as 'unlimited'."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.lineEdit().textEdited.connect(self._reformat_live)

    def textFromValue(self, value: int) -> str:
        return "unlimited" if value == 0 else f"{value:,}"

    def valueFromText(self, text: str) -> int:
        if text in ("unlimited", ""):
            return 0
        # Clamp to the spin box's own range before this reaches Qt/C++ —
        # QSpinBox normally clamps typed values itself, but overriding
        # valueFromText bypasses that, and an unclamped Python int (e.g. from
        # pasting a long digit string) silently overflows Qt's 32-bit int
        # storage (shiboken RuntimeWarning, then a crash) instead of erroring.
        digits = "".join(c for c in text if c.isdigit())
        value = int(digits or "0")
        return max(self.minimum(), min(self.maximum(), value))

    def validate(self, text: str, pos: int):
        if text in ("unlimited", ""):
            return (QValidator.State.Acceptable, text, pos)
        if any(c.isdigit() or c == "," for c in text):
            return (QValidator.State.Acceptable, text, pos)
        if _is_subsequence(text, "unlimited"):
            # A partial deletion of "unlimited" mid-backspace (e.g. "unlimite") —
            # not a final value, but a valid step toward one (clearing down to "").
            return (QValidator.State.Intermediate, text, pos)
        return (QValidator.State.Invalid, text, pos)

    def _reformat_live(self, text: str) -> None:
        """Insert thousand separators as the user types, instead of only on
        focus-out — so "1000000" reads as "1,000,000" immediately. Keeps the
        cursor anchored to the same digit (not the text end) as separators shift.

        Also clamps to the spin box's own maximum live, not just on commit —
        otherwise typing/pasting a long digit string would briefly show its
        full, unclamped value (e.g. "6,090,000,000") before snapping down to
        the real max on focus-out/Enter (see valueFromText), which reads as a
        bug rather than an enforced cap.
        """
        digits = "".join(c for c in text if c.isdigit())
        if not digits:
            return
        formatted = f"{min(int(digits), self.maximum()):,}"
        if formatted == text:
            return
        edit = self.lineEdit()
        digits_before_cursor = sum(c.isdigit() for c in text[: edit.cursorPosition()])
        new_pos = len(formatted)
        seen = 0
        for i, ch in enumerate(formatted):
            if ch.isdigit():
                seen += 1
                if seen == digits_before_cursor:
                    new_pos = i + 1
                    break
        edit.setText(formatted)
        edit.setCursorPosition(new_pos)


# ── Log bridge (thread-safe print → Qt signal) ─────────────────────────────────


class _LogBridge(QObject):
    message = Signal(str)
    challenge_adjusted = Signal(int, int)  # (base_challenges, buffered_challenges) from OCR detection
    phase_progress = Signal(str, int, int, int)  # (phase, current, total, cycle) — see orchestrator.phase_progress_hook


_log_bridge = _LogBridge()


class _FindCarCollectionBridge(QObject):
    """Thread-safe bridge for the Setup Wizard's "Find Automatically" button
    (farm_ui/wizard.py, Car Collection step) — farm_core.car_collection_finder
    .find_car() runs on a background threading.Thread (the same pattern
    farm_tab.py's farm run uses, not QThread), and these Signals marshal its
    progress/status/result back onto the Qt thread automatically via Qt's
    queued-connection mechanism (same as _LogBridge above) — no manual
    invokeMethod needed. Kept separate from _log_bridge since this is a
    distinct concern (one wizard dialog's search), not part of the main farm
    run's log stream. Named specifically for Car Collection (not just
    "find car") since a second, similarly-shaped search for the 9x
    multiplier car's filter rows is a likely future addition — see
    docs/car-position-autodetect-plan.md — and would get its own bridge
    rather than sharing this one, to keep each search's own progress/done
    signals from ever crossing wires. `progress` carries find_car()'s
    verbose `log` lines (shown in the wizard dialog's own status label);
    `status` carries its curated `on_status` phase text, driving
    farm_ui.finder_overlay's on-screen HUD instead — same split as
    _FindMultiplierFilterBridge below.
    """

    progress = Signal(str)  # one verbose diagnostic line as the search runs
    status = Signal(str)  # one curated high-level phase message, for the overlay
    done = Signal(bool, str, list)  # (success, message, recorded [key, count] sequence)


_find_car_collection_bridge = _FindCarCollectionBridge()


class _FindMultiplierFilterBridge(QObject):
    """Thread-safe bridge for the Setup Wizard's "Find Automatically" button
    (farm_ui/wizard.py, 9x Multiplier Car Filter step) — the second,
    similarly-shaped search _FindCarCollectionBridge's docstring anticipated.
    farm_core.multiplier_filter_finder.find_multiplier_filter() runs on a
    background threading.Thread, same pattern as _find_car_collection_bridge.

    Two separate signals carry the module's two deliberately different
    message channels (see find_multiplier_filter()'s docstring): `progress`
    is the verbose diagnostic log (shown in the wizard dialog's own status
    label, same as Car Collection's), `status` is the curated, high-level
    phase text (see find_multiplier_filter()'s on_status=) meant for the
    on-screen overlay shown over the FH6 window itself while the search runs.
    """

    progress = Signal(str)  # one verbose diagnostic line as the search runs
    status = Signal(str)  # one curated high-level phase message, for the overlay
    done = Signal(bool, str, list)  # (success, message, recorded [key, count] sequence)


_find_multiplier_filter_bridge = _FindMultiplierFilterBridge()


class _StdoutCapture:
    def write(self, text: str) -> None:
        text = text.strip()
        if text:
            _log_bridge.message.emit(text)

    def flush(self) -> None:
        pass


# ── Widget helpers ─────────────────────────────────────────────────────────────


def _sep() -> QFrame:
    f = QFrame()
    f.setProperty("class", "separator")
    f.setFixedHeight(1)
    return f


def _small(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("class", "small-label")
    return lbl


def _fixed_label(text: str, width: int) -> QLabel:
    lbl = QLabel(text)
    lbl.setFixedWidth(width)
    return lbl


def _info_button(callback) -> QPushButton:
    btn = QPushButton("ⓘ")
    btn.setFixedSize(22, 22)
    btn.setFlat(True)
    btn.setStyleSheet(
        "QPushButton { font-size: 13pt; color: #FF6B1A; border: none; padding: 0; }"
        "QPushButton:hover { color: #FF9955; }"
    )
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.clicked.connect(callback)
    return btn


def _required_label(text: str, width: int) -> QLabel:
    """Fixed-width label with a red asterisk — for fields required unless Challenge Only is ticked."""
    lbl = QLabel(f'{text} <span style="color:#FF5555;">*</span>')
    lbl.setFixedWidth(width)
    return lbl


def _show_info_popup(parent: QWidget, title: str, text: str) -> None:
    """Shared by the ⓘ info buttons (Settings/Timings tabs) and the Setup Wizard,
    so the popup styling can't drift between call sites."""
    dlg = QMessageBox(parent)
    dlg.setWindowTitle(title)
    dlg.setText(f"<b>{title}</b>")
    dlg.setInformativeText(text)
    dlg.setIcon(QMessageBox.Icon.Information)
    dlg.exec()
