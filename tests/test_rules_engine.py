import json
from pathlib import Path

import pytest

from backend.core.errors import HairlyError
from backend.services.normalize import normalize
from backend.services.rules_engine import KNOWN, RULES, evaluate


FIXTURES = Path(__file__).parent / "fixtures" / "obf"


def verdict(ingredients: list[str], **kwargs) -> str:
    return evaluate(ingredients, "dye allergy", **kwargs).verdict


def test_seed_names_are_already_normalized() -> None:
    for name in KNOWN:
        assert normalize(name) == [name]


def test_seed_severities_are_valid() -> None:
    for rules in RULES.values():
        assert 20 <= len(rules) <= 30
        assert all(rule["severity"] in {"low", "medium", "high"} and rule["reason"] for rule in rules.values())


def test_worst_severity_wins() -> None:
    result = evaluate(["water", "hydrogen peroxide", "p-phenylenediamine", "resorcinol"], "dye allergy")
    assert result.verdict == "avoid"
    assert [f.severity for f in result.flagged_ingredients] == ["high", "medium", "low"]


def test_verdicts() -> None:
    assert verdict(["water", "hydrogen peroxide"]) == "caution"
    assert verdict(["water", "glycerin"]) == "safe"
    assert verdict(["water", "mystery extract"]) == "unknown"
    assert verdict(["mystery extract", "resorcinol"]) == "caution"  # a match still counts
    assert verdict([]) == "unknown"
    assert verdict(["water", "glycerin"], is_hair=False) == "unknown"
    assert verdict(["p-phenylenediamine"], is_hair=False) == "unknown"


def test_color_treated_flags_sulfates_not_dyes() -> None:
    raw = json.loads((FIXTURES / "3600551119816.json").read_text())["product"]["ingredients_text"]
    result = evaluate(normalize(raw), "color-treated")  # baby shampoo: no dyes, but a sulfate
    assert result.verdict == "caution"
    assert [f.name for f in result.flagged_ingredients] == ["sodium laureth sulfate"]
    assert evaluate(["water", "sodium lauryl sulfate"], "color-treated").verdict == "avoid"
    assert evaluate(["water", "p-phenylenediamine"], "color-treated").verdict == "safe"


def test_concern_is_case_insensitive_and_validated() -> None:
    assert evaluate(["water"], "  Dye Allergy ").verdict == "safe"
    with pytest.raises(HairlyError) as exc:
        evaluate(["water"], "vegan")
    assert exc.value.code == "INVALID_INPUT"


@pytest.mark.parametrize(
    ("barcode", "expected"),
    [
        ("0309978695325", "avoid"),    # Revlon Colorsilk, PPD
        ("4064666339924", "avoid"),    # Wella Koleston, PTD sulfate
        ("3178040643802", "avoid"),    # Schwarzkopf, dash-separated list
        ("3348070010589", "caution"),  # henna + sodium picramate
        ("3600551119816", "safe"),     # baby shampoo, no dyes, all recognized
        ("6111056012986", "unknown"),  # Arabic label, unrecognized
        ("8698753382034", "unknown"),  # "Oksidanlı" only
    ],
)
def test_fixture_verdicts(barcode: str, expected: str) -> None:
    raw = json.loads((FIXTURES / f"{barcode}.json").read_text())["product"]["ingredients_text"]
    assert verdict(normalize(raw)) == expected
