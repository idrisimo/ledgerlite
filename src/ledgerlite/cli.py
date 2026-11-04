"""Command-line interface for ledgerlite."""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

from ledgerlite import __version__
from ledgerlite.importer import ColumnMapping, import_csv
from ledgerlite.models import UNCATEGORISED, Transaction
from ledgerlite.report import (
    FORMATS,
    build_report,
    format_table,
    merchant_name,
    money,
    render,
)
from ledgerlite.rules import RuleSet, load_rules


def _month(value: str) -> str:
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value):
        raise argparse.ArgumentTypeError(f"{value!r} is not a month like 2026-03")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ledgerlite",
        description="Turn bank-statement CSV exports into categorised monthly reports.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("statement", type=Path, help="bank statement CSV file")
        p.add_argument("--rules", type=Path, help="TOML rules file")

    report = sub.add_parser("report", help="print a categorised monthly report")
    common(report)
    report.add_argument("--month", type=_month, help="only report this month (YYYY-MM)")
    report.add_argument("--format", choices=FORMATS, default="table")
    report.add_argument("--top", type=int, default=5, help="top merchants to show")
    report.add_argument("--currency", default="£", help="currency symbol (default £)")

    cats = sub.add_parser(
        "categories", help="list uncategorised descriptions to help write rules"
    )
    common(cats)
    return parser


def _load(statement: Path, rules_path: Path | None) -> list[Transaction]:
    ruleset = load_rules(rules_path) if rules_path else RuleSet()
    transactions = import_csv(statement, ruleset.mapping or ColumnMapping())
    return ruleset.categorise_all(transactions)


def _cmd_report(args: argparse.Namespace) -> int:
    transactions = _load(args.statement, args.rules)
    reports = build_report(transactions, month=args.month, top=args.top)
    if not reports:
        where = f" for {args.month}" if args.month else ""
        print(f"ledgerlite: no transactions found{where}", file=sys.stderr)
        return 1
    print(render(reports, args.format, args.currency))
    return 0


def _cmd_categories(args: argparse.Namespace) -> int:
    transactions = _load(args.statement, args.rules)
    groups: dict[str, list[Decimal]] = defaultdict(list)
    for tx in transactions:
        if tx.category == UNCATEGORISED:
            groups[merchant_name(tx.description)].append(tx.amount)
    matched = len(transactions) - sum(len(v) for v in groups.values())
    print(f"{matched} of {len(transactions)} transactions categorised.")
    if not groups:
        return 0
    rows = [
        [name, str(len(amts)), money(sum(amts, Decimal(0)), signed=True)]
        for name, amts in sorted(
            groups.items(), key=lambda kv: (sum(kv[1], Decimal(0)), kv[0])
        )
    ]
    print()
    print(format_table(["Uncategorised", "Count", "Net"], rows, right=(1, 2)))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the ``ledgerlite`` console script."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    handlers = {"report": _cmd_report, "categories": _cmd_categories}
    try:
        return handlers[args.command](args)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"ledgerlite: error: {exc}", file=sys.stderr)
        return 2
