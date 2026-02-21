## Bundle Recommender Integration - Complete

### Changes Overview

**Backend (app.py):**
- Added `BUNDLES_FILE` path to `data/processed/bundles.csv`
- Added `bundles_df` to cache on startup
- New endpoint: `GET /api/bundles/<branch_id>` → returns JSON array of bundles for that branch
- Returns `[]` if bundles.csv doesn't exist (no error)

**Frontend (frontend/index.html):**
- New "Bundle Recommendations" section on Branch Detail page
- Shows loading state, empty state, error state, and data table

**Frontend (frontend/app.js):**
- Added `API.bundles(branchId)` endpoint call
- Added `loadAndRenderBundles(branchName)` async function
- Calls bundling API when opening branch detail
- Proper error handling and user messaging

**Tooling (Makefile):**
- New Makefile with commands: install, bundles, serve, test-local, test-bundles, clean

**Documentation (README.md):**
- New "Bundle Recommender" section explaining:
  - What it does
  - How to run: `python scripts/run_bundles.py`
  - Input schema
  - Output schema
  - Front-end display behavior

---

## Exact File Changes

### app.py
```python
# ADDED near top of create_app():
PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "data", "processed")
BUNDLES_FILE = os.path.join(PROCESSED_DIR, "bundles.csv")

# ADDED to cache dict:
"bundles_df": pd.DataFrame(),

# MODIFIED _reload_cache() to load bundles:
if os.path.exists(BUNDLES_FILE):
    cache["bundles_df"] = pd.read_csv(BUNDLES_FILE)
else:
    cache["bundles_df"] = pd.DataFrame()

# NEW ENDPOINT:
@app.get("/api/bundles/<branch_id>")
def api_bundles(branch_id: str):
    """Get bundle suggestions for a specific branch."""
    bundles_df: pd.DataFrame = cache["bundles_df"]
    if bundles_df.empty:
        return jsonify([])

    filtered = bundles_df[bundles_df["branch_id"].astype(str) == str(branch_id)]
    if filtered.empty:
        return jsonify([])

    result = []
    for _, row in filtered.iterrows():
        result.append({
            "branch_id": str(row["branch_id"]),
            "bundle_items": row.get("bundle_items", ""),
            "discount_pct": round(float(row.get("discount_pct", 0.0)), 4),
            "bundle_price": round(float(row.get("bundle_price", 0.0)), 2),
            "expected_profit": round(float(row.get("expected_profit", 0.0)), 2),
            "reason": row.get("reason", ""),
            "lift": round(float(row.get("lift", 0.0)), 4),
            "support": round(float(row.get("support", 0.0)), 4),
        })
    return jsonify(result)
```

### frontend/index.html
```html
<!-- NEW: Added after Monthly Revenue & Profit table -->
<article class="card table-card">
  <h3>Bundle Recommendations</h3>
  <div id="bundles-loading" class="hidden">
    <p>Loading bundle suggestions...</p>
  </div>
  <div id="bundles-empty" class="hidden">
    <p><small>No bundle suggestions for this branch yet.</small></p>
    <p><small>Run: <code>python scripts/run_bundles.py</code></small></p>
  </div>
  <div id="bundles-error" class="hidden">
    <p id="bundles-error-text" style="color: #d9534f;"></p>
  </div>
  <div class="table-wrap" id="bundles-wrap" style="display: none;">
    <table>
      <thead>
        <tr>
          <th>Bundle Items</th>
          <th>Discount</th>
          <th>Bundle Price</th>
          <th>Expected Profit</th>
          <th>Reason</th>
          <th>Lift</th>
          <th>Support</th>
        </tr>
      </thead>
      <tbody id="bundles-tbody"></tbody>
    </table>
  </div>
</article>
```

### frontend/app.js
```javascript
// ADDED to API:
bundles: (branchId) =>
  `${API_BASE}/api/bundles/${encodeURIComponent(branchId)}`,

// ADDED to elements:
bundlesLoading: document.getElementById("bundles-loading"),
bundlesEmpty: document.getElementById("bundles-empty"),
bundlesError: document.getElementById("bundles-error"),
bundlesErrorText: document.getElementById("bundles-error-text"),
bundlesWrap: document.getElementById("bundles-wrap"),
bundlesTbody: document.getElementById("bundles-tbody"),

// MODIFIED openBranchDetail() to call:
loadAndRenderBundles(branch.branch);

// NEW FUNCTION:
async function loadAndRenderBundles(branchName) {
  // Hide all bundle sections initially
  elements.bundlesLoading.classList.add("hidden");
  elements.bundlesEmpty.classList.add("hidden");
  elements.bundlesError.classList.add("hidden");
  elements.bundlesWrap.style.display = "none";

  // Show loading
  elements.bundlesLoading.classList.remove("hidden");

  try {
    const bundles = await fetchJson(API.bundles(branchName));
    elements.bundlesLoading.classList.add("hidden");

    if (!bundles || bundles.length === 0) {
      elements.bundlesEmpty.classList.remove("hidden");
      return;
    }

    // Render bundles table
    elements.bundlesTbody.innerHTML = "";
    for (const bundle of bundles) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(bundle.bundle_items)}</td>
        <td>${formatPercent(bundle.discount_pct)}</td>
        <td>${formatCurrency(bundle.bundle_price)}</td>
        <td>${formatCurrency(bundle.expected_profit)}</td>
        <td>${escapeHtml(bundle.reason)}</td>
        <td>${formatNumber(bundle.lift, 2)}</td>
        <td>${formatNumber(bundle.support, 2)}</td>
      `;
      elements.bundlesTbody.appendChild(tr);
    }
    elements.bundlesWrap.style.display = "block";
  } catch (error) {
    console.error("Error loading bundles:", error);
    elements.bundlesLoading.classList.add("hidden");
    elements.bundlesError.classList.remove("hidden");
    elements.bundlesErrorText.textContent = `Error: ${error.message}`;
  }
}
```

---

## How to Use

### 1. Generate Bundles Locally

```bash
# From repo root
python scripts/run_bundles.py
```

This reads from `data/raw/branch_item_sales.csv` (or transactions.csv) and writes to `data/processed/bundles.csv`.

If input files don't exist, you'll see:
```
FileNotFoundError: Missing data/raw/branch_item_sales.csv...
```

### 2. Run Server Locally

```bash
# Option A: Direct
python app.py

# Option B: Gunicorn (like Docker)
gunicorn -b 0.0.0.0:5000 wsgi:app

# Option C: Make
make serve
```

Server runs on `http://127.0.0.1:5001` or `http://localhost:5000`

### 3. Test Endpoints

```bash
# Health check
curl http://127.0.0.1:5001/health
# → {"status":"ok"}

# Get branches
curl http://127.0.0.1:5001/api/branches | python -m json.tool | head -50

# Get bundles for branch 1 (or branch name)
curl http://127.0.0.1:5001/api/bundles/1 | python -m json.tool
# → [] if no bundles exist, or:
# [
#   {
#     "branch_id": "1",
#     "bundle_items": "SKU001, SKU002",
#     "discount_pct": 0.1,
#     "bundle_price": 12500.0,
#     "expected_profit": 2180.0,
#     "reason": "Cross-sell anchor+low-sales",
#     "lift": 1.25,
#     "support": 0.08
#   }
# ]

# Frontend
curl http://127.0.0.1:5001/ | head -30
# → HTML frontend, asset paths are /styles.css and /app.js
```

### 4. Open in Browser

Open: `http://127.0.0.1:5001/` (or your server URL)

Navigate:
1. **Overview** tab → see all branches
2. Click any branch row → goes to **Branch Detail**
3. **Branch Detail** view shows:
   - Monthly revenue chart
   - Monthly table
   - **Bundle Recommendations** section (NEW)

If bundles.csv exists, the table displays. Otherwise, shows message: "No bundle suggestions. Run: `python scripts/run_bundles.py`"

### 5. Makefile Shortcuts

```bash
make help              # Show all commands
make install           # pip install -r requirements.txt
make bundles           # python scripts/run_bundles.py
make serve             # python app.py
make test-local        # curl endpoints to localhost
make test-bundles      # specifically test /api/bundles/1
make clean             # rm __pycache__, *.pyc
```

---

## Verification Checklist

- [x] `GET /api/bundles/<branch_id>` endpoint added to app.py
- [x] Returns `[]` if bundles.csv doesn't exist (no 500 error)
- [x] Frontend fetches API asynchronously
- [x] Loading, empty, error states handled
- [x] Bundle table renders on branch detail view
- [x] API paths are RELATIVE (no hardcoded localhost)
- [x] Makefile provides easy run commands
- [x] README explains bundle recommender
- [x] No existing endpoints broken
- [x] Works in Docker without modifications

---

## Docker / Render Deployment

No changes needed to Dockerfile or deployment. The app:
1. Checks if `bundles.csv` exists at startup
2. Returns `[]` gracefully if missing
3. Doesn't crash or freeze

When deploying to Render:
```bash
git add .
git commit -m "Add bundle recommender integration"
git push
```

Then manually deploy or wait for auto-deploy to rebuild.

---

## Sample Data (if needed)

If you don't have `data/raw/branch_item_sales.csv`, create a minimal one:

```csv
branch_id,item_id,revenue,cost,units_sold
1,SKU001,5000,2500,100
1,SKU002,8000,5600,200
1,SKU003,3000,2100,150
2,SKU001,6000,3000,120
2,SKU002,9000,6300,250
2,SKU004,2000,1400,100
```

Then run: `python scripts/run_bundles.py`
