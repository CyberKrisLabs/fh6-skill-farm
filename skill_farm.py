#!/usr/bin/env python3
# Skill farm — Wheelspin grind via car skill trees.
#
# Game changes 2026-07-13 (Playground patch):
#   - Subaru 22B raised to 300k+ CR and events nerfed to max 1 skill point per
#     race — the old Eventlab farm is dead.
#   - New farm car: Lamborghini (346,750 CR, 39 SP to unlock 1 Super Wheelspin
#     + 3 Wheelspins per car).
#   - Skill points are now farmed via CHALLENGES (share-code search, like
#     Eventlab before). The challenge forces a specific car while driving, but
#     the skill-tree perks of the car you sit in BEFORE joining still apply —
#     so the 9x skill-point multiplier car must be active when entering.
#
# Economics (Lambo defaults): 25 cars × 346,750 CR = 8,668,750 CR per cycle.
#   999 SP cap ÷ 39 SP/car = 25 cars, 975 SP used, 24 SP carry over.
#   ~10 SP per challenge → 98 challenges per subsequent cycle.
#   Car price / SP / positions are user-editable: skill_farm_settings.json
#   (GUI Settings tab). Per-car skill-tree walks: farm_core/unlock.py.
#
# Usage:
#   python skill_farm.py --start challenge                    # farm skill points (infinite)
#   python skill_farm.py --start challenge --skill-points 500 # farm from 500 to ~999
#   python skill_farm.py --start buy                          # buy → unlock → remove
#   python skill_farm.py --start unlock                       # unlock → remove
#   python skill_farm.py --start remove                       # just remove
#
# The actual implementation lives in farm_core/ (config, keys, vision,
# challenge/buy/unlock/remove, orchestrator, cli) — this file just launches it.

from farm_core.cli import main

if __name__ == "__main__":
    main()
