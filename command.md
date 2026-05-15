# Platform Commands Reference

## Starting the Platform

### Step 1 — Start infrastructure (always first)
```bash
docker-compose up -d
```
Starts MinIO, PostgreSQL, Airflow, and MinIO bucket initialisation.
Wait 30 seconds for all services to be healthy.

### Step 2 — Verify all containers are running
```bash
docker ps
```
Expected output — 4 containers:
```
lakehouse_airflow
lakehouse_postgres
lakehouse_minio
lakehouse_minio_init  (exits automatically after creating buckets)
```

### Step 3 — Verify service UIs are accessible
```
http://localhost:9001   MinIO console      admin / password123
http://localhost:8080   Airflow UI         admin / admin
```

---

## Running the Pipeline

### Option A — Run locally (recommended for development)
```bash
# Run each layer in order
python layers/bronze/ingest.py
python layers/silver/clean.py
python layers/gold/aggregate.py
python validation/validate.py
```

### Option B — Trigger via Airflow (recommended for production)
```bash
docker exec lakehouse_airflow airflow dags trigger medallion_pipeline
```
Then watch progress at `http://localhost:8080`

### Option C — Run everything in one command
```bash
python layers/bronze/ingest.py && \
python layers/silver/clean.py && \
python layers/gold/aggregate.py && \
python validation/validate.py && \
pytest tests/ -v
```

---

## Starting the API and Dashboard

### Start FastAPI (Terminal 1)
```bash
uvicorn api.main:app --reload --port 8000
```
Available at:
```
http://localhost:8000        Service info
http://localhost:8000/docs   Swagger UI
http://localhost:8000/health Health check
```

### Start Streamlit (Terminal 2)
```bash
python -m streamlit run dashboard/app.py
```
Available at:
```
http://localhost:8501
```

---

## Running Tests

### Run all 13 tests
```bash
pytest tests/ -v
```

### Run a specific test
```bash
pytest tests/test_pipeline.py::test_gold_covid_columns -v
```

### Run tests and show coverage
```bash
pytest tests/ -v --tb=short
```

---

## Airflow Commands

### List all DAGs
```bash
docker exec lakehouse_airflow airflow dags list
```

### Trigger pipeline manually
```bash
docker exec lakehouse_airflow airflow dags trigger medallion_pipeline
```

### Check DAG status
```bash
docker exec lakehouse_airflow airflow dags state medallion_pipeline $(date +%Y-%m-%dT%H:%M:%S) default
```

### View task logs
```bash
docker exec lakehouse_airflow airflow tasks logs medallion_pipeline ingest_bronze latest
docker exec lakehouse_airflow airflow tasks logs medallion_pipeline clean_silver latest
docker exec lakehouse_airflow airflow tasks logs medallion_pipeline aggregate_gold latest
docker exec lakehouse_airflow airflow tasks logs medallion_pipeline validate_quality latest
```

### Clear and rerun failed tasks
```bash
docker exec lakehouse_airflow airflow tasks clear medallion_pipeline -y
docker exec lakehouse_airflow airflow dags trigger medallion_pipeline
```

### Pause the daily schedule
```bash
docker exec lakehouse_airflow airflow dags pause medallion_pipeline
```

### Resume the daily schedule
```bash
docker exec lakehouse_airflow airflow dags unpause medallion_pipeline
```

---

## Docker Commands

### Start all containers
```bash
docker-compose up -d
```

### Stop all containers (data preserved)
```bash
docker-compose down
```

### Stop and delete all data (full reset)
```bash
docker-compose down -v
```

### Restart a specific container
```bash
docker-compose restart airflow
docker-compose restart minio
docker-compose restart postgres
```

### View container logs
```bash
docker logs lakehouse_airflow
docker logs lakehouse_minio
docker logs lakehouse_postgres
```

### View live logs
```bash
docker logs -f lakehouse_airflow
```

### Check container resource usage
```bash
docker stats
```

### Open a shell inside a container
```bash
docker exec -it lakehouse_airflow bash
docker exec -it lakehouse_minio bash
docker exec -it lakehouse_postgres bash
```

### Install a package inside Airflow container
```bash
docker exec -u root lakehouse_airflow pip install <package>
```

---

## MinIO Commands

### List all buckets
```bash
docker exec lakehouse_minio mc alias set local http://localhost:9000 admin password123
docker exec lakehouse_minio mc ls local
```

### List files in a bucket
```bash
docker exec lakehouse_minio mc ls local/bronze
docker exec lakehouse_minio mc ls local/silver
docker exec lakehouse_minio mc ls local/gold
docker exec lakehouse_minio mc ls local/metadata
```

### Check bucket sizes
```bash
docker exec lakehouse_minio mc du local/bronze
docker exec lakehouse_minio mc du local/silver
docker exec lakehouse_minio mc du local/gold
```

---

## Git Commands

### Save your work
```bash
git add .
git commit -m "your message here"
git push origin main
```

### Check what has changed
```bash
git status
git diff
```

### View commit history
```bash
git log --oneline
```

---

## Stopping the Platform

### Normal shutdown (preserves all data)
```bash
docker-compose down
```

### Full reset (deletes all MinIO data and Airflow history)
```bash
docker-compose down -v
```

---

## Typical Daily Workflow

```bash
# Morning — start everything
docker-compose up -d
python layers/bronze/ingest.py
python layers/silver/clean.py
python layers/gold/aggregate.py
python validation/validate.py

# Work on code changes...

# Test your changes
pytest tests/ -v

# Start services to test locally
uvicorn api.main:app --reload --port 8000
python -m streamlit run dashboard/app.py

# Save your work
git add .
git commit -m "feat: your change"
git push origin main

# Evening — shut everything down
docker-compose down
```