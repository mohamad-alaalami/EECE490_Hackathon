# scripts/run_bundles.py
import os
import pandas as pd

from src.bundling import generate_bundle_suggestions

DATA_DIR = "data"
RAW_DIR = os.path.join(DATA_DIR, "raw")
OUT_DIR = os.path.join(DATA_DIR, "processed")
os.makedirs(OUT_DIR, exist_ok=True)

# CHANGE THESE FILENAMES to match your data
ITEM_SALES_FILE = os.path.join(RAW_DIR, "branch_item_sales.csv")
TRANSACTIONS_FILE = os.path.join(RAW_DIR, "transactions.csv")  # optional


def main():
    if not os.path.exists(ITEM_SALES_FILE):
        raise FileNotFoundError(
            f"Missing {ITEM_SALES_FILE}. Create it in data/raw/ with branch-item sales."
        )

    item_sales = pd.read_csv(ITEM_SALES_FILE)

    transactions = None
    if os.path.exists(TRANSACTIONS_FILE):
        transactions = pd.read_csv(TRANSACTIONS_FILE)

    bundles = generate_bundle_suggestions(
        item_sales=item_sales,
        transactions=transactions,
        low_sales_quantile=0.30,
        anchor_sales_quantile=0.70,
        min_unit_margin=0.10,
        target_bundle_margin=0.15,
        max_discount_pct=0.25,
        top_k_per_branch=10
    )

    out_path = os.path.join(OUT_DIR, "bundles.csv")
    bundles.to_csv(out_path, index=False)
    print(f"✅ Wrote {out_path} ({len(bundles)} bundle suggestions)")


if __name__ == "__main__":
    main()