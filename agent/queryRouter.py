from agent.state import PharmaState

def query_router(state: PharmaState):

    routes = {
        "shortage": "shortage_risk",
        "expiry": "expiry_risk",
        "oversupply": "oversupply_risk",
        "claims": "claim_risk",
         "redistribution": "redistribution_risk",
  
    }

    selected = state.get("analysis_types", [])

    destinations = [
        routes[risk]
        for risk in selected
        if risk in routes
    ]

    return destinations or ["unsupported_analysis"]