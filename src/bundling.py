# src/bundling.py
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict

import pandas as pd


@dataclass
class BundleSuggestion:
    branch_id: str
    bundle_items: List[str]
    discount_pct: float
    bundle_price: float
    expected_profit: float
    support: float          # how often items co-occur (if transaction mode)
    lift: float             # association strength (if transaction mode)
    reason: str


def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def _infer_price_cost(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize item economics columns.

    Expected minimum columns:
      - branch_id
      - item_id (or product_id)
      - revenue OR price
      - cost OR profit

    Supports:
      - revenue & units_sold -> price = revenue/units
      - profit -> cost = revenue - profit (if revenue exists)
    """
    out = df.copy()

    # normalize column names
    if "product_id" in out.columns and "item_id" not in out.columns:
        out = out.rename(columns={"product_id": "item_id"})
    if "units" in out.columns and "units_sold" not in out.columns:
        out = out.rename(columns={"units": "units_sold"})

    if "price" not in out.columns:
        if "revenue" in out.columns and "units_sold" in out.columns:
            out["price"] = out["revenue"] / out["units_sold"].replace(0, pd.NA)
        elif "unit_price" in out.columns:
            out["price"] = out["unit_price"]
        else:
            raise ValueError("Need either (revenue & units_sold) OR price/unit_price columns.")

    # cost
    if "cost" not in out.columns:
        if "profit" in out.columns and "revenue" in out.columns:
            out["cost"] = out["revenue"] - out["profit"]
        elif "unit_cost" in out.columns:
            out["cost"] = out["unit_cost"]
        else:
            # if you truly only have margin %, this won't work
            raise ValueError("Need either cost/unit_cost, or (profit & revenue) to infer cost.")

    # unit cost
    if "unit_cost" not in out.columns:
        if "units_sold" in out.columns:
            out["unit_cost"] = out["cost"] / out["units_sold"].replace(0, pd.NA)
        else:
            out["unit_cost"] = out["cost"]

    # unit profit
    out["unit_profit"] = out["price"] - out["unit_cost"]
    out["unit_margin"] = out["unit_profit"] / out["price"].replace(0, pd.NA)

    # fill NaNs
    out = out.fillna(0)
    return out


def _build_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build baskets: one row per transaction with list of item_ids.

    Required columns:
      - branch_id
      - item_id
      and one of:
        - order_id, OR
        - (customer_id & date), OR
        - (date) with receipt_id-like grouping (fallback)

    Returns a table with columns: branch_id, basket_id, items (list)
    """
    x = df.copy()
    if "product_id" in x.columns and "item_id" not in x.columns:
        x = x.rename(columns={"product_id": "item_id"})

    # Determine basket id
    if "order_id" in x.columns:
        x["basket_id"] = x["order_id"].astype(str)
    elif "customer_id" in x.columns and "date" in x.columns:
        x["basket_id"] = x["customer_id"].astype(str) + "_" + x["date"].astype(str)
    elif "date" in x.columns:
        # weak fallback: treat each branch-day as a "basket"
        x["basket_id"] = x["date"].astype(str)
    else:
        raise ValueError("No transaction grouping columns found. Provide order_id OR (customer_id,date) OR date.")

    baskets = (
        x.groupby(["branch_id", "basket_id"])["item_id"]
        .apply(lambda s: sorted(set(map(str, s.tolist()))))
        .reset_index()
        .rename(columns={"item_id": "items"})
    )
    return baskets


def _pair_stats(baskets: pd.DataFrame) -> pd.DataFrame:
    """
    Compute pair support + lift per branch for item pairs.
    We only mine PAIRS (fast & hackathon-friendly).
    """
    rows = []
    for (branch_id), g in baskets.groupby("branch_id"):
        total = len(g)
        if total == 0:
            continue

        # item counts
        item_count: Dict[str, int] = {}
        pair_count: Dict[Tuple[str, str], int] = {}

        for items in g["items"]:
            for it in items:
                item_count[it] = item_count.get(it, 0) + 1
            # pairs
            n = len(items)
            for i in range(n):
                for j in range(i + 1, n):
                    a, b = items[i], items[j]
                    key = (a, b) if a < b else (b, a)
                    pair_count[key] = pair_count.get(key, 0) + 1

        # compute support & lift
        for (a, b), c_ab in pair_count.items():
            sup_ab = c_ab / total
            sup_a = item_count.get(a, 0) / total
            sup_b = item_count.get(b, 0) / total
            lift = _safe_div(sup_ab, (sup_a * sup_b))
            rows.append({
                "branch_id": str(branch_id),
                "a": a,
                "b": b,
                "support": sup_ab,
                "lift": lift
            })

    return pd.DataFrame(rows)


def _fallback_time_comovement(sales: pd.DataFrame, branch_id: str, item_a: str, item_b: str) -> float:
    """
    If no transactions exist, infer "go together" by time correlation of sales.
    Requires sales table with: branch_id, item_id, date/month, units_sold
    Returns correlation in [-1,1], maps to [0,1] as pseudo-support.
    """
    sdf = sales[sales["branch_id"].astype(str) == str(branch_id)].copy()
    if sdf.empty:
        return 0.0

    # choose time column
    time_col = "date" if "date" in sdf.columns else ("month" if "month" in sdf.columns else None)
    if time_col is None or "units_sold" not in sdf.columns:
        return 0.0

    piv = sdf.pivot_table(index=time_col, columns="item_id", values="units_sold", aggfunc="sum").fillna(0)
    if item_a not in piv.columns or item_b not in piv.columns:
        return 0.0

    corr = piv[item_a].corr(piv[item_b])
    if corr is None or math.isnan(corr):
        return 0.0
    return max(0.0, min(1.0, (corr + 1.0) / 2.0))  # map to [0,1]


def generate_bundle_suggestions(
    item_sales: pd.DataFrame,
    transactions: Optional[pd.DataFrame] = None,
    low_sales_quantile: float = 0.30,
    anchor_sales_quantile: float = 0.70,
    min_unit_margin: float = 0.10,
    target_bundle_margin: float = 0.15,
    max_discount_pct: float = 0.25,
    top_k_per_branch: int = 10
) -> pd.DataFrame:
    """
    item_sales: required columns (per branch-item):
      - branch_id
      - item_id or product_id
      - units_sold
      - revenue OR price
      - cost OR profit (with revenue)

    transactions: optional transaction-level table:
      - branch_id
      - item_id/product_id
      - order_id OR (customer_id & date) OR date

    Returns a dataframe of bundle suggestions.
    """
    sales = _infer_price_cost(item_sales)

    # identify low sellers and anchors per branch
    out_rows: List[BundleSuggestion] = []

    # build pair stats if transactions provided
    pair_df = pd.DataFrame()
    baskets = None
    if transactions is not None and not transactions.empty:
        baskets = _build_transactions(transactions)
        pair_df = _pair_stats(baskets)

    for branch_id, g in sales.groupby("branch_id"):
        g = g.copy()
        g["branch_id"] = g["branch_id"].astype(str)
        branch_id_str = str(branch_id)

        # quantile thresholds
        low_thr = g["units_sold"].quantile(low_sales_quantile) if "units_sold" in g.columns else 0
        anchor_thr = g["units_sold"].quantile(anchor_sales_quantile) if "units_sold" in g.columns else 0

        low_items = g[g["units_sold"] <= low_thr].copy()
        anchors = g[(g["units_sold"] >= anchor_thr) & (g["unit_margin"] >= min_unit_margin)].copy()

        if low_items.empty or anchors.empty:
            continue

        # rank anchors: high units * margin
        anchors["anchor_strength"] = anchors["units_sold"] * anchors["unit_margin"]
        anchors = anchors.sort_values("anchor_strength", ascending=False).head(30)

        # for each low item, find best anchor by lift/support (or fallback)
        for _, low in low_items.iterrows():
            low_id = str(low["item_id"])
            low_price = float(low["price"])
            low_cost = float(low["unit_cost"])
            low_margin = float(low["unit_margin"])
            low_units = float(low.get("units_sold", 0))

            # skip items that are truly loss-making unless anchor can cover it
            # (we still allow, but will ensure bundle margin later)
            best_candidates = []

            for _, anc in anchors.iterrows():
                anc_id = str(anc["item_id"])
                anc_price = float(anc["price"])
                anc_cost = float(anc["unit_cost"])
                anc_units = float(anc.get("units_sold", 0))

                # association strength
                support = 0.0
                lift = 1.0

                if not pair_df.empty:
                    # find pair row
                    a, b = (low_id, anc_id) if low_id < anc_id else (anc_id, low_id)
                    row = pair_df[(pair_df["branch_id"] == branch_id_str) & (pair_df["a"] == a) & (pair_df["b"] == b)]
                    if not row.empty:
                        support = float(row.iloc[0]["support"])
                        lift = float(row.iloc[0]["lift"])
                else:
                    # fallback pseudo-support from time comovement
                    support = _fallback_time_comovement(sales, branch_id_str, low_id, anc_id)
                    lift = 1.0 + support  # weak heuristic

                # prefer: strong anchor + low seller + high association
                score = (anc_units * 0.5) + (lift * 10.0) + (support * 20.0) - (low_units * 0.1)
                best_candidates.append((score, anc_id, anc_price, anc_cost, support, lift))

            if not best_candidates:
                continue

            best_candidates.sort(reverse=True)
            score, anc_id, anc_price, anc_cost, support, lift = best_candidates[0]

            # compute bundle economics
            full_price = anc_price + low_price
            full_cost = anc_cost + low_cost

            # choose a discount that still hits target_bundle_margin
            # profit = price*(1-discount) - cost >= target_margin * price*(1-discount)
            # => price*(1-discount) - cost >= target_margin * price*(1-discount)
            # => (1-target_margin)*price*(1-discount) >= cost
            # => (1-discount) >= cost / ((1-target_margin)*price)
            denom = (1.0 - target_bundle_margin) * full_price
            min_keep = (full_cost / denom) if denom > 0 else 1.0
            max_discount_allowed_by_margin = max(0.0, 1.0 - min_keep)

            discount = min(max_discount_pct, max_discount_allowed_by_margin)
            if discount < 0.01:
                # can’t discount while keeping margin; still propose a bundle with 0 discount (cross-sell)
                discount = 0.0

            bundle_price = full_price * (1.0 - discount)
            expected_profit = bundle_price - full_cost

            if expected_profit <= 0:
                # not acceptable
                continue

            reason = "Boost low-seller using strong anchor"
            if low_margin < 0:
                reason = "Loss-making item covered by bundle"

            out_rows.append(BundleSuggestion(
                branch_id=branch_id_str,
                bundle_items=[anc_id, low_id],
                discount_pct=round(discount * 100, 1),
                bundle_price=round(bundle_price, 2),
                expected_profit=round(expected_profit, 2),
                support=round(support, 4),
                lift=round(lift, 3),
                reason=reason
            ))

    # finalize dataframe
    df_out = pd.DataFrame([{
        "branch_id": r.branch_id,
        "bundle_items": "+".join(r.bundle_items),
        "discount_pct": r.discount_pct,
        "bundle_price": r.bundle_price,
        "expected_profit": r.expected_profit,
        "support": r.support,
        "lift": r.lift,
        "reason": r.reason
    } for r in out_rows])

    if df_out.empty:
        return df_out

    # rank bundles per branch
    df_out["score"] = df_out["expected_profit"] + (df_out["lift"] * 2.0) + (df_out["support"] * 50.0)
    df_out = df_out.sort_values(["branch_id", "score"], ascending=[True, False])

    # top k per branch
    df_out = df_out.groupby("branch_id").head(top_k_per_branch).drop(columns=["score"])
    return df_out.reset_index(drop=True)