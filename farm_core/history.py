"""Persisted history of past farm runs — a simple append-only record store,
separate from farm_settings.py (that's user configuration; this is run
outcomes) but living in the same app-data directory for the same reason
(survives past a PyInstaller temp-extraction dir).

Captured once per run by farm_ui.farm_tab, right at the "\x00DONE" sentinel
(the one point — natural completion or after Stop — where a run's final
elapsed time / gains totals are known) and shown read-only on the History tab
(farm_ui.history_tab).
"""

from __future__ import annotations

import dataclasses
import json

import farm_settings

HISTORY_PATH = farm_settings.APP_DATA_DIR / "history.json"

# Cap on how many past runs are kept — the file would otherwise grow forever.
MAX_RECORDS = 200


@dataclasses.dataclass
class HistoryRecord:
    timestamp: str  # "%Y-%m-%d_%H-%M-%S", same format as log filenames
    duration_seconds: int
    car_name: str
    start_phase: str
    wheelspins: int
    super_wheelspins: int
    cr_gained: int
    xp_gained: int
    challenges_completed: int
    cars_bought: int
    cr_spent: int  # CR spent buying farm cars — NOT the same as cr_gained (a car's cr_reward payout)


_FIELDS = {f.name for f in dataclasses.fields(HistoryRecord)}


def load_history(path=HISTORY_PATH) -> list[HistoryRecord]:
    """Load past-run records, oldest first. Ignores/skips a malformed entry
    rather than discarding the whole file, same tolerance as farm_settings.load()."""
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[WARN] Could not read {path.name} ({exc}) — history unavailable this session")
        return []
    records = []
    for entry in raw:
        try:
            records.append(HistoryRecord(**{k: v for k, v in entry.items() if k in _FIELDS}))
        except TypeError as exc:
            print(f"[WARN] Skipping malformed history entry: {exc}")
    return records


def save_history(records: list[HistoryRecord], path=HISTORY_PATH) -> None:
    path.write_text(json.dumps([dataclasses.asdict(r) for r in records], indent=2) + "\n", encoding="utf-8")


def append_record(record: HistoryRecord, path=HISTORY_PATH, max_keep: int = MAX_RECORDS) -> None:
    records = load_history(path)
    records.append(record)
    if len(records) > max_keep:
        records = records[-max_keep:]
    save_history(records, path)
