import re
from typing import Iterable, Optional

import pandas as pd


BRANCH_ALIAS_MAP = {
    "alay": "aley",
    "aley": "aley",
    ".": "unknown",
}


def normalize_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_branch_key(branch_name: str) -> str:
    text = normalize_text(branch_name)
    text = re.sub(r"^stories\s*[-–]?\s*", "", text).strip()
    text = BRANCH_ALIAS_MAP.get(text, text)
    return text.strip()


def canonical_branch_name(branch_name: str) -> str:
    key = normalize_branch_key(branch_name)
    key = re.sub(r"\s+", " ", key)
    return f"Stories {key.title()}".strip()


def is_valid_branch_key(branch_key: str) -> bool:
    key = normalize_branch_key(branch_key)
    if not key:
        return False
    if key in {"total", "totals", "all branches", "grand total"}:
        return False
    return True


def normalize_colname(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name).lower())


def find_col(df: pd.DataFrame, aliases: Iterable[str]) -> Optional[str]:
    alias_set = {normalize_colname(a) for a in aliases}
    for col in df.columns:
        if normalize_colname(col) in alias_set:
            return col
    return None


def parse_number(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text == "":
        return 0.0
    text = text.replace(",", "").replace("%", "")
    text = re.sub(r"[^0-9.\-]", "", text)
    if text in {"", "-", ".", "-."}:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def to_numeric(series: pd.Series) -> pd.Series:
    return series.apply(parse_number).astype(float)


def safe_div(a: float, b: float, default: float = 0.0) -> float:
    if b is None or b == 0:
        return default
    return float(a) / float(b)
