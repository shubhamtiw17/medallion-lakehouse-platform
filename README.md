# Medallion Lakehouse Data Engineering Platform

A production-ready healthcare analytics platform built on **Bronze → Silver → Gold** medallion architecture, orchestrated with Apache Airflow, stored in MinIO (S3-compatible), and served via FastAPI and Streamlit.

> This is a personal portfolio project and is not open for external contributions.

![Pipeline](screenshots/dashboard.png)

---

## Architecture

```
Live Public URLs (5 healthcare datasets)
              ↓
    Bronze Layer — MinIO S3
    Raw ingestion + metadata + incremental loading
              ↓
    Silver Layer — MinIO S3
    Cleaning · deduplication · type casting · null handling
              ↓
    Gold Layer — MinIO S3
    Business aggregations · KPIs · cross-dataset joins
              ↓
    FastAPI          Streamlit Dashboard
    REST endpoints   Interactive charts + lineage tab
```

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| Pandas | Data ingestion and transformation |
| DuckDB | Fast local SQL analytics |
| MinIO | S3-compatible local object storage |
| Apache Airflow | Pipeline orchestration and scheduling |
| PostgreSQL 15 | Airflow metadata database |
| Docker Compose | Full local infrastructure |
| FastAPI | REST API with auto Swagger docs |
| Streamlit | Interactive analytics dashboard |
| Plotly | Charts and visualizations |
| Pytest | 13 automated pipeline tests |
| GitHub Actions | CI/CD — runs pipeline on every push |

---

## Datasets

| Dataset | Source | Bronze Rows | Cleaning Work |
|---------|--------|-------------|---------------|
| COVID-19 Cases | github.com/datasets/covid-19 | 161,568 | Date parsing, country standardisation |
| Pima Diabetes | plotly/datasets | 768 | Zero → null replacement in medical columns |
| UCI Heart Disease | UCI ML Repository | 303 | Type casting, sex column encoding |
| US Hospital Capacity | covidcaremap/covid19 | 7,154 | Occupancy rate clipping, snake_case columns |
| Data Science Jobs | Glassdoor (uncleaned) | 672 | Salary string parsing, rating -1 handling |

---

## Gold Layer KPIs

| Dataset | Aggregation | Key Metric |
|---------|-------------|------------|
| COVID-19 | Per country | Death rate % |
| Diabetes | Per age group | Diabetes rate % + avg glucose |
| Heart Disease | Per age group + sex | Disease rate % + avg cholesterol |
| US Hospitals | Per state | Hospital count + total beds |
| DS Jobs | Per sector | Avg salary + job count |

---

## Quick Start

**Prerequisites:** Docker Desktop, Python 3.11, Git

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/medallion-lakehouse-platform
cd medallion-lakehouse-platform

# 2. Create environment file
cp .env.example .env

# 3. Start infrastructure
docker-compose up -d

# 4. Install dependencies
pip install pandas duckdb fastapi uvicorn streamlit plotly pyarrow minio python-dotenv pytest

# 5. Run the full pipeline
python layers/bronze/ingest.py
python layers/silver/clean.py
python layers/gold/aggregate.py
python validation/validate.py

# 6. Run tests
pytest tests/ -v

# 7. Start the API
uvicorn api.main:app --reload --port 8000

# 8. Start the dashboard (new terminal)
python -m streamlit run dashboard/app.py
```

---

## Infrastructure

| Service | URL | Credentials |
|---------|-----|-------------|
| Airflow UI | http://localhost:8080 | admin / admin |
| MinIO Console | http://localhost:9001 | admin / password123 |
| FastAPI Swagger | http://localhost:8000/docs | — |
| Streamlit Dashboard | http://localhost:8501 | — |

---

## Airflow Pipeline

The DAG `medallion_pipeline` runs daily and executes 4 tasks in sequence:

```
ingest_bronze → clean_silver → aggregate_gold → validate_quality
```

Trigger manually:
```bash
docker exec lakehouse_airflow airflow dags trigger medallion_pipeline
```

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Service info |
| `GET /health` | Health check |
| `GET /covid/summary` | Top 20 countries by confirmed cases |
| `GET /covid/top-deaths` | Top 10 countries by death count |
| `GET /diabetes/by-age` | Diabetes rate by age group |
| `GET /heart/by-age-sex` | Heart disease rate by age and sex |
| `GET /lineage` | Full pipeline run history |

---

## Data Quality

All datasets scored using automated quality checks:

| Dataset | Score | Grade |
|---------|-------|-------|
| COVID-19 | 100/100 | A |
| Diabetes | 100/100 | A |
| Heart Disease | 100/100 | A |
| US Hospitals | 100/100 | A |
| DS Jobs | 100/100 | A |
| **Overall** | **100/100** | **A** |

---

## Project Structure

```
medallion-lakehouse-platform/
├── layers/
│   ├── storage.py           # MinIO read/write client
│   ├── bronze/
│   │   └── ingest.py        # Raw ingestion + incremental loading
│   ├── silver/
│   │   └── clean.py         # Cleaning + transformation
│   ├── gold/
│   │   └── aggregate.py     # Business aggregations + KPIs
│   └── metadata/
│       └── logger.py        # Pipeline run logging
├── api/
│   └── main.py              # FastAPI REST endpoints
├── dashboard/
│   └── app.py               # Streamlit dashboard
├── dags/
│   └── medallion_pipeline.py # Airflow DAG
├── validation/
│   └── validate.py          # Data quality scoring
├── tests/
│   └── test_pipeline.py     # 13 pytest tests
├── .github/
│   └── workflows/
│       └── pipeline.yml     # GitHub Actions CI/CD
├── docker-compose.yml        # Full local infrastructure
├── .env.example             # Environment variable template
└── requirements.txt
```

---

## Environment Setup

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=your_access_key
MINIO_SECRET_KEY=your_secret_key
```

---

## What I Built

- Medallion lakehouse architecture from scratch with real public healthcare datasets
- Incremental data ingestion — skips unchanged data on repeat runs
- Dataset-specific Silver cleaning — zero replacement in medical columns, salary string parsing, occupancy rate validation
- Business aggregations in Gold layer producing death rates, diabetes rates, disease rates by demographic
- Full metadata lineage tracking — every pipeline run logged to MinIO
- Data quality scoring system grading each dataset 0-100 with automated checks
- REST API with 7 endpoints and auto-generated Swagger documentation
- Interactive 4-tab Streamlit dashboard including pipeline lineage tab
- Apache Airflow DAG orchestrating daily scheduled pipeline runs
- MinIO as local S3 replacement — all data stored in object storage buckets
- Docker Compose spinning up MinIO, Airflow, and PostgreSQL in one command
- 13 pytest unit tests validating every layer in MinIO
- GitHub Actions CI/CD running the full pipeline and tests on every push
- Credentials secured in `.env` file — never committed to version control

---

## Note on Production Design

> Pipeline uses Pandas locally for Windows compatibility.
> Production design uses PySpark + Delta Lake on Linux/cloud,
> which is reflected in the architecture and Airflow DAG design.