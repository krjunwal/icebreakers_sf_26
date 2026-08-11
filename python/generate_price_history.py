"""
Generate a synthetic weekly price-history time series for every matched
Abt<->Buy product pair, for the price-optimization / market-intelligence
Cortex agents and the Streamlit pricing dashboards to have something to
analyze.

WHY THIS EXISTS: the Abt-Buy benchmark dataset has no time-series pricing
data at all -- just a single point-in-time price per product (and even that
is missing on ~46-61% of rows). The hackathon brief calls for "Pricing
History Data" as an input, so this script fabricates a plausible one. Every
row this script produces is tagged is_synthetic=True all the way through the
pipeline (see sql/09_pricing/090_load_synthetic_price_history.sql) and
architecture.md has an explicit disclosure section -- this is demo data,
not a claim about real historical prices.

Method (deliberately simple -- no category modeling, no external
time-series library):
  1. Base price per pair: prefer the real Buy.csv price, else the real
     Abt.csv price, else bootstrap-sample from the pool of ~700 known real
     prices in the dataset.
  2. Two correlated-but-independent weekly series (one per retailer) for
     8-12 weeks ending today: each week, a small random-walk drift, plus a
     low-probability larger promo/undercut event.
  3. For a subset of pairs, bias one retailer to run consistently below the
     other for a stretch of weeks, so the undercutting narrative the
     price-optimization/market-intelligence agents are supposed to surface
     actually shows up in the data.

Runs entirely against the local CSVs in data/raw/ -- no Snowflake
dependency. Output: data/generated/price_history.csv, loaded into Snowflake
by sql/09_pricing/090_load_synthetic_price_history.sql.
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"
OUT_DIR = REPO_ROOT / "data" / "generated"
OUT_PATH = OUT_DIR / "price_history.csv"

MIN_WEEKS, MAX_WEEKS = 8, 12
WEEKLY_DRIFT_STD = 0.015          # routine week-to-week volatility
EVENT_PROB = 0.12                 # chance of a larger one-off move in a given week
EVENT_MAGNITUDE_RANGE = (0.04, 0.15)  # size of a promo/undercut event, as a fraction
UNDERCUT_STRETCH_PAIR_FRACTION = 0.30  # fraction of pairs given a sustained undercut stretch
MIN_PRICE = 1.00


def parse_price(raw):
    if not raw:
        return None
    cleaned = raw.replace("$", "").replace(",", "").strip()
    if not cleaned:
        return None
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def load_csv(path, encoding="ISO-8859-1"):
    with open(path, encoding=encoding, newline="") as f:
        return list(csv.DictReader(f))


def week_start_dates(num_weeks, end_date):
    return [end_date - timedelta(weeks=(num_weeks - 1 - i)) for i in range(num_weeks)]


def generate_series(base_price, num_weeks, rng, undercut_bias=None):
    """undercut_bias: None, or (start_week_idx, end_week_idx, multiplier) applied
    on top of the random walk to create a sustained cheaper/pricier stretch."""
    prices = []
    price = base_price
    for week_idx in range(num_weeks):
        drift = rng.gauss(0, WEEKLY_DRIFT_STD)
        price *= (1 + drift)
        if rng.random() < EVENT_PROB:
            magnitude = rng.uniform(*EVENT_MAGNITUDE_RANGE)
            direction = -1 if rng.random() < 0.7 else 1  # promos/undercuts more common than hikes
            price *= (1 + direction * magnitude)
        if undercut_bias is not None:
            start, end, multiplier = undercut_bias
            if start <= week_idx <= end:
                price *= multiplier
        price = max(MIN_PRICE, round(price, 2))
        prices.append(price)
    return prices


def main():
    random.seed()  # real entropy -- this is demo data regenerated per run, not a fixed fixture
    rng = random.Random()

    abt = {row["id"]: row for row in load_csv(RAW_DIR / "Abt.csv")}
    buy = {row["id"]: row for row in load_csv(RAW_DIR / "Buy.csv")}
    ground_truth = load_csv(RAW_DIR / "abt_buy_perfectMapping.csv", encoding="utf-8")

    known_prices = []
    for row in abt.values():
        p = parse_price(row.get("price"))
        if p:
            known_prices.append(p)
    for row in buy.values():
        p = parse_price(row.get("price"))
        if p:
            known_prices.append(p)

    print(f"{len(ground_truth)} ground-truth pairs, {len(known_prices)} known real prices to bootstrap from")

    today = date.today()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows_written = 0
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as out_f:
        writer = csv.writer(out_f)
        writer.writerow(["abt_id", "buy_id", "retailer", "week_start_date", "price", "is_synthetic"])

        for pair in ground_truth:
            abt_id, buy_id = pair["idAbt"], pair["idBuy"]
            abt_row, buy_row = abt.get(abt_id), buy.get(buy_id)
            if abt_row is None or buy_row is None:
                continue

            buy_price = parse_price(buy_row.get("price"))
            abt_price = parse_price(abt_row.get("price"))
            if buy_price:
                base_price = buy_price
            elif abt_price:
                base_price = abt_price
            else:
                base_price = rng.choice(known_prices)

            num_weeks = rng.randint(MIN_WEEKS, MAX_WEEKS)
            dates = week_start_dates(num_weeks, today)

            undercut_bias_abt = None
            undercut_bias_buy = None
            if rng.random() < UNDERCUT_STRETCH_PAIR_FRACTION:
                stretch_len = rng.randint(2, max(2, num_weeks // 2))
                start = rng.randint(0, num_weeks - stretch_len)
                end = start + stretch_len - 1
                multiplier = rng.uniform(0.85, 0.95)  # sustained undercut, not a single-week blip
                if rng.random() < 0.5:
                    undercut_bias_buy = (start, end, multiplier)
                else:
                    undercut_bias_abt = (start, end, multiplier)

            abt_series = generate_series(base_price, num_weeks, rng, undercut_bias_abt)
            buy_series = generate_series(base_price, num_weeks, rng, undercut_bias_buy)

            for d, price in zip(dates, abt_series):
                writer.writerow([abt_id, buy_id, "ABT", d.isoformat(), price, True])
                rows_written += 1
            for d, price in zip(dates, buy_series):
                writer.writerow([abt_id, buy_id, "BUY", d.isoformat(), price, True])
                rows_written += 1

    print(f"wrote {rows_written} rows to {OUT_PATH}")


if __name__ == "__main__":
    main()
