# Architecture & System Design

## Why Medallion Architecture

The medallion pattern (Bronze → Silver → Gold) solves a fundamental problem in data engineering — **raw data is never immediately trustworthy or useful**. By separating concerns into three distinct layers, each with a clear contract, we get:

- **Auditability** — raw data is always preserved in Bronze exactly as received
- **Reproducibility** — Silver and Gold can be rebuilt from Bronze at any time
- **Separation of concerns** — ingestion, cleaning, and aggregation are independent
- **Incremental trust** — data quality increases at each layer

This is the exact pattern used by Databricks, Delta Lake, and most modern data platforms at scale.

---

## Layer by Layer Design Decisions

### Bronze Layer — Raw Ingestion

**What it does:** Reads from source URLs and writes raw data to MinIO with metadata columns added.

**Why no transformations:** Bronze is a landing zone. If a Silver cleaning job has a bug, we can rerun it from Bronze without re-fetching the source. This is critical in production where APIs may be rate-limited or taken offline.

**Incremental loading:** We track `row_count` from the last run in MinIO metadata. If the source hasn't grown, we skip the write. In production this would use watermarks or CDC (Change Data Capture).

**Metadata columns added:**
```
_ingested_at    — when the row was ingested
_source_url     — where it came from
_dataset_name   — which dataset
_layer          — always "bronze"
_run_version    — row count at last run for incremental tracking
```

### Silver Layer — Cleaning & Standardisation

**What it does:** Reads Bronze, applies dataset-specific cleaning, writes clean data back to MinIO.

**Why dataset-specific cleaners:** Generic cleaning (drop nulls, drop duplicates) only goes so far. Real domain knowledge is needed — a `0` in a `Glucose` column isn't zero glucose, it's a missing value. A `-1` in a Glassdoor rating means "not rated". These rules live in Silver.

**Cleaning applied per dataset:**

| Dataset | Key cleaning |
|---------|-------------|
| COVID-19 | Date parsing, country name standardisation |
| Diabetes | Zero → null in medical columns, median imputation |
| Heart Disease | Type casting, sex encoding 1/0 → male/female |
| US Hospitals | Dropped empty source columns, occupancy rate clipping 0-1 |
| DS Jobs | Salary string parsing `$85K-$120K` → numeric, -1 rating handling |

### Gold Layer — Business Aggregations

**What it does:** Reads Silver, produces aggregated analytics-ready tables with business KPIs.

**Why aggregate here and not in the API:** Aggregating at query time is expensive at scale. Gold pre-computes the answers so the API and dashboard are fast. This mirrors how data warehouses like Snowflake and BigQuery work — the heavy lifting happens in the pipeline, not at query time.

**KPIs produced:**

| Dataset | Aggregation | KPI |
|---------|-------------|-----|
| COVID-19 | Per country | Death rate % |
| Diabetes | Per age group | Diabetes rate %, avg glucose |
| Heart Disease | Per age group + sex | Disease rate %, avg cholesterol |
| US Hospitals | Per state | Hospital count, total beds |
| DS Jobs | Per sector | Avg salary, job count |

---

## Infrastructure Design Decisions

### Why MinIO instead of local files

Local files don't scale and break when multiple processes try to read/write simultaneously. MinIO gives us:

- S3-compatible API — zero code changes needed to switch to AWS S3 in production
- Bucket isolation — bronze, silver, gold, metadata are separate namespaces
- Object storage semantics — append-only, versioned, durable

**In production this becomes:** Replace `localhost:9000` with your S3 bucket endpoint. One line change in `.env`.

### Why Apache Airflow

Airflow gives us:
- DAG-based pipeline definition — dependencies are explicit
- Retry logic — failed tasks retry automatically
- Scheduling — `@daily` runs without cron
- UI — visibility into every run, every task, every log
- Backfill — can rerun historical dates if needed

**Alternative:** Prefect or Dagster are more modern and developer-friendly. Airflow was chosen because it is the most widely used in enterprise environments and the most recognisable on a resume.

### Why PostgreSQL for Airflow metadata

Airflow needs a relational database to store DAG runs, task states, and user sessions. SQLite (Airflow's default) breaks under concurrent task execution. PostgreSQL 15 is the officially recommended backend and the most stable choice.

### Why Docker Compose

Docker Compose lets anyone clone the repo and run the full platform with one command — `docker-compose up -d`. No manual installation of MinIO, Postgres, or Airflow. This is critical for reproducibility and makes the project easy to demo.

### Why FastAPI

- Auto-generates Swagger docs at `/docs` — zero extra work
- Async-ready — handles concurrent requests efficiently
- Type hints — self-documenting and IDE-friendly
- DuckDB integration — sub-second SQL queries on Parquet files

**Alternative:** Flask is simpler but has no auto-docs. Django REST Framework is heavier and better suited to CRUD apps than analytics APIs.

### Why DuckDB for the API

DuckDB can query Parquet files directly with SQL — no database import needed. It runs in-process so there is no network latency. For analytical queries over millions of rows it is significantly faster than SQLite and comparable to PostgreSQL.

**Alternative:** Load Gold data into PostgreSQL and query from there. This adds a sync step but makes the API stateless.

### Why Streamlit

Fast to build, Python-native, and Plotly charts render beautifully. For a portfolio project it demonstrates the full stack without needing a React frontend.

**Alternative:** Grafana for production monitoring dashboards. Metabase for business user self-service analytics. Both connect to PostgreSQL or DuckDB directly.

---

## Data Quality Design

### Why score datasets 0-100 instead of pass/fail

Binary pass/fail hides how bad a failure is. A dataset with 0.1% nulls and a dataset with 40% nulls both "fail" the null check but are very different situations. A score gives operators a sense of urgency — a grade F dataset needs immediate attention, a grade B dataset can wait for the next sprint.

### Checks implemented

| Check | Penalty | Rationale |
|-------|---------|-----------|
| Null rate > 5% | -20 | High nulls indicate source problems |
| Duplicate rate > 1% | -15 | Duplicates skew aggregations |
| Row count < 100 | -30 | Too small to be meaningful |
| Missing metadata columns | -10 each | Pipeline integrity check |
| Empty columns | -10 each | Dead weight in the schema |

---

## What Could Be Improved

### Replace Pandas with PySpark
Pandas loads everything into memory — it breaks above ~10GB. PySpark distributes processing across a cluster and handles terabyte-scale datasets. The pipeline was designed with PySpark in mind; switching is a matter of replacing `pd.read_parquet` with `spark.read.parquet`.

### Replace local Parquet with Delta Lake
Delta Lake adds ACID transactions, schema enforcement, and time travel to Parquet files. You can query data as it was at any point in the past — critical for debugging production pipelines. This would be the first upgrade in a real production environment.

### Add dbt for Silver → Gold transformations
dbt (data build tool) turns SQL into a first-class transformation layer with built-in testing, documentation, and lineage tracking. The Silver → Gold aggregations in this project are a natural fit for dbt models.

### Replace MinIO with AWS S3
One environment variable change. In production `MINIO_ENDPOINT` becomes your S3 bucket endpoint and the code is unchanged.

### Replace local Airflow with AWS MWAA or Astronomer
Managed Airflow removes the operational burden of running Airflow yourself — upgrades, scaling, and availability are handled by the provider.

### Add real-time ingestion with Kafka
Currently the pipeline runs `@daily`. For real-time use cases (live COVID updates, live hospital capacity) you'd add a Kafka producer that streams new records into Bronze as they arrive, and a Spark Structured Streaming consumer that processes them into Silver in near-real-time.

### Add data lineage with OpenLineage
OpenLineage tracks which columns came from which source, which jobs transformed them, and which dashboards consume them. Essential for compliance in healthcare data environments.

### Add column-level encryption for PII
Healthcare data often contains PII (names, dates of birth, addresses). In production these columns would be encrypted at rest in Bronze and only decrypted by authorised downstream processes.

---

## Common Interview Questions

**Q: Why not just load everything into PostgreSQL from the start?**

A: Relational databases are optimised for row-level transactional operations — fast inserts, updates, and point lookups. Analytical queries (group by country, aggregate by age group) are better served by columnar storage like Parquet. At scale, a single PostgreSQL instance becomes a bottleneck that requires sharding, read replicas, and careful indexing. Object storage with Parquet scales horizontally with no configuration.

**Q: How would you handle schema changes in the source data?**

A: Bronze always accepts the raw schema as-is — it never rejects data. Silver handles schema evolution explicitly — new columns are detected and either passed through or dropped based on the cleaning logic. Delta Lake's schema evolution feature would handle this more elegantly in production, automatically merging new columns into the existing schema.

**Q: How would you scale this to handle 10x the data?**

A: Replace Pandas with PySpark on a Databricks or EMR cluster, replace MinIO with S3, replace local Parquet with Delta Lake, and replace local Airflow with MWAA. The pipeline logic itself does not change — only the execution engine and storage layer.

**Q: How do you ensure data quality doesn't degrade over time?**

A: The quality scoring system runs after every Gold build and writes scores to MinIO. In production you would add Airflow alerts that trigger when any dataset drops below a threshold score, and Great Expectations checkpoints that block downstream tasks if expectations fail.

**Q: What is incremental loading and why does it matter?**

A: Incremental loading means only processing new or changed records instead of reprocessing everything from scratch on every run. For a 161,000 row COVID dataset that grows by 200 rows per day, full reload wastes 99.9% of compute. Incremental loading tracks the last known row count and only fetches the delta. At petabyte scale this is the difference between a pipeline that finishes in minutes versus hours.

**Q: Why store metadata in MinIO rather than a database?**

A: Metadata files (pipeline runs, quality scores) are append-only and read infrequently. Storing them in MinIO keeps the architecture simple — one storage layer for everything, no additional database to manage. In production you might move this to a dedicated metadata store like Apache Atlas or DataHub for richer lineage queries.

**Q: What is the difference between a data lake and a data warehouse?**

A: A data lake stores raw data in its native format (CSV, JSON, Parquet) with no enforced schema — schema is applied on read. A data warehouse enforces a schema on write and is optimised for SQL queries. A lakehouse combines both — it stores data in open formats like Parquet (lake) but adds ACID transactions and schema enforcement (warehouse) via Delta Lake or Apache Iceberg. This project is a lakehouse implementation.