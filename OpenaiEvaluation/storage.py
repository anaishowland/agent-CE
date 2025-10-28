from __future__ import annotations

"""Storage helpers: write local result.json and optional GCS upload."""

import json
import os
from typing import Any, Dict
import logging
import time


def write_result_local(result_obj: Dict[str, Any], target_dir: str) -> str:
    os.makedirs(target_dir, exist_ok=True)
    dest = os.path.join(target_dir, "result.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(result_obj, f, indent=2, ensure_ascii=False)
    try:
        logging.info("[LOCAL] wrote result.json at %s", dest)
    except Exception:
        pass
    # Optional debug copy in ./debug-runs for quick access
    try:
        dbg_dir = os.path.join("debug-runs")
        os.makedirs(dbg_dir, exist_ok=True)
        ts = time.strftime("%Y%m%d-%H%M%S")
        job_id = str(result_obj.get("jobId", "job")).replace("/", "-")
        task_id = str((result_obj.get("task") or {}).get("taskId", "task"))
        dbg_name = f"{job_id}_{task_id}_{ts}.result.json"
        dbg_path = os.path.join(dbg_dir, dbg_name)
        with open(dbg_path, "w", encoding="utf-8") as df:
            json.dump(result_obj, df, indent=2, ensure_ascii=False)
        logging.info("[LOCAL] debug copy at %s", dbg_path)
    except Exception:
        pass
    return dest


def upload_artifacts_to_gcs(
    local_dir: str,
    user_id: str,
    job_id: str,
    episode: str | int,
    task_id: str | int,
) -> None:
    try:
        from google.cloud import storage  # type: ignore
    except Exception:
        return
    bucket_name = os.getenv("BUCKET_NAME") or os.getenv("GCS_BUCKET_NAME")
    if not bucket_name:
        return
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    prefix = f"{user_id}/{job_id}/{episode}/{task_id}"
    for fname in os.listdir(local_dir):
        local_path = os.path.join(local_dir, fname)
        if not os.path.isfile(local_path):
            continue
        if not (fname.endswith(".png") or fname.endswith(".json") or fname.endswith(".zst")):
            continue
        bucket.blob(f"{prefix}/{fname}").upload_from_filename(local_path)


