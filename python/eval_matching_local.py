"""
Fast local sanity check of the blocking + brand-matching design, run entirely
against the raw CSVs -- no Snowflake needed. This is the script referenced in
docs/architecture.md's "Results" section and docs/runbook.md step 9: it
simulates the exact logic in sql/02_prep/020_clean_price_and_brand_lookup.sql
and sql/03_blocking/030_candidate_pairs.sql in plain Python, so blocking
recall can be validated *before* spending any Snowflake AI budget.

If you change the blocking design in the SQL files, update this script to
match and re-run it -- the two should never diverge silently.

Measured result on the real dataset (see conversation / commit history):
100% recall (1097/1097 ground-truth pairs survive blocking), ~79K candidate
pairs out of ~1.18M possible.
"""

import csv
import re
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"

GENERIC_BRAND_WORDS = {
    "CASE", "TREE", "TOM", "PURE", "HILL", "MONSTER", "GAME", "DIGITAL",
    "SMITH", "SIRIUS", "SPECK", "UNIVERSAL", "SQUARE", "CHESTNUT",
}
STOPWORDS = {
    "THE", "AND", "FOR", "WITH", "INCH", "INCHES", "SERIES", "NEW", "BLACK",
    "WHITE", "SILVER", "SET", "KIT", "PACK", "OF", "TO", "IN", "ON", "A", "AN",
}
MIN_SHARED_TOKENS = 2


def load_csv(path, encoding="ISO-8859-1"):
    with open(path, encoding=encoding, newline="") as f:
        return list(csv.DictReader(f))


def clean_manufacturer(m):
    m = m.upper().strip()
    m = re.sub(r'\s*[,-]?\s*(INC\.?|LLC|CO\.?|CORP\.?|COMPANY|LTD\.?|GROUP)\s*$', '', m)
    m = re.sub(r'[.,]', '', m)
    return m.strip()


def word_boundary_match(haystack_upper, needle):
    if not needle:
        return False
    return re.search(r'\b' + re.escape(needle) + r'\b', haystack_upper) is not None


def tokenize(name):
    tokens = re.sub(r'[^A-Z0-9]+', ' ', name.upper()).split()
    return [t for t in tokens if len(t) >= 2 and t not in STOPWORDS]


def build_brand_lookup(buy_rows):
    manufacturers = sorted(set(r["manufacturer"].strip() for r in buy_rows if r["manufacturer"].strip()))
    lookup = []
    for raw in manufacturers:
        clean = clean_manufacturer(raw)
        if not clean:
            continue
        first_word = clean.split(' ')[0]
        lookup.append({
            "raw": raw,
            "clean": clean,
            "first_word": first_word,
            "first_word_is_generic": first_word in GENERIC_BRAND_WORDS,
        })
    return lookup


def abt_brand_matches(abt_rows, brand_lookup):
    """Many-to-many: every manufacturer whose brand text appears as a whole
    word in the Abt name, NOT a single 'best' winner (see 020's comments for
    why picking one winner silently drops true matches)."""
    matches = defaultdict(set)
    for row in abt_rows:
        name_upper = row["name"].upper()
        for b in brand_lookup:
            if word_boundary_match(name_upper, b["clean"]) or (
                not b["first_word_is_generic"] and word_boundary_match(name_upper, b["first_word"])
            ):
                matches[row["id"]].add(b["raw"])
    return matches


def token_overlap_candidates(abt_rows, buy_rows):
    abt_tokens = {r["id"]: set(tokenize(r["name"])) for r in abt_rows}
    buy_tokens = {r["id"]: set(tokenize(r["name"])) for r in buy_rows}
    buy_inverted = defaultdict(set)
    for buy_id, tokens in buy_tokens.items():
        for t in tokens:
            buy_inverted[t].add(buy_id)

    def matches_for(abt_id):
        counts = defaultdict(int)
        for t in abt_tokens[abt_id]:
            for buy_id in buy_inverted.get(t, ()):
                counts[buy_id] += 1
        return {buy_id for buy_id, c in counts.items() if c >= MIN_SHARED_TOKENS}

    return {r["id"]: matches_for(r["id"]) for r in abt_rows}


def main():
    abt_rows = load_csv(RAW_DIR / "Abt.csv")
    buy_rows = load_csv(RAW_DIR / "Buy.csv")
    ground_truth = load_csv(RAW_DIR / "abt_buy_perfectMapping.csv", encoding="utf-8")

    brand_lookup = build_brand_lookup(buy_rows)
    brand_matches = abt_brand_matches(abt_rows, brand_lookup)
    token_matches = token_overlap_candidates(abt_rows, buy_rows)

    buy_by_manufacturer = defaultdict(set)
    for row in buy_rows:
        m = row["manufacturer"].strip()
        if m:
            buy_by_manufacturer[m].add(row["id"])

    candidate_pairs = set()
    for row in abt_rows:
        abt_id = row["id"]
        buy_ids = set(token_matches.get(abt_id, ()))
        for manufacturer in brand_matches.get(abt_id, ()):
            buy_ids |= buy_by_manufacturer.get(manufacturer, set())
        for buy_id in buy_ids:
            candidate_pairs.add((abt_id, buy_id))

    print(f"abt={len(abt_rows)} buy={len(buy_rows)} ground_truth={len(ground_truth)}")
    print(f"candidate pairs: {len(candidate_pairs):,} (out of {len(abt_rows) * len(buy_rows):,} possible)")

    gt_pairs = [(r["idAbt"], r["idBuy"]) for r in ground_truth]
    hits = sum(1 for p in gt_pairs if p in candidate_pairs)
    print(f"blocking recall: {hits}/{len(gt_pairs)} = {hits / len(gt_pairs) * 100:.2f}%")

    misses = [p for p in gt_pairs if p not in candidate_pairs]
    if misses:
        abt_by_id = {r["id"]: r for r in abt_rows}
        buy_by_id = {r["id"]: r for r in buy_rows}
        print(f"\n{len(misses)} ground-truth pairs missed by blocking:")
        for abt_id, buy_id in misses:
            print(f"  ABT[{abt_id}]={abt_by_id[abt_id]['name']!r}  <->  BUY[{buy_id}]={buy_by_id[buy_id]['name']!r}")


if __name__ == "__main__":
    main()
