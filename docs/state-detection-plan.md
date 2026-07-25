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

1. **`buy.transition_to_buy()` — `LOADING_TRAVEL_WAIT`.** Free Roam →
   House/Festival site fast-travel. Anchor idea: some label/button unique to
   the destination menu that isn't present during the loading screen — a
   header, a tab name, whatever's stable once the site's UI is actually up.

2. **`challenge.transition_to_challenge()` — `LOADING_CHALLENGE_WAIT`.** The
   single longest wait in the app. Anchor idea: HUD becoming visible (car is
   drivable) — would need a new anchor built for this, since the previous
   candidate (reusing the stuck-check's speedometer OCR) no longer exists;
   that check was removed when the farmed challenge switched to a track with
   no wrong-direction-restart bug.

3. **`challenge.run_challenge_iteration()` — `LOADING_RETRY_WAIT`** (two call
   sites: Retry-via-Enter on a timeout, Retry-via-Escape on a finish). Same
   "is the car drivable again yet" uncertainty as #2 — likely the same anchor
   works for both.

4. **`challenge.run_challenge_iteration()` (final run) —
   `LOADING_AFTER_CHALLENGE_EXIT_WAIT`.** Already documented as "one of the
   longest waits" — landing back in Free Roam after Continue-ing out for the
   last time. Anchor idea: Free Roam HUD presence, or whatever `buy.py`'s
   very next transition already expects to see.

5. **`orchestrator.py` (Remove phase tail) — `LOADING_EXIT_TO_GAME_WAIT`.**
   Escaping the car menu back into Free Roam before navigating to Main
   Menu — already documented as varying by PC.

6. **`remove._switch_to_multiplier_car()` — the hardcoded
   `keys.mp("enter", wait=5)`** getting into the multiplier car. Not even a
   named constant, just an inline 5s guess — and it's the *exact same*
   preloaded-vs-not uncertainty already solved for Unlock
   (`unlock._wait_for_car_loaded()`). Strong candidate to reuse
   `CAR_SHOWCASE_KEYWORDS` / `CAR_LOADED_MENU_KEYWORDS` directly, same
   pattern.

## Candidates: real forks currently handled by assumption/settings (lower priority)

7. **The "What's Next" screen.** Currently gated behind a *user-configured
   setting* (`whats_next_enabled`) instead of detecting whether that screen
   is actually showing. If there's a reliable anchor (distinctive
   button-bar text), this could become self-detecting instead of relying on
   the user to correctly tell the app about their own game settings — and it
   would stop mattering if someone toggles that game setting mid-session.

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

Pick one candidate (probably #6, since it can likely reuse the existing
`CAR_SHOWCASE_KEYWORDS`/`CAR_LOADED_MENU_KEYWORDS` pattern with the least new
investigation), confirm the anchor works across at least two different
PCs/resolutions, and convert just that one — rather than converting the
whole list at once.
