from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path

import pytest

from ledgerlite.importer import (
    ColumnMapping,
    ImportFormatError,
    import_csv,
    parse_amount,
)


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "s.csv"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("12.50", "12.50"),
        ("£1,234.50", "1234.50"),
        ("-3.00", "-3.00"),
        ("(7.25)", "-7.25"),
        ("", "0"),
    ],
)
def test_parse_amount(text: str, expected: str) -> None:
    assert parse_amount(text) == Decimal(expected)


def test_parse_amount_rejects_garbage() -> None:
    with pytest.raises(ImportFormatError):
        parse_amount("twelve")


def test_debit_credit_columns(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "Date,Description,Debit,Credit\n"
        "01/03/2026,TESCO,10.00,\n"
        "02/03/2026,SALARY,,100.00\n",
    )
    txs = import_csv(path)
    assert [tx.amount for tx in txs] == [Decimal("-10.00"), Decimal("100.00")]
    assert txs[0].date == dt.date(2026, 3, 1)


def test_signed_amount_column_and_custom_format(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "when;what;amt\n2026-03-05;Coffee;-3.20\n2026-03-04;Pay;50\n",
    )
    mapping = ColumnMapping(
        date="when",
        description="what",
        amount="amt",
        debit=None,
        credit=None,
        date_format="%Y-%m-%d",
        delimiter=";",
    )
    txs = import_csv(path, mapping)
    assert [tx.description for tx in txs] == ["Pay", "Coffee"]  # sorted by date
    assert txs[1].amount == Decimal("-3.20")


def test_invert_amount_for_credit_card_exports(tmp_path: Path) -> None:
    path = write(tmp_path, "Date,Description,Amount\n01/03/2026,Shop,25.00\n")
    mapping = ColumnMapping(
        amount="Amount", debit=None, credit=None, invert_amount=True
    )
    assert import_csv(path, mapping)[0].amount == Decimal("-25.00")


def test_missing_column_is_reported(tmp_path: Path) -> None:
    path = write(tmp_path, "Date,Memo,Debit,Credit\n01/03/2026,x,1,\n")
    with pytest.raises(ImportFormatError, match="Description"):
        import_csv(path)


def test_bad_date_reports_line(tmp_path: Path) -> None:
    path = write(tmp_path, "Date,Description,Debit,Credit\n99/99/2026,x,1,\n")
    with pytest.raises(ImportFormatError, match="line 2"):
        import_csv(path)


def test_mapping_from_toml_table_signed_amount() -> None:
    mapping = ColumnMapping.from_dict({"amount": "Value", "date_format": "%d-%m-%Y"})
    assert mapping.debit is None
    assert mapping.credit is None
    with pytest.raises(ImportFormatError, match="unknown"):
        ColumnMapping.from_dict({"colour": "red"})


def test_example_statement_imports(example_statement: Path) -> None:
    txs = import_csv(example_statement)
    assert len(txs) >= 55
    assert {tx.month for tx in txs} == {"2026-01", "2026-02", "2026-03"}
