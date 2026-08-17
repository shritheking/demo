"""
connectivity_test.py
====================
Safe read-only connectivity test for the Azure worker.

Checks:
  1. .env loaded and all required vars present (key not printed)
  2. Worker ID present
  3. Render /health endpoint reachable (no auth required)
  4. Render API authentication succeeds (GET /jobs/pending)
  5. Queue state reported (empty / N pending jobs)

Does NOT:
  - Call POST /claim (that would lock a job as 'processing')
  - Compile anything
  - Deploy any EX5
  - Touch MT5
  - Create or modify any database record
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Load .env from the windows-worker directory
_WORKER_DIR = Path(__file__).resolve().parent
_ENV_FILE = _WORKER_DIR / ".env"

from dotenv import load_dotenv
load_dotenv(dotenv_path=_ENV_FILE)

import os
import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_BASE_URL: str = os.getenv("API_BASE_URL", "").rstrip("/")
WORKER_API_KEY: str | None = os.getenv("WORKER_API_KEY")
WORKER_ID: str = os.getenv("WORKER_ID", "")

PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "[INFO]"

results: list[tuple[str, str]] = []


def check(label: str, passed: bool, detail: str = "") -> bool:
    mark = PASS if passed else FAIL
    line = f"  {mark}  {label}"
    if detail:
        line += f"  —  {detail}"
    print(line)
    results.append((label, "PASS" if passed else "FAIL"))
    return passed


# ---------------------------------------------------------------------------
# Run checks
# ---------------------------------------------------------------------------

print()
print("=" * 60)
print("AZURE WORKER — CONNECTIVITY TEST (read-only)")
print("=" * 60)
print(f"  .env file : {_ENV_FILE}")
print()

# ── Check 1: API_BASE_URL ────────────────────────────────────────────────────
print("-- Check 1: API_BASE_URL ----------------------------------------")
c1 = check(
    "API_BASE_URL present and non-empty",
    bool(API_BASE_URL),
    API_BASE_URL if API_BASE_URL else "NOT SET",
)

# ── Check 2: WORKER_API_KEY ──────────────────────────────────────────────────
print("-- Check 2: WORKER_API_KEY --------------------------------------")
key_set = bool(WORKER_API_KEY) and WORKER_API_KEY != "CHANGE_ME"
c2 = check(
    "WORKER_API_KEY present (value hidden)",
    key_set,
    "key is set" if key_set else "NOT SET or still 'CHANGE_ME'",
)

# ── Check 3: WORKER_ID ───────────────────────────────────────────────────────
print("-- Check 3: WORKER_ID -------------------------------------------")
c3 = check(
    "WORKER_ID present",
    bool(WORKER_ID),
    WORKER_ID if WORKER_ID else "NOT SET",
)

# ── Check 4: /health (no auth needed) ────────────────────────────────────────
print("-- Check 4: Render /health endpoint -----------------------------")
health_url = f"{API_BASE_URL.rsplit('/api/v1', 1)[0]}/health"
print(f"  {INFO}  GET {health_url}")
try:
    r = requests.get(health_url, timeout=20)
    if r.status_code == 200:
        body = r.json()
        c4 = check(
            "Health endpoint reachable",
            True,
            f"HTTP 200 — {body.get('status', 'ok')} / {body.get('service', '')} v{body.get('version', '')}",
        )
    else:
        c4 = check("Health endpoint reachable", False, f"HTTP {r.status_code}: {r.text[:120]}")
except requests.exceptions.Timeout:
    c4 = check("Health endpoint reachable", False, "Request timed out (20s) — Render may be cold-starting")
except requests.exceptions.ConnectionError as exc:
    c4 = check("Health endpoint reachable", False, f"Connection error: {exc}")
except Exception as exc:
    c4 = check("Health endpoint reachable", False, f"Unexpected error: {exc}")

# ── Check 5: API authentication (GET /jobs/pending — read-only) ───────────────
print("-- Check 5: API authentication (GET /jobs/pending) --------------")
if not key_set:
    check("API authentication", False, "Skipped — WORKER_API_KEY not configured")
    c5 = False
    pending_count = None
else:
    pending_url = f"{API_BASE_URL}/jobs/pending"
    print(f"  {INFO}  GET {pending_url}")
    headers = {"infinity-worker-api-key": WORKER_API_KEY}
    try:
        r = requests.get(pending_url, headers=headers, timeout=20)
        if r.status_code == 200:
            jobs = r.json()
            pending_count = len(jobs) if isinstance(jobs, list) else None
            detail = f"HTTP 200 — {pending_count} pending job(s) in queue" if pending_count is not None else f"HTTP 200 — {r.text[:80]}"
            c5 = check("API authentication succeeded", True, detail)
        elif r.status_code == 401:
            c5 = check("API authentication succeeded", False, "HTTP 401 — WORKER_API_KEY does not match INFINITY_WORKER_API_KEY on Render")
            pending_count = None
        elif r.status_code == 403:
            c5 = check("API authentication succeeded", False, "HTTP 403 — Forbidden")
            pending_count = None
        elif r.status_code >= 500:
            c5 = check("API authentication succeeded", False, f"HTTP {r.status_code} — Render server error (may be cold-starting, retry in ~30s)")
            pending_count = None
        else:
            c5 = check("API authentication succeeded", False, f"HTTP {r.status_code}: {r.text[:120]}")
            pending_count = None
    except requests.exceptions.Timeout:
        c5 = check("API authentication succeeded", False, "Request timed out (20s) — Render may be cold-starting")
        pending_count = None
    except requests.exceptions.ConnectionError as exc:
        c5 = check("API authentication succeeded", False, f"Connection error: {exc}")
        pending_count = None
    except Exception as exc:
        c5 = check("API authentication succeeded", False, f"Unexpected error: {exc}")
        pending_count = None

# ── Check 6: Queue state ─────────────────────────────────────────────────────
print("-- Check 6: Queue state -----------------------------------------")
if c5:
    if pending_count == 0:
        c6 = check("Queue state", True, "status=empty — no pending jobs (worker would sleep and poll again)")
    elif pending_count and pending_count > 0:
        c6 = check("Queue state", True, f"{pending_count} job(s) pending — worker would claim and compile on next poll")
    else:
        c6 = check("Queue state", True, "Queue readable (count unavailable)")
else:
    check("Queue state", False, "Skipped — authentication check failed")
    c6 = False

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print()
print("=" * 60)
print("CONNECTIVITY TEST SUMMARY")
print("=" * 60)
total = len(results)
passed = sum(1 for _, s in results if s == "PASS")
failed = total - passed
for label, status in results:
    mark = PASS if status == "PASS" else FAIL
    print(f"  {mark}  {label}")
print()
print(f"  Result: {passed}/{total} checks passed")
print()
if failed == 0:
    print("[SUCCESS] Worker is connected and authenticated. Ready to poll.")
else:
    print(f"[ATTENTION] {failed} check(s) need attention before starting the worker.")
print()
print("NOTE: No jobs were created or modified. POST /claim was NOT called.")
print("=" * 60)

sys.exit(0 if failed == 0 else 1)
