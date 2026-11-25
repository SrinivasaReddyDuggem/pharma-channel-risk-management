
import json
import pandas as pd
import streamlit as st

from agent.graph import workflow

# ============================================================
# 1. PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Project Sankalp | Risk Intelligence",
    page_icon="💊",
    layout="wide"
)

# ============================================================
# 2. RISK CONFIGURATION
# ============================================================

RISK_OPTIONS = {
    "Shortage": "shortage",
    "Expiry": "expiry",
    "Oversupply": "oversupply",
    "Expiry Claims & Settlement": "claims",
    "Redistribution Delay": "redistribution",
    "Demand Forecast Accuracy": "forecast"
}

RESULT_KEYS = {
    "shortage": "shortage_results",
    "expiry": "expiry_risks",
    "oversupply": "oversupply_risks",
    "claims": "claim_results",
    "redistribution": "redistribution_results",
    "forecast": "forecast_results"
}

VALIDATION_KEYS = {
    "shortage": "valid_shortage",
    "expiry": "valid_expiry",
    "oversupply": "valid_oversupply"
}

RISK_COLUMNS = {
    "shortage": [
        "shortage_risk", "risk_level", "risk"
    ],
    "expiry": [
        "expiry_risk", "risk_level", "risk"
    ],
    "oversupply": [
        "oversupply_risk", "risk_level", "risk"
    ],
    "claims": [],
    "redistribution": [],
    "forecast": ["risk_level"]
}

RISK_COLORS = {
    "CRITICAL": "#FCA5A5",
    "HIGH": "#FCD34D",
    "MEDIUM": "#FDE68A",
    "LOW": "#86EFAC",
    "UNKNOWN": "#D1D5DB"
}

# ============================================================
# 3. HELPER FUNCTIONS
# ============================================================

def clean_table(records):
    """Convert graph results into a displayable DataFrame."""

    if isinstance(records, dict):
        records = [records]

    df = pd.DataFrame(records)

    for column in df.columns:
        df[column] = df[column].map(
            lambda value: json.dumps(
                value, default=str
            )
            if isinstance(value, (dict, list, set))
            else value
        )

    return df

def find_risk_column(df, risk):
    """Locate a risk-level column if one exists."""

    for column in RISK_COLUMNS.get(risk, []):
        if column in df.columns:
            return column

    return None

def risk_color(value):
    """Return background styling for risk severity."""

    level = str(value).strip().upper()

    color = RISK_COLORS.get(
        level, "#D1D5DB"
    )

    return (
        f"background-color: {color}; "
        "color: #111827;"
    )

def format_inr(value):
    """Format numbers in Indian Rupees."""

    try:
        value = float(value or 0)
    except (TypeError, ValueError):
        return "N/A"

    if value >= 10_000_000:
        return f"₹{value / 10_000_000:,.2f} Cr"

    if value >= 100_000:
        return f"₹{value / 100_000:,.2f} L"

    return f"₹{value:,.2f}"

# ============================================================
# 4. EXECUTE LANGGRAPH
# ============================================================

def run_analysis(selected_risks):

    question = (
        "Check " + ", ".join(selected_risks)
        + " inventory risks"
    )

    return workflow.invoke({
        "user_query": question,
        "analysis_types": selected_risks
    })

# ============================================================
# 5. DISPLAY RISK TABLES
# ============================================================

def show_risk_table(result, risk):

    records = result.get(
        RESULT_KEYS[risk], []
    ) or []

    st.subheader(
        f"{risk.title()} Analysis"
    )

    if not records:
        st.info(
            "No analysis records returned "
            "for this selection."
        )
        return

    df = clean_table(records)

    risk_column = find_risk_column(
        df, risk
    )

    # Risk level filtering
    if risk_column:

        levels = sorted(
            df[risk_column]
            .fillna("UNKNOWN")
            .astype(str)
            .str.upper()
            .unique()
            .tolist()
        )

        selected_levels = st.multiselect(
            "Filter by Risk Level",
            options=levels,
            default=levels,
            key=f"risk_filter_{risk}"
        )

        df = df[
            df[risk_column]
            .fillna("UNKNOWN")
            .astype(str)
            .str.upper()
            .isin(selected_levels)
        ]

    st.caption(
        f"Showing {len(df)} records"
    )

    if risk_column:

        styled_df = df.style.map(
            risk_color,
            subset=[risk_column]
        )

        st.dataframe(
            styled_df,
            hide_index=True,
            width="stretch"
        )

    else:

        st.dataframe(
            df,
            hide_index=True,
            width="stretch"
        )

    st.download_button(
        label=f"Download {risk.title()} CSV",
        data=df.to_csv(
            index=False
        ).encode("utf-8"),
        file_name=f"{risk}_results.csv",
        mime="text/csv",
        key=f"download_{risk}"
    )

# ============================================================
# 6. FINANCIAL IMPACT
# ============================================================

def show_financial_impact(result):

    financial = result.get(
        "financial_impact", {}
    ) or {}

    impacts = financial.get(
        "by_risk", {}
    ) or {}

    st.header("Financial Risk Impact")

    st.caption(
        "Estimated financial exposure using "
        "project SKU PTS prices. "
        "These values are not realized savings."
    )

    definitions = [
        ("expiry", "Expiry Exposure"),
        ("shortage", "Potential Sales at Risk"),
        ("oversupply", "Excess Inventory Value")
    ]

    columns = st.columns(3)

    chart_rows = []

    for col, (key, label) in zip(
        columns, definitions
    ):

        with col:

            details = impacts.get(key)

            if isinstance(details, dict):

                amount = details.get(
                    "exposure_inr"
                )

                if amount is not None:

                    st.metric(
                        label=label,
                        value=format_inr(amount)
                    )

                    chart_rows.append({
                        "Risk": key.title(),
                        "Amount (INR)": float(amount)
                    })

                else:
                    st.metric(
                        label=label,
                        value="N/A"
                    )

            else:
                st.metric(
                    label=label,
                    value="Not calculated"
                )

    if chart_rows:

        st.subheader(
            "Financial Exposure Comparison"
        )

        chart_df = pd.DataFrame(
            chart_rows
        )

        st.bar_chart(
            chart_df.set_index("Risk"),
            y="Amount (INR)"
        )

    missing = financial.get(
        "missing_price_skus", []
    ) or []

    if missing:
        st.warning(
            f"{len(missing)} SKUs could not be "
            "valued because PTS prices were missing."
        )

# ============================================================
# CLAIMS AND DELAYED SETTLEMENT SUMMARY
# ============================================================

def show_claims_summary(result):
    summary = result.get("claim_summary") or {}
    delayed = result.get("settlement_results") or []
    st.header("Expiry Claims & Delayed Settlement")
    st.caption(
        "Expired/near-expiry claims, evidence flags, and settlement monitoring. "
        "Threshold is a pilot alert, not a confirmed contractual SLA."
    )
    if not summary:
        st.warning("Claim summary missing. Check claims node routing and PharmaState.")
        return
    st.caption(
        f"Reporting as of {summary.get('as_of_date', 'N/A')} | "
        f"Monitoring threshold: {summary.get('monitor_threshold_days', 'N/A')} days"
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Expiry claim rows", summary.get("total_claim_rows", 0))
    c2.metric("Pending claims", summary.get("pending_rows", 0))
    c3.metric("Pending over threshold", summary.get("pending_over_threshold_rows", 0))
    c4.metric("Credited over threshold", summary.get("delayed_credited_rows", 0))
    avg = summary.get("average_settlement_days")
    st.metric("Average credited settlement", f"{avg} days" if avg is not None else "N/A")
    st.caption("Row counts can include repeated claim IDs; potential duplicates require review.")
    st.subheader("Settlement exceptions")
    if delayed:
        df = clean_table(delayed)
        st.dataframe(df, hide_index=True, width="stretch")
        st.download_button("Download settlement exceptions",
            df.to_csv(index=False).encode("utf-8"),
            file_name="claim_settlement_exceptions.csv", mime="text/csv",
            key="claim_settlement_export")
    else:
        st.info("No settlement exceptions returned.")
    st.subheader("Duplicate and Invalid Expiry Claims")
    review = result.get("duplicate_invalid_claims")
    if review is None:
        st.warning("Duplicate/invalid review output is missing. Update claimsAnalysis.py and PharmaState.")
    else:
        a, b, c, d = st.columns(4)
        a.metric("Potential duplicate rows", summary.get("potential_duplicate_rows", 0))
        b.metric("Invalid evidence rows", summary.get("invalid_evidence_rows", 0))
        c.metric("Incomplete evidence rows", summary.get("incomplete_evidence_rows", 0))
        d.metric("Total review rows", summary.get("duplicate_invalid_review_rows", 0))
        if review:
            review_df = clean_table(review)
            categories = sorted(review_df["review_category"].unique().tolist())
            chosen = st.multiselect(
                "Filter review category", categories, default=categories,
                key="claim_review_categories"
            )
            review_df = review_df[review_df["review_category"].isin(chosen)]
            st.dataframe(review_df, hide_index=True, width="stretch")
            st.download_button(
                "Download duplicate and invalid claim review CSV",
                review_df.to_csv(index=False).encode("utf-8"),
                file_name="expiry_claim_duplicate_invalid_review.csv", mime="text/csv",
                key="claim_review_export"
            )
        else:
            st.info("No duplicate or invalid evidence signals detected.")
    st.caption("Flags require manual investigation; none automatically rejects or approves a claim.")

    with st.expander("Claim evidence & monitoring notes"):
        st.write("Rows with evidence flags:", summary.get("flagged_rows", 0))
        st.write("Distinct claim numbers:", summary.get("distinct_claim_numbers", 0))
        for note in result.get("claim_warnings") or []:
            st.warning(note)


# ============================================================
# REDISTRIBUTION FRICTION (not allocation)
# ============================================================

def show_redistribution_summary(result):
    st.header("Slow Redistribution — Exposure Screening")
    summary = result.get("redistribution_summary") or {}
    rows = result.get("redistribution_results")
    st.caption(
        "Identify a shortage at one C&F when another has surplus of the same SKU. "
        "This does not calculate or approve stock transfers."
    )
    if rows is None:
        st.error("Redistribution results missing from LangGraph. Check routing and PharmaState.")
        return
    if summary:
        st.caption(
            f"Stock snapshot: {summary.get('snapshot_date', 'N/A')} | "
            f"Hypothetical delay: {summary.get('scenario_days', 'N/A')} days"
        )
        a, b, c = st.columns(3)
        a.metric("Affected C&F × SKU pairs", summary.get("impacted_receiver_locations", 0))
        b.metric("Affected SKUs", summary.get("affected_skus", 0))
        c.metric("Uncovered demand in scenario (packs)",
                 f"{summary.get('uncovered_demand_scenario_packs', 0):,}")
    st.info(
        "Actual redistribution duration is unavailable because transfer request, "
        "approval, dispatch and receipt timestamps are not in the source data. "
        "14 days is a scenario, NOT measured turnaround or an approved SLA."
    )
    if rows:
        df = clean_table(rows)
        st.subheader("Locations needing redistribution investigation")
        st.dataframe(df, hide_index=True, width="stretch")
        st.download_button("Download redistribution bottleneck report",
                           data=df.to_csv(index=False).encode("utf-8"),
                           file_name="redistribution_bottlenecks.csv",
                           mime="text/csv", key="redistribution_export")
    else:
        st.warning("No matching cross-location shortage/surplus patterns were returned.")
    with st.expander("Assumptions and data quality"):
        for warning in result.get("redistribution_warnings") or []:
            st.warning(str(warning))
        if summary:
            st.json(summary)


# ============================================================
# DEMAND FORECAST ACCURACY (HISTORICAL PRIMARY-SALES PROXY)
# ============================================================

def show_demand_forecast_summary(result):
    st.header("Inaccurate Demand Forecasting — Baseline Backtest")
    st.caption(
        "This compares a simple previous-three-month forecast with actual primary "
        "invoiced packs. It does not measure the company's official forecast accuracy "
        "or genuine secondary/customer demand."
    )
    rows = result.get("forecast_results")
    summary = result.get("forecast_summary") or {}
    if rows is None:
        st.error("Forecast results missing from LangGraph. Check state declaration and routing.")
        return

    if summary.get("reason"):
        st.warning(f"Cannot backtest: {summary['reason']}")
    c1, c2, c3, c4 = st.columns(4)
    wape = summary.get("wape_pct")
    bias = summary.get("bias_pct")
    c1.metric("Baseline WAPE", f"{wape:.2f}%" if wape is not None else "N/A")
    c2.metric("Baseline Bias", f"{bias:+.2f}%" if bias is not None else "N/A")
    c3.metric("High / Critical Months", summary.get("large_error_rows", 0))
    c4.metric("C&F × SKU × Months", summary.get("evaluated_cnf_sku_months", 0))
    st.caption(
        f"Backtest window: {summary.get('first_backtest_month', 'N/A')} to "
        f"{summary.get('last_backtest_month', 'N/A')} | "
        "WAPE = total absolute errors / total invoiced packs. "
        "Positive bias means over-forecasting."
    )

    if rows:
        df = clean_table(rows)
        levels = sorted(df["risk_level"].dropna().astype(str).unique().tolist())
        chosen = st.multiselect(
            "Filter forecast-risk severity", levels, default=levels,
            key="forecast_risk_levels"
        )
        filtered = df[df["risk_level"].isin(chosen)]
        st.subheader("Forecast-versus-primary-invoices by C&F, SKU and month")
        st.dataframe(filtered, hide_index=True, width="stretch")
        st.download_button(
            "Download forecast backtest CSV",
            data=filtered.to_csv(index=False).encode("utf-8"),
            file_name="demand_forecast_backtest.csv", mime="text/csv",
            key="forecast_export"
        )
        # Keep aggregates separate from per-SKU percentage errors.
        monthly = (
            df.groupby("month", as_index=False)[
                ["baseline_forecast_packs", "actual_primary_invoiced_packs"]
            ].sum().sort_values("month")
        )
        st.subheader("Monthly primary invoicing vs historical baseline")
        st.line_chart(
            monthly.set_index("month")
            [["baseline_forecast_packs", "actual_primary_invoiced_packs"]]
        )
        st.info(
            "A large difference may reflect schemes, quarter-end shipments, "
            "stock-outs, or genuine shifts in demand. Investigate before changing any plan."
        )
    else:
        st.warning("No eligible primary-invoice backtest records for the selected filters.")
    with st.expander("Forecast assumptions and data quality"):
        for warning in result.get("forecast_warnings") or []:
            st.warning(str(warning))
        st.json(summary)


# ============================================================
# 7. PAGE HEADER
# ============================================================

st.title(
    "💊 Project Sankalp - PharmaGuard AI"
)

st.caption(
    "Pharmaceutical Inventory Risk Intelligence"
)

st.markdown(
    "Analyze stock shortages, expiry exposure, oversupply, "
    "expiry-claim settlement, redistribution bottlenecks and demand forecasting across C&F locations."
)

# ============================================================
# 8. USER SELECTION
# ============================================================

with st.form("risk_selection_form"):

    selected_labels = st.multiselect(
        "Select Inventory Risks",
        options=list(RISK_OPTIONS.keys()),
        default=[
            "Shortage",
            "Expiry",
            "Oversupply"
        ]
    )

    submitted = st.form_submit_button(
        "Analyze Inventory",
        type="primary",
        use_container_width=True
    )

# ============================================================
# 9. EXECUTE ANALYSIS
# ============================================================

if submitted:

    if not selected_labels:

        st.warning(
            "Please select at least one analysis."
        )

        st.session_state.pop(
            "analysis_result", None
        )

        st.session_state.pop(
            "executed_risks", None
        )

    else:

        selected_risks = [
            RISK_OPTIONS[label]
            for label in selected_labels
        ]

        try:

            with st.spinner(
                "Analyzing inventory..."
            ):

                result = run_analysis(
                    selected_risks
                )

            st.session_state[
                "analysis_result"
            ] = result

            st.session_state[
                "executed_risks"
            ] = selected_risks

        except Exception as exc:

            st.session_state.pop(
                "analysis_result", None
            )

            st.session_state.pop(
                "executed_risks", None
            )

            st.error(
                f"Analysis failed: {exc}"
            )

# ============================================================
# 10. DISPLAY RESULTS
# ============================================================

result = st.session_state.get(
    "analysis_result"
)

if result is not None:

    selected_risks = st.session_state.get(
        "executed_risks", []
    )

    summary = result.get(
        "validation_summary", {}
    ) or {}

    if result.get("error"):
        st.error(result["error"])

    # --------------------------------------------------------
    # INVENTORY OVERVIEW
    # --------------------------------------------------------

    st.markdown(
        "### Inventory Overview"
    )

    cols = st.columns(4)

    cols[0].metric(
        "Stock Records",
        summary.get(
            "total_records", 0
        )
    )

    cols[1].metric(
        "Records With Issues",
        summary.get(
            "records_with_errors", 0
        )
    )

    cols[2].metric(
        "Risk Analyses",
        len(selected_risks)
    )

    cols[3].metric(
        "Recommendations",
        len(
            result.get("recommendations")
            or []
        )
    )

    st.divider()

    # --------------------------------------------------------
    # FINANCIAL IMPACT
    # --------------------------------------------------------

    if any(
        risk in selected_risks
        for risk in [
            "expiry",
            "shortage",
            "oversupply"
        ]
    ):
        show_financial_impact(result)

        st.divider()

    if "claims" in selected_risks:
        show_claims_summary(result)
        st.divider()

    if "redistribution" in selected_risks:
        show_redistribution_summary(result)
        st.divider()

    if "forecast" in selected_risks:
        show_demand_forecast_summary(result)
        st.divider()

    # --------------------------------------------------------
    # ANALYSIS RESULT TABS
    # --------------------------------------------------------

    st.markdown(
        "### Analysis Results"
    )

    tabs = st.tabs(
        [
            risk.title()
            for risk in selected_risks
        ]
        + [
            "Recommendations",
            "Data Quality"
        ]
    )

    for index, risk in enumerate(
        selected_risks
    ):

        with tabs[index]:

            validation_key = VALIDATION_KEYS.get(
                risk
            )

            if validation_key:
                st.caption(
                    "Validated stock records: "
                    f"{summary.get(validation_key, 0)}"
                )

            show_risk_table(
                result, risk
            )

    # --------------------------------------------------------
    # RECOMMENDATIONS TAB
    # --------------------------------------------------------

    with tabs[-2]:

        st.subheader(
            "Business Recommendations"
        )

        recommendations = result.get(
            "recommendations", []
        ) or []

        if recommendations:

            rec_df = clean_table(
                recommendations
            )

            st.dataframe(
                rec_df,
                hide_index=True,
                width="stretch"
            )

        else:

            st.info(
                "No recommendations returned."
            )

    # --------------------------------------------------------
    # DATA QUALITY TAB
    # --------------------------------------------------------

    with tabs[-1]:

        st.subheader(
            "Data Validation Report"
        )

        invalid = result.get(
            "invalid_stock", []
        ) or []

        if invalid:

            invalid_df = clean_table(
                invalid
            )

            st.warning(
                f"{len(invalid)} records "
                "have validation issues."
            )

            st.dataframe(
                invalid_df,
                hide_index=True,
                width="stretch"
            )

            st.download_button(
                "Download Invalid Records",
                invalid_df.to_csv(
                    index=False
                ).encode("utf-8"),
                file_name="invalid_stock.csv",
                mime="text/csv",
                key="download_invalid_stock"
            )

        else:

            st.success(
                "No validation issues reported."
            )