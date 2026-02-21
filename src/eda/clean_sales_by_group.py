#!/usr/bin/env python3

import pandas as pd
import argparse
import re


def clean_sales(input_path, items_out, totals_out):

    # ----------------------------
    # READ RAW FILE
    # ----------------------------
    df = pd.read_csv(input_path, header=None, dtype=str)

    # Drop first 3 rows
    df = df.iloc[3:].reset_index(drop=True)

    # Promote 4th row as header
    df.columns = df.iloc[0]
    df = df.iloc[1:].reset_index(drop=True)

    # Ensure Description exists
    if "Description" not in df.columns:
        raise ValueError("Expected 'Description' column not found.")

    # ----------------------------
    # REMOVE REPORT ARTIFACTS
    # ----------------------------

    # Remove repeated header rows
    df = df[df["Description"].str.strip() != "Description"]

    # Remove page/date rows
    df = df[~df["Description"].str.contains("Page", na=False)]
    df = df[~df["Description"].str.contains(
        r"\d{2}-[A-Za-z]{3}-\d{2}",
        regex=True,
        na=False
    )]

    # Remove footer rows (generalized)
    df = df[~df["Description"].str.contains(
        r"REP_|Copyright|omegapos\.com",
        regex=True,
        na=False
    )]

    # ----------------------------
    # DROP UNWANTED COLUMNS
    # ----------------------------

    # Drop Barcode column if present
    if "Barcode" in df.columns:
        df = df.drop(columns=["Barcode"])

    # Drop 5th column safely if exists
    if len(df.columns) >= 5:
        df = df.drop(df.columns[4], axis=1)

    # Keep only needed columns explicitly
    df = df[["Description", "Qty", "Total Amount"]]

    df = df.rename(columns={"Description": "Raw"})

    # ----------------------------
    # HIERARCHY PROCESSING
    # ----------------------------

    current_branch = None
    current_division = None
    current_group = None

    items_rows = []
    totals_rows = []

    for _, row in df.iterrows():
        raw_value = str(row["Raw"]).strip()

        if raw_value.startswith("Branch:"):
            current_branch = raw_value.replace("Branch:", "").strip()
            continue

        if raw_value.startswith("Division:"):
            current_division = raw_value.replace("Division:", "").strip()
            continue

        if raw_value.startswith("Group:"):
            current_group = raw_value.replace("Group:", "").strip()
            continue

        if raw_value.startswith("Total by"):
            level = None
            if "Group" in raw_value:
                level = "Group"
            elif "Division" in raw_value:
                level = "Division"
            elif "Branch" in raw_value:
                level = "Branch"

            name = raw_value.split(":")[-1].strip() if ":" in raw_value else None

            totals_rows.append({
                "Level": level,
                "Name": name,
                "Branch": current_branch,
                "Division": current_division,
                "Group": current_group,
                "Qty": row.get("Qty"),
                "Total Amount": row.get("Total Amount")
            })
            continue

        # Item rows
        items_rows.append({
            "Branch": current_branch,
            "Division": current_division,
            "Group": current_group,
            "Item": raw_value,
            "Qty": row.get("Qty"),
            "Total Amount": row.get("Total Amount")
        })

    items_df = pd.DataFrame(items_rows)
    totals_df = pd.DataFrame(totals_rows)

    # ----------------------------
    # SAFE NUMERIC CONVERSION
    # ----------------------------

    for df_ in [items_df, totals_df]:
        df_["Qty"] = pd.to_numeric(
            df_["Qty"].str.replace(",", "", regex=False),
            errors="coerce"
        )

        df_["Total Amount"] = pd.to_numeric(
            df_["Total Amount"].str.replace(",", "", regex=False),
            errors="coerce"
        )

        df_.dropna(subset=["Qty", "Total Amount"], inplace=True)

    # ----------------------------
    # SAVE OUTPUT
    # ----------------------------

    items_df.to_csv(items_out, index=False)
    totals_df.to_csv(totals_out, index=False)


def main():
    parser = argparse.ArgumentParser(
        description="Clean hierarchical sales CSV into normalized items and totals."
    )

    parser.add_argument("input_csv", help="Path to raw CSV file")
    parser.add_argument("items_output_csv", help="Path to cleaned items CSV")
    parser.add_argument("totals_output_csv", help="Path to totals CSV")

    args = parser.parse_args()

    clean_sales(
        args.input_csv,
        args.items_output_csv,
        args.totals_output_csv
    )


if __name__ == "__main__":
    main()