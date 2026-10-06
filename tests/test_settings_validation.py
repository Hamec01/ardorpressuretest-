"""R1 regression guard: Settings must fail closed for non-local ARDOR_ENV with unsafe values.

Pure object-construction tests - Settings is a plain pydantic BaseModel, so each case
constructs it directly with explicit kwargs rather than mutating process environment
variables (module-level defaults are only evaluated once, at first import).
"""
import pytest

from services.api.config import DEFAULT_CORS_ORIGINS, INSECURE_DEFAULT_SECRET, Settings

GOOD_SECRET = "a-real-randomly-generated-secret-value"
GOOD_DB_URL = "postgresql://ardor_user:x@postgres:5432/ardor_pressure_test"
GOOD_PUBLIC_ORIGIN = "https://84-247-130-242.sslip.io"
GOOD_SHARE_SECRET = "a-real-randomly-generated-share-secret-value-0123456789"


def _server_settings(**overrides):
    kwargs = dict(
        environment="staging",
        secret_key=GOOD_SECRET,
        database_url=GOOD_DB_URL,
        seed_default_users=False,
        cors_allowed_origins="https://example.ardor.internal",
        public_origin=GOOD_PUBLIC_ORIGIN,
        share_secret=GOOD_SHARE_SECRET,
    )
    kwargs.update(overrides)
    return Settings(**kwargs)


def test_server_mode_accepts_fully_safe_configuration():
    s = _server_settings()
    assert s.secret_key == GOOD_SECRET
    assert s.is_local_environment is False
    assert s.session_cookie_name == "__Host-ardor_session"
    assert s.csrf_cookie_name == "__Host-ardor_csrf"
    assert s.secure_cookies is True


@pytest.mark.parametrize("origin", [
    "",
    "http://84.247.130.242:8080",
    "https://user:pass@example.test",
    "https://example.test/path",
    "https://example.test/",
    "https://example.test?query=1",
    "https://example.test/#fragment",
    " https://example.test",
    "https://example.test ",
    "https://example.test:0",
    "https://example.test:invalid",
])
def test_server_mode_rejects_invalid_public_origin(origin):
    with pytest.raises(Exception):
        _server_settings(public_origin=origin)


@pytest.mark.parametrize("env_name", ["staging", "production", "Staging", "PRODUCTION"])
def test_server_mode_rejects_default_secret(env_name):
    with pytest.raises(Exception):
        _server_settings(environment=env_name, secret_key=INSECURE_DEFAULT_SECRET)


def test_server_mode_rejects_sqlite_database_url():
    with pytest.raises(Exception):
        _server_settings(database_url="sqlite:///./ardor_local.db")


def test_server_mode_rejects_auto_seed_enabled():
    with pytest.raises(Exception):
        _server_settings(seed_default_users=True)


def test_server_mode_rejects_empty_cors_origins():
    with pytest.raises(Exception):
        _server_settings(cors_allowed_origins="")


def test_server_mode_rejects_wildcard_cors_origin():
    with pytest.raises(Exception):
        _server_settings(cors_allowed_origins="*")


@pytest.mark.parametrize("origins", [
    "*,https://example.ardor.internal",
    "https://example.ardor.internal,*",
    "https://a.test,*,https://b.test",
])
def test_server_mode_rejects_wildcard_in_any_list_position(origins):
    with pytest.raises(Exception):
        _server_settings(cors_allowed_origins=origins)


def test_server_mode_rejects_unset_cors_origins_still_at_default():
    # ARDOR_CORS_ORIGINS was never explicitly set for this deployment - it must not
    # silently pass validation just because the list happens to be non-empty.
    with pytest.raises(Exception):
        _server_settings(cors_allowed_origins=DEFAULT_CORS_ORIGINS)


def test_missing_ardor_env_is_treated_as_server_mode_not_local():
    # Simulates ARDOR_ENV genuinely never being set: environment="" (the class's
    # fail-closed default) combined with otherwise-insecure local-style values must
    # still be rejected, not silently tolerated as if it were local.
    with pytest.raises(Exception):
        Settings(
            environment="",
            secret_key=INSECURE_DEFAULT_SECRET,
            database_url="sqlite:///./ardor_local.db",
            seed_default_users=False,
            cors_allowed_origins=DEFAULT_CORS_ORIGINS,
        )


def test_empty_ardor_env_is_not_local():
    # Supply otherwise-safe values so only the environment classification is under test.
    s = _server_settings(environment="")
    assert s.is_local_environment is False


@pytest.mark.parametrize("env_name", ["local", "dev", "development", "test", "testing", "LOCAL"])
def test_local_environments_allow_insecure_defaults(env_name):
    # Same "unsafe" values that are rejected in server mode must be tolerated locally.
    s = Settings(
        environment=env_name,
        secret_key=INSECURE_DEFAULT_SECRET,
        database_url="sqlite:///./ardor_local.db",
        seed_default_users=True,
        cors_allowed_origins=DEFAULT_CORS_ORIGINS,
    )
    assert s.is_local_environment is True
    assert s.session_cookie_name == "ardor_session"
    assert s.csrf_cookie_name == "ardor_csrf"
    assert s.secure_cookies is False


def test_cors_origin_list_parses_comma_separated_values():
    s = Settings(environment="local", cors_allowed_origins=" http://a.test , http://b.test ")
    assert s.cors_origin_list == ["http://a.test", "http://b.test"]


@pytest.mark.parametrize("share_secret", ["", "short", "ardor-local-share-secret-change-in-prod"])
def test_server_mode_rejects_missing_or_weak_share_secret(share_secret):
    with pytest.raises(Exception):
        _server_settings(share_secret=share_secret)
