"""PostgreSQL integration tests; all test records are rolled back."""

import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from importguard.importing import import_in_transaction
from importguard.models import Customer, ImportJob

pytestmark = pytest.mark.skipif(
    os.getenv("IMPORTGUARD_TEST_DATABASE") != "1",
    reason="Set IMPORTGUARD_TEST_DATABASE=1 to run PostgreSQL tests.",
)

MAPPING = {"full_name": "Name", "email": "Email"}


@pytest.fixture
def database_session():
    from importguard.database import SessionLocal

    with SessionLocal() as session:
        session.begin()
        try:
            yield session
        finally:
            session.rollback()


def sample():
    email = f"{uuid4().hex}@example.com"
    content = f"Name,Email\nJane,{email}\nInvalid,not-email\n".encode()
    return email, content


def test_retry_returns_original_report(database_session):
    email, content = sample()
    first = import_in_transaction(database_session, content, "first.csv", MAPPING)
    second = import_in_transaction(database_session, content, "renamed.csv", MAPPING)

    assert first["imported_rows"] == 1
    assert first["rejected_rows"] == 1
    assert first["replayed"] is False
    assert second["replayed"] is True
    assert second["job_id"] == first["job_id"]
    assert second["rows"] == first["rows"]
    count = database_session.scalar(
        select(func.count()).select_from(Customer).where(Customer.email == email)
    )
    assert count == 1


def test_different_file_cannot_overwrite_customer(database_session):
    email, content = sample()
    first = import_in_transaction(database_session, content, "first.csv", MAPPING)
    changed = f"Name,Email\nChanged Name,{email}\n".encode()
    second = import_in_transaction(database_session, changed, "different.csv", MAPPING)

    assert second["job_id"] != first["job_id"]
    assert second["replayed"] is False
    assert second["imported_rows"] == 0
    assert second["rejected_rows"] == 1
    customer = database_session.scalar(select(Customer).where(Customer.email == email))
    assert customer.full_name == "Jane"


def test_failure_rolls_back_customers_and_report():
    from importguard.database import SessionLocal

    email, content = sample()
    job_id = None

    with (
        pytest.raises(RuntimeError, match="Simulated failure"),
        SessionLocal.begin() as session,
    ):
        result = import_in_transaction(session, content, "rollback.csv", MAPPING)
        job_id = UUID(result["job_id"])
        assert session.get(ImportJob, job_id).result is not None
        assert (
            session.scalar(select(Customer).where(Customer.email == email)) is not None
        )
        raise RuntimeError("Simulated failure")

    assert job_id is not None
    with SessionLocal() as session:
        assert session.get(ImportJob, job_id) is None
        assert session.scalar(select(Customer).where(Customer.email == email)) is None
