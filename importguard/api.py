"""HTTP endpoints for customer import previews."""

import json
from dataclasses import asdict
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from sqlalchemy.exc import SQLAlchemyError

from importguard.history import router as history_router
from importguard.lookups import EmailLookup, get_email_lookup
from importguard.parsing import MAX_BYTES, parse_csv
from importguard.validation import validate_rows

app = FastAPI(
    title="ImportGuard",
    description="Preview customer data and identify rejected rows before importing.",
    version="0.1.0",
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/imports/preview")
def preview(
    email_lookup: Annotated[EmailLookup, Depends(get_email_lookup)],
    file: Annotated[UploadFile, File()],
    mapping: Annotated[
        str,
        Form(description='JSON mapping, e.g. {"full_name":"Name","email":"Email"}'),
    ],
):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(415, "Upload a .csv file. Excel support is coming next.")

    try:
        columns = json.loads(mapping)
    except json.JSONDecodeError as exc:
        raise HTTPException(422, "Column mapping must be valid JSON.") from exc

    if not isinstance(columns, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in columns.items()
    ):
        raise HTTPException(422, "Column mapping must be an object of string pairs.")

    content = file.file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(413, "Maximum CSV file size is 5 MB.")

    try:
        table = parse_csv(content)
        rows = validate_rows(table, columns)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    candidates = {row.cleaned["email"] for row in rows if row.valid}
    try:
        existing = email_lookup(candidates)
    except SQLAlchemyError as exc:
        raise HTTPException(
            503, "Database unavailable. Please retry the preview."
        ) from exc

    rows = validate_rows(table, columns, existing_emails=existing)
    valid_count = sum(row.valid for row in rows)
    return {
        "filename": file.filename,
        "headers": table.headers,
        "total_rows": len(rows),
        "valid_rows": valid_count,
        "rejected_rows": len(rows) - valid_count,
        "database_checked": True,
        "rows": [{**asdict(row), "valid": row.valid} for row in rows],
    }


@app.post("/imports/commit")
def commit(
    file: Annotated[UploadFile, File()],
    mapping: Annotated[str, Form()],
):
    from importguard.importing import commit_import

    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(415, "Upload a .csv file.")

    try:
        columns = json.loads(mapping)
    except json.JSONDecodeError as exc:
        raise HTTPException(422, "Column mapping must be valid JSON.") from exc

    if not isinstance(columns, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in columns.items()
    ):
        raise HTTPException(422, "Column mapping must be an object of string pairs.")

    content = file.file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(413, "Maximum CSV file size is 5 MB.")

    try:
        return commit_import(content, file.filename, columns)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            503,
            "Import could not be confirmed. Retry the same file and mapping.",
        ) from exc


app.include_router(history_router)


@app.post("/files/inspect")
def inspect_file(file: Annotated[UploadFile, File()]):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(415, "Upload a .csv file.")
    content = file.file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(413, "Maximum CSV file size is 5 MB.")
    try:
        table = parse_csv(content)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"headers": table.headers, "total_rows": len(table.rows)}


@app.get("/demo.csv")
def demo_file():
    from fastapi.responses import Response

    from importguard.demo import DEMO_CSV

    return Response(
        content=DEMO_CSV,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="demo.csv"'},
    )
