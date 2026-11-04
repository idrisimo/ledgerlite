"""Core data types shared across ledgerlite."""

from __future__ import annotations

import dataclasses
import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

UNCATEGORISED = "Uncategorised"


@dataclass(frozen=True, slots=True)
class Transaction:
    """A single statement line.

    ``amount`` is signed: negative for money going out, positive for money in.
    """

    date: dt.date
    description: str
    amount: Decimal
    category: str = UNCATEGORISED

    @property
    def is_income(self) -> bool:
        return self.amount > 0

    @property
    def is_spend(self) -> bool:
        return self.amount < 0

    @property
    def month(self) -> str:
        """The ``YYYY-MM`` key this transaction belongs to."""
        return f"{self.date.year:04d}-{self.date.month:02d}"

    def with_category(self, category: str) -> Transaction:
        return dataclasses.replace(self, category=category)
