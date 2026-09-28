from backend.core.errors import HairlyError
from backend.db.database import pool
from backend.schemas.api import AnalyzeResponse, FlaggedIngredient
from backend.services.normalize import ALIASES


# Filled once at startup by load_rules(). Updated in place, never reassigned, so every import sees the data.
RULES: dict[str, dict[str, dict[str, str]]] = {}  # concern slug -> ingredient -> {severity, reason}
KNOWN: set[str] = set()

DISCLAIMER = "Informational only; not medical advice."
SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


def validate_concern(concern: str) -> str:
    concern = concern.strip().casefold()
    if concern not in RULES:
        raise HairlyError("INVALID_INPUT", f"Unknown concern. Choose one of: {', '.join(RULES)}.", 400)
    return concern


def evaluate(
    ingredients: list[str], concern: str, product_name: str | None = None, is_hair: bool = True
) -> AnalyzeResponse:
    """Normalized ingredients in, verdict out. Worst severity wins; never `safe` on missing or unrecognized data."""
    concern = validate_concern(concern)
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


def load_rules() -> None:
    """Read concerns, rules, ingredients and aliases from the database into RULES, KNOWN and ALIASES."""
    with pool.connection() as conn:
        rules = {slug: {} for (slug,) in conn.execute("select slug from concerns")}
        if not rules:
            raise RuntimeError("The rules tables are empty. Run: python -m backend.db.seed")
        for slug, name, severity, reason in conn.execute(
            "select c.slug, i.canonical_name, r.severity, r.reason from concern_rules r"
            " join concerns c on c.id = r.concern_id join ingredients i on i.id = r.ingredient_id"
        ):
            rules[slug][name] = {"severity": severity, "reason": reason}
        known = {name for (name,) in conn.execute("select canonical_name from ingredients")}
        aliases = dict(conn.execute(
            "select a.alias, i.canonical_name from ingredient_aliases a join ingredients i on i.id = a.ingredient_id"
        ))
    RULES.clear()
    RULES.update(rules)
    KNOWN.clear()
    KNOWN.update(known)
    ALIASES.clear()
    ALIASES.update(aliases)


def record_unrecognized(names: list[str]) -> None:
    """Add names to the rule-curation backlog: new ones start at 1, repeats count up."""
    if not names:
        return
    with pool.connection() as conn:
        conn.execute(
            "insert into unrecognized_ingredients (name) select unnest(%s::text[])"
            " on conflict (name) do update set seen_count = unrecognized_ingredients.seen_count + 1",
            # Sorted so concurrent scans lock rows in the same order and can't deadlock each other.
            (sorted(names),),
        )
