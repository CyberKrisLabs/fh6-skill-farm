#!/usr/bin/env python3
"""GUI launcher for the FH6 Skill Farm automation.

Run with: python skill_farm_ui.py

The actual implementation lives in farm_ui/ (theme, widgets, farm_tab,
settings_tab, timings_tab, app) — this file just launches it.
"""

from farm_ui.app import main

if __name__ == "__main__":
    main()
