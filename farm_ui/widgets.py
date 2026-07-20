"""Small reusable widgets, the log bridge, and generic widget-builder helpers."""

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QSpinBox


class _CRSpinBox(QSpinBox):
    """QSpinBox that displays values with thousands separators; 0 shows as 'unlimited'."""

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
        return (QValidator.State.Invalid, text, pos)


# ── Log bridge (thread-safe print → Qt signal) ─────────────────────────────────


class _LogBridge(QObject):
    message = Signal(str)
    challenge_adjusted = Signal(int, int)  # (base_challenges, buffered_challenges) from OCR detection


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
