import pandas as pd
import duckdb
import json
from datetime import datetime
from pathlib import Path

DATASETS = [
    {
        "name": "covid_cases",
        "url": "https://raw.githubusercontent.com/datasets/covid-19/main/data/countries-aggregated.csv",
        "description": "COVID-19 country-level aggregated cases"
    },
    {
        "name": "diabetes",
        "url": "https://raw.githubusercontent.com/plotly/datasets/master/diabetes.csv",
        "description": "Pima Indians Diabetes dataset"
    },
    {
    "name": "heart_disease",
    "url": "https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/processed.cleveland.data",
    "description": "UCI Heart Disease Cleveland dataset"
},
]

def ingest_to_bronze(name, url, description):
    print(f"\nIngesting: {description}")
    print(f"URL: {url}")

    # Read from URL with pandas
    if name == "heart_disease":
        cols = ["age","sex","cp","trestbps","chol","fbs","restecg",
            "thalach","exang","oldpeak","slope","ca","thal","target"]
        df = pd.read_csv(url, names=cols, na_values="?", on_bad_lines="skip")
    else:
        df = pd.read_csv(url, on_bad_lines="skip")
    print(f"Loaded {len(df):,} rows, {len(df.columns)} columns")
    print(f"Columns: {list(df.columns)}")

    # Add bronze metadata columns
    df["_ingested_at"] = datetime.now().isoformat()
    df["_source_url"]  = url
    df["_dataset_name"] = name
    df["_layer"] = "bronze"

    # Create output folder
    output_path = Path(f"layers/bronze/{name}")
    output_path.mkdir(parents=True, exist_ok=True)

    # Write as parquet (Delta-compatible format)
    parquet_file = output_path / "data.parquet"
    df.to_parquet(parquet_file, index=False)

    # Write a simple delta_log to mimic Delta table structure
    log_path = output_path / "_delta_log"
    log_path.mkdir(exist_ok=True)
    metadata = {
        "timestamp": datetime.now().isoformat(),
        "source_url": url,
        "row_count": len(df),
        "columns": list(df.columns),
        "layer": "bronze"
    }
    with open(log_path / "00000000000000000000.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Written to {output_path}")
    return len(df)

if __name__ == "__main__":
    total = 0
    for ds in DATASETS:
        count = ingest_to_bronze(ds["name"], ds["url"], ds["description"])
        total += count

    print(f"\nDONE: {total:,} total rows ingested across {len(DATASETS)} datasets")

    # Verify with DuckDB
    print("\n=== Verification ===")
    for ds in DATASETS:
        count = duckdb.sql(f"SELECT COUNT(*) FROM read_parquet('layers/bronze/{ds['name']}/data.parquet')").fetchone()[0]
        print(f"  {ds['name']}: {count:,} rows in bronze")