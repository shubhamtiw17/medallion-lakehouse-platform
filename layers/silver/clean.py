import pandas as pd
import json
import time
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(".")
from layers.storage import write_parquet, read_parquet, write_json
from layers.metadata.logger import log_run

DATASETS = ["covid_cases", "diabetes", "heart_disease", "us_hospitals", "ds_jobs"]

def clean_covid(df):
    df["Date"]      = pd.to_datetime(df["Date"], errors="coerce")
    df["Confirmed"] = pd.to_numeric(df["Confirmed"], errors="coerce").fillna(0)
    df["Recovered"] = pd.to_numeric(df["Recovered"], errors="coerce").fillna(0)
    df["Deaths"]    = pd.to_numeric(df["Deaths"],    errors="coerce").fillna(0)
    df["Country"]   = df["Country"].str.strip().str.title()
    return df

def clean_diabetes(df):
    medical_cols = ["Glucose","BloodPressure","SkinThickness","Insulin","BMI"]
    for col in medical_cols:
        df[col] = df[col].replace(0, pd.NA)
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df[col] = df[col].fillna(df[col].median())
    return df

def clean_heart(df):
    df["age"]     = pd.to_numeric(df["age"],     errors="coerce")
    df["chol"]    = pd.to_numeric(df["chol"],    errors="coerce")
    df["thalach"] = pd.to_numeric(df["thalach"], errors="coerce")
    for col in df.select_dtypes(include="number").columns:
        df[col] = df[col].fillna(df[col].median())
    df["sex"] = df["sex"].map({1.0: "male", 0.0: "female"}).fillna("unknown")
    return df

def clean_us_hospitals(df):
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    print(f"  US hospitals columns: {list(df.columns[:6])}")

    # Drop empty source tracking columns
    source_cols = [c for c in df.columns if c.endswith("_source") or "_-_source" in c]
    df = df.drop(columns=source_cols)
    print(f"  Dropped {len(source_cols)} empty source columns")

    # Fix occupancy rates
    rate_cols = [c for c in df.columns if "rate" in c or "occupancy" in c]
    for col in rate_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df[col] = df[col].clip(0, 1)

    # Fix bed counts
    bed_cols = [c for c in df.columns if "bed" in c]
    for col in bed_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        median_val = df[col].median()
        df[col] = df[col].fillna(0 if pd.isna(median_val) else median_val)

    # Standardise state
    if "state" in df.columns:
        df["state"] = df["state"].str.strip().str.upper()

    # Fill string nulls
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].fillna("unknown")

    return df

def clean_ds_jobs(df):
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    print(f"  DS jobs columns: {list(df.columns[:6])}")

    # Parse salary range
    if "salary_estimate" in df.columns:
        df["salary_min"] = df["salary_estimate"].str.extract(r"\$(\d+)K").astype(float) * 1000
        df["salary_max"] = df["salary_estimate"].str.extract(r"-\$(\d+)K").astype(float) * 1000
        df["salary_avg"] = ((df["salary_min"] + df["salary_max"]) / 2).round(0)

    # Clean rating
    if "rating" in df.columns:
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
        df["rating"] = df["rating"].replace(-1, pd.NA)
        median_rating = df["rating"].median()
        df["rating"] = df["rating"].fillna(0 if pd.isna(median_rating) else median_rating)

    # Clean string columns
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.replace(r"\n", " ", regex=True).str.strip()
        df[col] = df[col].fillna("unknown")

    # Fill remaining numeric nulls
    for col in df.select_dtypes(include="number").columns:
        median_val = df[col].median()
        df[col] = df[col].fillna(0 if pd.isna(median_val) else median_val)

    return df

CLEANERS = {
    "covid_cases":   clean_covid,
    "diabetes":      clean_diabetes,
    "heart_disease": clean_heart,
    "us_hospitals":  clean_us_hospitals,
    "ds_jobs":       clean_ds_jobs,
}

def clean_to_silver(name):
    start = time.time()
    print(f"\nCleaning: {name}")

    df = read_parquet("bronze", f"{name}/data.parquet")
    raw_count = len(df)
    print(f"Bronze rows: {raw_count:,}")

    # Drop bronze metadata columns
    meta_cols = ["_ingested_at","_source_url","_dataset_name","_layer","_run_version"]
    df = df.drop(columns=[c for c in meta_cols if c in df.columns])

    # Generic cleaning
    df = df.drop_duplicates()
    df = df.dropna(how="all")

    # Dataset specific cleaning
    if name in CLEANERS:
        df = CLEANERS[name](df)

    # Add silver metadata
    df["_cleaned_at"] = datetime.now().isoformat()
    df["_layer"]      = "silver"

    clean_count = len(df)
    dropped     = raw_count - clean_count
    print(f"Clean rows: {clean_count:,} (dropped {dropped:,})")

    # Write to MinIO
    write_parquet(df, "silver", f"{name}/data.parquet")

    # Write metadata log
    metadata = {
        "timestamp":  datetime.now().isoformat(),
        "source":     f"bronze/{name}",
        "raw_rows":   raw_count,
        "clean_rows": clean_count,
        "dropped":    dropped,
        "columns":    list(df.columns),
        "layer":      "silver"
    }
    write_json(metadata, "metadata", f"silver_{name}_log.json")

    # Local copy
    local_path = Path(f"layers/silver/{name}")
    local_path.mkdir(parents=True, exist_ok=True)
    df.to_parquet(local_path / "data.parquet", index=False)

    duration = time.time() - start
    log_run(name, "silver", raw_count, clean_count, duration)
    return clean_count

if __name__ == "__main__":
    total = 0
    for name in DATASETS:
        try:
            count = clean_to_silver(name)
            total += count
        except Exception as e:
            print(f"ERROR on {name}: {e}")

    print(f"\nDONE: {total:,} clean rows across {len(DATASETS)} datasets")

    print("\n=== Verification ===")
    for name in DATASETS:
        try:
            df = read_parquet("silver", f"{name}/data.parquet")
            print(f"  {name}: {len(df):,} rows in MinIO silver bucket")
        except Exception as e:
            print(f"  {name}: MISSING - {e}")