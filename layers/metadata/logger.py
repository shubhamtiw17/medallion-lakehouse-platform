import json
import uuid
from datetime import datetime
from pathlib import Path

METADATA_PATH = Path("layers/metadata")
METADATA_PATH.mkdir(parents=True, exist_ok=True)
RUNS_FILE = METADATA_PATH / "pipeline_runs.jsonl"

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
    with open(RUNS_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")
    print(f"  Logged: {dataset} / {layer} — {output_rows:,} rows in {duration_seconds:.1f}s")
    return record