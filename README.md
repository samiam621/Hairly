# Hairly

**Scan a hair product and find out whether its ingredients are a problem for you.**

Hairly checks hair products against a specific concern, such as *"Is this hair dye safe if I'm sensitive to dye allergens?"* You scan a product's barcode. Hairly looks up the ingredient list, cleans it up, and checks each ingredient against a curated rule set. It then returns a plain-language verdict: **safe**, **caution**, **avoid**, or **unknown**. It also tells you which ingredients were flagged and why.

> Informational only, not medical advice.

---

## How it works

```mermaid
flowchart LR
    A[Scan barcode] --> B{Product in cache?}
    B -->|Yes| D[Normalize ingredients]
    B -->|No| C[Open Beauty Facts] --> D
    D --> E[Match against rules<br/>for the chosen concern]
    E --> F[Verdict + flagged ingredients]
```

1. **Look up the product.** The backend checks a PostgreSQL cache first and only calls [Open Beauty Facts](https://world.openbeautyfacts.org/) on a miss. It also caches products that weren't found, for a shorter time, so repeated scans of an unknown barcode don't keep hitting the API.
2. **Normalize the ingredients.** Real ingredient lists are messy: mixed languages, percentages, odd separators, and synonyms. They get lowercased, cleaned, and mapped to canonical names. For example, `aqua` and `eau` both become `water`, and `PPD` becomes `p-phenylenediamine`.
3. **Apply the rules.** Each concern has a list of ingredients, and each one has a severity and a reason. The worst match decides the verdict. Hairly never says **safe** when some ingredients are missing or unrecognized. In those cases it says **unknown**.
4. **Improve the rules over time.** Ingredients the rules don't recognize are logged to a backlog table, which shows which rules to add next.

### Example

`POST /api/analyze/barcode` with `{"barcode": "3348070010589", "concern": "dye allergy"}` returns:

```json
{
  "product_name": "Henné poudre - Auburn",
  "verdict": "caution",
  "summary": "Contains 2 ingredient(s) of concern for dye allergy: sodium picramate, lawsonia inermis.",
  "flagged_ingredients": [
    { "name": "sodium picramate", "reason": "Skin sensitizer sometimes added to henna-based dyes.", "severity": "medium" },
    { "name": "lawsonia inermis", "reason": "Henna. Pure henna rarely causes allergy, but \"black henna\" may contain PPD.", "severity": "low" }
  ],
  "all_ingredients": ["lawsonia inermis", "sodium picramate", "water"],
  "unrecognized_ingredients": [],
  "disclaimer": "Informational only; not medical advice."
}
```

---

## Tech stack

| Layer | Tech |
|---|---|
| Backend | Python, FastAPI, Pydantic |
| Database | PostgreSQL (Supabase), psycopg with a connection pool |
| Product data | Open Beauty Facts API |
| Frontend | React + Vite (in progress) |
| AI (planned) | Google Gemini, to read ingredient-label photos and classify unrecognized ingredients |
| Testing | pytest, with 19 real product responses saved as fixtures |

## Engineering highlights

- **Rules first, AI second.** Verdicts come from a transparent rule set that is checked into the repo, not from an LLM. Gemini will only handle what the rules can't: reading label photos and classifying unrecognized ingredients.
- **Verdicts are not cached.** Only ingredient data is cached, so a rule change takes effect immediately without clearing the cache.
- **Safe under concurrency.** Cache writes use an upsert, so two people scanning the same barcode at the same time don't cause an error.
- **Fails safely.** If Open Beauty Facts times out, the result isn't cached as "not found", and an expired cache entry is served when a refresh fails. A non-hair product gets `unknown` with an explanation instead of a made-up verdict.
- **Rules are data.** The rules live in [`rules.json`](backend/db/rules.json) and [`aliases.json`](backend/db/aliases.json). A seed script loads them into the database in one transaction and loads them into memory at startup.

---

## Getting started

### Prerequisites
- Python 3.10+ (developed on 3.12)
- A PostgreSQL database. A free [Supabase](https://supabase.com/) project works; use its pooled connection string.

### Run the API

```bash
git clone https://github.com/samiam621/Hairly.git
cd Hairly
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the repo root:

```
DATABASE_URL=postgresql://user:password@host:6543/postgres
```

Create the tables and load the rules, then start the server:

```bash
python -m backend.db.seed
uvicorn backend.main:app --reload
```

The API runs at `http://localhost:8000`, and interactive docs are at `http://localhost:8000/docs`.

```bash
curl -X POST http://localhost:8000/api/analyze/barcode \
  -H "Content-Type: application/json" \
  -d '{"barcode": "3348070010589", "concern": "dye allergy"}'
```

### Run the tests

The tests use saved fixtures and in-memory fakes, so they don't need a database or network access. `DATABASE_URL` only has to be set; its value isn't used.

```bash
DATABASE_URL=postgresql://unused pytest
```

---

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/api/analyze/barcode` | `{ "barcode", "concern" }` → verdict |
| `POST` | `/api/analyze/label` | *(planned)* Ingredient-label photo + concern → verdict |

Errors share one shape:

```json
{ "error": { "code": "PRODUCT_NOT_FOUND", "message": "We don't have ingredients for this product. Try a photo of the label." } }
```

Error codes: `INVALID_INPUT`, `PRODUCT_NOT_FOUND`, `LABEL_UNREADABLE`, `AI_UNAVAILABLE`, `RATE_LIMITED`.

---

## Project structure

```
Hairly/
├── backend/
│   ├── main.py              # FastAPI app, startup, error handlers
│   ├── routers/analyze.py   # HTTP endpoints
│   ├── services/
│   │   ├── product_lookup.py  # cache-first lookup + Open Beauty Facts client
│   │   ├── normalize.py       # ingredient cleanup + alias mapping
│   │   └── rules_engine.py    # rule matching + verdict logic
│   ├── db/                  # schema.sql, rules.json, aliases.json, seed script
│   ├── schemas/             # Pydantic request/response models
│   └── core/                # config and error types
├── hairlyWeb/               # React frontend (Vite)
└── tests/                   # pytest suite + real product fixtures
```

## Roadmap

- [x] Barcode lookup, normalization, and rules engine
- [x] PostgreSQL product cache with TTLs and rules tables
- [ ] React frontend: concern picker, camera barcode scanner, result view
- [ ] Label-photo flow with Gemini vision
- [ ] Gemini fallback for unrecognized ingredients
- [x] Second concern: color-treated hair (alongside dye allergy)
- [ ] Deployment (Render + Supabase)
