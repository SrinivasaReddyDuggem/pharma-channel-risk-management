
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from agent.state import PharmaState

EXPIRY_WINDOW_DAYS = 90
SHORTAGE_COVER_DAYS = 30
OVERSUPPLY_COVER_DAYS = 90

def number(value):
    return Decimal(str(value).replace(",", "").strip())

def parse_date(value):
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(str(value), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Invalid date: {value}")

def group_stock(rows):
    """Group inventory by C&F and SKU."""
    grouped = defaultdict(list)

    for row in rows:
        key = (
            row["cnf_code"].strip().upper(),
            row["sku_code"].strip().upper()
        )
        grouped[key].append(row)

    return grouped

def calculate_financial_impact(state: PharmaState) -> dict:

    selected = state.get("analysis_types", [])

    # SKU prices from project source data
    prices = {}

    for row in state.get("skus", []):
        code = row["sku_code"].strip().upper()
        prices[code] = number(row["pts_inr"])

    impact = {}
    missing_prices = set()

    # 1. EXPIRY FINANCIAL EXPOSURE
    if "expiry" in selected:
        expiry_value = Decimal("0")

        for row in state.get("valid_expiry_stock", []):
            sku = row["sku_code"].strip().upper()

            if sku not in prices:
                missing_prices.add(sku)
                continue

            snapshot = parse_date(row["snapshot_date"])
            expiry = parse_date(row["expiry_date"])

            days_left = (expiry - snapshot).days

            if 0 <= days_left <= EXPIRY_WINDOW_DAYS:
                qty = number(row["qty_on_hand_packs"])
                expiry_value += qty * prices[sku]

        impact["expiry"] = {
            "exposure_inr": float(expiry_value),
            "description": "Near-expiry stock value at PTS"
        }

    # 2. SHORTAGE FINANCIAL EXPOSURE
    if "shortage" in selected:
        shortage_value = Decimal("0")

        groups = group_stock(
            state.get("valid_shortage_stock", [])
        )

        for (cnf, sku), rows in groups.items():
            if sku not in prices:
                missing_prices.add(sku)
                continue

            available = sum(
                number(r["qty_on_hand_packs"])
                for r in rows
            )

            # Demand is repeated at C&F/SKU level
            monthly = number(
                rows[0]["avg_monthly_outward_packs"]
            )

            daily = monthly / Decimal("30")

            required = daily * SHORTAGE_COVER_DAYS
            shortfall = max(
                Decimal("0"), required - available
            )

            shortage_value += shortfall * prices[sku]

        impact["shortage"] = {
            "exposure_inr": float(shortage_value),
            "description": "Potential sales value at risk (PTS)"
        }

    # 3. OVERSUPPLY FINANCIAL EXPOSURE
    if "oversupply" in selected:
        excess_value = Decimal("0")

        groups = group_stock(
            state.get("valid_oversupply_stock", [])
        )

        for (cnf, sku), rows in groups.items():
            if sku not in prices:
                missing_prices.add(sku)
                continue

            available = sum(
                number(r["qty_on_hand_packs"])
                for r in rows
            )

            monthly = number(
                rows[0]["avg_monthly_outward_packs"]
            )

            daily = monthly / Decimal("30")

            target_stock = (
                daily * OVERSUPPLY_COVER_DAYS
            )

            excess = max(
                Decimal("0"), available - target_stock
            )

            excess_value += excess * prices[sku]

        impact["oversupply"] = {
            "exposure_inr": float(excess_value),
            "description": "Excess inventory value at PTS"
        }

    return {
        "financial_impact": {
            "by_risk": impact,
            "missing_price_skus": sorted(missing_prices),
            "valuation_basis": "SKU master PTS (INR)"
        }
    }