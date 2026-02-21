from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from utils import safe_div


STRUCTURAL_FEATURES = [
    "overall_margin",
    "growth_rate",
    "volatility",
    "beverage_share",
    "top5_profit_share",
]
FIXED_CLUSTER_COUNT = 3


def _fit_clusters(df: pd.DataFrame) -> np.ndarray:
    if len(df) <= 1:
        return np.zeros(len(df), dtype=int)

    X = df[STRUCTURAL_FEATURES].copy()
    for col in STRUCTURAL_FEATURES:
        X[col] = pd.to_numeric(X[col], errors="coerce")
        X[col] = X[col].fillna(X[col].median() if X[col].notna().any() else 0.0)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    cluster_count = min(FIXED_CLUSTER_COUNT, len(df))
    if cluster_count <= 1:
        return np.zeros(len(df), dtype=int)

    km = KMeans(n_clusters=cluster_count, n_init=20, random_state=42)
    return km.fit_predict(X_scaled)


def _compute_pca_2d(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    if len(df) == 0:
        return np.array([]), np.array([])

    X = df[STRUCTURAL_FEATURES].copy()
    for col in STRUCTURAL_FEATURES:
        X[col] = pd.to_numeric(X[col], errors="coerce")
        X[col] = X[col].fillna(X[col].median() if X[col].notna().any() else 0.0)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    if len(df) < 2:
        return np.zeros(len(df)), np.zeros(len(df))

    pca = PCA(n_components=2, random_state=42)
    transformed = pca.fit_transform(X_scaled)
    return transformed[:, 0], transformed[:, 1]


def _compute_health_score(df: pd.DataFrame) -> pd.Series:
    margin_component = np.clip(df["overall_margin"] / 0.40, 0, 1)
    growth_component = np.clip((df["growth_rate"] + 0.20) / 0.40, 0, 1)
    volatility_component = np.clip(1 - (df["volatility"] / 0.40), 0, 1)
    mix_balance_component = np.clip(1 - (np.abs(df["beverage_share"] - 0.5) / 0.5), 0, 1)
    concentration_component = np.clip(1 - df["top5_profit_share"], 0, 1)

    score = (
        0.35 * margin_component
        + 0.25 * growth_component
        + 0.20 * volatility_component
        + 0.10 * mix_balance_component
        + 0.10 * concentration_component
    ) * 100.0
    return np.clip(score, 0, 100)


def run_model(branch_df: pd.DataFrame) -> pd.DataFrame:
    if branch_df.empty:
        return branch_df.copy()

    out = branch_df.copy()
    out["cluster"] = _fit_clusters(out)
    pca_1, pca_2 = _compute_pca_2d(out)
    out["pca_1"] = pca_1
    out["pca_2"] = pca_2
    out["health_score"] = _compute_health_score(out)

    benchmark_rows = (
        out.sort_values("health_score", ascending=False)
        .groupby("cluster", as_index=False)
        .first()[["cluster", "branch", "overall_margin"]]
        .rename(
            columns={
                "branch": "benchmark_branch",
                "overall_margin": "benchmark_margin",
            }
        )
    )
    out = out.merge(benchmark_rows, on="cluster", how="left")

    out["gap_profit"] = (
        out["benchmark_margin"].fillna(0.0) * out["branch_revenue_est"].fillna(0.0)
    ) - out["branch_profit_est"].fillna(0.0)

    return out


def build_cluster_summary(scored_df: pd.DataFrame) -> List[dict]:
    if scored_df.empty:
        return []

    summary = (
        scored_df.groupby("cluster", as_index=False)
        .agg(
            count=("branch", "count"),
            avg_margin=("overall_margin", "mean"),
            avg_growth=("growth_rate", "mean"),
            avg_volatility=("volatility", "mean"),
            avg_bev_share=("beverage_share", "mean"),
            avg_food_share=("food_share", "mean"),
            avg_top5_profit_share=("top5_profit_share", "mean"),
            best_branch_name=("benchmark_branch", "first"),
        )
        .sort_values("cluster")
    )
    return summary.to_dict(orient="records")
