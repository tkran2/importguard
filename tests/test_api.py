import json

import pytest
from fastapi.testclient import TestClient

from importguard.api import app

client = TestClient(app)
MAPPING = json.dumps({"full_name": "Name", "email": "Email"})


def upload(content, mapping=MAPPING, filename="customers.csv"):
    return client.post(
        "/imports/preview",
        files={"file": (filename, content, "text/csv")},
        data={"mapping": mapping},
    )


def test_preview_reports_valid_invalid_and_duplicate_rows():
    response = upload(
        b"Name,Email\n"
        b"Jane,jane@example.com\n"
        b"Missing,invalid\n"
        b"Duplicate,JANE@example.com\n"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_rows"] == 3
    assert body["valid_rows"] == 1
    assert body["rejected_rows"] == 2
    assert body["database_checked"] is True
    assert body["rows"][2]["row_number"] == 4
    assert "line 2" in body["rows"][2]["errors"][0]


@pytest.mark.parametrize("mapping", ["not json", "[]", '{"email":12}'])
def test_bad_mapping_returns_client_error(mapping):
    response = upload(b"Name,Email\nJane,jane@example.com\n", mapping=mapping)
    assert response.status_code == 422


def test_missing_source_column_returns_client_error():
    response = upload(b"Other,Email\nJane,jane@example.com\n")
    assert response.status_code == 422
    assert "does not exist" in response.json()["detail"]


def test_malformed_csv_returns_client_error():
    response = upload(b"Name,Email\nJane\n")
    assert response.status_code == 422
    assert "expected 2" in response.json()["detail"]


def test_unsupported_extension():
    response = upload(b"something", filename="customers.xlsx")
    assert response.status_code == 415


def test_oversized_file(monkeypatch):
    monkeypatch.setattr("importguard.api.MAX_BYTES", 10)
    response = upload(b"Name,Email\nJane,jane@example.com\n")
    assert response.status_code == 413


@pytest.fixture(autouse=True)
def isolated_email_lookup():
    from importguard.lookups import get_email_lookup

    app.dependency_overrides[get_email_lookup] = lambda: lambda emails: set()
    yield
    app.dependency_overrides.pop(get_email_lookup, None)


def test_existing_customer_is_rejected_in_preview():
    from importguard.lookups import get_email_lookup

    def lookup(emails):
        assert emails == {"jane@example.com"}
        return {"jane@example.com"}

    app.dependency_overrides[get_email_lookup] = lambda: lookup
    response = upload(b"Name,Email\nJane,JANE@example.com\n")
    assert response.status_code == 200
    body = response.json()
    assert body["valid_rows"] == 0
    assert body["rejected_rows"] == 1
    assert "already exists" in body["rows"][0]["errors"][0]


def test_database_failure_returns_service_unavailable():
    from sqlalchemy.exc import SQLAlchemyError

    from importguard.lookups import get_email_lookup

    def unavailable(emails):
        raise SQLAlchemyError("Simulated database failure")

    app.dependency_overrides[get_email_lookup] = lambda: unavailable
    response = upload(b"Name,Email\nJane,jane@example.com\n")
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Database unavailable. Please retry the preview."
    )
