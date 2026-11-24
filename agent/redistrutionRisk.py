"""Project Sankalp: redistribution-friction exposure, not inventory allocation.

Uses load_data stock and (when available) previously validated stock records.
No movement orders are created; 14 days is a scenario assumption, not measured lead time.
Historical snapshots must be reconciled before action.
"""
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR

# Pilot scenario parameters. Move approved policy values into agent/rules.py.
REDISTRIBUTION_SCENARIO_DAYS = 14
DONOR_RESERVE_DAYS = 60
RECEIVER_TARGET_DAYS = 30
DAYS_PER_MONTH = 30
ZERO = Decimal(0)


def _code(value):
    return str(value).strip().upper() if value is not None else ""


def _number(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        n = Decimal(str(value).strip().replace(",", ""))
        return n if n.is_finite() else None
    except (ValueError, TypeError, InvalidOperation):
        return None


def _date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d-%b-%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            pass
    return None


def _floor(n):
    return int(n.to_integral_value(rounding=ROUND_FLOOR))


def _ceil(n):
    return int(n.to_integral_value(rounding=ROUND_CEILING))


def redistribution_risk(state: dict) -> dict:
    """Quantify historical stranded-inventory patterns, without suggesting transfers.

    Inputs: stock, batches, skus; optionally valid_shortage_stock and
    valid_oversupply_stock from existing validate_stock.
    Output: redistribution_results, redistribution_summary, redistribution_warnings.
    """
    raw = state.get("stock") or []
    warnings = [
        "No transfer request, dispatch, or receipt log was supplied: actual redistribution duration cannot be measured.",
        "14-day redistribution scenario and 30/60-day cover limits are pilot assumptions, not approved SLA or transfer policy.",
        "This is exposure screening, not an allocation plan or transfer authorization.",
    ]
    if not raw:
        return {"redistribution_results": [], "redistribution_summary": {"reason": "stock_missing"},
                "redistribution_warnings": warnings + ["No stock records loaded."]}

    dates = [d for r in raw if (d := _date(r.get("snapshot_date")))]
    if not dates:
        return {"redistribution_results": [], "redistribution_summary": {"reason": "no_valid_snapshot_dates"},
                "redistribution_warnings": warnings + ["No valid snapshot dates."]}
    snapshot = max(dates)
    warnings.append(f"Analyzed latest available historical snapshot: {snapshot.isoformat()}; reconfirm current stock before any decision.")

    # Use only current/latest snapshot. Incoming stock rows must be validated.
    latest = [r for r in raw if _date(r.get("snapshot_date")) == snapshot]
    master = defaultdict(list)
    for b in state.get("batches") or []:
        key = (_code(b.get("sku_code")), _code(b.get("batch_no")))
        if all(key):
            master[key].append(_date(b.get("expiry_date")))

    grouped = defaultdict(list)
    for r in latest:
        cnf, sku = _code(r.get("cnf_code")), _code(r.get("sku_code"))
        if cnf and sku:
            grouped[(cnf, sku)].append(r)

    # Existing validator already approved groups for either side; if its output
    # exists, respect it rather than weakening validation.
    validated_available = "valid_shortage_stock" in state or "valid_oversupply_stock" in state
    allowed_keys = None
    if validated_available:
        allowed_keys = set()
        for field in ("valid_shortage_stock", "valid_oversupply_stock"):
            for r in state.get(field) or []:
                if _date(r.get("snapshot_date")) == snapshot:
                    allowed_keys.add((_code(r.get("cnf_code")), _code(r.get("sku_code"))))

    positions = []
    rejected = 0
    rejected_unvalidated = 0
    for (cnf, sku), rows in grouped.items():
        if allowed_keys is not None and (cnf, sku) not in allowed_keys:
            rejected_unvalidated += 1
            continue
        demands = set()
        stock = 0
        seen_batches = set()
        valid = True
        for r in rows:
            qty = _number(r.get("qty_on_hand_packs"))
            monthly = _number(r.get("avg_monthly_outward_packs"))
            if (qty is None or monthly is None or qty < 0 or monthly < 0
                    or qty != qty.to_integral_value()):
                valid = False
                break
            demands.add(monthly)
            batch = _code(r.get("batch_no"))
            if qty == 0 and not batch:
                continue
            if not batch or batch in seen_batches:
                valid = False
                break
            seen_batches.add(batch)
            expiry = _date(r.get("expiry_date"))
            identity = master.get((sku, batch), [])
            if len(identity) != 1 or expiry is None or expiry != identity[0]:
                valid = False
                break
            if expiry <= snapshot:
                # Expired stock is not counted as usable inventory.
                continue
            stock += int(qty)
        if not valid or len(demands) != 1:
            rejected += 1
            continue
        monthly = next(iter(demands))
        daily = monthly / Decimal(DAYS_PER_MONTH)
        shortage = max(0, _ceil(daily * RECEIVER_TARGET_DAYS - stock))
        surplus = max(0, _floor(Decimal(stock) - daily * DONOR_RESERVE_DAYS))
        # This is an estimate of stock gap during the scenario window,
        # not confirmed lost sales or an approved movement volume.
        delay_gap = max(0, _ceil(daily * REDISTRIBUTION_SCENARIO_DAYS - stock))
        city = next((str(r.get("cnf_city") or "").strip() for r in rows if r.get("cnf_city")), "")
        positions.append({"cnf": cnf, "city": city, "sku": sku, "stock": stock,
                          "monthly": monthly, "shortage": shortage,
                          "surplus": surplus, "delay_gap": delay_gap})

    donors = defaultdict(list)
    for p in positions:
        if p["surplus"] > 0:
            donors[p["sku"]].append(p)

    prices = {}
    for r in state.get("skus") or []:
        pts = _number(r.get("pts_inr"))
        if pts is not None and pts >= ZERO:
            prices[_code(r.get("sku_code"))] = pts

    sku_filter = _code(state.get("sku_code"))
    cnf_filter = _code(state.get("cnf_code"))
    results = []
    for receiver in positions:
        if receiver["shortage"] <= 0:
            continue
        if sku_filter and receiver["sku"] != sku_filter:
            continue
        if cnf_filter and receiver["cnf"] != cnf_filter:
            continue
        other_sites = [d for d in donors[receiver["sku"]] if d["cnf"] != receiver["cnf"]]
        if not other_sites:
            continue
        pts = prices.get(receiver["sku"])
        # Surplus elsewhere indicates geographic imbalance. No quantity is allocated.
        results.append({
            "sku_code": receiver["sku"],
            "destination_cnf": receiver["cnf"],
            "destination_city": receiver["city"],
            "destination_on_hand_packs": receiver["stock"],
            "avg_monthly_outward_packs": float(receiver["monthly"]),
            "receiver_30_day_gap_packs": receiver["shortage"],
            "other_cnf_with_surplus": len(other_sites),
            "potential_source_locations": ", ".join(sorted(f'{d["cnf"]} ({d["city"]})' for d in other_sites)),
            "surplus_elsewhere_packs": sum(d["surplus"] for d in other_sites),
            "uncovered_demand_14_day_scenario_packs": receiver["delay_gap"],
            "uncovered_demand_value_pts_inr": (
                float(pts * receiver["delay_gap"]) if pts is not None else None
            ),
            "snapshot_date": snapshot.isoformat(),
            "status": "investigate_redistribution_bottleneck",
        })

    results.sort(key=lambda r: (-r["uncovered_demand_14_day_scenario_packs"],
                                -r["receiver_30_day_gap_packs"], r["sku_code"], r["destination_cnf"]))
    if rejected or rejected_unvalidated:
        warnings.append(f"Excluded {rejected} invalid groups and {rejected_unvalidated} groups not approved by stock validation.")
    if not results:
        warnings.append("No cross-location shortage/surplus overlap was found using the current screening rules.")
    summary = {
        "snapshot_date": snapshot.isoformat(),
        "scenario_days": REDISTRIBUTION_SCENARIO_DAYS,
        "receiver_target_days": RECEIVER_TARGET_DAYS,
        "donor_reserve_days": DONOR_RESERVE_DAYS,
        "screened_positions": len(positions),
        "impacted_receiver_locations": len(results),
        "affected_skus": len({r["sku_code"] for r in results}),
        "uncovered_demand_scenario_packs": sum(r["uncovered_demand_14_day_scenario_packs"] for r in results),
        "measured_transfer_turnaround_days": None,
        "excluded_invalid_groups": rejected,
        "excluded_unvalidated_groups": rejected_unvalidated,
    }
    return {"redistribution_results": results, "redistribution_summary": summary,
            "redistribution_warnings": warnings}
