
from agent.state import PharmaState


def combine_results(state: PharmaState) -> dict:

    findings = []

    selected = state.get("analysis_types") or []

    # 1. Expiry Risk
    if "expiry" in selected:
        results = state.get("expiry_risks") or []

        findings.append({
            "risk_type": "expiry",
            "total_records": len(results),
            "results": results
        })

    # 2. Shortage Risk
    if "shortage" in selected:
        results = state.get("shortage_results") or []

        findings.append({
            "risk_type": "shortage",
            "total_records": len(results),
            "results": results
        })

    # 3. Oversupply Risk
    if "oversupply" in selected:
        results = state.get("oversupply_risks") or []

        findings.append({
            "risk_type": "oversupply",
            "total_records": len(results),
            "results": results
        })

    # 4. Expiry Claims and Delayed Settlement
    if "claims" in selected:
        results = state.get("claim_results") or []

        findings.append({
            "risk_type": "claims",
            "total_records": len(results),
            "results": results
        })

    # 5. Slow Redistribution
    if "redistribution" in selected:
        results = state.get("redistribution_results") or []

        findings.append({
            "risk_type": "redistribution",
            "total_records": len(results),
            "results": results
        })

    # 6. Inaccurate Demand Forecasting
    if "forecast" in selected:
        results = state.get("forecast_results") or []

        findings.append({
            "risk_type": "forecast",
            "total_records": len(results),
            "results": results
        })

    return {
        "inventory_findings": findings
    }
