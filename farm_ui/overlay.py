"""In-game overlay: a frameless, always-on-top HUD mirroring Start/Stop, phase/
cycle progress, and the latest log line — positioned over the FH6 window
itself so Stop is reachable without alt-tabbing back to the app. Optional,
off by default (Settings tab checkbox). Lifecycle (create/show/hide/recreate
on focus changes) is owned by farm_ui.farm_tab.FarmTabMixin.
"""

import time

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from farm_core import vision
from farm_ui.widgets import _log_bridge

try:
    import pygetwindow as gw
except ImportError:  # pragma: no cover - Windows-only dependency
    gw = None


class IngameOverlay(QWidget):
    """Mirrors the main window's Start/Stop, phase progress, and last log line."""

    # Small dark rounded "chip" background for bare labels — readable over any
    # game background, and rounded to match the buttons' own border-radius
    # (5px, set globally on QPushButton in farm_ui.theme) instead of the
    # square, unstyled box a plain QLabel gets from the app's global
    # QWidget background rule.
    _CHIP_STYLE = "color: #FFFFFF; background-color: rgba(0, 0, 0, 150); border-radius: 5px; padding: 3px 8px;"

    def __init__(self, main_window) -> None:
        super().__init__(
            None,
            Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._win = main_window
        self._user_closed = False
        self._last_interaction_time = 0.0
        self._focus_grace_until = time.time() + 2.0

        self._build_ui()

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

        _log_bridge.message.connect(self._on_log_message)
        _log_bridge.phase_progress.connect(self._on_phase_progress)
        self._refresh()
        self.show()

    def _build_ui(self) -> None:
        self.setObjectName("ingameOverlay")
        self.setStyleSheet("#ingameOverlay { background-color: rgba(20, 20, 26, 190); border-radius: 12px; }")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(6)

        top_row = QHBoxLayout()
        title = QLabel("FH6 Skill Farm")
        title.setStyleSheet(f"font-size: 11pt; font-weight: bold; margin-right: 6px; {self._CHIP_STYLE}")
        top_row.addWidget(title)

        self._start_btn = QPushButton("Start")
        self._start_btn.setFixedWidth(80)
        self._start_btn.setProperty("class", "primary-btn")
        self._start_btn.clicked.connect(self._on_start_clicked)
        self._start_btn.pressed.connect(self._on_interact)
        top_row.addWidget(self._start_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setFixedWidth(80)
        self._stop_btn.setProperty("class", "danger-btn")
        self._stop_btn.clicked.connect(self._on_stop_clicked)
        self._stop_btn.pressed.connect(self._on_interact)
        top_row.addWidget(self._stop_btn)

        self._elapsed_lbl = QLabel("⏱ 00:00:00")
        self._elapsed_lbl.setStyleSheet(self._CHIP_STYLE)
        top_row.addWidget(self._elapsed_lbl)

        self._progress_lbl = QLabel("")
        self._progress_lbl.setStyleSheet(self._CHIP_STYLE)
        top_row.addWidget(self._progress_lbl)

        top_row.addStretch()

        self._hide_btn = QPushButton("Hide")
        self._hide_btn.setFixedWidth(70)
        self._hide_btn.clicked.connect(self._on_hide_clicked)
        self._hide_btn.pressed.connect(self._on_interact)
        top_row.addWidget(self._hide_btn)

        outer.addLayout(top_row)

        self._log_lbl = QLabel("")
        self._log_lbl.setStyleSheet(
            "font-size: 9pt; color: #DDDDDD; background-color: rgba(0,0,0,0.5); padding: 4px 6px; border-radius: 5px;"
        )
        self._log_lbl.setWordWrap(False)
        # Cap width so an unusually long log line can't widen the whole
        # overlay (and with it top_row's addStretch(), pushing Hide off to
        # the right) — a long line just gets clipped instead.
        self._log_lbl.setMaximumWidth(500)
        outer.addWidget(self._log_lbl)

    def _on_interact(self) -> None:
        self._last_interaction_time = time.time()
        self._focus_grace_until = time.time() + 1.0

    def _on_start_clicked(self) -> None:
        self._win._on_start()

    def _on_stop_clicked(self) -> None:
        self._win._on_stop()

    def _on_hide_clicked(self) -> None:
        self._user_closed = True
        self.close()

    def _on_log_message(self, text: str) -> None:
        if text == "\x00DONE":
            self._log_lbl.setText("Done.")
        else:
            self._log_lbl.setText(text[:140])

    def _on_phase_progress(self, phase: str, current: int, total: int, cycle: int) -> None:
        label = phase.capitalize()
        if total:
            self._progress_lbl.setText(f"Cycle {cycle} · {label} {current}/{total}")
        else:
            self._progress_lbl.setText(f"Cycle {cycle} · {label} {current}")

    def _update_controls(self) -> None:
        running = self._win._stop_btn.isEnabled()
        self._start_btn.setEnabled(not running)
        self._stop_btn.setEnabled(running)
        h, rem = divmod(self._win._elapsed_seconds, 3600)
        m, s = divmod(rem, 60)
        self._elapsed_lbl.setText(f"⏱ {h:02d}:{m:02d}:{s:02d}")

    def _refresh(self) -> None:
        geometry = self._fh6_geometry()
        if geometry is None:
            self.close()
            return
        try:
            active = gw.getActiveWindow() if gw else None
            fh6_wins = gw.getWindowsWithTitle("Forza Horizon 6") if gw else []
            fh6 = fh6_wins[0] if fh6_wins else None
            not_focused = not active or not fh6 or active.title != fh6.title
            recent_interact = (time.time() - self._last_interaction_time) < 1.2
            grace_passed = time.time() > self._focus_grace_until
            if not_focused and grace_passed and not recent_interact:
                self.close()
                return
        except Exception:
            pass
        self.setGeometry(*geometry)
        self._update_controls()

    # Windowed FH6 has a title bar between the window's outer top (what
    # get_fh6_window_logical_region() reports) and the actual rendered game
    # content below it; fullscreen/borderless has none, so the window top IS
    # the content top. _WINDOWED_TOP_OFFSET clears a standard Windows title
    # bar; _FULLSCREEN_TOP_OFFSET is just a small visual gap from the edge.
    _FULLSCREEN_TOP_OFFSET = 4
    _WINDOWED_TOP_OFFSET = 34

    def _fh6_geometry(self) -> tuple[int, int, int, int] | None:
        region = vision.get_fh6_window_logical_region()
        if region is None:
            return None
        left, top, width, height = region
        self.adjustSize()
        w = self.sizeHint().width()
        h = max(28, self.sizeHint().height())
        x = left + width // 2 - w // 2
        screen = QApplication.screenAt(QPoint(left, top)) or QApplication.primaryScreen()
        screen_height = screen.geometry().height() if screen is not None else height
        # Heuristic: a window notably shorter than the screen is windowed
        # (has a title bar); one filling (or nearly filling) the screen
        # height is fullscreen/borderless.
        is_windowed = height < screen_height * 0.97
        y = top + (self._WINDOWED_TOP_OFFSET if is_windowed else self._FULLSCREEN_TOP_OFFSET)
        if screen is not None:
            sg = screen.geometry()
            x = max(sg.left(), min(x, sg.left() + sg.width() - w))
        return (x, y, w, h)

    def closeEvent(self, event) -> None:
        if getattr(self._win, "_ingame_overlay", None) is self:
            self._win._ingame_overlay = None
            if self._user_closed:
                self._win.overlay_hidden_by_user()
        try:
            _log_bridge.message.disconnect(self._on_log_message)
            _log_bridge.phase_progress.disconnect(self._on_phase_progress)
        except (RuntimeError, TypeError):
            pass
        super().closeEvent(event)
