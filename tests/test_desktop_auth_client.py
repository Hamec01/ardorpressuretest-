"""Desktop keyring credential lifecycle and authenticated sync-client tests."""

import json

import httpx
import pytest

from wika_report.auth_client import (
    CredentialStorageError,
    DesktopAuthClient,
    DesktopAuthenticationError,
)
from wika_report.config import DEFAULT_SYNC_SERVER_URL, normalize_sync_server_url
from wika_report.sync_client import SyncClient
from wika_report.sync_queue import QueueItem


class FakeKeyring:
    def __init__(self):
        self.values = {}

    def get_password(self, service, account):
        return self.values.get((service, account))

    def set_password(self, service, account, value):
        self.values[(service, account)] = value

    def delete_password(self, service, account):
        self.values.pop((service, account), None)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://ardor.example", "https://ardor.example"),
        ("https://ardor.example/", "https://ardor.example"),
        ("http://127.0.0.1:8080", "http://127.0.0.1:8080"),
        ("http://localhost:8080/", "http://localhost:8080"),
        ("http://[::1]:8080", "http://[::1]:8080"),
    ],
)
def test_sync_server_url_accepts_https_and_explicit_loopback_http(value, expected):
    assert normalize_sync_server_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        " https://ardor.example",
        "http://ardor.example",
        "ftp://ardor.example",
        "https://user:password@ardor.example",
        "https://ardor.example/api",
        "https://ardor.example?query=1",
        "https://ardor.example#fragment",
        "https://ardor.example:bad",
    ],
)
def test_sync_server_url_rejects_unsafe_or_non_origin_values(value):
    with pytest.raises(ValueError, match="sync_server_url"):
        normalize_sync_server_url(value)


def test_default_sync_server_is_the_verified_https_origin():
    assert DEFAULT_SYNC_SERVER_URL == "https://84-247-130-242.sslip.io"


def test_auth_client_rejects_remote_plain_http_before_any_request():
    with pytest.raises(ValueError, match="HTTPS"):
        DesktopAuthClient("http://84.247.130.242:8080", keyring_backend=FakeKeyring())


class FailingKeyring(FakeKeyring):
    def set_password(self, service, account, value):
        raise RuntimeError(f"must not leak {value}")


def _pair(access="access.jwt.value", refresh="R" * 43):
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": 900,
        "user": {
            "id": "user-1",
            "username": "desktop-user",
            "full_name": "Desktop User",
            "role": "viewer",
            "email": None,
            "must_change_password": False,
        },
    }


def test_login_keeps_access_only_in_memory_and_refresh_only_in_keyring():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=_pair())

    store = FakeKeyring()
    client = DesktopAuthClient(
        "https://ardor.example",
        keyring_backend=store,
        transport=httpx.MockTransport(handler),
    )
    assert client.login("desktop-user", "secret password", "Field laptop") == "access.jwt.value"
    assert len(seen) == 1
    assert seen[0].url.path == "/api/v1/desktop/login"
    assert list(store.values.values()) == ["R" * 43]
    assert "access.jwt.value" not in store.values.values()
    assert client.get_access_token() == "access.jwt.value"
    assert len(seen) == 1  # cached access token performs no refresh request


def test_refresh_rotates_saved_keyring_secret_and_access_token(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path.endswith("/login"):
            return httpx.Response(200, json=_pair())
        assert json.loads(request.content)["refresh_token"] == "R" * 43
        return httpx.Response(200, json=_pair("new.access.jwt", "N" * 43))

    store = FakeKeyring()
    client = DesktopAuthClient(
        "https://ardor.example",
        keyring_backend=store,
        transport=httpx.MockTransport(handler),
    )
    client.login("desktop-user", "secret password")
    monkeypatch.setattr("wika_report.auth_client.time.monotonic", lambda: 10_000.0)
    client._access_valid_until = 10_001.0
    assert client.get_access_token() == "new.access.jwt"
    assert list(store.values.values()) == ["N" * 43]
    assert len(calls) == 2


def test_rejected_refresh_clears_keyring_and_requires_login():
    store = FakeKeyring()
    client = DesktopAuthClient(
        "https://ardor.example",
        keyring_backend=store,
        transport=httpx.MockTransport(lambda request: httpx.Response(401, json={})),
    )
    store.set_password(client._service_name, client.REFRESH_ACCOUNT, "R" * 43)
    with pytest.raises(DesktopAuthenticationError, match="Desktop login required"):
        client.refresh()
    assert store.values == {}


def test_keyring_write_failure_revokes_new_remote_session_without_leaking_secret():
    paths = []

    def handler(request):
        paths.append(request.url.path)
        return httpx.Response(200, json=_pair())

    client = DesktopAuthClient(
        "https://ardor.example",
        keyring_backend=FailingKeyring(),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(CredentialStorageError) as exc_info:
        client.login("desktop-user", "secret password")
    assert "R" * 43 not in str(exc_info.value)
    assert paths == ["/api/v1/desktop/login", "/api/v1/auth/logout"]


def test_hostile_server_token_shapes_never_reach_keyring():
    bad_payloads = [
        {},
        _pair(access=""),
        _pair(refresh="header.payload.signature"),
        {**_pair(), "expires_in": True},
    ]
    for payload in bad_payloads:
        store = FakeKeyring()
        client = DesktopAuthClient(
            "https://ardor.example",
            keyring_backend=store,
            transport=httpx.MockTransport(lambda request, value=payload: httpx.Response(200, json=value)),
        )
        with pytest.raises(DesktopAuthenticationError):
            client.login("desktop-user", "secret password")
        assert store.values == {}


class StaticAuthClient:
    def get_access_token(self):
        return "desktop.access.jwt"


class RecordingQueue:
    def __init__(self):
        self.updates = []

    def update_status(self, operation_id, **kwargs):
        self.updates.append((operation_id, kwargs))


def test_sync_client_adds_desktop_bearer_to_pipecloud_request():
    seen_authorization = []

    def handler(request):
        seen_authorization.append(request.headers.get("authorization"))
        return httpx.Response(200, json={"pipecloud_added": True})

    item = QueueItem(
        id=1,
        operation_id="op-1",
        operation_type="pipecloud_status_update",
        log_no="001",
        revision_id=None,
        manifest_path=None,
        payload_json=json.dumps({"added": True}),
        status="pending",
        attempts=0,
        last_error=None,
        receipt_id=None,
        created_at="now",
        synced_at=None,
    )
    queue = RecordingQueue()
    client = SyncClient(
        base_url="https://ardor.example",
        auth_client=StaticAuthClient(),
        transport=httpx.MockTransport(handler),
    )
    assert client.sync_item(item, queue=queue)["pipecloud_added"] is True
    assert seen_authorization == ["Bearer desktop.access.jwt"]


def test_sync_client_transitional_no_auth_mode_sends_no_authorization_header():
    seen_authorization = []

    def handler(request):
        seen_authorization.append(request.headers.get("authorization"))
        return httpx.Response(200, json={"pipecloud_added": False})

    item = QueueItem(
        id=1,
        operation_id="op-2",
        operation_type="pipecloud_status_update",
        log_no="002",
        revision_id=None,
        manifest_path=None,
        payload_json=json.dumps({"added": False}),
        status="pending",
        attempts=0,
        last_error=None,
        receipt_id=None,
        created_at="now",
        synced_at=None,
    )
    SyncClient(
        base_url="https://ardor.example",
        transport=httpx.MockTransport(handler),
    ).sync_item(item, queue=RecordingQueue())
    assert seen_authorization == [None]
