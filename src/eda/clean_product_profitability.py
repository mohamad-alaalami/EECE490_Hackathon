#!/usr/bin/env python3

import pandas as pd
import argparse
import re


DATE_RE = r"\d{2}-[A-Za-z]{3}-\d{2}"


def to_numeric_safe(series):
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce"
    )


def clean_omega(input_path, output_path):

    df = pd.read_csv(input_path, header=None, dtype=str)

    # --------------------------------
    # Basic Report Cleanup
    # --------------------------------

    df = df.iloc[3:].reset_index(drop=True)
    df.columns = df.iloc[0]
    df = df.iloc[1:].reset_index(drop=True)

    first_col = df.columns[0]

    # Remove repeated header rows
    df = df[df[first_col].astype(str).str.strip() != first_col]

    # Remove page/date rows
    df = df[~df[first_col].str.contains("Page", na=False)]
    df = df[~df[first_col].str.contains(DATE_RE, regex=True, na=False)]

    # Remove footer rows
    df = df[~df[first_col].str.contains(
        r"REP_|Copyright|omegapos\.com",
        regex=True,
        na=False
    )]

    # Drop completely empty columns
    df = df.dropna(axis=1, how="all")

    # --------------------------------
    # Convert numeric columns
    # --------------------------------

    numeric_cols = []

    for col in df.columns[1:]:
        converted = to_numeric_safe(df[col])
        if converted.notna().sum() > 0:
            df[col] = converted
            numeric_cols.append(col)

    # --------------------------------
    # Hierarchy Detection
    # --------------------------------

    L1 = L2 = L3 = L4 = None
    cleaned_rows = []

    for _, row in df.iterrows():
        desc = str(row[first_col]).strip()

        # Check if this is a label row (no numeric values)
        is_label = all(pd.isna(row[col]) for col in numeric_cols)

        if is_label:
            if L1 is None:
                L1 = desc
            elif L2 is None:
                L2 = desc
            elif L3 is None:
                L3 = desc
            else:
                L4 = desc
            continue

        # Data row
        new_row = {
            "L1": L1,
            "L2": L2,
            "L3": L3,
            "L4": L4,
            "Item": desc
        }

        for col in numeric_cols:
            new_row[col] = row[col]

        cleaned_rows.append(new_row)

    cleaned_df = pd.DataFrame(cleaned_rows)

    cleaned_df.to_csv(output_path, index=False)


def main():
    parser = argparse.ArgumentParser(
        description="General Omega POS report cleaner."
    )

    parser.add_argument("input_csv")
    parser.add_argument("output_csv")

    args = parser.parse_args()

    clean_omega(args.input_csv, args.output_csv)


if __name__ == "__main__":
    main()