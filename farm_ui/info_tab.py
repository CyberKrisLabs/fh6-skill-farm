"""Info tab mixin — version, GitHub/donate links, and update check."""

import threading
import webbrowser

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from _version import __version__
from farm_ui.widgets import _sep

try:
    import requests

    HAVE_REQUESTS = True
except ImportError:
    requests = None
    HAVE_REQUESTS = False

GITHUB_URL = "https://github.com/CyberKrisLabs/fh6-skill-farm"
RELEASES_URL = f"{GITHUB_URL}/releases"
DONATE_URL = "https://www.paypal.com/ncp/payment/W2FY4KHD58UEG"
RELEASES_API_URL = "https://api.github.com/repos/CyberKrisLabs/fh6-skill-farm/releases/latest"


class _UpdateCheckBridge(QObject):
    result = Signal(str)


_update_bridge = _UpdateCheckBridge()


def _check_updates_worker() -> None:
    if not HAVE_REQUESTS:
        _update_bridge.result.emit("⚠️ 'requests' not installed — cannot check for updates")
        return
    try:
        resp = requests.get(RELEASES_API_URL, timeout=4)
        if resp.ok:
            data = resp.json()
            tag = data.get("tag_name", "")
            release_url = data.get("html_url") or RELEASES_URL
            latest = tag.lstrip("vV")
            try:
                newer = tuple(int(x) for x in latest.split(".")) > tuple(int(x) for x in __version__.split("."))
            except ValueError:
                newer = latest != __version__
            if newer:
                _update_bridge.result.emit(
                    f'🔄 Update available: <a href="{release_url}">{tag} — download from the releases page</a>'
                )
            else:
                _update_bridge.result.emit("✅ You are up to date")
        else:
            _update_bridge.result.emit("⚠️ Update check failed")
    except Exception:
        _update_bridge.result.emit("⚠️ Update check failed (network error)")


class InfoTabMixin:
    def _build_info_tab(self) -> QWidget:
        root_widget = QWidget()
        root = QVBoxLayout(root_widget)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        root.addWidget(QLabel("<b style='font-size:14pt;'>FH6 Skill Farm</b>"))
        root.addWidget(QLabel(f"Version {__version__}"))

        root.addWidget(_sep())

        gh_row = QHBoxLayout()
        gh_row.addWidget(QLabel("View the project on GitHub"))
        gh_btn = QPushButton("Open")
        gh_btn.setFixedWidth(80)
        gh_btn.clicked.connect(lambda: webbrowser.open(GITHUB_URL))
        gh_row.addWidget(gh_btn)
        gh_row.addStretch()
        root.addLayout(gh_row)

        pp_row = QHBoxLayout()
        pp_row.addWidget(QLabel("Support the project via PayPal"))
        pp_btn = QPushButton("Donate")
        pp_btn.setFixedWidth(80)
        pp_btn.clicked.connect(lambda: webbrowser.open(DONATE_URL))
        pp_row.addWidget(pp_btn)
        pp_row.addStretch()
        root.addLayout(pp_row)

        upd_row = QHBoxLayout()
        self._update_btn = QPushButton("Check for Updates")
        self._update_btn.setFixedWidth(160)
        self._update_btn.clicked.connect(self._on_check_updates)
        upd_row.addWidget(self._update_btn)
        upd_row.addStretch()
        root.addLayout(upd_row)

        self._update_label = QLabel("")
        self._update_label.setOpenExternalLinks(True)
        root.addWidget(self._update_label)

        root.addStretch()
        return root_widget

    def _on_check_updates(self) -> None:
        self._update_btn.setEnabled(False)
        self._update_label.setText("Checking…")
        threading.Thread(target=_check_updates_worker, daemon=True).start()

    def _on_update_result(self, html: str) -> None:
        self._update_label.setText(html)
        self._update_btn.setEnabled(True)
