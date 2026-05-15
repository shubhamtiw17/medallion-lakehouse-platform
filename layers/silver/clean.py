import pandas as pd
import duckdb
import json
from datetime import datetime
from pathlib import Path

DATASETS = [
    {"name": "covid_cases",   "sort_col": "Confirmed"},
    {"name": "diabetes",      "sort_col": "Glucose"},
    {"name": "heart_disease", "sort_col": "age"},
]

def clean_to_silver(name, sort_col):
    print(f"\nCleaning: {name}")

    # Read from bronze
    df = pd.read_parquet(f"layers/bronze/{name}/data.parquet")
    raw_count = len(df)
    print(f"Bronze rows: {raw_count:,}")

    # Drop bronze metadata columns before cleaning
    meta_cols = ["_ingested_at", "_source_url", "_dataset_name", "_layer"]
    df = df.drop(columns=[c for c in meta_cols if c in df.columns])

    # Clean: drop duplicates
    df = df.drop_duplicates()

    # Clean: drop rows where ALL values are null
    df = df.dropna(how="all")

    # Clean: strip whitespace from string columns
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()

    # Clean: fill remaining nulls with sensible defaults
    for col in df.select_dtypes(include="number").columns:
        df[col] = df[col].fillna(df[col].median())
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].fillna("unknown")

    # Add silver metadata
    df["_cleaned_at"] = datetime.now().isoformat()
    df["_layer"] = "silver"

    clean_count = len(df)
    dropped = raw_count - clean_count
    print(f"Clean rows: {clean_count:,} (dropped {dropped:,} rows)")

    # Write to silver
    output_path = Path(f"layers/silver/{name}")
    output_path.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path / "data.parquet", index=False)

    # Write metadata log
    log_path = output_path / "_delta_log"
    log_path.mkdir(exist_ok=True)
    metadata = {
        "timestamp": datetime.now().isoformat(),
        "source": f"layers/bronze/{name}",
        "raw_rows": raw_count,
        "clean_rows": clean_count,
        "dropped_rows": dropped,
        "columns": list(df.columns),
        "layer": "silver"
    }
    with open(log_path / "00000000000000000000.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Written to {output_path}")
    return clean_count

if __name__ == "__main__":
    total = 0
    for ds in DATASETS:
        count = clean_to_silver(ds["name"], ds["sort_col"])
        total += count

    print(f"\nDONE: {total:,} total clean rows across {len(DATASETS)} datasets")

    # Verify
    print("\n=== Verification ===")
    for ds in DATASETS:
        count = duckdb.sql(f"SELECT COUNT(*) FROM read_parquet('layers/silver/{ds['name']}/data.parquet')").fetchone()[0]
        print(f"  {ds['name']}: {count:,} rows in silver")