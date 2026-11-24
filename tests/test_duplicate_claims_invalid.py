"""pytest tests for agent.claimsAnalysis (copy to tests/ or project root)."""
from agent.claimsAnalysis import expiry_claims_analysis


def sample_state():
    return {
        'claims': [
            {'claim_no':'CLM-2609-00001','claim_date':'01-09-2026','stockist_code':'STK1',
             'cnf_code':'CF1','sku_code':'SKU1','batch_no':'B1','expiry_date_as_claimed':'30-09-2026',
             'qty_claimed':'10','claim_value_inr':'100.00','claim_type':'Near expiry',
             'original_invoice_ref':'INV1','status':'Pending','credit_note_date':None,
             'credit_note_no':None,'credit_value_inr':None},
            {'claim_no':'CLM-2609-00002','claim_date':'01-07-2026','stockist_code':'STK1',
             'cnf_code':'CF1','sku_code':'SKU1','batch_no':'B1','expiry_date_as_claimed':'30-09-2026',
             'qty_claimed':'2','claim_value_inr':'20.00','claim_type':'Expired',
             'original_invoice_ref':'INV1','status':'Credited','credit_note_date':'25-08-2026',
             'credit_note_no':'CN1','credit_value_inr':'20'},
        ],
        'batches':[{'sku_code':'SKU1','batch_no':'B1','expiry_date':'30-09-2026'}],
        'stockists':[{'stockist_code':'STK1','cnf_code':'CF1'}],
        'sales':[{'invoice_no':'INV1','stockist_code':'STK1','sku_code':'SKU1',
                  'batch_no':'B1','invoiced_qty':'10','free_qty':'3'}],
        'claim_emails':[],
        'analysis_date':'20-10-2026',
    }


def test_pending_and_delayed_credit():
    result=expiry_claims_analysis(sample_state())
    assert result['claim_summary']['total_claim_rows']==2
    assert result['claim_summary']['pending_over_threshold_rows']==1
    assert result['claim_summary']['delayed_credited_rows']==1
    assert result['claim_results'][0]['settlement_status']=='pending_over_threshold'
    assert result['claim_results'][1]['settlement_days']==55


def test_invoice_batch_mismatch_flagged():
    state=sample_state()
    state['claims'][0]['batch_no']='B2'
    result=expiry_claims_analysis(state)
    assert 'invoice_stockist_sku_batch_mismatch' in result['claim_results'][0]['validation_flags']


def test_repeated_claim_number_flagged():
    state=sample_state()
    state['claims'].append(dict(state['claims'][0]))
    result=expiry_claims_analysis(state)
    assert any('repeated_claim_number' in row['validation_flags'] for row in result['claim_results'])


def test_empty_claims():
    assert expiry_claims_analysis({'claims':[]})['claim_results']==[]


def test_review_report_flags_duplicate_and_invalid():
    state = sample_state()
    state["claims"].append(dict(state["claims"][0]))
    state["claims"][0]["qty_claimed"] = "999"
    result = expiry_claims_analysis(state)
    assert result["claim_summary"]["potential_duplicate_rows"] >= 2
    assert result["claim_summary"]["invalid_evidence_rows"] >= 1
    assert len(result["duplicate_invalid_claims"]) >= 2
    assert "duplicate_flags" in result["duplicate_invalid_claims"][0]

def test_review_report_empty():
    result = expiry_claims_analysis({"claims": []})
    assert result["duplicate_invalid_claims"] == []
