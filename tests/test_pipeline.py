import pandas as pd
import sys
sys.path.append(".")

DATASETS = ["covid_cases", "diabetes", "heart_disease", "us_hospitals", "ds_jobs"]

def test_bronze_files_exist_in_minio():
    from layers.storage import read_parquet
    for name in DATASETS:
        df = read_parquet("bronze", f"{name}/data.parquet")
        assert len(df) > 0, f"Bronze {name} is empty in MinIO"

def test_silver_files_exist_in_minio():
    from layers.storage import read_parquet
    for name in DATASETS:
        df = read_parquet("silver", f"{name}/data.parquet")
        assert len(df) > 0, f"Silver {name} is empty in MinIO"

def test_gold_files_exist_in_minio():
    from layers.storage import read_parquet
    for name in DATASETS:
        df = read_parquet("gold", f"{name}/data.parquet")
        assert len(df) > 0, f"Gold {name} is empty in MinIO"

def test_silver_has_metadata_columns():
    from layers.storage import read_parquet
    for name in DATASETS:
        df = read_parquet("silver", f"{name}/data.parquet")
        assert "_cleaned_at" in df.columns, f"{name} missing _cleaned_at"
        assert "_layer"      in df.columns, f"{name} missing _layer"
        assert df["_layer"].iloc[0] == "silver", f"{name} _layer is not silver"

def test_silver_no_all_null_rows():
    from layers.storage import read_parquet
    for name in DATASETS:
        df = read_parquet("silver", f"{name}/data.parquet")
        all_null = df.isnull().all(axis=1).sum()
        assert all_null == 0, f"{name} has {all_null} completely null rows"

def test_silver_smaller_or_equal_to_bronze():
    from layers.storage import read_parquet
    for name in DATASETS:
        bronze = read_parquet("bronze", f"{name}/data.parquet")
        silver = read_parquet("silver", f"{name}/data.parquet")
        assert len(silver) <= len(bronze), \
            f"{name}: silver ({len(silver)}) has more rows than bronze ({len(bronze)})"

def test_gold_covid_columns():
    from layers.storage import read_parquet
    df = read_parquet("gold", "covid_cases/data.parquet")
    assert "death_rate_pct"  in df.columns
    assert "total_confirmed" in df.columns
    assert "total_deaths"    in df.columns
    assert "Country"         in df.columns

def test_gold_death_rate_valid():
    from layers.storage import read_parquet
    df = read_parquet("gold", "covid_cases/data.parquet")
    assert df["death_rate_pct"].between(0, 100).all(), \
        "Death rate contains values outside 0-100%"

def test_gold_diabetes_rate_valid():
    from layers.storage import read_parquet
    df = read_parquet("gold", "diabetes/data.parquet")
    assert df["diabetes_rate_pct"].between(0, 100).all(), \
        "Diabetes rate contains values outside 0-100%"

def test_gold_us_hospitals_has_state():
    from layers.storage import read_parquet
    df = read_parquet("gold", "us_hospitals/data.parquet")
    assert "state"            in df.columns
    assert "hospital_count"   in df.columns
    assert len(df) > 0

def test_gold_ds_jobs_has_salary():
    from layers.storage import read_parquet
    df = read_parquet("gold", "ds_jobs/data.parquet")
    assert "avg_salary" in df.columns
    assert "job_count"  in df.columns
    assert len(df) > 0

def test_metadata_log_exists_in_minio():
    from layers.storage import read_jsonl
    runs = read_jsonl("metadata", "pipeline_runs.jsonl")
    assert len(runs) > 0, "No pipeline runs logged in MinIO"

def test_quality_scores_exist_in_minio():
    from layers.storage import read_json
    scores = read_json("metadata", "quality_scores.json")
    assert len(scores) > 0, "No quality scores in MinIO"