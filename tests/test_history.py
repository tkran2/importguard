import csv
import io

import pytest

from importguard.history import rejection_csv, spreadsheet_cell


@pytest.mark.parametrize(
    "value",
    ["=1+1", "+123", "-123", "@SUM(A1)", "  =1+1", "\ttext"],
)
def test_formula_like_cells_are_prefixed(value):
    assert spreadsheet_cell(value) == "'" + value


def test_ordinary_cell_is_preserved():
    assert spreadsheet_cell("Doe, Jane") == "Doe, Jane"


def test_export_contains_only_rejected_rows_and_preserves_quoting():
    report = {
        "rows": [
            {
                "row_number": 2,
                "original": {"Name": "Accepted"},
                "errors": [],
                "imported": True,
            },
            {
                "row_number": 3,
                "original": {"Name": "Doe, Jane"},
                "errors": ["email: required."],
                "imported": False,
            },
        ]
    }
    rows = list(csv.DictReader(io.StringIO(rejection_csv(report))))
    assert len(rows) == 1
    assert rows[0]["source_row"] == "3"
    assert rows[0]["source:Name"] == "Doe, Jane"
    assert rows[0]["errors"] == "email: required."
