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
        return int("".join(c for c in text if c.isdigit()) or "0")

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
        """
        digits = "".join(c for c in text if c.isdigit())
        if not digits:
            return
        formatted = f"{int(digits):,}"
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
