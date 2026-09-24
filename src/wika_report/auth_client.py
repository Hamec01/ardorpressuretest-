"""Desktop access/refresh lifecycle with OS-keyring-only refresh persistence."""

import hashlib
import time
from typing import Optional

import httpx
import keyring

from wika_report.config import normalize_sync_server_url


class DesktopAuthenticationError(RuntimeError):
    pass


class CredentialStorageError(RuntimeError):
    pass


class DesktopAuthClient:
    REFRESH_ACCOUNT = "desktop-refresh-token"

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        keyring_backend=None,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self.base_url = normalize_sync_server_url(base_url)
        self.timeout = timeout
        self._keyring = keyring_backend or keyring
        self._transport = transport
        self._access_token: Optional[str] = None
        self._access_valid_until = 0.0
        origin_key = hashlib.sha256(self.base_url.encode("utf-8")).hexdigest()[:16]
        self._service_name = f"ardor-pressure-test:{origin_key}"

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            transport=self._transport,
        )

    def _read_refresh(self) -> Optional[str]:
        try:
            return self._keyring.get_password(self._service_name, self.REFRESH_ACCOUNT)
        except Exception as exc:
            raise CredentialStorageError("Desktop credential storage is unavailable") from None

    def _save_refresh(self, value: str) -> None:
        try:
            self._keyring.set_password(self._service_name, self.REFRESH_ACCOUNT, value)
        except Exception:
            raise CredentialStorageError("Desktop credential storage is unavailable") from None

    def _delete_refresh(self) -> None:
        try:
            self._keyring.delete_password(self._service_name, self.REFRESH_ACCOUNT)
        except Exception:
            # Deletion is best-effort: some backends raise when no value exists.
            pass

    def _best_effort_remote_revoke(self, access_token: str) -> None:
        try:
            with self._client() as client:
                client.post(
                    "/api/v1/auth/logout",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
        except Exception:
            pass

    def _accept_token_pair(self, payload: dict) -> str:
        access = payload.get("access_token")
        refresh = payload.get("refresh_token")
        expires_in = payload.get("expires_in")
        if (
            not isinstance(access, str)
            or not access
            or not isinstance(refresh, str)
            or not refresh
            or "." in refresh
            or not isinstance(expires_in, int)
            or isinstance(expires_in, bool)
            or expires_in <= 0
        ):
            raise DesktopAuthenticationError("Desktop authentication response is invalid")
        try:
            self._save_refresh(refresh)
        except CredentialStorageError:
            self._best_effort_remote_revoke(access)
            self.clear_local_credentials()
            raise
        self._access_token = access
        self._access_valid_until = time.monotonic() + expires_in
        return access

    def login(self, username: str, password: str, device_label: Optional[str] = None) -> str:
        try:
            with self._client() as client:
                response = client.post(
                    "/api/v1/desktop/login",
                    json={
                        "username": username,
                        "password": password,
                        "device_label": device_label,
                    },
                )
            if response.status_code != 200:
                raise DesktopAuthenticationError("Desktop login failed")
            return self._accept_token_pair(response.json())
        except (DesktopAuthenticationError, CredentialStorageError):
            raise
        except Exception:
            raise DesktopAuthenticationError("Desktop login failed") from None

    def refresh(self) -> str:
        refresh_secret = self._read_refresh()
        if not refresh_secret:
            raise DesktopAuthenticationError("Desktop login required")
        try:
            with self._client() as client:
                response = client.post(
                    "/api/v1/desktop/token/refresh",
                    json={"refresh_token": refresh_secret},
                )
            if response.status_code != 200:
                self.clear_local_credentials()
                raise DesktopAuthenticationError("Desktop login required")
            return self._accept_token_pair(response.json())
        except (DesktopAuthenticationError, CredentialStorageError):
            raise
        except Exception:
            raise DesktopAuthenticationError("Desktop token refresh failed") from None

    def get_access_token(self) -> str:
        if self._access_token and time.monotonic() < self._access_valid_until - 30:
            return self._access_token
        return self.refresh()

    def has_saved_login(self) -> bool:
        return bool(self._read_refresh())

    def clear_local_credentials(self) -> None:
        self._access_token = None
        self._access_valid_until = 0.0
        self._delete_refresh()
