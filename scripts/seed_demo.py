#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed demo transactions into TrustiPay Analytics API.")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8005",
        help="API base URL (default: http://127.0.0.1:8005)",
    )
    parser.add_argument(
        "--payload",
        default="sample_data/demo_ingest.json",
        help="Path to ingest payload JSON file",
    )
    parser.add_argument(
        "--ingest-key",
        default=None,
        help="Ingestion key (defaults to INGEST_KEY env var)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ingest_key = args.ingest_key or os.getenv("INGEST_KEY")
    if not ingest_key:
        print("INGEST_KEY is required. Provide --ingest-key or set INGEST_KEY in your environment.")
        return 1

    payload_path = Path(args.payload)
    if not payload_path.exists():
        print(f"Payload file not found: {payload_path}")
        return 1

    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    url = f"{args.base_url.rstrip('/')}/v1/ingest/transactions"
    headers = {"X-INGEST-KEY": ingest_key, "Content-Type": "application/json"}

    response = requests.post(url, json=payload, headers=headers, timeout=30)
    print(f"POST {url} -> {response.status_code}")

    try:
        body = response.json()
    except Exception:
        print(response.text)
        return 1

    print(json.dumps(body, indent=2))
    return 0 if response.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
