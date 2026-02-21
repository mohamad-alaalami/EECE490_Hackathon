import os
import pandas as pd

RAW_DIR = "data/raw"
OUT_DIR = "data/processed"
os.makedirs(OUT_DIR, exist_ok=True)

# Temporary dummy outputs so the API works before real data is ready
branches = pd.DataFrame([
    {"branch_id": "1", "cluster": 0, "health_score": 0.72, "gap": 12000,
     "margin_pct": 0.18, "growth_rate": 0.05, "revenue_volatility": 0.12},
    {"branch_id": "2", "cluster": 1, "health_score": 0.41, "gap": 34000,
     "margin_pct": 0.10, "growth_rate": -0.02, "revenue_volatility": 0.30},
])

monthly = pd.DataFrame([
    {"branch_id": "1", "month": "2025-01", "revenue": 50000, "profit": 9000},
    {"branch_id": "1", "month": "2025-02", "revenue": 52000, "profit": 9500},
    {"branch_id": "2", "month": "2025-01", "revenue": 45000, "profit": 5000},
    {"branch_id": "2", "month": "2025-02", "revenue": 42000, "profit": 3500},
])

branches.to_csv(os.path.join(OUT_DIR, "branches_scored.csv"), index=False)
monthly.to_csv(os.path.join(OUT_DIR, "branch_monthly.csv"), index=False)

print("✅ Wrote data/processed/branches_scored.csv and branch_monthly.csv")