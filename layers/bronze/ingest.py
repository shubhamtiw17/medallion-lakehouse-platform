import pandas as pd
import json
import time
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(".")
from layers.storage import write_parquet, write_json, read_json
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
    {
    "name": "us_hospitals",
    "url": "https://raw.githubusercontent.com/covidcaremap/covid19-healthsystemcapacity/master/data/published/us_healthcare_capacity-facility-CovidCareMap.csv",
    "description": "US hospital capacity data with missing values and mixed types",
    "header": True
},
{
    "name": "ds_jobs",
    "url": "https://raw.githubusercontent.com/andreluizls1/datacleaning_glassdoor/main/Uncleaned_DS_jobs.csv",
    "description": "Uncleaned data science jobs with messy salary ranges and locations",
    "header": True
},
]

HEART_COLS = ["age","sex","cp","trestbps","chol","fbs","restecg",
              "thalach","exang","oldpeak","slope","ca","thal","target"]

def ingest_to_bronze(name, url, description, header):
    start = time.time()
    print(f"\nIngesting: {description}")
    print(f"URL: {url}")

    # Check last run for incremental loading
    last_info  = read_json("metadata", f"bronze_{name}_last_run.json")
    last_count = last_info.get("row_count", 0)
    if last_count > 0:
        print(f"Previous run: {last_count:,} rows")

    # Read from URL
    try:
        if not header:
            df = pd.read_csv(url, names=HEART_COLS, na_values="?", on_bad_lines="skip")
        else:
            df = pd.read_csv(url, on_bad_lines="skip")
    except Exception as e:
        print(f"Failed to read {url}: {e}")
        return 0

    current_count = len(df)
    print(f"Loaded {current_count:,} rows, {len(df.columns)} columns")
    print(f"Columns: {list(df.columns)}")

    # Incremental check
    if current_count <= last_count and last_count > 0:
        print(f"No new rows — skipping")
        return 0

    # Add bronze metadata
    df["_ingested_at"]  = datetime.now().isoformat()
    df["_source_url"]   = url
    df["_dataset_name"] = name
    df["_layer"]        = "bronze"
    df["_run_version"]  = last_count

    # Write to MinIO
    write_parquet(df, "bronze", f"{name}/data.parquet")

    # Write delta log to MinIO
    metadata = {
        "timestamp":  datetime.now().isoformat(),
        "source_url": url,
        "row_count":  current_count,
        "columns":    list(df.columns),
        "layer":      "bronze"
    }
    write_json(metadata, "metadata", f"bronze_{name}_last_run.json")

    # Also keep local copy for Airflow access
    local_path = Path(f"layers/bronze/{name}")
    local_path.mkdir(parents=True, exist_ok=True)
    df.to_parquet(local_path / "data.parquet", index=False)

    duration = time.time() - start
    log_run(name, "bronze", 0, current_count, duration)
    return current_count

if __name__ == "__main__":
    total = 0
    for ds in DATASETS:
        count = ingest_to_bronze(
            ds["name"], ds["url"], ds["description"], ds["header"]
        )
        total += count

    print(f"\nDONE: {total:,} total rows across {len(DATASETS)} datasets")

    print("\n=== Verification ===")
    from layers.storage import read_parquet
    for ds in DATASETS:
        try:
            df = read_parquet("bronze", f"{ds['name']}/data.parquet")
            print(f"  {ds['name']}: {len(df):,} rows in MinIO bronze bucket")
        except Exception as e:
            print(f"  {ds['name']}: ERROR - {e}")