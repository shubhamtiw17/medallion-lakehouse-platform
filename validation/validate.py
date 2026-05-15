import pandas as pd
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(".")
from layers.storage import read_parquet, write_json

DATASETS = ["covid_cases", "diabetes", "heart_disease", "us_hospitals", "ds_jobs"]

def score_dataset(name):
    df     = read_parquet("silver", f"{name}/data.parquet")
    score  = 100
    issues = []

    null_pct = df.isnull().sum().sum() / (len(df) * len(df.columns)) * 100
    if null_pct > 5:
        score -= 20
        issues.append(f"High null rate: {null_pct:.1f}%")

    dup_pct = df.duplicated().sum() / len(df) * 100
    if dup_pct > 1:
        score -= 15
        issues.append(f"Duplicates: {dup_pct:.1f}%")

    if len(df) < 100:
        score -= 30
        issues.append(f"Low row count: {len(df)}")

    for col in ["_cleaned_at", "_layer"]:
        if col not in df.columns:
            score -= 10
            issues.append(f"Missing metadata: {col}")

    empty_cols = [c for c in df.columns if df[c].isnull().all()]
    if empty_cols:
        score -= 10 * len(empty_cols)
        issues.append(f"Empty columns: {empty_cols}")

    score = max(0, score)

    return {
        "dataset":    name,
        "score":      score,
        "grade":      "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "F",
        "row_count":  len(df),
        "col_count":  len(df.columns),
        "null_pct":   round(null_pct, 2),
        "dup_pct":    round(dup_pct, 2),
        "issues":     issues,
        "checked_at": datetime.now().isoformat()
    }

if __name__ == "__main__":
    print("=== Data Quality Report ===\n")
    results = []

    for name in DATASETS:
        try:
            result = score_dataset(name)
            results.append(result)
            print(f"{name}")
            print(f"  Score:  {result['score']}/100  (Grade: {result['grade']})")
            print(f"  Rows:   {result['row_count']:,}")
            print(f"  Cols:   {result['col_count']}")
            print(f"  Nulls:  {result['null_pct']}%")
            print(f"  Dupes:  {result['dup_pct']}%")
            print(f"  Issues: {result['issues'] if result['issues'] else 'None'}")
            print()
        except Exception as e:
            print(f"SKIPPED {name}: {e}\n")

    if results:
        write_json(results, "metadata", "quality_scores.json")
        Path("layers/metadata").mkdir(parents=True, exist_ok=True)
        with open("layers/metadata/quality_scores.json", "w") as f:
            json.dump(results, f, indent=2)

        avg = sum(r["score"] for r in results) / len(results)
        print(f"Overall average: {avg:.0f}/100")
        print("Scores saved to MinIO metadata bucket")