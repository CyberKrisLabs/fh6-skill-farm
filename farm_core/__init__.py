"""Core FH6 skill-farm automation.

Submodules: config (settings + wait constants + derived economics), keys
(input primitives + watchdog), vision (OCR screen detection), challenge/buy/
unlock/remove (per-phase logic), orchestrator (run_phase/run_farm), cli
(argparse entry point used by the root skill_farm.py launcher).

Callers (farm_ui, cli) should import the specific submodule they need — e.g.
`from farm_core import config` then use `config.NUM_CARS` — rather than
expecting values re-exported here, since config.refresh_config() /
refresh_timings() rebind those names at runtime and a re-export would freeze
at whatever value was current when this package was first imported.
"""
