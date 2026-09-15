import pytest

from importguard.parsing import parse_csv
from importguard.validation import validate_rows

MAPPING = {"full_name": "Name", "email": "Email"}


def test_mapping_normalization_and_original_preservation():
    table = parse_csv(b"Name,Email\n Jane , JANE@example.com \n")
    row = validate_rows(table, MAPPING)[0]
    assert row.valid
    assert row.cleaned == {
        "full_name": "Jane",
        "email": "jane@example.com",
        "company": None,
        "phone": None,
    }
    assert row.original["Email"] == " JANE@example.com "


def test_missing_name_and_invalid_email_report_both_errors():
    row = validate_rows(parse_csv(b"Name,Email\n ,not-an-email\n"), MAPPING)[0]
    assert not row.valid
    assert any("full_name: required" in error for error in row.errors)
    assert any(error.startswith("email:") for error in row.errors)


def test_duplicate_email_ignores_case():
    table = parse_csv(b"Name,Email\nJane,JANE@example.com\nAnother,jane@example.com\n")
    rows = validate_rows(table, MAPPING)
    assert rows[0].valid
    assert not rows[1].valid
    assert "line 2" in rows[1].errors[0]


def test_invalid_row_does_not_block_later_valid_row():
    table = parse_csv(b"Name,Email\n,jane@example.com\nJane,jane@example.com\n")
    rows = validate_rows(table, MAPPING)
    assert not rows[0].valid
    assert rows[1].valid


def test_existing_database_email_is_rejected():
    table = parse_csv(b"Name,Email\nJane,jane@example.com\n")
    row = validate_rows(table, MAPPING, {"jane@example.com"})[0]
    assert not row.valid
    assert "already exists" in row.errors[0]


@pytest.mark.parametrize(
    "mapping",
    [
        {"email": "Email"},
        {"email": "Missing", "full_name": "Name"},
        {"email": "Email", "full_name": "Email"},
        {"email": "Email", "full_name": "Name", "age": "Name"},
    ],
)
def test_invalid_mapping_is_rejected(mapping):
    table = parse_csv(b"Name,Email\nJane,jane@example.com\n")
    with pytest.raises(ValueError):
        validate_rows(table, mapping)


def test_overlong_name_is_rejected():
    content = f"Name,Email\n{'x' * 201},jane@example.com\n".encode()
    row = validate_rows(parse_csv(content), MAPPING)[0]
    assert not row.valid
    assert any("200 characters" in error for error in row.errors)


def test_optional_fields_are_mapped():
    table = parse_csv(
        b"Name,Email,Organization,Telephone\n"
        b"Jane,jane@example.com,Example Inc,+1 555 0100\n"
    )
    mapping = {**MAPPING, "company": "Organization", "phone": "Telephone"}
    row = validate_rows(table, mapping)[0]
    assert row.valid
    assert row.cleaned["company"] == "Example Inc"
    assert row.cleaned["phone"] == "+1 555 0100"


def test_internal_control_character_is_rejected():
    table = parse_csv(b'Name,Email\n"Ja\tne",jane@example.com\n')
    row = validate_rows(table, MAPPING)[0]
    assert not row.valid
    assert any("control characters" in error for error in row.errors)
