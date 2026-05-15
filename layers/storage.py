import io
import json
import os
import pandas as pd
from minio import Minio
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

MINIO_ENDPOINT   = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")

client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

BUCKETS = ["bronze", "silver", "gold", "metadata"]

def ensure_buckets():
    for bucket in BUCKETS:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
            print(f"Created bucket: {bucket}")

def write_parquet(df, bucket, key):
    ensure_buckets()
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False)
    buffer.seek(0)
    size = buffer.getbuffer().nbytes
    client.put_object(bucket, key, buffer, size,
                      content_type="application/octet-stream")
    print(f"Written to minio://{bucket}/{key} ({len(df):,} rows)")

def read_parquet(bucket, key):
    response = client.get_object(bucket, key)
    buffer   = io.BytesIO(response.read())
    return pd.read_parquet(buffer)

def write_json(data, bucket, key):
    ensure_buckets()
    content = json.dumps(data, indent=2).encode("utf-8")
    buffer  = io.BytesIO(content)
    client.put_object(bucket, key, buffer, len(content),
                      content_type="application/json")

def write_jsonl_line(record, bucket, key):
    ensure_buckets()
    try:
        existing = client.get_object(bucket, key).read().decode("utf-8")
    except:
        existing = ""
    updated = existing + json.dumps(record) + "\n"
    content = updated.encode("utf-8")
    buffer  = io.BytesIO(content)
    client.put_object(bucket, key, buffer, len(content),
                      content_type="application/json")

def read_jsonl(bucket, key):
    try:
        response = client.get_object(bucket, key)
        lines    = response.read().decode("utf-8").strip().split("\n")
        return [json.loads(l) for l in lines if l]
    except:
        return []

def read_json(bucket, key):
    try:
        response = client.get_object(bucket, key)
        return json.loads(response.read().decode("utf-8"))
    except:
        return {}