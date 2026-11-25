
import json
from typing import Literal

from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

from agent.state import PharmaState
from agent.llm import get_llm


# ============================================
# 1. STRUCTURED RECOMMENDATION OUTPUT
# ============================================

class Recommendation(BaseModel):

    risk_type: Literal[
        "expiry",
        "shortage",
        "oversupply",
        "claims",
        "redistribution",
        "forecast"
    ]

    priority: Literal["HIGH", "MEDIUM", "LOW"]

    issue: str
    suggested_action: str
    business_benefit: str


class RecommendationOutput(BaseModel):

    recommendations: list[Recommendation] = Field(
        default_factory=list
    )


# ============================================
# 2. BUILD SMALL LLM INPUT
# ============================================

# Fields that can help the LLM understand
# specific findings without receiving entire datasets.
IMPORTANT_FIELDS = {
    "risk_level",
    "risk",
    "sku_code",
    "batch_no",
    "cnf_code",
    "stockist_code",
    "claim_id",
    "status",
    "issue",
    "reason",
    "days_to_expiry",
    "shortage_packs",
    "excess_packs",
    "claim_amount",
    "settlement_days",
    "source_cnf",
    "destination_cnf",
}


def compact_record(record):
    """Keep only a small number of useful fields."""

    if not isinstance(record, dict):
        return {}

    return {
        key: str(value)[:100]
        for key, value in record.items()
        if key in IMPORTANT_FIELDS
        and value is not None
    }


def build_recommendation_context(state: PharmaState):

    selected = state.get("analysis_types") or []

    # Each selected analysis supplies a different result list.
    analysis_fields = {
        "expiry": "expiry_risks",
        "shortage": "shortage_results",
        "oversupply": "oversupply_risks",
        "claims": "claim_results",
        "redistribution": "redistribution_results",
        "forecast": "forecast_results",
    }

    context = {
        "analyses": {},
        "financial_impact": {},
    }

    for risk in selected:

        field = analysis_fields.get(risk)

        if field is None:
            continue

        records = state.get(field) or []

        context["analyses"][risk] = {
            "total_records": len(records),
            "sample_findings": [
                compact_record(record)
                for record in records[:3]
            ]
        }

    # Financial impact is already calculated by Python.
    # Include only the three established risk totals.
    financial = state.get("financial_impact") or {}
    by_risk = financial.get("by_risk") or {}

    for risk in ("expiry", "shortage", "oversupply"):

        details = by_risk.get(risk)

        if isinstance(details, dict):
            context["financial_impact"][risk] = {
                "exposure_inr": details.get("exposure_inr")
            }

    # Add compact claim and forecast summaries.
    for risk, summary_field in (
        ("claims", "claim_summary"),
        ("redistribution", "redistribution_summary"),
        ("forecast", "forecast_summary"),
    ):

        if risk not in selected:
            continue

        summary = state.get(summary_field) or {}

        if isinstance(summary, dict):
            context["analyses"][risk]["summary"] = {
                str(key)[:60]: str(value)[:150]
                for key, value in list(summary.items())[:12]
            }

    # Limit the final input even if source values are large.
    text = json.dumps(
        context,
        default=str,
        ensure_ascii=False
    )

    if len(text) > 14000:
        # Keep the valid JSON structure by dropping examples.
        for item in context["analyses"].values():
            item["sample_findings"] = []

        text = json.dumps(
            context,
            default=str,
            ensure_ascii=False
        )

    if len(text) > 14000:
        # Keep only counts and known financial totals.
        for item in context["analyses"].values():
            item.pop("summary", None)

        text = json.dumps(
            context,
            default=str,
            ensure_ascii=False
        )

    return text


# ============================================
# 3. RECOMMENDATION AGENT
# ============================================

def recommendation_agent(state: PharmaState) -> dict:

    selected = state.get("analysis_types") or []

    supported = {
        "expiry",
        "shortage",
        "oversupply",
        "claims",
        "redistribution",
        "forecast",
    }

    if not any(risk in supported for risk in selected):
        return {"recommendations": []}

    # Step 1: Prepare small evidence summary
    context = build_recommendation_context(state)

    print(
        "Recommendation LLM input characters:",
        len(context)
    )

    # Step 2: Configure your existing LLM
    llm = get_llm().with_structured_output(
        RecommendationOutput
    )

    system_prompt = """
    You are a pharmaceutical inventory analysis assistant
    for Project Sankalp.

    Provide practical, evidence-based recommendations
    for the selected business risks.

    Supported risks:
    expiry, shortage, oversupply, claims,
    redistribution and forecast.

    Rules:
    1. Use only facts in the supplied context.
    2. Never invent SKU codes, batch numbers, C&F codes,
       claim IDs, quantities, dates, prices or savings.
    3. Focus on actionable business recommendations.
    4. Prioritize urgent and high-risk findings.
    5. Recommend possible stock transfers only for
       investigation, not as approved movements.
    6. Never recommend transferring expired inventory.
    7. Treat potential duplicate claims as review flags,
       not confirmed fraud.
    8. Do not present estimated forecast errors as
       official company forecast errors.
    9. Distinguish estimated exposure from actual losses.
    10. If evidence is missing, identify what is needed.
    11. The sample records are examples, not a complete
        ranking of all risks.
    12. Provide at most two recommendations per
        selected analysis.
    13. Return an empty list if no supported action
        can be identified.
    """

    # Step 3: Call LLM with compact evidence
    result = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=context)
    ])

    # Step 4: Update existing PharmaState
    return {
        "recommendations": [
            item.model_dump()
            for item in result.recommendations
        ]
    }
