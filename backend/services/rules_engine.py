import json
from pathlib import Path

from backend.core.errors import HairlyError
from backend.schemas.api import AnalyzeResponse, FlaggedIngredient


_SEED = json.loads((Path(__file__).parents[1] / "db" / "rules.json").read_text())
RULES: dict[str, dict[str, dict[str, str]]] = _SEED["concerns"]
KNOWN: set[str] = set(_SEED["known_ingredients"]).union(*RULES.values())

DISCLAIMER = "Informational only; not medical advice."
SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


def evaluate(
    ingredients: list[str], concern: str, product_name: str | None = None, is_hair: bool = True
) -> AnalyzeResponse:
    """Normalized ingredients in, verdict out. Worst severity wins; never `safe` on missing or unrecognized data."""
    concern = concern.strip().casefold()
    if concern not in RULES:
        raise HairlyError("INVALID_INPUT", f"Unknown concern. Choose one of: {', '.join(RULES)}.", 400)
    rules = RULES[concern]

    flagged = sorted(
        (FlaggedIngredient(name=name, **rules[name]) for name in ingredients if name in rules),
        key=lambda f: SEVERITY_RANK[f.severity],
    )
    unrecognized = [name for name in ingredients if name not in KNOWN]

    if not is_hair:
        verdict, summary = "unknown", "This doesn't look like a hair product, so we can't give a verdict."
    elif flagged:
        verdict = "avoid" if flagged[0].severity == "high" else "caution"
        names = ", ".join(f.name for f in flagged[:3]) + (" and more" if len(flagged) > 3 else "")
        summary = f"Contains {len(flagged)} ingredient(s) of concern for {concern}: {names}."
    elif not ingredients:
        verdict, summary = "unknown", "No ingredient list to check."
    elif unrecognized:
        verdict = "unknown"
        summary = f"No known {concern} concerns, but we couldn't recognize {len(unrecognized)} ingredient(s), so we can't call it safe."
    else:
        verdict, summary = "safe", f"No ingredients of concern for {concern} were found."

    return AnalyzeResponse(
        product_name=product_name,
        verdict=verdict,
        summary=summary,
        flagged_ingredients=flagged,
        all_ingredients=ingredients,
        unrecognized_ingredients=unrecognized,
        disclaimer=DISCLAIMER,
    )
