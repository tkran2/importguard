"""Map source columns and validate customer rows without database writes."""

from dataclasses import dataclass

from email_validator import EmailNotValidError, validate_email

from importguard.parsing import ParsedTable

FIELD_LIMITS = {
    "email": 320,
    "full_name": 200,
    "company": 200,
    "phone": 50,
}
REQUIRED_FIELDS = {"email", "full_name"}


@dataclass(frozen=True)
class ValidatedRow:
    row_number: int
    original: dict[str, str]
    cleaned: dict[str, str | None]
    errors: list[str]

    @property
    def valid(self) -> bool:
        return not self.errors


def validate_mapping(headers: list[str], mapping: dict[str, str]) -> None:
    """Mappings use destination fields as keys and source headers as values."""
    unknown = set(mapping) - set(FIELD_LIMITS)
    if unknown:
        raise ValueError(f"Unknown destination fields: {', '.join(sorted(unknown))}")
    missing = REQUIRED_FIELDS - set(mapping)
    if missing:
        raise ValueError(f"Map required fields: {', '.join(sorted(missing))}")
    if any(source not in headers for source in mapping.values()):
        raise ValueError("A mapped source column does not exist.")
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("Map each source column to only one destination field.")


def validate_rows(
    table: ParsedTable,
    mapping: dict[str, str],
    existing_emails: set[str] | None = None,
) -> list[ValidatedRow]:
    validate_mapping(table.headers, mapping)
    existing = {email.strip().lower() for email in (existing_emails or set())}
    accepted_emails: dict[str, int] = {}
    results = []

    for row in table.rows:
        cleaned: dict[str, str | None] = {}
        errors = []

        for field, limit in FIELD_LIMITS.items():
            source = mapping.get(field)
            value = row.values[source].strip() if source is not None else ""
            cleaned[field] = value or None
            if field in REQUIRED_FIELDS and not value:
                errors.append(f"{field}: required.")
            if len(value) > limit:
                errors.append(f"{field}: must contain at most {limit} characters.")
            if any(ord(character) < 32 for character in value):
                errors.append(f"{field}: must not contain control characters.")

        email = cleaned["email"]
        if email:
            try:
                # Lowercasing the entire address is our customer identity policy.
                email = validate_email(
                    email, check_deliverability=False
                ).normalized.lower()
                cleaned["email"] = email
                if len(email) > FIELD_LIMITS["email"]:
                    errors.append("email: normalized address is too long.")
            except EmailNotValidError as exc:
                errors.append(f"email: {exc}")

        if email in existing:
            errors.append("email: already exists in the customer database.")
        if email in accepted_emails:
            errors.append(
                f"email: duplicates the valid row on line {accepted_emails[email]}."
            )

        if not errors and email:
            accepted_emails[email] = row.row_number

        results.append(
            ValidatedRow(
                row_number=row.row_number,
                original=dict(row.values),
                cleaned=cleaned,
                errors=errors,
            )
        )

    return results
