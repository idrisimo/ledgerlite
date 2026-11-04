# ledgerlite

[![CI](https://github.com/idrisimo/ledgerlite/actions/workflows/ci.yml/badge.svg)](https://github.com/idrisimo/ledgerlite/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Turn bank-statement CSV exports into categorised monthly spending reports, from your terminal, with no dependencies.

## Features

- Configurable CSV import: column names, date format, delimiter, and either separate debit/credit columns or one signed amount column
- TOML categorisation rules: substring or regex matching, optional amount ranges, first match wins, fallback to "Uncategorised"
- Monthly reports: spend per category, income vs spend, top merchants
- Output as an aligned table, JSON, CSV or Markdown
- `categories` command that lists what your rules missed, so you can write better ones
- Python 3.11+, standard library only at runtime, `Decimal` for all money, fully typed

## Install

```bash
pip install git+https://github.com/idrisimo/ledgerlite
```

## Quickstart

The repo ships with a fake three-month statement and a matching rules file in `examples/`.

```bash
ledgerlite report examples/statement.csv --rules examples/rules.toml --month 2026-03
```

```text
March 2026 (21 transactions)

   Income      Spend       Net
---------  ---------  --------
£2,450.00  £1,559.57  +£890.43

Category              Spend   Share
----------------  ---------  ------
Housing             £950.00   60.9%
Groceries           £182.51   11.7%
Bills               £120.60    7.7%
Big Purchases        £89.99    5.8%
Entertainment        £42.50    2.7%
Eating Out           £41.90    2.7%
Transport            £39.10    2.5%
Health & Fitness     £24.99    1.6%
Subscriptions        £22.98    1.5%
Uncategorised        £45.00    2.9%
Total             £1,559.57  100.0%

Top merchants      Spend  Visits
---------------  -------  ------
Rent             £950.00       1
Tesco Stores     £146.61       3
Amazon.Co.Uk      £89.99       1
British Gas Dd    £58.10       1
Mr Patel Dental   £45.00       1
```

Omit `--month` to report every month in the file. Other options: `--format table|json|csv|markdown`, `--top N` (merchants shown), `--currency SYMBOL`.

Find out what your rules are missing:

```bash
ledgerlite categories examples/statement.csv --rules examples/rules.toml
```

```text
58 of 61 transactions categorised.

Uncategorised       Count      Net
------------------  -----  -------
Mr Patel Dental         2  -£90.00
Local Hardware Ltd      1  -£23.75
```

Positive amounts count as income (refunds included) and negative amounts as spend. Exit codes: `0` success, `1` no transactions matched, `2` bad input.

## Rules file format

Rules live in a TOML file (see [`examples/rules.toml`](examples/rules.toml)). They are checked top to bottom and the first match wins.

```toml
[import]                     # optional; shown with its defaults
date = "Date"
description = "Description"
debit = "Debit"
credit = "Credit"            # or: amount = "Amount" for one signed column
date_format = "%d/%m/%Y"
# delimiter = ","
# invert_amount = true       # for exports where spending is positive

[[rules]]
category = "Groceries"
contains = ["tesco", "sainsbury"]   # case-insensitive substrings

[[rules]]
category = "Eating Out"
regex = "pret|costa|deliveroo"      # case-insensitive regex

[[rules]]
category = "Big Purchases"
contains = "amazon"
min_amount = 50                     # compared to the absolute amount
```

Each rule needs a `category` and at least one of `contains`, `regex`, `min_amount` or `max_amount`. `contains` and `regex` take a string or a list; a rule matches if any entry matches.

## Project structure

```text
src/ledgerlite/
  models.py     Transaction dataclass
  importer.py   CSV import and column mapping
  rules.py      TOML rules and categorisation
  report.py     monthly aggregation and output formats
  cli.py        argparse command line
examples/       sample statement and rules
tests/          pytest suite
```

## Running tests

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"     # Windows: .venv\Scripts\pip
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

## Roadmap

- Preset column mappings for common UK banks
- Month-over-month comparison and budget targets
- Optional charts and an HTML report

## License

[MIT](LICENSE) &copy; 2026 Idris Silva
