"""Synthetic data for the shared public demonstration."""

import os

DEMO_CSV = (
    b"Name,Email,Company\n"
    b"Alex Morgan,alex.demo@example.com,Northstar\n"
    b"Sam Rivera,sam.demo@example.com,Cedar Labs\n"
    b"Taylor Chen,taylor.demo@example.com,Harbor\n"
    b"Invalid Address,not-an-email,Northstar\n"
    b",missing.demo@example.com,Cedar Labs\n"
    b"Duplicate Alex,alex.demo@example.com,Northstar\n"
)


def enforce_demo_upload(content: bytes) -> None:
    if os.getenv("PUBLIC_DEMO") == "1" and content != DEMO_CSV:
        raise ValueError(
            "This shared demo accepts only the supplied sample. "
            "Click Load demo data. Run locally to import your own files."
        )
