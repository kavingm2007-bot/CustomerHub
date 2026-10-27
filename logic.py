"""RFM (Recency, Frequency, Monetary) analysis and customer segmentation for CustomerHub.

Reads cleaned transaction data from SQLite database (shop.db),
computes RFM metrics, and segments customers using rule-based logic.
"""

import sys
import pandas as pd
from db import get_engine, TABLE_ORDERS


def get_orders_data() -> pd.DataFrame:
    """Read orders dataset from SQLite database using SQLAlchemy engine."""
    engine = get_engine()

    # Query columns for RFM calculation directly from SQLite
    try:
        query = f"SELECT CustomerID, CustomerName, InvoiceNo, InvoiceDate, Amount FROM {TABLE_ORDERS}"
        df = pd.read_sql(query, con=engine)
    except Exception:
        # Fallback if CustomerName is not present in legacy schema
        query = f"SELECT CustomerID, InvoiceNo, InvoiceDate, Amount FROM {TABLE_ORDERS}"
        df = pd.read_sql(query, con=engine)

    return df


def calculate_rfm(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate Recency, Frequency, and Monetary metrics for each customer.

    Parameters:
    - df: DataFrame containing CustomerID, InvoiceNo, InvoiceDate, Amount (and optional CustomerName).

    Returns:
    - DataFrame with columns: CustomerID, (CustomerName), Recency, Frequency, Monetary.
    """
    if df.empty:
        raise ValueError("The orders dataset is empty. Cannot compute RFM metrics.")

    # 1. Handle dates and missing values safely
    df = df.dropna(subset=["CustomerID", "InvoiceDate", "InvoiceNo", "Amount"]).copy()

    # Ensure CustomerID is string format (supports both CUST-XXXX and numeric IDs)
    df["CustomerID"] = df["CustomerID"].astype(str)

    # Convert InvoiceDate to datetime safely
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")
    df = df.dropna(subset=["InvoiceDate"])

    # 2. Reference Date: Latest InvoiceDate in dataset + 1 day
    latest_date = df["InvoiceDate"].max()
    reference_date = latest_date + pd.Timedelta(days=1)

    # 3. Group by CustomerID to calculate metrics
    agg_kwargs = {
        "LatestPurchase": ("InvoiceDate", "max"),
        "Frequency": ("InvoiceNo", "nunique"),
        "Monetary": ("Amount", "sum")
    }
    if "CustomerName" in df.columns:
        agg_kwargs["CustomerName"] = ("CustomerName", "first")

    rfm_grouped = df.groupby("CustomerID").agg(**agg_kwargs).reset_index()

    # 4. Recency: Number of days since customer's latest purchase
    rfm_grouped["Recency"] = (reference_date - rfm_grouped["LatestPurchase"]).dt.days

    # 5. Format and select output columns
    rfm_grouped["Monetary"] = rfm_grouped["Monetary"].round(2)
    select_cols = ["CustomerID"]
    if "CustomerName" in rfm_grouped.columns:
        select_cols.append("CustomerName")
    select_cols.extend(["Recency", "Frequency", "Monetary"])

    return rfm_grouped[select_cols].copy()


def assign_customer_segment(row: pd.Series) -> str:
    """Classify an individual customer using rule-based logic based on RFM values.

    Rules:
    1. New Customer:
       - Made a new purchase or order recently (Recency <= 30 days).
    2. VIP Customer:
       - Active buyer (Recency <= 60 days) with high activity:
         either frequent orders (Frequency >= 4) or high spend (Monetary >= ₹50,000).
    3. Regular Customer:
       - Active buyer (Recency <= 90 days) with repeated purchases (Frequency >= 2).
    4. At Risk:
       - Has not made any purchase in over 90 days (Recency > 90 days).
    5. Occasional Customer:
       - Infrequent buyer (single purchase or lower spend).
    """
    recency = row["Recency"]
    frequency = row["Frequency"]
    monetary = row["Monetary"]

    if recency <= 30:
        return "New Customer"
    elif recency <= 60 and (frequency >= 4 or monetary >= 50000):
        return "VIP Customer"
    elif recency <= 90 and frequency >= 2:
        return "Regular Customer"
    elif recency > 90:
        return "At Risk"
    else:
        return "Occasional Customer"


def segment_customers(rfm_df: pd.DataFrame) -> pd.DataFrame:
    """Add a CustomerSegment column to the RFM DataFrame using rule-based classification."""
    segmented_df = rfm_df.copy()
    segmented_df["CustomerSegment"] = segmented_df.apply(assign_customer_segment, axis=1)
    return segmented_df


def get_customer_transactions(customer_id: str | int) -> pd.DataFrame:
    """Retrieve all transaction records for a specific customer from shop.db.

    Sorted by InvoiceDate descending (newest first).
    Includes: InvoiceNo, InvoiceDate, StockCode, Description, Quantity, UnitPrice, Amount.
    """
    engine = get_engine()
    query = f"""
        SELECT InvoiceNo, InvoiceDate, StockCode, Description, Quantity, UnitPrice, Amount
        FROM {TABLE_ORDERS}
        WHERE CustomerID = '{customer_id}'
        ORDER BY InvoiceDate DESC
    """
    df = pd.read_sql(query, con=engine)
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")
    return df


def get_customer_profile(customer_id: str | int, rfm_df: pd.DataFrame | None = None) -> dict:
    """Calculate summary profile metrics for a specific customer from shop.db records.

    Calculates:
    - CustomerID
    - CustomerName (if present)
    - CustomerSegment (from rfm_df if provided)
    - Recency (from rfm_df if provided)
    - Frequency (distinct invoices, avoiding double-counting)
    - Monetary value (total spend)
    - Total quantity purchased
    - First purchase date
    - Most recent purchase date
    - Total line-item transaction count
    """
    engine = get_engine()
    try:
        query = f"""
            SELECT CustomerID,
                   MAX(CustomerName) AS CustomerName,
                   MIN(InvoiceDate) AS FirstPurchaseDate,
                   MAX(InvoiceDate) AS LastPurchaseDate,
                   SUM(Quantity) AS TotalQuantity,
                   ROUND(SUM(Amount), 2) AS Monetary,
                   COUNT(DISTINCT InvoiceNo) AS Frequency,
                   COUNT(*) AS TotalTransactions
            FROM {TABLE_ORDERS}
            WHERE CustomerID = '{customer_id}'
        """
        res = pd.read_sql(query, con=engine)
    except Exception:
        query = f"""
            SELECT CustomerID,
                   MIN(InvoiceDate) AS FirstPurchaseDate,
                   MAX(InvoiceDate) AS LastPurchaseDate,
                   SUM(Quantity) AS TotalQuantity,
                   ROUND(SUM(Amount), 2) AS Monetary,
                   COUNT(DISTINCT InvoiceNo) AS Frequency,
                   COUNT(*) AS TotalTransactions
            FROM {TABLE_ORDERS}
            WHERE CustomerID = '{customer_id}'
        """
        res = pd.read_sql(query, con=engine)

    if res.empty or pd.isna(res.iloc[0]["CustomerID"]):
        raise ValueError(f"Customer #{customer_id} not found in database.")

    row = res.iloc[0]
    first_dt = pd.to_datetime(row["FirstPurchaseDate"], errors="coerce")
    last_dt = pd.to_datetime(row["LastPurchaseDate"], errors="coerce")

    segment = "Unknown"
    recency = 0
    cust_name = str(row.get("CustomerName") or "")
    if rfm_df is not None:
        match = rfm_df[rfm_df["CustomerID"].astype(str) == str(customer_id)]
        if not match.empty:
            segment = match.iloc[0].get("CustomerSegment", "Unknown")
            recency = int(match.iloc[0].get("Recency", 0))
            if not cust_name:
                cust_name = str(match.iloc[0].get("CustomerName", ""))

    return {
        "CustomerID": str(row["CustomerID"]),
        "CustomerName": cust_name,
        "CustomerSegment": segment,
        "Recency": recency,
        "Frequency": int(row["Frequency"]),
        "Monetary": float(row["Monetary"]),
        "TotalQuantity": int(row["TotalQuantity"]),
        "FirstPurchaseDate": first_dt,
        "MostRecentPurchaseDate": last_dt,
        "TotalTransactions": int(row["TotalTransactions"]),
    }


def main():
    """Main execution function for RFM analysis and customer segmentation."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 70)
    print("CustomerHub: RFM Analysis & Rule-Based Customer Segmentation")
    print("=" * 70)
    print("Fetching transaction records from SQLite database (shop.db)...")

    orders_df = get_orders_data()
    print(f"Loaded {len(orders_df):,} transaction records.")

    # 1. Compute RFM
    print("\nCalculating RFM metrics for each customer...")
    try:
        rfm_df = calculate_rfm(orders_df)
    except Exception as e:
        print(f"\n[ERROR] RFM calculation failed: {e}")
        sys.exit(1)

    print(f"Successfully calculated RFM values for {len(rfm_df):,} unique customers.")

    # 2. Segment Customers
    print("Applying rule-based customer segmentation (including New Customer)...")
    segmented_df = segment_customers(rfm_df)

    # 3. Display Segment Counts Summary
    print("\n" + "=" * 70)
    print("CUSTOMER SEGMENTATION SUMMARY")
    print("=" * 70)
    counts = segmented_df["CustomerSegment"].value_counts()
    total = len(segmented_df)
    print(f"{'Customer Segment':<25} | {'Count':<10} | {'Percentage':<12}")
    print("-" * 70)
    for segment_name, count in counts.items():
        pct = (count / total) * 100
        print(f"{segment_name:<25} | {count:<10,} | {pct:>6.1f}%")
    print("-" * 70)
    print(f"{'Total Customers':<25} | {total:<10,} | {'100.0%':>7}")
    print("=" * 70)

    # 4. Display the first 10 customers with segments
    print("\n" + "=" * 80)
    print("FIRST 10 CUSTOMERS (RFM & SEGMENTS)")
    print("=" * 80)
    header = f"{'CustomerID':<14} | {'Recency (d)':<12} | {'Frequency':<10} | {'Monetary (₹)':<16} | {'CustomerSegment':<20}"
    print(header)
    print("-" * len(header))
    for _, row in segmented_df.head(10).iterrows():
        print(
            f"{str(row['CustomerID']):<14} | "
            f"{int(row['Recency']):<12} | "
            f"{int(row['Frequency']):<10} | "
            f"₹{row['Monetary']:>14,.2f} | "
            f"{row['CustomerSegment']:<20}"
        )
    print("=" * 80)


if __name__ == "__main__":
    main()
