import json
import re
import unicodedata
from pathlib import Path


ALIASES: dict[str, str] = json.loads((Path(__file__).parents[1] / "db" / "aliases.json").read_text())

SEPARATOR = re.compile(r"[,;•،](?![^()]*\))")  # , ; • and Arabic comma, not inside (...)
CI_CODE = re.compile(r"\bc\s*\.?\s*i\s*\.?\s*-?\s*(\d{5})\b")
PERCENT = re.compile(r"\d+(?:[.,]\d+)?\s*%")
PARENS = re.compile(r"(?<![\w-])\(([^()]*)\)")  # "Parfum (Fragrance)", not "Bis(2-Hydroxyethyl)"


def normalize(raw: str, aliases: dict[str, str] = ALIASES) -> list[str]:
    """Raw ingredient text in, deduplicated canonical ingredient names out (label order kept)."""
    text = "".join(c for c in unicodedata.normalize("NFKD", raw) if not unicodedata.combining(c))
    text = re.sub(r"[‐-―−]", "-", text)
    names = []
    for line in text.splitlines():
        items = _split(line)
        if len(items) > 1:
            items = _split(re.sub(r"(?<=[a-z]) - (?=[a-z])", "", line))  # "Hy - droxy" line-wrap hyphenation
            items[0] = items[0].rsplit(" - ", 1)[-1]  # "1126261 - CREME COLORANTE - AQUA" section header
        else:
            items = line.split(" - ")  # some brands separate with dashes only
        for item in items:
            name = _canonical(item.rsplit(":", 1)[-1], aliases)  # "Colorant: Water" section header
            if any(c.isalpha() for c in name):
                names.append(name)
    return list(dict.fromkeys(names))


def _split(line: str) -> list[str]:
    parts, start = [], 0
    for m in SEPARATOR.finditer(line):
        if not _inside_name(line, m.start()):
            parts.append(line[start : m.start()])
            start = m.end()
    return parts + [line[start:]]


def _inside_name(line: str, i: int) -> bool:
    """Commas that belong to a name: "toluene-2,5-diamine", "N,N-bis"."""
    before, after = line[i - 1 : i], line[i + 1 : i + 2]
    if before.isdigit() and after.isdigit():
        return True
    return before.isalpha() and after.isalpha() and not line[max(i - 2, 0) : i - 1].isalpha() and not line[i + 2 : i + 3].isalpha()


def _canonical(item: str, aliases: dict[str, str]) -> str:
    """Pick the best name out of "Aqua/Water", "Parfum (Fragrance)", "Yellow 5 (CI 19140)"."""
    outer = PARENS.sub(" ", item)
    inner = [part for group in PARENS.findall(item) for part in re.split(r"[,/]", group)]
    alternates = outer.split("/")
    if len(alternates) == 2 and _is_alternate(*alternates):
        outer = alternates[0]
    candidates = [_clean(c) for c in [outer, *alternates, *inner]]
    for c in candidates:
        if CI_CODE.fullmatch(c):
            return c
    for c in candidates:
        if c in aliases:
            return aliases[c]
    return candidates[0]


def _is_alternate(left: str, right: str) -> bool:
    """"Seed Oil / Sunflower Seed Oil" is two names for one ingredient; "Caprylyl/Capryl Glucoside" is one name."""
    if left.endswith(" ") and right.startswith(" "):
        return True
    left, right = left.split(), right.split()
    return len(left) > 1 and len(right) > 1 and left[-1].casefold() == right[-1].casefold()


def _clean(name: str) -> str:
    name = CI_CODE.sub(r"ci \1", name.casefold())
    name = PERCENT.sub(" ", name)
    name = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", name)  # "no.1" -> "no 1", keeps "0.5"
    name = re.sub(r"[^\w\s,/&+.()-]", " ", name)
    if name.count("(") != name.count(")"):
        name = re.sub(r"[()]", " ", name)
    name = re.sub(r"\s*-\s*", "-", name)
    return re.sub(r"\s+", " ", name).strip(" -,/")
