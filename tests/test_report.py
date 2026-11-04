from __future__ import annotations

import csv
import io
import json
from decimal import Decimal

import pytest

from ledgerlite.report import build_report, merchant_name, money, render

from .conftest import make_tx

TXS = [
    make_tx("SALARY", "1000.00", "2026-02-28", "Income"),
    make_tx("TESCO STORES 1", "-40.00", "2026-03-02", "Groceries"),
    make_tx("TESCO STORES 2", "-60.00", "2026-03-09", "Groceries"),
    make_tx("COSTA 11", "-10.00", "2026-03-10", "Eating Out"),
    make_tx("MYSTERY", "-90.00", "2026-03-11"),
    make_tx("SALARY", "2000.00", "2026-03-28", "Income"),
]


def test_months_are_sorted_and_filterable() -> None:
    assert [r.month for r in build_report(TXS)] == ["2026-02", "2026-03"]
    assert [r.month for r in build_report(TXS, month="2026-03")] == ["2026-03"]
    assert build_report(TXS, month="2025-01") == []


def test_income_spend_net() -> None:
    march = build_report(TXS, month="2026-03")[0]
    assert march.income == Decimal("2000.00")
    assert march.spend == Decimal("200.00")
    assert march.net == Decimal("1800.00")
    assert march.title == "March 2026"


def test_categories_ranked_with_uncategorised_last() -> None:
    march = build_report(TXS, month="2026-03")[0]
    names = [c.category for c in march.categories]
    assert names == ["Groceries", "Eating Out", "Uncategorised"]
    assert march.share(Decimal("100.00")) == Decimal("50.0")


def test_top_merchants_merge_store_numbers() -> None:
    march = build_report(TXS, month="2026-03", top=2)[0]
    assert len(march.top_merchants) == 2
    top = march.top_merchants[0]
    assert (top.merchant, top.total, top.count) == (
        "Tesco Stores",
        Decimal("100.00"),
        2,
    )
    assert march.top_merchants[1].merchant == "Mystery"


def test_merchant_name() -> None:
    assert merchant_name("TESCO STORES 3412") == "Tesco Stores"
    assert merchant_name("AMAZON.CO.UK*2K4TY") == "Amazon.Co.Uk"
    assert merchant_name("RENT - LETTINGS DIRECT") == "Rent"


def test_money_format() -> None:
    assert money(Decimal("1234.5")) == "£1,234.50"
    assert money(Decimal("-3"), "$") == "-$3.00"
    assert money(Decimal("5"), signed=True) == "+£5.00"


def test_table_is_aligned() -> None:
    out = render(build_report(TXS, month="2026-03"), "table")
    assert "March 2026" in out
    lines = out.splitlines()
    header = next(ln for ln in lines if ln.startswith("Category"))
    row = next(ln for ln in lines if ln.startswith("Groceries"))
    # Right-aligned money column: header and values end at the same position.
    assert header.index("Spend") + len("Spend") == row.index("100.00") + len("100.00")


def test_json_format() -> None:
    data = json.loads(render(build_report(TXS, month="2026-03"), "json"))
    month = data["months"][0]
    assert month["spend"] == "200.00"
    assert month["categories"][0] == {
        "category": "Groceries",
        "spend": "100.00",
        "share": "50.0",
    }


def test_csv_format() -> None:
    out = render(build_report(TXS, month="2026-03"), "csv")
    rows = list(csv.reader(io.StringIO(out)))
    assert rows[0] == ["month", "section", "name", "amount"]
    assert ["2026-03", "category", "Groceries", "100.00"] in rows


def test_markdown_format() -> None:
    out = render(build_report(TXS, month="2026-03"), "markdown")
    assert out.startswith("## March 2026")
    assert "| Groceries | £100.00 | 50.0% |" in out


def test_unknown_format_raises() -> None:
    with pytest.raises(ValueError, match="unknown format"):
        render([], "xml")
