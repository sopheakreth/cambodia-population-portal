"""Upload checks: columns, types, units. Rejected rows are returned with a reason.

Add a new schema to SCHEMAS to accept a new kind of upload.
"""
from __future__ import annotations

import csv
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src import config
from src.pipeline import match_province

SCHEMAS: dict[str, dict] = {
    # A long-format province indicator file, e.g. new survey figures
    "province_indicator": {
        "description": "One value per province, year and measure",
        "columns": {"province": "str", "year": "int", "measure": "str", "value": "float", "unit": "str"},
        "units": {"persons", "households", "km2", "persons_per_km2", "percent", "persons_per_household"},
        "year_range": (1950, 2100),
        "non_negative": ["value"],
    },
    # Commune list, e.g. the MEF Commune List 2025 reshaped
    "commune_list": {
        "description": "One row per commune",
        "columns": {"commune_code": "str", "commune_name": "str", "province": "str", "type": "str"},
        "allowed": {"type": {"khum", "sangkat"}},
    },
}


def _norm_col(c: str) -> str:
    return re.sub(r"\W+", "_", str(c).strip().lower()).strip("_")


def read_upload(file, filename: str) -> pd.DataFrame:
    """Read a CSV or Excel upload (file-like or path)."""
    name = filename.lower()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(file)
    if name.endswith(".csv"):
        return pd.read_csv(file)
    raise ValueError("Only .csv, .xlsx or .xls files are accepted.")


def validate(df: pd.DataFrame, schema_name: str) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Check an uploaded table against a schema.

    Returns (accepted_rows, rejected_rows_with_reason, file_level_errors).
    If a required column is missing, every row is rejected.
    """
    schema = SCHEMAS[schema_name]
    df = df.rename(columns=_norm_col).copy()
    df.insert(0, "row", range(2, len(df) + 2))  # spreadsheet row number (header = row 1)
    errors: list[str] = []

    missing = [c for c in schema["columns"] if c not in df.columns]
    if missing:
        errors.append(f"Missing column(s): {', '.join(missing)}")
        rej = df.assign(reason=f"File is missing column(s): {', '.join(missing)}")
        return df.iloc[0:0], rej, errors

    reasons = pd.Series([""] * len(df), index=df.index, dtype=object)

    def add(mask, msg):
        nonlocal reasons
        reasons = reasons.where(~mask | (reasons != ""), msg)

    for col, typ in schema["columns"].items():
        s = df[col]
        add(s.isna() | (s.astype(str).str.strip() == ""), f"Empty value in '{col}'")
        if typ in ("int", "float"):
            num = pd.to_numeric(s, errors="coerce")
            add(s.notna() & num.isna(), f"'{col}' is not a number")
            df[col] = num
            if typ == "int":
                add(num.notna() & (num % 1 != 0), f"'{col}' must be a whole number")

    if "province" in df.columns:
        codes = df["province"].astype(str).map(match_province)
        add(df["province"].notna() & codes.isna(), "Unknown province name")
        df["pro_code"] = codes

    for col in schema.get("non_negative", []):
        add(df[col] < 0, f"Negative '{col}' not allowed")

    if "units" in schema and "unit" in df.columns:
        add(~df["unit"].astype(str).str.strip().str.lower().isin(schema["units"]),
            f"Unit not allowed (use one of: {', '.join(sorted(schema['units']))})")

    if "year_range" in schema and "year" in df.columns:
        lo, hi = schema["year_range"]
        add((df["year"] < lo) | (df["year"] > hi), f"Year outside {lo}–{hi}")

    for col, allowed in schema.get("allowed", {}).items():
        add(~df[col].astype(str).str.strip().str.lower().isin(allowed),
            f"'{col}' must be one of: {', '.join(sorted(allowed))}")

    rejected = df[reasons != ""].assign(reason=reasons[reasons != ""])
    accepted = df[reasons == ""]
    return accepted, rejected, errors


def store_upload(accepted: pd.DataFrame, filename: str, schema_name: str,
                 n_rejected: int) -> Path:
    """Save accepted rows as data/uploads/<date>_<name>.csv and log the upload."""
    stamp = datetime.now(timezone.utc)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", Path(filename).stem)
    dest = config.UPLOAD_DIR / f"{stamp:%Y-%m-%d_%H%M%S}_{safe}.csv"
    out = accepted.drop(columns=["row"], errors="ignore").assign(
        source_file=filename, uploaded_at=stamp.isoformat(timespec="seconds"))
    out.to_csv(dest, index=False)

    new = not config.UPLOAD_LOG.exists()
    with open(config.UPLOAD_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "file", "schema", "accepted", "rejected", "stored_as"])
        w.writerow([stamp.isoformat(timespec="seconds"), filename, schema_name,
                    len(accepted), n_rejected, dest.name])
    return dest
