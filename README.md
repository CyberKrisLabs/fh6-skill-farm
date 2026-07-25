# FH6 Skill Farm

Automated skill point farming for Forza Horizon 6. Cycles the challenge share-code
loop for skill points, then buys, unlocks (wheelspins), and removes cars on a
configured farm car — no manual repetition required.

---

## Getting Started

**Requirements:**
- Windows 10/11 (window detection and DPI scaling use Windows-only APIs)
- Forza Horizon 6, installed and running
- Python 3.10+ (only if running from source — not needed for the packaged exe)

> **The game must be set to English.** All screen detection is OCR-based and
> matches specific English text (`CONTINUE`, `RETRY`, `SELECT`, etc.) — other
> languages won't be recognized.

> **Check Settings → Difficulty before the challenge.** Steering must NOT be
> set to "Auto-Steering" — on this challenge's drag strip layout, auto-steering
> turns the car into the wall, and the resulting wall friction slows it down
> for the rest of the run. Shifting must be set to Automatic — the throttle
> hold and timings are tuned for automatic shifting, and manual transmission
> changes acceleration behavior enough to throw off the tuned timings. No
> other difficulty/assist settings need to be touched.

> **Auto Drive must be turned off.** It shows a prompt right at the start of
> the challenge, and drives the car itself — both interfere with how the
> Challenge phase is farmed (the farm expects to be the one holding the
> throttle, and the extra prompt isn't a screen it knows how to handle).

> **Prefer fullscreen, or a large window — avoid 4:3/unusual aspect ratios.**
> All screen detection is OCR-based, and how many real pixels actually reach
> the OCR engine turns out to matter more than the game's resolution
> *setting*: Windows stretches the game's internal render to whatever size
> the window is drawn at, so a small windowed game gets fewer real captured
> pixels for small HUD text (available skill points) than
> the same resolution setting run fullscreen — field-tested back-to-back at
> the identical 1280x720 setting, a small window misread available skill
> points (173 read as 10) while fullscreen read it correctly moments later,
> purely because fullscreen captured ~37% more vertical pixels for the same
> UI element. Separately, 4:3 (1024x768) has tested unreliably in both
> windowed and fullscreen — avoid that regardless of window size. The farm
> falls back to a safe default when a read fails, so it keeps running either
> way — but fullscreen (or a large window) means fewer of those fallbacks
> get used at all.

```bash
pip install -r requirements.txt
python skill_farm_ui.py
```

1. Launch FH6 and get to Free Roam (in-car, on the map)
2. Open FH6 Skill Farm and fill in the Settings tab: farm car, Car Collection
   Row/Column, share code, and the 9x multiplier car filter + position
3. Pick a "Start From" point on the Farm tab and enter your current Skill Points
4. Hit **Start** — switch back to the game during the countdown and let it run

Each starting point has its own ⓘ info button in the app explaining exactly
where in the game to be before pressing Start.

**Why manual entry for Car Collection position and the 9x multiplier car?**
These positions come from your own account's Car Collection / My Cars lists,
which are different for everyone — how many cars you own and which ones
shifts the exact row/column for any given car. Hardcoding fixed positions
would break the moment FH6 adds new cars in a game update, or the moment your
own garage changes at all — a tool that asks you to type these in once (and
re-check them after any garage change, see the ⓘ info buttons in Settings)
keeps working across updates instead of needing constant maintenance to chase
a moving target.

---

## How It Works

The tool detects screen state with Windows Runtime OCR (challenge end screens,
car showcase button bars, available skill points) and drives the
game with held keyboard presses — no memory reading, no network calls to the
game.

**Challenge phase** — Enters the configured challenge via its share code,
holds the throttle solid from the start, and detects the end screen
(finished-on-time vs. timed-out, which have swapped Enter/Escape mappings) to
retry or continue.

**Buy → Unlock → Remove cycle** — buys the configured farm car repeatedly from
the Car Collection, opens each newly bought (non-preloaded) car to unlock its
wheelspin skill rewards, then removes them, freeing up garage space for the next
cycle.

Every key press goes through a keyDown → hold → keyUp sequence, since the game
samples input once per rendered frame and an instant press can be dropped entirely.

---

## Features

| Feature | Description |
|---|---|
| Challenge Only mode | Farm skill points via the challenge alone, bounded to ~999 SP — no car/garage setup required |
| Full cycle mode | Challenge → Buy → Unlock → Remove, repeating for as many loops as your Credits allow |
| Flexible starting point | Start from Main Menu, Challenge, Buy, Unlock, or Remove — useful for resuming a partial run |
| Time & cost estimate | Live summary of challenges/buys/unlocks, CR cost, and estimated wall-clock time before you start |
| Editable timings | Tune wait constants per your PC/connection speed in the Timings tab |
| Buffer challenges | Optional extra challenge runs to offset runs which did not yield the full 10 skill points |
| GUI & CLI | PySide6 GUI, or `skill_farm.py` for scripted/headless runs |
| Standalone EXE | Packages into a single executable with PyInstaller |

---

## CLI Usage

```bash
python skill_farm.py --start challenge --skill-points 500   # farm challenge from 500 SP to ~999
python skill_farm.py --start buy                             # buy → unlock → remove
python skill_farm.py --start unlock                           # unlock → remove
python skill_farm.py --start remove                            # just remove
python skill_farm.py --start main --cycle --cr 500000          # full loop, budget-limited
```

| Flag | Description |
|---|---|
| `--start` | Phase to begin from: `main`, `challenge`, `buy`, `unlock`, `remove` (default: `buy`) |
| `--skill-points`, `-s` | Current skill points; drives challenge count and buy count |
| `--cars` | Cars to process this run (buy count, or unlock/remove count) |
| `--cr` | Current Credits; limits buy phases to what you can afford in cycle mode |
| `--cycle` | Repeat the full flow indefinitely |
| `--countdown`, `-c` | Seconds to wait before starting (default: 5) |
| `--no-buffer` | Disable the extra buffer challenges added to offset runs that yield fewer points |

Car, share code, and grid positions are configured via `skill_farm_settings.json`
(edit through the GUI Settings tab — this file isn't meant to be hand-edited).

---

## Building a Standalone EXE

```powershell
pyinstaller "FH6 Skill Farm.spec"
```

Output: `dist\FH6 Skill Farm.exe`

The spec file includes the WinRT OCR hidden imports and the app icon. Settings
and logs are never bundled — they live in `%APPDATA%\FH6SkillFarm\` and are
created on first run, since a PyInstaller exe's own folder is a temporary
extraction directory that's deleted on exit.

---

## Project Structure

```
skill_farm.py            CLI launcher → farm_core.cli.main()
skill_farm_ui.py          GUI launcher → farm_ui.app.main()
farm_settings.py         Settings dataclasses; load/save to %APPDATA%\FH6SkillFarm\

farm_core/               Core automation
  config.py                CFG load, wait constants, derived economics
  keys.py                   Keyboard input primitives, stop event, watchdog
  vision.py                 OCR screen-detection helpers
  challenge.py              Phase: Challenge
  buy.py                    Phase: Buy
  unlock.py                 Phase: Unlock
  remove.py                 Phase: Remove
  orchestrator.py           Ties phases into cycles
  cli.py                    argparse entry point

farm_ui/                 PySide6 GUI
  farm_tab.py               Start From / Options / Summary / Start-Stop / Log
  settings_tab.py            Farm car, Car Collection position, share code, multiplier car
  timings_tab.py             User-editable wait constants
  info_tab.py                 Version, GitHub/donate links, update check
  app.py                     Main window
```

---

## Running Tests

```bash
pytest -q
pytest --cov --cov-report=term-missing
```

Settings and config tests use pure functions with `tmp_path`/`monkeypatch` fixtures
— no game or OCR dependency. Phase logic that drives real keyboard input against
a running game isn't unit-tested beyond checking sequence data shapes.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "Setup required" warning on Start | Fill in Car Collection Row/Column and the 9x multiplier car filter/position in Settings, or tick "Challenge Only" to skip car setup entirely |
| Timings feel off for your PC | Adjust the wait constants in the Timings tab and re-run |
| Farm doesn't find the right cars for Unlock/Remove | Make sure no other cars were acquired after the ones you're farming — Unlock/Remove sort by recently added |

**Config location** (useful for debugging):
- Settings: `%APPDATA%\FH6SkillFarm\skill_farm_settings.json`
- Logs: `%APPDATA%\FH6SkillFarm\logs\*.txt`

---

## Support

If this tool saves you time, consider supporting development:

[Donate via PayPal](https://www.paypal.com/ncp/payment/W2FY4KHD58UEG)
