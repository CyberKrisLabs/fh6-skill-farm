# Releasing FH6 Skill Farm

## How it works

Pushing a version tag triggers the **Release** GitHub Actions workflow, which:

1. Builds `FH6 Skill Farm.exe` with PyInstaller
2. Packages it into `FH6_Skill_Farm_Installer_vX.Y.Z.exe` with Inno Setup
3. Creates a GitHub Release with the installer attached and auto-generated release notes

## Cutting a release

1. Bump `__version__` in `_version.py`:
   ```python
   __version__ = "0.2.0"
   ```

2. Bump `#define MyAppVersion` in `installer/installer.iss` to match:
   ```iss
   #define MyAppVersion "0.2.0"
   ```
   > **Note:** The CI workflow patches this automatically, but keeping it in sync
   > means local installer builds (see below) produce the right filename too.

3. Commit and push:
   ```powershell
   git add _version.py installer/installer.iss
   git commit -m "Bump version to 0.2.0"
   git push
   ```

4. Tag and push the tag — this triggers the release workflow:
   ```powershell
   git tag v0.2.0
   git push origin v0.2.0
   ```

5. Watch the workflow at https://github.com/CyberKrisLabs/fh6-skill-farm/actions

6. When it finishes, the release is live at https://github.com/CyberKrisLabs/fh6-skill-farm/releases

## Building locally

```powershell
pip install pyinstaller
pyinstaller "FH6 Skill Farm.spec"
# exe appears at dist\FH6 Skill Farm.exe

# Then build the installer (requires Inno Setup 6):
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\installer.iss
# installer appears at installer\Output\FH6_Skill_Farm_Installer_vX.Y.Z.exe
```

## Config & logs while testing a build

The exe reads/writes `%APPDATA%\FH6SkillFarm\skill_farm_settings.json` and
`%APPDATA%\FH6SkillFarm\logs\`, same as a dev-mode run — nothing extra to set up.

## Files

| File | Purpose |
|---|---|
| `FH6 Skill Farm.spec` | PyInstaller build spec (one-file exe; includes the winrt OCR hidden imports) |
| `installer/installer.iss` | Inno Setup installer script |
| `.github/workflows/release.yml` | CI/CD — builds and publishes on version tag push |
| `assets/skillfarm.ico` | App icon, embedded in the exe and used by the installer |
