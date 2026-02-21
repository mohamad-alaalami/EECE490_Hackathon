from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from utils import (
    canonical_branch_name,
    find_col,
    is_valid_branch_key,
    normalize_branch_key,
    to_numeric,
)


@dataclass
class LoadedData:
    monthly: pd.DataFrame
    category: pd.DataFrame
    product: pd.DataFrame
    groups: pd.DataFrame


class DataLoadError(RuntimeError):
    pass


def _read_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise DataLoadError(f"Missing processed file: {path}")
    if path.suffix.lower() != ".csv":
        raise DataLoadError(f"Expected CSV processed file, got: {path.name}")
    return pd.read_csv(path, dtype=str)


def _clean_branch_column(df: pd.DataFrame) -> pd.DataFrame:
    branch_col = find_col(df, ["branch", "store", "location"])
    if not branch_col:
        raise DataLoadError("Could not detect branch column.")
    out = df.copy()
    out["branch_key"] = out[branch_col].apply(normalize_branch_key)
    out["branch"] = out[branch_col].apply(canonical_branch_name)
    out = out[out["branch_key"].apply(is_valid_branch_key)]
    return out


def load_monthly_sales() -> pd.DataFrame:
    path = Path("data/processed/monthly_sales_clean.csv")
    df = _read_table(path)
    df = _clean_branch_column(df)

    for col in df.columns:
        if any(month in str(col).lower() for month in ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")):
            df[col] = to_numeric(df[col])

    return df


def load_category_summary() -> pd.DataFrame:
    path = Path("data/processed/category__summary_clean.csv")
    df = _read_table(path)
    df = _clean_branch_column(df)

    category_col = find_col(df, ["category"])
    if not category_col:
        raise DataLoadError("Category summary: missing category column.")

    total_cost_col = find_col(df, ["total cost", "cost"])
    total_profit_col = find_col(df, ["total profit", "profit"])
    total_price_col = find_col(df, ["total price", "revenue", "total amount"])
    qty_col = find_col(df, ["qty", "quantity"])

    if not total_cost_col or not total_profit_col:
        raise DataLoadError("Category summary: missing total cost/profit columns.")

    out = df.copy()
    out["category"] = out[category_col].astype(str).str.strip().str.lower()
    out["qty"] = to_numeric(out[qty_col]) if qty_col else 0.0
    out["total_cost"] = to_numeric(out[total_cost_col])
    out["total_profit"] = to_numeric(out[total_profit_col])
    out["total_price_raw"] = to_numeric(out[total_price_col]) if total_price_col else 0.0
    out["revenue_true"] = out["total_cost"] + out["total_profit"]

    return out


def load_product_profitability() -> pd.DataFrame:
    path = Path("data/processed/product_profitability_clean.csv")
    df = _read_table(path)
    df = _clean_branch_column(df)

    item_col = find_col(df, ["item", "product", "description", "item description"])
    qty_col = find_col(df, ["qty", "quantity"])
    price_col = find_col(df, ["total price", "price", "total amount"])
    cost_col = find_col(df, ["total cost", "cost"])
    profit_col = find_col(df, ["total profit", "profit"])

    if not item_col or not cost_col or not profit_col:
        raise DataLoadError("Product profitability: missing item/cost/profit columns.")

    out = df.copy()
    out["item"] = out[item_col].astype(str).str.strip()
    out["qty"] = to_numeric(out[qty_col]) if qty_col else 0.0
    out["total_cost"] = to_numeric(out[cost_col])
    out["total_profit"] = to_numeric(out[profit_col])
    out["total_price_raw"] = to_numeric(out[price_col]) if price_col else 0.0
    out["revenue_true"] = out["total_cost"] + out["total_profit"]
    return out


def load_groups() -> pd.DataFrame:
    path = Path("data/processed/totals_clean.csv")
    if not path.exists():
        return pd.DataFrame()
    df = _read_table(path)
    try:
        df = _clean_branch_column(df)
    except DataLoadError:
        return pd.DataFrame()
    return df


def get_mock_data() -> LoadedData:
    monthly = pd.DataFrame(
        [
            {
                "branch_key": "stories zalka",
                "branch": "Stories Zalka",
                "Jan 2025": 42000,
                "Feb 2025": 39000,
                "Mar 2025": 46000,
                "Apr 2025": 51000,
                "May 2025": 56000,
                "Jun 2025": 49000,
                "Jan 2026": 53000,
            }
        ]
    )
    category = pd.DataFrame(
        [
            {
                "branch_key": "stories zalka",
                "branch": "Stories Zalka",
                "category": "beverages",
                "qty": 100,
                "total_cost": 20000,
                "total_profit": 30000,
                "total_price_raw": 50000,
                "revenue_true": 50000,
            },
            {
                "branch_key": "stories zalka",
                "branch": "Stories Zalka",
                "category": "food",
                "qty": 80,
                "total_cost": 15000,
                "total_profit": 10000,
                "total_price_raw": 25000,
                "revenue_true": 25000,
            },
        ]
    )
    product = pd.DataFrame(
        [
            {
                "branch_key": "stories zalka",
                "branch": "Stories Zalka",
                "item": "LATTE",
                "qty": 300,
                "total_cost": 5000,
                "total_profit": 12000,
                "total_price_raw": 17000,
                "revenue_true": 17000,
            }
        ]
    )
    return LoadedData(monthly=monthly, category=category, product=product, groups=pd.DataFrame())


def load_all_data(use_mock_fallback: bool = False) -> LoadedData:
    try:
        return LoadedData(
            monthly=load_monthly_sales(),
            category=load_category_summary(),
            product=load_product_profitability(),
            groups=load_groups(),
        )
    except Exception as exc:
        if use_mock_fallback:
            return get_mock_data()
        raise DataLoadError(
            f"Failed loading processed input files from data/processed: {exc}"
        ) from exc
