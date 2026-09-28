import json
from pathlib import Path

import pytest

from backend.services.normalize import normalize


FIXTURES = Path(__file__).parent / "fixtures" / "obf"


def fixture(barcode: str) -> list[str]:
    return normalize(json.loads((FIXTURES / f"{barcode}.json").read_text())["product"]["ingredients_text"])


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  AQUA, Glycerin ,  Parfum.", ["water", "glycerin", "fragrance"]),
        ("Aqua 70%, Glycerin 2.5 %", ["water", "glycerin"]),
        ("Water; Oleic Acid • Resorcinol ، Linalool", ["water", "oleic acid", "resorcinol", "linalool"]),
        ("Aqua (Water, Eau), Parfum (Fragrance)", ["water", "fragrance"]),
        ("Toluene-2,5-Diamine, N,N-Bis(2-Hydroxyethyl)-P-Phenylenediamine Sulfate",
         ["toluene-2,5-diamine", "n,n-bis(2-hydroxyethyl)-p-phenylenediamine sulfate"]),
        ("C.I. 77891, CI77491, ci-19140, Yellow 5 (CI 19140), CI 14700/RED 4, Titanium Dioxide",
         ["ci 77891", "ci 77491", "ci 19140", "ci 14700"]),
        ("FD&C Blue No.1, D&C Green No. 5", ["ci 42090", "ci 61570"]),
        ("Aqua, p-Phenylenediamine (CI 76060), Toluene-2,5-Diamine Sulfate (CI 76043), Yellow 5 (CI 19140)",
         ["water", "p-phenylenediamine", "toluene-2,5-diamine sulfate", "ci 19140"]),
        ("CI 76042, Resorcinol (C.I. 76505), CI-76545, Basic Brown 17 (CI 12251)",
         ["toluene-2,5-diamine", "resorcinol", "m-aminophenol", "basic brown 17"]),
        ("HÉLIANTHUS ANNUUS SEED OIL/SUNFLOWER SEED OIL, Caprylyl/Capryl Glucoside",
         ["helianthus annuus seed oil", "caprylyl/capryl glucoside"]),
        ("Methylchloroisothi - azolinone, PEG - 12", ["methylchloroisothiazolinone", "peg-12"]),
        ("Aqua - Resorcinol - m-Aminophenol - Toluene-2,5-Diamine Sulfate",
         ["water", "resorcinol", "m-aminophenol", "toluene-2,5-diamine sulfate"]),
        ("Colorant: Water, PPD\r\n\r\nDeveloper: Aqua, Hydrogen Peroxide, (F01)",
         ["water", "p-phenylenediamine", "hydrogen peroxide"]),
        ("1126261 - CRÈME COLORANTE - PARAFFINUM LIQUIDUM, AQUA", ["mineral oil", "water"]),
        ("", []),
    ],
)
def test_normalize(raw: str, expected: list[str]) -> None:
    assert normalize(raw) == expected


def test_fixtures_are_clean() -> None:
    for path in FIXTURES.glob("*.json"):
        text = (json.loads(path.read_text()).get("product") or {}).get("ingredients_text")
        for name in normalize(text or ""):
            assert name == name.strip().casefold()
            assert not set(name) & set("*%:;•\r\n"), (path.stem, name)


def test_fixture_dyes_are_found() -> None:
    assert "p-phenylenediamine" in fixture("0309978695325")
    assert "toluene-2,5-diamine sulfate" in fixture("3178040643802")  # dash-separated list
    assert "toluene-2,5-diamine" in fixture("3600541524415")
    assert {"ci 19140", "ci 61570"} <= set(fixture("3140100047875"))
    assert fixture("3348070010589") == ["lawsonia inermis", "sodium picramate", "water"]
    assert fixture("0309978695325").count("water") == 1  # kit with three parts
