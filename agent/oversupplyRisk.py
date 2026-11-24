from collections import defaultdict
from typing import Any

from agent.state import PharmaState


OVERSUPPLY_DAYS_THRESHOLD = 75


def oversupply_risk(state: PharmaState) -> dict[str, list[dict[str, Any]]]:
    grouped = defaultdict(list)
    for row in state.get("valid_oversupply_stock", []):
        grouped[(row["cnf_code"], row["sku_code"])].append(row)

    sku_lookup = {
        row["sku_code"]: row
        for row in state.get("skus", [])
    }

    results = []
    for (cnf_code, sku_code), rows in grouped.items():
        available_stock = sum(row["qty_on_hand_packs"] for row in rows)
        monthly_demand = float(rows[0]["avg_monthly_outward_packs"])
        daily_demand = monthly_demand / 30
        days_of_cover = (
            available_stock / daily_demand if daily_demand > 0 else None
        )
        risk = (
            "UNKNOWN" if days_of_cover is None
            else "HIGH" if days_of_cover > OVERSUPPLY_DAYS_THRESHOLD
            else "LOW"
        )

        results.append({
            "cnf_code": cnf_code,
            "sku_code": sku_code,
            "product_description": sku_lookup.get(
                sku_code, {}
            ).get("product_description", ""),
            "available_stock": available_stock,
            "avg_monthly_demand": monthly_demand,
            "avg_daily_demand": round(daily_demand, 2),
            "days_of_cover": (
                round(days_of_cover, 2) if days_of_cover is not None else None
            ),
            "oversupply_risk": risk,
        })

    return {"oversupply_risks": results}
