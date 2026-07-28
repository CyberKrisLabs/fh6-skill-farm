"""Main window: combines the Farm/Settings/Timings/Guide/Info tab mixins into
one QMainWindow, navigated via a vertical sidebar (matching FH6 Sniper's
layout) instead of a horizontal QTabWidget — each page can still use its own
internal horizontal QTabWidget (e.g. the Guide tab's Settings/Timings/Starting
Points sub-tabs).
"""

import sys
import threading

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QHBoxLayout, QListWidget, QMainWindow, QStackedWidget, QWidget

from _version import __version__
from farm_ui import theme
from farm_ui.farm_tab import FarmTabMixin
from farm_ui.guide_tab import GuideTabMixin
from farm_ui.info_tab import InfoTabMixin, _update_bridge
from farm_ui.paths import resource_path
from farm_ui.settings_tab import SettingsTabMixin
from farm_ui.timings_tab import TimingsTabMixin
from farm_ui.widgets import _log_bridge

_NAV_STYLESHEET = """
QListWidget {
    background-color: #1A1A26;
    border: none;
    border-right: 1px solid #2A2A3A;
    font-size: 11pt;
    outline: none;
}
QListWidget::item {
    padding: 14px 12px;
    color: #AAAACC;
}
QListWidget::item:selected {
    background-color: #22222E;
    color: #FFFFFF;
    border-left: 3px solid #FF6B1A;
    padding-left: 9px;
}
QListWidget::item:hover:!selected {
    background-color: #1E1E2A;
    color: #DDDDEE;
}
"""


class SkillFarmWindow(QMainWindow, FarmTabMixin, SettingsTabMixin, TimingsTabMixin, GuideTabMixin, InfoTabMixin):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"FH6 Skill Farm v{__version__}")
        self.setFixedSize(730, 720)

        try:
            icon_path = resource_path("assets/skillfarm.ico")
            if icon_path.is_file():
                self.setWindowIcon(QIcon(str(icon_path)))
        except OSError:
            pass

        self._farm_thread: threading.Thread | None = None
        self._countdown_timer = QTimer()
        self._countdown_remaining = 0
        self._countdown_timer.timeout.connect(self._tick)
        self._elapsed_seconds = 0
        self._elapsed_timer = QTimer()
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)

        self._ocr_challenge_override: tuple[int, int] | None = None  # (base, buffered) from live OCR

        # Live XP/wheelspins/CR-gained-so-far counter (Farm tab's Log header
        # row) — reset for real in FarmTabMixin._launch at the start of every
        # run; initialized here just so _on_gains_progress has something to
        # accumulate into if it ever fired before a first run.
        self._gains_seen: dict[tuple[str, int], int] = {}
        self._gained_xp = 0
        self._gained_wheelspins = 0
        self._gained_super_wheelspins = 0
        self._gained_cr = 0

        self._build_ui()
        self._update_fields()
        self._update_summary()
        _log_bridge.message.connect(self._on_log)
        _log_bridge.challenge_adjusted.connect(self._on_challenge_adjusted)
        _log_bridge.phase_progress.connect(self._on_gains_progress)
        _update_bridge.result.connect(self._on_update_result)

    def _build_ui(self) -> None:
        pages = [
            (self._build_farm_tab(), "Farm"),
            (self._build_settings_tab(), "Settings"),
            (self._build_timings_tab(), "Timings"),
            (self._build_guide_tab(), "Guide"),
            (self._build_info_tab(), "Info"),
        ]

        central = QWidget()
        h_layout = QHBoxLayout(central)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        nav = QListWidget()
        nav.setFixedWidth(130)
        nav.addItems([label for _, label in pages])
        nav.setStyleSheet(_NAV_STYLESHEET)

        stack = QStackedWidget()
        for widget, _label in pages:
            stack.addWidget(widget)

        nav.currentRowChanged.connect(stack.setCurrentIndex)
        nav.setCurrentRow(0)

        h_layout.addWidget(nav)
        h_layout.addWidget(stack)
        self.setCentralWidget(central)


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(theme.STYLESHEET)
    win = SkillFarmWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
