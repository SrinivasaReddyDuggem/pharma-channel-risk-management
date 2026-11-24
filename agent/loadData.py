
# Load stock

from agent.state import PharmaState
from agent.tools import load_batches, load_claim_emails, load_expiry_claims, load_latest_cnf_stock,load_primary_sales, load_skus, load_stockists

def load_data(pharmaState : PharmaState ) -> PharmaState:

 # Load stock
 pharmaState["stock"] = load_latest_cnf_stock()
 # Load claims
 pharmaState["claims"] = load_expiry_claims()
 # Load sales
 pharmaState["sales"] = load_primary_sales()
 # Load stockists
 pharmaState["stockists"] = load_stockists()

 pharmaState["skus"] = load_skus()
 pharmaState["batches"] = load_batches()
 pharmaState["claim_emails"] = load_claim_emails()

 return pharmaState


