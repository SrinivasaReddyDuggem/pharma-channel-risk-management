
from collections import defaultdict
from agent.state import PharmaState


def shortage_risk(state: PharmaState) -> dict:
    # Step 1: Read data already loaded into state
    stock = state["valid_shortage_stock"]
    skus = state["skus"]

    # Step 2: Create SKU lookup
    sku_lookup = {
        row["sku_code"].strip().upper(): row
        for row in skus
    }

    # Step 3: Group stock by C&F and SKU
    grouped = defaultdict(list)

    for row in stock:
        cnf = row["cnf_code"].strip().upper()
        sku = row["sku_code"].strip().upper()
        grouped[(cnf, sku)].append(row)

    results = []
    data_issues = []

    # Step 4: Calculate shortage risk
    for (cnf, sku), rows in grouped.items():

        # Check for repeated batch records
        batch_numbers = [
            row["batch_no"].strip().upper()
            for row in rows
        ]

        if len(batch_numbers) != len(set(batch_numbers)):
            data_issues.append({
                "cnf_code": cnf,
                "sku_code": sku,
                "reason": "Duplicate batch records; review stock quantities"
            })
            continue

        # Sum available stock across unique batches
        available_stock = sum(
            row["qty_on_hand_packs"]
              for row in rows
            )

        # Monthly outward should not be added once per batch
        outward_values = {
            float(row["avg_monthly_outward_packs"])
            for row in rows
        }

        if len(outward_values) != 1:
            data_issues.append({
                "cnf_code": cnf,
                "sku_code": sku,
                "reason": "Inconsistent average monthly outward"
            })
            continue

        monthly_demand = outward_values.pop()
        daily_demand = monthly_demand / 30

        # Step 5: Calculate days of cover
        if daily_demand > 0:
            days_of_cover = available_stock / daily_demand
        else:
            days_of_cover = None

        # Step 6: Classify using preliminary thresholds
        if available_stock == 0 and daily_demand > 0:
            risk = "CRITICAL"
        elif days_of_cover is None:
            risk = "UNKNOWN"
        elif days_of_cover < 15:
            risk = "HIGH"
        elif days_of_cover < 30:
            risk = "MEDIUM"
        else:
            risk = "LOW"

        # Step 7: Get product description
        sku_details = sku_lookup.get(sku, {})

        # Step 8: Prepare result
        results.append({
            "cnf_code": cnf,
            "sku_code": sku,
            "product_description": sku_details.get(
                "product_description", ""
            ),
            "available_stock": available_stock,
            "avg_monthly_demand": monthly_demand,
            "avg_daily_demand": round(daily_demand, 2),
            "days_of_cover": (
                round(days_of_cover, 2)
                if days_of_cover is not None else None
            ),
            "shortage_risk": risk
        })

    # Step 9: Return only the state updates
    return {
        "shortage_results": results

    }

