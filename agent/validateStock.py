
from collections import defaultdict, Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation

from agent.state import PharmaState


SCENARIOS = ("expiry", "shortage", "oversupply")


def parse_number(value):
    """Convert '4,199.00' to Decimal('4199.00')."""
    try:
        number = Decimal(str(value).strip().replace(",", ""))
        return number if number.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def parse_date(value):
    """Support date formats used in Project Sankalp."""
    if not value:
        return None

    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d-%b-%Y"):
        try:
            return datetime.strptime(
                str(value).strip(), fmt
            ).date()
        except ValueError:
            continue

    return None


def clean_code(value):
    return str(value or "").strip().upper()


def validate_stock(state: PharmaState) -> dict:

    stock = state.get("stock", [])
    batches = state.get("batches", [])

    # Build batch master lookup
    batch_lookup = defaultdict(list)

    for batch in batches:
        batch_no = clean_code(batch.get("batch_no"))
        if batch_no:
            batch_lookup[batch_no].append(batch)

    # Keep validation information for every row
    checked = []
    groups = defaultdict(list)

    # STEP 1: Row-level validation
    for index, row in enumerate(stock):

        record = row.copy()

        cnf = clean_code(row.get("cnf_code"))
        sku = clean_code(row.get("sku_code"))
        batch_no = clean_code(row.get("batch_no"))

        qty = parse_number(row.get("qty_on_hand_packs"))
        demand = parse_number(
            row.get("avg_monthly_outward_packs")
        )

        snapshot_date = parse_date(
            row.get("snapshot_date")
        )

        expiry_date = parse_date(
            row.get("expiry_date")
        )

        # Separate errors for each scenario
        errors = {s: [] for s in SCENARIOS}

        def reject(message, scenarios=SCENARIOS):
            for scenario in scenarios:
                errors[scenario].append(message)

        # Common validations
        if not cnf:
            reject("Missing C&F code")

        if not sku:
            reject("Missing SKU code")

        if not batch_no:
            reject("Missing batch number")

        if snapshot_date is None:
            reject("Missing or invalid snapshot date")

        if qty is None:
            reject("Invalid stock quantity")
        elif qty < 0:
            reject("Negative stock quantity")
        elif qty != qty.to_integral_value():
            reject("Stock quantity must be whole packs")

        if demand is None:
            reject("Invalid average monthly outward")
        elif demand < 0:
            reject("Negative average monthly outward")

        # Expiry and oversupply need valid expiry
        if expiry_date is None:
            reject(
                "Missing or invalid expiry date",
                ("expiry", "oversupply")
            )

        # STEP 2: Batch master validation
        if batch_no:
            matches = batch_lookup.get(batch_no, [])

            if not matches:
                reject(
                    "Batch not found in batch master",
                    ("expiry", "oversupply")
                )

            elif len(matches) > 1:
                reject(
                    "Duplicate batch number in batch master",
                    ("expiry", "oversupply")
                )

            else:
                master = matches[0]

                master_sku = clean_code(
                    master.get("sku_code")
                )

                master_expiry = parse_date(
                    master.get("expiry_date")
                )

                if sku and master_sku != sku:
                    reject(
                        "SKU does not match batch master",
                        ("expiry", "oversupply")
                    )

                if master_expiry is None:
                    reject(
                        "Invalid expiry date in batch master",
                        ("expiry", "oversupply")
                    )

                elif expiry_date and expiry_date != master_expiry:
                    reject(
                        "Expiry date differs from batch master",
                        ("expiry", "oversupply")
                    )

        # STEP 3: Normalize valid numeric fields
        record["cnf_code"] = cnf
        record["sku_code"] = sku
        record["batch_no"] = batch_no

        if qty is not None and qty >= 0:
            if qty == qty.to_integral_value():
                record["qty_on_hand_packs"] = int(qty)

        if demand is not None and demand >= 0:
            record["avg_monthly_outward_packs"] = float(demand)

        item = {
            "record": record,
            "errors": errors,
            "qty": qty,
            "demand": demand
        }

        checked.append(item)

        # Group by C&F + SKU, not just batch
        if cnf and sku:
            groups[(cnf, sku)].append(item)

    # STEP 4: Group-level validation
    for (cnf, sku), entries in groups.items():

        # Duplicate batch records
        batch_counts = Counter(
            e["record"]["batch_no"]
            for e in entries
            if e["record"]["batch_no"]
        )

        if any(count > 1 for count in batch_counts.values()):
            for entry in entries:
                for scenario in SCENARIOS:
                    entry["errors"][scenario].append(
                        "Duplicate batch in C&F/SKU group"
                    )

        # Demand is C&F/SKU-level in this model
        demand_values = {
            e["demand"] for e in entries
            if e["demand"] is not None
        }

        if len(demand_values) > 1:
            for entry in entries:
                for scenario in SCENARIOS:
                    entry["errors"][scenario].append(
                        "Inconsistent monthly outward in C&F/SKU group"
                    )

        # Do not calculate stock cover using partial inventory
        for scenario in SCENARIOS:
            if any(e["errors"][scenario] for e in entries):
                for entry in entries:
                    if not entry["errors"][scenario]:
                        entry["errors"][scenario].append(
                            "Incomplete C&F/SKU group: "
                            "another row failed validation"
                        )

    # STEP 5: Split data for three scenarios
    valid_expiry = []
    valid_shortage = []
    valid_oversupply = []
    invalid_stock = []

    valid_sets = {
        "expiry": valid_expiry,
        "shortage": valid_shortage,
        "oversupply": valid_oversupply
    }

    for item in checked:
        record = item["record"]
        errors = item["errors"]

        for scenario in SCENARIOS:
            if not errors[scenario]:
                valid_sets[scenario].append(record.copy())

        invalid_for = [
            s for s in SCENARIOS if errors[s]
        ]

        if invalid_for:
            invalid_record = record.copy()
            invalid_record["invalid_for"] = invalid_for

            invalid_record["remark"] = " | ".join(
                f"{scenario}: {', '.join(dict.fromkeys(errors[scenario]))}"
                for scenario in invalid_for
            )

            invalid_stock.append(invalid_record)

    # STEP 6: Return state updates
    return {
        "valid_expiry_stock": valid_expiry,
        "valid_shortage_stock": valid_shortage,
        "valid_oversupply_stock": valid_oversupply,
        "invalid_stock": invalid_stock,
        "validation_summary": {
            "total_records": len(stock),
            "valid_expiry": len(valid_expiry),
            "valid_shortage": len(valid_shortage),
            "valid_oversupply": len(valid_oversupply),
            "records_with_errors": len(invalid_stock)
        }
    }
