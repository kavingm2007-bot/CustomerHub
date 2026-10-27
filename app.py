"""CustomerHub: Interactive Streamlit Dashboard for Customer Segmentation & Targeted Recommendations.

Visualizes RFM metrics, rule-based customer segments, segment-specific marketing offers,
and customer-personalized product recommendations using Streamlit and Plotly.
"""

import math
import streamlit as st
import plotly.express as px
import pandas as pd

# Reuse existing RFM and segmentation logic from logic.py
from logic import (
    get_orders_data,
    calculate_rfm,
    segment_customers,
    get_customer_transactions,
    get_customer_profile
)
# Reuse customer offer generation and product recommendations from offers.py
from offers import (
    add_customer_offers,
    assign_offer,
    get_product_catalog,
    get_recently_introduced_products,
    get_popular_products,
    get_customer_purchase_history,
    get_customer_category_recommendations,
    get_personalized_offer_details,
    get_profit_protection_rules,
    calculate_loyalty_points,
    get_vip_progress,
    get_combo_offers,
    get_limited_time_offers,
    get_discounted_comeback_products,
    get_customer_frequently_purchased,
    get_referral_program_details,
    CATEGORY_GROSS_MARGINS,
    MIN_PROFIT_MARGIN_FLOOR
)

# Set page configuration
st.set_page_config(
    page_title="CustomerHub - Customer Segmentation & Offers",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom color palette for segments
SEGMENT_COLORS = {
    "VIP Customer": "#10B981",       # Emerald Green
    "Regular Customer": "#3B82F6",   # Royal Blue
    "New Customer": "#8B5CF6",       # Purple / Violet
    "Occasional Customer": "#F59E0B",# Amber
    "At Risk": "#EF4444"             # Red
}


@st.cache_data(show_spinner="Loading customer data from shop.db...")
def load_data() -> pd.DataFrame:
    """Load data from SQLite, compute RFM segments, and attach offer suggestions."""
    orders_df = get_orders_data()
    rfm_df = calculate_rfm(orders_df)
    segmented_df = segment_customers(rfm_df)
    offers_df = add_customer_offers(segmented_df)
    return offers_df


def render_dashboard(df: pd.DataFrame):
    """Render the main CustomerHub overview dashboard."""
    total_customers = len(df)
    counts = df["CustomerSegment"].value_counts()

    vip_count = counts.get("VIP Customer", 0)
    regular_count = counts.get("Regular Customer", 0)
    new_count = counts.get("New Customer", 0)
    at_risk_count = counts.get("At Risk", 0)

    # Main Dashboard Header
    st.title("CustomerHub")
    st.markdown("Explore customer behavior, purchase patterns, and segment distributions based on **Recency, Frequency, and Monetary (RFM)** analysis with **Indian Retail Sales** data.")
    st.markdown("<br>", unsafe_allow_html=True)

    # Top Metric Cards (Total Customers, VIP Customers, Regular Customers, New Customers, At Risk Customers)
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric(
            label="👥 Total Customers",
            value=f"{total_customers:,}",
            help="Total unique customers identified in shop.db"
        )
    with col2:
        vip_pct = (vip_count / total_customers) * 100 if total_customers else 0
        st.metric(
            label="🌟 VIP Customers",
            value=f"{vip_count:,}",
            delta=f"{vip_pct:.1f}% of total"
        )
    with col3:
        reg_pct = (regular_count / total_customers) * 100 if total_customers else 0
        st.metric(
            label="🔄 Regular Customers",
            value=f"{regular_count:,}",
            delta=f"{reg_pct:.1f}% of total"
        )
    with col4:
        new_pct = (new_count / total_customers) * 100 if total_customers else 0
        st.metric(
            label="🎉 New Customers",
            value=f"{new_count:,}",
            delta=f"{new_pct:.1f}% of total"
        )
    with col5:
        risk_pct = (at_risk_count / total_customers) * 100 if total_customers else 0
        st.metric(
            label="⚠️ At Risk Customers",
            value=f"{at_risk_count:,}",
            delta=f"-{risk_pct:.1f}% of total",
            delta_color="inverse"
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Visualizations Row: Bar Chart & Pie Chart
    chart_col1, chart_col2 = st.columns(2)

    # Segment summary data for plotting
    segment_order = ["VIP Customer", "Regular Customer", "New Customer", "Occasional Customer", "At Risk"]
    summary_df = pd.DataFrame({
        "CustomerSegment": segment_order,
        "Count": [counts.get(s, 0) for s in segment_order]
    })
    summary_df["Percentage"] = (summary_df["Count"] / total_customers) * 100

    with chart_col1:
        st.subheader("📊 Customers by Segment")
        bar_fig = px.bar(
            summary_df,
            x="CustomerSegment",
            y="Count",
            color="CustomerSegment",
            color_discrete_map=SEGMENT_COLORS,
            text="Count",
            labels={"CustomerSegment": "Segment", "Count": "Number of Customers"},
            title="Customer Count per Segment"
        )
        bar_fig.update_traces(
            texttemplate="%{text:,}",
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Customers: %{y:,}<br>Share: %{customdata[0]:.1f}%<extra></extra>",
            customdata=summary_df[["Percentage"]].values
        )
        bar_fig.update_layout(
            showlegend=False,
            height=380,
            xaxis_title="",
            yaxis_title="Customers",
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(bar_fig, use_container_width=True)

    with chart_col2:
        st.subheader("🥧 Percentage Share per Segment")
        pie_fig = px.pie(
            summary_df,
            names="CustomerSegment",
            values="Count",
            color="CustomerSegment",
            color_discrete_map=SEGMENT_COLORS,
            hole=0.45,
            title="Segment Share (% of Total Customers)"
        )
        pie_fig.update_traces(
            textinfo="percent+label",
            hovertemplate="<b>%{label}</b><br>Customers: %{value:,}<br>Percentage: %{percent}<extra></extra>"
        )
        pie_fig.update_layout(
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
            height=380,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(pie_fig, use_container_width=True)

    st.markdown("---")

    # Customer Table & Dropdown Filter Section
    st.subheader("🔍 Customer Details Table")

    filter_col1, filter_col2 = st.columns([1, 2])
    with filter_col1:
        segment_options = ["All Segments", "VIP Customer", "Regular Customer", "New Customer", "Occasional Customer", "At Risk"]
        selected_segment = st.selectbox(
            "Filter by Customer Segment:",
            options=segment_options,
            index=0,
            key="dashboard_segment_filter"
        )
    with filter_col2:
        search_id = st.text_input(
            "Search by Customer ID (optional):",
            placeholder="e.g. CUST-1507",
            key="dashboard_search_id"
        )

    # Filter DataFrame according to user selection
    filtered_df = df.copy()
    if selected_segment != "All Segments":
        filtered_df = filtered_df[filtered_df["CustomerSegment"] == selected_segment]

    if search_id.strip():
        filtered_df = filtered_df[filtered_df["CustomerID"].astype(str).str.contains(search_id.strip(), case=False)]

    st.markdown(f"Showing **{len(filtered_df):,}** customers:")

    # Customer Table displaying CustomerID, Recency, Frequency, Monetary, and CustomerSegment
    table_cols = {
        "CustomerID": st.column_config.TextColumn(
            "Customer ID"
        ),
        "Recency": st.column_config.NumberColumn(
            "Recency (Days)",
            help="Days since last purchase",
            format="%d days"
        ),
        "Frequency": st.column_config.NumberColumn(
            "Frequency (Orders)",
            help="Number of distinct purchase invoices",
            format="%d"
        ),
        "Monetary": st.column_config.NumberColumn(
            "Monetary (₹)",
            help="Total amount spent across all orders in INR",
            format="₹%.2f"
        ),
        "CustomerSegment": st.column_config.TextColumn(
            "Customer Segment"
        )
    }
    if "CustomerName" in filtered_df.columns:
        table_cols = {
            "CustomerID": st.column_config.TextColumn("Customer ID"),
            "CustomerName": st.column_config.TextColumn("Customer Name"),
            "Recency": table_cols["Recency"],
            "Frequency": table_cols["Frequency"],
            "Monetary": table_cols["Monetary"],
            "CustomerSegment": table_cols["CustomerSegment"]
        }

    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True,
        column_config=table_cols
    )


def render_customer_profile_page(df: pd.DataFrame):
    """Render the detailed Customer Profile page with 360 metrics and paginated transaction history."""
    st.title("👤 Customer Profile")
    st.markdown("Comprehensive customer 360 profile: summary metrics, purchase totals, and complete line-item transaction history from `shop.db`.")
    st.markdown("<br>", unsafe_allow_html=True)

    # Data Notice Box
    st.info(
        "ℹ️ **Data Transparency Note**: All metrics and transaction logs below are calculated directly from verified records in `shop.db`. "
        "Customer search events and browsing histories are not invented or tracked, as the India Retail Sales dataset only records completed transactions."
    )

    # Customer Selection Controls
    st.subheader("🔍 Select Customer")
    sel_col1, sel_col2, sel_col3 = st.columns([1.2, 1.8, 1])

    with sel_col1:
        segment_filter = st.selectbox(
            "Filter Customer List by Segment:",
            options=["All Segments", "VIP Customer", "Regular Customer", "New Customer", "Occasional Customer", "At Risk"],
            index=0,
            key="profile_segment_filter"
        )

    # Filter candidate customers based on segment selection
    if segment_filter == "All Segments":
        candidate_customers = df
    else:
        candidate_customers = df[df["CustomerSegment"] == segment_filter]

    # Pre-build customer display choices
    customer_ids = candidate_customers["CustomerID"].tolist()
    customer_options_display = [
        f"{str(cid)} - {candidate_customers.loc[candidate_customers['CustomerID'] == cid, 'CustomerName'].values[0]} ({candidate_customers.loc[candidate_customers['CustomerID'] == cid, 'CustomerSegment'].values[0]} - ₹{candidate_customers.loc[candidate_customers['CustomerID'] == cid, 'Monetary'].values[0]:,.2f})"
        if "CustomerName" in candidate_customers.columns and pd.notna(candidate_customers.loc[candidate_customers['CustomerID'] == cid, 'CustomerName'].values[0])
        else f"{str(cid)} ({candidate_customers.loc[candidate_customers['CustomerID'] == cid, 'CustomerSegment'].values[0]} - ₹{candidate_customers.loc[candidate_customers['CustomerID'] == cid, 'Monetary'].values[0]:,.2f})"
        for cid in customer_ids
    ]

    with sel_col2:
        selected_option = st.selectbox(
            "Select Customer from List:",
            options=customer_options_display,
            index=0 if customer_options_display else None,
            key="profile_customer_select"
        )

    with sel_col3:
        direct_cid_input = st.text_input(
            "Or Type Customer ID directly:",
            placeholder="e.g. CUST-1507 or 1507",
            key="profile_direct_cid"
        )

    # Determine final chosen customer ID
    chosen_cid = None
    if direct_cid_input.strip():
        typed_raw = direct_cid_input.strip()
        if typed_raw in df["CustomerID"].values:
            chosen_cid = typed_raw
        elif f"CUST-{typed_raw}" in df["CustomerID"].values:
            chosen_cid = f"CUST-{typed_raw}"
        else:
            st.warning(f"Customer ID '{typed_raw}' not found in database. Using selected customer from dropdown.")

    if chosen_cid is None and selected_option:
        chosen_cid = selected_option.split()[0]

    if chosen_cid is None:
        st.warning("No customers available with the selected filter.")
        return

    # Fetch Customer Profile & Transactions
    try:
        profile = get_customer_profile(chosen_cid, rfm_df=df)
        raw_tx_df = get_customer_transactions(chosen_cid)
    except Exception as e:
        st.error(f"Failed to load customer profile from database: {e}")
        return

    # Display Profile Summary Metrics
    st.markdown("<br>", unsafe_allow_html=True)
    header_name = f" - {profile.get('CustomerName')}" if profile.get("CustomerName") else ""
    st.subheader(f"📊 Customer Overview: {chosen_cid}{header_name}")

    # Row 1: Core Identification & RFM Metrics
    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
    with mcol1:
        st.metric(
            label="🆔 Customer ID",
            value=f"{profile['CustomerID']}",
            help="Unique customer identifier in shop.db"
        )
    with mcol2:
        st.metric(
            label="🏷️ Customer Segment",
            value=profile["CustomerSegment"],
            help="Rule-based RFM classification"
        )
    with mcol3:
        st.metric(
            label="⏱️ Recency",
            value=f"{profile['Recency']} days",
            help="Days since customer's most recent purchase"
        )
    with mcol4:
        st.metric(
            label="🔄 Frequency",
            value=f"{profile['Frequency']} invoices",
            help="Number of distinct purchase invoices (avoids double-counting)"
        )

    # Row 2: Spend, Volume & Lifetime Dates
    mcol5, mcol6, mcol7, mcol8 = st.columns(4)
    with mcol5:
        st.metric(
            label="💰 Monetary Value",
            value=f"₹{profile['Monetary']:,.2f}",
            help="Total amount spent across all transactions in shop.db"
        )
    with mcol6:
        st.metric(
            label="📦 Total Quantity Purchased",
            value=f"{profile['TotalQuantity']:,} units",
            help="Sum of all item quantities purchased"
        )
    with mcol7:
        first_dt_str = profile["FirstPurchaseDate"].strftime("%Y-%m-%d %H:%M") if pd.notnull(profile["FirstPurchaseDate"]) else "N/A"
        st.metric(
            label="📅 First Purchase Date",
            value=first_dt_str,
            help="Timestamp of customer's earliest order"
        )
    with mcol8:
        last_dt_str = profile["MostRecentPurchaseDate"].strftime("%Y-%m-%d %H:%M") if pd.notnull(profile["MostRecentPurchaseDate"]) else "N/A"
        st.metric(
            label="🕒 Most Recent Purchase",
            value=last_dt_str,
            help="Timestamp of customer's latest order"
        )

    st.markdown("<br><hr>", unsafe_allow_html=True)

    # Transaction History Section (Requirement 5, 6, 7, 8, 9)
    st.subheader(f"🧾 Complete Transaction History ({len(raw_tx_df):,} total records)")
    st.caption("Transactions are sorted by **InvoiceDate (newest first)**. Filter by date or product description, or paginate through the full record set.")

    # Useful Filters (Requirement 9)
    fcol1, fcol2, fcol3 = st.columns([1.5, 1.5, 1])

    # Date range bounds
    min_date = raw_tx_df["InvoiceDate"].min().date() if not raw_tx_df.empty else None
    max_date = raw_tx_df["InvoiceDate"].max().date() if not raw_tx_df.empty else None

    with fcol1:
        if min_date and max_date:
            date_filter = st.date_input(
                "Filter by Date Range:",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                key="tx_date_filter"
            )
        else:
            date_filter = None

    with fcol2:
        desc_filter = st.text_input(
            "Filter by Product Description:",
            placeholder="e.g. BAG, HEART, MUG, etc.",
            key="tx_desc_filter"
        )

    with fcol3:
        invoices = ["All Invoices"] + [str(inv) for inv in raw_tx_df["InvoiceNo"].unique()]
        invoice_filter = st.selectbox(
            "Filter by Invoice Number:",
            options=invoices,
            index=0,
            key="tx_invoice_filter"
        )

    # Apply Filters to Transactions
    filtered_tx = raw_tx_df.copy()

    # Apply Date Filter
    if date_filter and len(date_filter) == 2:
        start_d, end_d = date_filter
        filtered_tx = filtered_tx[
            (filtered_tx["InvoiceDate"].dt.date >= start_d) &
            (filtered_tx["InvoiceDate"].dt.date <= end_d)
        ]

    # Apply Description Filter
    if desc_filter.strip():
        filtered_tx = filtered_tx[
            filtered_tx["Description"].fillna("").str.contains(desc_filter.strip(), case=False)
        ]

    # Apply Invoice Filter
    if invoice_filter != "All Invoices":
        filtered_tx = filtered_tx[filtered_tx["InvoiceNo"].astype(str) == invoice_filter]

    # Filtered Summary Metrics
    filtered_records = len(filtered_tx)
    filtered_qty = filtered_tx["Quantity"].sum() if not filtered_tx.empty else 0
    filtered_amount = filtered_tx["Amount"].sum() if not filtered_tx.empty else 0.0

    st.markdown(
        f"**Filtered Results:** Showing **{filtered_records:,}** of **{len(raw_tx_df):,}** transactions "
        f"(Total Items: **{filtered_qty:,}** units | Total Value: **₹{filtered_amount:,.2f}**)"
    )

    if filtered_records == 0:
        st.warning("No transactions match the selected filters. Try broadening your filter criteria.")
        return

    # Pagination Controls
    pcol1, pcol2, pcol3 = st.columns([1, 1, 2])
    with pcol1:
        page_size_options = [25, 50, 100, "All"]
        chosen_page_size = st.selectbox(
            "Rows per page:",
            options=page_size_options,
            index=0,
            key="tx_page_size"
        )

    if chosen_page_size != "All":
        page_size = int(chosen_page_size)
        total_pages = max(1, math.ceil(filtered_records / page_size))
        with pcol2:
            page_number = st.number_input(
                f"Page (of {total_pages}):",
                min_value=1,
                max_value=total_pages,
                value=1,
                step=1,
                key="tx_page_number"
            )
        start_idx = (page_number - 1) * page_size
        end_idx = min(start_idx + page_size, filtered_records)
        display_tx = filtered_tx.iloc[start_idx:end_idx]
        with pcol3:
            st.markdown("<div style='padding-top: 28px;'>", unsafe_allow_html=True)
            st.caption(f"Displaying rows {start_idx + 1} - {end_idx} of {filtered_records:,}")
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        display_tx = filtered_tx
        with pcol3:
            st.markdown("<div style='padding-top: 28px;'>", unsafe_allow_html=True)
            st.caption(f"Displaying all {filtered_records:,} transactions")
            st.markdown("</div>", unsafe_allow_html=True)

    # Transaction Table displaying all required columns
    st.dataframe(
        display_tx,
        use_container_width=True,
        hide_index=True,
        column_config={
            "InvoiceNo": st.column_config.TextColumn(
                "Order / Invoice No"
            ),
            "InvoiceDate": st.column_config.DatetimeColumn(
                "Order Date",
                format="YYYY-MM-DD"
            ),
            "StockCode": st.column_config.TextColumn(
                "Product Code"
            ),
            "Description": st.column_config.TextColumn(
                "Product Name"
            ),
            "Quantity": st.column_config.NumberColumn(
                "Quantity",
                format="%d"
            ),
            "UnitPrice": st.column_config.NumberColumn(
                "Unit Price (₹)",
                format="₹%.2f"
            ),
            "Amount": st.column_config.NumberColumn(
                "Line Total (₹)",
                format="₹%.2f"
            )
        }
    )

    # Download All / Filtered Transactions (CSV)
    csv_data = filtered_tx.to_csv(index=False)
    st.download_button(
        label=f"📥 Download Filtered Transactions for Customer {chosen_cid} (CSV)",
        data=csv_data,
        file_name=f"customer_{chosen_cid}_transactions.csv",
        mime="text/csv"
    )


def render_offers_page(df: pd.DataFrame):
    """Render the Personalized Offers and Product Recommendations page."""
    st.title("🎁 Customer Offers & Product Recommendations")
    st.markdown("Explore segment-specific marketing campaigns, profit-protected discounts, combo bundles, and personalized product recommendations based on real customer purchase history in `shop.db`.")
    st.markdown("<br>", unsafe_allow_html=True)

    # Data Notice Box
    st.info(
        "ℹ️ **Data Transparency Note**: Product recommendations, invoice counts, prices, and past purchases are computed from actual transaction data in `shop.db`. "
        "Promotional discounts (e.g. 5% first order, 5% repeat scratch card, 5% occasional selected discount, 10% comeback offer, 20% VIP privilege) are **simulated marketing offers** with built-in **profit protection guardrails** (minimum 15% net profit margin floor)."
    )

    # Segment Strategy Overview Cards
    st.subheader("🎯 Marketing Strategies by Segment")
    card1, card2, card3, card4, card5 = st.columns(5)
    with card1:
        st.markdown(
            """
            <div style="background-color: rgba(16, 185, 129, 0.1); border-left: 4px solid #10B981; padding: 12px; border-radius: 6px; height: 100%;">
                <h4 style="margin: 0; color: #10B981;">🌟 VIP Customer</h4>
                <p style="margin: 6px 0 0 0; font-size: 0.88em;">
                    <strong>Perks:</strong> Loyalty points & exclusive 20% VIP rewards.<br>
                    <strong>Access:</strong> Early access to new catalog arrivals.<br>
                    <strong>Delivery:</strong> Free Priority Delivery (₹0 threshold).<br>
                    <strong>Safeguard:</strong> MOV ₹2,500 | Max cap ₹5,000.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
    with card2:
        st.markdown(
            """
            <div style="background-color: rgba(59, 130, 246, 0.1); border-left: 4px solid #3B82F6; padding: 12px; border-radius: 6px; height: 100%;">
                <h4 style="margin: 0; color: #3B82F6;">🔄 Regular Customer</h4>
                <p style="margin: 6px 0 0 0; font-size: 0.88em;">
                    <strong>Strategy:</strong> 5% repeat purchase discount.<br>
                    <strong>Milestone:</strong> Visual progress toward VIP rewards.<br>
                    <strong>Perks:</strong> Loyalty points + scratch card reward.<br>
                    <strong>Recs:</strong> Frequently purchased products.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
    with card3:
        st.markdown(
            """
            <div style="background-color: rgba(245, 158, 11, 0.1); border-left: 4px solid #F59E0B; padding: 12px; border-radius: 6px; height: 100%;">
                <h4 style="margin: 0; color: #F59E0B;">🛒 Occasional</h4>
                <p style="margin: 6px 0 0 0; font-size: 0.88em;">
                    <strong>Strategy:</strong> 5% discount on selected products.<br>
                    <strong>Combos:</strong> Value bundles to encourage larger orders.<br>
                    <strong>Shipping:</strong> Free shipping on orders ≥ ₹999.<br>
                    <strong>Safeguard:</strong> MOV ₹1,000 | Max cap ₹500.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
    with card4:
        st.markdown(
            """
            <div style="background-color: rgba(239, 68, 68, 0.1); border-left: 4px solid #EF4444; padding: 12px; border-radius: 6px; height: 100%;">
                <h4 style="margin: 0; color: #EF4444;">⚠️ At Risk</h4>
                <p style="margin: 6px 0 0 0; font-size: 0.88em;">
                    <strong>Strategy:</strong> 10% win-back comeback offer.<br>
                    <strong>Expiry:</strong> Valid for 14 days.<br>
                    <strong>Recs:</strong> Buy-again, trending & discounted deals.<br>
                    <strong>Safeguard:</strong> MOV ₹1,500 | Max cap ₹1,500.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
    with card5:
        st.markdown(
            """
            <div style="background-color: rgba(139, 92, 246, 0.1); border-left: 4px solid #8B5CF6; padding: 12px; border-radius: 6px; height: 100%;">
                <h4 style="margin: 0; color: #8B5CF6;">🎉 New Customer</h4>
                <p style="margin: 6px 0 0 0; font-size: 0.88em;">
                    <strong>Strategy:</strong> 5% discount on first order.<br>
                    <strong>Expiry:</strong> Valid for 30 days.<br>
                    <strong>Recs:</strong> Trending & best-selling products.<br>
                    <strong>Safeguard:</strong> MOV ₹500 | Max cap ₹500.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Storewide Attraction & Profit Protection Overview Expander
    with st.expander("🛡️ Storewide Attraction Features & Profit Protection Policy", expanded=False):
        att_tab1, att_tab2, att_tab3, att_tab4 = st.tabs([
            "🛡️ Profit Protection Guardrails",
            "📦 Curated Combo Offers",
            "⏰ Limited-Time Flash Deals",
            "🚚 Free Shipping & Referral Program"
        ])

        with att_tab1:
            st.markdown("#### 🛡️ Profit Margin Safeguards & Financial Guardrails")
            st.markdown(
                """
                To ensure promotional offers never compromise business profitability, CustomerHub enforces four strict rules:
                1. **15% Minimum Net Margin Floor**: Every offer guarantees the company retains at least a **15.0% net profit margin** after deducting discounts and fulfillment costs.
                2. **Category Margin Differentiation**: Discounts are only permitted on categories with sufficient gross margins:
                   - **Clothing (38% margin)** & **Furniture (35% margin)**: Eligible for up to 20% discounts (VIP tier).
                   - **Office Supplies (30% margin)**: Eligible for up to 10% discounts.
                   - **Groceries (22% margin)** & **Electronics (20% margin)**: Strictly capped at 5% maximum discount.
                3. **Minimum Order Values (MOV)**: ₹500 (New), ₹1,000 (Regular/Occasional), ₹1,500 (At Risk), ₹2,500 (VIP) to prevent losses from packaging and logistics.
                4. **Maximum Discount Caps**: Limits total promotion loss on high-value basket orders (capped at ₹500 to ₹5,000).
                """
            )
            margin_cols = st.columns(5)
            for idx, (cat, m) in enumerate(CATEGORY_GROSS_MARGINS.items()):
                with margin_cols[idx]:
                    st.metric(f"{cat}", f"{m * 100:.0f}% Gross", delta="Net Margin ≥ 15%")

        with att_tab2:
            st.markdown("#### 📦 Curated Combo Offers (Basket Size Booster)")
            st.caption("Bundled complementary products offering 6% to 9% savings while keeping profit margins safely above 15%.")
            combos_list = get_combo_offers()
            c_cols = st.columns(2)
            for idx, combo in enumerate(combos_list):
                with c_cols[idx % 2]:
                    st.markdown(
                        f"""
                        <div style="background-color: rgba(245, 158, 11, 0.08); border: 1px solid #F59E0B; padding: 12px; border-radius: 8px; margin-bottom: 12px;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <strong style="font-size: 1.05em; color: #D97706;">{combo['title']}</strong>
                                <span style="background: #F59E0B; color: #1E293B; font-weight: bold; font-size: 0.8em; padding: 2px 6px; border-radius: 4px;">{combo['discount_pct']} OFF</span>
                            </div>
                            <p style="margin: 4px 0; font-size: 0.88em; color: #4B5563;">{combo['description']}</p>
                            <p style="margin: 4px 0; font-size: 0.85em;"><strong>Items:</strong> {', '.join(combo['items'])}</p>
                            <div style="margin-top: 6px;">
                                <span style="text-decoration: line-through; color: #9CA3AF; margin-right: 6px;">₹{combo['regular_price']:,.0f}</span>
                                <strong style="color: #059669; font-size: 1.1em;">₹{combo['combo_price']:,.0f}</strong>
                                <span style="color: #10B981; font-size: 0.9em; margin-left: 6px;">(Save ₹{combo['savings']:,.0f})</span>
                            </div>
                            <div style="margin-top: 4px; font-size: 0.8em; color: #6B7280;">
                                Promo Code: <code>{combo['promo_code']}</code> | Profit: {combo['margin_after_discount']}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

        with att_tab3:
            st.markdown("#### ⏰ Limited-Time Flash Deals (48-Hour Weekend Window)")
            st.caption("Time-limited 7% discounts on select high-margin items to create urgency and accelerate conversions.")
            deals_df = get_limited_time_offers(limit=4)
            st.dataframe(
                deals_df[["StockCode", "Description", "AvgPrice", "DealPrice", "Savings", "FlashDiscount", "ExpiresIn", "ProfitStatus"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "StockCode": st.column_config.TextColumn("Product Code"),
                    "Description": st.column_config.TextColumn("Product Name"),
                    "AvgPrice": st.column_config.NumberColumn("Regular Price (₹)", format="₹%.2f"),
                    "DealPrice": st.column_config.NumberColumn("Deal Price (₹)", format="₹%.2f"),
                    "Savings": st.column_config.NumberColumn("You Save (₹)", format="₹%.2f"),
                    "FlashDiscount": st.column_config.TextColumn("Discount"),
                    "ExpiresIn": st.column_config.TextColumn("Timer"),
                    "ProfitStatus": st.column_config.TextColumn("Profit Protection")
                }
            )

        with att_tab4:
            st.markdown("#### 🚚 Free Express Shipping & 🤝 Referral Rewards Program")
            col_ship, col_ref = st.columns(2)
            with col_ship:
                st.markdown(
                    """
                    <div style="background-color: rgba(59, 130, 246, 0.08); border-left: 4px solid #3B82F6; padding: 14px; border-radius: 6px;">
                        <h4 style="margin: 0; color: #3B82F6;">🚚 Free Express Shipping</h4>
                        <p style="margin: 8px 0 0 0; font-size: 0.9em;">
                            - <strong>Standard Threshold:</strong> Free Express Shipping across all states in India on orders <strong>≥ ₹999</strong>.<br>
                            - <strong>VIP Privilege:</strong> Free Priority Delivery on <strong>all orders</strong> with no minimum order threshold.<br>
                            - <strong>Profit Rationale:</strong> Orders over ₹999 generate sufficient gross margin contribution to fully absorb logistics overhead.
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            with col_ref:
                st.markdown(
                    """
                    <div style="background-color: rgba(16, 185, 129, 0.08); border-left: 4px solid #10B981; padding: 14px; border-radius: 6px;">
                        <h4 style="margin: 0; color: #10B981;">🤝 Referral Rewards Program</h4>
                        <p style="margin: 8px 0 0 0; font-size: 0.9em;">
                            - <strong>Reward Points:</strong> Earn <strong>250 Loyalty Points (₹250 cash value)</strong> when a referred friend makes their first purchase.<br>
                            - <strong>Friend's Benefit:</strong> Your friend enjoys a 5% First Order Welcome Discount (Code <code>FIRST5</code>).<br>
                            - <strong>Zero Friction:</strong> Points are automatically credited to your loyalty balance upon verified checkout.
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

    st.markdown("<hr>", unsafe_allow_html=True)

    # Interactive Section: Personalize by CustomerID
    st.subheader("👤 Customer Personalization & Product Recommendations")
    st.caption("Select any customer to generate their segment-tailored offer, loyalty points balance, reward voucher, and personalized product recommendations.")

    pick_col1, pick_col2 = st.columns([1, 2])
    with pick_col1:
        segment_filter = st.selectbox(
            "Filter Customer Segment:",
            options=["All Segments", "VIP Customer", "Regular Customer", "New Customer", "Occasional Customer", "At Risk"],
            index=0,
            key="rec_segment_filter"
        )

    # Filter candidate customers
    if segment_filter == "All Segments":
        candidate_customers = df
    else:
        candidate_customers = df[df["CustomerSegment"] == segment_filter]

    # Customer select dropdown
    customer_options = candidate_customers["CustomerID"].tolist()
    customer_options_display = [
        f"{str(cid)} - {candidate_customers.loc[candidate_customers['CustomerID'] == cid, 'CustomerName'].values[0]} ({candidate_customers.loc[candidate_customers['CustomerID'] == cid, 'CustomerSegment'].values[0]} - ₹{candidate_customers.loc[candidate_customers['CustomerID'] == cid, 'Monetary'].values[0]:,.2f})"
        if "CustomerName" in candidate_customers.columns and pd.notna(candidate_customers.loc[candidate_customers['CustomerID'] == cid, 'CustomerName'].values[0])
        else f"{str(cid)} ({candidate_customers.loc[candidate_customers['CustomerID'] == cid, 'CustomerSegment'].values[0]} - ₹{candidate_customers.loc[candidate_customers['CustomerID'] == cid, 'Monetary'].values[0]:,.2f})"
        for cid in customer_options
    ]

    with pick_col2:
        selected_option = st.selectbox(
            "Select Customer:",
            options=customer_options_display,
            index=0 if customer_options_display else None,
            key="selected_customer_option"
        )

    if not selected_option:
        st.warning("No customers match the selected filter.")
        return

    # Extract chosen CustomerID
    selected_customer_id = selected_option.split()[0]
    cust_row = df[df["CustomerID"] == selected_customer_id].iloc[0]
    cust_segment = cust_row["CustomerSegment"]

    # Get personalized offer and recommendation details
    details = get_personalized_offer_details(selected_customer_id, cust_segment)
    loyalty = details["loyalty_info"]
    profit_rules = details["profit_rules"]
    referral = details["referral_info"]

    # Customer Profile Summary Bar
    st.markdown("<br>", unsafe_allow_html=True)
    prof_col1, prof_col2, prof_col3, prof_col4, prof_col5, prof_col6 = st.columns(6)
    with prof_col1:
        st.metric("Customer ID", f"{selected_customer_id}")
    with prof_col2:
        st.metric("Segment", cust_segment)
    with prof_col3:
        st.metric("Recency", f"{int(cust_row['Recency'])} days")
    with prof_col4:
        st.metric("Frequency", f"{int(cust_row['Frequency'])} orders")
    with prof_col5:
        st.metric("Total Spend", f"₹{cust_row['Monetary']:,.2f}")
    with prof_col6:
        st.metric("Loyalty Balance", f"{loyalty['points']:,} pts", delta=f"{loyalty['tier']}")

    # Segment Specific Personalized Offer Card
    st.markdown("<br>", unsafe_allow_html=True)

    # 1. VIP Customer
    if cust_segment == "VIP Customer":
        st.success(
            f"### {details['offer_title']}\n"
            f"**Exclusive Offer:** {details['offer_description']}\n\n"
            f"👑 **VIP Privilege Code:** `{details['promo_code']}` | 🎁 **Loyalty Points:** **{loyalty['points']:,} Points** ({loyalty['tier']} - Value ₹{loyalty['cash_value_inr']:,.2f})\n\n"
            f"🚚 **Shipping:** {details['free_shipping_status']}\n\n"
            f"🛡️ **Profit Protection Guardrails:** Minimum Order: ₹{details['min_order_value']:,.0f} | Max Discount: ₹{details['max_discount_cap']:,.0f} | Net Margin Floor: Guaranteed ≥ 15%\n\n"
            f"🤝 **Customer Referral Code:** `{referral['referral_code']}` (Earn {referral['reward_points']} points when a friend orders)\n\n"
            f"*{details['simulation_note']}*"
        )

    # 2. Regular Customer
    elif cust_segment == "Regular Customer":
        st.info(
            f"### {details['offer_title']}\n"
            f"**Offer:** {details['offer_description']}\n\n"
            f"🎁 **Promo Code:** `{details['promo_code']}` | 🎖️ **Loyalty Balance:** **{loyalty['points']:,} Points** ({loyalty['tier']})\n\n"
            f"🛡️ **Profit Protection:** Min Order: ₹{details['min_order_value']:,.0f} | Max Discount: ₹{details['max_discount_cap']:,.0f} | Net Margin Floor: ≥ 15%\n\n"
            f"*{details['simulation_note']}*"
        )

        # Visual Progress toward VIP Rewards
        vip_p = details.get("vip_progress")
        if vip_p:
            st.markdown("##### 🚀 Progress Toward VIP Rewards")
            st.progress(vip_p["overall_pct"] / 100.0)

            v_col1, v_col2, v_col3 = st.columns(3)
            with v_col1:
                st.metric(
                    "Order Milestone",
                    f"{vip_p['current_orders']} / {vip_p['target_orders']} orders",
                    delta=f"{vip_p['orders_remaining']} more needed" if vip_p['orders_remaining'] > 0 else "Goal Achieved!"
                )
            with v_col2:
                st.metric(
                    "Spend Milestone",
                    f"₹{vip_p['current_spend']:,.2f} / ₹{vip_p['target_spend']:,.0f}",
                    delta=f"₹{vip_p['spend_remaining']:,.2f} needed" if vip_p['spend_remaining'] > 0 else "Goal Achieved!"
                )
            with v_col3:
                st.metric(
                    "Next Tier Milestone",
                    "20% VIP Privilege Code",
                    delta=f"{vip_p['overall_pct']:.0f}% Completed"
                )

        # Interactive Scratch Card Simulation
        with st.expander("🎫 Reveal Scratch-Card Reward", expanded=False):
            st.markdown(
                f"""
                <div style="background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%); color: white; padding: 20px; border-radius: 10px; text-align: center;">
                    <h3 style="margin: 0; color: white;">🎉 YOU UNLOCKED A 5% REPEAT PURCHASE DISCOUNT!</h3>
                    <p style="margin: 8px 0; font-size: 1.1em;">Use Code at Checkout: <strong style="background: #F59E0B; color: #1E293B; padding: 4px 10px; border-radius: 4px;">{details['promo_code']}</strong></p>
                    <p style="margin: 0; font-size: 0.85em; opacity: 0.9;">Valid for your next order. Minimum order ₹{details['min_order_value']:,.0f}. Net company profit guaranteed ≥ 15%.</p>
                </div>
                """,
                unsafe_allow_html=True
            )

    # 3. Occasional Customer
    elif cust_segment == "Occasional Customer":
        st.warning(
            f"### {details['offer_title']}\n"
            f"**Offer:** {details['offer_description']}\n\n"
            f"🏷️ **Promo Code:** `{details['promo_code']}` (5% Discount on selected margin-healthy products)\n\n"
            f"📦 **Combo Offer Incentive:** Combine complementary products from the 'Curated Combo Offers' tab below to save an additional 6%–9% on your order!\n\n"
            f"🛡️ **Profit Protection:** Min Order: ₹{details['min_order_value']:,.0f} | Max Discount: ₹{details['max_discount_cap']:,.0f} | 🚚 Free Express Shipping on orders ≥ ₹999\n\n"
            f"*{details['simulation_note']}*"
        )

    # 4. At Risk Customer
    elif cust_segment == "At Risk":
        st.error(
            f"### {details['offer_title']}\n"
            f"**Offer:** {details['offer_description']}\n\n"
            f"💌 **Comeback Promo Code:** `{details['promo_code']}` | ⏰ **Expiry Date:** **{details['expiry_date']}** (Valid for 14 days)\n\n"
            f"🔁 **Re-Order Incentive:** Apply your 10% comeback code to previously purchased products in your 'Buy It Again' tab or explore discounted comeback items below.\n\n"
            f"🛡️ **Profit Protection:** Min Order: ₹{details['min_order_value']:,.0f} | Max Discount: ₹{details['max_discount_cap']:,.0f} | Net Margin Floor: Guaranteed ≥ 15%\n\n"
            f"*{details['simulation_note']}*"
        )

    # 5. New Customer
    elif cust_segment == "New Customer":
        st.success(
            f"### {details['offer_title']}\n"
            f"**Offer:** {details['offer_description']}\n\n"
            f"🎁 **Welcome Promo Code:** `{details['promo_code']}` | ⏰ **Valid Until:** **{details['expiry_date']}** (Valid for 30 days)\n\n"
            f"⭐ **First Order Perks:** 5% Discount on your first order + Free Express Shipping on orders reaching ₹999.\n\n"
            f"🛡️ **Profit Protection:** Min Order: ₹{details['min_order_value']:,.0f} | Max Discount: ₹{details['max_discount_cap']:,.0f} | Net Margin Floor: Guaranteed ≥ 15%\n\n"
            f"*{details['simulation_note']}*"
        )

    # Customer Specific Financial Guardrails Summary
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander(f"🛡️ Financial Safeguards & Referral Program for Customer {selected_customer_id}", expanded=False):
        g_col1, g_col2, g_col3 = st.columns(3)
        with g_col1:
            st.markdown(
                f"""
                <strong>Financial Guardrails:</strong><br>
                - Promo Discount Rate: <strong>{profit_rules['discount_rate']}</strong><br>
                - Min Order Value (MOV): <strong>₹{profit_rules['min_order_value']:,.0f}</strong><br>
                - Max Discount Cap: <strong>₹{profit_rules['max_discount_cap']:,.0f}</strong><br>
                - Net Margin Floor: <strong>{profit_rules['margin_floor_pct']}</strong>
                """,
                unsafe_allow_html=True
            )
        with g_col2:
            st.markdown(
                f"""
                <strong>Shipping & Delivery:</strong><br>
                - Status: <strong>{details.get('free_shipping_status', 'Standard Express')}</strong><br>
                - Policy: <strong>{profit_rules['shipping_policy']}</strong><br>
                - Free Shipping Threshold: <strong>₹999.00</strong>
                """,
                unsafe_allow_html=True
            )
        with g_col3:
            st.markdown(
                f"""
                <strong>Referral Rewards Program:</strong><br>
                - Referral Code: <code>{referral['referral_code']}</code><br>
                - Reward: <strong>{referral['reward_points']} Points (₹{referral['reward_value_inr']:,.0f})</strong><br>
                - Friend Perk: <strong>{referral['friend_discount']}</strong>
                """,
                unsafe_allow_html=True
            )

    # Product Recommendations Sections
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader(f"🛍️ Personalized Product Recommendations for Customer {selected_customer_id}")

    tab_titles = []
    if cust_segment == "VIP Customer":
        tab_titles = ["✨ VIP Early-Access New Arrivals", "🎯 Category Recommendations", "⭐ Popular Products", "📜 Purchase History"]
    elif cust_segment == "Regular Customer":
        tab_titles = ["🔁 Frequently Purchased Products", "🎯 Recommended Categories", "⭐ Popular Bestsellers", "📜 Past Orders"]
    elif cust_segment == "Occasional Customer":
        tab_titles = ["🏷️ Selected 5% Discount Items", "📦 Curated Combo Offers", "🎯 Products Related to Past Orders", "📜 Past Purchases"]
    elif cust_segment == "At Risk":
        tab_titles = ["🔁 Buy It Again (Purchase History)", "🔥 Trending Products", "🏷️ Discounted Comeback Products", "📜 Full Purchase History"]
    elif cust_segment == "New Customer":
        tab_titles = ["🔥 Trending Products", "⭐ Best-Selling Products", "🎯 Category Recommendations", "📜 Order Details"]
    else:
        tab_titles = ["🎯 Category Recommendations", "⭐ Popular Products", "📜 Purchase History"]

    tabs = st.tabs(tab_titles)

    # 1. VIP Customer Tabs
    if cust_segment == "VIP Customer":
        # Tab 1: Early-Access
        with tabs[0]:
            st.markdown("##### 🚀 Early-Access: Recently Introduced Products")
            st.caption("Exclusive VIP access to new product catalog arrivals, identified by earliest date in `shop.db`.")
            early_df = details["early_access_products"]
            st.dataframe(
                early_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "StockCode": st.column_config.TextColumn("Product Code"),
                    "Description": st.column_config.TextColumn("Product Name"),
                    "OrdersCount": st.column_config.NumberColumn("Total Orders", format="%d"),
                    "TotalQuantity": st.column_config.NumberColumn("Total Sold", format="%d units"),
                    "AvgPrice": st.column_config.NumberColumn("Unit Price (₹)", format="₹%.2f"),
                    "FirstSeen": st.column_config.DatetimeColumn("Introduced On", format="YYYY-MM-DD")
                }
            )

        # Tab 2: Category Recs
        with tabs[1]:
            st.markdown("##### 🎯 Recommended Based on Past Preferred Categories")
            st.caption("Personalized catalog recommendations matched with your past high-spend category groups.")
            st.dataframe(
                details["category_recommendations"],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "StockCode": st.column_config.TextColumn("Product Code"),
                    "Description": st.column_config.TextColumn("Product Name"),
                    "OrdersCount": st.column_config.NumberColumn("Total Orders", format="%d"),
                    "TotalQuantity": st.column_config.NumberColumn("Total Sold", format="%d units"),
                    "AvgPrice": st.column_config.NumberColumn("Unit Price (₹)", format="₹%.2f")
                }
            )

        # Tab 3: Popular
        with tabs[2]:
            st.markdown("##### ⭐ Top Bestsellers Overall")
            st.dataframe(
                details["popular_recommendations"],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "StockCode": st.column_config.TextColumn("Product Code"),
                    "Description": st.column_config.TextColumn("Product Name"),
                    "OrdersCount": st.column_config.NumberColumn("Total Orders", format="%d"),
                    "TotalQuantity": st.column_config.NumberColumn("Total Sold", format="%d units"),
                    "AvgPrice": st.column_config.NumberColumn("Unit Price (₹)", format="₹%.2f")
                }
            )

        # Tab 4: History
        with tabs[3]:
            st.markdown("##### 📜 Customer Purchase History")
            st.dataframe(
                details["history"],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "StockCode": st.column_config.TextColumn("Product Code"),
                    "Description": st.column_config.TextColumn("Product Name"),
                    "OrdersCount": st.column_config.NumberColumn("Times Ordered", format="%d"),
                    "TotalQuantity": st.column_config.NumberColumn("Units Bought", format="%d"),
                    "AvgPrice": st.column_config.NumberColumn("Avg Price (₹)", format="₹%.2f"),
                    "TotalSpent": st.column_config.NumberColumn("Total Spent (₹)", format="₹%.2f")
                }
            )

    # 2. Regular Customer Tabs
    elif cust_segment == "Regular Customer":
        # Tab 1: Frequently Purchased Products
        with tabs[0]:
            st.markdown("##### 🔁 Frequently Purchased Products")
            st.caption("Products you purchase most frequently in CustomerHub for quick re-ordering.")
            freq_df = details.get("frequently_purchased", details["history"])
            st.dataframe(
                freq_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "StockCode": st.column_config.TextColumn("Product Code"),
                    "Description": st.column_config.TextColumn("Product Name"),
                    "OrdersCount": st.column_config.NumberColumn("Times Ordered", format="%d"),
                    "TotalQuantity": st.column_config.NumberColumn("Units Bought", format="%d"),
                    "AvgPrice": st.column_config.NumberColumn("Avg Price (₹)", format="₹%.2f"),
                    "TotalSpent": st.column_config.NumberColumn("Total Spent (₹)", format="₹%.2f")
                }
            )

        # Tab 2: Recommended Categories
        with tabs[1]:
            st.markdown("##### 🎯 Recommended from Frequently Purchased Product Groups")
            st.caption("Items in your favorite categories that you have not bought yet.")
            st.dataframe(
                details["category_recommendations"],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "StockCode": st.column_config.TextColumn("Product Code"),
                    "Description": st.column_config.TextColumn("Product Name"),
                    "OrdersCount": st.column_config.NumberColumn("Total Orders", format="%d"),
                    "TotalQuantity": st.column_config.NumberColumn("Total Sold", format="%d units"),
                    "AvgPrice": st.column_config.NumberColumn("Unit Price (₹)", format="₹%.2f")
                }
            )

        # Tab 3: Popular
        with tabs[2]:
            st.markdown("##### ⭐ Popular Bestsellers Across India")
            st.dataframe(
                details["popular_recommendations"],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "StockCode": st.column_config.TextColumn("Product Code"),
                    "Description": st.column_config.TextColumn("Product Name"),
                    "OrdersCount": st.column_config.NumberColumn("Total Orders", format="%d"),
                    "TotalQuantity": st.column_config.NumberColumn("Total Sold", format="%d units"),
                    "AvgPrice": st.column_config.NumberColumn("Unit Price (₹)", format="₹%.2f")
                }
            )

        # Tab 4: Past Orders
        with tabs[3]:
            st.markdown("##### 📜 Past Orders History")
            st.dataframe(
                details["history"],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "StockCode": st.column_config.TextColumn("Product Code"),
                    "Description": st.column_config.TextColumn("Product Name"),
                    "OrdersCount": st.column_config.NumberColumn("Times Ordered", format="%d"),
                    "TotalQuantity": st.column_config.NumberColumn("Units Bought", format="%d"),
                    "AvgPrice": st.column_config.NumberColumn("Avg Price (₹)", format="₹%.2f"),
                    "TotalSpent": st.column_config.NumberColumn("Total Spent (₹)", format="₹%.2f")
                }
            )

    # 3. Occasional Customer Tabs
    elif cust_segment == "Occasional Customer":
        # Tab 1: Selected 5% Discount Items
        with tabs[0]:
            st.markdown("##### 🏷️ Selected Products Eligible for 5% Discount")
            st.caption("Curated margin-healthy products eligible for promo code `OCCASIONAL5`.")
            st.dataframe(
                details["category_recommendations"],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "StockCode": st.column_config.TextColumn("Product Code"),
                    "Description": st.column_config.TextColumn("Product Name"),
                    "OrdersCount": st.column_config.NumberColumn("Total Orders", format="%d"),
                    "TotalQuantity": st.column_config.NumberColumn("Total Sold", format="%d units"),
                    "AvgPrice": st.column_config.NumberColumn("Unit Price (₹)", format="₹%.2f")
                }
            )

        # Tab 2: Curated Combo Offers
        with tabs[1]:
            st.markdown("##### 📦 Curated Combo Offers (Save 6% to 9%)")
            st.caption("Bundle these popular products together to unlock instant combo savings.")
            c_cols = st.columns(2)
            for idx, combo in enumerate(details["combos"]):
                with c_cols[idx % 2]:
                    st.markdown(
                        f"""
                        <div style="background-color: rgba(245, 158, 11, 0.08); border: 1px solid #F59E0B; padding: 12px; border-radius: 8px; margin-bottom: 12px;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <strong style="font-size: 1.05em; color: #D97706;">{combo['title']}</strong>
                                <span style="background: #F59E0B; color: #1E293B; font-weight: bold; font-size: 0.8em; padding: 2px 6px; border-radius: 4px;">{combo['discount_pct']} OFF</span>
                            </div>
                            <p style="margin: 4px 0; font-size: 0.88em; color: #4B5563;">{combo['description']}</p>
                            <p style="margin: 4px 0; font-size: 0.85em;"><strong>Items:</strong> {', '.join(combo['items'])}</p>
                            <div style="margin-top: 6px;">
                                <span style="text-decoration: line-through; color: #9CA3AF; margin-right: 6px;">₹{combo['regular_price']:,.0f}</span>
                                <strong style="color: #059669; font-size: 1.1em;">₹{combo['combo_price']:,.0f}</strong>
                                <span style="color: #10B981; font-size: 0.9em; margin-left: 6px;">(Save ₹{combo['savings']:,.0f})</span>
                            </div>
                            <div style="margin-top: 4px; font-size: 0.8em; color: #6B7280;">
                                Promo Code: <code>{combo['promo_code']}</code> | Profit: {combo['margin_after_discount']}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

        # Tab 3: Related to Past Purchases
        with tabs[2]:
            st.markdown("##### 🎯 Products Related to Your Past Purchases")
            st.dataframe(
                details["popular_recommendations"],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "StockCode": st.column_config.TextColumn("Product Code"),
                    "Description": st.column_config.TextColumn("Product Name"),
                    "OrdersCount": st.column_config.NumberColumn("Total Orders", format="%d"),
                    "TotalQuantity": st.column_config.NumberColumn("Total Sold", format="%d units"),
                    "AvgPrice": st.column_config.NumberColumn("Unit Price (₹)", format="₹%.2f")
                }
            )

        # Tab 4: Past Purchases
        with tabs[3]:
            st.markdown("##### 📜 Your Past Purchases")
            st.dataframe(
                details["history"],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "StockCode": st.column_config.TextColumn("Product Code"),
                    "Description": st.column_config.TextColumn("Product Name"),
                    "OrdersCount": st.column_config.NumberColumn("Times Ordered", format="%d"),
                    "TotalQuantity": st.column_config.NumberColumn("Units Bought", format="%d"),
                    "AvgPrice": st.column_config.NumberColumn("Avg Price (₹)", format="₹%.2f"),
                    "TotalSpent": st.column_config.NumberColumn("Total Spent (₹)", format="₹%.2f")
                }
            )

    # 4. At Risk Customer Tabs
    elif cust_segment == "At Risk":
        # Tab 1: Buy It Again
        with tabs[0]:
            st.markdown("##### 🔁 Buy It Again (Previously Purchased Products)")
            st.caption("Re-order your favorite past items with your 10% comeback discount!")
            st.dataframe(
                details.get("buy_again_products", details["history"]),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "StockCode": st.column_config.TextColumn("Product Code"),
                    "Description": st.column_config.TextColumn("Product Name"),
                    "OrdersCount": st.column_config.NumberColumn("Times Ordered", format="%d"),
                    "TotalQuantity": st.column_config.NumberColumn("Units Bought", format="%d"),
                    "AvgPrice": st.column_config.NumberColumn("Avg Price (₹)", format="₹%.2f"),
                    "TotalSpent": st.column_config.NumberColumn("Total Spent (₹)", format="₹%.2f")
                }
            )

        # Tab 2: Trending Products
        with tabs[1]:
            st.markdown("##### 🔥 Storewide Trending Products")
            st.caption("Top trending items with highest customer order volume across India.")
            st.dataframe(
                details["popular_recommendations"],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "StockCode": st.column_config.TextColumn("Product Code"),
                    "Description": st.column_config.TextColumn("Product Name"),
                    "OrdersCount": st.column_config.NumberColumn("Total Orders", format="%d"),
                    "TotalQuantity": st.column_config.NumberColumn("Total Sold", format="%d units"),
                    "AvgPrice": st.column_config.NumberColumn("Unit Price (₹)", format="₹%.2f")
                }
            )

        # Tab 3: Discounted Comeback Products
        with tabs[2]:
            st.markdown("##### 🏷️ Discounted Comeback Products (10% Off)")
            st.caption("High-margin items eligible for code `COMEBACK10` with verified >20% net company profit.")
            disc_df = details.get("discounted_products", get_discounted_comeback_products(limit=6))
            st.dataframe(
                disc_df[["StockCode", "Description", "AvgPrice", "ComebackPrice", "Savings", "Discount", "ProfitStatus"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "StockCode": st.column_config.TextColumn("Product Code"),
                    "Description": st.column_config.TextColumn("Product Name"),
                    "AvgPrice": st.column_config.NumberColumn("Regular Price (₹)", format="₹%.2f"),
                    "ComebackPrice": st.column_config.NumberColumn("Comeback Price (₹)", format="₹%.2f"),
                    "Savings": st.column_config.NumberColumn("Savings (₹)", format="₹%.2f"),
                    "Discount": st.column_config.TextColumn("Discount"),
                    "ProfitStatus": st.column_config.TextColumn("Profit Safeguard")
                }
            )

        # Tab 4: Full History
        with tabs[3]:
            st.markdown("##### 📜 Full Purchase History")
            st.dataframe(
                details["history"],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "StockCode": st.column_config.TextColumn("Product Code"),
                    "Description": st.column_config.TextColumn("Product Name"),
                    "OrdersCount": st.column_config.NumberColumn("Times Ordered", format="%d"),
                    "TotalQuantity": st.column_config.NumberColumn("Units Bought", format="%d"),
                    "AvgPrice": st.column_config.NumberColumn("Avg Price (₹)", format="₹%.2f"),
                    "TotalSpent": st.column_config.NumberColumn("Total Spent (₹)", format="₹%.2f")
                }
            )

    # 5. New Customer Tabs
    elif cust_segment == "New Customer":
        # Tab 1: Trending Products
        with tabs[0]:
            st.markdown("##### 🔥 Trending Products (Highest Volume Sold)")
            st.caption("Top trending catalog products based on total units ordered across India.")
            trend_df = details.get("trending_products", get_popular_products(limit=6, sort_by="TotalQuantity"))
            st.dataframe(
                trend_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "StockCode": st.column_config.TextColumn("Product Code"),
                    "Description": st.column_config.TextColumn("Product Name"),
                    "OrdersCount": st.column_config.NumberColumn("Total Orders", format="%d"),
                    "TotalQuantity": st.column_config.NumberColumn("Total Sold", format="%d units"),
                    "AvgPrice": st.column_config.NumberColumn("Unit Price (₹)", format="₹%.2f")
                }
            )

        # Tab 2: Best-Selling Products
        with tabs[1]:
            st.markdown("##### ⭐ Best-Selling Products Across India")
            st.caption("Most popular store products ranked by distinct order invoice count.")
            best_df = details.get("bestseller_products", get_popular_products(limit=6, sort_by="OrdersCount"))
            st.dataframe(
                best_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "StockCode": st.column_config.TextColumn("Product Code"),
                    "Description": st.column_config.TextColumn("Product Name"),
                    "OrdersCount": st.column_config.NumberColumn("Total Orders", format="%d"),
                    "TotalQuantity": st.column_config.NumberColumn("Total Sold", format="%d units"),
                    "AvgPrice": st.column_config.NumberColumn("Unit Price (₹)", format="₹%.2f")
                }
            )

        # Tab 3: Category Recs
        with tabs[2]:
            st.markdown("##### 🎯 Category Recommendations")
            st.caption("Recommended items in categories matching your first purchase.")
            st.dataframe(
                details["category_recommendations"],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "StockCode": st.column_config.TextColumn("Product Code"),
                    "Description": st.column_config.TextColumn("Product Name"),
                    "OrdersCount": st.column_config.NumberColumn("Total Orders", format="%d"),
                    "TotalQuantity": st.column_config.NumberColumn("Total Sold", format="%d units"),
                    "AvgPrice": st.column_config.NumberColumn("Unit Price (₹)", format="₹%.2f")
                }
            )

        # Tab 4: Order Details
        with tabs[3]:
            st.markdown("##### 📜 First Order Details")
            st.dataframe(
                details["history"],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "StockCode": st.column_config.TextColumn("Product Code"),
                    "Description": st.column_config.TextColumn("Product Name"),
                    "OrdersCount": st.column_config.NumberColumn("Times Ordered", format="%d"),
                    "TotalQuantity": st.column_config.NumberColumn("Units Bought", format="%d"),
                    "AvgPrice": st.column_config.NumberColumn("Avg Price (₹)", format="₹%.2f"),
                    "TotalSpent": st.column_config.NumberColumn("Total Spent (₹)", format="₹%.2f")
                }
            )

    st.markdown("<br><hr>", unsafe_allow_html=True)

    # Master Offers Table Section
    st.subheader("📋 Master Customer Offers Table")

    table_filter_col1, table_filter_col2 = st.columns([1, 2])
    with table_filter_col1:
        tbl_segment = st.selectbox(
            "Filter Master Table by Segment:",
            options=["All Segments", "VIP Customer", "Regular Customer", "New Customer", "Occasional Customer", "At Risk"],
            index=0,
            key="tbl_segment_filter"
        )
    with table_filter_col2:
        tbl_search = st.text_input(
            "Search Customer ID in Table:",
            placeholder="e.g. CUST-1507",
            key="tbl_search_input"
        )

    # Filter Master Table
    offers_display = df[["CustomerID", "CustomerSegment", "Monetary", "Offer"]].copy()

    if tbl_segment != "All Segments":
        offers_display = offers_display[offers_display["CustomerSegment"] == tbl_segment]

    if tbl_search.strip():
        offers_display = offers_display[offers_display["CustomerID"].astype(str).str.contains(tbl_search.strip(), case=False)]

    st.markdown(f"Showing **{len(offers_display):,}** customer offers:")

    # Display Table showing CustomerID, CustomerSegment, Monetary, and Offer
    st.dataframe(
        offers_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "CustomerID": st.column_config.TextColumn(
                "Customer ID"
            ),
            "CustomerSegment": st.column_config.TextColumn(
                "Customer Segment"
            ),
            "Monetary": st.column_config.NumberColumn(
                "Monetary Spend (₹)",
                help="Total purchase amount in shop.db in INR",
                format="₹%.2f"
            ),
            "Offer": st.column_config.TextColumn(
                "Suggested Offer"
            )
        }
    )

    # Export Option
    csv_data = offers_display.to_csv(index=False)
    st.download_button(
        label="📥 Download Filtered Offers (CSV)",
        data=csv_data,
        file_name="customer_offers.csv",
        mime="text/csv"
    )


def main():
    # Load dataset with cached segmentation & offers
    try:
        df = load_data()
    except Exception as e:
        st.error(f"Failed to load customer data from database: {e}")
        st.stop()

    # Sidebar: Navigation & Guidance
    with st.sidebar:
        st.header("🛍️ CustomerHub")
        st.caption("E-Commerce Customer Analytics (India Retail)")
        st.markdown("---")

        st.subheader("🧭 Navigation")
        selected_page = st.radio(
            "Go to page:",
            options=[
                "📊 Dashboard Overview",
                "👤 Customer Profile",
                "🎁 Customer Offers & Recommendations"
            ],
            index=0
        )

        st.markdown("---")
        st.subheader("📌 Segment Definitions")
        st.markdown(
            """
            - **🎉 New Customer**: Customers who made a recent purchase or order (`R ≤ 30d`).
            - **🌟 VIP Customer**: Active buyers (`R ≤ 60d`) with high order frequency (`F ≥ 4`) or high total spend (`M ≥ ₹50,000`).
            - **🔄 Regular Customer**: Active returning buyers (`R ≤ 90d`) with multiple orders (`F ≥ 2`).
            - **⚠️ At Risk**: Inactive customers with no purchase in over 90 days (`R > 90d`).
            - **🛒 Occasional Customer**: Infrequent single-order or lower spend buyers.
            """
        )

        st.markdown("---")
        st.subheader("⚙️ Data Settings")
        if st.button("🔄 Refresh Data Cache"):
            st.cache_data.clear()
            st.rerun()

    # Render selected view
    if selected_page == "📊 Dashboard Overview":
        render_dashboard(df)
    elif selected_page == "👤 Customer Profile":
        render_customer_profile_page(df)
    else:
        render_offers_page(df)


if __name__ == "__main__":
    main()
