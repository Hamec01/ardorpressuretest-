#!/usr/bin/env python3
"""Interactive, non-syncing acceptance check for the R3 desktop auth flow."""

import getpass
import sys

from wika_report.auth_client import (
    CredentialStorageError,
    DesktopAuthClient,
    DesktopAuthenticationError,
)
from wika_report.config import DEFAULT_SYNC_SERVER_URL


def main() -> int:
    if not sys.stdin.isatty():
        print("SMOKE_FAILED: an interactive terminal is required")
        return 2

    username = input("Username: ").strip()
    if not username:
        print("SMOKE_FAILED: username is required")
        return 2
    password = getpass.getpass("Password: ")
    try:
        client = DesktopAuthClient(DEFAULT_SYNC_SERVER_URL)
        client.login(username, password, device_label="R3 desktop acceptance")
        password = ""
        client.refresh()  # proves keyring persistence and mandatory refresh rotation
        print("DESKTOP_LOGIN_OK: True")
        print("KEYRING_REFRESH_ROTATION_OK: True")
        print("BUSINESS_SYNC_PERFORMED: False")
        return 0
    except (DesktopAuthenticationError, CredentialStorageError) as exc:
        password = ""
        print(f"SMOKE_FAILED: {exc}")
        return 1
    except Exception:
        password = ""
        print("SMOKE_FAILED: unexpected error (details suppressed)")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
