# State-Detection Plan (future work, not yet started)

This is a survey + discussion doc, not an implementation plan. Nothing here is
scheduled — it's a list of *candidates* for the next person (probably the
project owner) to investigate, one at a time, by finding a reliable OCR
"anchor" (a label, button, or HUD element) for each.

## Why this doc exists

The farm already made this exact trade at a few points this project's
lifetime, converting a blind `sleep(N)` into "poll until a specific screen is
detected":

- Challenge end-screen detection (`CONTINUE` / `RETRY` / `QUIT` keywords)
- Car showcase vs. already-loaded menu (`CAR_SHOWCASE_KEYWORDS` /
  `CAR_LOADED_MENU_KEYWORDS`), used in both `remove.py` and `unlock.py`
- Challenge search found/not-found (`CHALLENGE_FOUND_KEYWORDS`)
- The available-skill-points check (`_read_available_sp`)
- The stuck-start speedometer check (since removed along with the rest of
  the wrong-direction-restart handling — the currently farmed challenge
  doesn't have that bug)

Every one of these is a spot where the *duration was genuinely unpredictable*
(loading takes however long it takes) or there's a *real fork in behavior*
depending on which screen actually shows up — exactly where a fixed wait is
worst (too short misses it, too long wastes time or a race-clock deadline)
and a wrong guess costs the most. This doc extends that same list to the
remaining fixed waits in `farm_core/`.

## IMPORTANT — read before converting anything on this list

This app was deliberately built simple at first: fixed, user-adjustable wait
constants (the Timings tab) instead of screen detection, specifically
*because* detection can vary user to user in ways a single developer testing
on 1-2 PCs can't fully see coming — a different FH6 version, a different UI
scale/theme, some regional or accessibility variant, anything only a small
fraction of users would ever hit. A wait constant degrades gracefully: if
it's a little off for someone's PC, they nudge a number in Settings and it
still works. Detection does not degrade gracefully by default: if the exact
label/keyword/layout it's looking for isn't there for some user's setup, the
farm can get stuck entirely, with no adjustable number to fix it. Converting
a wait to detection can accidentally make the farm work *worse* for whatever
odd-one-out case would have been fine with the old dumb `sleep()`.

This isn't a reason to avoid the whole idea — the conversions already done
were worth it and are documented as such in `CLAUDE.md`. It's a reason to be
careful about *how* each one gets converted:

- Prefer falling back to the old fixed-wait behavior if detection doesn't
  find anything within some reasonable timeout, rather than hanging
  indefinitely waiting for an anchor that might not exist for this user.
  (Every existing detection conversion already does this — worth keeping
  the streak going.)
- Keep the underlying wait constant around as the fallback/floor even after
  adding detection, rather than deleting it outright (contrast with
  `LOADING_NON_PRELOADED_CAR_WAIT`, which *was* safe to delete entirely,
  since detection there has a full state machine covering both outcomes,
  not just "detected or gave up").
- Test on more than one machine/resolution/game-version combo before trusting
  an anchor generalizes — the same caution already written up in `CLAUDE.md`
  for the OCR reliability findings applies here too.

## Candidates: loading transitions (clearest wins — duration genuinely varies by PC/scene)

1. ~~**`buy.transition_to_buy()` — `LOADING_TRAVEL_WAIT`.** Free Roam →
   House/Festival site fast-travel.~~ **Done.** Field-confirmed anchor: the
   fast-travel lands on the Buy & Sell tab (not a "Get in Car" flow on a
   specific car, unlike #6/Unlock), whose button bar reads Select | Back |
   Forzavista | Set as Home | Series Update | Drive right after arrival —
   the exact same `CAR_LOADED_MENU_KEYWORDS` string set `unlock`/`remove`
   already check, reused here for a different reason: FH6 shows that same
   button bar for whichever car is highlighted on *any* car-browsing screen,
   not just a specific car's own "already loaded" state, so it doubles as a
   fine "has this tab finished loading" anchor. No showcase-vs-loaded fork
   applies here at all (there's no car being individually entered), so
   unlike #6, `buy._wait_for_travel_loaded()` is a plain poll with no
   branching: settle 5s (`TRAVEL_LOAD_POLL_START_DELAY`), then poll every
   `TRAVEL_LOAD_POLL_INTERVAL`s up to `TRAVEL_LOAD_POLL_MAX_SECONDS` (30s)
   before giving up and proceeding anyway.
   `LOADING_TRAVEL_WAIT` itself — the user-tunable Timings-tab setting this
   used to be — was removed entirely rather than kept as a poll-ceiling
   fallback (contrast with this doc's general guidance above, and with #2-5's
   fallback-timings approach below, which does keep theirs): the anchor here
   is a straight reuse of an already-proven keyword set (not new/unverified),
   and 30s has generous margin over every value that setting was ever
   measured or preset at (10-12s), so there was nothing left for a user to
   usefully tune — same reasoning this doc already uses to justify
   `LOADING_NON_PRELOADED_CAR_WAIT`'s prior removal (see CLAUDE.md).

2. ~~**`challenge.transition_to_challenge()` — `LOADING_CHALLENGE_WAIT`.**
   The single longest wait in the app.~~ **Done**, alongside #3 and #5 below
   — see the shared writeup after #5.

3. ~~**`challenge.run_challenge_iteration()` — `LOADING_RETRY_WAIT`** (two
   call sites: Retry-via-Enter on a timeout, Retry-via-Escape on a
   finish).~~ **Done** — see #5.

4. ~~**`challenge.run_challenge_iteration()` (final run) —
   `LOADING_AFTER_CHALLENGE_EXIT_WAIT`.**~~ **Done** — see #5. One wrinkle
   specific to this call site, later folded into #7's fix below: if "What's
   Next" is on, that screen (not Free Roam) is what actually shows next, so
   the original version of this poll (checking only for the drivable HUD)
   just spent its full ceiling and fell back for those users — no
   regression from the old flat wait, but no early-exit speedup either.
   `_wait_for_drivable_or_whats_next()` (see #7) now checks for both
   outcomes in the same poll, closing that gap.

5. ~~**`orchestrator.py` (Remove phase tail) — `LOADING_EXIT_TO_GAME_WAIT`.**
   Escaping the car menu back into Free Roam before navigating to Main
   Menu.~~ **Done, together with #2, #3, and #4.** Field-confirmed anchor:
   the minimap HUD (bottom-left corner) shows the co-driver's name ("Anna")
   and a "Link" prompt whenever the car is actually drivable — Free Roam or
   an active challenge run — but not during a loading screen. One new
   keyword set (`vision.DRIVABLE_HUD_KEYWORDS = {"ANNA", "LINK"}`, OCR'd
   from a new bottom-left-20%x20% crop, `vision._read_minimap_hud_text()`)
   and one shared poll helper (`challenge._wait_for_drivable(settle,
   max_seconds, warn_label)`, living in `challenge.py` since
   `orchestrator.py` already imports it) replaced all four flat waits at
   once — this is what the doc meant by "the biggest remaining payoff": one
   HUD anchor covers every "is the car actually drivable yet" spot in the
   app, not just one. `settle` is scaled per call site rather than one
   shared number, since checking before a transition could plausibly finish
   just wastes OCR calls: `DRIVABLE_POLL_START_DELAY_SHORT` (5s) for
   `orchestrator.py`'s remove-exit wait (`LOADING_EXIT_TO_GAME_WAIT`,
   default 15s), `DRIVABLE_POLL_START_DELAY_MEDIUM` (15s) for the
   challenge-exit wait (`LOADING_AFTER_CHALLENGE_EXIT_WAIT`, default 20s),
   `DRIVABLE_POLL_START_DELAY_LONG` (20s) for challenge load and retry
   (`LOADING_CHALLENGE_WAIT`/`LOADING_RETRY_WAIT`, both default 30s,
   field-confirmed to never finish faster than 20s) — clamped to
   `max_seconds` if a user's tuned that ceiling below the settle (these are
   `farm_settings.TIMING_DEFAULTS`, so check there for the current numbers
   rather than trusting this doc if they're ever retuned again). Then polls
   every `DRIVABLE_POLL_INTERVAL` (1s) up to each call site's own existing
   Timings-tab wait constant, which stays as the poll ceiling/fallback —
   unlike #1's `LOADING_TRAVEL_WAIT`
   removal, this anchor is brand new, so per this doc's general guidance
   nothing gets deleted here regardless of how well it tests. **Field-tested
   and confirmed working** for challenge load, retry, and remove-exit (via a
   temporary debug instrument — OCR text + saved crop per poll attempt,
   same pattern as the prior SP-misread investigation — added to
   `vision._read_minimap_hud_text()`, confirmed the anchor, then removed
   again per CLAUDE.md's convention of not leaving that kind of
   instrumentation in permanently); "Link" sometimes OCR's as "LIN U" but
   "Anna" alone reliably satisfies the `any(...)` check, so detection still
   succeeds either way. The final-run challenge-exit call site
   (`LOADING_AFTER_CHALLENGE_EXIT_WAIT`) hasn't been exercised in the field
   yet — still worth watching for its own `[WARN]` line. Also worth adding:
   both Start-From-Main and Start-From-Challenge guide entries (and the
   README) now note that hiding Anna/Link in HUD & Gameplay settings just
   loses the early-exit benefit rather than breaking anything — the farm
   still falls back to the full Timings-tab wait.

6. ~~**`remove._switch_to_multiplier_car()` — the hardcoded
   `keys.mp("enter", wait=5)`** getting into the multiplier car.~~ **Done.**
   Replaced with `remove._wait_for_multiplier_car_loaded()`, polling
   `CAR_SHOWCASE_KEYWORDS` / `CAR_LOADED_MENU_KEYWORDS` (same pattern and
   same True/False-on-showcase return as `unlock._wait_for_car_loaded()`)
   every `CAR_LOAD_POLL_INTERVAL`s after an initial `CAR_LOAD_POLL_START_DELAY`s
   settle, up to `CAR_LOAD_POLL_MAX_SECONDS` before giving up and assuming
   already-loaded (with a `[WARN]` line) — never hangs indefinitely if the
   anchor doesn't generalize to some setup. `_switch_to_multiplier_car()`
   escapes out of the showcase view when detected, same as Unlock, so both
   preload states converge on the same screen before the orchestrator's next
   action (back into the car list, or straight out to the game for the
   skip-remove path) — that next action was previously only ever exercised
   against the already-loaded case in the field, since the multiplier car is
   driven every single cycle and is virtually never actually un-preloaded;
   the showcase branch is real but effectively untested. Give-up defaults to
   already-loaded (not showcase, unlike Unlock's default) for the same
   reason. The old fixed 5s wait is still the effective floor
   (`CAR_LOAD_POLL_START_DELAY`), so on the common already-loaded path this
   can only help (catching a slower load) or be a no-op (fast load, detected
   immediately after the floor), never regress below the old behavior — the
   showcase branch is the one part of this conversion that's genuinely new
   behavior, not just a safety net around the old one, and is worth testing
   deliberately (e.g. right after a PC restart, before the multiplier car has
   been driven at all this session) rather than assuming it's correct by
   analogy to Unlock's version.

## Candidates: real forks currently handled by assumption/settings (lower priority)

7. ~~**The "What's Next" screen.** Currently gated behind a *user-configured
   setting* (`whats_next_enabled`).~~ **Done.** Field-tested first (no
   meaningful timing difference exiting a challenge with vs. without "What's
   Next" on — ~14-15s either way — so timing alone can't distinguish the two
   outcomes; OCR content has to). Anchor: the screen's own button bar reads
   "Select | Back" (`vision.WHATS_NEXT_KEYWORDS`), read from the same crop as
   `_read_car_screen_buttons()`. Neither word is unique on its own (`SELECT`
   is also `CHALLENGE_FOUND_KEYWORDS`, a wholly different screen/code path;
   `BACK` is on plenty of menus) — requiring both together is safe here
   specifically because `challenge._wait_for_drivable_or_whats_next()` only
   ever polls this in the narrow post-challenge-exit window, where Free Roam
   (`DRIVABLE_HUD_KEYWORDS`) or this screen are the only two possible
   outcomes, not an unconstrained global check. `Settings.whats_next_enabled`
   (the Settings-tab checkbox this used to be gated behind) was removed
   entirely rather than kept as a fallback — unlike the four `LOADING_*`
   fallback timings, there's no meaningful "wait longer" number to fall back
   to for a fork this binary (either the screen is showing or it isn't), so
   a settings flag wouldn't degrade gracefully the way a wait constant does;
   it would just be a second, now-redundant way of saying the same thing
   detection already confirms directly. It no longer matters whether the
   user remembers to flag this, or toggles the game setting mid-session.

8. **The "Rate Challenge?" prompt.** Same idea — currently sent
   unconditionally, relying on it being a harmless no-op when absent. Lower
   priority than #7 since it isn't currently costing correctness, just a
   couple of no-op key presses.

## Not candidates (worth noting why, so this doesn't get relitigated later)

The skill-tree walk (`ENTER_SKILL_TREE` / `EXIT_TO_CAR_LIST` /
`UNLOCK_SEQUENCES`) and `run_buy_iteration()` / `run_remove_iteration()`'s
confirmation sequences — static-menu navigation with no loading uncertainty
(the menu structure is assumed stable, which is a cheap assumption to verify
once and rarely breaks except on a game update, which would need a code fix
either way). Easier to predict and much more likely to be the same across
different PCs than a loading duration is, so converting them to detection
would add OCR overhead and a new failure surface without fixing an actual
uncertainty.

## Suggested next step

All six loading-transition candidates (#1-6) plus #7 are done (see above).
#1 and #6 reused the existing `CAR_LOADED_MENU_KEYWORDS` anchor; #2/#3/#4/#5
needed a genuinely new one (the minimap HUD's `DRIVABLE_HUD_KEYWORDS`); #7
needed its own new one too (`WHATS_NEXT_KEYWORDS`), field-tested first to
rule out a timing-based approach before committing to OCR content. Only #8
is left, and it stays lowest priority — it isn't currently costing
correctness, just harmless no-op key presses when the prompt doesn't
actually appear.
