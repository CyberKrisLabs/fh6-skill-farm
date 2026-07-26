"""Bundled-resource path resolution — shared by app.py (window icon) and
wizard.py (setup-wizard screenshots).
"""

import sys
from pathlib import Path


def resource_path(relative: str) -> Path:
    """Resolve a bundled resource, handling PyInstaller's one-file extraction dir.

    During development, falls back to the repo root.
    """
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative
