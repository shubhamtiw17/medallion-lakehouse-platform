from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import duckdb
import json
from pathlib import Path

app = FastAPI(
    title="Medallion Lakehouse API",
    description="Healthcare analytics REST API — Bronze/Silver/Gold architecture",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def query(sql):
    return duckdb.connect().execute(sql).df().to_dict(orient="records")

@app.get("/")
def root():
    return {
        "name": "Medallion Lakehouse API",
        "status": "running",
        "datasets": ["covid_cases", "diabetes", "heart_disease"]
    }

@app.get("/health")
def health():
    try:
        duckdb.connect().execute("SELECT 1 FROM read_parquet('layers/gold/covid_cases/data.parquet') LIMIT 1")
        return {"status": "healthy", "gold_layer": "accessible"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@app.get("/covid/summary")
def covid_summary():
    return query("""
        SELECT Country, total_confirmed, total_deaths, death_rate_pct
        FROM read_parquet('layers/gold/covid_cases/data.parquet')
        ORDER BY total_confirmed DESC
        LIMIT 20
    """)

@app.get("/covid/top-deaths")
def covid_top_deaths():
    return query("""
        SELECT Country, total_deaths, death_rate_pct
        FROM read_parquet('layers/gold/covid_cases/data.parquet')
        ORDER BY total_deaths DESC
        LIMIT 10
    """)

@app.get("/diabetes/by-age")
def diabetes_by_age():
    return query("""
        SELECT age_group, total_patients, diabetic_count,
               diabetes_rate_pct, avg_glucose, avg_bmi
        FROM read_parquet('layers/gold/diabetes/data.parquet')
        ORDER BY age_group
    """)

@app.get("/heart/by-age-sex")
def heart_by_age_sex():
    return query("""
        SELECT age_group, sex, total_patients,
               disease_rate_pct, avg_cholesterol, avg_max_hr
        FROM read_parquet('layers/gold/heart_disease/data.parquet')
        ORDER BY age_group, sex
    """)

@app.get("/lineage")
def get_lineage():
    runs_file = Path("layers/metadata/pipeline_runs.jsonl")
    if not runs_file.exists():
        return []
    with open(runs_file) as f:
        return [json.loads(line) for line in f.readlines()]