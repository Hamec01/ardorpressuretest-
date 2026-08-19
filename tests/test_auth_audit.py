import shutil
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from services.api.config import settings
from services.api.database import Base, SessionLocal, engine
from services.api.main import app
from services.api.auth import hash_password, seed_default_users, verify_password


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_default_users(db)
    if settings.storage_dir.exists():
        shutil.rmtree(settings.storage_dir, ignore_errors=True)
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    yield
    Base.metadata.drop_all(bind=engine)
    if settings.storage_dir.exists():
        shutil.rmtree(settings.storage_dir, ignore_errors=True)


def test_password_hashing_and_verification():
    h = hash_password("secret_pass_123")
    assert verify_password("secret_pass_123", h) is True
    assert verify_password("wrong_password", h) is False


def test_login_flow():
    client = TestClient(app)

    # 1. Failed login with wrong password
    bad_res = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "wrong_password"
    })
    assert bad_res.status_code == 401

    # 2. Successful login with default admin
    ok_res = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert ok_res.status_code == 200
    data = ok_res.json()
    assert "access_token" in data
    assert data["user"]["username"] == "admin"
    assert data["user"]["role"] == "admin"

    token = data["access_token"]

    # 3. Access /api/v1/auth/me
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "admin"


def test_audit_logs_and_rbac():
    client = TestClient(app)

    # 1. Login as operator
    op_res = client.post("/api/v1/auth/login", json={
        "username": "operator_pekka",
        "password": "operator123"
    })
    assert op_res.status_code == 200
    op_token = op_res.json()["access_token"]

    # Operator cannot view audit logs (requires foreman/admin)
    audit_forbidden = client.get("/api/v1/audit", headers={"Authorization": f"Bearer {op_token}"})
    assert audit_forbidden.status_code == 403

    # 2. Login as foreman
    foreman_res = client.post("/api/v1/auth/login", json={
        "username": "foreman_matti",
        "password": "foreman123"
    })
    assert foreman_res.status_code == 200
    foreman_token = foreman_res.json()["access_token"]

    # Foreman can view audit logs
    audit_ok = client.get("/api/v1/audit", headers={"Authorization": f"Bearer {foreman_token}"})
    assert audit_ok.status_code == 200
    events = audit_ok.json()
    assert len(events) >= 1  # Login events recorded
    assert any(e["action"] == "login" for e in events)
