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
  overlay.py                 IngameOverlay — optional always-on-top HUD shown over the FH6
                             window (Start/Stop, phase/cycle progress, last log line);
                             lifecycle owned by FarmTabMixin, off by default (Settings tab)
  app.py                     SkillFarmWindow (combines the tab mixins)
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
  loading finishes, before Free Roam. This *is* gated — behind
  `Settings.whats_next_enabled` (Settings tab checkbox, default off) — since
  it's a per-user game setting the tool can't detect, and sending the extra
  Escape when the screen never appears would misfire into whatever's next.
  Backing out of it repeatedly can also trigger FH6's own "Change What's
  Next?" nag (Yes / No / No, and don't ask me again) — handled the same way
  as the Rate Challenge prompt (unconditional Down, Enter → "No", harmless
  no-op if it never appears). Deliberately picks plain "No", not "don't ask
  again" — the user has What's Next on *by choice*, so the nag should keep
  coming back rather than the tool silently changing that game setting for them.

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
- `farm_settings.TIMING_PRESETS` (Fast/Mid/Slow, Timings tab preset combo, same
  apply-and-save-immediately UX as FH6-Sniper's preset combo) only varies
  `LOADING_TRAVEL_WAIT`/`LOADING_CHALLENGE_WAIT` between tiers — the two waits
  actually measured to differ between a tested desktop and a tested laptop
  running FH6 at 1024x768. Every other timing is left at `TIMING_DEFAULTS`
  across all three tiers deliberately; don't invent variance for the rest
  without a real measured data point to back it.
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
  and hope it landed on the showcase in time. Reworked to match
  `remove._select_non_farm_car_as_active()`'s existing approach: poll
  `vision._read_car_screen_buttons()` against `CAR_SHOWCASE_KEYWORDS` /
  `CAR_LOADED_MENU_KEYWORDS` instead of guessing a fixed wait (start
  polling after `CAR_LOAD_POLL_START_DELAY=5s`, every
  `CAR_LOAD_POLL_INTERVAL=1s`, give up after `CAR_LOAD_POLL_MAX_SECONDS=20s`).
  The give-up default is the *opposite* of remove.py's: Unlock almost always
  processes the farm's own freshly-bought cars, so the showcase view is by
  far the more likely true state on a give-up, unlike
  `_select_non_farm_car_as_active()` (switches to some *other*, likely-
  already-driven car, where assuming already-loaded is the better bet) —
  don't copy remove.py's give-up direction here without re-checking which
  way the odds actually point for the caller. The escape-out-of-showcase
  step only runs when the showcase is actually detected (or assumed, on
  give-up); `ENTER_SKILL_TREE` had that escape removed from its own sequence
  since it's now conditional, applied by the caller first when needed. This
  removed `LOADING_NON_PRELOADED_CAR_WAIT` entirely (from `config.py`,
  `farm_settings.TIMING_DEFAULTS`, and both the Timings tab and Guide tab's
  UNLOCK/REMOVE sections) — one fewer thing for the user to configure, and
  it also means a car already loaded from earlier the same session no
  longer needs the full non-preloaded-length wait at all. The routine
  "Waiting Ns, then polling..." / "Car hasn't been loaded before..." /
  "Car already loaded..." progress prints (in both this and
  `remove._select_non_farm_car_as_active`, which follows the same pattern
  but isn't a shared function) were removed per user feedback — silent
  during normal polling, keeping only the `[WARN]` give-up line.
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
