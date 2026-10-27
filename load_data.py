"""Data loading and cleaning script for CustomerHub.

Reads the India Retail Sales dataset (india_retail_sales_dataset.csv), cleans the records,
and loads the data into the SQLite database (shop.db).
"""

import os
import sys
from pathlib import Path
import pandas as pd
from sqlalchemy import text

# Import database utilities from db.py
from db import get_engine, get_db_path, TABLE_ORDERS

# ==============================================================================
# CONFIGURATION
# Default dataset filename (India Retail Sales dataset)
# Example: python load_data.py "india_retail_sales_dataset.csv"
# ==============================================================================
DEFAULT_DATA_PATH = "india_retail_sales_dataset.csv"


def get_data_path() -> Path:
    """Determine the dataset file path from CLI argument, environment variable, or default."""
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).resolve()

    # Check if configured via environment variable
    env_path = os.getenv("ONLINE_RETAIL_DATA_PATH") or os.getenv("ONLINE_RETAIL_CSV_PATH")
    if env_path:
        return Path(env_path).resolve()

    # Fallback to default path, or look for standard alternatives in current working directory
    default_path = Path(DEFAULT_DATA_PATH).resolve()
    if default_path.exists():
        return default_path

    for candidate in ["india_retail_sales_dataset.csv", "Online Retail.xlsx", "Online Retail.xls", "Online Retail.csv", "online_retail.csv"]:
        candidate_path = Path(candidate).resolve()
        if candidate_path.exists():
            return candidate_path

    return default_path


def read_csv_safely(file_path: Path) -> pd.DataFrame:
    """Read CSV file using pandas read_csv() with fallback encodings."""
    encodings = ["utf-8", "ISO-8859-1", "cp1252"]
    for enc in encodings:
        try:
            return pd.read_csv(file_path, encoding=enc)
        except UnicodeDecodeError:
            continue
        except pd.errors.EmptyDataError:
            raise ValueError(f"The CSV file at '{file_path}' is empty.")

    # Fallback with replacement characters if all standard attempts fail
    return pd.read_csv(file_path, encoding="utf-8", encoding_errors="replace")


def load_dataset(file_path: Path) -> pd.DataFrame:
    """Read dataset from CSV or Excel file based on extension.
    
    Requirements:
    - If file ends with .csv, read it using pandas read_csv().
    - If file ends with .xlsx or .xls, read it using pandas read_excel().
    - If unsupported format, raise ValueError with a clear message.
    """
    if not file_path.exists():
        raise FileNotFoundError(
            f"File not found at: {file_path}\n"
            f"Please ensure '{file_path.name}' is placed in the project folder or specify the correct path."
        )

    file_name = file_path.name.lower()

    if file_name.endswith(".csv"):
        return read_csv_safely(file_path)
    elif file_name.endswith((".xlsx", ".xls")):
        return pd.read_excel(file_path)
    else:
        raise ValueError(
            f"Unsupported file format for '{file_path.name}'.\n"
            f"Supported file formats are CSV (.csv) and Excel (.xlsx, .xls)."
        )


def clean_retail_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean the raw retail dataset according to business requirements.
    
    Supports both India Retail Sales Dataset (india_retail_sales_dataset.csv)
    and legacy Online Retail dataset.
    """
    # Detect India Retail Sales Dataset columns
    if "Customer ID" in df.columns and "Order ID" in df.columns:
        # 1. Drop records missing key identification fields
        cleaned = df.dropna(subset=["Customer ID", "Order ID", "Order Date", "Sales", "Quantity"]).copy()

        # 2. Filter out returned orders if Returned column exists
        if "Returned" in cleaned.columns:
            cleaned = cleaned[cleaned["Returned"].astype(str).str.strip().str.lower() != "yes"]

        # 3. Clean Quantity and ensure positive
        cleaned["Quantity"] = pd.to_numeric(cleaned["Quantity"], errors="coerce").fillna(0).astype(int)
        cleaned = cleaned[cleaned["Quantity"] > 0]

        # 4. Clean Sales (Amount in INR)
        sales_str = cleaned["Sales"].astype(str).str.replace(",", "", regex=False)
        cleaned["Amount"] = pd.to_numeric(sales_str, errors="coerce").round(2)
        cleaned = cleaned[cleaned["Amount"] > 0]

        # 5. Clean List Price (UnitPrice in INR)
        if "List Price" in cleaned.columns:
            lp_str = cleaned["List Price"].astype(str).str.replace(",", "", regex=False)
            cleaned["UnitPrice"] = pd.to_numeric(lp_str, errors="coerce").round(2)
        else:
            cleaned["UnitPrice"] = (cleaned["Amount"] / cleaned["Quantity"]).round(2)

        # 6. Parse Order Date into InvoiceDate (DD-MM-YYYY format)
        cleaned["InvoiceDate"] = pd.to_datetime(cleaned["Order Date"], format="%d-%m-%Y", errors="coerce")
        # Fallback to general parsing if any NaT
        if cleaned["InvoiceDate"].isna().any():
            cleaned["InvoiceDate"] = cleaned["InvoiceDate"].fillna(pd.to_datetime(cleaned["Order Date"], errors="coerce"))
        cleaned = cleaned.dropna(subset=["InvoiceDate"])

        # 7. Map standard fields for CustomerHub compatibility
        cleaned["CustomerID"] = cleaned["Customer ID"].astype(str).str.strip()
        cleaned["InvoiceNo"] = cleaned["Order ID"].astype(str).str.strip()
        cleaned["Description"] = cleaned["Product Name"].astype(str).str.strip() if "Product Name" in cleaned.columns else "Product"
        cleaned["CustomerName"] = cleaned["Customer Name"].astype(str).str.strip() if "Customer Name" in cleaned.columns else cleaned["CustomerID"]

        # 8. Generate standard product code (StockCode) from distinct products
        unique_products = sorted(cleaned["Description"].dropna().unique())
        prod_code_map = {name: f"IND-{i+1:03d}" for i, name in enumerate(unique_products)}
        cleaned["StockCode"] = cleaned["Description"].map(prod_code_map)

        # 9. Geography & categories
        cleaned["Country"] = "India"
        if "City" in cleaned.columns:
            cleaned["City"] = cleaned["City"].astype(str).str.strip()
        if "State" in cleaned.columns:
            cleaned["State"] = cleaned["State"].astype(str).str.strip()
        if "Category" in cleaned.columns:
            cleaned["Category"] = cleaned["Category"].astype(str).str.strip()
        if "Sub-Category" in cleaned.columns:
            cleaned["SubCategory"] = cleaned["Sub-Category"].astype(str).str.strip()
        if "Payment Mode" in cleaned.columns:
            cleaned["PaymentMode"] = cleaned["Payment Mode"].astype(str).str.strip()

        # Select standard columns and additional metadata
        standard_cols = [
            "InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate",
            "UnitPrice", "CustomerID", "CustomerName", "Country", "Amount"
        ]
        extra_cols = [c for c in ["City", "State", "Category", "SubCategory", "PaymentMode"] if c in cleaned.columns]
        return cleaned[standard_cols + extra_cols].copy()

    # Legacy Online Retail format
    required_columns = {"CustomerID", "Quantity", "UnitPrice", "InvoiceDate"}
    missing_cols = required_columns - set(df.columns)
    if missing_cols:
        raise ValueError(
            f"The input dataset is missing required column(s): {', '.join(sorted(missing_cols))}.\n"
            f"Found columns: {', '.join(df.columns)}"
        )

    # 1. Remove rows where CustomerID is missing
    cleaned = df.dropna(subset=["CustomerID"]).copy()

    # Convert CustomerID to string format to support various ID styles
    cleaned["CustomerID"] = cleaned["CustomerID"].astype(int).astype(str)

    # 2. Remove rows where Quantity <= 0
    cleaned = cleaned[cleaned["Quantity"] > 0]

    # 3. Remove rows where UnitPrice <= 0
    cleaned = cleaned[cleaned["UnitPrice"] > 0]

    # 4. Convert InvoiceDate to datetime format
    cleaned["InvoiceDate"] = pd.to_datetime(cleaned["InvoiceDate"], errors="coerce")
    
    # Drop rows if any InvoiceDate could not be parsed
    cleaned = cleaned.dropna(subset=["InvoiceDate"])

    # 5. Create a new column named Amount using Quantity * UnitPrice
    cleaned["Amount"] = (cleaned["Quantity"] * cleaned["UnitPrice"]).round(2)

    return cleaned


def import_data_to_db(df: pd.DataFrame, table_name: str = TABLE_ORDERS) -> int:
    """Insert the cleaned dataframe into the SQLite database.
    
    Replaces existing table if script is run again to prevent duplicates.
    """
    engine = get_engine()

    # if_exists='replace' drops the existing table and re-creates it
    df.to_sql(
        name=table_name,
        con=engine,
        if_exists="replace",
        index=False,
        chunksize=10000,
    )

    # Verify rows in database
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        inserted_count = result.scalar()

    return int(inserted_count)


def main():
    """Main execution function."""
    data_path = get_data_path()
    print("=" * 60)
    print("CustomerHub: India Retail Sales Data Importer")
    print("=" * 60)
    print(f"Reading dataset from: {data_path}")

    # 1. Read dataset (CSV or Excel)
    try:
        raw_df = load_dataset(data_path)
    except FileNotFoundError as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Failed to read dataset: {e}")
        sys.exit(1)

    original_rows = len(raw_df)
    print(f"Successfully loaded {original_rows:,} raw records.")

    # 2. Clean Data
    print("Cleaning data...")
    try:
        cleaned_df = clean_retail_data(raw_df)
    except Exception as e:
        print(f"\n[ERROR] Data cleaning failed: {e}")
        sys.exit(1)

    cleaned_rows = len(cleaned_df)

    if cleaned_rows == 0:
        print("\n[ERROR] No valid rows remained after data cleaning.")
        sys.exit(1)

    # 3. Import to Database
    print(f"Importing {cleaned_rows:,} cleaned records into database...")
    try:
        inserted_rows = import_data_to_db(cleaned_df, TABLE_ORDERS)
    except Exception as e:
        print(f"\n[ERROR] Database import failed: {e}")
        sys.exit(1)

    # 4. Print Summary Information
    print("\n" + "=" * 60)
    print("IMPORT SUMMARY")
    print("=" * 60)
    print(f"Original number of rows:             {original_rows:,}")
    print(f"Number of rows after cleaning:       {cleaned_rows:,}")
    print(f"Number of rows inserted into DB:     {inserted_rows:,}")
    print(f"Database file location:              {get_db_path()}")
    print(f"Table name:                          {TABLE_ORDERS}")
    print("=" * 60)
    print("Data imported successfully!\n")


if __name__ == "__main__":
    main()
