"""Single source of truth for the app version.

Bump this when cutting a release — see docs/releasing.md. installer/installer.iss's
#define MyAppVersion is kept in sync manually (and patched automatically by the
release workflow from the pushed git tag).
"""

__version__ = "1.4.0"
