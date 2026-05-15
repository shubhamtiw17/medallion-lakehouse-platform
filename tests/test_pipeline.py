import pandas as pd
import duckdb
import sys
sys.path.append(".")

def test_bronze_files_exist():
    from pathlib import Path
    for name in ["covid_cases", "diabetes", "heart_disease"]:
        assert Path(f"layers/bronze/{name}/data.parquet").exists()

def test_silver_files_exist():
    from pathlib import Path
    for name in ["covid_cases", "diabetes", "heart_disease"]:
        assert Path(f"layers/silver/{name}/data.parquet").exists()

def test_gold_files_exist():
    from pathlib import Path
    for name in ["covid_cases", "diabetes", "heart_disease"]:
        assert Path(f"layers/gold/{name}/data.parquet").exists()

def test_silver_no_all_null_rows():
    for name in ["covid_cases", "diabetes", "heart_disease"]:
        df = pd.read_parquet(f"layers/silver/{name}/data.parquet")
        assert df.isnull().all(axis=1).sum() == 0

def test_silver_smaller_or_equal_to_bronze():
    for name in ["covid_cases", "diabetes", "heart_disease"]:
        bronze = pd.read_parquet(f"layers/bronze/{name}/data.parquet")
        silver = pd.read_parquet(f"layers/silver/{name}/data.parquet")
        assert len(silver) <= len(bronze)

def test_gold_covid_columns():
    df = duckdb.sql("SELECT * FROM read_parquet('layers/gold/covid_cases/data.parquet')").df()
    assert "death_rate_pct"   in df.columns
    assert "total_confirmed"  in df.columns
    assert "total_deaths"     in df.columns

def test_gold_death_rate_valid():
    df = duckdb.sql("SELECT * FROM read_parquet('layers/gold/covid_cases/data.parquet')").df()
    assert df["death_rate_pct"].between(0, 100).all()

def test_gold_diabetes_rate_valid():
    df = duckdb.sql("SELECT * FROM read_parquet('layers/gold/diabetes/data.parquet')").df()
    assert df["diabetes_rate_pct"].between(0, 100).all()

def test_metadata_log_exists():
    from pathlib import Path
    assert Path("layers/metadata/pipeline_runs.jsonl").exists()

def test_quality_scores_exist():
    from pathlib import Path
    assert Path("layers/metadata/quality_scores.json").exists()