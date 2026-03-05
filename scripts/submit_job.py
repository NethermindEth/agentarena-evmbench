#!/usr/bin/env python3
"""Submit a zip file to evmbench and wait for the result.

Usage:
    python scripts/submit_job.py \
        --url https://domain:port \
        --model claude-opus-4.5 \
        --api-key sk-ant-... \
        --zip path/to/contracts.zip

The script retries automatically if a job fails.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

POLL_INTERVAL = 1       # seconds between status polls
RETRY_DELAY = 3         # seconds to wait before retrying after a failed job
TERMINAL_STATUSES = {"succeeded", "failed"}


def start_job(base_url: str, model: str, api_key: str, zip_path: Path) -> str:
    url = f"{base_url}/v1/jobs/start"
    with zip_path.open("rb") as fh:
        try:
            resp = requests.post(
                url,
                files={"file": (zip_path.name, fh, "application/zip")},
                data={"model": model, "api_key": api_key},
                timeout=30,
            )
        except requests.ConnectionError as exc:
            sys.exit(f"Server not available: {exc}")

    if not resp.ok:
        sys.exit(f"Failed to start job ({resp.status_code}): {resp.text}")

    body = resp.json()
    job_id: str = body["job_id"]
    print(f"Job created: {job_id} (status={body['status']})")
    return job_id


def poll_job(base_url: str, job_id: str) -> dict:
    url = f"{base_url}/v1/jobs/{job_id}"
    while True:
        try:
            resp = requests.get(url, timeout=30)
        except requests.ConnectionError as exc:
            sys.exit(f"Server not available while polling: {exc}")

        if not resp.ok:
            sys.exit(f"Error polling job ({resp.status_code}): {resp.text}")

        body = resp.json()
        status: str = body["status"]
        print(f"  status={status}", flush=True)

        if status in TERMINAL_STATUSES:
            return body

        time.sleep(POLL_INTERVAL)


def run(base_url: str, model: str, api_key: str, zip_path: Path) -> dict:
    attempt = 0
    while True:
        attempt += 1
        print(f"\n[Attempt {attempt}] Starting job...")
        job_id = start_job(base_url, model, api_key, zip_path)
        result = poll_job(base_url, job_id)

        if result["status"] == "succeeded":
            return result

        print(f"Job failed. Retrying in {RETRY_DELAY}s...")
        time.sleep(RETRY_DELAY)


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit a job to evmbench and wait for the result.")
    parser.add_argument("--url", required=True, help="Base URL of the evmbench API (e.g. https://domain:port)")
    parser.add_argument("--model", required=True, help="Model to use (e.g. claude-opus-4.5)")
    parser.add_argument("--api-key", required=True, dest="api_key", help="API key for the chosen model")
    parser.add_argument("--zip", required=True, dest="zip_file", help="Path to the .zip file to submit")
    args = parser.parse_args()

    zip_path = Path(args.zip_file)
    if not zip_path.is_file():
        sys.exit(f"File not found: {zip_path}")
    if zip_path.suffix.lower() != ".zip":
        sys.exit(f"Expected a .zip file, got: {zip_path.name}")

    base_url = args.url.rstrip("/")

    result = run(base_url, args.model, args.api_key, zip_path)
    print("\n=== Result ===")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
