"""Monthly spending reports and their text renderings."""

from __future__ import annotations

import calendar
import csv
import io
import json
import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import NamedTuple

from ledgerlite.models import UNCATEGORISED, Transaction

FORMATS = ("table", "json", "csv", "markdown")
_ZERO = Decimal(0)


class CategoryTotal(NamedTuple):
    category: str
    total: Decimal


class MerchantTotal(NamedTuple):
    merchant: str
    total: Decimal
    count: int


@dataclass(frozen=True, slots=True)
class MonthReport:
    """Aggregates for one calendar month. ``spend`` is a positive number."""

    month: str
    income: Decimal
    spend: Decimal
    transaction_count: int
    categories: tuple[CategoryTotal, ...]
    top_merchants: tuple[MerchantTotal, ...]

    @property
    def net(self) -> Decimal:
        return self.income - self.spend

    def share(self, total: Decimal) -> Decimal:
        """Percentage of this month's spend that ``total`` represents."""
        if not self.spend:
            return _ZERO
        return (total / self.spend * 100).quantize(Decimal("0.1"))

    @property
    def title(self) -> str:
        year, month = self.month.split("-")
        return f"{calendar.month_name[int(month)]} {year}"


def merchant_name(description: str) -> str:
    """Reduce a raw statement description to a readable merchant name.

    Drops anything after `` - `` or ``*`` and tokens containing digits (store or
    reference numbers), then title-cases the rest.
    """
    head = re.split(r"\s-\s|\*", description, maxsplit=1)[0]
    words = [w for w in head.split() if not any(c.isdigit() for c in w)]
    return " ".join(words).title() or description.strip().title()


def build_report(
    transactions: Iterable[Transaction], month: str | None = None, top: int = 5
) -> list[MonthReport]:
    """Group transactions by month and summarise each one.

    Positive amounts count as income (refunds included), negative as spend.
    """
    by_month: dict[str, list[Transaction]] = defaultdict(list)
    for tx in transactions:
        if month is None or tx.month == month:
            by_month[tx.month].append(tx)
    return [_summarise(key, by_month[key], top) for key in sorted(by_month)]


def _summarise(month: str, txs: Sequence[Transaction], top: int) -> MonthReport:
    income = sum((tx.amount for tx in txs if tx.is_income), _ZERO)
    categories: dict[str, Decimal] = defaultdict(lambda: _ZERO)
    merchants: dict[str, list[Decimal]] = defaultdict(list)
    for tx in txs:
        if tx.is_spend:
            categories[tx.category] += -tx.amount
            merchants[merchant_name(tx.description)].append(-tx.amount)
    ranked_categories = sorted(
        categories.items(), key=lambda kv: (kv[0] == UNCATEGORISED, -kv[1], kv[0])
    )
    ranked_merchants = sorted(
        ((name, sum(amts, _ZERO), len(amts)) for name, amts in merchants.items()),
        key=lambda m: (-m[1], m[0]),
    )
    return MonthReport(
        month=month,
        income=income,
        spend=sum(categories.values(), _ZERO),
        transaction_count=len(txs),
        categories=tuple(CategoryTotal(*c) for c in ranked_categories),
        top_merchants=tuple(MerchantTotal(*m) for m in ranked_merchants[:top]),
    )


def money(amount: Decimal, currency: str = "£", signed: bool = False) -> str:
    """Format ``amount`` like ``£1,234.50`` (``+``/``-`` prefixed if ``signed``)."""
    sign = "-" if amount < 0 else ("+" if signed else "")
    return f"{sign}{currency}{abs(amount):,.2f}"


def render(reports: Sequence[MonthReport], fmt: str, currency: str = "£") -> str:
    """Render reports in one of :data:`FORMATS`."""
    if fmt == "table":
        return _render_table(reports, currency)
    if fmt == "json":
        return _render_json(reports)
    if fmt == "csv":
        return _render_csv(reports)
    if fmt == "markdown":
        return _render_markdown(reports, currency)
    raise ValueError(f"unknown format: {fmt!r}")


def format_table(
    headers: Sequence[str], rows: Sequence[Sequence[str]], right: Iterable[int] = ()
) -> str:
    """Lay out ``rows`` as a plain-text table with aligned columns."""
    right_cols = set(right)
    widths = [
        max(len(str(cell)) for cell in column)
        for column in zip(headers, *rows, strict=True)
    ]

    def line(cells: Sequence[str]) -> str:
        parts = [
            str(c).rjust(w) if i in right_cols else str(c).ljust(w)
            for i, (c, w) in enumerate(zip(cells, widths, strict=True))
        ]
        return "  ".join(parts).rstrip()

    rule = "  ".join("-" * w for w in widths)
    return "\n".join([line(headers), rule, *(line(r) for r in rows)])


def _category_rows(report: MonthReport, currency: str) -> list[list[str]]:
    rows = [
        [c.category, money(c.total, currency), f"{report.share(c.total)}%"]
        for c in report.categories
    ]
    rows.append(["Total", money(report.spend, currency), "100.0%" if rows else "0.0%"])
    return rows


def _merchant_rows(report: MonthReport, currency: str) -> list[list[str]]:
    return [
        [m.merchant, money(m.total, currency), str(m.count)]
        for m in report.top_merchants
    ]


def _render_table(reports: Sequence[MonthReport], currency: str) -> str:
    blocks = []
    for r in reports:
        summary = format_table(
            ["Income", "Spend", "Net"],
            [
                [
                    money(r.income, currency),
                    money(r.spend, currency),
                    money(r.net, currency, signed=True),
                ]
            ],
            right=(0, 1, 2),
        )
        cats = format_table(
            ["Category", "Spend", "Share"], _category_rows(r, currency), right=(1, 2)
        )
        parts = [f"{r.title} ({r.transaction_count} transactions)", "", summary]
        parts += ["", cats]
        if r.top_merchants:
            merchants = format_table(
                ["Top merchants", "Spend", "Visits"],
                _merchant_rows(r, currency),
                right=(1, 2),
            )
            parts += ["", merchants]
        blocks.append("\n".join(parts))
    return "\n\n".join(blocks)


def _render_json(reports: Sequence[MonthReport]) -> str:
    payload = {
        "months": [
            {
                "month": r.month,
                "transactions": r.transaction_count,
                "income": str(r.income),
                "spend": str(r.spend),
                "net": str(r.net),
                "categories": [
                    {
                        "category": c.category,
                        "spend": str(c.total),
                        "share": str(r.share(c.total)),
                    }
                    for c in r.categories
                ],
                "top_merchants": [
                    {"merchant": m.merchant, "spend": str(m.total), "count": m.count}
                    for m in r.top_merchants
                ],
            }
            for r in reports
        ]
    }
    return json.dumps(payload, indent=2)


def _render_csv(reports: Sequence[MonthReport]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["month", "section", "name", "amount"])
    for r in reports:
        writer.writerow([r.month, "summary", "income", r.income])
        writer.writerow([r.month, "summary", "spend", r.spend])
        writer.writerow([r.month, "summary", "net", r.net])
        for c in r.categories:
            writer.writerow([r.month, "category", c.category, c.total])
        for m in r.top_merchants:
            writer.writerow([r.month, "merchant", m.merchant, m.total])
    return buffer.getvalue().rstrip("\n")


def _markdown_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    align = ["---" if i == 0 else "---:" for i in range(len(headers))]
    lines = [headers, align, *rows]
    return "\n".join("| " + " | ".join(row) + " |" for row in lines)


def _render_markdown(reports: Sequence[MonthReport], currency: str) -> str:
    blocks = []
    for r in reports:
        parts = [
            f"## {r.title}",
            "",
            f"**Income:** {money(r.income, currency)} | "
            f"**Spend:** {money(r.spend, currency)} | "
            f"**Net:** {money(r.net, currency, signed=True)}",
            "",
            _markdown_table(
                ["Category", "Spend", "Share"], _category_rows(r, currency)
            ),
        ]
        if r.top_merchants:
            parts += [
                "",
                _markdown_table(
                    ["Top merchants", "Spend", "Visits"], _merchant_rows(r, currency)
                ),
            ]
        blocks.append("\n".join(parts))
    return "\n\n".join(blocks)
