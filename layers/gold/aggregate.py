import pandas as pd
import json
import time
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(".")
from layers.storage import write_parquet, read_parquet, write_json
from layers.metadata.logger import log_run

def build_gold_covid():
    df = read_parquet("silver", "covid_cases/data.parquet")
    gold = df.groupby("Country").agg(
        total_confirmed=("Confirmed", "max"),
        total_recovered=("Recovered", "max"),
        total_deaths=("Deaths",      "max"),
        data_points=("Confirmed",    "count")
    ).reset_index()
    gold["death_rate_pct"] = (
        (gold["total_deaths"] / gold["total_confirmed"]) * 100
    ).round(2).fillna(0)
    gold["_aggregated_at"] = datetime.now().isoformat()
    gold["_layer"]         = "gold"
    return gold

def build_gold_diabetes():
    df = read_parquet("silver", "diabetes/data.parquet")
    df["age_group"] = pd.cut(
        df["Age"],
        bins=[0, 30, 45, 60, 100],
        labels=["Under 30", "30-45", "45-60", "Over 60"]
    ).astype(str)
    gold = df.groupby("age_group").agg(
        total_patients=("Outcome", "count"),
        diabetic_count=("Outcome", "sum"),
        avg_glucose=("Glucose",   "mean"),
        avg_bmi=("BMI",           "mean")
    ).reset_index()
    gold["diabetes_rate_pct"] = ((gold["diabetic_count"] / gold["total_patients"]) * 100).round(2)
    gold["avg_glucose"]       = gold["avg_glucose"].round(2)
    gold["avg_bmi"]           = gold["avg_bmi"].round(2)
    gold["_aggregated_at"]    = datetime.now().isoformat()
    gold["_layer"]            = "gold"
    return gold

def build_gold_heart():
    df = read_parquet("silver", "heart_disease/data.parquet")
    df["age_group"] = pd.cut(
        df["age"],
        bins=[0, 40, 55, 70, 100],
        labels=["Under 40", "40-55", "55-70", "Over 70"]
    ).astype(str)
    gold = df.groupby(["age_group", "sex"]).agg(
        total_patients=("target",  "count"),
        disease_count=("target",   "sum"),
        avg_cholesterol=("chol",   "mean"),
        avg_max_hr=("thalach",     "mean")
    ).reset_index()
    gold["disease_rate_pct"]  = ((gold["disease_count"] / gold["total_patients"]) * 100).round(2)
    gold["avg_cholesterol"]   = gold["avg_cholesterol"].round(2)
    gold["avg_max_hr"]        = gold["avg_max_hr"].round(2)
    gold["_aggregated_at"]    = datetime.now().isoformat()
    gold["_layer"]            = "gold"
    return gold

def build_gold_us_hospitals():
    df = read_parquet("silver", "us_hospitals/data.parquet")
    print(f"  US hospitals columns: {list(df.columns[:6])}")

    group_col = "state" if "state" in df.columns else df.columns[0]
    bed_col   = next((c for c in df.columns if "staffed_all_beds" in c), None)
    if not bed_col:
        bed_col = next((c for c in df.columns if "bed" in c), None)
    if not bed_col:
        print("  No bed column found")
        return pd.DataFrame()

    icu_col  = next((c for c in df.columns if "icu" in c and "bed" in c), None)
    rate_col = next((c for c in df.columns if "occupancy" in c and "rate" in c and "icu" not in c), None)

    agg_dict = {bed_col: ["count", "sum", "mean"]}
    if icu_col:
        agg_dict[icu_col] = ["sum", "mean"]
    if rate_col:
        agg_dict[rate_col] = ["mean"]

    gold = df.groupby(group_col).agg(agg_dict).reset_index()
    gold.columns = [
        "_".join(col).strip("_") if isinstance(col, tuple) else col
        for col in gold.columns
    ]
    gold = gold.rename(columns={
        f"{bed_col}_count": "hospital_count",
        f"{bed_col}_sum":   "total_staffed_beds",
        f"{bed_col}_mean":  "avg_staffed_beds",
    })
    for col in gold.select_dtypes(include="number").columns:
        gold[col] = gold[col].round(1)

    gold["_aggregated_at"] = datetime.now().isoformat()
    gold["_layer"]         = "gold"
    return gold

def build_gold_ds_jobs():
    df = read_parquet("silver", "ds_jobs/data.parquet")
    print(f"  DS jobs columns: {list(df.columns[:8])}")

    salary_col = "salary_avg" if "salary_avg" in df.columns else None
    group_col  = next(
        (c for c in df.columns if c in ["sector", "industry"]),
        None
    )

    if not salary_col:
        print("  No salary_avg column found — skipping ds_jobs gold")
        return pd.DataFrame()

    if not group_col:
        print("  No sector/industry column found — skipping ds_jobs gold")
        return pd.DataFrame()

    gold = df.groupby(group_col).agg(
        job_count  = (group_col,  "count"),
        avg_salary = (salary_col, "mean"),
        min_salary = (salary_col, "min"),
        max_salary = (salary_col, "max"),
        avg_rating = ("rating",   "mean")
    ).reset_index()

    gold["avg_salary"]     = gold["avg_salary"].round(0)
    gold["avg_rating"]     = gold["avg_rating"].round(2)
    gold["_aggregated_at"] = datetime.now().isoformat()
    gold["_layer"]         = "gold"
    return gold

def build_gold_covid_hospitals_join():
    try:
        covid     = read_parquet("gold", "covid_cases/data.parquet")
        hospitals = read_parquet("gold", "us_hospitals/data.parquet")

        state_col = next((c for c in hospitals.columns if c == "state"), None)
        if not state_col:
            print("  No state column in hospitals gold layer")
            return pd.DataFrame()

        us_covid = covid[covid["Country"].str.contains(
            "US|United States|America", na=False, case=False
        )]
        if us_covid.empty:
            us_covid = covid[covid["Country"] == "Us"]
        if us_covid.empty:
            print("  No US COVID data found for join")
            return pd.DataFrame()

        hospitals["total_us_confirmed"] = us_covid["total_confirmed"].values[0]
        hospitals["total_us_deaths"]    = us_covid["total_deaths"].values[0]
        hospitals["_joined_at"]         = datetime.now().isoformat()
        hospitals["_layer"]             = "gold"

        print(f"  Built hospital + COVID join: {len(hospitals):,} rows")
        return hospitals

    except Exception as e:
        print(f"  Join failed: {e}")
        return pd.DataFrame()

def save_gold(df, name):
    if df is None or df.empty:
        print(f"  Skipping {name} — empty dataframe")
        return

    write_parquet(df, "gold", f"{name}/data.parquet")

    local_path = Path(f"layers/gold/{name}")
    local_path.mkdir(parents=True, exist_ok=True)
    df.to_parquet(local_path / "data.parquet", index=False)

    metadata = {
        "timestamp": datetime.now().isoformat(),
        "rows":      len(df),
        "columns":   list(df.columns),
        "layer":     "gold"
    }
    write_json(metadata, "metadata", f"gold_{name}_log.json")
    print(f"Written {name}: {len(df):,} rows")

if __name__ == "__main__":
    print("Building gold layer...\n")

    datasets = [
        ("covid_cases",   build_gold_covid,        161568),
        ("diabetes",      build_gold_diabetes,      768),
        ("heart_disease", build_gold_heart,         303),
        ("us_hospitals",  build_gold_us_hospitals,  7154),
        ("ds_jobs",       build_gold_ds_jobs,       672),
    ]

    for name, builder, input_rows in datasets:
        print(f"Aggregating: {name}")
        start = time.time()
        try:
            df = builder()
            save_gold(df, name)
            if df is not None and not df.empty:
                log_run(name, "gold", input_rows, len(df), time.time() - start)
        except Exception as e:
            print(f"  SKIPPED {name}: {e}")

    print("\nBuilding cross-dataset join: covid + us_hospitals")
    start = time.time()
    try:
        joined = build_gold_covid_hospitals_join()
        save_gold(joined, "covid_hospitals_joined")
        if joined is not None and not joined.empty:
            log_run("covid_hospitals_joined", "gold", 0, len(joined), time.time() - start)
    except Exception as e:
        print(f"  SKIPPED join: {e}")

    print("\n=== Verification ===")
    for name, _, _ in datasets:
        try:
            df    = read_parquet("gold", f"{name}/data.parquet")
            print(f"  {name}: {len(df):,} aggregated rows in MinIO gold bucket")
        except Exception as e:
            print(f"  {name}: SKIPPED - {e}")

    print("\nDONE: Gold layer complete")