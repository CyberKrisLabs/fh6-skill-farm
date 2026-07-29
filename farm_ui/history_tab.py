"""History tab mixin — read-only view of past farm runs (farm_core.history).

_refresh_history_tab() is also called by farm_tab.FarmTabMixin._record_history()
right after a run's "\x00DONE" sentinel appends a new record, so the table
stays current without needing separate "on tab shown" plumbing.
"""

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from farm_core import history

# Payout columns (what you farmed for) right after the identifying info,
# cost columns (what it took) last — the more exciting numbers stay visible
# without needing to scroll right. Full labels since the table scrolls
# horizontally rather than abbreviating everything to fit at once.
_COLUMNS = [
    "Date",
    "Duration",
    "Start Point",
    "Wheelspins",
    "Super Wheelspins",
    "CR Gained",
    "XP",
    "Bought Cars",
    "CR Spent",
]


def _format_duration(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class HistoryTabMixin:
    def _build_history_tab(self) -> QWidget:
        root_widget = QWidget()
        root = QVBoxLayout(root_widget)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        root.addWidget(QLabel("<b style='font-size:14pt;'>Run History</b>"))

        self._history_summary_lbl = QLabel("")
        root.addWidget(self._history_summary_lbl)

        self._history_table = QTableWidget(0, len(_COLUMNS))
        self._history_table.setHorizontalHeaderLabels(_COLUMNS)
        self._history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._history_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._history_table.verticalHeader().setVisible(False)
        self._history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._history_table.horizontalHeader().setStretchLastSection(False)
        root.addWidget(self._history_table)

        clear_row = QHBoxLayout()
        clear_row.addStretch()
        clear_btn = QPushButton("Clear History")
        clear_btn.clicked.connect(self._on_clear_history)
        clear_row.addWidget(clear_btn)
        root.addLayout(clear_row)

        self._refresh_history_tab()
        return root_widget

    def _refresh_history_tab(self) -> None:
        records = history.load_history()
        table = self._history_table
        table.setRowCount(len(records))
        for row, rec in enumerate(reversed(records)):  # newest first
            values = [
                rec.timestamp.replace("_", " "),
                _format_duration(rec.duration_seconds),
                rec.start_phase.capitalize(),
                str(rec.wheelspins) if rec.wheelspins else "",
                str(rec.super_wheelspins) if rec.super_wheelspins else "",
                f"{rec.cr_gained:,}" if rec.cr_gained else "",
                f"{rec.xp_gained:,}",
                str(rec.cars_bought),
                f"{rec.cr_spent:,}" if rec.cr_spent else "",
            ]
            for col, value in enumerate(values):
                table.setItem(row, col, QTableWidgetItem(value))

        if not records:
            self._history_summary_lbl.setText("No runs recorded yet.")
            return

        total_wheelspins = sum(r.wheelspins for r in records)
        total_super = sum(r.super_wheelspins for r in records)
        total_cr_gained = sum(r.cr_gained for r in records)
        total_xp = sum(r.xp_gained for r in records)
        total_bought = sum(r.cars_bought for r in records)
        total_spent = sum(r.cr_spent for r in records)
        parts = [f"{len(records)} runs"]
        if total_super:
            parts.append(f"x{total_super} Super")
        if total_wheelspins:
            parts.append(f"x{total_wheelspins} Wheelspins")
        if total_cr_gained:
            parts.append(f"{total_cr_gained:,} CR gained")
        parts.append(f"{total_xp:,} XP")
        parts.append(f"{total_bought} cars bought")
        if total_spent:
            parts.append(f"{total_spent:,} CR spent")
        self._history_summary_lbl.setText("All-time: " + "  ·  ".join(parts))

    def _on_clear_history(self) -> None:
        reply = QMessageBox.question(
            self,
            "Clear History",
            "Delete all recorded run history? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            history.save_history([])
            self._refresh_history_tab()
