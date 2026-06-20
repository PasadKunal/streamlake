"""
Olist enrichment features - computed from CSV files, not from the event stream.

These 3 features capture customer experience signals that are not present in
the raw purchase events:

  avg_delivery_delay_days   - positive means late, negative means early
  avg_review_score          - 1-5 star rating averaged across all orders
  avg_payment_installments  - higher = more price-sensitive buyer

In production these would be computed by a daily batch job after new reviews
and deliveries are logged, then written to the Feast online store. For Step 1
validation they are computed from the Olist CSVs and joined at training time.

Usage:
    python -m feature_store.olist_enrichment
    # writes feature_store/data/olist_enrichment.parquet
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from loguru import logger

OLIST_DIR   = Path("data/olist")
OUTPUT_PATH = Path("feature_store/data/olist_enrichment.parquet")

REQUIRED = [
    "olist_orders_dataset.csv",
    "olist_customers_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_order_payments_dataset.csv",
]


def compute(olist_dir: Path = OLIST_DIR) -> pd.DataFrame:
    for f in REQUIRED:
        if not (olist_dir / f).exists():
            raise FileNotFoundError(f"Missing: {olist_dir / f}")

    orders    = pd.read_csv(olist_dir / "olist_orders_dataset.csv")
    customers = pd.read_csv(olist_dir / "olist_customers_dataset.csv")
    reviews   = pd.read_csv(olist_dir / "olist_order_reviews_dataset.csv")
    payments  = pd.read_csv(olist_dir / "olist_order_payments_dataset.csv")

    # Attach customer_unique_id to orders
    orders = orders.merge(
        customers[["customer_id", "customer_unique_id"]],
        on="customer_id", how="left",
    )

    # 1. Delivery delay: actual - estimated delivery date (days)
    #    Positive = arrived late, negative = arrived early
    orders["order_estimated_delivery_date"] = pd.to_datetime(
        orders["order_estimated_delivery_date"], utc=True, errors="coerce"
    )
    orders["order_delivered_customer_date"] = pd.to_datetime(
        orders["order_delivered_customer_date"], utc=True, errors="coerce"
    )
    orders["delivery_delay_days"] = (
        orders["order_delivered_customer_date"]
        - orders["order_estimated_delivery_date"]
    ).dt.days

    avg_delay = (
        orders.groupby("customer_unique_id")["delivery_delay_days"]
        .mean()
        .rename("avg_delivery_delay_days")
        .round(2)
    )

    # 2. Average review score per customer (1-5)
    r = reviews.merge(orders[["order_id", "customer_unique_id"]], on="order_id", how="left")
    avg_review = (
        r.groupby("customer_unique_id")["review_score"]
        .mean()
        .rename("avg_review_score")
        .round(4)
    )

    # 3. Average payment installments per customer
    #    Brazilian boleto/card buyers vary widely: 1 = lump sum, 12+ = stretched
    p = payments.merge(orders[["order_id", "customer_unique_id"]], on="order_id", how="left")
    avg_installments = (
        p.groupby("customer_unique_id")["payment_installments"]
        .mean()
        .rename("avg_payment_installments")
        .round(2)
    )

    enrichment = (
        pd.DataFrame(index=avg_delay.index)
        .join(avg_delay,        how="outer")
        .join(avg_review,       how="outer")
        .join(avg_installments, how="outer")
        .reset_index()
        .rename(columns={"customer_unique_id": "user_id"})
    )

    logger.info(
        f"Enrichment features computed | users={len(enrichment):,} "
        f"| avg_delay={enrichment['avg_delivery_delay_days'].mean():.1f}d "
        f"| avg_review={enrichment['avg_review_score'].mean():.2f} "
        f"| avg_installments={enrichment['avg_payment_installments'].mean():.1f}"
    )
    return enrichment


def run(olist_dir: Path = OLIST_DIR, output: Path = OUTPUT_PATH) -> None:
    df = compute(olist_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output, index=False)
    logger.info(f"Written -> {output}")


if __name__ == "__main__":
    run()
