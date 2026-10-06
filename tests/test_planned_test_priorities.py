from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.api.database import Base
from services.api.models import (
    AuditEvent,
    Pipe,
    PlannedTestList,
    PlannedTestPipe,
    PressureTest,
    TestRevision,
    User,
)
from services.api.routes.planned_tests import (
    PlannedListCreateRequest,
    PlannedListUpdateRequest,
    list_planned_lists,
    update_planned_list,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _planned_pipe(plan_id: str, pipe_number: str) -> PlannedTestPipe:
    bundle_number, suffix = pipe_number.split("/", 1)
    return PlannedTestPipe(
        planned_test_list_id=plan_id,
        pipe_number=pipe_number,
        bundle_number=bundle_number,
        pipe_sort_key=suffix,
        source_data={},
    )


def test_priority_requests_accept_only_none_through_p3():
    assert PlannedListCreateRequest(name="Normal").priority == 0
    assert PlannedListCreateRequest(name="Urgent", priority=3).priority == 3
    assert PlannedListUpdateRequest(priority=2).priority == 2

    with pytest.raises(ValidationError):
        PlannedListCreateRequest(name="Invalid", priority=4)
    with pytest.raises(ValidationError):
        PlannedListUpdateRequest(priority=-1)


def test_incomplete_priorities_are_pinned_but_completed_priority_is_not(db_session):
    plans = [
        PlannedTestList(id="urgent", name="300", priority=3, updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        PlannedTestList(id="elevated", name="200", priority=2, updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc)),
        PlannedTestList(id="priority-one", name="100", priority=1, updated_at=datetime(2026, 1, 3, tzinfo=timezone.utc)),
        PlannedTestList(id="normal", name="400", priority=0, updated_at=datetime(2026, 1, 4, tzinfo=timezone.utc)),
        PlannedTestList(id="completed-urgent", name="500", priority=3, updated_at=datetime(2026, 1, 5, tzinfo=timezone.utc)),
    ]
    db_session.add_all(plans)
    db_session.add_all([
        _planned_pipe("urgent", "300/1"),
        _planned_pipe("elevated", "200/1"),
        _planned_pipe("priority-one", "100/1"),
        _planned_pipe("normal", "400/1"),
        _planned_pipe("completed-urgent", "500/1"),
    ])
    pressure_test = PressureTest(id="test-500", log_no="LOG-500", is_archived=False)
    revision = TestRevision(
        id="revision-500",
        pressure_test_id=pressure_test.id,
        revision_id="r1",
        status="complete",
        is_primary=True,
        metadata_json={},
        metrics_json={},
    )
    db_session.add_all([
        pressure_test,
        revision,
        Pipe(test_revision_id=revision.id, pipe_number="500/1"),
    ])
    db_session.commit()

    result = list_planned_lists(q="", db=db_session)

    assert [item["id"] for item in result] == [
        "urgent",
        "elevated",
        "priority-one",
        "completed-urgent",
        "normal",
    ]
    assert result[0]["priority"] == 3
    assert result[3]["completed_count"] == result[3]["pipe_count"] == 1


def test_priority_change_is_persisted_and_audited(db_session):
    user = User(
        id="priority-user",
        username="priority_foreman",
        full_name="Priority Foreman",
        role="foreman",
        hashed_password="hash",
        is_active=True,
    )
    plan = PlannedTestList(id="priority-plan", name="Urgent order", priority=0)
    db_session.add_all([user, plan])
    db_session.commit()

    response = update_planned_list(
        list_id=plan.id,
        payload=PlannedListUpdateRequest(priority=3),
        current_user=user,
        db=db_session,
    )

    db_session.refresh(plan)
    event = db_session.query(AuditEvent).filter(
        AuditEvent.entity_id == plan.id,
        AuditEvent.action == "planned_list_updated",
    ).one()
    assert response["priority"] == 3
    assert plan.priority == 3
    assert event.actor_name == "Priority Foreman"
    assert event.details_json["priority"] == 3


def test_priority_ui_exposes_icons_sorting_and_all_translations():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    component = (root / "apps/web/src/components/PlannedTestsTab.tsx").read_text(encoding="utf-8")
    sorting = (root / "apps/web/src/plannedTestPlanSorting.ts").read_text(encoding="utf-8")
    translations = (root / "apps/web/src/i18n.ts").read_text(encoding="utf-8")

    for icon in ("ArrowUp", "ChevronsUp", "Flame"):
        assert icon in component
    for mode in ("created_desc", "created_asc", "name_asc", "name_desc", "pipes_desc", "pipes_asc"):
        assert mode in component
        assert mode in sorting
    for key in (
        "planned_priority",
        "planned_priority_none",
        "planned_priority_level",
        "planned_priority_hint",
        "planned_list_sort",
        "planned_added_by",
    ):
        assert translations.count(f"{key}:") == 3
