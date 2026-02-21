# t
#!/usr/bin/env python3
import re
import argparse
import pandas as pd

MONTHS = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
]
MONTHS_LOWER = [m.lower() for m in MONTHS]
MONTH_ABBR = {m: m[:3] for m in MONTHS}

YEAR_RE = re.compile(r"^(19|20)\d{2}$")
BRANCH_RE = re.compile(r"\bstories\b", re.IGNORECASE)

def to_number(x: str) -> float:
    if x is None:
        return 0.0
    s = str(x).strip()
    if s == "" or s.lower() == "nan":
        return 0.0
    # remove commas and weird spaces
    s = s.replace(",", "").replace("\u00a0", " ")
    # keep only plausible numeric characters
    s = re.sub(r"[^0-9.\-]", "", s)
    if s in ("", "-", ".", "-."):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0

def find_year_in_row(row) -> str | None:
    for v in row:
        if pd.isna(v):
            continue
        s = str(v).strip()
        if YEAR_RE.match(s):
            return s
    return None

def detect_month_map(row) -> dict[str, int]:
    """
    Return mapping {month_name: column_index} if row contains month headers.
    Works even if months shift left/right between blocks/pages.
    """
    month_map = {}
    for idx, v in enumerate(row):
        if pd.isna(v):
            continue
        s = str(v).strip().lower()
        if s in MONTHS_LOWER:
            month_map[MONTHS[MONTHS_LOWER.index(s)]] = idx
    # treat as a header row only if it has at least 3 months (avoid false positives)
    return month_map if len(month_map) >= 3 else {}

def find_branch_in_row(row) -> str | None:
    # pick the first cell that contains "Stories" (your branches look like that)
    for v in row:
        if pd.isna(v):
            continue
        s = str(v).strip()
        if BRANCH_RE.search(s):
            return s
    return None

def main():
    ap = argparse.ArgumentParser(description="Clean messy Comparative Monthly Sales CSV into Branch x Month table.")
    ap.add_argument("--input", default="/mnt/data/Monthly_Sales.csv", help="Path to raw CSV export")
    ap.add_argument("--output", default="/mnt/data/cleaned_output.csv", help="Path to write cleaned CSV")
    args = ap.parse_args()

    raw = pd.read_csv(args.input, header=None, dtype=str)

    current_year = None
    current_month_map = {}
    records = []  # (branch, year, month, value)

    for _, row in raw.iterrows():
        row_list = row.tolist()

        # update current year if present anywhere in the row
        y = find_year_in_row(row_list)
        if y:
            current_year = y

        # detect month header rows (this resets the column mapping)
        mm = detect_month_map(row_list)
        if mm:
            current_month_map = mm
            continue  # header row itself has no data

        if not current_year or not current_month_map:
            continue  # we don't know how to interpret this row yet

        branch = find_branch_in_row(row_list)
        if not branch:
            continue  # skip report junk, totals, blanks

        # harvest month values based on the latest detected header mapping
        for month_name, col_idx in current_month_map.items():
            val = to_number(row_list[col_idx] if col_idx < len(row_list) else None)
            # store everything; we'll filter to the months we want later
            records.append((branch, int(current_year), month_name, val))

    if not records:
        raise SystemExit("No records extracted. The file structure might differ from expected 'Stories ...' branches.")

    df = pd.DataFrame(records, columns=["Branch", "Year", "Month", "Value"])

    # Keep only what you asked for: Jan–Dec 2025 and Jan 2026
    want = []
    for m in MONTHS:
        want.append((2025, m))
    want.append((2026, "January"))
    want_set = set(want)

    df = df[df.apply(lambda r: (r["Year"], r["Month"]) in want_set, axis=1)]

    # Aggregate in case the same branch-month appears multiple times across blocks/pages
    df = df.groupby(["Branch", "Year", "Month"], as_index=False)["Value"].sum()

    # Create column labels like "Jan 2025"
    df["Col"] = df["Month"].map(MONTH_ABBR) + " " + df["Year"].astype(str)

    # Pivot to wide format
    wide = df.pivot_table(index="Branch", columns="Col", values="Value", aggfunc="sum", fill_value=0.0)

    # Force column order exactly as requested
    ordered_cols = [f"{MONTH_ABBR[m]} 2025" for m in MONTHS] + ["Jan 2026"]
    for c in ordered_cols:
        if c not in wide.columns:
            wide[c] = 0.0
    wide = wide[ordered_cols]

    # Totals
    wide["Total 2025"] = wide[[f"{MONTH_ABBR[m]} 2025" for m in MONTHS]].sum(axis=1)
    wide["Total"] = wide["Total 2025"] + wide["Jan 2026"]

    # Add last row with monthly totals
    total_row = pd.DataFrame(wide.sum(axis=0)).T
    total_row.index = ["TOTAL"]
    wide = pd.concat([wide, total_row], axis=0)

    # Round everything to 2 decimal places
    wide = wide.round(2)

    # Final output
    out = wide.reset_index().rename(columns={"index": "Branch"})
    out["Branch"] = (
    out["Branch"]
    .str.replace(r"(?i)^stories\s*-?\s*", "", regex=True)
    .str.strip()
    .str.lower()
    )
    out.to_csv(args.output, index=False)

    print(f"Saved cleaned table -> {args.output}")

if __name__ == "__main__":
    main()