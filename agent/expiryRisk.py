from datetime import date
from agent.state import PharmaState
from agent.tools import parse_date


def expiry_risk(state: PharmaState) -> dict:
    today = date.today()

    skus = {
        row["sku_code"]: row
        for row in state.get("skus", [])
    }

    results = []

    for stock in state.get("valid_expiry_stock", []):
        sku_code = stock["sku_code"]
        batch_no = stock["batch_no"]
        cnf_code = stock["cnf_code"]

        sku = skus.get(sku_code)
        expiry_date = parse_date(stock["expiry_date"])
        if not sku or expiry_date is None:
            continue

        days_to_expiry = (expiry_date - today).days

        if days_to_expiry < 0:
            risk_level = "expired"
        elif days_to_expiry <= 30:
            risk_level = "critical"
        elif days_to_expiry <= 90:
            risk_level = "high"
        elif days_to_expiry <= 180:
            risk_level = "monitor"
        else:
            risk_level = "low"

        quantity = int(stock["qty_on_hand_packs"])
        pts = float(sku["pts_inr"])

        results.append({
            "sku_code": sku_code,
            "batch_no": batch_no,
            "cnf_code": cnf_code,
            "expiry_date": expiry_date.isoformat(),
            "days_to_expiry": days_to_expiry,
            "current_stock": quantity,
            "risk_level": risk_level,
            "stock_value_pts": round(quantity * pts, 2),
            "product_description": sku.get("product_description", "")
        })

    return {"expiry_risks": results}