#!/usr/bin/env python3
import argparse
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler


SCALE_COLS = ["margin", "growth", "volatility", "avg_revenue"]


def cluster_scale_and_health(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    for col in ["margin_scaled", "growth_scaled", "volatility_scaled", "avg_revenue_scaled"]:
        out[col] = 0.0

    for cluster_id, idx in out.groupby("cluster").groups.items():
        cluster_slice = out.loc[idx, SCALE_COLS].apply(pd.to_numeric, errors="coerce").fillna(0.0)
        scaler = MinMaxScaler()
        scaled = scaler.fit_transform(cluster_slice)

        out.loc[idx, "margin_scaled"] = scaled[:, 0]
        out.loc[idx, "growth_scaled"] = scaled[:, 1]
        out.loc[idx, "volatility_scaled"] = scaled[:, 2]
        out.loc[idx, "avg_revenue_scaled"] = scaled[:, 3]

    out["volatility_inverse"] = 1.0 - out["volatility_scaled"]
    out["health_score"] = (
        0.4 * out["margin_scaled"]
        + 0.2 * out["growth_scaled"]
        + 0.2 * out["volatility_inverse"]
        + 0.2 * out["avg_revenue_scaled"]
    )
    return out


def add_benchmark_and_opportunity(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    # One benchmark branch per cluster based on highest health score.
    benchmark_rows = (
        df.sort_values(["cluster", "health_score"], ascending=[True, False])
        .groupby("cluster", as_index=False)
        .head(1)
        .loc[:, ["cluster", "branch_id", "health_score", "margin"]]
        .rename(columns={"margin": "benchmark_margin", "branch_id": "cluster_benchmark"})
        .sort_values("cluster")
        .reset_index(drop=True)
    )

    out = df.merge(
        benchmark_rows[["cluster", "cluster_benchmark", "benchmark_margin"]],
        on="cluster",
        how="left",
    )
    out["potential_profit"] = out["total_revenue"] * out["benchmark_margin"]
    out["opportunity_gap"] = out["potential_profit"] - out["total_profit"]
    out["opportunity_gap"] = out["opportunity_gap"].clip(lower=0.0)
    return out, benchmark_rows


def run(input_path: str, output_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(input_path)
    required = [
        "branch_id",
        "avg_revenue",
        "total_revenue",
        "total_profit",
        "margin",
        "growth",
        "volatility",
        "food_share",
        "beverage_share",
        "cluster",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    for c in required:
        if c not in ["branch_id"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    df = cluster_scale_and_health(df)
    df, benchmark_rows = add_benchmark_and_opportunity(df)
    df = df.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    out_cols = [
        "branch_id",
        "avg_revenue",
        "total_revenue",
        "total_profit",
        "margin",
        "growth",
        "volatility",
        "food_share",
        "beverage_share",
        "cluster",
        "health_score",
        "benchmark_margin",
        "potential_profit",
        "opportunity_gap",
    ]
    df[out_cols].to_csv(output_path, index=False)
    return df[out_cols], benchmark_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute branch health score and opportunity gap from branch clusters.")
    parser.add_argument("--input", default="data/processed/branch_clusters.csv")
    parser.add_argument("--output", default="data/processed/branch_final_analysis.csv")
    args = parser.parse_args()

    final_df, benchmark_rows = run(args.input, args.output)

    print("Benchmark branch per cluster (branch_id + health_score):")
    print(benchmark_rows[["cluster", "cluster_benchmark", "health_score"]].to_string(index=False))

    print("\nTop 5 branches by opportunity_gap:")
    print(
        final_df.sort_values("opportunity_gap", ascending=False)
        .loc[:, ["branch_id", "cluster", "opportunity_gap"]]
        .head(5)
        .to_string(index=False)
    )

    print("\nTotal opportunity_gap:")
    print(f"{final_df['opportunity_gap'].sum():.2f}")

    print("\nAverage health_score per cluster:")
    print(
        final_df.groupby("cluster", as_index=False)["health_score"]
        .mean()
        .sort_values("cluster")
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
