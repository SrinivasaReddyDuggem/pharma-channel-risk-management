from typing import Annotated, Any, Optional, TypedDict
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class PharmaState(TypedDict, total=False):

    # 1. USER REQUEST
    user_query: str
    analysis_types: list[str]

    # 2. DATA LOADED FROM CSV
    stock: list
    claims: list
    sales: list
    stockists: list
    skus: list
    batches: list
    claim_emails: list

    # Validation outputs
    valid_expiry_stock: list[dict]
    valid_shortage_stock: list[dict]
    valid_oversupply_stock: list[dict]
    invalid_stock: list[dict]
    validation_summary: dict


    sku_code: Optional[str]
    batch_no: Optional[str]
    cnf_code: Optional[str]


    # 3. PARALLEL ANALYSIS
    expiry_risks: list[dict[str, Any]]
    shortage_results: list[dict[str, Any]]
    oversupply_risks: list[dict[str, Any]]


      # - Valid records for allocation analysis
    valid_allocation_stock: list[dict]


    # New allocation analysis results
    allocation_findings: list[dict]
    allocation_warnings: list[str]
    allocation_diagnostics: dict

    # Data quality / missing data
    data_warnings: list[str]

    # 4. COMBINED RESULTS
    inventory_findings: list

    financial_impact: dict[str, Any]

    # 5. LLM RECOMMENDATIONS
    recommendations: list

    # 6. OPTIONAL LLM MESSAGE HISTORY
    messages: Annotated[list[AnyMessage], add_messages]

    # 7. FINAL RESPONSE
    final_answer: str
    recommendations: list
    
    # Expiry claims and settlement analysis
    claim_results: list[dict]
    settlement_results: list[dict]
    claim_summary: dict
    claim_warnings: list[str]
    # 8. Duplicate and invalid claims analysis
    duplicate_invalid_claims: list[dict]

    #Slow redistribution between locations
    redistribution_results: list[dict]
    redistribution_summary: dict
    redistribution_warnings: list[str]
    
    # Forecosted demand and supply analysis
    forecast_results: list[dict]
    forecast_summary: dict
    forecast_warnings: list[str]


    # 9. Error handling
    error: str