# Branch Performance Intelligence Dashboard (Clustering + Health Score + Opportunity Gap)

A lightweight, executive-facing dashboard that groups branches by **structural behavior**, scores branch **health** relative to similar peers, and quantifies **unrealized profit opportunity** (“gap-to-best-in-cluster”).

Instead of clustering on raw revenue (size-dominated and misleading), this system clusters branches on **behavioral ratios** (margin, growth, volatility, product mix) to generate clear **branch personas** and actionable priorities.

---

## What This Delivers (CEO Language)

✅ **“Which branches are underperforming relative to similar peers?”**  
✅ **“How much profit are we leaving on the table?”**  
✅ **“What characterizes each branch cluster?”**  

Outputs:
- **Structural clusters** (branch personas)
- **Health score** per branch (within-cluster normalization)
- **Gap-to-best** metric (benchmarking vs. top peer in cluster)
- A simple **decision dashboard**: Overview → Cluster → Branch drill-down

---

## Method Overview

### 1) Structural Behavior Clustering (Branch Personas)
For each branch, we engineer *behavioral features* so size doesn’t dominate:

- Avg monthly revenue  
- Avg monthly profit  
- **Margin %** = profit / revenue  
- Beverage revenue share  
- Food revenue share  
- **Revenue growth rate** (first month vs last month)  
- **Revenue volatility** = std(revenue) / mean(revenue)

We aggregate monthly data → **one row per branch**, standardize features, then run **KMeans** (k=3 or 4).

---

### 2) Health Score (Within Cluster)
Inside each cluster:

**Health Score** (example weights, defensible and simple):

`Health = 0.4*Margin + 0.2*Growth + 0.2*(1-Volatility) + 0.2*Revenue`

All components are normalized **within the cluster**.

---

### 3) Opportunity Gap (Gap-to-Best-in-Cluster)
For each cluster, the **top branch** becomes the benchmark.

We estimate “potential profit” if the branch matched the benchmark margin:

`Potential Profit = Benchmark Margin * Branch Revenue`  
`Gap = Potential Profit - Actual Profit`

This quantifies **unrealized profit opportunity** in real dollars.

---

## Dashboard Pages

### Overview
- Total opportunity gap across all branches
- Table: Branch | Cluster | Health Score | Gap
- Sort by highest gap → instantly shows where profit is leaking

### Cluster View
- Cluster averages (margin, growth, volatility, mix)
- Cluster profile chart (radar/bar) to explain personas visually

### Branch Detail
- Revenue trend line
- Margin trend
- Health score breakdown
- Gap vs cluster leader
- **Bundle Recommendations** (see Bundle Recommender section)

---

## Bundle Recommender

### What It Does
Identifies product bundles that increase basket size and same-visit profitability:

- **Low-sales items** bundled with **anchor items** (high volume)
- Strategic discount to meet target bundle margin
- Outputs: **lift** (correlation), **support** (co-occurrence %), **expected profit**

### How to Run

```bash
python scripts/run_bundles.py
```

Creates: `data/processed/bundles.csv`

Input files:
- `data/raw/branch_item_sales.csv` (required): branch_id, item_id, revenue, cost, units_sold
- `data/raw/transactions.csv` (optional): branch_id, transaction_id, item1_id, item2_id, ...

Output columns: branch_id, bundle_items, discount_pct, bundle_price, expected_profit, reason, lift, support

### Front-end
Shows in **Branch Detail** view under "Bundle Recommendations":
- If no bundles exist: "No bundle suggestions. Run: `python scripts/run_bundles.py`"
- Otherwise: table with Bundle Items, Discount, Price, Profit, Reason, Lift, Support

---

## Tech Stack

- **Python**: pandas, numpy, scikit-learn  
- **Backend**: Flask  
- **Frontend**: Plotly / Chart.js (simple HTML templates)  
- **Data**: CSV (no database needed for demo)

---

## Project Structure
