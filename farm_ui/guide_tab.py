"""Guide tab: a full read-through of setup and usage, built from the same
content the ⓘ info popups use (farm_ui.guide_content) — so there is one place
to read everything before ever opening Settings/Timings/Farm.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QTabWidget, QVBoxLayout, QWidget

from farm_ui.guide_content import SETTINGS_INFO, START_FROM_INFO, TIMING_INFO
from farm_ui.widgets import _sep


def _scroll_page() -> tuple[QScrollArea, QVBoxLayout]:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    container = QWidget()
    root = QVBoxLayout(container)
    root.setContentsMargins(18, 16, 18, 24)
    root.setSpacing(6)
    scroll.setWidget(container)
    return scroll, root


def _add_section(root: QVBoxLayout, title: str) -> None:
    if root.count():
        root.addSpacing(14)
    lbl = QLabel(title)
    lbl.setProperty("class", "section-label")
    root.addWidget(lbl)
    root.addWidget(_sep())


def _add_para(root: QVBoxLayout, text: str) -> None:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("padding-top: 4px;")
    lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    root.addWidget(lbl)


def _add_subhead(root: QVBoxLayout, text: str) -> None:
    lbl = QLabel(f"<b style='color:#FF6B1A;'>{text}</b>")
    lbl.setStyleSheet("padding-top: 10px;")
    root.addWidget(lbl)


class GuideTabMixin:
    """Mixed into SkillFarmWindow."""

    def _build_guide_tab(self) -> QWidget:
        root_widget = QWidget()
        outer = QVBoxLayout(root_widget)
        outer.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        outer.addWidget(tabs)

        settings_page, settings_root = _scroll_page()
        self._populate_guide_settings(settings_root)
        tabs.addTab(settings_page, "Settings")

        timings_page, timings_root = _scroll_page()
        self._populate_guide_timings(timings_root)
        tabs.addTab(timings_page, "Timings")

        start_page, start_root = _scroll_page()
        self._populate_guide_starting_points(start_root)
        tabs.addTab(start_page, "Starting Points")

        return root_widget

    @staticmethod
    def _populate_guide_settings(root: QVBoxLayout) -> None:
        _add_para(
            root,
            "Everything below needs to be filled in on the Settings tab before "
            "you can start the farm — unless Challenge Only is ticked on the "
            "Farm tab, which skips the Car Collection and 9x multiplier car "
            "requirements entirely (challenge-only never buys, unlocks, or "
            "removes cars).",
        )

        _add_para(
            root,
            "Why manual entry for the Car Collection position and 9x "
            "multiplier car, instead of the app just knowing? These come "
            "from your own account's Car Collection / My Cars lists, which "
            "are different for everyone — how many cars you own and which "
            "ones shifts the exact row/column for any given car. Hardcoding "
            "fixed positions would break the moment FH6 adds new cars in a "
            "game update, or the moment your own garage changes at all — "
            "typing these in once per account (and re-checking them after "
            "any garage change) keeps the tool working across updates "
            "instead of needing constant maintenance to chase a moving "
            "target.",
        )

        _add_section(root, "FARM CAR")
        _add_para(
            root,
            "Pick the car this farm should buy, unlock, and remove each cycle "
            "from the dropdown. Its price, skill points to unlock, and "
            "reward (wheelspins, a straight CR payout, or both — not every "
            "car grants the same thing) are shown read-only underneath once "
            "selected, only showing the reward types that car actually has — "
            "these come from the app's built-in car data, not something you "
            "type in.",
        )

        title, text = SETTINGS_INFO["soko78"]
        _add_section(root, title.upper())
        _add_para(root, text)

        title, text = SETTINGS_INFO["car_collection"]
        _add_section(root, title.upper())
        _add_para(root, text)

        _add_section(root, "CHALLENGE SHARE CODE")
        _add_para(
            root,
            "The share code for the challenge used to farm skill points. This "
            "is copy-only in the app — use the Copy button next to it to grab "
            "the code, then paste it into the in-game challenge search when "
            "setting up the Challenge starting point (see the Starting Points "
            "guide tab).",
        )

        title, text = SETTINGS_INFO["multiplier_filter"]
        _add_section(root, title.upper())
        _add_para(root, text)

        title, text = SETTINGS_INFO["multiplier_position"]
        _add_section(root, title.upper())
        _add_para(root, text)

        root.addStretch()

    @staticmethod
    def _populate_guide_timings(root: QVBoxLayout) -> None:
        _add_para(
            root,
            "Timings control how long the farm waits after each key press or "
            "screen transition. The defaults are tuned for a mid-range PC — "
            "adjust them if the farm misses inputs (too fast for your PC) or "
            "feels sluggish (too slow). Each field has a minimum floor (1/5 of "
            "its default) low enough to tune but not so low the game reliably "
            "drops the input.",
        )

        _add_para(
            root,
            "Separately from timing: prefer fullscreen, or a large window "
            "— avoid 4:3/unusual aspect ratios. All screen detection is "
            "OCR-based, and how many real pixels actually reach the OCR "
            "engine turns out to matter more than the game's resolution "
            "setting: Windows stretches the game's internal render to "
            "whatever size the window is drawn at, so a small windowed "
            "game gets fewer real captured pixels for small HUD text "
            "(available skill points) than the same resolution "
            "setting run fullscreen — field-tested back-to-back at the "
            "identical 1280x720 setting, a small window misread available "
            "skill points (173 read as 10) while fullscreen read it "
            "correctly moments later, purely because fullscreen captured "
            "~37% more vertical pixels for the same UI element. "
            "Separately, 4:3 (1024x768) has tested unreliably in both "
            "windowed and fullscreen — avoid that regardless of window "
            "size. The retries built into these checks fall back to a "
            "safe default when a read fails, so the farm keeps running "
            "either way — but fullscreen (or a large window) means fewer "
            "of those fallbacks getting used at all.",
        )

        _add_section(root, "MENU NAVIGATION")
        for key in ("MENU_WAIT", "NAV_WAIT", "PAGE_WAIT", "TYPING_WAIT"):
            label, text = TIMING_INFO[key]
            _add_subhead(root, label)
            _add_para(root, text)

        _add_section(root, "FALLBACK TIMINGS  (used only if drivable-HUD detection doesn't confirm in time)")
        for key in (
            "LOADING_CHALLENGE_WAIT",
            "LOADING_AFTER_CHALLENGE_EXIT_WAIT",
            "LOADING_RETRY_WAIT",
            "LOADING_EXIT_TO_GAME_WAIT",
        ):
            label, text = TIMING_INFO[key]
            _add_subhead(root, label)
            _add_para(root, text)

        root.addStretch()

    @staticmethod
    def _populate_guide_starting_points(root: QVBoxLayout) -> None:
        _add_para(
            root,
            "Each starting point on the Farm tab expects the game to already "
            "be in a specific place — pick the one that matches where you are "
            "right now instead of always starting from Main Menu.",
        )

        for key in ("main", "challenge", "buy", "unlock", "remove"):
            label, text = START_FROM_INFO[key]
            _add_section(root, label.upper())
            _add_para(root, text)

        root.addStretch()
