
import csv
from pathlib import Path
from functools import lru_cache
from datetime import datetime

DATA = Path(__file__).resolve().parent.parent / "data"


# Step 1: Common CSV loader
@lru_cache(maxsize=7)
def load_csv(filename: str) -> list[dict]:
    with open(DATA / filename, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# Step 2: Individual file loaders
def load_skus() -> list[dict]:
    return load_csv("sku_master.csv")


def load_batches() -> list[dict]:
    return load_csv("batch_master.csv")


def load_cnf_stock() -> list[dict]:
    return load_csv("cnf_stock_snapshot.csv")


def load_primary_sales() -> list[dict]:
    return load_csv("primary_sales.csv")


def load_expiry_claims() -> list[dict]:
    return load_csv("expiry_claims.csv")


def load_stockists() -> list[dict]:
    return load_csv("stockist_master.csv")


def load_claim_emails() -> list[dict]:
    return load_csv("claim_emails.csv")


# Step 3: Handle multiple date formats
def parse_date(value: str):
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d-%b-%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue

    raise ValueError(f"Invalid date: {value}")


# Step 4: Get latest stock snapshot
def load_latest_cnf_stock() -> list[dict]:
    rows = load_cnf_stock()

    if not rows:
        return []

    latest_date = max(
        parse_date(r["snapshot_date"]) for r in rows
    )

    return [
        r for r in rows
        if parse_date(r["snapshot_date"]) == latest_date
    ]
