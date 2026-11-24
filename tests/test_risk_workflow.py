import pytest

from agent.graph import app as pharma_graph
from agent.oversupplyRisk import oversupply_risk


@pytest.mark.parametrize(
    ("query", "result_key"),
    [
        ("Check for shortage risk", "shortage_results"),
        ("Check for expiry risk", "expiry_risks"),
        ("Check for oversupply risk", "oversupply_risks"),
    ],
)
def test_selected_risk_query_returns_its_table_rows(query, result_key):
    result = pharma_graph.invoke({"user_query": query})

    assert result["user_query"] == query
    assert result["analysis_type"] in {"shortage", "expiry", "oversupply"}
    assert result[result_key]


def test_oversupply_marks_stock_above_75_days_of_cover():
    result = oversupply_risk({
        "valid_oversupply_stock": [{
            "cnf_code": "CF-S02",
            "sku_code": "PFL1602",
            "qty_on_hand_packs": 4230,
            "avg_monthly_outward_packs": 1265,
        }],
        "skus": [{
            "sku_code": "PFL1602",
            "product_description": "Sertraline 50 mg tablets",
        }],
    })

    row = result["oversupply_risks"][0]
    assert row["days_of_cover"] == 100.32
    assert row["oversupply_risk"] == "HIGH"
