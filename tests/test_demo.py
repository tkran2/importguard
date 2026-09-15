import pytest

from importguard.demo import DEMO_CSV
from importguard.parsing import parse_csv


def test_public_demo_accepts_sample(monkeypatch):
    monkeypatch.setenv("PUBLIC_DEMO", "1")
    assert len(parse_csv(DEMO_CSV).rows) == 6


def test_public_demo_rejects_other_uploads(monkeypatch):
    monkeypatch.setenv("PUBLIC_DEMO", "1")
    with pytest.raises(ValueError, match="only the supplied sample"):
        parse_csv(b"Name,Email\nJane,jane@example.com\n")


def test_local_mode_accepts_other_uploads(monkeypatch):
    monkeypatch.delenv("PUBLIC_DEMO", raising=False)
    assert len(parse_csv(b"Name,Email\nJane,jane@example.com\n").rows) == 1
