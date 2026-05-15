import pandas as pd
import duckdb
import json
import time
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(".")
from layers.metadata.logger import log_run

DATASETS = [
    {"name": "covid_cases"},
    {"name": "diabetes"},
    {"name": "heart_disease"},
]

def clean_to_silver(name):
    start = time.time()
    print(f"\nCleaning: {name}")

    df = pd.read_parquet(f"layers/bronze/{name}/data.parquet")
    raw_count = len(df)
    print(f"Bronze rows: {raw_count:,}")

    # Drop bronze metadata columns
    meta_cols = ["_ingested_at", "_source_url", "_dataset_name", "_layer", "_run_version"]
    df = df.drop(columns=[c for c in meta_cols if c in df.columns])

    # Clean
    df = df.drop_duplicates()
    df = df.dropna(how="all")

    # Strip whitespace from strings
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()

    # Fill nulls
    for col in df.select_dtypes(include="number").columns:
        df[col] = df[col].fillna(df[col].median())
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].fillna("unknown")

    # Add silver metadata
    df["_cleaned_at"] = datetime.now().isoformat()
    df["_layer"]      = "silver"

    clean_count = len(df)
    dropped     = raw_count - clean_count
    print(f"Clean rows: {clean_count:,} (dropped {dropped:,})")

    # Write silver
    output_path = Path(f"layers/silver/{name}")
    output_path.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path / "data.parquet", index=False)

    # Write delta log
    log_path = output_path / "_delta_log"
    log_path.mkdir(exist_ok=True)
    metadata = {
        "timestamp":   datetime.now().isoformat(),
        "source":      f"layers/bronze/{name}",
        "raw_rows":    raw_count,
        "clean_rows":  clean_count,
        "dropped":     dropped,
        "columns":     list(df.columns),
        "layer":       "silver"
    }
    with open(log_path / "00000000000000000000.json", "w") as f:
        json.dump(metadata, f, indent=2)

    duration = time.time() - start
    log_run(name, "silver", raw_count, clean_count, duration)
    print(f"Written to {output_path}")
    return clean_count

if __name__ == "__main__":
    total = 0
    for ds in DATASETS:
        count = clean_to_silver(ds["name"])
        total += count

    print(f"\nDONE: {total:,} clean rows across {len(DATASETS)} datasets")

    print("\n=== Verification ===")
    for ds in DATASETS:
        count = duckdb.sql(f"SELECT COUNT(*) FROM read_parquet('layers/silver/{ds['name']}/data.parquet')").fetchone()[0]
        print(f"  {ds['name']}: {count:,} rows in silver")