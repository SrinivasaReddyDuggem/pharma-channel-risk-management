
from agent.state import PharmaState


def combine_results(state: PharmaState) -> dict:
    findings = []

    # 1. Expiry analysis
    if "expiry" in state.get("analysis_types", []):
        results = state.get("expiry_risks", [])

        findings.append({
            "risk_type": "expiry",
            "total_records": len(results),
            "results": results
        })

    # 2. Shortage analysis
    if "shortage" in state.get("analysis_types", []):
        results = state.get("shortage_results", [])

        findings.append({
            "risk_type": "shortage",
            "total_records": len(results),
            "results": results
        })

    # 3. Oversupply analysis
    if "oversupply" in state.get("analysis_types", []):
        results = state.get("oversupply_risks", [])

        findings.append({
            "risk_type": "oversupply",
            "total_records": len(results),
            "results": results
        })

    # 4. Allocation analysis (NEW)
    if "allocation" in state.get("analysis_types", []):
        results = state.get("allocation_findings", [])

        findings.append({
            "risk_type": "allocation",
            "total_records": len(results),
            "results": results
        })

    return {
        "inventory_findings": findings
    }
