"""Project Sankalp: historical demand-proxy forecast backtesting.

Uses only `state['sales']` from the existing load_data node. Invoiced primary
sales are NOT secondary/customer demand or an official forecast. The output
backtests a three-prior-month moving-average baseline against completed months.
The node does not make or approve replenishment/allocation decisions.
"""
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

LOOKBACK_MONTHS = 3       # Pilot benchmark, not a business-approved forecasting policy
BACKTEST_MONTHS = 6       # Last six complete months with enough preceding history
HIGH_APE_PCT = Decimal("25")  # Pilot investigation threshold
CRITICAL_APE_PCT = Decimal("50")
ZERO = Decimal(0)


def _num(value):
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
    if value is None or str(value).strip() == "":
        return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d-%b-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _month_index(d):
    return d.year * 12 + d.month - 1


def _month_label(index):
    year, month0 = divmod(index, 12)
    return f"{year:04d}-{month0 + 1:02d}"


def _round_int(n):
    return int(n.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def demand_forecast_risk(state: dict) -> dict:
    """Return forecast-backtest rows, summary and data-quality warnings.

    Each result = (C&F, SKU, evaluated calendar month). Historical rolling
    predictions use only the three months before the evaluated month, which
    avoids look-ahead leakage. Empty internal months are treated as zero
    primary-invoice activity, not verified zero customer demand.
    """
    sales = state.get("sales") or []
    warnings = [
        "Primary invoices are a sales/shipment proxy, not secondary demand or actual customer orders.",
        "No saved official forecast or secondary-sales history was provided; accuracy is measured against a simple 3-month baseline, not the company's forecasting system.",
        "25%/50% SKU-month error thresholds are pilot investigation thresholds, not an approved KPI/SLA.",
        "Quarter-end and scheme-code correlations are context only; they do not prove causation.",
    ]
    if not sales:
        return {"forecast_results": [], "forecast_summary": {"reason": "primary_sales_missing"},
                "forecast_warnings": warnings + ["No primary sales records were loaded."]}

    totals = defaultdict(lambda: ZERO)
    scheme_totals = defaultdict(lambda: ZERO)
    observed_months = set()
    groups = set()
    skipped_dates = skipped_qty = skipped_keys = 0
    raw_latest = None
    for row in sales:
        d = _date(row.get("invoice_date"))
        if d is None:
            skipped_dates += 1
            continue
        month = _month_index(d)
        raw_latest = month if raw_latest is None else max(month, raw_latest)
        cnf = str(row.get("cnf_code") or "").strip().upper()
        sku = str(row.get("sku_code") or "").strip().upper()
        if not cnf or not sku:
            skipped_keys += 1
            continue
        qty = _num(row.get("invoiced_qty"))
        if qty is None or qty < ZERO or qty != qty.to_integral_value():
            skipped_qty += 1
            continue
        observed_months.add(month)
        groups.add((cnf, sku))
        key = (cnf, sku, month)
        totals[key] += qty
        if str(row.get("scheme_code") or "").strip():
            scheme_totals[key] += qty

    if not observed_months:
        return {"forecast_results": [], "forecast_summary": {"reason": "no_usable_primary_sales"},
                "forecast_warnings": warnings + ["No rows have valid dates, location, SKU and invoiced quantities."]}

    first = min(observed_months)
    last = max(observed_months)
    today = date.today()
    last_completed = _month_index(today) - 1
    if last > last_completed:
        last = last_completed
        warnings.append("Excluded the current or future calendar month to avoid evaluating incomplete months.")
    if raw_latest is not None and last < raw_latest:
        warnings.append("Latest available invoices include months beyond the backtest cutoff.")
    if last - first < LOOKBACK_MONTHS:
        return {"forecast_results": [],
                "forecast_summary": {"reason": "insufficient_history", "earliest_month": _month_label(first),
                                     "latest_complete_month": _month_label(last)},
                "forecast_warnings": warnings + ["At least four consecutive calendar months are needed for a 3-month baseline."]}

    missing_global_months = sorted(set(range(first, last + 1)) - observed_months)
    if missing_global_months:
        warnings.append(f"{len(missing_global_months)} months have no usable primary invoice lines; zeros may represent missing data, not true demand.")
    if skipped_dates or skipped_qty or skipped_keys:
        warnings.append(f"Excluded {skipped_dates} invalid-date, {skipped_qty} invalid-quantity and {skipped_keys} missing-C&F/SKU sales rows.")
    if last < _month_index(today) - 1:
        warnings.append(f"Latest completed invoicing month is {_month_label(last)}; this is a historical backtest, not a current forecast.")

    backtest_start = max(first + LOOKBACK_MONTHS, last - BACKTEST_MONTHS + 1)
    sku_filter = str(state.get("sku_code") or "").strip().upper()
    cnf_filter = str(state.get("cnf_code") or "").strip().upper()
    groups = sorted(g for g in groups if (not sku_filter or g[1] == sku_filter)
                    and (not cnf_filter or g[0] == cnf_filter))

    output = []
    abs_error_total = ZERO
    actual_total = ZERO
    signed_error_total = ZERO
    forecast_total = ZERO
    large_errors = 0
    scheme_rows = 0
    for month in range(backtest_start, last + 1):
        # Exclude an entire month if the dataset contains no invoices anywhere.
        if month not in observed_months:
            continue
        for cnf, sku in groups:
            history = [totals[(cnf, sku, m)] for m in range(month - LOOKBACK_MONTHS, month)]
            actual = totals[(cnf, sku, month)]
            # Do not fabricate a forecast for combinations with no activity in
            # history and in the month being evaluated.
            if not any(history) and actual == ZERO:
                continue
            estimate = sum(history, ZERO) / Decimal(LOOKBACK_MONTHS)
            error = estimate - actual
            absolute = abs(error)
            pct = absolute * 100 / actual if actual > ZERO else None
            if pct is None:
                severity = "HIGH" if estimate > ZERO else "LOW"
            elif pct >= CRITICAL_APE_PCT:
                severity = "CRITICAL"
            elif pct >= HIGH_APE_PCT:
                severity = "HIGH"
            else:
                severity = "LOW"
            if severity in ("HIGH", "CRITICAL"):
                large_errors += 1
            scheme_packs = scheme_totals[(cnf, sku, month)]
            scheme_share = (scheme_packs * 100 / actual) if actual > ZERO else ZERO
            if scheme_packs > ZERO:
                scheme_rows += 1
            output.append({
                "month": _month_label(month), "cnf_code": cnf, "sku_code": sku,
                "baseline_forecast_packs": _round_int(estimate),
                "actual_primary_invoiced_packs": int(actual),
                "forecast_error_packs": _round_int(error),
                "absolute_error_packs": _round_int(absolute),
                "absolute_percentage_error_pct": round(float(pct), 2) if pct is not None else None,
                "error_direction": "OVER_FORECAST" if error > ZERO else "UNDER_FORECAST" if error < ZERO else "ON_TARGET",
                "risk_level": severity,
                "quarter_end_month": (month % 12 + 1) in (3, 6, 9, 12),
                "scheme_invoiced_packs": int(scheme_packs),
                "scheme_share_of_primary_pct": round(float(scheme_share), 2),
                "history_months": LOOKBACK_MONTHS,
                "comparison_basis": "primary_invoice_proxy",
            })
            abs_error_total += absolute
            actual_total += actual
            signed_error_total += error
            forecast_total += estimate

    output.sort(key=lambda r: (r["month"], r["absolute_error_packs"]), reverse=True)
    wape = (abs_error_total / actual_total * 100) if actual_total else None
    bias = (signed_error_total / actual_total * 100) if actual_total else None
    summary = {
        "comparison_basis": "historical_primary_invoices_not_secondary_demand",
        "forecast_method": "simple_previous_3_calendar_month_average",
        "official_forecast_accuracy_available": False,
        "first_backtest_month": _month_label(backtest_start),
        "last_backtest_month": _month_label(last),
        "evaluated_cnf_sku_months": len(output),
        "evaluated_cnf_sku_pairs": len({(r["cnf_code"], r["sku_code"]) for r in output}),
        "wape_pct": round(float(wape), 2) if wape is not None else None,
        "bias_pct": round(float(bias), 2) if bias is not None else None,
        "large_error_rows": large_errors,
        "scheme_influenced_rows": scheme_rows,
        "total_actual_primary_packs": int(actual_total),
        "total_baseline_forecast_packs": _round_int(forecast_total),
        "invalid_date_rows": skipped_dates,
        "invalid_quantity_rows": skipped_qty,
        "missing_key_rows": skipped_keys,
    }
    if not output:
        warnings.append("No C&F/SKU backtest rows were eligible for the selected filters and months.")
    warnings.append("WAPE = sum(abs(baseline minus invoiced quantity)) / sum(invoiced quantity). Positive bias means baseline forecasts exceed primary invoicing.")
    return {"forecast_results": output, "forecast_summary": summary,
            "forecast_warnings": warnings}
