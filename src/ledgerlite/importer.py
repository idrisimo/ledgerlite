"""CSV statement import with a configurable column mapping."""

from __future__ import annotations

import csv
import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass, fields
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from ledgerlite.models import Transaction

_CURRENCY_CHARS = "£$€ " + chr(0xA0)  # symbols, space, no-break space


class ImportFormatError(ValueError):
    """Raised when a statement cannot be parsed with the given mapping."""


@dataclass(frozen=True, slots=True)
class ColumnMapping:
    """Describes how a bank's CSV columns map onto a :class:`Transaction`.

    Use either a single signed ``amount`` column, or ``debit`` and/or ``credit``
    columns. If ``amount`` is set, the debit/credit columns are ignored.
    Set ``invert_amount`` for exports (often credit cards) where spending is
    positive.
    """

    date: str = "Date"
    description: str = "Description"
    amount: str | None = None
    debit: str | None = "Debit"
    credit: str | None = "Credit"
    date_format: str = "%d/%m/%Y"
    delimiter: str = ","
    invert_amount: bool = False
    encoding: str = "utf-8-sig"

    def __post_init__(self) -> None:
        if self.amount is None and self.debit is None and self.credit is None:
            raise ImportFormatError(
                "mapping needs an 'amount' column or 'debit'/'credit' columns"
            )

    @classmethod
    def from_dict(cls, table: Mapping[str, Any]) -> ColumnMapping:
        """Build a mapping from a parsed TOML ``[import]`` table."""
        known = {f.name for f in fields(cls)}
        unknown = set(table) - known
        if unknown:
            raise ImportFormatError(
                f"unknown [import] option(s): {', '.join(sorted(unknown))}"
            )
        values = dict(table)
        if "amount" in values:
            # A signed amount column replaces the debit/credit defaults.
            values.setdefault("debit", None)
            values.setdefault("credit", None)
        return cls(**values)


def parse_amount(text: str) -> Decimal:
    """Parse a money string such as ``"1,234.50"`` or ``"(12.00)"``.

    Empty strings parse as zero. Parentheses and a leading minus mean negative.
    """
    cleaned = text.strip()
    if not cleaned:
        return Decimal(0)
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    for ch in _CURRENCY_CHARS:
        cleaned = cleaned.replace(ch, "")
    cleaned = cleaned.replace(",", "")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        raise ImportFormatError(f"invalid amount: {text!r}") from None
    return -value if negative else value


def import_csv(
    path: str | Path, mapping: ColumnMapping | None = None
) -> list[Transaction]:
    """Read a statement CSV into a date-ordered list of transactions."""
    mapping = mapping or ColumnMapping()
    with open(path, newline="", encoding=mapping.encoding) as handle:
        reader = csv.DictReader(handle, delimiter=mapping.delimiter)
        if reader.fieldnames is None:
            raise ImportFormatError(f"{path}: file is empty")
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        _check_columns(reader.fieldnames, mapping)
        transactions = [
            _parse_row(row, mapping, reader.line_num)
            for row in reader
            if any((value or "").strip() for value in row.values())
        ]
    transactions.sort(key=lambda tx: tx.date)
    return transactions


def _check_columns(fieldnames: list[str], mapping: ColumnMapping) -> None:
    wanted = [mapping.date, mapping.description]
    if mapping.amount is not None:
        wanted.append(mapping.amount)
    else:
        wanted.extend(c for c in (mapping.debit, mapping.credit) if c is not None)
    missing = [name for name in wanted if name not in fieldnames]
    if missing:
        raise ImportFormatError(
            f"missing column(s) {', '.join(missing)}; found {', '.join(fieldnames)}"
        )


def _parse_row(
    row: dict[str, str | None], mapping: ColumnMapping, line: int
) -> Transaction:
    def cell(name: str | None) -> str:
        return (row.get(name) or "").strip() if name else ""

    try:
        date = dt.datetime.strptime(cell(mapping.date), mapping.date_format).date()
        if mapping.amount is not None:
            amount = parse_amount(cell(mapping.amount))
        else:
            amount = parse_amount(cell(mapping.credit)) - parse_amount(
                cell(mapping.debit)
            )
    except ValueError as exc:
        raise ImportFormatError(f"line {line}: {exc}") from None
    if mapping.invert_amount:
        amount = -amount
    description = " ".join(cell(mapping.description).split())
    return Transaction(date=date, description=description, amount=amount)
