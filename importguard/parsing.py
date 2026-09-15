"""Parse customer CSV uploads before validation or database writes."""

import csv
import io
from dataclasses import dataclass

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 10_000
MAX_COLUMNS = 50


class FileValidationError(ValueError):
    """An upload cannot safely be interpreted as a table."""


@dataclass(frozen=True)
class SourceRow:
    row_number: int
    values: dict[str, str]


@dataclass(frozen=True)
class ParsedTable:
    headers: list[str]
    rows: list[SourceRow]


def parse_csv(content: bytes) -> ParsedTable:
    if not content:
        raise FileValidationError("The uploaded file is empty.")
    if len(content) > MAX_BYTES:
        raise FileValidationError("Upload a file smaller than or equal to 5 MB.")

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise FileValidationError("Save the CSV using UTF-8 encoding.") from exc

    if "\x00" in text:
        raise FileValidationError("The file contains invalid null characters.")

    reader = csv.reader(io.StringIO(text, newline=""), strict=True)

    try:
        raw_headers = next(reader, None)
        if not raw_headers:
            raise FileValidationError("The CSV must start with a header row.")

        headers = [header.strip() for header in raw_headers]
        if len(headers) > MAX_COLUMNS:
            raise FileValidationError("A file may contain at most 50 columns.")
        if any(not header for header in headers):
            raise FileValidationError("Every column must have a name.")
        if len({header.casefold() for header in headers}) != len(headers):
            raise FileValidationError("Column names must be unique.")

        rows = []
        while True:
            row_number = reader.line_num + 1
            values = next(reader, None)
            if values is None:
                break
            if not values or all(not value.strip() for value in values):
                continue
            if len(values) != len(headers):
                raise FileValidationError(
                    f"Row starting on line {row_number} has {len(values)} "
                    f"columns; expected {len(headers)}."
                )
            if len(rows) >= MAX_ROWS:
                raise FileValidationError("A file may contain at most 10,000 rows.")
            rows.append(
                SourceRow(
                    row_number=row_number,
                    values=dict(zip(headers, values, strict=True)),
                )
            )
    except csv.Error as exc:
        raise FileValidationError(
            f"Malformed CSV near line {reader.line_num}: {exc}"
        ) from exc

    if not rows:
        raise FileValidationError("The CSV contains no data rows.")

    return ParsedTable(headers=headers, rows=rows)
