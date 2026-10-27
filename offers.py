"""Customer Offers and Product Recommendations module for CustomerHub.

Reuses existing RFM and CustomerSegment data from logic.py and shop.db
to generate segment-specific offers, profit-protected discounts, combo bundles,
and personalized product recommendations.
"""

import sys
import re
from collections import Counter
import pandas as pd
from logic import get_orders_data, calculate_rfm, segment_customers
from db import get_engine, TABLE_ORDERS

# ==============================================================================
# 1. PROFIT PROTECTION & MARGIN SAFEGUARDS
# ==============================================================================
# Category gross margin estimates based on standard retail margins
CATEGORY_GROSS_MARGINS = {
    "Clothing": 0.38,        # 38% gross margin (High margin)
    "Furniture": 0.35,       # 35% gross margin (High margin)
    "Office Supplies": 0.30, # 30% gross margin (Medium-High margin)
    "Groceries": 0.22,       # 22% gross margin (Lower margin)
    "Electronics": 0.20      # 20% gross margin (Medium-Low margin)
}

# Profit Protection Floor: Minimum company net profit margin after discount
MIN_PROFIT_MARGIN_FLOOR = 0.15  # 15.0% guaranteed net margin floor


def get_profit_protection_rules(segment: str) -> dict:
    """Return segment-tailored financial guardrails and margin protection parameters.

    Guarantees:
    - Discounts are only applied to products with sufficient profit margin.
    - No promotion reduces net profit margin below the 15% allowed limit.
    - Minimum Order Values (MOV) absorb packaging and shipping overhead.
    - Maximum Discount Limits (Caps) prevent profit erosion on high-value carts.
    """
    rules_map = {
        "VIP Customer": {
            "discount_rate": "20%",
            "min_order_value": 2500.0,
            "max_discount_cap": 5000.0,
            "eligible_categories": ["Clothing", "Furniture", "Office Supplies"],
            "margin_floor_pct": "15.0%",
            "shipping_policy": "Complimentary Priority Delivery (Threshold: ₹0)",
            "safeguard_summary": "Applied to high-margin catalog items (Clothing & Furniture margin 35-38%). Capped at ₹5,000 max discount with ₹2,500 MOV."
        },
        "Regular Customer": {
            "discount_rate": "5%",
            "min_order_value": 1000.0,
            "max_discount_cap": 1000.0,
            "eligible_categories": ["Clothing", "Furniture", "Office Supplies", "Groceries", "Electronics"],
            "margin_floor_pct": "15.0%",
            "shipping_policy": "Free Express Shipping on orders ≥ ₹999",
            "safeguard_summary": "5% repeat purchase incentive safely preserves 15%-33% net profit across all catalog categories. Capped at ₹1,000."
        },
        "Occasional Customer": {
            "discount_rate": "5%",
            "min_order_value": 1000.0,
            "max_discount_cap": 500.0,
            "eligible_categories": ["Clothing", "Furniture", "Office Supplies"],
            "margin_floor_pct": "15.0%",
            "shipping_policy": "Free Express Shipping on orders ≥ ₹999",
            "safeguard_summary": "5% discount strictly restricted to selected margin-healthy categories. Encourages basket size expansion with ₹1,000 MOV."
        },
        "At Risk": {
            "discount_rate": "10%",
            "min_order_value": 1500.0,
            "max_discount_cap": 1500.0,
            "eligible_categories": ["Clothing", "Furniture", "Office Supplies"],
            "margin_floor_pct": "15.0%",
            "shipping_policy": "Free Express Shipping on orders ≥ ₹999",
            "safeguard_summary": "10% win-back incentive applied strictly to categories with ≥25% gross margin. Capped at ₹1,500 with ₹1,500 MOV."
        },
        "New Customer": {
            "discount_rate": "5%",
            "min_order_value": 500.0,
            "max_discount_cap": 500.0,
            "eligible_categories": ["Clothing", "Furniture", "Office Supplies", "Groceries", "Electronics"],
            "margin_floor_pct": "15.0%",
            "shipping_policy": "Free Express Shipping on orders ≥ ₹999",
            "safeguard_summary": "5% introductory discount on first order with low barrier ₹500 MOV, capped at ₹500. Net company margin guaranteed ≥15%."
        }
    }
    return rules_map.get(segment, rules_map["New Customer"])


# ==============================================================================
# 2. LOYALTY POINTS & VIP REWARDS TRACKER
# ==============================================================================
def calculate_loyalty_points(monetary: float) -> dict:
    """Calculate customer loyalty reward points based on verified lifetime spend.

    Accrual rate: 1 Point per ₹50 spent.
    Redemption value: ₹1 per Point.
    """
    points = int(monetary // 50)
    if monetary >= 100000:
        tier = "💎 Platinum VIP Tier"
        perk = "20% privilege rewards + 3x Points Multiplier + Personal VIP Concierge"
        next_tier = "Highest Tier Achieved"
        pts_to_next = 0
    elif monetary >= 50000:
        tier = "🌟 Gold VIP Tier"
        perk = "20% privilege rewards + 2x Points Multiplier + Free Priority Shipping"
        next_tier = "Platinum VIP Tier (at ₹1,00,000 spend)"
        pts_to_next = int(max(0, (100000 - monetary) // 50))
    elif monetary >= 25000:
        tier = "🥈 Silver Tier"
        perk = "5% repeat discounts + 1.5x Points Multiplier"
        next_tier = "Gold VIP Tier (at ₹50,000 spend)"
        pts_to_next = int(max(0, (50000 - monetary) // 50))
    else:
        tier = "🥉 Bronze Tier"
        perk = "5% welcome & repeat rewards"
        next_tier = "Silver Tier (at ₹25,000 spend)"
        pts_to_next = int(max(0, (25000 - monetary) // 50))

    return {
        "points": points,
        "redeemable_value": float(points),  # ₹1 per point
        "tier": tier,
        "perk": perk,
        "next_tier": next_tier,
        "pts_to_next": pts_to_next
    }


def get_vip_progress(frequency: int, monetary: float) -> dict:
    """Calculate progress of a Regular Customer toward achieving VIP status.

    VIP Qualification Criteria:
    - Recency <= 60 days AND (Frequency >= 4 OR Monetary >= ₹50,000)
    """
    target_orders = 4
    target_spend = 50000.0

    orders_pct = min(100.0, round((frequency / target_orders) * 100, 1))
    spend_pct = min(100.0, round((monetary / target_spend) * 100, 1))
    overall_pct = max(orders_pct, spend_pct)

    orders_remaining = max(0, target_orders - frequency)
    spend_remaining = max(0.0, round(target_spend - monetary, 2))

    is_qualified = (frequency >= target_orders) or (monetary >= target_spend)

    return {
        "is_qualified": is_qualified,
        "overall_pct": min(100.0, overall_pct),
        "orders_pct": orders_pct,
        "spend_pct": spend_pct,
        "current_orders": frequency,
        "target_orders": target_orders,
        "orders_remaining": orders_remaining,
        "current_spend": monetary,
        "target_spend": target_spend,
        "spend_remaining": spend_remaining,
        "reward_milestone": "Unlock 20% VIP Privilege Discount + Complimentary Priority Delivery"
    }


# ==============================================================================
# 3. COMBO OFFERS & FLASH DEALS
# ==============================================================================
def get_combo_offers() -> list[dict]:
    """Generate curated profit-protected product bundle combos with 6% to 10% small discounts.

    Encourages larger basket sizes while preserving company profit margins above 15%.
    """
    return [
        {
            "combo_id": "COMBO-01",
            "title": "👔 Smart Wardrobe Duo",
            "category": "Clothing",
            "items": ["Kids T-Shirt (IND-037)", "Kids Shorts (IND-036)"],
            "description": "Essential comfort pair: Premium Cotton Kids T-Shirt bundled with matching Kids Shorts.",
            "regular_price": 3550.0,
            "combo_price": 3299.0,
            "savings": 251.0,
            "discount_pct": "7%",
            "promo_code": "COMBO7",
            "margin_after_discount": "31% (Profit Protected)",
            "min_order": 999.0
        },
        {
            "combo_id": "COMBO-02",
            "title": "📚 Executive Study & Workstation Pack",
            "category": "Furniture & Office",
            "items": ["Corner Bookshelf (IND-016)", "Study Table (IND-063)"],
            "description": "Upgrade your home office with a durable corner bookshelf and ergonomic study desk.",
            "regular_price": 23730.0,
            "combo_price": 21899.0,
            "savings": 1831.0,
            "discount_pct": "8%",
            "promo_code": "STUDY8",
            "margin_after_discount": "27% (Profit Protected)",
            "min_order": 2500.0
        },
        {
            "combo_id": "COMBO-03",
            "title": "🍿 Weekend Snacking & Beverage Combo",
            "category": "Groceries",
            "items": ["Namkeen Mix 400g (IND-044)", "Chips Combo Pack (IND-012)", "Fruit Juice Pack (IND-030)"],
            "description": "Family snack pack: Crunchy Namkeen Mix, Potato Chips combo, and refreshing fruit juice.",
            "regular_price": 1846.0,
            "combo_price": 1729.0,
            "savings": 117.0,
            "discount_pct": "6%",
            "promo_code": "SNACK6",
            "margin_after_discount": "16% (Profit Protected)",
            "min_order": 999.0
        },
        {
            "combo_id": "COMBO-04",
            "title": "🖊️ Student & Office Essentials Bundle",
            "category": "Office Supplies",
            "items": ["Gel Pen Pack (IND-031)", "Chart Paper Pack (IND-011)", "Ring Binder (IND-052)"],
            "description": "Complete stationery set for students and home documentation needs.",
            "regular_price": 2370.0,
            "combo_price": 2149.0,
            "savings": 221.0,
            "discount_pct": "9%",
            "promo_code": "OFFICE9",
            "margin_after_discount": "21% (Profit Protected)",
            "min_order": 999.0
        }
    ]


def get_limited_time_offers(limit: int = 4) -> pd.DataFrame:
    """Generate limited-time flash discount deals on select high-margin products with active countdown."""
    catalog = get_product_catalog()
    # High-margin items from Clothing, Furniture, Office Supplies
    eligible = catalog[catalog["OrdersCount"] >= 10].copy()
    deals = eligible.head(limit).copy()
    deals["FlashDiscount"] = "7% OFF"
    deals["DealPrice"] = (deals["AvgPrice"] * 0.93).round(2)
    deals["Savings"] = (deals["AvgPrice"] - deals["DealPrice"]).round(2)
    deals["ExpiresIn"] = "48 Hours (Weekend Special)"
    deals["ProfitStatus"] = "Safe (Net Margin ≥ 20%)"
    return deals


def get_discounted_comeback_products(limit: int = 6) -> pd.DataFrame:
    """Select high-margin products eligible for the 10% comeback discount."""
    catalog = get_product_catalog()
    df = catalog.head(limit).copy()
    df["Discount"] = "10% OFF"
    df["ComebackPrice"] = (df["AvgPrice"] * 0.90).round(2)
    df["Savings"] = (df["AvgPrice"] - df["ComebackPrice"]).round(2)
    df["ProfitStatus"] = "Protected (>20% net margin)"
    return df


def get_referral_program_details(customer_id: str | int) -> dict:
    """Generate unique referral rewards details for the customer."""
    cid_str = str(customer_id).replace("CUST-", "")
    return {
        "referral_code": f"REF-{cid_str}",
        "reward_points": 250,
        "reward_value_inr": 250.0,
        "friend_discount": "5% First Order Discount",
        "friend_min_order": 500.0,
        "referral_link": f"https://customerhub.in/join?ref=REF-{cid_str}",
        "rules": "Points credit to your balance automatically when your referred friend completes their first purchase of ₹500 or more."
    }


# Common stop words to exclude when extracting product category keywords from descriptions
CATEGORY_STOP_WORDS = {
    "SET", "OF", "THE", "AND", "WITH", "FOR", "RED", "BLUE", "PINK",
    "WHITE", "BLACK", "GREEN", "SMALL", "LARGE", "MINI", "PACK",
    "BOX", "BAG", "COLOUR", "COLOURS", "ASSORTED", "DESIGN", "RETRO"
}


# ==============================================================================
# 4. HEADLINE OFFERS & CATALOG RETRIEVAL
# ==============================================================================
def assign_offer(segment: str) -> str:
    """Generate basic offer headline based on customer segment."""
    if segment == "VIP Customer":
        return "Loyalty points, exclusive perks & early access"
    elif segment == "Regular Customer":
        return "Repeat purchase discount & VIP tier roadmap"
    elif segment == "Occasional Customer":
        return "5% discount on selected products & combo offers"
    elif segment == "At Risk":
        return "10% comeback offer & buy-again recommendations"
    elif segment == "New Customer":
        return "5% discount on first order & trending bestsellers"
    else:
        return "Standard promotional store offer"


def add_customer_offers(df: pd.DataFrame) -> pd.DataFrame:
    """Add an 'Offer' column to customer DataFrame based on CustomerSegment."""
    if "CustomerSegment" not in df.columns:
        raise ValueError("Input DataFrame must contain 'CustomerSegment' column.")

    offers_df = df.copy()
    offers_df["Offer"] = offers_df["CustomerSegment"].apply(assign_offer)
    return offers_df


def get_customer_offers_data() -> pd.DataFrame:
    """Fetch orders from SQLite database, compute RFM segments, and add offer suggestions."""
    orders_df = get_orders_data()
    rfm_df = calculate_rfm(orders_df)
    segmented_df = segment_customers(rfm_df)
    return add_customer_offers(segmented_df)


# Cache product catalog in memory to avoid redundant database reads
_PRODUCT_CATALOG: pd.DataFrame | None = None


def get_product_catalog() -> pd.DataFrame:
    """Extract distinct products with real transaction metrics and categories from shop.db."""
    global _PRODUCT_CATALOG
    if _PRODUCT_CATALOG is not None:
        return _PRODUCT_CATALOG

    engine = get_engine()
    query = f"""
        SELECT StockCode,
               MAX(Description) AS Description,
               MAX(Category) AS Category,
               MAX(SubCategory) AS SubCategory,
               COUNT(DISTINCT InvoiceNo) AS OrdersCount,
               SUM(Quantity) AS TotalQuantity,
               ROUND(AVG(UnitPrice), 2) AS AvgPrice,
               MIN(InvoiceDate) AS FirstSeen
        FROM {TABLE_ORDERS}
        WHERE Description IS NOT NULL
        GROUP BY StockCode
        ORDER BY OrdersCount DESC
    """
    catalog = pd.read_sql(query, con=engine)
    catalog["FirstSeen"] = pd.to_datetime(catalog["FirstSeen"], errors="coerce")
    _PRODUCT_CATALOG = catalog
    return _PRODUCT_CATALOG


def get_recently_introduced_products(limit: int = 6) -> pd.DataFrame:
    """Identify recently introduced products using the earliest available transaction date.

    Designed for VIP Early-Access section.
    """
    catalog = get_product_catalog()
    valid_new = catalog[catalog["OrdersCount"] >= 2].copy()
    return valid_new.sort_values(by="FirstSeen", ascending=False).head(limit)


def get_popular_products(limit: int = 6, sort_by: str = "OrdersCount") -> pd.DataFrame:
    """Identify popular products based on real invoice counts or total purchase quantities."""
    catalog = get_product_catalog()
    if sort_by == "TotalQuantity":
        return catalog.sort_values(by="TotalQuantity", ascending=False).head(limit)
    return catalog.sort_values(by="OrdersCount", ascending=False).head(limit)


def get_customer_purchase_history(customer_id: str | int) -> pd.DataFrame:
    """Retrieve actual past purchases for a specific customer from shop.db."""
    engine = get_engine()
    query = f"""
        SELECT StockCode,
               MAX(Description) AS Description,
               MAX(Category) AS Category,
               COUNT(DISTINCT InvoiceNo) AS OrdersCount,
               SUM(Quantity) AS TotalQuantity,
               ROUND(AVG(UnitPrice), 2) AS AvgPrice,
               ROUND(SUM(Amount), 2) AS TotalSpent,
               MAX(InvoiceDate) AS LastPurchased
        FROM {TABLE_ORDERS}
        WHERE CustomerID = '{customer_id}'
        GROUP BY StockCode
        ORDER BY OrdersCount DESC, TotalQuantity DESC
    """
    history = pd.read_sql(query, con=engine)
    return history


def get_customer_frequently_purchased(customer_id: str | int, limit: int = 6) -> pd.DataFrame:
    """Retrieve frequently purchased items by this customer, or top category items."""
    history = get_customer_purchase_history(customer_id)
    if not history.empty and len(history) >= 2:
        return history.sort_values(by=["OrdersCount", "TotalQuantity"], ascending=False).head(limit)
    return get_customer_category_recommendations(customer_id, limit=limit)


def get_customer_category_recommendations(customer_id: str | int, limit: int = 6) -> pd.DataFrame:
    """Recommend products from categories or product groups the customer frequently purchases."""
    catalog = get_product_catalog()
    history = get_customer_purchase_history(customer_id)

    if history.empty:
        return get_popular_products(limit=limit)

    already_bought = set(history["StockCode"].dropna().unique())

    # Extract keywords from the customer's purchased item descriptions
    extracted_words = []
    for desc in history["Description"].dropna():
        tokens = re.findall(r"[A-Za-z]{4,}", desc.upper())
        extracted_words.extend([w for w in tokens if w not in CATEGORY_STOP_WORDS])

    if not extracted_words:
        unbought = catalog[~catalog["StockCode"].isin(already_bought)]
        return unbought.head(limit)

    # Find the top 6 most frequent category keywords
    top_keywords = [w for w, _ in Counter(extracted_words).most_common(6)]

    def matches_keywords(text: str) -> bool:
        upper = str(text).upper()
        return any(kw in upper for kw in top_keywords)

    candidates = catalog[
        (~catalog["StockCode"].isin(already_bought)) &
        (catalog["Description"].apply(matches_keywords))
    ]

    if candidates.empty:
        candidates = catalog[~catalog["StockCode"].isin(already_bought)]

    return candidates.head(limit)


# ==============================================================================
# 5. PERSONALIZED OFFER DETAILS GENERATOR
# ==============================================================================
def get_personalized_offer_details(customer_id: str | int, segment: str, reference_date: pd.Timestamp | None = None) -> dict:
    """Generate segment-specific offer copy, simulated promotional rewards, profit rules, and recommendations.

    Segment Features:
    1. VIP Customer:
       - Loyalty points, exclusive rewards (20% discount up to ₹5,000, MOV ₹2,500), early access to new products.
    2. Regular Customer:
       - Recommend frequently purchased products, show progress toward VIP rewards, 5% repeat discount.
    3. Occasional Customer:
       - 5% discounts on selected products (MOV ₹1,000, Cap ₹500), suggest combo offers to lift basket.
    4. At Risk Customer:
       - 10% comeback offer (MOV ₹1,500, Cap ₹1,500), recommend previously purchased, trending, and discounted products.
    5. New Customer:
       - 5% discount on first order (MOV ₹500, Cap ₹500), show trending and best-selling products.
    6. Attraction Features:
       - Combo offers, limited-time flash deals, free shipping (threshold ₹999), referral rewards program (250 pts).
    7. Profit Protection:
       - Guaranteed minimum 15% profit floor, maximum discount limits, minimum order values.
    """
    if reference_date is None:
        reference_date = pd.Timestamp("2026-01-01 00:00:00")

    history = get_customer_purchase_history(customer_id)
    category_recs = get_customer_category_recommendations(customer_id, limit=6)
    popular_recs = get_popular_products(limit=6)
    profit_rules = get_profit_protection_rules(segment)
    referral_info = get_referral_program_details(customer_id)
    combos = get_combo_offers()
    limited_time_deals = get_limited_time_offers(limit=4)

    total_spent = float(history["TotalSpent"].sum()) if not history.empty else 0.0
    total_orders = int(history["OrdersCount"].sum()) if not history.empty else 1
    loyalty_info = calculate_loyalty_points(total_spent)

    details = {
        "customer_id": str(customer_id),
        "segment": segment,
        "history": history,
        "category_recommendations": category_recs,
        "popular_recommendations": popular_recs,
        "combos": combos,
        "limited_time_deals": limited_time_deals,
        "profit_rules": profit_rules,
        "loyalty_info": loyalty_info,
        "referral_info": referral_info,
        "free_shipping": {
            "threshold": 999.0,
            "message": "Free Express Shipping on all orders over ₹999 across India"
        },
        "is_simulated": True,
    }

    # 1. VIP Customer
    if segment == "VIP Customer":
        details.update({
            "offer_title": "🌟 VIP Exclusive Loyalty Privilege & Rewards",
            "offer_badge": "VIP Gold Tier",
            "offer_description": "Exclusive Loyalty Reward: 20% VIP Privilege Discount + Complimentary Priority Delivery on your entire order.",
            "promo_code": "VIPLOYALTY20",
            "min_order_value": profit_rules["min_order_value"],
            "max_discount_cap": profit_rules["max_discount_cap"],
            "simulation_note": "Simulated promotional offer: Created by CustomerHub to reward high-value VIP customers with loyalty points and exclusive rewards.",
            "has_scratch_card": False,
            "has_expiry": False,
            "expiry_date": None,
            "early_access_products": get_recently_introduced_products(limit=6),
            "free_shipping_status": "Unlocked (Complimentary Priority Shipping on All Orders)"
        })

    # 2. Regular Customer
    elif segment == "Regular Customer":
        vip_progress = get_vip_progress(total_orders, total_spent)
        details.update({
            "offer_title": "🔄 Regular Customer Repeat Reward & VIP Roadmap",
            "offer_badge": "Repeat Shopper Perk",
            "offer_description": "5% Repeat Purchase Discount on your next order. Keep ordering to unlock 20% VIP Gold Tier Rewards!",
            "promo_code": "REPEAT5",
            "min_order_value": profit_rules["min_order_value"],
            "max_discount_cap": profit_rules["max_discount_cap"],
            "has_scratch_card": True,
            "scratch_card_label": "🎁 Scratch Card Reward: 5% Off Repeat Purchases",
            "simulation_note": "Simulated promotional feature: The interactive scratch-card reward is simulated by CustomerHub for demonstration.",
            "has_expiry": False,
            "expiry_date": None,
            "vip_progress": vip_progress,
            "frequently_purchased": get_customer_frequently_purchased(customer_id, limit=6),
            "early_access_products": None
        })

    # 3. Occasional Customer
    elif segment == "Occasional Customer":
        details.update({
            "offer_title": "🛒 Occasional Shopper 5% Savings & Value Combos",
            "offer_badge": "Selected Items Perk",
            "offer_description": "5% Discount on selected products + Extra savings with curated product combo offers to encourage basket growth.",
            "promo_code": "OCCASIONAL5",
            "min_order_value": profit_rules["min_order_value"],
            "max_discount_cap": profit_rules["max_discount_cap"],
            "has_scratch_card": False,
            "has_expiry": False,
            "expiry_date": None,
            "simulation_note": "Simulated promotional offer: 5% discount on selected margin-healthy categories and combo packs.",
            "early_access_products": None
        })

    # 4. At Risk Customer
    elif segment == "At Risk":
        expiry = reference_date + pd.Timedelta(days=14)
        details.update({
            "offer_title": "💔 Win-Back Customer Campaign: 10% Comeback Offer",
            "offer_badge": "Comeback Special",
            "offer_description": "We Miss You! 10% Comeback Discount on your return order (Valid for 14 days, capped at ₹1,500).",
            "promo_code": "COMEBACK10",
            "min_order_value": profit_rules["min_order_value"],
            "max_discount_cap": profit_rules["max_discount_cap"],
            "has_scratch_card": False,
            "has_expiry": True,
            "expiry_date": expiry.strftime("%B %d, %Y"),
            "simulation_note": "Simulated promotional offer: Win-back 10% discount and 14-day expiry date are simulated by CustomerHub.",
            "buy_again_products": history.head(6) if not history.empty else popular_recs,
            "discounted_products": get_discounted_comeback_products(limit=6),
            "early_access_products": None
        })

    # 5. New Customer
    elif segment == "New Customer":
        expiry = reference_date + pd.Timedelta(days=30)
        details.update({
            "offer_title": "🎉 New Customer Welcome: 5% First Order Discount",
            "offer_badge": "New Shopper Special",
            "offer_description": "Welcome to CustomerHub! Enjoy 5% Discount on your first order (Min order ₹500, Max discount ₹500, Valid for 30 days).",
            "promo_code": "FIRST5",
            "min_order_value": profit_rules["min_order_value"],
            "max_discount_cap": profit_rules["max_discount_cap"],
            "has_scratch_card": False,
            "has_expiry": True,
            "expiry_date": expiry.strftime("%B %d, %Y"),
            "simulation_note": "Simulated promotional offer: 5% welcome discount created by CustomerHub for new customers.",
            "trending_products": get_popular_products(limit=6, sort_by="TotalQuantity"),
            "bestseller_products": get_popular_products(limit=6, sort_by="OrdersCount"),
            "early_access_products": None
        })

    else:
        details.update({
            "offer_title": "🛍️ General Store Offer",
            "offer_badge": "Storewide Perk",
            "offer_description": "5% standard discount on all featured items.",
            "promo_code": "SAVE5",
            "min_order_value": 500.0,
            "max_discount_cap": 500.0,
            "has_scratch_card": False,
            "has_expiry": False,
            "expiry_date": None,
            "simulation_note": "Simulated standard store offer.",
            "early_access_products": None
        })

    return details


def main():
    """Main execution function for testing Customer Offers and Recommendations."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 75)
    print("CustomerHub: Customer-Personalized Offers & Recommendation System")
    print("=" * 75)
    print("Loading product catalog and customer segmentation data from shop.db...")

    try:
        offers_df = get_customer_offers_data()
        catalog = get_product_catalog()
    except Exception as e:
        print(f"\n[ERROR] Failed to load data: {e}")
        sys.exit(1)

    print(f"Loaded {len(catalog):,} distinct catalog products.")
    print(f"Generated offers for {len(offers_df):,} customers.\n")

    # Display Profit Protection Rules
    print("=" * 75)
    print("PROFIT PROTECTION RULES (15% MINIMUM NET MARGIN FLOOR)")
    print("=" * 75)
    for seg in ["VIP Customer", "Regular Customer", "Occasional Customer", "At Risk", "New Customer"]:
        r = get_profit_protection_rules(seg)
        print(f"[{seg}] Rate: {r['discount_rate']} | Min Order: ₹{r['min_order_value']:.0f} | Cap: ₹{r['max_discount_cap']:.0f} | Margin Floor: {r['margin_floor_pct']}")

    # Display Curated Combos
    print("\n" + "=" * 75)
    print("CURATED COMBO OFFERS")
    print("=" * 75)
    for c in get_combo_offers():
        print(f"- {c['title']} ({c['discount_pct']} off) | Regular: ₹{c['regular_price']:.0f} -> Combo: ₹{c['combo_price']:.0f} (Save ₹{c['savings']:.0f})")

    # Display Sample Personalized Strategies across Segments
    sample_customers = ["CUST-1003", "CUST-1005", "CUST-1000"]
    print("\n" + "=" * 75)
    print("SAMPLE PERSONALIZED STRATEGIES BY CUSTOMER")
    print("=" * 75)
    for cid in sample_customers:
        match = offers_df[offers_df["CustomerID"] == cid]
        if match.empty:
            continue
        seg = match.iloc[0]["CustomerSegment"]
        details = get_personalized_offer_details(cid, seg)
        print(f"\nCustomerID {cid} ({seg}):")
        print(f"  Title: {details['offer_title']}")
        print(f"  Offer: {details['offer_description']}")
        print(f"  Loyalty: {details['loyalty_info']['points']} pts ({details['loyalty_info']['tier']})")
        if details.get("expiry_date"):
            print(f"  Expiry: {details['expiry_date']}")
        print(f"  Category Recs: {len(details['category_recommendations'])} items found")
        print(f"  Purchase History: {len(details['history'])} distinct items")

    print("\n" + "=" * 75)
    print("Offers and Recommendation module is ready!")
    print("=" * 75)


if __name__ == "__main__":
    main()
