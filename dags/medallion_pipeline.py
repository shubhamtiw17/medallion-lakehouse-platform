from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, "/opt/airflow")
os.environ["MINIO_ENDPOINT"]   = "minio:9000"
os.environ["MINIO_ACCESS_KEY"] = "admin"
os.environ["MINIO_SECRET_KEY"] = "password123"

DATASETS = [
    {"name": "covid_cases",   "url": "https://raw.githubusercontent.com/datasets/covid-19/main/data/countries-aggregated.csv",                                                                          "description": "COVID-19 country-level aggregated cases",        "header": True},
    {"name": "diabetes",      "url": "https://raw.githubusercontent.com/plotly/datasets/master/diabetes.csv",                                                                                           "description": "Pima Indians Diabetes dataset",                  "header": True},
    {"name": "heart_disease", "url": "https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/processed.cleveland.data",                                                                "description": "UCI Heart Disease Cleveland dataset",            "header": False},
    {"name": "us_hospitals",  "url": "https://raw.githubusercontent.com/covidcaremap/covid19-healthsystemcapacity/master/data/published/us_healthcare_capacity-facility-CovidCareMap.csv",              "description": "US hospital capacity data",                      "header": True},
    {"name": "ds_jobs",       "url": "https://raw.githubusercontent.com/andreluizls1/datacleaning_glassdoor/main/Uncleaned_DS_jobs.csv",                                                                "description": "Uncleaned data science jobs dataset",            "header": True},
]

default_args = {
    "owner":            "lakehouse",
    "retries":          2,
    "retry_delay":      timedelta(minutes=3),
    "email_on_failure": False,
}

def task_bronze():
    from layers.bronze.ingest import ingest_to_bronze
    for ds in DATASETS:
        ingest_to_bronze(ds["name"], ds["url"], ds["description"], ds["header"])

def task_silver():
    from layers.silver.clean import clean_to_silver
    for ds in DATASETS:
        try:
            clean_to_silver(ds["name"])
        except Exception as e:
            print(f"Silver failed for {ds['name']}: {e}")

def task_gold():
    from layers.gold.aggregate import (
        build_gold_covid, build_gold_diabetes, build_gold_heart,
        build_gold_us_hospitals, build_gold_ds_jobs, save_gold
    )
    save_gold(build_gold_covid(),         "covid_cases")
    save_gold(build_gold_diabetes(),      "diabetes")
    save_gold(build_gold_heart(),         "heart_disease")
    save_gold(build_gold_us_hospitals(),  "us_hospitals")
    save_gold(build_gold_ds_jobs(),       "ds_jobs")

def task_validate():
    from validation.validate import score_dataset
    import json
    from pathlib import Path

    results = []
    for ds in DATASETS:
        try:
            result = score_dataset(ds["name"])
            results.append(result)
            print(f"{ds['name']}: {result['score']}/100 (Grade: {result['grade']})")
        except Exception as e:
            print(f"Validation failed for {ds['name']}: {e}")

    avg = sum(r["score"] for r in results) / len(results) if results else 0
    print(f"\nOverall average quality score: {avg:.0f}/100")

    Path("/opt/airflow/layers/metadata").mkdir(parents=True, exist_ok=True)
    with open("/opt/airflow/layers/metadata/quality_scores.json", "w") as f:
        json.dump(results, f, indent=2)

with DAG(
    "medallion_pipeline",
    default_args=default_args,
    description="Bronze → Silver → Gold healthcare lakehouse pipeline",
    schedule_interval="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["lakehouse", "healthcare", "production"],
) as dag:

    bronze_task = PythonOperator(
        task_id="ingest_bronze",
        python_callable=task_bronze,
    )

    silver_task = PythonOperator(
        task_id="clean_silver",
        python_callable=task_silver,
    )

    gold_task = PythonOperator(
        task_id="aggregate_gold",
        python_callable=task_gold,
    )

    validate_task = PythonOperator(
        task_id="validate_quality",
        python_callable=task_validate,
    )

    bronze_task >> silver_task >> gold_task >> validate_task