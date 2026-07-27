"""On-screen status overlay for automated "Find Automatically" searches
(farm_core.multiplier_filter_finder, farm_core.car_collection_finder) — a
small, frameless, always-on-top label shown over the FH6 window itself while
a search runs, so the user (watching the game, not the Setup Wizard dialog
they just alt-tabbed away from) can see what's happening without switching
back. Lifecycle (create/update/close) is owned by whichever wizard step
triggers a search — see farm_ui/wizard.py. Deliberately much simpler than
overlay.IngameOverlay (no Start/Stop controls, no focus-based auto-hide —
this is tied to a short automated action the user is actively watching, not
a long farm-run session).
"""

import ctypes

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from farm_core import vision

# Makes a window invisible to screenshot/screen-capture APIs while remaining
# fully visible on the real display — exactly what this overlay needs, since
# it sits on top of the FH6 window and farm_core.car_collection_finder /
# multiplier_filter_finder capture that same region via pyautogui.screenshot()
# to OCR it. Confirmed necessary in the field: without this, the overlay's
# own status text ("Searching for manufacturer 'LAMBORGHINI'...") got
# captured and OCR'd right alongside the real Manufacturers list, corrupting
# the row/column grid reconstruction and landing the search on a completely
# unrelated manufacturer ("Wuling") — see the module's git history for the
# live-testing session that caught this by diffing a Wizard-triggered run's
# OCR dump against the CLI tool's clean one. Requires Windows 10 2004+;
# silently does nothing on older Windows (falls back to the pre-fix
# behavior — screenshot-visible — rather than raising).
_WDA_EXCLUDEFROMCAPTURE = 0x00000011


class FinderStatusOverlay(QWidget):
    """Shows one status line, positioned ~10% down from the FH6 window's top
    edge and horizontally centered — clear of the window's own title bar and
    whatever menu/list the search is actively navigating below it."""

    _TOP_FRAC = 0.10

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._build_ui()

        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._reposition)
        self._timer.start()

        self._reposition()
        self.show()
        self._exclude_from_capture()

    def _exclude_from_capture(self) -> None:
        try:
            ctypes.windll.user32.SetWindowDisplayAffinity(int(self.winId()), _WDA_EXCLUDEFROMCAPTURE)
        except Exception:
            pass

    def _build_ui(self) -> None:
        self.setObjectName("finderStatusOverlay")
        self.setStyleSheet("#finderStatusOverlay { background-color: rgba(20, 20, 26, 200); border-radius: 10px; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        self._label = QLabel("")
        self._label.setStyleSheet("color: #FFFFFF; font-size: 12pt; font-weight: bold;")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

    def update_status(self, text: str) -> None:
        self._label.setText(text)
        self._reposition()

    def _reposition(self) -> None:
        region = vision.get_fh6_window_logical_region()
        if region is None:
            return
        left, top, width, height = region
        self.adjustSize()
        w = self.sizeHint().width()
        h = max(28, self.sizeHint().height())
        x = left + width // 2 - w // 2
        y = top + int(height * self._TOP_FRAC)
        screen = QApplication.screenAt(QPoint(left, top)) or QApplication.primaryScreen()
        if screen is not None:
            sg = screen.geometry()
            x = max(sg.left(), min(x, sg.left() + sg.width() - w))
        self.setGeometry(x, y, w, h)
