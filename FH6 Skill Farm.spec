# -*- mode: python ; coding: utf-8 -*-

import os, site

from PyInstaller.utils.hooks import collect_submodules

def _find_winrt_dll():
    # Search all site-packages directories (handles both venv and global installs)
    for sp in site.getsitepackages():
        p = os.path.join(sp, "winrt", "msvcp140.dll")
        if os.path.isfile(p):
            return p
    # Local .venv fallback (developer workstation)
    fallback = os.path.join(".venv", "Lib", "site-packages", "winrt", "msvcp140.dll")
    if os.path.isfile(fallback):
        return fallback
    return None

_winrt_dll = _find_winrt_dll()
_binaries = [(_winrt_dll, ".")] if _winrt_dll else []

# winrt's own imports are inside try/except so PyInstaller's static analysis can't see them at
# all. Hand-listing dotted names for the pure-Python winrt.windows.* subpackages used to work
# for most of them, but proved unreliable: winrt.windows.foundation.collections was correctly
# REQUESTED (present in the Analysis) but silently never actually bundled into the PYZ archive —
# field-confirmed via a packaged .exe's console output ("ModuleNotFoundError: no module named
# winrt.windows.foundation.collections") despite the name being spelled correctly and its files
# genuinely existing on disk. Its leaf name collides with Python's own stdlib `collections`
# module, which is the likely culprit for whatever resolution shortcut silently dropped it.
# collect_submodules() walks the REAL package directory tree on disk instead of relying on a
# hand-typed name list, so it can't silently miss a submodule (present or future) the way a
# manual list just did.
_winrt_windows_submodules = collect_submodules("winrt.windows")

a = Analysis(
    ["skill_farm_ui.py"],
    pathex=[],
    binaries=_binaries,
    datas=[
        ("assets", "assets"),
    ],
    hiddenimports=[
        # Native (.pyd) extension modules — not pure-Python packages, so
        # collect_submodules() above can't discover these; each corresponds to a real
        # .pyd confirmed installed under site-packages/winrt/.
        "winrt._winrt",
        "winrt._winrt_windows_foundation",
        "winrt._winrt_windows_foundation_collections",
        "winrt._winrt_windows_graphics_imaging",
        "winrt._winrt_windows_media_ocr",
        "winrt._winrt_windows_storage_streams",
        "winrt.runtime",
        "winrt.runtime._internals",
        "winrt.runtime.interop",
        "winrt.system",
        "winrt.system.hresult",
    ]
    + _winrt_windows_submodules,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # we use PySide6, not tkinter
        "tkinter",
        "_tkinter",
        # unused scientific/plotting stack (may be pulled in transitively via numpy/cv2)
        "matplotlib",
        # Python's own top-level test package — not needed at runtime
        # NOTE: do NOT exclude unittest — pyrect (a pyautogui dependency) imports
        # doctest which imports unittest
        "test",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="FH6 Skill Farm",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir="%LOCALAPPDATA%\\FH6SkillFarm",
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=["assets\\skillfarm.ico"],
)
