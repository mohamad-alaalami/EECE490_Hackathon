#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import MinMaxScaler, StandardScaler


FEATURE_COLS = ["margin", "growth", "volatility", "food_share", "avg_revenue"]


def safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0 or pd.isna(denominator):
        return 0.0
    return float(numerator) / float(denominator)


def load_monthly(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in ["revenue", "profit", "food_revenue", "beverage_revenue"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    df = df.sort_values(["branch_id", "date"]).reset_index(drop=True)
    return df


def build_branch_features(monthly: pd.DataFrame) -> pd.DataFrame:
    def per_branch(g: pd.DataFrame) -> pd.Series:
        g = g.sort_values("date")
        first_rev = float(g["revenue"].iloc[0]) if len(g) else 0.0
        last_rev = float(g["revenue"].iloc[-1]) if len(g) else 0.0
        avg_revenue = float(g["revenue"].mean())
        total_revenue = float(g["revenue"].sum())
        total_profit = float(g["profit"].sum())
        total_food = float(g["food_revenue"].sum())
        total_beverage = float(g["beverage_revenue"].sum())
        std_revenue = float(g["revenue"].std())

        return pd.Series(
            {
                "avg_revenue": avg_revenue,
                "total_revenue": total_revenue,
                "total_profit": total_profit,
                "margin": safe_div(total_profit, total_revenue),
                "growth": safe_div(last_rev - first_rev, first_rev),
                "volatility": safe_div(std_revenue, avg_revenue),
                "food_share": safe_div(total_food, total_revenue),
                "beverage_share": safe_div(total_beverage, total_revenue),
            }
        )

    features = monthly.groupby("branch_id", as_index=False).apply(per_branch, include_groups=False)
    features = features.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    features = features.sort_values("branch_id").reset_index(drop=True)
    return features


def cluster_branches(features: pd.DataFrame) -> tuple[pd.DataFrame, int, float]:
    x = features[FEATURE_COLS].apply(pd.to_numeric, errors="coerce")
    x = x.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    x_scaled = StandardScaler().fit_transform(x)

    best_k = -1
    best_score = -1.0
    best_labels: np.ndarray | None = None

    for k in [3, 4, 5]:
        model = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = model.fit_predict(x_scaled)
        score = silhouette_score(x_scaled, labels)
        if score > best_score:
            best_k = k
            best_score = score
            best_labels = labels

    out = features.copy()
    out["cluster"] = best_labels
    return out, best_k, best_score


def add_health_and_opportunity(clusters: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = clusters.copy()
    df["margin_scaled"] = 0.0
    df["growth_scaled"] = 0.0
    df["volatility_scaled"] = 0.0
    df["avg_revenue_scaled"] = 0.0

    for _, idx in df.groupby("cluster").groups.items():
        subset = df.loc[idx, ["margin", "growth", "volatility", "avg_revenue"]].apply(pd.to_numeric, errors="coerce").fillna(0.0)
        scaled = MinMaxScaler().fit_transform(subset)
        df.loc[idx, "margin_scaled"] = scaled[:, 0]
        df.loc[idx, "growth_scaled"] = scaled[:, 1]
        df.loc[idx, "volatility_scaled"] = scaled[:, 2]
        df.loc[idx, "avg_revenue_scaled"] = scaled[:, 3]

    df["volatility_inverse"] = 1.0 - df["volatility_scaled"]
    df["health_score"] = (
        0.4 * df["margin_scaled"]
        + 0.2 * df["growth_scaled"]
        + 0.2 * df["volatility_inverse"]
        + 0.2 * df["avg_revenue_scaled"]
    )

    benchmark_rows = (
        df.sort_values(["cluster", "health_score"], ascending=[True, False])
        .groupby("cluster", as_index=False)
        .head(1)
        .loc[:, ["cluster", "branch_id", "health_score", "margin"]]
        .rename(columns={"branch_id": "cluster_benchmark", "margin": "benchmark_margin"})
        .sort_values("cluster")
        .reset_index(drop=True)
    )

    df = df.merge(benchmark_rows[["cluster", "cluster_benchmark", "benchmark_margin"]], on="cluster", how="left")
    df["potential_profit"] = df["total_revenue"] * df["benchmark_margin"]
    df["opportunity_gap"] = df["potential_profit"] - df["total_profit"]
    df["opportunity_gap"] = df["opportunity_gap"].clip(lower=0.0)
    df = df.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    final_cols = [
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
    return df[final_cols], benchmark_rows


def save_plots(clusters_df: pd.DataFrame, final_df: pd.DataFrame, plots_dir: Path) -> list[Path]:
    plots_dir.mkdir(parents=True, exist_ok=True)
    output_files: list[Path] = []

    # 1) cluster_pca_map.png
    x = clusters_df[FEATURE_COLS].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    x_scaled = StandardScaler().fit_transform(x)
    pca = PCA(n_components=2, random_state=42)
    comps = pca.fit_transform(x_scaled)
    pca_df = pd.DataFrame({"pc1": comps[:, 0], "pc2": comps[:, 1], "cluster": clusters_df["cluster"]})

    plt.figure(figsize=(11, 7))
    for c in sorted(pca_df["cluster"].unique()):
        subset = pca_df[pca_df["cluster"] == c]
        plt.scatter(subset["pc1"], subset["pc2"], s=90, alpha=0.8, label=f"Cluster {c}")
    plt.title("Branch Clusters on PCA Map")
    plt.xlabel("Principal Component 1")
    plt.ylabel("Principal Component 2")
    plt.legend()
    plt.tight_layout()
    p1 = plots_dir / "cluster_pca_map.png"
    plt.savefig(p1, dpi=150)
    plt.close()
    output_files.append(p1)

    # 2) opportunity_gap_bar.png
    bar_df = final_df.sort_values("opportunity_gap", ascending=False).reset_index(drop=True)
    colors = plt.cm.Set2(bar_df["cluster"] / max(1, bar_df["cluster"].max()))
    plt.figure(figsize=(14, 7))
    plt.bar(bar_df["branch_id"], bar_df["opportunity_gap"], color=colors)
    plt.title("Opportunity Gap by Branch (Descending)")
    plt.xlabel("Branch ID")
    plt.ylabel("Opportunity Gap")
    plt.xticks(rotation=75, ha="right")
    plt.tight_layout()
    p2 = plots_dir / "opportunity_gap_bar.png"
    plt.savefig(p2, dpi=150)
    plt.close()
    output_files.append(p2)

    # 3) cluster_profile.png
    profile = (
        final_df.groupby("cluster", as_index=False)[["margin", "growth", "volatility", "food_share", "avg_revenue"]]
        .mean()
        .sort_values("cluster")
    )
    metrics = ["margin", "growth", "volatility", "food_share", "avg_revenue"]
    x_pos = np.arange(len(profile["cluster"]))
    width = 0.16

    plt.figure(figsize=(14, 8))
    for i, metric in enumerate(metrics):
        plt.bar(x_pos + (i - 2) * width, profile[metric], width=width, label=metric)
    plt.title("Cluster Profile (Mean Metrics)")
    plt.xlabel("Cluster")
    plt.ylabel("Mean Value")
    plt.xticks(x_pos, profile["cluster"].astype(int))
    plt.legend()
    plt.tight_layout()
    p3 = plots_dir / "cluster_profile.png"
    plt.savefig(p3, dpi=150)
    plt.close()
    output_files.append(p3)

    # 4) health_score_distribution.png
    plt.figure(figsize=(10, 7))
    cluster_ids = sorted(final_df["cluster"].unique())
    data = [final_df.loc[final_df["cluster"] == c, "health_score"].values for c in cluster_ids]
    plt.boxplot(data, tick_labels=[str(c) for c in cluster_ids])
    plt.title("Health Score Distribution by Cluster")
    plt.xlabel("Cluster")
    plt.ylabel("Health Score")
    plt.tight_layout()
    p4 = plots_dir / "health_score_distribution.png"
    plt.savefig(p4, dpi=150)
    plt.close()
    output_files.append(p4)

    return output_files


def main() -> None:
    parser = argparse.ArgumentParser(description="Run branch analytics pipeline: features, clustering, health score, opportunity gap, and plots.")
    parser.add_argument("--input", default="data/processed/branch_monthly_aggregated.csv")
    parser.add_argument("--features-out", default="data/processed/branch_features.csv")
    parser.add_argument("--clusters-out", default="data/processed/branch_clusters.csv")
    parser.add_argument("--final-out", default="data/processed/branch_final_analysis.csv")
    parser.add_argument("--plots-dir", default="reports/figures")
    args = parser.parse_args()

    input_path = Path(args.input)
    features_out = Path(args.features_out)
    clusters_out = Path(args.clusters_out)
    final_out = Path(args.final_out)
    plots_dir = Path(args.plots_dir)

    monthly = load_monthly(input_path)
    features = build_branch_features(monthly)
    features_out.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(features_out, index=False)

    clusters, best_k, best_score = cluster_branches(features)
    clusters_out.parent.mkdir(parents=True, exist_ok=True)
    clusters.to_csv(clusters_out, index=False)

    final_df, benchmarks = add_health_and_opportunity(clusters)
    final_out.parent.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(final_out, index=False)

    plot_files = save_plots(clusters, final_df, plots_dir)

    print(f"Best k: {best_k}")
    print(f"Silhouette score: {best_score:.6f}")
    print("\nBranch count per cluster:")
    print(clusters["cluster"].value_counts().sort_index().to_string())

    print("\nTotal opportunity gap:")
    print(f"{final_df['opportunity_gap'].sum():.2f}")

    print("\nTop 5 branches by opportunity_gap:")
    print(
        final_df.sort_values("opportunity_gap", ascending=False)
        .loc[:, ["branch_id", "cluster", "opportunity_gap"]]
        .head(5)
        .to_string(index=False)
    )

    print("\nBenchmark branch per cluster:")
    print(benchmarks.loc[:, ["cluster", "cluster_benchmark", "health_score"]].to_string(index=False))

    print("\nGenerated files:")
    generated = [features_out, clusters_out, final_out] + plot_files
    for p in generated:
        print(str(p.as_posix()))


if __name__ == "__main__":
    main()
