"""Project Sankalp — expiry-claim validation and settlement monitoring.

Reads existing PharmaState fields supplied by load_data(): claims, sales,
batches, stockists, skus, claim_emails. Does not change inventory analysis.

Important: These are evidence checks, not final claim adjudication.
The monitoring threshold is a configurable pilot assumption, NOT an approved SLA.
"""

from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re
from typing import Any

EXPIRY_TYPES = {"EXPIRED", "NEAR EXPIRY"}
MONITOR_DELAY_DAYS = 45  # Pilot alert threshold only; confirm contractual SLA.
DUP_FIELDS = ("stockist_code", "sku_code", "batch_no", "qty_claimed", "original_invoice_ref", "claim_type")


def _code(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().upper()


def _number(value: Any) -> Decimal | None:
    if value is None or not str(value).strip():
        return None
    try:
        n = Decimal(str(value).replace(",", "").strip())
        return n if n.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value or not str(value).strip():
        return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d-%b-%Y", "%d-%B-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            pass
    return None


def _days(start: date | None, end: date | None) -> int | None:
    return (end - start).days if start and end else None


def _settlement_anchor(state: dict, claim_dates: list[date]) -> date:
    """Pick a stated as-of date; otherwise latest observed date in the dataset."""
    if state.get("analysis_date"):
        d = _date(state["analysis_date"])
        if d is None:
            raise ValueError("analysis_date must be a valid date")
        return d
    dates = list(claim_dates)
    dates.extend(filter(None, (_date(x.get("credit_note_date")) for x in state.get("claims", []) or [])))
    dates.extend(filter(None, (_date(x.get("received_date")) for x in state.get("claim_emails", []) or [])))
    if not dates:
        raise ValueError("Claims data has no usable reporting dates")
    return max(dates)


def expiry_claims_analysis(state: dict) -> dict:
    """LangGraph node: validate expiry claims and monitor settlement delays.

    Returns claim_results, claim_summary, claim_warnings, settlement_results.
    Every finding is informational and should be reviewed by claims operations.
    """
    claims = state.get("claims") or []
    sales = state.get("sales") or []
    batches = state.get("batches") or []
    stockists = state.get("stockists") or []
    emails = state.get("claim_emails") or []

    selected = [c for c in claims if _code(c.get("claim_type")) in EXPIRY_TYPES]
    if not selected:
        return {
            "claim_results": [], "settlement_results": [],
            "claim_warnings": ["No Expired or Near expiry claims were loaded."],
            "claim_summary": {"total_claim_rows": 0, "as_of_date": None},
        }

    dates = [_date(x.get("claim_date")) for x in selected]
    as_of = _settlement_anchor(state, [d for d in dates if d])
    threshold = state.get("claim_monitor_days", MONITOR_DELAY_DAYS)
    if type(threshold) is not int or threshold <= 0:
        raise ValueError("claim_monitor_days must be a positive integer")

    batch_index = defaultdict(list)
    for b in batches:
        batch_index[(_code(b.get("sku_code")), _code(b.get("batch_no")))].append(b)

    stockist_index = defaultdict(list)
    for s in stockists:
        stockist_index[_code(s.get("stockist_code"))].append(s)

    # One invoice can contain multiple line items; match the exact stockist/SKU/batch.
    invoices = defaultdict(list)
    for sale in sales:
        ref = _code(sale.get("invoice_no"))
        if ref:
            invoices[ref].append(sale)

    claim_id_counts = Counter(_code(c.get("claim_no")) for c in selected if _code(c.get("claim_no")))
    exact_counts = Counter(tuple(_code(c.get(k)) for k in DUP_FIELDS) for c in selected)

    # Follow-ups only when an actual claim identifier occurs in email text.
    email_refs = defaultdict(list)
    for email in emails:
        text = f"{email.get('subject') or ''} {email.get('body') or ''}"
        for ref in set(re.findall(r"CLM-\d{4}-\d+", text, flags=re.IGNORECASE)):
            email_refs[_code(ref)].append(_code(email.get("email_id")))

    results = []
    for row in selected:
        claim_no = _code(row.get("claim_no"))
        sku = _code(row.get("sku_code"))
        batch = _code(row.get("batch_no"))
        stockist = _code(row.get("stockist_code"))
        cnf = _code(row.get("cnf_code"))
        cdate = _date(row.get("claim_date"))
        bdate = _date(row.get("expiry_date_as_claimed"))
        credit_date = _date(row.get("credit_note_date"))
        amount = _number(row.get("claim_value_inr"))
        credit_amount = _number(row.get("credit_value_inr"))
        qty = _number(row.get("qty_claimed"))
        status = _code(row.get("status"))
        ref = _code(row.get("original_invoice_ref"))
        flags = []
        evidence = []

        if not claim_no:
            flags.append("missing_claim_number")
        if not cdate:
            flags.append("invalid_claim_date")
        elif cdate > as_of:
            flags.append("claim_after_reporting_date")
        if not qty or qty <= 0 or qty != qty.to_integral_value():
            flags.append("invalid_claim_quantity")
        if amount is None or amount < 0:
            flags.append("missing_or_invalid_claim_value")

        matched_batches = batch_index.get((sku, batch), [])
        if len(matched_batches) != 1:
            flags.append("batch_missing_or_ambiguous")
        else:
            master_expiry = _date(matched_batches[0].get("expiry_date"))
            if master_expiry is None or bdate is None:
                flags.append("missing_or_invalid_expiry_date")
            elif master_expiry != bdate:
                flags.append("claimed_expiry_mismatch")
            else:
                evidence.append("expiry_matches_batch_master")

        mappings = stockist_index.get(stockist, [])
        if len(mappings) != 1:
            flags.append("stockist_missing_or_ambiguous")
        elif _code(mappings[0].get("cnf_code")) != cnf:
            flags.append("cnf_differs_from_current_stockist_master")

        if not ref:
            flags.append("missing_invoice_reference")
        else:
            lines = invoices.get(ref, [])
            if not lines:
                flags.append("invoice_reference_not_found")
            else:
                matching = [line for line in lines if
                            _code(line.get("stockist_code")) == stockist and
                            _code(line.get("sku_code")) == sku and
                            _code(line.get("batch_no")) == batch]
                if not matching:
                    flags.append("invoice_stockist_sku_batch_mismatch")
                else:
                    evidence.append("matching_primary_invoice_line_found")
                    delivery_total = sum((_number(x.get("invoiced_qty")) or Decimal(0)) +
                                         (_number(x.get("free_qty")) or Decimal(0)) for x in matching)
                    if qty is not None and qty > delivery_total:
                        flags.append("claimed_quantity_exceeds_matched_invoice")

        if claim_id_counts[claim_no] > 1 and claim_no:
            flags.append("repeated_claim_number")
        if exact_counts[tuple(_code(row.get(k)) for k in DUP_FIELDS)] > 1:
            flags.append("possible_duplicate_claim")

        age = _days(cdate, as_of)
        elapsed = _days(cdate, credit_date) if credit_date else None
        if credit_date and cdate and credit_date < cdate:
            flags.append("credit_before_claim")
        if credit_date and credit_date > as_of:
            flags.append("credit_after_reporting_date")
        if status == "CREDITED":
            if not credit_date or not _code(row.get("credit_note_no")):
                flags.append("credited_without_complete_credit_note")
            if credit_amount is None:
                flags.append("missing_credit_value")
            if amount is not None and credit_amount is not None and credit_amount != amount:
                flags.append("credit_value_differs_from_claim")
            settlement_status = "credited_delayed" if elapsed is not None and elapsed > threshold else "credited"
            if elapsed is None:
                settlement_status = "credited_unverifiable"
        elif status == "PENDING":
            if credit_date or _code(row.get("credit_note_no")):
                flags.append("pending_with_credit_note")
            settlement_status = "pending_over_threshold" if age is not None and age > threshold else "pending"
        elif status == "REJECTED":
            settlement_status = "rejected"
        else:
            settlement_status = "unknown_status"
            flags.append("unrecognized_claim_status")

        results.append({
            "claim_no": claim_no, "claim_date": cdate.isoformat() if cdate else None,
            "claim_type": _code(row.get("claim_type")), "stockist_code": stockist,
            "cnf_code": cnf, "sku_code": sku, "batch_no": batch,
            "qty_claimed": int(qty) if qty is not None and qty == qty.to_integral_value() else None,
            "claim_value_inr": float(amount) if amount is not None else None,
            "status": status, "credit_note_no": _code(row.get("credit_note_no")) or None,
            "credit_note_date": credit_date.isoformat() if credit_date else None,
            "credit_value_inr": float(credit_amount) if credit_amount is not None else None,
            "settlement_days": elapsed, "age_days": age,
            "settlement_status": settlement_status, "monitor_threshold_days": threshold,
            "validation_flags": sorted(set(flags)), "evidence": evidence,
            "followup_email_ids": sorted(set(email_refs.get(claim_no, []))),
            "decision": "manual_review" if flags else "evidence_checks_passed_not_policy_approved",
        })

    status_count = Counter(x["settlement_status"] for x in results)
    flagged = sum(bool(x["validation_flags"]) for x in results)
    settlement = [x for x in results if x["settlement_status"] in ("credited_delayed", "pending_over_threshold", "credited_unverifiable")]
    settled_days = [x["settlement_days"] for x in results if x["status"] == "CREDITED" and x["settlement_days"] is not None and x["settlement_days"] >= 0]
    summary = {
        "as_of_date": as_of.isoformat(), "monitor_threshold_days": threshold,
        "total_claim_rows": len(results), "distinct_claim_numbers": len({x["claim_no"] for x in results if x["claim_no"]}),
        "flagged_rows": flagged, "pending_rows": sum(x["status"] == "PENDING" for x in results),
        "delayed_credited_rows": status_count["credited_delayed"],
        "pending_over_threshold_rows": status_count["pending_over_threshold"],
        "average_settlement_days": round(sum(settled_days) / len(settled_days), 1) if settled_days else None,
        "settlement_status_counts": dict(status_count),
    }
    return {
        "claim_results": results, "settlement_results": settlement,
        "claim_summary": summary,
        "claim_warnings": [
            "Only Expired and Near expiry claims are included; other claim types are excluded.",
            "The delay threshold is a pilot monitoring rule, not a verified contractual SLA.",
            "A matching invoice/batch is evidence only; claim eligibility and policy windows require approved policy rules.",
            "Repeated source rows are flagged, not automatically removed or rejected.",
            "Email links require an explicit claim number; unlinked emails must be reviewed separately.",
        ],
    }


# Alias if graph prefers this name.
claim_risk = expiry_claims_analysis
