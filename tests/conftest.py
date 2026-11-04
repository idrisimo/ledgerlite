from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path

import pytest

from ledgerlite.models import Transaction

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


@pytest.fixture
def example_statement() -> Path:
    return EXAMPLES / "statement.csv"


@pytest.fixture
def example_rules() -> Path:
    return EXAMPLES / "rules.toml"


def make_tx(
    description: str,
    amount: str,
    day: str = "2026-03-10",
    category: str = "Uncategorised",
) -> Transaction:
    return Transaction(
        dt.date.fromisoformat(day), description, Decimal(amount), category
    )
