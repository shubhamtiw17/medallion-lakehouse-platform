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
    {
        "name": "covid_cases",
        "url": "https://raw.githubusercontent.com/datasets/covid-19/main/data/countries-aggregated.csv",
        "description": "COVID-19 country-level aggregated cases",
        "header": True
    },
    {
        "name": "diabetes",
        "url": "https://raw.githubusercontent.com/plotly/datasets/master/diabetes.csv",
        "description": "Pima Indians Diabetes dataset",
        "header": True
    },
    {
        "name": "heart_disease",
        "url": "https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/processed.cleveland.data",
        "description": "UCI Heart Disease Cleveland dataset",
        "header": False
    },
]

HEART_COLS = ["age","sex","cp","trestbps","chol","fbs","restecg",
              "thalach","exang","oldpeak","slope","ca","thal","target"]

def ingest_to_bronze(name, url, description, header):
    start = time.time()
    print(f"\nIngesting: {description}")
    print(f"URL: {url}")

    last_run_file = Path(f"layers/bronze/{name}/_delta_log/last_run.json")

    # Incremental check
    last_count = 0
    if last_run_file.exists():
        last_info = json.load(open(last_run_file))
        last_count = last_info.get("row_count", 0)
        print(f"Previous run: {last_count:,} rows")

    # Read data
    if not header:
        df = pd.read_csv(url, names=HEART_COLS, na_values="?", on_bad_lines="skip")
    else:
        df = pd.read_csv(url, on_bad_lines="skip")

    current_count = len(df)
    print(f"Loaded {current_count:,} rows, {len(df.columns)} columns")
    print(f"Columns: {list(df.columns)}")

    # Skip if no new data
    if current_count <= last_count and last_count > 0:
        print(f"No new rows since last run — skipping")
        return 0

    new_rows = current_count - last_count
    print(f"New rows: {new_rows:,}")

    # Add metadata columns
    df["_ingested_at"]  = datetime.now().isoformat()
    df["_source_url"]   = url
    df["_dataset_name"] = name
    df["_layer"]        = "bronze"
    df["_run_version"]  = last_count

    # Write parquet
    output_path = Path(f"layers/bronze/{name}")
    output_path.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path / "data.parquet", index=False)

    # Write delta log
    log_path = output_path / "_delta_log"
    log_path.mkdir(exist_ok=True)

    metadata = {
        "timestamp":  datetime.now().isoformat(),
        "source_url": url,
        "row_count":  current_count,
        "columns":    list(df.columns),
        "layer":      "bronze"
    }
    with open(log_path / "00000000000000000000.json", "w") as f:
        json.dump(metadata, f, indent=2)

    # Save last run info for incremental loading
    with open(last_run_file, "w") as f:
        json.dump({"timestamp": datetime.now().isoformat(), "row_count": current_count, "source_url": url}, f, indent=2)

    duration = time.time() - start
    log_run(name, "bronze", 0, current_count, duration)
    print(f"Written to {output_path}")
    return current_count

if __name__ == "__main__":
    total = 0
    for ds in DATASETS:
        count = ingest_to_bronze(ds["name"], ds["url"], ds["description"], ds["header"])
        total += count

    print(f"\nDONE: {total:,} total rows ingested across {len(DATASETS)} datasets")

    print("\n=== Verification ===")
    for ds in DATASETS:
        count = duckdb.sql(f"SELECT COUNT(*) FROM read_parquet('layers/bronze/{ds['name']}/data.parquet')").fetchone()[0]
        print(f"  {ds['name']}: {count:,} rows in bronze")