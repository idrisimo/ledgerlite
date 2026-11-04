from __future__ import annotations

from pathlib import Path

import pytest

from ledgerlite.models import UNCATEGORISED
from ledgerlite.rules import RuleError, load_rules, parse_rules

from .conftest import make_tx


def test_contains_is_case_insensitive() -> None:
    rs = parse_rules({"rules": [{"category": "Groceries", "contains": "tesco"}]})
    assert rs.category_for(make_tx("TESCO STORES 3412", "-5")) == "Groceries"


def test_regex_match() -> None:
    rs = parse_rules({"rules": [{"category": "Bills", "regex": "gas|water"}]})
    assert rs.category_for(make_tx("Thames Water", "-30")) == "Bills"
    assert rs.category_for(make_tx("Cafe", "-3")) == UNCATEGORISED


def test_first_match_wins() -> None:
    rs = parse_rules(
        {
            "rules": [
                {"category": "A", "contains": "shop"},
                {"category": "B", "contains": "shop"},
            ]
        }
    )
    assert rs.category_for(make_tx("The Shop", "-1")) == "A"


def test_amount_range_uses_absolute_value() -> None:
    rs = parse_rules(
        {
            "rules": [
                {"category": "Big", "contains": "amazon", "min_amount": 50},
                {"category": "Shopping", "contains": "amazon"},
            ]
        }
    )
    assert rs.category_for(make_tx("AMAZON", "-89.99")) == "Big"
    assert rs.category_for(make_tx("AMAZON", "-19.99")) == "Shopping"


def test_amount_only_rule() -> None:
    rs = parse_rules({"rules": [{"category": "Tiny", "max_amount": 1}]})
    assert rs.category_for(make_tx("anything", "-0.50")) == "Tiny"
    assert rs.category_for(make_tx("anything", "-5")) == UNCATEGORISED


def test_categorise_all_sets_category() -> None:
    rs = parse_rules({"rules": [{"category": "Fun", "contains": "odeon"}]})
    out = rs.categorise_all([make_tx("ODEON", "-9"), make_tx("Other", "-1")])
    assert [tx.category for tx in out] == ["Fun", UNCATEGORISED]


@pytest.mark.parametrize(
    "bad",
    [
        {"rules": [{"contains": "x"}]},
        {"rules": [{"category": "X"}]},
        {"rules": [{"category": "X", "regex": "("}]},
        {"rules": [{"category": "X", "contains": 5}]},
        {"rules": "nope"},
    ],
)
def test_invalid_rules_raise(bad: dict) -> None:
    with pytest.raises(RuleError):
        parse_rules(bad)


def test_example_rules_load(example_rules: Path) -> None:
    rs = load_rules(example_rules)
    assert len(rs.rules) >= 8
    assert rs.mapping is not None
    assert rs.mapping.date_format == "%d/%m/%Y"
