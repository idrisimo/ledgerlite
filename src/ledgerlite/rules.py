"""TOML-driven transaction categorisation. The first matching rule wins."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from ledgerlite.importer import ColumnMapping
from ledgerlite.models import UNCATEGORISED, Transaction


class RuleError(ValueError):
    """Raised when a rules file is malformed."""


@dataclass(frozen=True, slots=True)
class Rule:
    """One categorisation rule.

    A transaction matches when *any* ``contains`` substring or regex pattern
    matches its description (case-insensitive) and its absolute amount lies in
    the optional ``[min_amount, max_amount]`` range. A rule with only an amount
    range matches on amount alone.
    """

    category: str
    contains: tuple[str, ...] = ()
    patterns: tuple[re.Pattern[str], ...] = ()
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None

    def matches(self, tx: Transaction) -> bool:
        size = abs(tx.amount)
        if self.min_amount is not None and size < self.min_amount:
            return False
        if self.max_amount is not None and size > self.max_amount:
            return False
        if not self.contains and not self.patterns:
            return True
        text = tx.description.lower()
        if any(needle in text for needle in self.contains):
            return True
        return any(pattern.search(tx.description) for pattern in self.patterns)


@dataclass(frozen=True, slots=True)
class RuleSet:
    """An ordered list of rules plus an optional CSV column mapping."""

    rules: tuple[Rule, ...] = ()
    mapping: ColumnMapping | None = None

    def category_for(self, tx: Transaction) -> str:
        for rule in self.rules:
            if rule.matches(tx):
                return rule.category
        return UNCATEGORISED

    def categorise(self, tx: Transaction) -> Transaction:
        return tx.with_category(self.category_for(tx))

    def categorise_all(self, transactions: Iterable[Transaction]) -> list[Transaction]:
        return [self.categorise(tx) for tx in transactions]


def load_rules(path: str | Path) -> RuleSet:
    """Load a rules TOML file."""
    with open(path, "rb") as handle:
        data = tomllib.load(handle)
    return parse_rules(data)


def parse_rules(data: Mapping[str, Any]) -> RuleSet:
    """Build a :class:`RuleSet` from parsed TOML data."""
    raw_rules = data.get("rules", [])
    if not isinstance(raw_rules, list):
        raise RuleError("'rules' must be an array of tables ([[rules]])")
    rules = tuple(_parse_rule(raw, i) for i, raw in enumerate(raw_rules, start=1))
    mapping = None
    if "import" in data:
        mapping = ColumnMapping.from_dict(data["import"])
    return RuleSet(rules=rules, mapping=mapping)


def _as_list(value: Any, label: str, index: int) -> list[str]:
    items = [value] if isinstance(value, str) else value
    if not isinstance(items, list) or not all(isinstance(i, str) for i in items):
        raise RuleError(f"rule {index}: '{label}' must be a string or list of strings")
    return items


def _as_amount(value: Any, label: str, index: int) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        raise RuleError(f"rule {index}: '{label}' is not a number") from None


def _parse_rule(raw: Mapping[str, Any], index: int) -> Rule:
    category = raw.get("category")
    if not isinstance(category, str) or not category.strip():
        raise RuleError(f"rule {index}: missing 'category'")
    contains = tuple(
        s.lower() for s in _as_list(raw.get("contains", []), "contains", index)
    )
    regexes = _as_list(raw.get("regex", []), "regex", index)
    try:
        patterns = tuple(re.compile(r, re.IGNORECASE) for r in regexes)
    except re.error as exc:
        raise RuleError(f"rule {index}: bad regex ({exc})") from None
    min_amount = _as_amount(raw.get("min_amount"), "min_amount", index)
    max_amount = _as_amount(raw.get("max_amount"), "max_amount", index)
    if not (contains or patterns or min_amount is not None or max_amount is not None):
        raise RuleError(f"rule {index}: needs 'contains', 'regex' or an amount range")
    return Rule(category.strip(), contains, patterns, min_amount, max_amount)
