
import json
from agent.state import PharmaState


def final_response(state: PharmaState) -> dict:

    response = {
        "question": state.get("user_query"),
        "analysis_types": state.get("analysis_types", []),
        "validation_summary": state.get(
            "validation_summary", {}
        ),
        "inventory_findings": state.get(
            "inventory_findings", []
        ),
        "recommendations": state.get(
            "recommendations", []
        ),
        "error": state.get("error")
    }

    return {
        "final_answer": json.dumps(
            response,
            indent=2,
            default=str
        )
    }
