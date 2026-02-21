from __future__ import annotations

import re
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from utils import safe_div


MONTH_MAP = {
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}

MODIFIER_KEYWORDS = ("extra", "shot", "oat", "almond", "syrup")


def _month_col_to_key(col_name: str) -> str | None:
    match = re.match(r"^\s*([A-Za-z]{3})\s+(\d{4})\s*$", str(col_name))
    if not match:
        return None
    mon = MONTH_MAP.get(match.group(1).lower())
    year = match.group(2)
    if not mon:
        return None
    return f"{year}-{mon}"


def _extract_monthly_records(monthly_df: pd.DataFrame) -> Tuple[Dict[str, List[dict]], pd.DataFrame]:
    month_cols = []
    for col in monthly_df.columns:
        key = _month_col_to_key(col)
        if key:
            month_cols.append((col, key))

    rows = []
    monthly_series: Dict[str, List[dict]] = {}
    for _, row in monthly_df.iterrows():
        branch_key = row["branch_key"]
        branch_name = row["branch"]
        points = []
        for src_col, month_key in sorted(month_cols, key=lambda x: x[1]):
            val = float(row.get(src_col, 0.0) or 0.0)
            if val == 0:
                continue
            points.append({"month": month_key, "revenue": val})
        monthly_series[branch_key] = points

        revenues = [p["revenue"] for p in points]
        avg_monthly_revenue = float(np.mean(revenues)) if revenues else 0.0
        if len(revenues) >= 2 and revenues[0] != 0:
            growth_rate = (revenues[-1] - revenues[0]) / abs(revenues[0])
        else:
            growth_rate = 0.0
        volatility = safe_div(float(np.std(revenues)), avg_monthly_revenue, 0.0) if revenues else 0.0

        apr = next((p["revenue"] for p in points if p["month"] == "2025-04"), None)
        jun = next((p["revenue"] for p in points if p["month"] == "2025-06"), None)
        may_june_drop = safe_div(apr - jun, apr, 0.0) if apr and jun else 0.0

        rows.append(
            {
                "branch_key": branch_key,
                "branch": branch_name,
                "avg_monthly_revenue": avg_monthly_revenue,
                "growth_rate": growth_rate,
                "volatility": volatility,
                "may_june_drop": may_june_drop,
                "monthly_revenue_total": float(np.sum(revenues)) if revenues else 0.0,
            }
        )

    return monthly_series, pd.DataFrame(rows)


def _build_category_features(category_df: pd.DataFrame) -> pd.DataFrame:
    work = category_df.copy()
    work["is_beverage"] = work["category"].astype(str).str.contains("bev", case=False, na=False)
    work["is_food"] = work["category"].astype(str).str.contains("food", case=False, na=False)

    grouped = work.groupby(["branch_key", "branch"], as_index=False).agg(
        total_revenue=("revenue_true", "sum"),
        total_profit=("total_profit", "sum"),
        beverage_revenue=("revenue_true", lambda s: s[work.loc[s.index, "is_beverage"]].sum()),
        food_revenue=("revenue_true", lambda s: s[work.loc[s.index, "is_food"]].sum()),
        beverage_profit=("total_profit", lambda s: s[work.loc[s.index, "is_beverage"]].sum()),
        food_profit=("total_profit", lambda s: s[work.loc[s.index, "is_food"]].sum()),
    )
    grouped["beverage_share"] = grouped.apply(
        lambda r: safe_div(r["beverage_revenue"], r["total_revenue"]), axis=1
    )
    grouped["food_share"] = grouped.apply(
        lambda r: safe_div(r["food_revenue"], r["total_revenue"]), axis=1
    )
    grouped["overall_margin"] = grouped.apply(
        lambda r: safe_div(r["total_profit"], r["total_revenue"]), axis=1
    )
    return grouped


def _build_product_features(product_df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, List[dict]], Dict[str, float]]:
    base = product_df.copy()
    base["item"] = base["item"].astype(str).str.strip()
    base["item_l"] = base["item"].str.lower()
    base["is_modifier"] = base["item_l"].apply(lambda x: any(k in x for k in MODIFIER_KEYWORDS))

    product_grouped = base.groupby(["branch_key", "branch", "item"], as_index=False).agg(
        qty=("qty", "sum"),
        revenue=("revenue_true", "sum"),
        profit=("total_profit", "sum"),
    )
    product_grouped["margin"] = product_grouped.apply(lambda r: safe_div(r["profit"], r["revenue"]), axis=1)

    top_products_by_branch: Dict[str, List[dict]] = {}
    for bk, grp in product_grouped.groupby("branch_key"):
        top = grp.sort_values("profit", ascending=False).head(10)
        top_products_by_branch[bk] = [
            {
                "product": str(r["item"]),
                "qty": float(r["qty"]),
                "profit": float(r["profit"]),
                "margin": float(r["margin"]),
            }
            for _, r in top.iterrows()
        ]

    branch_summary = base.groupby(["branch_key", "branch"], as_index=False).agg(
        total_profit=("total_profit", "sum"),
        total_revenue=("revenue_true", "sum"),
        sku_count=("item", lambda s: s.astype(str).nunique()),
        modifier_qty=("qty", lambda s: s[base.loc[s.index, "is_modifier"]].sum()),
        total_qty=("qty", "sum"),
    )

    top5_share_map: Dict[str, float] = {}
    for bk, grp in product_grouped.groupby("branch_key"):
        total_profit = float(grp["profit"].sum())
        top5_profit = float(grp.sort_values("profit", ascending=False).head(5)["profit"].sum())
        top5_share_map[bk] = safe_div(top5_profit, total_profit)

    branch_summary["top5_profit_share"] = branch_summary["branch_key"].map(top5_share_map).fillna(0.0)
    branch_summary["modifier_rate"] = branch_summary.apply(
        lambda r: safe_div(float(r["modifier_qty"]), float(r["total_qty"])), axis=1
    )
    branch_summary = branch_summary.drop(columns=["modifier_qty", "total_qty"])
    modifier_rate_map = dict(zip(branch_summary["branch_key"], branch_summary["modifier_rate"]))

    return branch_summary, top_products_by_branch, modifier_rate_map


def build_branch_dataset(
    monthly_df: pd.DataFrame, category_df: pd.DataFrame, product_df: pd.DataFrame
) -> Tuple[pd.DataFrame, Dict[str, List[dict]], Dict[str, List[dict]]]:
    monthly_map, monthly_features = _extract_monthly_records(monthly_df)
    category_features = _build_category_features(category_df)
    product_features, top_products_by_branch, _ = _build_product_features(product_df)

    merged = monthly_features.merge(
        category_features,
        on=["branch_key", "branch"],
        how="outer",
        suffixes=("", "_cat"),
    ).merge(
        product_features,
        on=["branch_key", "branch"],
        how="outer",
        suffixes=("", "_prod"),
    )

    merged["avg_monthly_revenue"] = merged["avg_monthly_revenue"].fillna(0.0)
    merged["growth_rate"] = merged["growth_rate"].fillna(0.0)
    merged["volatility"] = merged["volatility"].fillna(0.0)
    merged["may_june_drop"] = merged["may_june_drop"].fillna(0.0)
    merged["overall_margin"] = merged["overall_margin"].fillna(0.0)
    merged["beverage_share"] = merged["beverage_share"].fillna(0.0)
    merged["food_share"] = merged["food_share"].fillna(0.0)
    merged["top5_profit_share"] = merged["top5_profit_share"].fillna(0.0)
    merged["sku_count"] = merged["sku_count"].fillna(0).astype(int)

    merged["branch_revenue_est"] = merged["total_revenue"].fillna(merged["monthly_revenue_total"]).fillna(0.0)
    merged["branch_profit_est"] = merged["total_profit"].fillna(0.0)

    return merged, monthly_map, top_products_by_branch

