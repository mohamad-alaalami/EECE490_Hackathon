#!/usr/bin/env python3
import argparse
import numpy as np
import pandas as pd


def safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0 or pd.isna(denominator):
        return 0.0
    return numerator / denominator


def build_features(input_path: str, output_path: str) -> pd.DataFrame:
    df = pd.read_csv(input_path)
    expected = ["branch_id", "date", "revenue", "profit", "food_revenue", "beverage_revenue"]
    missing = [c for c in expected if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    numeric_cols = ["revenue", "profit", "food_revenue", "beverage_revenue"]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.sort_values(["branch_id", "date"]).reset_index(drop=True)

    def per_branch(g: pd.DataFrame) -> pd.Series:
        g = g.sort_values("date")
        first_rev = float(g["revenue"].iloc[0]) if len(g) else 0.0
        last_rev = float(g["revenue"].iloc[-1]) if len(g) else 0.0

        avg_revenue = float(g["revenue"].mean())
        total_revenue = float(g["revenue"].sum())
        total_profit = float(g["profit"].sum())
        total_food_revenue = float(g["food_revenue"].sum())
        total_beverage_revenue = float(g["beverage_revenue"].sum())
        std_revenue = float(g["revenue"].std())

        return pd.Series(
            {
                "avg_revenue": avg_revenue,
                "total_revenue": total_revenue,
                "total_profit": total_profit,
                "margin": safe_div(total_profit, total_revenue),
                "growth": safe_div(last_rev - first_rev, first_rev),
                "volatility": safe_div(std_revenue, avg_revenue),
                "food_share": safe_div(total_food_revenue, total_revenue),
                "beverage_share": safe_div(total_beverage_revenue, total_revenue),
            }
        )

    features = df.groupby("branch_id", as_index=False).apply(per_branch, include_groups=False)
    features = features.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    features = features.sort_values("branch_id").reset_index(drop=True)
    features.to_csv(output_path, index=False)
    return features


def main() -> None:
    parser = argparse.ArgumentParser(description="Create branch-level features from monthly aggregated branch data.")
    parser.add_argument("--input", default="data/processed/branch_monthly_aggregated.csv")
    parser.add_argument("--output", default="data/processed/branch_features.csv")
    args = parser.parse_args()

    features = build_features(args.input, args.output)

    print("First 10 rows:")
    print(features.head(10).to_string(index=False))
    print("\nColumn names:")
    print(list(features.columns))
    print("\nShape:")
    print(features.shape)
    print("\nBasic descriptive stats:")
    print(features.describe(include="all").to_string())


if __name__ == "__main__":
    main()
