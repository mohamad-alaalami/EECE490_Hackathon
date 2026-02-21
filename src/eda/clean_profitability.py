#!/usr/bin/env python3
import pandas as pd
import argparse
import re

DATE_RE = re.compile(r"^\d{2}-[A-Za-z]{3}-\d{2}$")
DEPARTMENTS_CANON = {"TOTERS", "TAKE AWAY"}

def norm_label(s: str) -> str:
    s = str(s).strip().upper()
    s = s.replace("-", " ")
    s = re.sub(r"\s+", " ", s)
    return s

def is_branch(label: str) -> bool:
    return str(label).strip().lower().startswith("stories")

def to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(
        s.astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce"
    )

def clean_profitability(input_path: str, output_path: str):
    df = pd.read_csv(input_path, header=None, dtype=str)

    # Drop first 3 rows; promote 4th as header
    df = df.iloc[3:].reset_index(drop=True)
    df.columns = df.iloc[0]
    df = df.iloc[1:].reset_index(drop=True)

    first_col = df.columns[0]

    # Remove repeated header rows mid-file
    df = df[df[first_col].astype(str).str.strip() != first_col]

    # Remove report noise rows (do NOT cache a Series before filtering)
    df = df[~df[first_col].astype(str).str.contains("Page", na=False)]
    df = df[~df[first_col].astype(str).str.contains(r"\bREP_", regex=True, na=False)]
    df = df[~df[first_col].astype(str).str.contains(r"Copyright", regex=True, na=False)]
    df = df[~df[first_col].astype(str).str.contains(r"omegapos\.com", regex=True, na=False)]
    df = df[~df[first_col].astype(str).str.match(DATE_RE, na=False)]

    # Drop 4th, 8th, 10th columns (1-based) => indices 3,7,9 (0-based)
    drop_idx = [3, 7, 9]
    drop_cols = [df.columns[i] for i in drop_idx if i < len(df.columns)]
    if drop_cols:
        df = df.drop(columns=drop_cols)

    # Drop completely empty columns
    df = df.dropna(axis=1, how="all")

    # Convert numeric columns
    numeric_cols = []
    for c in df.columns[1:]:
        converted = to_num(df[c])
        if converted.notna().sum() > 0:
            df[c] = converted
            numeric_cols.append(c)

    # ----------------------------
    # Hierarchy (NO CATEGORY)
    # Branch -> Department -> Division -> Items
    # Any non-branch/non-department label row becomes the current Division.
    # ----------------------------
    branch = None
    dept = None
    division = None
    out_rows = []

    for _, r in df.iterrows():
        label = str(r[first_col]).strip()
        label_norm = norm_label(label)

        is_label_row = all(pd.isna(r[c]) for c in numeric_cols)

        if is_label_row:
            if is_branch(label):
                branch = label
                dept = None
                division = None
                continue

            if label_norm in DEPARTMENTS_CANON:
                dept = label_norm.title() if label_norm != "TOTERS" else "Toters"
                division = None
                continue

            # everything else is a "division" label
            division = label
            continue

        # Item row
        row_out = {
            "Branch": branch,
            "Department": dept,
            "Division": division,
            "Item": label,
        }
        for c in numeric_cols:
            row_out[c] = r[c]
        out_rows.append(row_out)

    cleaned = pd.DataFrame(out_rows)
    cleaned.to_csv(output_path, index=False)

def main():
    ap = argparse.ArgumentParser(description="Clean Omega 'Theoretical Profit By Item' CSV export (no category).")
    ap.add_argument("input_csv", help="Raw Omega CSV")
    ap.add_argument("output_csv", help="Clean output CSV")
    args = ap.parse_args()
    clean_profitability(args.input_csv, args.output_csv)

if __name__ == "__main__":
    main()