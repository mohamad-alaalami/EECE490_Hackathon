"""
Flask app factory for Stories Coffee Dashboard.

Run locally:
1) pip install -r requirements.txt
2) python app.py

Run with gunicorn:
   gunicorn -b 0.0.0.0:5000 wsgi:app
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

import pandas as pd
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from data_loader import DataLoadError, load_all_data
from features import build_branch_dataset
from model import build_cluster_summary, run_model
from utils import normalize_branch_key


def create_app() -> Flask:
    """Factory function to create and configure Flask app."""
    app = Flask(__name__)
    CORS(app)

    # Global cache for branch data
    cache: Dict[str, object] = {
        "branches_df": pd.DataFrame(),
        "cluster_summary": [],
        "monthly_by_branch": {},
        "top_products_by_branch": {},
        "load_error": None,
    }

    def _reload_cache() -> None:
        """Load and process branch data from CSV files."""
        try:
            use_mock_fallback = os.getenv("USE_MOCK_FALLBACK", "0") == "1"
            loaded = load_all_data(use_mock_fallback=use_mock_fallback)
            branch_df, monthly_by_branch, top_products_by_branch = build_branch_dataset(
                loaded.monthly, loaded.category, loaded.product
            )
            scored_df = run_model(branch_df)
            cluster_summary = build_cluster_summary(scored_df)

            cache["branches_df"] = scored_df
            cache["cluster_summary"] = cluster_summary
            cache["monthly_by_branch"] = monthly_by_branch
            cache["top_products_by_branch"] = top_products_by_branch
            cache["load_error"] = None
        except Exception as exc:
            cache["load_error"] = str(exc)
            cache["branches_df"] = pd.DataFrame()
            cache["cluster_summary"] = []
            cache["monthly_by_branch"] = {}
            cache["top_products_by_branch"] = {}

    def _branch_payload(df: pd.DataFrame) -> List[dict]:
        """Convert DataFrame row to API payload."""
        if df.empty:
            return []
        out = []
        for _, r in df.iterrows():
            out.append(
                {
                    "branch": r["branch"],
                    "cluster": int(r["cluster"]),
                    "health_score": round(float(r["health_score"]), 2),
                    "gap_profit": round(float(r["gap_profit"]), 2),
                    "avg_revenue": round(float(r.get("avg_monthly_revenue", 0.0)), 2),
                    "margin": round(float(r.get("overall_margin", 0.0)), 4),
                    "growth": round(float(r.get("growth_rate", 0.0)), 4),
                    "volatility": round(float(r.get("volatility", 0.0)), 4),
                    "bev_share": round(float(r.get("beverage_share", 0.0)), 4),
                    "food_share": round(float(r.get("food_share", 0.0)), 4),
                    "top5_profit_share": round(float(r.get("top5_profit_share", 0.0)), 4),
                    "sku_count": int(r.get("sku_count", 0)),
                    "may_june_drop": round(float(r.get("may_june_drop", 0.0)), 4),
                    "pca_1": round(float(r.get("pca_1", 0.0)), 4),
                    "pca_2": round(float(r.get("pca_2", 0.0)), 4),
                }
            )
        return out

    # Frontend routes
    @app.get("/")
    def index():
        """Serve main frontend."""
        frontend_path = Path(__file__).parent / "frontend" / "index.html"
        if frontend_path.exists():
            return send_from_directory("frontend", "index.html")
        return jsonify({"error": "Frontend not found"}), 404

    @app.get("/styles.css")
    def serve_css():
        """Serve frontend CSS."""
        return send_from_directory("frontend", "styles.css")

    @app.get("/app.js")
    def serve_js():
        """Serve frontend JavaScript."""
        return send_from_directory("frontend", "app.js")

    @app.get("/health")
    def health():
        """Health check for load balancers / Render."""
        return jsonify({"status": "ok"})

    @app.get("/api/health-check")
    def api_health_check():
        """API health check with data load status."""
        branches_df: pd.DataFrame = cache["branches_df"]
        payload = {"status": "ok", "branches_loaded": int(len(branches_df))}
        if cache["load_error"]:
            payload["status"] = "error"
            payload["error"] = cache["load_error"]
        return jsonify(payload)

    @app.get("/api/branches")
    def api_branches():
        """Get all branches with metrics."""
        if cache["load_error"]:
            return jsonify({"error": cache["load_error"]}), 500
        branches_df: pd.DataFrame = cache["branches_df"]
        return jsonify(_branch_payload(branches_df))

    @app.get("/api/cluster-summary")
    def api_cluster_summary():
        """Get cluster summary."""
        if cache["load_error"]:
            return jsonify({"error": cache["load_error"]}), 500
        return jsonify(cache["cluster_summary"])

    @app.get("/api/branch/<branch_name>")
    def api_branch_detail(branch_name: str):
        """Get detailed metrics for a specific branch."""
        if cache["load_error"]:
            return jsonify({"error": cache["load_error"]}), 500

        branches_df: pd.DataFrame = cache["branches_df"]
        if branches_df.empty:
            return jsonify({"error": "No branch data loaded."}), 404

        query_key = normalize_branch_key(branch_name)
        row_match = branches_df[branches_df["branch_key"] == query_key]
        if row_match.empty:
            return jsonify({"error": f"Branch not found: {branch_name}"}), 404

        row = row_match.iloc[0]
        monthly = cache["monthly_by_branch"].get(query_key, [])
        top_products = cache["top_products_by_branch"].get(query_key, [])

        avg_margin = float(row.get("overall_margin", 0.0))
        monthly_with_profit = [
            {
                "month": p["month"],
                "revenue": round(float(p["revenue"]), 2),
                "profit": round(float(p["revenue"] * avg_margin), 2),
            }
            for p in monthly
        ]

        payload = {
            "branch": row["branch"],
            "cluster": int(row["cluster"]),
            "health_score": round(float(row["health_score"]), 2),
            "gap_profit": round(float(row["gap_profit"]), 2),
            "monthly": monthly_with_profit,
            "top_products": top_products,
        }
        return jsonify(payload)

    # Load data on startup
    _reload_cache()

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=True)
