import pytest

from importguard.parsing import FileValidationError, parse_csv


def test_bom_quotes_and_original_values():
    table = parse_csv(
        "\ufeff Name ,Email,Company\r\n"
        '"Doe, Jane",JANE@example.com,"Example, Inc."\r\n'.encode()
    )
    assert table.headers == ["Name", "Email", "Company"]
    assert table.rows[0].row_number == 2
    assert table.rows[0].values == {
        "Name": "Doe, Jane",
        "Email": "JANE@example.com",
        "Company": "Example, Inc.",
    }


def test_blank_lines_preserve_source_line_numbers():
    table = parse_csv(b"name,email\n\nJane,jane@example.com\n")
    assert len(table.rows) == 1
    assert table.rows[0].row_number == 3


def test_multiline_quoted_cells_preserve_next_row_number():
    table = parse_csv(b'name,note\nJane,"first line\nsecond line"\nTom,hello\n')
    assert table.rows[0].values["note"] == "first line\nsecond line"
    assert table.rows[1].row_number == 4


@pytest.mark.parametrize(
    "content,message",
    [
        (b"", "empty"),
        (b"\xff", "UTF-8"),
        (b"name,\x00email\nJane,x\n", "null"),
        (b"name,Name\nJane,Tom\n", "unique"),
        (b"name,\nJane,x\n", "column must have a name"),
        (b"name,email\n", "no data rows"),
        (b"name,email\nJane\n", "expected 2"),
        (b'name,email\n"Jane,x\n', "Malformed CSV"),
    ],
)
def test_invalid_files_have_clear_errors(content, message):
    with pytest.raises(FileValidationError, match=message):
        parse_csv(content)


def test_row_limit(monkeypatch):
    monkeypatch.setattr("importguard.parsing.MAX_ROWS", 2)
    with pytest.raises(FileValidationError, match="at most"):
        parse_csv(b"name\nJane\nTom\nAlex\n")


def test_byte_limit(monkeypatch):
    monkeypatch.setattr("importguard.parsing.MAX_BYTES", 5)
    with pytest.raises(FileValidationError, match="5 MB"):
        parse_csv(b"name\nJane\n")


def test_column_limit(monkeypatch):
    monkeypatch.setattr("importguard.parsing.MAX_COLUMNS", 1)
    with pytest.raises(FileValidationError, match="columns"):
        parse_csv(b"name,email\nJane,jane@example.com\n")
