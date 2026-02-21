#!/usr/bin/env python3
import argparse
import re
import pandas as pd


MONTH_COL_RE = re.compile(r"^[A-Za-z]{3}\s+\d{4}$")


def normalize_branch(value: str) -> str:
    s = str(value).strip().lower()
    s = re.sub(r"^stories\s*[-–]?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s)
    return s


def to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    ).fillna(0.0)


def load_monthly_revenue(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["branch_id"] = df["Branch"].map(normalize_branch)
    df = df[~df["branch_id"].isin({"", "total"})]
    df = df[df["branch_id"].str.contains(r"[a-z0-9]", regex=True, na=False)]
    month_cols = [c for c in df.columns if MONTH_COL_RE.match(str(c).strip())]

    long_df = df.melt(
        id_vars=["branch_id"],
        value_vars=month_cols,
        var_name="month_label",
        value_name="revenue",
    )
    long_df["revenue"] = to_num(long_df["revenue"])
    long_df["date"] = pd.to_datetime(long_df["month_label"], format="%b %Y", errors="coerce")
    long_df["date"] = long_df["date"].dt.to_period("M").dt.to_timestamp()

    out = (
        long_df.groupby(["branch_id", "date"], as_index=False)["revenue"]
        .sum()
        .sort_values(["branch_id", "date"])
    )
    return out


def load_branch_ratios(path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(path)
    df["branch_id"] = df["Branch"].map(normalize_branch)
    df["category"] = df["Category"].astype(str).str.strip().str.lower()
    df["total_cost"] = to_num(df["Total Cost"])
    df["total_profit"] = to_num(df["Total Profit"])
    df["category_revenue"] = df["total_cost"] + df["total_profit"]

    branch_totals = (
        df.groupby("branch_id", as_index=False)[["total_cost", "total_profit", "category_revenue"]]
        .sum()
        .rename(columns={"category_revenue": "branch_revenue_ref"})
    )
    branch_totals["profit_ratio"] = branch_totals.apply(
        lambda r: (r["total_profit"] / r["branch_revenue_ref"]) if r["branch_revenue_ref"] > 0 else 0.0,
        axis=1,
    )

    cat_pivot = (
        df.pivot_table(
            index="branch_id",
            columns="category",
            values="category_revenue",
            aggfunc="sum",
            fill_value=0.0,
        )
        .reset_index()
    )
    for c in ["food", "beverages"]:
        if c not in cat_pivot.columns:
            cat_pivot[c] = 0.0

    cat_pivot = cat_pivot.merge(
        branch_totals[["branch_id", "branch_revenue_ref"]],
        on="branch_id",
        how="left",
    )
    cat_pivot["food_share"] = cat_pivot.apply(
        lambda r: (r["food"] / r["branch_revenue_ref"]) if r["branch_revenue_ref"] > 0 else 0.0,
        axis=1,
    )
    cat_pivot["beverage_share"] = cat_pivot.apply(
        lambda r: (r["beverages"] / r["branch_revenue_ref"]) if r["branch_revenue_ref"] > 0 else 0.0,
        axis=1,
    )
    return branch_totals[["branch_id", "profit_ratio"]], cat_pivot[["branch_id", "food_share", "beverage_share"]]


def build_dataset(monthly_path: str, category_path: str, output_path: str) -> pd.DataFrame:
    monthly = load_monthly_revenue(monthly_path)
    profit_ratio_df, category_share_df = load_branch_ratios(category_path)

    out = monthly.merge(profit_ratio_df, on="branch_id", how="left")
    out = out.merge(category_share_df, on="branch_id", how="left")

    out["profit_ratio"] = out["profit_ratio"].fillna(0.0)
    out["food_share"] = out["food_share"].fillna(0.0)
    out["beverage_share"] = out["beverage_share"].fillna(0.0)

    out["profit"] = out["revenue"] * out["profit_ratio"]
    out["food_revenue"] = out["revenue"] * out["food_share"]
    out["beverage_revenue"] = out["revenue"] * out["beverage_share"]

    out = out[["branch_id", "date", "revenue", "profit", "food_revenue", "beverage_revenue"]]
    out = out.fillna(0.0)
    out["date"] = pd.to_datetime(out["date"]).dt.to_period("M").dt.to_timestamp()
    out = out.sort_values(["branch_id", "date"]).reset_index(drop=True)
    out.to_csv(output_path, index=False)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare branch-level monthly aggregation for clustering.")
    parser.add_argument("--monthly-sales", default="data/processed/monthly_sales_clean.csv")
    parser.add_argument("--category-summary", default="data/processed/category__summary_clean.csv")
    parser.add_argument("--output", default="data/processed/branch_monthly_aggregated.csv")
    args = parser.parse_args()

    df = build_dataset(args.monthly_sales, args.category_summary, args.output)

    print("First 10 rows:")
    print(df.head(10).to_string(index=False))
    print("\nColumn names:")
    print(list(df.columns))
    print("\nNumber of branches:")
    print(df["branch_id"].nunique())
    months_per_branch = df.groupby("branch_id")["date"].nunique()
    print("\nNumber of months per branch (min/max):")
    print(f"min={months_per_branch.min()}, max={months_per_branch.max()}")


if __name__ == "__main__":
    main()
