from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledgerlite import __version__
from ledgerlite.cli import main


def test_report_table(
    example_statement: Path, example_rules: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["report", str(example_statement), "--rules", str(example_rules)])
    out = capsys.readouterr().out
    assert code == 0
    for month in ("January 2026", "February 2026", "March 2026"):
        assert month in out


def test_report_single_month_json(
    example_statement: Path, example_rules: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        [
            "report",
            str(example_statement),
            "--rules",
            str(example_rules),
            "--month",
            "2026-03",
            "--format",
            "json",
        ]
    )
    data = json.loads(capsys.readouterr().out)
    assert code == 0
    assert [m["month"] for m in data["months"]] == ["2026-03"]
    assert data["months"][0]["income"] == "2450.00"


def test_report_without_rules_is_all_uncategorised(
    example_statement: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["report", str(example_statement), "--month", "2026-01"]) == 0
    assert "Uncategorised" in capsys.readouterr().out


def test_report_empty_month_exits_1(
    example_statement: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["report", str(example_statement), "--month", "2030-01"]) == 1
    assert "no transactions" in capsys.readouterr().err


def test_missing_file_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["report", "nope.csv"]) == 2
    assert "error" in capsys.readouterr().err


def test_bad_month_rejected() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["report", "x.csv", "--month", "March"])
    assert exc.value.code == 2


def test_categories_lists_unmatched(
    example_statement: Path, example_rules: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main(["categories", str(example_statement), "--rules", str(example_rules)]) == 0
    )
    out = capsys.readouterr().out
    assert "transactions categorised" in out
    assert "Mr Patel Dental" in out
    assert "Tesco" not in out


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out
