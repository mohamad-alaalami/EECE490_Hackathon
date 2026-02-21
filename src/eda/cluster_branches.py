#!/usr/bin/env python3
import argparse
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler


FEATURE_COLS = ["margin", "growth", "volatility", "food_share", "avg_revenue"]


def run_clustering(input_path: str, output_path: str) -> tuple[int, float, pd.DataFrame, pd.Series]:
    df = pd.read_csv(input_path)

    required_cols = ["branch_id"] + FEATURE_COLS
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    x = df[FEATURE_COLS].apply(pd.to_numeric, errors="coerce")
    x = x.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(x)

    best_k = None
    best_score = -1.0
    best_labels = None

    for k in [3, 4, 5]:
        model = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = model.fit_predict(x_scaled)
        score = silhouette_score(x_scaled, labels)
        if score > best_score:
            best_score = score
            best_k = k
            best_labels = labels

    out_df = df.copy()
    out_df["cluster"] = best_labels
    out_df.to_csv(output_path, index=False)

    cluster_summary = (
        out_df.groupby("cluster", as_index=False)[FEATURE_COLS]
        .mean()
        .sort_values("cluster")
        .reset_index(drop=True)
    )
    cluster_counts = out_df["cluster"].value_counts().sort_index()

    return best_k, best_score, cluster_summary, cluster_counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Cluster branches from branch-level features.")
    parser.add_argument("--input", default="data/processed/branch_features.csv")
    parser.add_argument("--output", default="data/processed/branch_clusters.csv")
    args = parser.parse_args()

    best_k, best_score, cluster_summary, cluster_counts = run_clustering(args.input, args.output)

    print(f"Best k: {best_k}")
    print(f"Best silhouette score: {best_score:.6f}")
    print("\nCluster summary (mean feature values):")
    print(cluster_summary.to_string(index=False))
    print("\nNumber of branches per cluster:")
    print(cluster_counts.to_string())


if __name__ == "__main__":
    main()
