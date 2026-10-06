"""Shared fixtures.

Since docs/ACCESS_PLAN_R4-R7.md stage 3 every business route requires a signed-in
employee. Tests that exercise business behaviour (not access control) use
`signed_in_admin`, which stands in an active admin for the reader/writer checks.
Access control itself is covered by tests/test_route_access_matrix.py and the auth tests.
"""
import pytest


@pytest.fixture
def signed_in_admin():
    from fastapi import Depends
    from sqlalchemy.orm import Session

    from services.api.database import get_db
    from services.api.main import app
    from services.api.models import User
    from services.api.permissions import require_reader, require_writer

    def test_admin(db: Session = Depends(get_db)) -> User:
        user = db.query(User).filter(User.username == "test-admin").first()
        if user is None:
            user = User(username="test-admin", full_name="Test Admin", hashed_password="!", role="admin", is_active=True)
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    overrides = {require_reader: test_admin, require_writer: test_admin}
    app.dependency_overrides.update(overrides)
    yield
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)
