"""Create the tables, then replace the rules tables with rules.json + aliases.json.

Run after editing either file: python -m backend.db.seed (then restart the API to pick up the change).
"""

import json
from pathlib import Path

import psycopg

from backend.core.config import settings


DB = Path(__file__).parent


def main() -> None:
    seed = json.loads((DB / "rules.json").read_text())
    aliases: dict[str, str] = json.loads((DB / "aliases.json").read_text())
    rules: dict[str, dict[str, dict[str, str]]] = seed["concerns"]
    names = sorted(set(seed["known_ingredients"]).union(*rules.values(), aliases.values()))

    # One transaction: the API never sees half-loaded rules, and any error leaves the old rules in place.
    with psycopg.connect(settings.database_url, prepare_threshold=None) as conn, conn.cursor() as cur:
        cur.execute((DB / "schema.sql").read_text())
        # Wipe and reload so a rule deleted from the JSON is deleted here too.
        cur.execute("truncate concern_rules, ingredient_aliases, concerns, ingredients restart identity")
        cur.executemany("insert into ingredients (canonical_name) values (%s)", [(n,) for n in names])
        cur.executemany("insert into concerns (slug, label) values (%s, %s)", [(s, s.capitalize()) for s in rules])
        cur.executemany(
            "insert into concern_rules (concern_id, ingredient_id, severity, reason)"
            " select c.id, i.id, %s, %s from concerns c, ingredients i where c.slug = %s and i.canonical_name = %s",
            [(r["severity"], r["reason"], slug, name) for slug, rs in rules.items() for name, r in rs.items()],
        )
        cur.executemany(
            "insert into ingredient_aliases (alias, ingredient_id) select %s, id from ingredients where canonical_name = %s",
            list(aliases.items()),
        )
    print(f"Seeded {len(rules)} concern(s), {len(names)} ingredients, {len(aliases)} aliases.")


if __name__ == "__main__":
    main()
