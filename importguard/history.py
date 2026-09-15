"""Browse completed imports and download rejected source rows."""

import csv
import io
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from importguard.models import ImportJob

router = APIRouter(prefix="/imports", tags=["Import history"])


def spreadsheet_cell(value: object) -> str:
    """Prefix formula-like text for spreadsheet-oriented CSV exports."""
    text = "" if value is None else str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(
        ("\t", "\r", "\n")
    ):
        return "'" + text
    return text


def rejection_csv(report: dict) -> str:
    rows = report["rows"]
    headers = list(dict.fromkeys(header for row in rows for header in row["original"]))
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        ["source_row", "errors"] + [f"source:{header}" for header in headers]
    )
    for row in rows:
        if not row["imported"]:
            writer.writerow(
                [
                    row["row_number"],
                    spreadsheet_cell("; ".join(row["errors"])),
                    *[
                        spreadsheet_cell(row["original"].get(header, ""))
                        for header in headers
                    ],
                ]
            )
    return output.getvalue()


def load_report(job_id: UUID) -> dict:
    from importguard.database import SessionLocal

    try:
        with SessionLocal() as session:
            job = session.get(ImportJob, job_id)
            if job is None:
                raise HTTPException(404, "Import not found.")
            if job.result is None:
                raise HTTPException(409, "This import has no saved report.")
            return job.result
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Import history is temporarily unavailable.") from exc


@router.get("")
def list_imports(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    from importguard.database import SessionLocal

    try:
        with SessionLocal() as session:
            # Select summary columns only, avoiding large JSON reports.
            statement = (
                select(
                    ImportJob.id,
                    ImportJob.filename,
                    ImportJob.status,
                    ImportJob.total_rows,
                    ImportJob.imported_rows,
                    ImportJob.rejected_rows,
                    ImportJob.created_at,
                )
                .order_by(ImportJob.created_at.desc(), ImportJob.id.desc())
                .offset(offset)
                .limit(limit)
            )
            items = [
                {**dict(row), "id": str(row["id"])}
                for row in session.execute(statement).mappings()
            ]
            return {"items": items, "limit": limit, "offset": offset}
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Import history is temporarily unavailable.") from exc


@router.get("/{job_id}")
def get_import(job_id: UUID):
    return load_report(job_id)


@router.get("/{job_id}/rejections.csv")
def download_rejections(job_id: UUID):
    report = load_report(job_id)
    return Response(
        content=rejection_csv(report).encode("utf-8-sig"),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="import-{job_id}-rejections.csv"'
            )
        },
    )
