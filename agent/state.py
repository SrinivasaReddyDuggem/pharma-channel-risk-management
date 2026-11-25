from typing import Annotated, Any, Optional, TypedDict
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class PharmaState(TypedDict, total=False):

    # ========================================
    # 1. STREAMLIT INPUT / UNDERSTAND QUERY
    # ========================================

    user_query: str
    analysis_types: list[str]

    # Optional filters
    sku_code: Optional[str]
    batch_no: Optional[str]
    cnf_code: Optional[str]

    # ========================================
    # 2. LOAD DATA NODE
    # ========================================

    stock: list[dict]
    claims: list[dict]
    sales: list[dict]
    stockists: list[dict]
    skus: list[dict]
    batches: list[dict]
    claim_emails: list[dict]

    # ========================================
    # 3. VALIDATE STOCK NODE
    # ========================================

    valid_expiry_stock: list[dict]
    valid_shortage_stock: list[dict]
    valid_oversupply_stock: list[dict]

    invalid_stock: list[dict]
    validation_summary: dict

    # ========================================
    # 4. INVENTORY RISK NODES
    # ========================================

    # expiry_risk
    expiry_risks: list[dict[str, Any]]

    # shortage_risk
    shortage_results: list[dict[str, Any]]

    # oversupply_risk
    oversupply_risks: list[dict[str, Any]]

    # ========================================
    # 5. CLAIM RISK NODE
    # ========================================

    claim_results: list[dict]
    settlement_results: list[dict]
    claim_summary: dict
    claim_warnings: list[str]

    # Duplicate and invalid claims
    duplicate_invalid_claims: list[dict]

    # ========================================
    # 6. REDISTRIBUTION RISK NODE
    # ========================================

    redistribution_results: list[dict]
    redistribution_summary: dict
    redistribution_warnings: list[str]

    # ========================================
    # 7. DEMAND FORECAST RISK NODE
    # ========================================

    forecast_results: list[dict]
    forecast_summary: dict
    forecast_warnings: list[str]

    # ========================================
    # 8. COMBINE RESULTS NODE
    # ========================================

    inventory_findings: list[dict]

    # ========================================
    # 9. FINANCIAL IMPACT NODE
    # ========================================

    financial_impact: dict[str, Any]

    # ========================================
    # 10. RECOMMENDATION AGENT
    # ========================================

    recommendations: list

    # ========================================
    # 11. OPTIONAL LLM MESSAGE HISTORY
    # ========================================

    messages: Annotated[
        list[AnyMessage],
        add_messages
    ]

    # ========================================
    # 12. FINAL RESPONSE NODE
    # ========================================

    final_answer: str

    # ========================================
    # 13. WARNINGS AND ERRORS
    # ========================================

    data_warnings: list[str]
    error: str