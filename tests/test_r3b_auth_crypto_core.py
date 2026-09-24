"""Regression guard for R3b-2: password/secret/token primitives (Argon2id hashing,
legacy-PBKDF2-compatible verification with transparent upgrade, new-password
validation, opaque-secret helpers, desktop access JWT create/verify).

None of this is wired into login/logout/me/users, FastAPI dependency injection, cookies,
CSRF, Origin checks, rate limiting, sessions, frontend, or desktop code yet - these
tests only prove the primitives themselves. The existing create_access_token()/
decode_access_token()/get_current_user()/require_role() pair is untouched; the existing
regression files that exercise it (test_require_role_fail_closed.py,
test_bootstrap_andrei_sakki_admin_reset.py, etc.) are the "legacy JWT still passes"
proof and are re-run as part of the full suite, not duplicated here.

Isolated by design, same pattern as every other regression test in this repo: no
database is needed for most of these (pure functions), and the one fixture that does
use a session follows the same private in-memory SQLite pattern as the rest.
"""
import hashlib
import os

_db_url = os.environ.get("DATABASE_URL", "")
_storage_dir = os.environ.get("STORAGE_DIR", "")

if not _db_url or "5432" in _db_url or "postgres" in _db_url.lower() or "ardor_pressure_test" in _db_url:
    raise RuntimeError(
        "DATABASE_URL is missing or looks like the staging Postgres target. "
        "Export an isolated temporary DATABASE_URL before running this test."
    )
if not _storage_dir or os.path.normpath(_storage_dir) == "/data/storage":
    raise RuntimeError(
        "STORAGE_DIR is missing or points at the staging storage volume (/data/storage). "
        "Export an isolated temporary STORAGE_DIR before running this test."
    )

import time

import pytest

from services.api.auth import (
    DESKTOP_ACCESS_TOKEN_LIFETIME_SECONDS,
    DESKTOP_ACCESS_TOKEN_TYPE,
    DUMMY_ARGON2_HASH,
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    DesktopAccessTokenError,
    check_password_with_upgrade,
    compare_secret_hashes,
    create_access_token,
    create_desktop_access_token,
    decode_access_token,
    generate_opaque_secret,
    hash_opaque_secret,
    hash_password,
    validate_new_password,
    verify_desktop_access_token,
    verify_password,
)
import services.api.auth as auth_module


def _legacy_pbkdf2_hash(password: str, salt: str = "fixedsaltforthistestonly0000000") -> str:
    """Builds a hash in the exact pre-R3b-2 legacy format (salt$hex), independent of
    hash_password() (which now only ever produces Argon2id output) - a fixed,
    reproducible "known legacy hash" for verify-only regression coverage."""
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()
    return f"{salt}${hashed}"


# --- verify_password(): known legacy PBKDF2, wrong password, corrupted formats -----

def test_known_legacy_pbkdf2_hash_verifies_correctly():
    stored = _legacy_pbkdf2_hash("correct horse battery staple")
    assert verify_password("correct horse battery staple", stored) is True


def test_legacy_pbkdf2_wrong_password_rejected():
    stored = _legacy_pbkdf2_hash("correct horse battery staple")
    assert verify_password("wrong password", stored) is False


@pytest.mark.parametrize("corrupted", [
    "",
    "not-a-hash-at-all",
    "$argon2id$garbage-not-a-real-argon2-hash",
    "$argon2id$v=19$m=12288,t=3,p=1$onlytwo$parts$toomany",
    "onlyonepart-no-dollar-separator",
    "salt$" + "z" * 10,  # not valid hex for the pbkdf2 branch
])
def test_corrupted_or_unknown_formats_return_false_not_raise(corrupted):
    assert verify_password("anything", corrupted) is False


def test_argon2id_hash_verifies_correctly():
    h = hash_password("a fresh argon2 password")
    assert verify_password("a fresh argon2 password", h) is True


def test_argon2id_hash_wrong_password_rejected():
    h = hash_password("a fresh argon2 password")
    assert verify_password("not the right password", h) is False


# --- hash_password(): Argon2id, fresh salt every call --------------------------------

def test_hash_password_produces_argon2id_prefix():
    h = hash_password("some password")
    assert h.startswith("$argon2id$")


def test_hash_password_uses_exact_configured_parameters():
    h = hash_password("some password")
    assert "m=12288" in h
    assert "t=3" in h
    assert "p=1" in h


def test_same_password_hashed_twice_produces_different_hashes():
    h1 = hash_password("identical password")
    h2 = hash_password("identical password")
    assert h1 != h2
    assert verify_password("identical password", h1) is True
    assert verify_password("identical password", h2) is True


# --- check_password_with_upgrade(): pure, upgrades legacy, leaves Argon2id alone -----

def test_check_password_with_upgrade_successful_legacy_offers_argon2id_upgrade():
    stored = _legacy_pbkdf2_hash("legacy user password")
    result = check_password_with_upgrade("legacy user password", stored)
    assert result.ok is True
    assert result.upgraded_hash is not None
    assert result.upgraded_hash.startswith("$argon2id$")
    assert verify_password("legacy user password", result.upgraded_hash) is True


def test_check_password_with_upgrade_failed_legacy_offers_no_upgrade():
    stored = _legacy_pbkdf2_hash("legacy user password")
    result = check_password_with_upgrade("wrong password", stored)
    assert result.ok is False
    assert result.upgraded_hash is None


def test_check_password_with_upgrade_current_argon2id_needs_no_upgrade():
    stored = hash_password("already current")
    result = check_password_with_upgrade("already current", stored)
    assert result.ok is True
    assert result.upgraded_hash is None


def test_check_password_with_upgrade_wrong_argon2id_password_fails_cleanly():
    stored = hash_password("already current")
    result = check_password_with_upgrade("wrong one", stored)
    assert result.ok is False
    assert result.upgraded_hash is None


def test_check_password_with_upgrade_does_not_touch_a_database():
    """Static proof this really is a pure function - no db/session parameter exists to
    touch in the first place, and its own source contains no Session/commit/query call."""
    import inspect
    source = inspect.getsource(check_password_with_upgrade)
    assert "db" not in inspect.signature(check_password_with_upgrade).parameters
    for forbidden in ("db.commit", "db.add", "db.query", ".query("):
        assert forbidden not in source


# --- Unicode / whitespace preservation, no trim, no normalization -------------------

def test_unicode_password_with_leading_and_trailing_spaces_is_preserved_exactly():
    pw = "  pässwörd with spaces  "
    h = hash_password(pw)
    assert verify_password(pw, h) is True
    assert verify_password(pw.strip(), h) is False


def test_unicode_only_password_verifies():
    pw = "пароль-пароль-日本語-🔒"
    h = hash_password(pw)
    assert verify_password(pw, h) is True


def test_validate_new_password_does_not_alter_or_reject_intentional_whitespace():
    pw = "  a b c d  "  # 11 codepoints, well within bounds, spaces throughout
    assert validate_new_password(pw) is None


# --- validate_new_password(): exact 5/6/128/129 codepoint boundaries ----------------

def test_password_length_5_codepoints_is_rejected():
    assert validate_new_password("a" * 5) is not None


def test_password_length_6_codepoints_is_accepted():
    assert validate_new_password("a" * 6) is None


def test_password_length_128_codepoints_is_accepted():
    assert validate_new_password("a" * 128) is None


def test_password_length_129_codepoints_is_rejected():
    assert validate_new_password("a" * 129) is not None


def test_password_boundaries_hold_for_multibyte_unicode_too():
    """len() counts codepoints, not bytes - a 6-codepoint multibyte string must pass
    exactly like a 6-codepoint ASCII string."""
    assert validate_new_password("日" * 5) is not None
    assert validate_new_password("日" * 6) is None
    assert validate_new_password("日" * 128) is None
    assert validate_new_password("日" * 129) is not None


def test_validate_new_password_message_never_contains_the_password_itself():
    secret_marker = "unlikely-marker-xyz123"
    msg = validate_new_password(secret_marker)
    assert msg is None  # within bounds, but if it weren't:
    too_short_msg = validate_new_password("x")
    assert secret_marker not in (too_short_msg or "")
    assert "x" != too_short_msg  # sanity: message is a sentence, not an echo


def test_validate_new_password_constants_match_spec():
    assert PASSWORD_MIN_LENGTH == 6
    assert PASSWORD_MAX_LENGTH == 128


# --- DUMMY_ARGON2_HASH: fixed, valid, not used by any login path yet ----------------

def test_dummy_argon2_hash_is_a_valid_argon2id_hash_with_the_configured_parameters():
    assert DUMMY_ARGON2_HASH.startswith("$argon2id$")
    assert "m=12288" in DUMMY_ARGON2_HASH
    assert "t=3" in DUMMY_ARGON2_HASH
    assert "p=1" in DUMMY_ARGON2_HASH


def test_dummy_argon2_hash_verifies_only_against_its_own_known_fixed_plaintext():
    assert verify_password(
        "r3b2-fixed-non-secret-dummy-string-for-timing-safety-only", DUMMY_ARGON2_HASH
    ) is True
    assert verify_password("some other guess", DUMMY_ARGON2_HASH) is False


def test_dummy_argon2_hash_not_referenced_by_any_route_yet():
    """Static proof it is genuinely unused so far - no routes module imports it."""
    import subprocess
    result = subprocess.run(
        ["grep", "-rl", "DUMMY_ARGON2_HASH", "services/api/routes/"],
        capture_output=True, text=True,
    )
    assert result.stdout.strip() == "", f"DUMMY_ARGON2_HASH is referenced in: {result.stdout}"


# --- opaque secret helpers: entropy, shape, hash-only storage, constant-time compare -

def test_generate_opaque_secret_is_reasonably_long_and_urlsafe():
    values = {generate_opaque_secret() for _ in range(50)}
    assert len(values) == 50  # all distinct - no collisions, no fixed/predictable output
    for v in values:
        assert "." not in v
        assert "=" not in v  # no padding
        assert len(v) >= 32  # base64url(32 raw bytes) is 43 chars; generous lower bound
        assert all(c.isalnum() or c in "-_" for c in v)


def test_generate_opaque_secret_uses_token_urlsafe_32_as_its_source():
    """Static proof of the required entropy source, not just an indirect byte-count
    inference - greps the actual implementation."""
    import inspect
    source = inspect.getsource(generate_opaque_secret)
    assert "secrets.token_urlsafe(32)" in source


def test_hash_opaque_secret_is_sha256_hex_and_differs_from_the_secret():
    secret = generate_opaque_secret()
    hashed = hash_opaque_secret(secret)
    assert len(hashed) == 64
    assert all(c in "0123456789abcdef" for c in hashed)
    assert hashed != secret
    assert secret not in hashed


def test_hash_opaque_secret_is_deterministic_for_lookup_purposes():
    secret = generate_opaque_secret()
    assert hash_opaque_secret(secret) == hash_opaque_secret(secret)


def test_different_secrets_hash_differently():
    a, b = generate_opaque_secret(), generate_opaque_secret()
    assert hash_opaque_secret(a) != hash_opaque_secret(b)


def test_compare_secret_hashes_matches_and_mismatches_correctly():
    h1 = hash_opaque_secret("value-one")
    h2 = hash_opaque_secret("value-one")
    h3 = hash_opaque_secret("value-two")
    assert compare_secret_hashes(h1, h2) is True
    assert compare_secret_hashes(h1, h3) is False


def test_compare_secret_hashes_is_constant_time_primitive():
    """Static proof it delegates to hmac.compare_digest rather than `==` (checking the
    function's code line, not its docstring, which legitimately mentions `==` in prose)."""
    import inspect
    source = inspect.getsource(compare_secret_hashes)
    assert "hmac.compare_digest" in source
    code_line = [ln for ln in source.splitlines() if "return" in ln][0]
    assert "==" not in code_line


# --- desktop access token: create + strict verify, happy path and each rejection ----

def _b64_encode_json(obj) -> str:
    import base64
    import json
    s = json.dumps(obj, separators=(",", ":"), sort_keys=True)
    return base64.urlsafe_b64encode(s.encode("utf-8")).decode("utf-8").rstrip("=")


def _build_signed_token(header_obj, payload_obj) -> str:
    """Test-only helper: builds a syntactically-valid, CORRECTLY SIGNED JWT out of
    arbitrary header/payload JSON values (which may deliberately not be well-formed
    desktop-access shapes, or not even objects), using the same secret key production
    code uses - so each test can isolate exactly which verify_desktop_access_token()
    check rejects a given malformed shape, rather than always failing at signature
    verification first."""
    import hmac as _hmac
    import hashlib as _hashlib
    import base64 as _base64
    from services.api.config import settings as _settings

    header_b64 = _b64_encode_json(header_obj)
    payload_b64 = _b64_encode_json(payload_obj)
    message = f"{header_b64}.{payload_b64}"
    sig = _hmac.new(_settings.secret_key.encode("utf-8"), message.encode("utf-8"), _hashlib.sha256).digest()
    sig_b64 = _base64.urlsafe_b64encode(sig).decode("utf-8").rstrip("=")
    return f"{message}.{sig_b64}"


def _valid_header():
    return {"alg": "HS256", "typ": "JWT"}


def _valid_payload(**overrides):
    now = int(time.time())
    payload = {
        "typ": DESKTOP_ACCESS_TOKEN_TYPE,
        "sub": "user-123",
        "sid": "session-abc",
        "iat": now,
        "exp": now + DESKTOP_ACCESS_TOKEN_LIFETIME_SECONDS,
    }
    payload.update(overrides)
    return payload


def _assert_invalid_claim(header=None, payload=None):
    token = _build_signed_token(header or _valid_header(), payload)
    result = verify_desktop_access_token(token)
    assert result.ok is False
    assert result.error is DesktopAccessTokenError.INVALID_CLAIM
    return result


def _assert_invalid_header(header):
    token = _build_signed_token(header, _valid_payload())
    result = verify_desktop_access_token(token)
    assert result.ok is False
    assert result.error is DesktopAccessTokenError.INVALID_HEADER
    return result


def test_desktop_access_token_happy_path():
    token = create_desktop_access_token(user_id="user-123", session_id="session-abc")
    result = verify_desktop_access_token(token)
    assert result.ok is True
    assert result.user_id == "user-123"
    assert result.session_id == "session-abc"
    assert result.error is None


def test_desktop_access_token_via_build_helper_happy_path():
    """Proves _build_signed_token()/_valid_header()/_valid_payload() themselves produce
    a token verify_desktop_access_token() accepts - every negative test below trusts
    that a single deviation from this baseline is what triggers its expected error."""
    token = _build_signed_token(_valid_header(), _valid_payload())
    result = verify_desktop_access_token(token)
    assert result.ok is True
    assert result.error is None


def test_desktop_access_token_has_exactly_15_minute_lifetime_constant():
    assert DESKTOP_ACCESS_TOKEN_LIFETIME_SECONDS == 15 * 60


def test_desktop_access_token_contains_all_required_claims():
    import base64
    import json
    token = create_desktop_access_token(user_id="user-123", session_id="session-abc")
    payload_b64 = token.split(".")[1]
    rem = len(payload_b64) % 4
    padded = payload_b64 + ("=" * (4 - rem) if rem else "")
    payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    assert payload["typ"] == DESKTOP_ACCESS_TOKEN_TYPE
    assert payload["sub"] == "user-123"
    assert payload["sid"] == "session-abc"
    assert "iat" in payload
    assert "exp" in payload
    assert payload["exp"] - payload["iat"] == DESKTOP_ACCESS_TOKEN_LIFETIME_SECONDS


def test_desktop_access_token_uses_one_time_snapshot_when_clock_crosses_second(monkeypatch):
    """A second boundary during creation must not shorten a fresh token to 899s."""
    first_second = 1_700_000_000
    observed_times = iter((float(first_second), float(first_second + 1)))
    monkeypatch.setattr(auth_module.time, "time", lambda: next(observed_times))

    token = create_desktop_access_token(user_id="user-123", session_id="session-abc")

    import base64
    import json
    payload_b64 = token.split(".")[1]
    padded = payload_b64 + ("=" * ((4 - len(payload_b64) % 4) % 4))
    payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    assert payload["iat"] == first_second
    assert payload["exp"] - payload["iat"] == DESKTOP_ACCESS_TOKEN_LIFETIME_SECONDS

    # The verifier consumes the second supplied clock value. The token remains valid
    # and proves creation itself sampled the clock only once.
    result = verify_desktop_access_token(token)
    assert result.ok is True


def test_desktop_access_token_does_not_carry_a_role_claim():
    token = create_desktop_access_token(user_id="user-123", session_id="session-abc")
    import base64
    import json
    payload_b64 = token.split(".")[1]
    rem = len(payload_b64) % 4
    padded = payload_b64 + ("=" * (4 - rem) if rem else "")
    payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    assert "role" not in payload


# --- create_desktop_access_token(): rejects invalid user_id/session_id -------------

def test_create_desktop_access_token_rejects_empty_user_id():
    with pytest.raises(ValueError):
        create_desktop_access_token(user_id="", session_id="session-abc")


def test_create_desktop_access_token_rejects_non_string_user_id():
    for bad in (None, 123, ["user-123"], {"id": "user-123"}, True):
        with pytest.raises(ValueError):
            create_desktop_access_token(user_id=bad, session_id="session-abc")


def test_create_desktop_access_token_rejects_empty_session_id():
    with pytest.raises(ValueError):
        create_desktop_access_token(user_id="user-123", session_id="")


def test_create_desktop_access_token_rejects_non_string_session_id():
    for bad in (None, 456, ["session-abc"], {"id": "session-abc"}, False):
        with pytest.raises(ValueError):
            create_desktop_access_token(user_id="user-123", session_id=bad)


# --- header: missing/wrong alg, wrong typ, non-object shapes -----------------------

def test_desktop_access_token_header_missing_alg_rejected():
    _assert_invalid_header({"typ": "JWT"})


def test_desktop_access_token_header_wrong_alg_rejected():
    for wrong_alg in ("HS384", "RS256", "none", "", None):
        _assert_invalid_header({"alg": wrong_alg, "typ": "JWT"})


def test_desktop_access_token_header_missing_typ_rejected():
    _assert_invalid_header({"alg": "HS256"})


def test_desktop_access_token_header_wrong_typ_rejected():
    for wrong_typ in ("JWS", "jwt", "", None):
        _assert_invalid_header({"alg": "HS256", "typ": wrong_typ})


def test_desktop_access_token_header_as_array_rejected():
    _assert_invalid_header(["HS256", "JWT"])


def test_desktop_access_token_header_as_string_rejected():
    _assert_invalid_header("not-a-header-object")


def test_desktop_access_token_header_as_null_rejected():
    _assert_invalid_header(None)


# --- payload: non-object shapes -----------------------------------------------------

def test_desktop_access_token_payload_as_array_rejected():
    token = _build_signed_token(_valid_header(), ["not", "an", "object"])
    result = verify_desktop_access_token(token)
    assert result.ok is False
    assert result.error is DesktopAccessTokenError.INVALID_CLAIM


def test_desktop_access_token_payload_as_string_rejected():
    token = _build_signed_token(_valid_header(), "not-a-payload-object")
    result = verify_desktop_access_token(token)
    assert result.ok is False
    assert result.error is DesktopAccessTokenError.INVALID_CLAIM


def test_desktop_access_token_payload_as_null_rejected():
    token = _build_signed_token(_valid_header(), None)
    result = verify_desktop_access_token(token)
    assert result.ok is False
    assert result.error is DesktopAccessTokenError.INVALID_CLAIM


# --- typ / missing claims (now unified under INVALID_CLAIM, except wrong `typ`) ----

def test_desktop_access_token_wrong_type_rejected():
    # A generic legacy-shaped token (no typ claim at all) must not verify as desktop -
    # its header is still well-formed (alg=HS256, typ=JWT), so this specifically
    # isolates the payload-level typ check, not the header check.
    token = create_access_token({"sub": "user-123", "sid": "session-abc"}, expires_delta_seconds=900)
    result = verify_desktop_access_token(token)
    assert result.ok is False
    assert result.error is DesktopAccessTokenError.WRONG_TYPE


def test_desktop_access_token_missing_sub_rejected():
    payload = _valid_payload()
    del payload["sub"]
    _assert_invalid_claim(payload=payload)


def test_desktop_access_token_missing_sid_rejected():
    payload = _valid_payload()
    del payload["sid"]
    _assert_invalid_claim(payload=payload)


# --- sub/sid: must be non-empty strings ---------------------------------------------

def test_desktop_access_token_numeric_sub_rejected():
    _assert_invalid_claim(payload=_valid_payload(sub=123))


def test_desktop_access_token_boolean_sub_rejected():
    _assert_invalid_claim(payload=_valid_payload(sub=True))


def test_desktop_access_token_empty_sub_rejected():
    _assert_invalid_claim(payload=_valid_payload(sub=""))


def test_desktop_access_token_numeric_sid_rejected():
    _assert_invalid_claim(payload=_valid_payload(sid=456))


def test_desktop_access_token_boolean_sid_rejected():
    _assert_invalid_claim(payload=_valid_payload(sid=False))


def test_desktop_access_token_empty_sid_rejected():
    _assert_invalid_claim(payload=_valid_payload(sid=""))


# --- iat/exp: must be genuine int, not bool/float/string ----------------------------

def test_desktop_access_token_string_iat_rejected():
    now = int(time.time())
    _assert_invalid_claim(payload=_valid_payload(iat=str(now), exp=now + DESKTOP_ACCESS_TOKEN_LIFETIME_SECONDS))


def test_desktop_access_token_float_iat_rejected():
    now = int(time.time())
    _assert_invalid_claim(payload=_valid_payload(iat=float(now), exp=now + DESKTOP_ACCESS_TOKEN_LIFETIME_SECONDS))


def test_desktop_access_token_boolean_iat_rejected():
    _assert_invalid_claim(payload=_valid_payload(iat=True, exp=1 + DESKTOP_ACCESS_TOKEN_LIFETIME_SECONDS))


def test_desktop_access_token_string_exp_rejected():
    now = int(time.time())
    _assert_invalid_claim(payload=_valid_payload(iat=now, exp=str(now + DESKTOP_ACCESS_TOKEN_LIFETIME_SECONDS)))


def test_desktop_access_token_float_exp_rejected():
    now = int(time.time())
    _assert_invalid_claim(payload=_valid_payload(iat=now, exp=float(now + DESKTOP_ACCESS_TOKEN_LIFETIME_SECONDS)))


def test_desktop_access_token_boolean_exp_rejected():
    _assert_invalid_claim(payload=_valid_payload(iat=0, exp=True))


# --- exp - iat must be exactly 900 ---------------------------------------------------

def test_desktop_access_token_lifetime_899_seconds_rejected():
    now = int(time.time())
    _assert_invalid_claim(payload=_valid_payload(iat=now, exp=now + 899))


def test_desktop_access_token_lifetime_901_seconds_rejected():
    now = int(time.time())
    _assert_invalid_claim(payload=_valid_payload(iat=now, exp=now + 901))


def test_desktop_access_token_lifetime_exactly_900_seconds_accepted():
    now = int(time.time())
    token = _build_signed_token(_valid_header(), _valid_payload(iat=now, exp=now + 900))
    result = verify_desktop_access_token(token)
    assert result.ok is True


# --- iat clock skew: max 30 seconds in the future -----------------------------------

def test_desktop_access_token_iat_15_seconds_in_future_within_skew_accepted(monkeypatch):
    now = 1_700_000_000
    monkeypatch.setattr(auth_module.time, "time", lambda: float(now))
    future_iat = now + 15
    token = _build_signed_token(_valid_header(), _valid_payload(
        iat=future_iat, exp=future_iat + DESKTOP_ACCESS_TOKEN_LIFETIME_SECONDS,
    ))
    result = verify_desktop_access_token(token)
    assert result.ok is True


def test_desktop_access_token_iat_30_seconds_in_future_at_skew_boundary_accepted(monkeypatch):
    now = 1_700_000_000
    monkeypatch.setattr(auth_module.time, "time", lambda: float(now))
    future_iat = now + 30
    token = _build_signed_token(_valid_header(), _valid_payload(
        iat=future_iat, exp=future_iat + DESKTOP_ACCESS_TOKEN_LIFETIME_SECONDS,
    ))
    result = verify_desktop_access_token(token)
    assert result.ok is True


def test_desktop_access_token_iat_31_seconds_in_future_beyond_skew_rejected(monkeypatch):
    now = 1_700_000_000
    monkeypatch.setattr(auth_module.time, "time", lambda: float(now))
    future_iat = now + 31
    _assert_invalid_claim(payload=_valid_payload(
        iat=future_iat, exp=future_iat + DESKTOP_ACCESS_TOKEN_LIFETIME_SECONDS,
    ))


def test_desktop_access_token_iat_far_in_future_rejected(monkeypatch):
    now = 1_700_000_000
    monkeypatch.setattr(auth_module.time, "time", lambda: float(now))
    future_iat = now + 3600
    _assert_invalid_claim(payload=_valid_payload(
        iat=future_iat, exp=future_iat + DESKTOP_ACCESS_TOKEN_LIFETIME_SECONDS,
    ))


# --- signature / structure -----------------------------------------------------------

def test_desktop_access_token_invalid_signature_rejected():
    token = create_desktop_access_token(user_id="user-123", session_id="session-abc")
    header_b64, payload_b64, sig_b64 = token.split(".")
    tampered = f"{header_b64}.{payload_b64}.{sig_b64[:-4]}AAAA"
    result = verify_desktop_access_token(tampered)
    assert result.ok is False
    assert result.error is DesktopAccessTokenError.INVALID_SIGNATURE


def test_desktop_access_token_malformed_structure_rejected():
    for bogus in ("", "not-a-jwt", "only.two", "a.b.c.d"):
        result = verify_desktop_access_token(bogus)
        assert result.ok is False
        assert result.error is DesktopAccessTokenError.MISSING_OR_INVALID_STRUCTURE


def test_desktop_access_token_longer_than_max_length_rejected():
    token = create_desktop_access_token(user_id="user-123", session_id="session-abc")
    oversized = token + "A" * 4100
    assert len(oversized) > 4096
    result = verify_desktop_access_token(oversized)
    assert result.ok is False
    assert result.error is DesktopAccessTokenError.MISSING_OR_INVALID_STRUCTURE


def test_desktop_access_token_at_exact_max_length_boundary_still_verifies():
    """Proves the length guard's boundary is strictly '> 4096', not '>= 4096': builds a
    fully valid, correctly-structured, correctly-signed token of EXACTLY 4096 characters
    (by padding the sub claim to the precise length needed) and confirms it verifies
    successfully end-to-end - not just that some particular error code is absent."""
    token = None
    padding_len = 0
    while padding_len < 5000:
        candidate = _build_signed_token(_valid_header(), _valid_payload(sub="user-" + ("x" * padding_len)))
        if len(candidate) == 4096:
            token = candidate
            break
        if len(candidate) > 4096:
            break
        padding_len += 1
    assert token is not None, "could not construct an exactly-4096-character valid token"
    result = verify_desktop_access_token(token)
    assert result.ok is True


def test_desktop_access_token_one_character_over_max_length_rejected():
    """The same construction as above, but one character longer - proves the exact
    off-by-one boundary, not just 'obviously oversized' like the 4100-char test above."""
    token = None
    padding_len = 0
    while padding_len < 5000:
        candidate = _build_signed_token(_valid_header(), _valid_payload(sub="user-" + ("x" * padding_len)))
        if len(candidate) == 4097:
            token = candidate
            break
        if len(candidate) > 4097:
            break
        padding_len += 1
    assert token is not None, "could not construct an exactly-4097-character token"
    result = verify_desktop_access_token(token)
    assert result.ok is False
    assert result.error is DesktopAccessTokenError.MISSING_OR_INVALID_STRUCTURE


# --- expiry: now >= exp means expired, exact boundary included ---------------------

def test_desktop_access_token_expired_rejected(monkeypatch):
    token = create_desktop_access_token(user_id="user-123", session_id="session-abc")
    real_time = time.time  # captured before patching, to avoid the patched fn calling itself
    monkeypatch.setattr(auth_module.time, "time", lambda: real_time() + DESKTOP_ACCESS_TOKEN_LIFETIME_SECONDS + 60)
    result = verify_desktop_access_token(token)
    assert result.ok is False
    assert result.error is DesktopAccessTokenError.EXPIRED


def test_desktop_access_token_now_exactly_equal_to_exp_is_expired(monkeypatch):
    now = int(time.time())
    token = _build_signed_token(_valid_header(), _valid_payload(
        iat=now, exp=now + DESKTOP_ACCESS_TOKEN_LIFETIME_SECONDS,
    ))
    frozen_now = float(now + DESKTOP_ACCESS_TOKEN_LIFETIME_SECONDS)  # now == exp exactly
    monkeypatch.setattr(auth_module.time, "time", lambda: frozen_now)
    result = verify_desktop_access_token(token)
    assert result.ok is False
    assert result.error is DesktopAccessTokenError.EXPIRED


def test_desktop_access_token_one_second_before_exp_is_not_expired(monkeypatch):
    now = int(time.time())
    token = _build_signed_token(_valid_header(), _valid_payload(
        iat=now, exp=now + DESKTOP_ACCESS_TOKEN_LIFETIME_SECONDS,
    ))
    frozen_now = float(now + DESKTOP_ACCESS_TOKEN_LIFETIME_SECONDS - 1)
    monkeypatch.setattr(auth_module.time, "time", lambda: frozen_now)
    result = verify_desktop_access_token(token)
    assert result.ok is True


# --- never raises, for any Python value - including non-str types, tested for real -

def test_verify_desktop_access_token_never_raises_on_malformed_strings():
    hostile_strings = [
        "", "not-a-jwt", "a" * 10000, "....", "..", ".",
        "\x00\x01\x02", "control-char-prefix-then-malformed",
    ]
    for value in hostile_strings:
        try:
            result = verify_desktop_access_token(value)
            assert result.ok is False
        except Exception as e:
            pytest.fail(f"verify_desktop_access_token raised on hostile input {value!r}: {e!r}")


def test_verify_desktop_access_token_never_raises_on_non_string_types():
    """None, bytes, int, list, and dict are each actually passed to the verifier here -
    not skipped - and must each come back as a safe ok=False result, never an
    exception."""
    hostile_non_strings = [
        None,
        b"bytes-not-str",
        123,
        ["a", "list", "not", "a", "token"],
        {"typ": "desktop_access", "sub": "x", "sid": "y", "iat": 0, "exp": 900},
    ]
    for value in hostile_non_strings:
        try:
            result = verify_desktop_access_token(value)
        except Exception as e:
            pytest.fail(f"verify_desktop_access_token raised on non-string input {value!r}: {e!r}")
        assert result.ok is False
        assert result.error is DesktopAccessTokenError.MISSING_OR_INVALID_STRUCTURE


# --- existing legacy create_access_token()/decode_access_token() contract untouched -

def test_legacy_create_and_decode_access_token_roundtrip_unchanged():
    token = create_access_token({"sub": "legacy-user-id"})
    payload = decode_access_token(token)
    assert payload["sub"] == "legacy-user-id"
    assert "exp" in payload and "iat" in payload
    assert "typ" not in payload  # legacy tokens never gained a typ claim
