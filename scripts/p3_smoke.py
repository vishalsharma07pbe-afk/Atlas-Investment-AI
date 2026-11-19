#!/usr/bin/env python3
"""Bounded HTTP readiness and load smoke check for an operator-controlled ATLAS URL."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


ALLOWED_HOSTS = {"127.0.0.1", "localhost"}


def validate_base_url(value: str, allow_remote: bool = False) -> str:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
        raise ValueError("BASE_URL_MUST_BE_HTTP_OR_HTTPS")
    if not allow_remote and parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError("REMOTE_TARGET_REQUIRES_EXPLICIT_ALLOW_REMOTE")
    if parsed.query or parsed.fragment:
        raise ValueError("BASE_URL_MUST_NOT_HAVE_QUERY_OR_FRAGMENT")
    return value.rstrip("/")


def request_once(url: str, timeout: float) -> tuple[bool, float, int]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = response.read(1_000_000)
            ok = 200 <= response.status < 300 and bool(payload)
            status = response.status
    except (urllib.error.URLError, TimeoutError, ValueError):
        ok, status = False, 0
    return ok, (time.perf_counter() - started) * 1000, status


def run(base_url: str, requests: int, concurrency: int, timeout: float,
        p95_limit_ms: float, error_rate_limit: float) -> dict:
    if not 1 <= requests <= 10_000 or not 1 <= concurrency <= 100:
        raise ValueError("LOAD_LIMIT_OUT_OF_RANGE")
    target = base_url + "/healthz"
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(lambda _: request_once(target, timeout), range(requests)))
    latencies = sorted(row[1] for row in results)
    successes = sum(1 for row in results if row[0])
    p95_index = max(0, min(len(latencies) - 1, round(len(latencies) * .95) - 1))
    p95 = latencies[p95_index]
    error_rate = (requests - successes) / requests * 100
    passed = error_rate <= error_rate_limit and p95 <= p95_limit_ms
    return {
        "status": "PASS" if passed else "FAIL", "target": target,
        "requests": requests, "concurrency": concurrency, "successes": successes,
        "error_rate_percent": round(error_rate, 3),
        "latency_ms": {"mean": round(statistics.mean(latencies), 3),
                       "p95": round(p95, 3), "max": round(max(latencies), 3)},
        "thresholds": {"p95_ms": p95_limit_ms,
                       "error_rate_percent": error_rate_limit},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8088")
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=5)
    parser.add_argument("--p95-ms", type=float, default=750)
    parser.add_argument("--max-error-rate", type=float, default=1)
    parser.add_argument("--allow-remote", action="store_true")
    args = parser.parse_args()
    try:
        base = validate_base_url(args.base_url, args.allow_remote)
        result = run(base, args.requests, args.concurrency, args.timeout,
                     args.p95_ms, args.max_error_rate)
    except ValueError as exc:
        print(json.dumps({"status": "ERROR", "code": str(exc)}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
