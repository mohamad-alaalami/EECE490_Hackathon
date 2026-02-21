#!/usr/bin/env python3
import re
import argparse
import pandas as pd

DATE_RE = re.compile(r"^\d{2}-[A-Za-z]{3}-\d{2}$")  # dd-MMM-yy

def main():
    ap = argparse.ArgumentParser(description="Clean and reshape report-export CSV.")
    ap.add_argument("input_csv", help="Path to raw CSV export")
    ap.add_argument("output_csv", help="Path to write cleaned CSV")
    ap.add_argument("--encoding", default="utf-8", help="CSV encoding")
    ap.add_argument("--sep", default=",", help="CSV separator")
    args = ap.parse_args()

    # -------- PHASE 1: RAW CLEANING --------

    df = pd.read_csv(
        args.input_csv,
        header=None,
        dtype=str,
        encoding=args.encoding,
        sep=args.sep
    )

    # Drop 4th, 8th, 10th columns (Excel positions)
    drop_cols = [c for c in [3, 7, 9] if c in df.columns]
    df = df.drop(columns=drop_cols)

    # Remove first 3 rows
    df = df.iloc[3:].reset_index(drop=True)

    # Promote next row as header
    header = df.iloc[0].fillna("").astype(str).tolist()
    df = df.iloc[1:].reset_index(drop=True)
    df.columns = header

    first_col = df.columns[0]

    # Remove date rows
    df = df[~df[first_col].fillna("").astype(str).str.strip().str.match(DATE_RE)]

    # Remove rows where first column == "Category"
    df = df[~df[first_col].fillna("").astype(str).str.strip().str.lower().eq("category")]

    # Remove rows starting with REP
    df = df[~df[first_col].fillna("").astype(str).str.strip().str.startswith("REP", na=False)]

    # Drop completely empty rows
    df = df.dropna(how="all").reset_index(drop=True)

    # -------- PHASE 2: RESHAPE TO TIDY --------

    # Identify branch header rows (contain "Stories")
    branch_mask = df[first_col].str.contains("Stories", case=False, na=False)

    # Create Branch column
    df["Branch"] = None
    df.loc[branch_mask, "Branch"] = df.loc[branch_mask, first_col]

    # Forward fill branch
    df["Branch"] = df["Branch"].ffill()

    # Clean branch name (remove "Stories - ")
    df["Branch"] = df["Branch"].str.replace(
        r"^Stories\s*[-–]?\s*",
        "",
        regex=True
    )

    # Remove branch header rows
    df = df[~branch_mask]

    # Remove "Total By Branch"
    df = df[~df[first_col].str.contains("Total", case=False, na=False)]

    # Rename first column to Category
    df = df.rename(columns={first_col: "Category"})

    #standardize category and branch names by
    df["Category"] = df["Category"].astype(str).str.strip().str.lower()
    df["Branch"] = df["Branch"].astype(str).str.strip().str.lower()
    # Reorder columns
    ordered_cols = ["Branch", "Category"] + \
                   [c for c in df.columns if c not in ["Branch", "Category"]]
    df = df[ordered_cols]

    df = df.reset_index(drop=True)

    df.to_csv(args.output_csv, index=False, encoding=args.encoding)


if __name__ == "__main__":
    main()