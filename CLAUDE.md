# FH6 Skill Farm — Claude Context

## Project

Windows automation tool that farms skill points in Forza Horizon 6 via the challenge
share-code loop, then cycles buy → unlock (wheelspins) → remove on a configured farm
car. Detects screen state via Windows Runtime OCR and drives the game with keyboard
automation (no memory reading / no network calls to the game).

**Platform:** Windows only (DPI scaling and window detection via ctypes/pygetwindow).
**UI framework:** PySide6.

---

## Setup

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

---

## Key Commands

| Task | Command |
|---|---|
| Run the GUI | `python skill_farm_ui.py` |
| Run the CLI | `python skill_farm.py --start challenge` |
| Lint | `ruff check .` |
| Format | `ruff format .` |
| Lint + auto-fix | `ruff check --fix . && ruff format .` |
| Tests | `pytest -q` |
| Tests with coverage | `pytest -q --cov` |

---

## Before Pushing

1. `ruff check . && ruff format --check .`
2. `pytest -q` — all tests green

CI enforces the same checks on every push.

---

## Architecture

```
skill_farm.py           Thin CLI launcher → farm_core.cli.main()
skill_farm_ui.py         Thin GUI launcher → farm_ui.app.main()
farm_settings.py        Settings dataclasses; load/save to %APPDATA%\FH6SkillFarm\

farm_core/              Core automation
  config.py               CFG load, refresh_config()/refresh_timings(), derived
                           economics, wait constants, BUFFER_ENABLED, LOGS_DIR
  keys.py                  mp()/_press_key() input primitives, stop event, watchdog
  vision.py                OCR screen-detection helpers + keyword sets
  challenge.py             Phase: Challenge (share-code search, drive, end-screen detect)
  buy.py                   Phase: Buy
  unlock.py                Phase: Unlock (+ transition_to_unlock)
  remove.py                Phase: Remove
  orchestrator.py          run_phase/run_farm/_run_farm_inner — ties phases into cycles
  cli.py                   argparse entry point

farm_ui/                PySide6 GUI
  theme.py                 Stylesheet
  widgets.py                Small reusable widgets, log bridge, generic builders
  farm_tab.py               Farm tab mixin — Start From / Options / Summary / Start-Stop / Log
  settings_tab.py            Settings tab mixin — farm car, Car Collection position,
                             share code, 9x multiplier car filter + position
  timings_tab.py             Timings tab mixin — user-editable wait constants
  info_tab.py                 Info tab mixin — version, GitHub/donate links, update check
                             (GitHub Releases API call — the only network call in the app;
                             the "no network calls" rule above is about the game itself)
  app.py                     SkillFarmWindow (combines the 4 tab mixins)
```

**Cross-module rule:** wait constants and `BUFFER_ENABLED`/`CFG` live in `farm_core.config`
and get rebound at runtime by `refresh_config()`/`refresh_timings()` (called when the
user saves Settings/Timings while the GUI is already running). Every other module must
access them via `config.NAME` (`from farm_core import config`, then `config.MENU_WAIT`)
— never `from farm_core.config import NAME`, which would freeze at the value seen at
import time and silently stop picking up later changes. `mp()` in `keys.py` follows the
same rule for its own default argument (`wait=None`, resolved to `config.MENU_WAIT`
inside the function body, not baked into the signature).

---

## Config & Logs

Runtime settings and session logs live at `%APPDATA%\FH6SkillFarm\`:
- `skill_farm_settings.json` — car config, Car Collection/multiplier-car positions,
  share code, Timings tab values (see `farm_settings.Settings`)
- `logs\*.txt` — one timestamped log per farm run

This is deliberate, not incidental — under a PyInstaller exe, `__file__` resolves
inside a temp extraction folder that's deleted on exit, so anything written next to
the script wouldn't survive between runs. Never revert to `pathlib.Path(__file__).parent`
for either of these.

Never commit `skill_farm_settings.json` (already in `.gitignore` as a defense-in-depth
measure — it shouldn't appear in the repo directory at all now).

---

## Testing Philosophy

This is a new test suite — start from the pure-logic layer and expand as you touch code:

| Layer | Approach |
|---|---|
| `farm_settings.py` (load/save/migration) | **TDD** — pure functions, easy to test first |
| `farm_core/config.py` (`_buffer_extra`, `_buffered`) | **TDD** — pure math, no side effects |
| OCR / vision helpers | **Fixture-based** — monkeypatch `pyautogui.screenshot`; avoid asserting on real WinRT OCR output |
| Phase logic / key-press sequences | **Skip or mock-heavy** — these drive real keyboard input against a running game; not meaningful to unit test beyond checking the sequence data (e.g. `UNLOCK_SEQUENCES` shape) |
| PySide6 widgets | **Test-after with pytest-qt** if the suite grows that far — not required yet |

**Running tests:**
```bash
pytest -q
pytest --cov --cov-report=term-missing
```

---

## Known Behaviors (don't "fix" these back)

- **Stuck-start detection:** after certain mid-run restarts, FH6 can spawn the
  car facing the wrong way. `challenge.run_challenge_iteration(check_stuck_start=True)`
  OCRs the speedometer ~5s in and restarts immediately if it reads near-zero,
  instead of waiting out the full ~45s challenge timer. Only checked on the run
  *after* a failure — a clean first run has never shown this bug — and skipped
  again immediately after a stuck-restart fires (confirmed to reliably fix the
  direction, so re-checking the very next run would be wasted time).
- **Challenge end-screen ambiguity:** the two possible end screens (finished-on-time
  vs timed-out) have swapped Enter/Escape mappings. If OCR only catches "RETRY"
  (common to both) without "CONTINUE" or "QUIT", the code assumes the failed/timed-out
  layout and presses Enter — *not* the pause-menu fallback, whose first key
  (Escape) would hit Quit on that screen instead of retrying.
- **Car Collection / multiplier-car position fields are 1-based in the UI, 0-based
  in storage**, and 0 is a *legitimate* real position (top-left / first row) — not
  a usable "unset" sentinel. Whether these are configured is tracked by explicit
  `*_configured` boolean flags, not by checking for a zero value.
- **Ease-in W-tap sequence** (`CHALLENGE_START_*` constants in `challenge.py`) exists
  specifically to avoid overshooting an early jump — flooring the throttle from a
  dead stop clears it too fast. These constants are tuned per-account/track and
  are not exposed in the Timings tab (unlike the `LOADING_*`/`*_WAIT` constants,
  which are).

---

## Performance / Input Rules

- All game key presses go through `keys._press_key()`/`keys.mp()` (keyDown → 50-100ms
  hold → keyUp), never bare `pyautogui.press()`. The game samples input once per
  rendered frame, so an instant down+up shorter than a frame can be dropped entirely.
- Timing defaults live ONLY in `farm_settings.TIMING_DEFAULTS` (source of truth for
  the Timings tab's reset-to-default and validation floors) and the matching
  constants in `farm_core/config.py`. Never introduce a second copy.
