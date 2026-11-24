from langgraph.graph import END, START, StateGraph

from agent.expiryRisk import expiry_risk
from agent.loadData import load_data
from agent.oversupplyRisk import oversupply_risk
from agent.queryRouter import query_router
from agent.state import PharmaState
from agent.shortageRisk import shortage_risk
from agent.understandQuery import understand_query
from agent.validateStock import validate_stock
from agent.combineResults import combine_results
from agent.recommendationAgent import recommendation_agent
from agent.finalResponse import final_response
from agent.financialImpact import calculate_financial_impact
from agent.claimsAnalysis import claim_risk


# ============================================
# 1. CREATE GRAPH
# ============================================

graph = StateGraph(PharmaState)

# ============================================
# 2. REGISTER NODES
# ============================================

graph.add_node("understand_query", understand_query)
graph.add_node("load_data", load_data)
graph.add_node("validate_stock", validate_stock)

graph.add_node("shortage_risk", shortage_risk)
graph.add_node("expiry_risk", expiry_risk)
graph.add_node("oversupply_risk", oversupply_risk)
graph.add_node("claim_risk", claim_risk)

graph.add_node(
    "unsupported_analysis",
    lambda _state: {
        "error": "Please select a supported inventory risk analysis."
    }
)

graph.add_node("combine_results", combine_results)
graph.add_node("financial_impact", calculate_financial_impact)
graph.add_node("recommendation_agent", recommendation_agent)
graph.add_node("final_response", final_response)

# ============================================
# 3. SEQUENTIAL FLOW
# ============================================

graph.add_edge(START, "understand_query")

graph.add_edge("understand_query", "load_data")

graph.add_edge("load_data", "validate_stock")

# ============================================
# 4. CONDITIONAL PARALLEL ANALYSIS
# ============================================

graph.add_conditional_edges(
    "validate_stock",
    query_router,
    {
        "shortage_risk": "shortage_risk",
        "expiry_risk": "expiry_risk",
        "oversupply_risk": "oversupply_risk",
        "claim_risk": "claim_risk",
        "unsupported_analysis": "unsupported_analysis"
    }
)

# ============================================
# 5. COMBINE ANALYSIS RESULTS
# ============================================

graph.add_edge("shortage_risk", "combine_results")
graph.add_edge("expiry_risk", "combine_results")
graph.add_edge("oversupply_risk", "combine_results")
graph.add_edge("claim_risk", "combine_results")
# ============================================
# 6. EXISTING DOWNSTREAM FLOW
# ============================================

graph.add_edge("combine_results", "financial_impact")

graph.add_edge("financial_impact", "recommendation_agent")

graph.add_edge("recommendation_agent", "final_response")

graph.add_edge("final_response", END)
graph.add_edge("unsupported_analysis", END)

# ============================================
# 7. COMPILE
# ============================================

workflow = graph.compile()

# Test with Streamlit-style selections
result = workflow.invoke({
    "user_query": "Analyze the inventory for potential expiry, oversupply ,shortage risks and claim risks.",
    "analysis_types": [
        "expiry",
        "oversupply",
        "shortage",
        "claim"
    ]
})



