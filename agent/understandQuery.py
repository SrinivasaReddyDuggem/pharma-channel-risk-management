from agent.state import PharmaState

def understand_query(state: PharmaState) -> dict:

    selected = state.get("analysis_types") or []

    allowed = {
        "shortage",
        "expiry",
        "oversupply"
    }

    return {
        "analysis_types": [
            risk
            for risk in dict.fromkeys(selected)
            if risk in allowed
        ]
    }