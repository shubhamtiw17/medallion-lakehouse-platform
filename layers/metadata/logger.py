import json
import uuid
from datetime import datetime
from pathlib import Path
import sys
sys.path.append(".")

def log_run(dataset, layer, input_rows, output_rows, duration_seconds, quality_score=None):
    record = {
        "run_id":           str(uuid.uuid4()),
        "dataset":          dataset,
        "layer":            layer,
        "input_rows":       input_rows,
        "output_rows":      output_rows,
        "rows_dropped":     input_rows - output_rows,
        "duration_seconds": round(duration_seconds, 2),
        "quality_score":    quality_score,
        "run_at":           datetime.now().isoformat()
    }

    # Write to MinIO
    try:
        from layers.storage import write_jsonl_line
        write_jsonl_line(record, "metadata", "pipeline_runs.jsonl")
    except Exception as e:
        print(f"MinIO log failed, falling back to local: {e}")
        Path("layers/metadata").mkdir(parents=True, exist_ok=True)
        with open("layers/metadata/pipeline_runs.jsonl", "a") as f:
            f.write(json.dumps(record) + "\n")

    print(f"  Logged: {dataset} / {layer} — {output_rows:,} rows in {duration_seconds:.1f}s")
    return record