# Car Collection Position Auto-Detect (done — phases 1-5 below; phase 6 still open)

This started as a survey + discussion doc, mirroring `docs/state-detection-plan.md`'s
format. It's since been built and field-tested successfully (Lamborghini
Revuelto and Dodge Viper GTS ACR, both via the standalone `tools/car_collection_finder.py`
prototype and later the promoted `farm_core/car_collection_finder.py` + the Setup
Wizard's "Find Automatically" button) — see "Proposed phases" at the bottom
for what's done vs. still open. Kept as a historical record of the design
process and the several real bugs it took to get here (title-bar/highlight
color collision, row-clustering threshold miscalibration, badge-row
contamination, multi-word model name matching) — the finished code's own
comments reference specific sections of this doc rather than re-explaining
the same reasoning twice.

## The problem

The Setup Wizard's Car Collection step (`farm_ui/wizard.py`) asks the user to
manually count rows/column while scrolling the Car Collection list — tedious
for an account with several hundred owned cars (5 columns wide, so 600 cars
is ~120 rows). The idea: automate finding a specific car's position.

## The key insight that makes this tractable

Car Collection has a "Manufacturers" list (opened with Backspace from the
main list) — 4 columns wide, dynamic rows, sorted A→Z, that grows with car
packs/DLC (different per account, so it can't be hardcoded). **Important
correction from an earlier draft of this doc:** this is not a persistent
filter that narrows the visible grid — confirmed by the user, it's a
jump-to-position shortcut. Selecting a manufacturer and confirming jumps the
cursor straight to that manufacturer's first row **in the same full,
unfiltered Car Collection list** `buy.py` already navigates every cycle — it
doesn't hide the other manufacturers' cars, it just scrolls you there.

That's actually simpler than the original two-stage idea, and removes a
concern the original draft raised (see "Now unblocked" below): since the
jump lands in the *exact same coordinate space* the live farm already uses,
there's no filtered-vs-unfiltered translation problem to solve. This is
still two stages, but stage 2 is now "a short local scan from wherever the
jump landed," not a second full search:

1. Find the target car's **manufacturer**'s row/column in the Manufacturers
   list (this is the part worth burst-scanning — see below). Confirmed
   viewport: 4 columns × 12 rows visible at once (48 cells/screen) before
   any scrolling.
2. Confirm it (jump), then scan a short distance from the landing point to
   find the specific car and read off its final row/column. Confirmed
   behavior: the jump lands on the highlighted first-by-year car of that
   manufacturer, at whatever row/column that happens to be within Car
   Collection's own viewport (5 columns × 3 rows visible at once — smaller
   than the Manufacturers list). Car Collection sorts each manufacturer's
   block by **year** (Lamborghini Revuelto is 2024; the Viper GTS ACR is
   1999 Dodge), so this stage is small and ordered, not a blind scan —
   usually just a handful of cars, often fewer than one screenful.

Both stages are the same underlying problem (`find this text in a scrollable
grid, report its row/column`) — worth building as one reusable scanner, not
two separate implementations.

The car card itself (picture + text) reads model name on one line, then
`"YEAR MANUFACTURER"` below it — e.g. `"Revuelto"` / `"2024 Lamborghini"`,
`"Viper GTS ACR"` / `"1999 Dodge"`. That's the exact text stage 2 needs to
match against, and it's a further disambiguation signal beyond name alone
(manufacturer + year + model, not just model) — see "Data gap" below.

## Navigation constraint

This list only supports Up/Down/Left/Right — **no Page Up/Down**, confirmed
by the user. That rules out a true "coarse jump" the way Page Down would give
one. The practical equivalent: send a *burst* of Down presses without OCR'ing
in between, then take one screenshot/OCR pass over whatever page that landed
on, rather than pressing-then-OCR'ing on every single row. This gets most of
the same speed win (few OCR calls instead of one per row) without needing any
assumption about wraparound or page-jump keys.

Now that the Manufacturers list's viewport is confirmed (12 rows visible at
once), the burst size doesn't need to be guessed: a burst of 11 Down presses
advances almost exactly one full screen with a one-row overlap — the overlap
means the previous screen's bottom row and the new screen's top row should be
the same car, a free consistency check that the scan didn't skip anything
(e.g. from a dropped keypress). A burst of exactly 12 would tile screens
back-to-back with no overlap and no free check — worth the extra row.

A "start from whichever end of the alphabet is closer" idea (jump up-then-
wrap if the target letter is late-alphabet) was considered and set aside for
now: it depends on unverified wraparound behavior (Up from row 1 → last row),
and manufacturer names aren't evenly spread across the alphabet anyway (real
manufacturer lists skew heavily A–M), so the expected win is smaller than it
first looks. Burst-scanning downward from the top is simpler, makes no
assumptions, and self-corrects every step since it re-reads the screen after
every burst. Revisit only if burst-scanning turns out too slow in the field.

## OCR approach: whole-screen read + spatial clustering, not fixed-% crops

The concern raised: a hardcoded percentage crop for "the currently selected
row" (the same style of crop `vision._read_available_sp()` etc. already use)
is exactly the kind of thing that's broken before on this project — it
silently assumes a specific window size/scaling and breaks in ways that are
hard to notice (see CLAUDE.md's SP-misread investigation).

The fix: don't crop to a row at all. Take one full, uncropped screenshot of
the window, OCR the whole thing, and use each recognized word's **bounding
box** (WinRT's `OcrWord.bounding_rect`, not just its text) to reconstruct the
grid — cluster words by y-position into rows, then by x-position within a row
into columns. This reads real pixel positions off that specific screenshot
every time, so it isn't tied to any assumed resolution or window size the way
a percentage crop is.

**This needs a new OCR helper.** `vision._winrt_ocr_async()` today only
returns `result.text` — a flattened string, throwing away the per-line/
per-word bounding-box data the WinRT result object actually carries. A
variant that returns `[{"text": ..., "words": [{"text": ..., "rect": (x,y,w,h)}, ...]}]`
per line is a prerequisite for this whole approach. `tools/ocr_debug.py` (see
below) implements this variant standalone first, to verify the data shape
works the way this doc assumes before it's promoted into `vision.py` for real.

## Prerequisites to verify (what the debug tool is for)

None of these are confirmed yet — this is exactly why `tools/ocr_debug.py`
exists, so they can be checked against the real game before writing the real
feature:

1. ~~**Does the winrt Python projection actually expose per-word bounding
   boxes** the way assumed (`word.bounding_rect.x/.y/.width/.height`)?~~
   **Confirmed**, via `tools/ocr_debug.py` against a real desktop screenshot —
   `word.bounding_rect.{x,y,width,height}` works exactly as assumed, boxes
   line up correctly when drawn back onto the (2x-upscaled) image. One catch
   found along the way: iterating `result.lines` needs
   `winrt-Windows.Foundation.Collections`, a package `vision._winrt_ocr_async()`
   never needed (it only reads `result.text`, never iterates the line/word
   collections) — not previously in `requirements.txt`, now added.
2. ~~**How reliable is OCR on manufacturer/car name text** at this user's
   window size — the same "small text = fewer real captured pixels" risk
   already documented for the SP check.~~ **Confirmed reliable enough in
   practice** — repeated successful live runs (Lamborghini Revuelto, Dodge
   Viper GTS ACR, and a full field test against this account's 600+-car
   collection) never needed a fuzzy-match rescue; the per-word substring
   matching in `find_car_in_grid()` was enough on its own.
3. ~~**Does the Manufacturers filter behave like the 9x-multiplier filter**
   (checkbox list, Enter toggles without closing, needs an explicit
   confirm/close key)?~~ **Resolved by the correction above** — it isn't a
   filter at all, it's a jump-to-position action (confirm once, land on that
   manufacturer's first row in the full list). Simpler than the checkbox
   case: no "leave it checked or uncheck it after" question.

## Data gap

`farm_settings.CAR_CATALOG` only stores a combined `name` field today (e.g.
`"Lamborghini Revuelto"`, `"Dodge Viper GTS ACR"`) — but the car card in-game
shows three separate pieces (model, year, manufacturer), and matching against
the Manufacturers list needs manufacturer on its own. Naively splitting
`name` on the first word breaks for multi-word manufacturers (Aston Martin,
Alfa Romeo) and multi-word models. Cleanest fix: give `CarInfo` explicit
`manufacturer`, `model`, and `year` fields matching exactly what's on screen
(`model` on one line, `f"{year} {manufacturer}"` below it), rather than
deriving them from the combined `name` at OCR-match time.

## Near-duplicate name risk

Worth calling out from an actual field screenshot taken for the Setup Wizard:
the multiplier-position example showed two very similarly-named Subaru trims
sitting in adjacent rows — `"B-STI VERSION"` and `"IMPREZA 22B-STI VERSION"`.
Whatever fuzzy-match logic this uses needs to be exact enough not to confuse
those; a match that isn't clearly unique should not auto-confirm silently —
same principle as the SP-check plausibility retry (CLAUDE.md) not trusting a
single OCR read blindly.

## Now unblocked: this could help the live farm too, not just the wizard

An earlier draft of this doc assumed the Manufacturers list was a persistent
filter, and flagged that as a reason this could only ever help the one-time
Setup Wizard, not the live Buy phase (since `buy.py` navigates the plain,
unfiltered list every cycle, and a filtered view would be a different
coordinate space needing translation). Now that it's confirmed to be a
jump-to-position action *in that same unfiltered list*, that concern goes
away — there's nothing to translate.

That opens up a real, separate idea worth considering later: `buy.py` could
*also* jump via the Manufacturers list every cycle instead of walking
row-down/column-right from the very top each time. That would make the
stored position far more stable against future garage growth — a new car
pack only shifts rows *after* wherever it's inserted alphabetically, and the
manufacturer jump always lands at the right spot regardless, vs. today where
any new car anywhere in the account's whole collection can shift every row
number below it. Still a change to the live farm loop, not just the wizard,
so it's its own decision (and its own field-testing) — noted here, not
bundled into this plan.

## Safety / bounding

Automated navigation here means sending real key presses to the game, so it
must go through the same safety plumbing as every other automation path in
this app — `keys.mp()`'s `_fh6_focused()` + `_stop_event` checks — not a
bespoke input loop that bypasses them. It also needs a hard ceiling so it
can't loop forever if the target is never found. Conveniently, both lists
carry their own natural bound already visible on screen: the Car Collection
header shows something like `"4,095 / 4,125"` (owned/total — itself
OCR-readable), and the Manufacturers list is itself finite and bounded
(dozens, not thousands, of entries even with every car pack). Scanning
past either bound means "not found" and should fall back to the manual
fields, exactly like every existing OCR-detection fallback in this app
degrades to a fixed value instead of hanging.

## Proposed phases

1. ~~**Validate the OCR data shape**~~ **Done** — `tools/ocr_debug.py`
   confirmed per-word bounding boxes come back usable, and real captures
   showed how manufacturer/car name text actually OCRs (including the
   title-bar/highlight color collision and the badge-row contamination,
   both fixed along the way — see the finished code's own comments in
   `farm_core/car_collection_finder.py`).
2. ~~**Add `manufacturer`/`model`/`year` fields to `CarInfo`/`CAR_CATALOG`.**~~
   **Done.**
3. ~~**Build a generic scanner**~~ **Done** — `farm_core/car_collection_finder.py`'s
   `_find_manufacturer()`/`_find_car_in_collection()`, burst-navigate + OCR +
   `build_grid()`, used for both the Manufacturers list and the post-jump
   Car Collection scan. Ended up needing per-word (not full-phrase) matching
   for multi-word models (`find_car_in_grid()`) — a real gap found field-
   testing the Dodge Viper GTS ACR, not anticipated at design time.
4. ~~**Wire a "Find Automatically" button into the Wizard's Car Collection
   step**~~ **Done** — `farm_ui/wizard.py`, though the actual mechanism ended
   up different from what this phase originally proposed: rather than
   writing results into the Row/Column spinboxes (that assumed the earlier,
   wrong "absolute position" design), it writes a recorded navigation
   sequence to new `CarConfig.car_collection_find_sequence`/
   `car_collection_auto_found` fields, with Row/Column staying as an
   explicit, clearly-labeled fallback for whenever it hasn't been run or
   fails — see "Now unblocked" below for why an absolute position was never
   recoverable to begin with.
5. ~~**Field-test against a real, large collection (600+ cars)**~~ **Done** —
   confirmed working against this account's real Car Collection (600+ owned
   cars) for both farm cars, not just a small/typical-sized one.
6. **`buy.py`'s live per-cycle navigation now has a replay path** (see
   below), but not the fresh manufacturer-jump-every-cycle idea this phase
   originally described. What got built: `_navigate_car_collection_to_car()`
   replays whatever sequence Find Automatically already recorded — a fixed,
   pre-verified [key, count] list, no OCR at replay time — falling back to
   the manual row/column count when auto-find was never run. What's still
   open: having `buy.py` run its own manufacturer-jump-and-search from
   scratch every cycle (rather than replaying something recorded once) is a
   materially different, larger idea that's still just a consideration, not
   built.
