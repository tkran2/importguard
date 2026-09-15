"""Look up uploaded email addresses without loading every customer."""

from collections.abc import Callable

from sqlalchemy import select

EmailLookup = Callable[[set[str]], set[str]]


def lookup_existing_emails(emails: set[str]) -> set[str]:
    from importguard.database import SessionLocal
    from importguard.models import Customer

    if not emails:
        return set()

    matches = set()
    candidates = sorted(emails)
    with SessionLocal() as session:
        for start in range(0, len(candidates), 500):
            statement = select(Customer.email).where(
                Customer.email.in_(candidates[start : start + 500])
            )
            matches.update(session.scalars(statement))
    return matches


def get_email_lookup() -> EmailLookup:
    return lookup_existing_emails
