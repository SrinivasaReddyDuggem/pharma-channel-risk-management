
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
    "Oversupply": "oversupply"
}

RESULT_KEYS = {
    "shortage": "shortage_results",
    "expiry": "expiry_risks",
    "oversupply": "oversupply_risks"
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
    ]
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
# 7. PAGE HEADER
# ============================================================

st.title(
    "💊 Project Sankalp - PharmaGuard AI"
)

st.caption(
    "Pharmaceutical Inventory Risk Intelligence"
)

st.markdown(
    "Analyze stock shortages, expiry exposure, and "
    "oversupply across C&F locations."
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