
import json
from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

from agent.state import PharmaState
from agent.llm import get_llm


class Recommendation(BaseModel):
    risk_type: Literal["expiry", "shortage", "oversupply"]
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    issue: str
    suggested_action: str
    business_benefit: str


class RecommendationOutput(BaseModel):
    recommendations: list[Recommendation] = Field(
        default_factory=list
    )


def recommendation_agent(state: PharmaState) -> dict:

    # Step 1: Read combined results
    findings = state.get("inventory_findings", [])

    if not findings:
        return {"recommendations": []}

    # Step 2: Configure structured LLM
    llm = get_llm().with_structured_output(
        RecommendationOutput
    )

    system_prompt = """
    You are a pharmaceutical inventory analysis assistant
    for Project Sankalp.

    Analyze the supplied inventory risk findings.

    Provide practical, evidence-based recommendations
    for expiry, shortage and oversupply risks.

    Rules:
    1. Use only facts present in the supplied findings.
    2. Never invent SKU codes, batch numbers, C&F codes,
       quantities, dates, prices or financial savings.
    3. Focus on actionable business recommendations.
    4. Prioritize urgent and high-risk findings.
    5. Recommend possible transfers only for further
       evaluation, not as approved stock movements.
    6. Do not recommend selling or transferring expired
       or otherwise ineligible inventory.
    7. If evidence is insufficient, identify the missing
       information instead of assuming it.
    8. Do not classify risk based on an invalid record.
    9. Return an empty recommendations list if no
       supported action can be identified.
    """

    # Step 3: Send findings to LLM
    result = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=json.dumps(
            findings,
            default=str
        ))
    ])

    # Step 4: Update LangGraph state
    return {
        "recommendations": [
            item.model_dump()
            for item in result.recommendations
        ]
    }
