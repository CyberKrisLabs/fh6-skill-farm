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
  car_collection_finder.py find_car(target, log) — automated Car Collection position
                           finder behind the Setup Wizard's "Find Automatically" button
                           (farm_ui/wizard.py) and the standalone tools/car_collection_finder.py
                           CLI. Promoted out of a tools/ prototype once proven out — see
                           docs/car-position-autodetect-plan.md for the full design/
                           field-testing history. Opens the Manufacturers list, burst-
                           scans + OCRs to jump to the target's manufacturer, then
                           burst-scans Car Collection for the exact car — all via full-
                           window OCR word positions reconstructed into a row/column
                           grid (build_grid()), not fixed-% crops, plus a color-based
                           (not OCR) selection-highlight detector (find_highlight_box())
                           to locate the cursor. Returns a FindResult (success, message,
                           recorded [key, count] sequence) instead of raising — `log`
                           defaults to print() for the CLI, the Wizard passes a Qt-signal
                           emitter instead so this module never touches Qt directly.
                           compress_sequence() (shared with multiplier_filter_finder.py)
                           collapses the raw recorded path's burst-scan exploration
                           (overshoot-then-correct, e.g. down 8 ×4 then up 6) into its net
                           per-axis delta before the sequence is returned/saved — replay
                           (buy.py/remove.py) only ever needs the destination, not the
                           search's own exploration steps, so this makes every future
                           replay faster without touching how the search itself works.
                           _read_grid_retrying_empty() (shared with multiplier_filter_finder
                           .py's own _find_car_type_row) retries a burst-scan read IN PLACE
                           (no keys pressed) up to EMPTY_READ_RETRIES times if the read comes
                           back too thin (below a per-viewport min_rows floor) — field-caught:
                           a screenshot taken mid-scroll-animation can catch the screen's own
                           static header text while the actual list is still blank, and
                           without this the OLD code just pressed another burst on top of a
                           read that never really happened, silently doubling the distance
                           moved and skipping straight past the target. Both burst loops
                           (_find_manufacturer/_find_car_in_collection) also compare each
                           read's text against the PREVIOUS read and abort immediately if two
                           non-empty reads in a row are identical — genuinely reached the
                           bottom of the list, not just a bad frame — instead of burning
                           through the full burst-count ceiling or needing a manual Stop.
  multiplier_filter_finder.py find_multiplier_filter(performance_class, car_type, log,
                           on_status) — automated 9x Multiplier Car Filter finder behind
                           the Setup Wizard Step 2's "Find Automatically" button
                           (farm_ui/wizard.py) and the standalone
                           tools/multiplier_filter_finder.py CLI. Same OCR/burst-scan
                           foundation as car_collection_finder.py (reuses its
                           ocr_with_boxes()) but a different screen with two genuinely
                           different sub-problems: Performance Class (D/C/B/A/S1/S2/R/X)
                           can't be OCR'd at all — WinRT treats an isolated
                           single/double-char string as noise — so it's found via
                           multi-scale cv2.matchTemplate() against
                           assets/perf_class_templates/*.png instead; Car Type (e.g. "GT
                           Cars") is normal OCR-readable text, found the same
                           burst-scan-and-match way car_collection_finder.py finds
                           Manufacturers. Has its own cursor detector, _find_cursor_box()
                           — this screen's real per-row cursor is a thin lime-green
                           BORDER around an otherwise black row, not the solid-filled
                           highlight car_collection_finder.find_highlight_box() looks for
                           (that same hue is confusingly ALSO used by this screen's own
                           "Filter" title and section headers, which really are solid
                           fills — distinguished by fill-ratio, not just area/width).
                           Returns a FindResult, same shape/reasoning as
                           car_collection_finder.FindResult. `on_status` is a second,
                           deliberately separate callback from `log`: `log` carries every
                           verbose diagnostic line, `on_status` carries only curated
                           high-level phase text ("Scanning for Performance Class
                           'R'...") for farm_ui.finder_overlay's on-screen HUD — the
                           Wizard wires both to Qt signals, the CLI only uses `log`.
  challenge.py             Phase: Challenge (share-code search, drive, end-screen detect)
  buy.py                   Phase: Buy — _navigate_car_collection_to_car() has two
                           mutually exclusive methods depending on
                           CarConfig.car_collection_auto_found: replay the recorded
                           car_collection_finder.py sequence, or the original manual row-then-
                           column press count (the fallback, and the only method before
                           Find Automatically existed)
  unlock.py                Phase: Unlock (+ transition_to_unlock)
  remove.py                Phase: Remove — _switch_to_multiplier_car() has the same
                           two-method split as buy.py above, keyed off
                           Settings.filter_auto_found: replay the recorded
                           multiplier_filter_finder.py sequence
                           (_replay_filter_find_sequence), or the original manual
                           Performance-Class-row/Car-Type-row press counts (the
                           fallback, and the only method before Find Automatically
                           existed for this screen)
  orchestrator.py          run_phase/run_farm/_run_farm_inner — ties phases into cycles
  cli.py                   argparse entry point

farm_ui/                PySide6 GUI
  theme.py                 Stylesheet
  widgets.py                Small reusable widgets, log bridge, generic builders.
                             `_find_car_collection_bridge` — a second, separate QObject Signal
                             bridge (same cross-thread pattern as `_log_bridge`) for
                             wizard.py's "Find Automatically" — kept separate since a
                             wizard search isn't part of the main farm run's log stream.
                             `_find_multiplier_filter_bridge` — the analogous bridge for
                             Step 2's "Find Automatically", with an extra `status` Signal
                             alongside `progress`/`done`: `progress` carries
                             multiplier_filter_finder.find_multiplier_filter()'s verbose
                             `log` lines (shown in the wizard dialog's own status label,
                             same as Car Collection's), `status` carries its curated
                             `on_status` phase text, which drives finder_overlay.py's
                             on-screen HUD instead.
  farm_tab.py               Farm tab mixin — Start From / Options / Summary / Start-Stop / Log
  settings_tab.py            Settings tab mixin — farm car, Car Collection position,
                             share code, 9x multiplier car filter + position, Skip
                             Remove in Cycle, in-game overlay toggle. Both the Car
                             Collection and Multiplier Filter sections have a "Use
                             Auto-Found Position"/"Use Auto-Found Filter" checkbox
                             (same wording/behavior as wizard.py's own, kept in sync
                             so the two can't drift) — only enabled once
                             CarConfig.car_collection_auto_found / Settings.filter_auto_found
                             is true for whichever car/filter is selected; ticking it
                             disables the manual Row/Column (or Filter Row) fields
                             below and switches farm_core.buy/remove over to
                             replaying the recorded sequence, unticking re-enables
                             them and reverts to the manual fields — the recorded
                             sequence itself is never discarded either way (see
                             `car_collection_use_auto_find`/`filter_use_auto_find`).
                             A `_set_cc_mode_label`/`_set_filter_mode_label` under
                             each checkbox always states in plain text which one is
                             actually in effect (`_refresh_cc_mode_display`/
                             `_refresh_filter_mode_display`). Every field
                             auto-saves (debounced 400ms) — no Save button. A
                             `_loading_settings` guard flag stops the initial
                             programmatic field-load (on tab build) from being
                             mistaken for a user edit and auto-saving bogus
                             `*_configured` flags — see farm_tab.py's identical
                             `_loading_timings` pattern below.
  timings_tab.py             Timings tab mixin — user-editable wait constants, split
                             into "Menu Navigation" and "Fallback Timings" (the
                             latter only used when drivable-HUD OCR detection
                             doesn't confirm loading in time — see vision.py below).
                             Same auto-save + `_loading_timings` guard pattern as
                             settings_tab.py; no preset combo (removed — see
                             docs/state-detection-plan.md #1).
  guide_tab.py               Guide tab — a full read-through built from the same
                             (title, text) content guide_content.py supplies to
                             every ⓘ info popup elsewhere, so the two can't drift.
  guide_content.py           Shared explanatory text: START_FROM_INFO / SETTINGS_INFO
                             / TIMING_INFO dicts, keyed by the same strings
                             settings_tab.py/timings_tab.py/farm_tab.py look up.
  info_tab.py                 Info tab mixin — version, GitHub/donate links, update check
                             (GitHub Releases API call — the only network call in the app;
                             the "no network calls" rule above is about the game itself)
  overlay.py                 IngameOverlay — optional always-on-top HUD shown over the FH6
                             window (Start/Stop, phase/cycle progress, last log line);
                             lifecycle owned by FarmTabMixin, off by default (Settings tab)
  finder_overlay.py           FinderStatusOverlay — a much simpler always-on-top HUD than
                             IngameOverlay above: one status label, no controls, no
                             focus-based auto-hide (tied to a short automated search the
                             user is actively watching, not a long farm-run session).
                             Positioned ~10% down from the FH6 window's top edge,
                             horizontally centered. `update_status(text)` is its only
                             public method. Lifecycle (create on search start, close ~2s
                             after done/failed so the final message is actually readable)
                             is owned by wizard.py — one shared `self._search_overlay`
                             instance reused by both Step 1's and Step 2's "Find
                             Automatically" (only one search is ever in flight at a
                             time), not by this class itself.
  wizard.py                  SetupWizardDialog — 3-step guided setup for Car Collection
                             Row/Column, then 9x Multiplier Car Filter + Position (the
                             fields gating farm_tab._on_start's "Setup required" check).
                             Each step pages through wizard_content.py's
                             (image_filename, caption) slides one at a time (Prev/Next),
                             falling back to a plain instructional paragraph if a step
                             has no slides defined yet. Each Next/Finish saves
                             immediately via the same farm_settings.save()/
                             config.refresh_config() calls settings_tab.py's autosave
                             uses, so closing partway through never loses an
                             already-confirmed step. Opened from a "Setup Wizard" button
                             atop the Settings tab (`SettingsTabMixin._open_setup_wizard`)
                             and from an "Open Wizard" button on farm_tab.py's
                             "Setup required" warning dialog. `_build_step_page()`
                             deliberately renders a step's `extra_widget` (the "Find
                             Automatically" section) BEFORE its manual fields — Find
                             Automatically is the primary path, manual entry the
                             fallback, and the layout order says so.

                             Both Step 1 and Step 2 have a "Find Automatically"
                             button, same shape: confirm dialog → 5s QTimer countdown
                             (same pattern as farm_tab.py's start countdown) → a
                             background threading.Thread runs the matching farm_core
                             finder, emitting progress through its own widgets bridge
                             (queued onto the Qt thread automatically, same as
                             `_log_bridge`) — on success writes the recorded sequence,
                             sets its auto-found flag, and checks that step's "Use
                             Auto-Found Position"/"Use Auto-Found Filter" checkbox
                             (`_cc_use_auto_chk`/`_filter_use_auto_chk`); on failure
                             leaves the manual fields as the fallback.
                             `_clear_cc_auto_find`/`_clear_filter_auto_find` clear the
                             PREVIOUSLY recorded auto-found flag/sequence to
                             False/`[]` the moment a search actually commits to running
                             (countdown + focus check passed, about to press keys) —
                             not on button-click, so an attempt aborted before it even
                             starts (FH6 not focused) doesn't disturb a working result.
                             Field-requested (2026-07-27) so a re-run that FAILS can't
                             leave stale-but-still-"active"-looking data behind — but
                             the flip side is real and undocumented nowhere else: a
                             re-run that fails does NOT restore the previous good
                             result, it's simply gone until the next success. Re-running
                             "just to double-check" an already-working result is a real
                             way to lose it. That checkbox
                             — only enabled once a sequence actually exists — lets the
                             user switch back to the manual fields (which re-enable)
                             WITHOUT discarding the recorded sequence, so re-ticking it
                             later doesn't require re-running the search; a
                             `_cc_mode_label`/`_filter_mode_label` underneath always
                             states in plain text which one is actually in effect
                             (`_refresh_cc_mode_display`/`_refresh_filter_mode_display`
                             — same checkbox/labels/wording the Settings tab shows, kept
                             in sync so the two can't drift). Step 1:
                             farm_core.car_collection_finder.find_car() →
                             `_find_car_collection_bridge` →
                             CarConfig.car_collection_find_sequence/car_collection_auto_found/
                             car_collection_use_auto_find. Step 2: a Performance Class
                             combo (closed set, multiplier_filter_finder.PERFORMANCE_CLASSES)
                             + an editable Car Type combo (pre-filled from
                             multiplier_filter_finder.KNOWN_CAR_TYPES — observed values
                             from one account, NOT a confirmed-exhaustive list, hence
                             editable) feed farm_core.multiplier_filter_finder.
                             find_multiplier_filter() → `_find_multiplier_filter_bridge` →
                             Settings.filter_find_sequence/filter_auto_found/
                             filter_use_auto_find/filter_performance_class/filter_car_type.

                             Both steps' searches open ONE shared
                             finder_overlay.FinderStatusOverlay (`self._search_overlay`),
                             updated from each bridge's `status` Signal (the curated
                             `on_status` channel — see multiplier_filter_finder.py's
                             entry above for why that's separate from `progress`), closed
                             ~2s after the search finishes or immediately if the dialog
                             itself closes first. Both steps share one `self._searching`
                             flag (only one search is ever reachable at a time — nav
                             buttons, the only way to reach the other step, are disabled
                             for its whole duration) that blocks Cancel/Back/window-close
                             (`closeEvent`) while a search is in flight, so the dialog
                             can't be destroyed out from under a still-running background
                             thread.
  wizard_content.py          WIZARD_STEPS: per-step title/fallback_text/slides for
                             wizard.py — its own copy, deliberately NOT
                             guide_content.SETTINGS_INFO (that's reference text for
                             someone who already knows the app; the wizard walks a
                             first-timer through the exact in-game clicks instead).
                             Slide images live at assets/wizard/<folder>/<filename>.
  paths.py                   resource_path() — PyInstaller-safe bundled-resource
                             resolution, shared by app.py (window icon) and wizard.py
                             (screenshots)
  app.py                     SkillFarmWindow (combines the tab mixins)
```

See also `docs/state-detection-plan.md` — the active tracking doc for converting fixed
waits into OCR-based detection polling; referenced by name in several code comments
below (`buy.py`, `challenge.py`, `remove.py`).

**Cross-module rule:** wait constants and `BUFFER_ENABLED`/`CFG` live in `farm_core.config`
and get rebound at runtime by `refresh_config()`/`refresh_timings()` (called after every
Settings/Timings autosave — or Reset — while the GUI is already running). Every other module must
access them via `config.NAME` (`from farm_core import config`, then `config.MENU_WAIT`)
— never `from farm_core.config import NAME`, which would freeze at the value seen at
import time and silently stop picking up later changes. `mp()` in `keys.py` follows the
same rule for its own default argument (`wait=None`, resolved to `config.MENU_WAIT`
inside the function body, not baked into the signature).

---

## Config & Logs

Runtime settings and session logs live at `%APPDATA%\FH6SkillFarm\`:
- `skill_farm_settings.json` — car config, Car Collection/multiplier-car positions,
  share code, Timings tab values, Soko 78 house, Skip Remove in Cycle, in-game
  overlay toggle (see `farm_settings.Settings` for the full field list)
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

- **`vision._winrt_ocr_async()` takes an optional `scale: float = 2.0`
  upscale factor (2026-07-29); `vision._read_minimap_hud_text()` passes
  `scale=3.0` instead of the default.** Field-confirmed dead zone: a real
  farm run at a 2701x1563 (outer window) FH6 session logged "Drivable HUD
  not detected... proceeding anyway" despite Anna/Link genuinely being on
  screen the whole time — confirmed from a saved debug frame showing
  clearly legible "ANNA"/"LINK" badges, not a crop-position miss. Re-running
  WinRT OCR offline on that exact saved crop 5/5 times at the default 2x
  upscale returned nothing at all every time; 5/5 times at 3x it read
  `'LINK @ ANNA'` cleanly, and 1.5x/4x also worked — so this is WinRT's
  recognizer being sensitive to specific pixel dimensions after the
  upscale, not an OCR-quality or crop-position problem. Narrowing the crop
  itself (to exclude the compass graphic above the badges) was tried first
  and looked promising on one attempt, but a slightly different narrow-crop
  size on the same frame went right back to failing 3/3 — ruling out "the
  compass confuses it" as the cause, and ruling out crop-size tuning as a
  reliable fix (a differently-sized crop can just relocate to a different
  dead zone at some other window size later). `scale` defaults to 2.0
  (unchanged from before this became tunable) for every other caller —
  only override it where a dead zone is actually confirmed the same way, not
  preemptively.
- **`challenge._wait_for_drivable()` takes a keyword-only `settle_after: bool
  = False` (2026-07-29, corrected same day); `_wait_for_drivable_or_whats_next()`
  always settles.** Anna/Link render on the minimap ~2s before FH6 actually
  starts accepting input again — but what that costs depends on what kind of
  input follows, not whether it's held vs. tapped. W is continuous throttle:
  if the first instant of it doesn't register, the car just starts
  accelerating a beat late — harmless, self-correcting. An Escape into a
  menu is a discrete state transition: if THAT press is dropped (the game
  just never registered it, no error/log to show for it), the code's
  assumption "I'm now in menu X" is simply wrong, and every subsequent press
  in the sequence fires at the wrong screen, desyncing the whole flow. So
  `settle_after=True` (sleeps `DRIVABLE_SETTLE_WAIT`, 1.5s, right after HUD
  detection) is only passed by the two call sites about to fire a
  menu-opening Escape — the "What's Next" back-out inside
  `run_challenge_iteration()`, and `orchestrator._exit_remove_phase_to_game()`'s
  remove→Free Roam wait — not by challenge load or any of the three
  challenge retry call sites, whose next action is just the next race's
  throttle. An earlier version of this fix applied the settle unconditionally
  to every caller (citing "the retry loop's next W-hold" as also observed
  dropping, and reasoning that a held key "survives" the window) — both
  field-corrected the same day: the actual distinction is what a dropped
  input costs (self-correcting throttle vs. a wrongly-assumed menu state),
  not hold-duration, and the broad application was unnecessary and was
  costing ~1.5s on every single challenge iteration (real, since a cycle can
  run 90+ challenges). `_wait_for_drivable_or_whats_next()` has no such
  parameter since both of its outcomes always lead straight into a
  menu-opening key press from the caller. Deliberately NOT added to the
  give-up/timeout path either way — that path already burned the full
  `max_seconds` polling and finding nothing, so there's no reason to believe
  waiting a bit more first would help before proceeding anyway.
- **The Setup Wizard's "Find Automatically" (both steps) clears
  `keys._stop_event` right before a search commits to running
  (2026-07-29 fix), same spot as `_clear_cc_auto_find`/
  `_clear_filter_auto_find`.** `keys._stop_event` is a module-level global,
  and historically only `farm_tab._on_start()` (and `cli.py`) ever cleared
  it — Stop (Farm tab) or any `keys.mp()` call that itself detects FH6 lost
  focus both `.set()` it, and NOTHING un-set it again except starting the
  main farm. Since it's checked first-thing in every `mp()` call, once set
  it silently no-ops every future key press anywhere in the app, forever,
  until the farm is (re)started. Field-confirmed (2026-07-29): after
  clicking Stop on the Farm tab once, or after a wizard search that itself
  briefly lost focus, EVERY subsequent "Find Automatically" attempt failed
  near-instantly with `car_collection_finder`/`multiplier_filter_finder`'s
  `_SearchAborted("... lost FH6 focus ...")` — even though the Wizard's own
  pre-search `keys._fh6_focused()` check (5s countdown) correctly reported
  FH6 as focused, since that check doesn't consult `_stop_event` at all. The
  giveaway that this was stale global state, not a real focus bug: restarting
  the app always fixed it (fresh `threading.Event()`), and the main farm
  itself was never affected (it always clears the event on its own Start).
  If a similar "works once, breaks forever until restart" report comes in
  for some other feature that calls into `keys.mp()`/`_press_key()`, check
  first whether that entry point ever clears `_stop_event` before assuming
  it's a fresh bug.
- **`vision._read_car_screen_buttons()` OCRs the button bar in 4 overlapping
  horizontal slices (2026-07-27), not one pass over the full window width.**
  Field-confirmed via debug screenshots: WinRT OCR silently drops whole
  button-hint clusters (a boxed key + its label, e.g. "X Explode") when too
  many of them sit on one line — even when a narrower crop leaves the text
  fully legible, sharp, un-dimmed (ruling out image quality/resolution as
  the cause). A 2-way split wasn't narrow enough on its own (still dropped
  "X Explode" / "Y Photo Mode" / "BACKSTEG Hide UI" from the car showcase
  screen's button bar, confirmed present and legible in the debug
  screenshot of that exact half); 4 slices (`_BUTTON_BAR_SLICE_COUNT`,
  `_button_bar_slices()`) was enough. This is a cousin of the
  already-documented "isolated single/double-char string treated as noise"
  WinRT limitation (multiplier_filter_finder.py's Performance Class
  letters, described in its own architecture entry below) — just for rows
  of several small badge+label pairs rather than one isolated string.
  `_BUTTON_BAR_SLICE_COUNT` is deliberately a tunable module constant, not
  a derived value — if a future screen's button bar still drops text with
  4 slices, raise it rather than re-deriving from scratch. This function is
  shared by every screen that could show the car showcase view
  (buy/remove/unlock's CAR_SHOWCASE_KEYWORDS/CAR_LOADED_MENU_KEYWORDS
  checks, challenge.py's WHATS_NEXT_KEYWORDS check), so the fix applies
  everywhere at once without needing to touch those call sites.
- **`keys._prevent_idle()` (a harmless 1px mouse jiggle) runs every ~1s
  during `unlock._wait_for_car_loaded`'s and
  `remove._wait_for_multiplier_car_loaded`'s polling loops ONLY
  (2026-07-27) — nowhere else in the codebase.** Field-reported: selecting
  a car from the car list and waiting on its showcase-vs-loaded-menu
  detection is the one spot an idle/screensaver state has actually been
  observed engaging (~14s into a poll-only wait with zero real input) on a
  laptop. Deliberately a mouse move, not a key press: the real showcase
  screen maps Space to Drive, so a keep-alive that presses ANY key risks
  firing a real game action on a screen that's actually fine and just
  hasn't been OCR-recognized yet. This was initially over-applied to
  buy.py's and challenge.py's own long polling loops too, on the untested
  assumption they shared the same risk — reverted after the user clarified
  the screensaver has only ever actually been observed on the car-list
  "Get in Car" flow specifically. Don't re-spread this to other polling
  loops without checking first; a wrong guess here isn't cost-free (see its
  docstring for why a key-press-based keep-alive specifically would be
  worse than doing nothing).
- **`orchestrator._run_farm_inner`'s cycle loop treats "CR insufficient for
  even one car" as a special case on cycle 1 too (2026-07-27), not just from
  cycle 2 onward.** Only the `else: # challenge` branch of the initial
  buy_count/unlock_count computation derives its count from `cr` (a
  Buy/Unlock/Remove start's counts come from `skill_points`/`cars` instead,
  never from `cr`, at least for cycle 1) — so this new branch is gated on
  `start == "challenge"` specifically. Before this fix, cycle 1 always ran
  the full `phases_to_run` set regardless, meaning a `cr` too low to afford
  even one car (field-confirmed with `cr=500`, far below any real car's
  price) still drove real in-game Buy → Unlock transitions for phases that
  would do nothing (0 cars either way) — wasted actions, not just a wasted
  log line. Cycle 2+ already had the equivalent protection
  (`elif remaining_cr is not None and remaining_cr < config.CAR_PRICE_CR`);
  this closes the one gap where it didn't apply from the very first cycle.
  Sets `is_final=True` same as that later-cycle branch, since nothing in
  this loop ever increases CR — once insufficient, always insufficient, so
  there's no point looping again after the one challenge-only cycle.
- **`farm_ui.farm_tab._simulate_subsequent_cycles`'s `first_subsequent_ci`
  parameter is used as the FALLBACK top-up estimate too (2026-07-27), not
  only when its own `while` loop actually iterates.** This helper computes
  the correct, SP-aware challenge count for the very first post-Buy/Unlock/
  Remove challenge phase (`first_subsequent_ci`, derived from the user's
  entered `skill_points`) — but before this fix, that value was ONLY ever
  consumed inside the `while remaining >= config.CAR_PRICE_CR:` loop's first
  iteration. When the current cycle's own buy leaves too little CR for even
  one more car (loop never iterates — e.g. buying 1 car for ~347k of a
  500k budget), the value was silently discarded, and `final_top_up` fell
  back to `config.challenges_to_refill(initial_last_unlock)` instead — a
  formula that assumes SP was ALREADY at the 999 cap going into the last
  unlock, true from cycle 2 onward but not for a session's first
  challenge-after-buy phase, which has to climb from the user's actual
  entered `skill_points`. Field-confirmed: cars=1, skill_points=560,
  cr=500,000 showed "~5 min total" in the pre-run estimate while the real
  run needed ~48 challenges (~20-40 min) to refill SP — the correct 48-value
  was computed (`first_challenges`/`base_c` in `_update_summary`) but thrown
  away by this exact path. Fixed by using `first_subsequent_ci` directly as
  `final_top_up` whenever the loop's first iteration never ran, instead of
  falling through to the cycle-2+ formula. Affects both `_time_buy()` and
  `_time_unlock_remove()`, which share this one helper — fixing it here
  covers both callers at once.
- **`farm_ui.finder_overlay.FinderStatusOverlay` excludes itself from
  screenshot capture (2026-07-27), via `SetWindowDisplayAffinity(...,
  WDA_EXCLUDEFROMCAPTURE)`.** Field-caught: the overlay sits on top of the
  FH6 window to show search progress, but `farm_core.car_collection_finder`
  / `multiplier_filter_finder` read that SAME region via
  `pyautogui.screenshot()` to OCR it — a plain region screenshot captures
  whatever's visually on screen, including other windows drawn on top. The
  overlay's own status text ("Searching for manufacturer 'LAMBORGHINI'...")
  was getting OCR'd right alongside the real Manufacturers list, corrupting
  `build_grid()`'s row clustering and landing the search on a completely
  unrelated manufacturer ("Wuling") — reproduced by diffing a
  Wizard-triggered run's OCR dump against the CLI tool's clean one (the CLI
  never creates this overlay, so it was never affected). `WDA_EXCLUDEFROMCAPTURE`
  keeps the overlay visible to the user on the real display while making it
  invisible to any screenshot API — no hide-before-screenshot/show-after
  timing needed, which would otherwise require synchronizing the Qt-owned
  overlay with the finder's background search thread. Requires Windows 10
  2004+; silently falls back to the pre-fix (screenshot-visible) behavior on
  older Windows rather than raising. If a similar always-on-top overlay is
  ever added elsewhere in this codebase, check whether it can end up on top
  of a region something OCRs — `overlay.IngameOverlay` is safe today only
  because nothing currently OCRs the exact area it occupies, not because of
  any structural protection.
- **Removed (2026-07-25): stuck-start detection.** The farmed challenge was
  switched to a new share code (Festival Drag Strip) that has never shown the
  wrong-direction-restart bug the old challenge had — so the whole apparatus
  for it was deleted rather than kept dormant: `challenge.run_challenge_iteration`'s
  `check_stuck_start` param, `_reset_challenge()`, `STUCK_CHECK_*` constants,
  `vision._read_speedometer_text()`/`_is_speed_zero()`/`_speed_digit_readable()`/
  `STUCK_SPEED_THRESHOLD`, the `LOADING_RESET_WAIT` timing (Timings tab + Guide
  tab entries, `farm_settings.TIMING_DEFAULTS`), and `orchestrator.py`'s
  `retry_after_failure`/`_last_run_was_stuck_restart` plumbing around the
  three challenge-loop call sites. If a future challenge share code brings
  this bug back, re-add detection following the same shape (OCR the
  speedometer a few seconds in, restart on a near-zero reading, skip the
  check on the run right after a stuck-restart fires) rather than resurrecting
  the deleted code verbatim — re-verify the field-tuned constants
  (`STUCK_SPEED_THRESHOLD`, crop percentages, poll counts) against the new
  track/resolution instead of assuming they still apply.
- **Challenge end-screen ambiguity:** the two possible end screens (finished-on-time
  vs timed-out) have swapped Enter/Escape mappings. If OCR only catches "RETRY"
  (common to both) without "CONTINUE" or "QUIT" — **or catches none of the three
  at all** — the code assumes the failed/timed-out layout and presses Enter, never
  a pause-menu-restart sequence (Escape first). By the time this check runs, the
  challenge timer (~38s on the current track) has already elapsed, so some end
  screen is almost certainly showing — an Escape-first recovery would hit Quit on
  the actual end screen and exit the challenge entirely instead of retrying
  (confirmed happening in the field, back when this path could still fire the
  now-removed stuck-start restart sequence, which opened with Escape) — don't
  reintroduce an Escape-first recovery call for the "OCR caught nothing" case.
- **Car Collection / multiplier-car position fields are 1-based in the UI, 0-based
  in storage**, and 0 is a *legitimate* real position (top-left / first row) — not
  a usable "unset" sentinel. Whether these are configured is tracked by explicit
  `*_configured` boolean flags, not by checking for a zero value.
- **Post-challenge "Rate Challenge?" prompt:** on the *final* run of the challenge
  phase, FH6 shows a Like/Dislike/Cancel prompt after Continue-ing out — for
  everyone except whoever's account owns `config.CHALLENGE_SHARE_CODE`. Handled
  unconditionally (Down, Down, Enter → Cancel) in `run_challenge_iteration`'s
  `final` branch, regardless of whether the prompt actually appears — on the
  creator's own account the game is already in a loading screen by then, where
  these presses are a harmless no-op. Don't gate this behind a setting.
- **"What's Next" (HUD & Gameplay) extra screen:** if the user has that game
  setting on, an extra Select/Back screen appears after the post-challenge
  loading finishes, before Free Roam. **Removed (2026-07-25): the
  `Settings.whats_next_enabled` Settings-tab checkbox** that used to gate
  this, since the tool couldn't detect the screen and had to be told about
  the user's own game setting. Replaced with direct detection
  (`vision.WHATS_NEXT_KEYWORDS = {"SELECT", "BACK"}`,
  `farm_core.challenge._wait_for_drivable_or_whats_next`) — field-tested to
  show no meaningful timing difference between exiting a challenge with vs.
  without "What's Next" on (~14-15s either way), so there was no reliable
  way to infer it from timing alone; OCR content is what actually
  distinguishes the two outcomes. "SELECT"/"BACK" are each common on other
  screens on their own (e.g. `CHALLENGE_FOUND_KEYWORDS`'s own use of
  "SELECT", in an unrelated code path) — requiring both together is only
  safe because this poll runs in the narrow post-challenge-exit window where
  Free Roam (`DRIVABLE_HUD_KEYWORDS`) or this screen are the only two
  possible outcomes, not a blind global check. It no longer matters whether
  the user remembers to flag this, or toggles the game setting mid-session.
  Backing out of it repeatedly can also trigger FH6's own "Change What's
  Next?" nag (Yes / No / No, and don't ask me again) — handled the same way
  as the Rate Challenge prompt (unconditional Down, Enter → "No", harmless
  no-op if it never appears). Deliberately picks plain "No", not "don't ask
  again" — the user has What's Next on *by choice*, so the nag should keep
  coming back rather than the tool silently changing that game setting for them.
- **Remove phase switches to the 9x multiplier car FIRST, not last
  (2026-07-25).** `remove._switch_to_multiplier_car()` now runs *before* the
  remove loop instead of after — it does double duty as both the safety
  switch away from a farm car (so the loop never tries to remove the active
  car) and prep for the next cycle's challenge, so there's no second switch
  needed at the end. `remove._select_non_farm_car_as_active()` (the old,
  separate safety-switch step) was deleted entirely. Real consequence: the
  9x Multiplier Car Position (Settings tab) must now be recorded on My Cars'
  *default* sort, not "Recently Added" like before the reorder — see the
  Settings ⓘ info. Also means starting manually from the "Remove" point
  requires NOT currently driving the multiplier car (the switch-in doesn't
  work the same way on a car you're already in, and gets stuck).
- **`Settings.skip_remove_in_cycle`** (Settings tab checkbox, off by
  default) lets the automatic buy/unlock/remove cycle skip the Remove step
  entirely, for users who'd rather keep or gift the cars themselves (e.g.
  FH6's Gift Drop — not automatable here, since its car list has no
  "Recently Added" sort or filter to isolate just the farm's own cars).
  Only gates the *automatic* cycle: explicitly picking "Remove" as the Start
  From point on the Farm tab always actually removes, regardless of this
  setting — see `orchestrator._run_farm_inner`'s manual-start exception.
  Leaving it on indefinitely without ever removing/gifting risks hitting
  FH6's 2000-car garage cap; the farm doesn't track or warn about this
  itself, it's the user's own responsibility (see the Settings ⓘ info).
- **`farm_settings.CarInfo.cr_reward`** — some farm cars (e.g. the Dodge
  Viper GTS ACR, added alongside the original Lamborghini Revuelto) grant a
  straight CR payout instead of/alongside wheelspins. The Settings tab's
  Super Wheelspins / Wheelspins / CR Reward readouts each hide themselves
  when that selected car's value is 0, rather than showing a permanent "0"
  for a reward type it doesn't have — see `settings_tab.py`'s
  `_load_car_fields()`.
- **OCR-based detection has replaced most fixed loading waits (2026-07-25).**
  See `docs/state-detection-plan.md` for the full write-up of each
  conversion (#1-7, all done) — `vision.DRIVABLE_HUD_KEYWORDS = {"ANNA",
  "LINK"}` (the co-driver name + "Link" prompt near the minimap) is the big
  one, reused via `farm_core.challenge._wait_for_drivable()` at four
  different call sites (challenge load, every retry path, the final-run
  challenge-exit, and Remove's exit-to-game wait) instead of four separate
  blind `sleep()`s. Those four `LOADING_*` Timings-tab constants are kept as
  poll *ceilings*/fallbacks, not deleted — they're what the farm falls back
  to if the HUD is never detected (e.g. the user has Anna/Link hidden in
  their own HUD & Gameplay settings, or OCR just has trouble reading them).
  `buy._wait_for_travel_loaded()` is the one exception where the old
  constant (`LOADING_TRAVEL_WAIT`) was deleted outright instead of kept as a
  fallback — its anchor is a straight reuse of an already-proven keyword set
  (`CAR_LOADED_MENU_KEYWORDS`), not a new/unverified one.
- **XP/Wheelspins/CR gains tracking (2026-07-28), both live (Farm tab's Log
  header row) and estimated (the pre-run Summary line) — see "XP and CR.txt"
  for the field-measured source numbers.** XP = challenges completed ×
  `_XP_PER_CHALLENGE` (2,500 — the ultimate skill chain reward shown after
  every challenge) + cars unlocked × (that car's `sp_to_unlock` ×
  `_XP_PER_SP_UNLOCK` (200 — exact on both the Lambo's 39 SP/7800 XP and the
  Viper's 30 SP/6000 XP) + `_XP_FIRST_SKILL_UNLOCK`). Wheelspins/Super
  Wheelspins/CR are cars unlocked × the selected car's own
  `wheelspins`/`super_wheelspins`/`cr_reward` yields (0-value ones omitted,
  same convention as the Settings tab's car-reward readouts). **CR gained
  from challenges themselves is deliberately never tracked or shown** —
  ~3,721 CR over 24 challenges (per the same notes) is noise; CR from a
  car's `cr_reward` (e.g. the Viper's 150,000 CR) very much is not, and is
  shown.
  - **`_XP_FIRST_SKILL_UNLOCK = 5000` (2026-07-30, field-reported):**
    unlocking the very first skill in a freshly-bought car's own skill tree
    pays a flat 5,000 XP separate from, and on top of, the per-SP amount
    above — every car pays this once per unlock, regardless of its own
    `sp_to_unlock`/wheelspin yields (both the Lambo and Viper confirmed to
    grant it). Not part of the `_XP_PER_SP_UNLOCK` field measurement above
    (that ratio landed on an exact 200/SP for both cars with no remainder,
    meaning the original "XP and CR.txt" totals didn't include this bonus)
    — treated as a separate, additive term rather than folded into
    `_XP_PER_SP_UNLOCK`, so a future car with a different `sp_to_unlock`
    doesn't need this constant re-derived.
  - Live counter (`farm_tab._on_gains_progress`) is fed by the existing
    `orchestrator.phase_progress_hook` (already wired for the in-game
    overlay — see `overlay.py`'s own `_on_phase_progress`), not by scraping
    log text.
  - **`_report_progress("challenge", ...)` fires only after
    `challenge.run_challenge_iteration()` returns success (2026-07-28
    follow-up fix)**, not when the iteration is announced/started — it used
    to fire right after printing `"  Challenge N/total"` and before the race
    actually ran, so the live XP counter (and the overlay's progress number)
    visibly jumped by 2,500 XP at the START of a challenge instead of at
    `"[INFO] Challenge N/total finished successfully"`, and would have
    over-counted a `[RESET] Challenge not counted — retrying` the same way
    (the retry re-announces the same N, but the OLD before-the-fact report
    had already fired once per attempt, not once per success). All three
    challenge-loop variants in `run_phase` (fixed count, skill-points-bound,
    and "run until interrupted") now only call `_report_progress` inside
    `if success:`, using the post-increment `completed`/`i`. The `unlock`
    branch got the same treatment for the same reason (report after
    `unlock.run_unlock_iteration()` returns, not before) — as a side effect
    this also means iteration 1's report now uses the SP-adjusted `effective`
    count when `run_unlock_iteration` lowers it, instead of the
    pre-adjustment value. `buy`/`remove` were deliberately left reporting
    before-the-fact — neither phase retries, and neither feeds the gains
    counter, so there was no bug to fix there.
  - `farm_tab._on_gains_progress` still dedupes on top of this (keying the
    last-seen `current` by `(phase, cycle)`, only crediting a
    strictly-increasing value) as defense-in-depth, not as the primary
    correctness mechanism anymore — the real fix is that the hook itself now
    only fires once per confirmed success.
  - Resets to nothing at the start of every run (`_launch`) and freezes at
    its final value when the run stops, same as the elapsed-time label right
    next to it.
  - Estimated totals (`_gains_estimate_str`, fed by `_time_main_challenge`/
    `_time_buy`/`_time_unlock_remove`, each now returning `(time_str,
    totals)` instead of just a string) are computed from the same whole-
    session cycle simulation (`_simulate_subsequent_cycles`) that already
    drives the time estimate — so they reflect the buffer setting and CR
    limits across every simulated cycle, not just the first one. `totals` is
    `None` when `cr<=0` (the farm loops forever in that case — same
    reasoning as `_cycle_tag`'s "↺ forever"; there's no finite total to
    show). An explicit "Start From: Remove" doesn't count *that* remove's
    own cars toward gains (they were already unlocked in an earlier run —
    only cycle 2 onward's new buy/unlock counts).
- **The Summary line's challenge-count format now depends on the Buffer
  checkbox (2026-07-28).** `Challenge 12 + 4 buffer = 16×` (showing the
  base/buffer/total breakdown) was previously shown even with the buffer
  OFF, where it degenerated to a redundant `Challenge 16 = 16×` — fixed via
  `_challenge_count_str`: buffer off → plain `x16`; buffer on → the full
  breakdown, unchanged. Applies to both `_challenge_lbl` (Main/Challenge
  start) and the unlock/remove branch's `challenge_tag` (including the OCR-
  adjusted variant).

---

## Deferred / Future Work

- **`vision._read_available_sp()`'s tight crop (`SP_ROW_TOP_FRAC=0.843`,
  `SP_ROW_HEIGHT_FRAC=0.047`) misses the "Available Points" row entirely at
  4:3 aspect ratios — not just noisily, completely empty OCR output — while
  the identical crop reads correctly at 16:9 (2026-07-29 field test, not yet
  fixed).** Tested live: FH6 windowed at 1600x1200 (4:3) with the skill tree
  open — the tight crop's OCR returned `''` (nothing), while a wider crop
  (bottom 25% of the window) found the text further down:
  `'227 0 Back ESC - Available Points Unlock All'` (227 = the real Available
  Points value, "0" the usual icon-fused-as-a-digit quirk). Switching the
  *exact same window* to 1600x900 (16:9), same skill tree screen, and the
  existing tight crop read `227` correctly on the first try — isolating the
  cause to aspect ratio, not window size/resolution/DPI/OCR noise. This
  suggests the skill-tree panel sits at a genuinely different vertical
  position (as a fraction of window height) at 4:3 vs. the 16:9-ish aspect
  `SP_ROW_TOP_FRAC`/`SP_ROW_HEIGHT_FRAC` were originally pixel-measured
  from — a real layout difference, not just fewer/noisier pixels. This is a
  second, independent reason 4:3 is unreliable, on top of whatever OCR-
  quality factors already motivate `vision.check_window_size_ok()`'s 4:3
  warning (see its own comment). **Not fixed deliberately**: 4:3 is already
  actively discouraged (the pre-flight warning tells users to avoid it
  entirely), so tuning crop percentages for a resolution the tool tells
  people not to use wasn't prioritized. If 4:3 support is ever wanted: field-
  measure the actual Available Points row position at a 4:3 aspect
  specifically (same methodology as the original `SP_ROW_TOP_FRAC`/
  `SP_ROW_HEIGHT_FRAC` derivation — see that function's own docstring/history
  above), then branch the crop fractions by aspect ratio (`_get_fh6_client_size()`
  already gives an accurate width/height to compute the aspect from) instead
  of assuming one fixed layout works everywhere.

---

## Performance / Input Rules

- All game key presses go through `keys._press_key()`/`keys.mp()` (keyDown → 50-100ms
  hold → keyUp), never bare `pyautogui.press()`. The game samples input once per
  rendered frame, so an instant down+up shorter than a frame can be dropped entirely.
- `keys.mp()` also checks `keys._fh6_focused()` before every press, same granularity
  as its `_stop_event` check — if the user tabs away from FH6 mid-run (e.g. during
  the Remove → Main Menu transition, which fired off several `mp()` calls with no
  stop-checkable gap), further presses would otherwise go to whatever window they
  switched to. Treated as a hard stop (`_stop_event.set()`), not a pause/auto-resume
  — this codebase's transitions are scripted key sequences, not a retry loop, so
  resuming mid-sequence later could leave things half-finished. Ported the idea
  from FH6-Sniper's `window_utils.is_fh6_focused()`, but checks every press (not
  once per loop iteration) since the check itself (`GetForegroundWindow` +
  `GetWindowTextW`, no pygetwindow enumeration) is cheap. Fails open (assumes
  focused) on any lookup error, so a transient OS-call hiccup can't spuriously
  stop a run.
- Timing defaults live ONLY in `farm_settings.TIMING_DEFAULTS` (source of truth for
  the Timings tab's reset-to-default and validation floors) and the matching
  constants in `farm_core/config.py`. Never introduce a second copy.
- **Removed: `farm_settings.TIMING_PRESETS`** (Fast/Mid/Slow, Timings tab
  preset combo). It only ever varied `LOADING_CHALLENGE_WAIT` between tiers
  (`LOADING_TRAVEL_WAIT` was the other one, until `buy._wait_for_travel_loaded()`
  replaced it with polling and removed the setting entirely — see
  `docs/state-detection-plan.md` #1) — and once all four remaining `LOADING_*`
  waits became fallback-only ceilings behind drivable-HUD detection
  (`docs/state-detection-plan.md` #2/#3/#4/#5), a hardware-tier preset for a
  value most users now rarely even hit stopped pulling its weight. The
  Timings tab's four loading waits now live in one "FALLBACK TIMINGS" group
  (`farm_ui/timings_tab.py`), each tuned individually if the fallback ever
  actually fires for that user — no combo box, no per-tier numbers.
- Small-HUD OCR reads (available-SP check during Unlock) are inherently less
  reliable at low game resolutions than large end-screen text — there are
  fewer real source pixels to work with, and the 2x cubic upscale in
  `vision._winrt_ocr_async` smooths the image but can't recover detail that
  was never captured. `SP_CHECK_POLL_COUNT` (3, plus a post-spend second
  chance — see below) exists to paper over this with retries, not fix it
  outright — don't be surprised if a low-resolution setup still logs an
  occasional failed read; the check already falls back to a safe default
  (proceed without the SP correction) when every attempt comes back empty.
  Field-tested resolution/aspect findings,
  one account/PC: (2026-07-21) 1024x768 (4:3) unreliable in both windowed
  and fullscreen, including outright digit misreads (not just empty reads —
  199 SP once read back as 10); 1280x720 (16:9) borderline/inconsistent
  (worked in some windowed and fullscreen tries, misread in others); 1920x1080
  (16:9) read cleanly in both windowed and fullscreen every time tried.
  (2026-07-22, after the SP_CHECK_POLL_COUNT bump to 5) 1280x768 also read
  reliably in further testing, and a fresh 1280x720 misread (173 read as 10)
  turned out — once
  `_read_available_sp()` started logging its crop region + window bounds on
  success too, not just failure (see below) — to be explained by window
  size, not resolution or aspect ratio: same 1280x720 *setting* in both
  runs, but a small windowed game window measured 1185px physical tall (237px
  crop) vs. 1620px fullscreen (324px crop) — ~37% fewer captured pixels for
  the identical UI element, purely because Windows stretches the game's
  internal render to whatever size the window is drawn at. This reframes the
  earlier "resolution/aspect ratio" guidance: what actually matters is how
  many real pixels the screenshot captures, which depends on the window's
  on-screen size (fullscreen automatically maximizes it; a small windowed
  game doesn't, regardless of resolution setting) — 4:3 (1024x768) is still
  worth avoiding separately, since that tested unreliably at both window
  sizes. See the resolution note in README.md and the Guide tab's Timings
  page.
- `vision._read_available_sp()` logs its crop region, window bounds, and
  resolution/DPI numbers (`_window_diagnostic_info()`) on a *successful*
  read too, not just on failure — this is what let a windowed-vs-fullscreen
  misread be root-caused directly from user-supplied logs (see above)
  instead of guessed at from a single failure line alone.
- **Skill-point icon fusing onto the number as an in-range false reading:**
  the skill-point icon directly after the "Available Points" number
  sometimes OCRs as a fused trailing zero (e.g. real 95 SP read as "950")
  instead of its own separate token. `vision._read_available_sp()` already
  strips a fused trailing zero when the result overshoots the 0-999 cap
  (e.g. "8410" → 841, unambiguous since >999 can't be real) — but a fusion
  that still lands in 0-999 on its own (950 is a perfectly plausible SP
  value) can't be told apart from a genuine reading by magnitude alone, and
  vision.py has no "expected SP" context to disambiguate with. Fixed one
  layer up in `unlock.run_unlock_iteration()` instead, which DOES have that
  context: if `detected_sp` is a multiple of 10 and stripping the trailing
  zero lands meaningfully closer to `expected_sp_val` (cars-so-far ×
  `SKILL_POINTS_PER_CAR`) than the raw reading does, the stripped value is
  used instead. Confirmed in the field: an inflated `detected_sp` (950
  instead of 95) fooled the residual/challenge-count math into thinking SP
  was already near the 999 cap, scheduling far too few top-up challenges
  afterward — the fix restores a normal-sized top-up.
- **A bad SP-check OCR reading used to cascade into much worse damage than
  the misread itself.** Field case (2026-07-22): a 99-challenge phase capped
  SP near 999, but the very next SP check (Unlock iteration 1, 2 cars bought)
  misread it as "10" — a different, more severe failure than the icon-fusion
  case above (most of the digits were lost, not just a trailing zero, so the
  icon-fusion fix alone can't catch it — see the plausibility-retry entry
  below, added afterward, which does). That alone was an OCR problem; what
  made it bad was three latent inconsistencies in how the result got used,
  all now fixed:
  - `run_unlock_iteration()`'s iteration 1 unconditionally runs the actual
    skill-tree unlock sequence *regardless* of what the SP check concludes
    (you're already deep in that car's skill tree by the time the check
    runs) — so `adjusted_effective` could claim "0 cars effectively
    unlocked" while iteration 1 had, in reality, just spent SP unlocking one.
    This was wrong even independent of any OCR error: the reported count
    could never legitimately go below 1. Fixed: `adjusted_effective = max(1,
    can_unlock)`.
  - The Remove phase used the *original planned* unlock count, not the
    corrected one — so with the old bug it removed both cars even though
    only one had actually been unlocked, permanently discarding the other's
    unclaimed wheelspins for nothing. Fixed: `orchestrator.py`'s cycle loop
    now reassigns `u = effective_unlocked` right after Unlock returns, so
    Remove (which runs immediately after, same cycle) only removes cars that
    were actually unlocked.
  - `last_unlock_count` (which sizes the *next* cycle's top-up via
    `challenges_to_refill`) inherited the same bad 0, producing "0
    challenges needed" for the final top-up even though real SP was nowhere
    near capped — this is what the "0 challenges" line in the log actually
    was. Fixed as a side effect of the `max(1, ...)` change above.
  Separately, `orchestrator.py`'s cycle loop no longer navigates to the
  challenge phase at all when the computed count is 0 (it used to transition
  in unconditionally, before computing the count, then immediately run zero
  iterations) — the count is now computed first and the transition is
  skipped entirely when it's 0, logging "Skipping challenge phase — 0
  challenges needed." instead.
- **SP-check plausibility retry** (added to fix the "10" case above): a
  successful OCR parse isn't automatically a good one — reading most of the
  digits wrong (999 → 10) can't be caught by range-checking alone, since 10
  is a perfectly valid-looking SP value on its own. `orchestrator.py` now
  computes `expected_sp_hint` once per cycle — `config.SKILL_POINTS_CAP` if
  a challenge phase is scheduled before Unlock this cycle (every challenge
  phase in this app is sized to reach the cap, so SP should be at/near it by
  the time Unlock's check runs), otherwise the user's own entered starting
  `skill_points` (nothing's touched SP yet if this cycle skips straight to
  Unlock/Remove) — and passes it into `run_unlock_iteration()`. A reading
  more than `max(200, hint // 2)` away from the hint (`_sp_reading_plausible`)
  triggers a retry instead of being accepted outright, using the same
  `SP_CHECK_POLL_COUNT` budget as the existing "OCR returned nothing" retry
  (both share one pool of attempts, not additive budgets). If no attempt
  ever produces a plausible reading, the hint itself is used as `detected_sp`
  instead of the implausible OCR value — acting on tracked context we
  already have beats acting on a reading we don't believe. The icon-fusion
  check above was also switched from comparing against `expected_sp_val`
  (cars-so-far × `SKILL_POINTS_PER_CAR` — how much SP is *needed*, a
  different quantity) to `expected_sp_hint` when available (an estimate of
  the actual current *total*) — comparing a total reading against a needed-
  amount baseline previously "corrected" a correct-but-large reading
  downward (e.g. a genuine 960 got mangled to 96 because 96 happened to sit
  closer to a 78-SP requirement).
- **The accurate residual-based top-up formula used to only fire on a
  session's first Unlock SP check.** `orchestrator.py`'s cycle loop computes
  two different formulas for the next challenge phase's count: an exact one
  (`residual = ocr_sp - effective_unlocked * SKILL_POINTS_PER_CAR`, top-up =
  `ceil((SKILL_POINTS_CAP - residual) / POINTS_PER_CHALLENGE)`) that uses the
  actually-detected SP, and a cruder fallback
  (`challenges_to_refill(last_unlock_count)`) that only knows how many cars
  got unlocked and assumes SP was exactly at the cap beforehand. The exact
  one used to be gated behind `if first_challenge`, i.e. only ran on a
  session's very first Unlock check (relevant for Buy/Unlock/Remove starts;
  Main/Challenge starts flip `first_challenge` False as soon as their own
  first challenge phase runs, before Unlock ever executes) — every
  subsequent cycle silently fell back to the cruder formula, ignoring
  whatever residual gap the SP check had just detected. Field-verified
  impact: SP=999 assumed, challenge run to cap, buy 2 cars, Unlock detects
  actual SP=930 (not 999) — cruder formula scheduled 8 top-up challenges;
  the exact formula (accounting for the real 852 residual, not an assumed
  936) computes 15 — the gap grows with how far actual SP is from the
  assumed cap, and was silently dropped every cycle after the first. Fixed:
  removed the `first_challenge` gate — the exact formula now runs any time
  Unlock actually reads/tracks SP (which, combined with the SP-check
  fallback-to-hint behavior above, is effectively every time). The cruder
  `challenges_to_refill` fallback still matters for cycles with no Unlock
  phase at all (e.g. the "CR exhausted, final top-up" cycle, which is
  challenge-only) — there's no fresh SP data to compute an exact residual
  from in that case, so it's the best available estimate, not a bug.
- **Retrying the SP check before spending on a car can't recover from a
  consistently-wrong reading, because the skill tree is a static menu
  screen.** Field-confirmed (2026-07-22): 5 retries in a row read the exact
  same wrong value ("10"), across sessions with different true SP totals
  (999 and 960) and identical crop/window coordinates both times — ruling
  out "random bad OCR frame" (which would vary) in favor of a deterministic
  misread of unchanging pixels. Unlike the now-removed speedometer stuck-check
  (retried against a live, changing race scene — each attempt was a genuinely
  fresh frame), nothing changes on a paused skill-tree screen between one
  screenshot and the next, so retrying just re-runs OCR on identical input
  and gets the identical (wrong) answer every time. Fixed by giving
  `run_unlock_iteration()` a genuine second chance instead of just more
  retries against the same frame: `_poll_sp_check()` (factored out of the
  inline retry loop) now runs once before `UNLOCK_SEQUENCES`, and — only if
  that pass never found anything plausible — once more right after (the
  skill tree stays open the whole time; only `EXIT_TO_CAR_LIST`'s first
  escape closes it), with the hint lowered by one `SKILL_POINTS_PER_CAR`
  and the reading added back before use. This is a real different screen
  (the Available Points count has genuinely dropped from the spend), not a
  retry against the same pixels. Only falls back to `expected_sp_hint`
  outright if *neither* pass ever produces a plausible reading.
- **Debug-image saving and the verbose window/resolution diagnostic string**
  (`vision._save_debug_image()`, `_window_diagnostic_info()`) were temporary
  — added specifically to root-cause the "always reads 10" SP misread below
  via field screenshots, then removed once that was found and fixed. Don't
  re-add either as a permanent feature without being asked; if a similar
  investigation is needed again, re-introduce them the same way (temporary,
  clearly diagnostic) rather than leaving them in for every run.
- **Root-caused the "consistently reads 10" SP misread** (2026-07-22, via
  the debug images above): it wasn't a resolution/image-quality problem —
  the field screenshot showed the skill tree's "Owned" row (a small, mostly
  car-independent value) sitting directly above "Available Points" within
  the old bottom-20%-of-window crop, and the raw OCR text
  (`'Cost Available Points 10 999 0 Select RETUR Back ESC : . Unlock All'`)
  showed WinRT reading labels-first here, not numbers-first as the parsing
  logic assumed. Walking backward from "AVAILABLE" in that order hits
  nothing (both labels come immediately before it), falls through to the
  "next digit forward" fallback, and grabs "10" (Owned's value, immediately
  after "POINTS") instead of "999" (Available Points', one token further).
  A *different* screenshot in the same log read `'100 960 0 Back ESC : . '
  'Owned Available Points Uniock All'` — numbers-first there, which the
  backward walk handles correctly — confirming WinRT's reading order for
  this row pair isn't consistent call-to-call, not that one specific order
  is reliably wrong. Fixed by pixel-measuring the actual row boundaries
  from the field screenshot (Owned ends ~83.2% of window height, Available
  Points spans ~85.5-87.6%, the button row starts ~91.9%) and tightening
  the crop (`SP_ROW_TOP_FRAC = 0.843`, `SP_ROW_HEIGHT_FRAC = 0.047`) to
  contain only the Available Points row — with Owned's number no longer in
  the token stream at all, neither reading order can be confused with it
  anymore (verified: both orders parse to 999 once Owned is excluded).
  Percentage-based, like the app's other OCR crops, so it should scale with
  window size the same way; a game update that relayouts this specific
  panel would need these two constants refit against a fresh screenshot.
- **Unlock no longer requires cars to be non-preloaded.** Previously,
  `ENTER_SKILL_TREE` unconditionally started with an escape to back out of
  the car showcase view, on the assumption every car opened during Unlock
  is freshly bought and never entered — true for the normal automated
  buy→unlock→remove cycle, but not for a user manually starting from the
  Unlock point with cars they'd already driven. `run_unlock_iteration()`
  used to just sleep `LOADING_NON_PRELOADED_CAR_WAIT` after selecting a car
  and hope it landed on the showcase in time. Reworked to match the same
  approach `remove.py`'s car-switch helper used at the time
  (`_select_non_farm_car_as_active()`, since replaced by
  `_switch_to_multiplier_car()`/`_wait_for_multiplier_car_loaded()` — see the
  Remove-phase-reorder entry below): poll `vision._read_car_screen_buttons()`
  against `CAR_SHOWCASE_KEYWORDS` / `CAR_LOADED_MENU_KEYWORDS` instead of
  guessing a fixed wait (start polling after `CAR_LOAD_POLL_START_DELAY=5s`,
  every `CAR_LOAD_POLL_INTERVAL=1s`, give up after
  `CAR_LOAD_POLL_MAX_SECONDS=20s`). The give-up default is the *opposite* of
  remove.py's: Unlock almost always processes the farm's own freshly-bought
  cars, so the showcase view is by far the more likely true state on a
  give-up, unlike remove.py's car-switch helper (which — both before and
  after the later reorder — switches to/lands on a car that's virtually
  always already-driven, where assuming already-loaded is the better bet) —
  don't copy remove.py's give-up direction here without re-checking which
  way the odds actually point for the caller. The escape-out-of-showcase
  step only runs when the showcase is actually detected (or assumed, on
  give-up); `ENTER_SKILL_TREE` had that escape removed from its own sequence
  since it's now conditional, applied by the caller first when needed. This
  removed `LOADING_NON_PRELOADED_CAR_WAIT` entirely (from `config.py`,
  `farm_settings.TIMING_DEFAULTS`, and both the Timings tab and Guide tab's
  UNLOCK/REMOVE sections, since renamed/merged — see the Fallback Timings
  entry below) — one fewer thing for the user to configure, and it also
  means a car already loaded from earlier the same session no longer needs
  the full non-preloaded-length wait at all. The routine "Waiting Ns, then
  polling..." / "Car hasn't been loaded before..." / "Car already
  loaded..." progress prints (in both this and remove.py's car-switch
  helper, which followed the same pattern but wasn't a shared function)
  were removed per user feedback — silent during normal polling, keeping
  only the `[WARN]` give-up line.
- **The Buy tab's summary line used to show a hardcoded, often-wrong
  "then {CHALLENGES_SUBSEQUENT}×/cycle"** (e.g. "4× first, then 98×/cycle")
  whenever `sp_remaining > 0` after the planned unlock — that branch never
  called `_cycle_tag`/`_simulate_subsequent_cycles` like the `else` branch
  right next to it does, so it fell back to the generic full-NUM_CARS-cycle
  constant even when the actual run (e.g. CR-limited to buying 1-2 cars at a
  time) would never come close to a full cycle. Field-confirmed: SP=999,
  buy 1 car, CR=800,000 showed "4× first, then 98×/cycle" while the *time
  estimate right below it* (which already used the correct simulation)
  correctly predicted ~13m total — the two numbers were inconsistent with
  each other. Fixed by dropping the hardcoded figure entirely and always
  calling `_cycle_tag(...)` — subsequent cycles' challenge counts can
  genuinely vary cycle-to-cycle once partial CR-limited buys are involved,
  so there was never a single accurate "Xx/cycle" figure to print here in
  the first place; the loop-count tag and the time estimate (both already
  correct) are what should carry this information, not a fixed number.
- **Two `unlock.py` message fixes, same investigation:** "more SP than
  planned" was confusing (`expected_sp_val` is how much SP is *needed* for
  these cars, not the value the user typed in — reworded to "more SP than
  needed for N cars"); and `[SP ADJUST]`'s "(was X)" comparison baseline
  used the same generic `CHALLENGES_SUBSEQUENT` constant the Buy-tab bug
  above did, so it was comparing the real, context-aware challenge count
  against a full-cycle assumption that was never relevant to a smaller
  run — fixed to compare against `challenges_to_refill(adjusted_effective)`
  instead (this run's own actual car count assumed exactly at cap
  beforehand), which also means the whole `[SP ADJUST]` line now correctly
  stays silent when detected SP exactly matches what was already assumed
  (nothing to adjust) instead of firing a spurious comparison every time.
  Also dropped the redundant "4 = 4 challenges" when the buffer adds
  nothing (`buf_adj == 0`) — now prints just "4 challenges" in that case,
  the full "base + buffer = total" breakdown only when they actually differ.
