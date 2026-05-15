import pandas as pd
import duckdb
import json
import time
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(".")
from layers.metadata.logger import log_run

def build_gold_covid():
    df = pd.read_parquet("layers/silver/covid_cases/data.parquet")
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
    df = pd.read_parquet("layers/silver/diabetes/data.parquet")
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
    df = pd.read_parquet("layers/silver/heart_disease/data.parquet")
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
    gold["sex"]               = gold["sex"].map({1: "male", 0: "female"}).fillna("unknown")
    gold["_aggregated_at"]    = datetime.now().isoformat()
    gold["_layer"]            = "gold"
    return gold

def save_gold(df, name):
    output_path = Path(f"layers/gold/{name}")
    output_path.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path / "data.parquet", index=False)

    log_path = output_path / "_delta_log"
    log_path.mkdir(exist_ok=True)
    metadata = {
        "timestamp": datetime.now().isoformat(),
        "source":    f"layers/silver/{name}",
        "rows":      len(df),
        "columns":   list(df.columns),
        "layer":     "gold"
    }
    with open(log_path / "00000000000000000000.json", "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Written to {output_path} ({len(df):,} rows)")

if __name__ == "__main__":
    print("Building gold layer...\n")

    print("Aggregating: covid_cases")
    start = time.time()
    covid = build_gold_covid()
    save_gold(covid, "covid_cases")
    log_run("covid_cases", "gold", 161568, len(covid), time.time() - start)

    print("Aggregating: diabetes")
    start = time.time()
    diabetes = build_gold_diabetes()
    save_gold(diabetes, "diabetes")
    log_run("diabetes", "gold", 768, len(diabetes), time.time() - start)

    print("Aggregating: heart_disease")
    start = time.time()
    heart = build_gold_heart()
    save_gold(heart, "heart_disease")
    log_run("heart_disease", "gold", 303, len(heart), time.time() - start)

    print("\n=== Verification ===")
    for name in ["covid_cases", "diabetes", "heart_disease"]:
        con    = duckdb.connect()
        count  = con.execute(f"SELECT COUNT(*) FROM read_parquet('layers/gold/{name}/data.parquet')").fetchone()[0]
        sample = con.execute(f"SELECT * FROM read_parquet('layers/gold/{name}/data.parquet') LIMIT 2").df()
        print(f"\n  {name}: {count:,} aggregated rows")
        print(sample.to_string(index=False))

    print("\nDONE: Gold layer complete")