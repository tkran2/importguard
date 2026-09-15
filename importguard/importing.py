"""Transactional customer imports with replayable results."""

import hashlib
import json
from dataclasses import asdict

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from importguard.models import Customer, ImportJob
from importguard.parsing import parse_csv
from importguard.validation import validate_rows

IMPORT_LOCK = 73419201
VALIDATION_VERSION = "customers-v1"


def import_fingerprint(content: bytes, mapping: dict[str, str]) -> str:
    payload = {
        "file_sha256": hashlib.sha256(content).hexdigest(),
        "mapping": mapping,
        "validation_version": VALIDATION_VERSION,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def import_in_transaction(
    session: Session,
    content: bytes,
    filename: str,
    mapping: dict[str, str],
) -> dict:
    """Caller owns the transaction and must commit or roll it back."""
    if not filename or len(filename) > 255:
        raise ValueError("Filename must contain between 1 and 255 characters.")

    table = parse_csv(content)
    rows = validate_rows(table, mapping)
    fingerprint = import_fingerprint(content, mapping)

    # Serialize prototype imports across processes, not just Python threads.
    session.execute(text("SET LOCAL lock_timeout = '10s'"))
    session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": IMPORT_LOCK},
    )

    previous = session.scalar(
        select(ImportJob).where(ImportJob.fingerprint == fingerprint)
    )
    if previous is not None:
        if previous.status != "completed" or previous.result is None:
            raise ValueError("This import has no completed result to replay.")
        return {**previous.result, "replayed": True}

    job = ImportJob(
        filename=filename,
        fingerprint=fingerprint,
        column_mapping=mapping,
        status="previewed",
        total_rows=len(rows),
        imported_rows=0,
        rejected_rows=0,
    )
    session.add(job)
    session.flush()

    inserted_emails = set()
    candidates = sorted(
        (row for row in rows if row.valid),
        key=lambda row: row.cleaned["email"],
    )

    for start in range(0, len(candidates), 500):
        batch = candidates[start : start + 500]
        statement = (
            insert(Customer)
            .values([{**row.cleaned, "import_job_id": job.id} for row in batch])
            .on_conflict_do_nothing(constraint="uq_customers_email")
            .returning(Customer.email)
        )
        inserted_emails.update(session.scalars(statement))

    report_rows = []
    for row in rows:
        errors = list(row.errors)
        imported = row.valid and row.cleaned["email"] in inserted_emails
        if row.valid and not imported:
            errors.append("email: already exists in the customer database.")
        report_rows.append(
            {
                **asdict(row),
                "errors": errors,
                "imported": imported,
            }
        )

    result = {
        "job_id": str(job.id),
        "filename": filename,
        "status": "completed",
        "total_rows": len(rows),
        "imported_rows": len(inserted_emails),
        "rejected_rows": len(rows) - len(inserted_emails),
        "rows": report_rows,
    }
    job.status = "completed"
    job.imported_rows = result["imported_rows"]
    job.rejected_rows = result["rejected_rows"]
    job.result = result
    session.flush()
    return {**result, "replayed": False}


def commit_import(
    content: bytes,
    filename: str,
    mapping: dict[str, str],
) -> dict:
    from importguard.database import SessionLocal

    with SessionLocal.begin() as session:
        result = import_in_transaction(session, content, filename, mapping)
    return result
