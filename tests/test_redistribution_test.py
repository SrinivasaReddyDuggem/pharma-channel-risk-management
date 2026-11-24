"""Run: python -m pytest -q test_redistribution_risk.py"""
from datetime import date, timedelta
from redistributionRisk import redistribution_risk


def sample_state():
    now = date(2026, 9, 30)
    exp = date(2027, 12, 31)
    stock = [
        {"snapshot_date": now.isoformat(), "cnf_code": "CF-A", "cnf_city": "Alpha", "sku_code": "SKU1", "batch_no": "B1", "expiry_date": exp.isoformat(), "qty_on_hand_packs": "400", "avg_monthly_outward_packs": "30"},
        {"snapshot_date": now.isoformat(), "cnf_code": "CF-B", "cnf_city": "Beta", "sku_code": "SKU1", "batch_no": "", "expiry_date": "", "qty_on_hand_packs": "0", "avg_monthly_outward_packs": "60"},
    ]
    batches = [{"sku_code": "SKU1", "batch_no": "B1", "expiry_date": exp.isoformat()}]
    return {"stock": stock, "batches": batches, "skus": [{"sku_code": "SKU1", "pts_inr": "5"}]}


def test_surplus_elsewhere_produces_investigation_not_transfer():
    output = redistribution_risk(sample_state())
    assert output["redistribution_summary"]["impacted_receiver_locations"] == 1
    row = output["redistribution_results"][0]
    assert row["destination_cnf"] == "CF-B"
    assert "CF-A" in row["potential_source_locations"]
    assert row["uncovered_demand_14_day_scenario_packs"] == 28
    assert "suggested_qty" not in row
    assert output["redistribution_summary"]["measured_transfer_turnaround_days"] is None


def test_no_other_surplus_means_no_redistribution_candidate():
    s = sample_state()
    s["stock"] = s["stock"][1:]
    assert redistribution_risk(s)["redistribution_results"] == []


def test_expired_donor_is_not_usable():
    s = sample_state()
    s["stock"][0]["expiry_date"] = "2026-08-31"
    s["batches"][0]["expiry_date"] = "2026-08-31"
    assert redistribution_risk(s)["redistribution_results"] == []


def test_missing_data_returns_warnings_without_fabricating_delays():
    result = redistribution_risk({"stock": []})
    assert result["redistribution_results"] == []
    assert result["redistribution_summary"]["reason"] == "stock_missing"


def test_unvalidated_groups_excluded_when_validator_supplies_fields():
    s = sample_state()
    s["valid_shortage_stock"] = s["stock"][1:]
    s["valid_oversupply_stock"] = []
    result = redistribution_risk(s)
    assert result["redistribution_results"] == []
    assert result["redistribution_summary"]["excluded_unvalidated_groups"] == 1
