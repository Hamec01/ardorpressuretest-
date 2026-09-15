"""R1 regression guard: require_role() must never fall back to a default user.

Isolated by design, same pattern as test_trash_read_only.py: a private in-memory
SQLite session is used directly, never the process-wide engine. DATABASE_URL /
STORAGE_DIR must still be exported to isolated temporary values by the caller,
because services.api.config.Settings() is constructed at first import time.
"""
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

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.database import Base
from services.api.models import User
from services.api.auth import create_access_token, hash_password, require_role


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def seeded_foreman_matti(db_session):
    """A user literally named foreman_matti exists - proving the fallback truly is gone,
    not merely absent because the account happens to be missing in this test DB."""
    u = User(
        username="foreman_matti",
        hashed_password=hash_password("foreman123"),
        full_name="Matti Meikalainen (Foreman)",
        role="foreman",
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    return u


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_no_authorization_header_is_rejected(db_session, seeded_foreman_matti):
    checker = require_role(["admin", "foreman"])
    with pytest.raises(HTTPException) as exc_info:
        checker(auth=None, db=db_session)
    assert exc_info.value.status_code == 401


@pytest.mark.parametrize("placeholder", ["", "null", "undefined", "None"])
def test_placeholder_credentials_are_rejected(db_session, seeded_foreman_matti, placeholder):
    checker = require_role(["admin", "foreman"])
    with pytest.raises(HTTPException) as exc_info:
        checker(auth=_creds(placeholder), db=db_session)
    assert exc_info.value.status_code == 401


def test_malformed_token_is_rejected(db_session, seeded_foreman_matti):
    checker = require_role(["admin", "foreman"])
    with pytest.raises(HTTPException) as exc_info:
        checker(auth=_creds("not-a-jwt-at-all"), db=db_session)
    assert exc_info.value.status_code == 401


def test_valid_signature_for_unknown_user_is_rejected(db_session, seeded_foreman_matti):
    # A syntactically/cryptographically valid token, but "sub" matches no row in this DB.
    token = create_access_token({"sub": "00000000-0000-0000-0000-000000000000"})
    checker = require_role(["admin", "foreman"])
    with pytest.raises(HTTPException) as exc_info:
        checker(auth=_creds(token), db=db_session)
    assert exc_info.value.status_code == 401


def test_valid_token_for_inactive_user_is_rejected(db_session):
    inactive = User(
        username="deactivated_admin",
        hashed_password=hash_password("whatever"),
        full_name="Deactivated Admin",
        role="admin",
        is_active=False,
    )
    db_session.add(inactive)
    db_session.commit()

    token = create_access_token({"sub": inactive.id})
    checker = require_role(["admin"])
    with pytest.raises(HTTPException) as exc_info:
        checker(auth=_creds(token), db=db_session)
    assert exc_info.value.status_code == 401


def test_none_of_the_rejections_ever_return_foreman_matti(db_session, seeded_foreman_matti):
    """The historical bug: every failure path used to silently return foreman_matti.
    pytest.raises itself fails the test if any of these cases returns instead of raising."""
    checker = require_role(["admin"])
    for auth in (None, _creds(""), _creds("garbage"), _creds(create_access_token({"sub": "nope"}))):
        with pytest.raises(HTTPException):
            checker(auth=auth, db=db_session)


def test_insufficient_role_is_403_not_401(db_session, seeded_foreman_matti):
    token = create_access_token({"sub": seeded_foreman_matti.id})
    checker = require_role(["admin"])  # foreman_matti has role "foreman"
    with pytest.raises(HTTPException) as exc_info:
        checker(auth=_creds(token), db=db_session)
    assert exc_info.value.status_code == 403


def test_valid_token_correct_role_succeeds(db_session, seeded_foreman_matti):
    token = create_access_token({"sub": seeded_foreman_matti.id})
    checker = require_role(["foreman", "admin"])
    result = checker(auth=_creds(token), db=db_session)
    assert result.username == "foreman_matti"
