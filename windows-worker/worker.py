"""
windows-worker/worker.py
========================
Azure Windows compilation worker for the InfinityTrader licensing system.

Job flow (one job at a time):
    1.  Poll Render API: POST /api/v1/jobs/claim
    2.  Receive: job_id, license_id, mt5_id, expiry_date, plan
        compile_ea(mt5_id, expiry_date, plan, license_uuid)                   — compiler/compile.py
    4.  deploy_ex5(ex5_path)                   — compiler/mt5_deploy.py
    5.  Upload EX5:  POST /api/v1/jobs/{id}/upload
    6.  Report failure: POST /api/v1/jobs/{id}/fail  (on any error)
    7.  Continue polling

IMPORTANT:
  - Does NOT enable AutoTrading.
  - Does NOT place trades.
  - Does NOT modify trading account or broker settings.
  - Uses compile_ea() and deploy_ex5() as the single source of truth.
  - Never calls CMD copy / dir for deployment.
  - Never logs API keys, passwords, or credentials.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Bootstrap — must happen before any local imports
# ---------------------------------------------------------------------------

# Load .env from the same directory as this script (absolute, not CWD-relative).
_WORKER_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=_WORKER_DIR / ".env")

# ---------------------------------------------------------------------------
# Configuration (from environment — never hard-coded)
# ---------------------------------------------------------------------------

API_BASE_URL: str = os.getenv(
    "API_BASE_URL", "https://infinity-trader-api.onrender.com/api/v1"
).rstrip("/")

WORKER_API_KEY: str | None = os.getenv("WORKER_API_KEY")
WORKER_ID: str = os.getenv("WORKER_ID", "azure-worker-01")

METAEDITOR_PATH = Path(
    os.getenv("METAEDITOR_PATH", r"C:\Program Files\MetaTrader 5\MetaEditor64.exe")
)

# COMPILER_DIR: absolute path to compiler/ — contains compile.py and mt5_deploy.py
COMPILER_DIR = Path(
    os.getenv("COMPILER_DIR", r"C:\mt5-license-system\compiler")
).resolve()

POLL_INTERVAL: int = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))

# Local copy of the EA source template that compile.py reads from. Synced
# from the backend's active EaTemplate before every job so an admin can
# replace the EA file/version from the web UI without touching this
# machine at all.
EA_TEMPLATE_LOCAL_PATH: Path = _WORKER_DIR / "templates" / "bot.mq5"

# ---------------------------------------------------------------------------
# Logging setup (structured [WORKER] prefix)
# ---------------------------------------------------------------------------

_LOG_DIR = _WORKER_DIR / "logs"
_LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[
        logging.FileHandler(_LOG_DIR / "worker.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
_logger = logging.getLogger(__name__)


def _log(level: str, message: str) -> None:
    """Emit a structured [WORKER] log line without revealing secrets."""
    line = f"[WORKER] [{level}] {message}"
    if level in ("INFO", "SUCCESS"):
        _logger.info(line)
    elif level == "WARNING":
        _logger.warning(line)
    elif level == "ERROR":
        _logger.error(line)
    else:
        _logger.info(line)


# ---------------------------------------------------------------------------
# Add compiler to sys.path so compile_ea / deploy_ex5 can be imported
# ---------------------------------------------------------------------------

if str(COMPILER_DIR) not in sys.path:
    sys.path.insert(0, str(COMPILER_DIR))

# Module-level references populated by _load_compiler_modules()
compile_ea = None
deploy_ex5 = None
discover_mt5_data_folder = None


def _load_compiler_modules() -> None:
    """Import compile_ea and deploy_ex5 from the compiler directory."""
    global compile_ea, deploy_ex5, discover_mt5_data_folder
    try:
        from compile import compile_ea as _cea  # type: ignore[import]
        compile_ea = _cea
    except ImportError as exc:
        raise ImportError(
            f"Cannot import compile_ea from {COMPILER_DIR}: {exc}\n"
            "Ensure COMPILER_DIR in .env points to the compiler/ directory."
        )
    try:
        from mt5_deploy import deploy_ex5 as _dex, discover_mt5_data_folder as _disc  # type: ignore[import]
        deploy_ex5 = _dex
        discover_mt5_data_folder = _disc
    except ImportError as exc:
        raise ImportError(
            f"Cannot import deploy_ex5/discover_mt5_data_folder from {COMPILER_DIR}: {exc}\n"
            "Ensure mt5_deploy.py exists in the compiler/ directory."
        )


# ---------------------------------------------------------------------------
# Startup validation
# ---------------------------------------------------------------------------

def check_prerequisites() -> None:
    """
    Verify all required dependencies before entering the poll loop.
    Raises on first failure rather than silently continuing.
    """
    errors: list[str] = []

    # 1. API configuration
    if not WORKER_API_KEY:
        errors.append("WORKER_API_KEY is not set in .env")
    if not API_BASE_URL:
        errors.append("API_BASE_URL is not set in .env")
    if not WORKER_ID:
        errors.append("WORKER_ID is not set in .env")

    # 2. Python modules
    try:
        _load_compiler_modules()
        _log("INFO", "compile_ea imported successfully")
        _log("INFO", "deploy_ex5 imported successfully")
    except ImportError as exc:
        errors.append(str(exc))

    # 3. MetaEditor executable
    if not METAEDITOR_PATH.exists():
        errors.append(f"MetaEditor not found: {METAEDITOR_PATH}")
    else:
        _log("INFO", f"MetaEditor found: {METAEDITOR_PATH}")

    # 4. MT5 installation discovery
    if discover_mt5_data_folder is not None:
        try:
            mt5_info = discover_mt5_data_folder()
            _log("INFO", f"MT5 instance: {mt5_info['instance_id']}")
            _log("INFO", f"Experts folder: {mt5_info['experts_folder']}")
            if not mt5_info["experts_folder"].is_dir():
                errors.append(
                    f"MQL5\\Experts folder not found: {mt5_info['experts_folder']}"
                )
        except RuntimeError as exc:
            errors.append(f"MT5 data folder not found: {exc}")

    # 5. compiler/ directory exists
    if not COMPILER_DIR.is_dir():
        errors.append(f"COMPILER_DIR does not exist: {COMPILER_DIR}")

    if errors:
        for e in errors:
            _log("ERROR", e)
        raise SystemExit(
            f"[WORKER] Startup failed: {len(errors)} prerequisite(s) missing. "
            "Fix the errors above and restart."
        )

    _log("INFO", "All prerequisites verified")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _headers() -> dict[str, str]:
    """Build auth headers. Never include the key value in any log statement."""
    return {"infinity-worker-api-key": WORKER_API_KEY}  # type: ignore[return-value]


def is_valid_mt5_id(mt5_id: str) -> bool:
    """Alphanumeric + underscore/dash only — prevent path traversal."""
    return bool(re.match(r"^[A-Za-z0-9_-]+$", mt5_id))


def sync_ea_template() -> bool:
    """
    Fetch whichever EA source version the admin currently has active
    (GET /ea-templates/current) and write it over the local
    templates/bot.mq5 that compile.py reads from.

    Non-fatal: if this fails (network hiccup, nothing uploaded yet), we log
    a warning and keep using whatever is already on disk, so a transient
    API issue never blocks compilation outright.

    Returns True if the local template was updated (or already current).
    """
    try:
        resp = requests.get(
            f"{API_BASE_URL}/ea-templates/current",
            headers=_headers(),
            timeout=20,
        )
    except requests.exceptions.RequestException as exc:
        _log("WARNING", f"Could not reach API to sync EA template: {exc}. Using local copy.")
        return False

    if resp.status_code == 404:
        _log("WARNING", "No active EA template configured in admin — using local copy.")
        return False
    if resp.status_code != 200:
        _log("WARNING", f"EA template sync returned HTTP {resp.status_code} — using local copy.")
        return False

    try:
        data = resp.json()
        source_code = data["source_code"]
    except (ValueError, KeyError) as exc:
        _log("WARNING", f"Malformed EA template response: {exc}. Using local copy.")
        return False

    EA_TEMPLATE_LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        current = EA_TEMPLATE_LOCAL_PATH.read_text(encoding="utf-8") if EA_TEMPLATE_LOCAL_PATH.exists() else None
    except Exception:
        current = None

    if current == source_code:
        return True  # already up to date, nothing to write

    EA_TEMPLATE_LOCAL_PATH.write_text(source_code, encoding="utf-8")
    _log(
        "INFO",
        f"EA template synced: version={data.get('version_label') or data.get('id')} "
        f"filename={data.get('filename')} ({len(source_code)} bytes)",
    )
    return True


def _report_failure(job_id: int, error_message: str) -> None:
    """
    Report a job failure to the Render API.
    Never includes secrets in the payload.
    """
    try:
        resp = requests.post(
            f"{API_BASE_URL}/jobs/{job_id}/fail",
            json={"worker_id": WORKER_ID, "error_message": error_message},
            headers=_headers(),
            timeout=15,
        )
        if resp.status_code == 200:
            _log("INFO", f"Failure reported to API for job {job_id}")
        else:
            _log("WARNING", f"API returned {resp.status_code} when reporting failure for job {job_id}")
    except Exception as exc:
        _log("ERROR", f"Could not report failure for job {job_id} to API: {exc}")


# ---------------------------------------------------------------------------
# Job processor
# ---------------------------------------------------------------------------

def process_job(
    job_id: int,
    mt5_id: str,
    expiry_date: str,
    plan: str,
    license_uuid: str = "",
) -> None:
    """
    Process one compilation job end-to-end:

        compile_ea(mt5_id, expiry_date, plan, license_uuid)
            → deploy_ex5(ex5_path)
            → POST /jobs/{job_id}/upload

    On any failure, reports to the API and returns so the poll loop continues.
    """
    _log("INFO", f"Job claimed: {job_id}")
    _log("INFO", f"MT5 ID: {mt5_id} | Expiry: {expiry_date} | Plan: {plan}")

    # ── Validate inputs ──────────────────────────────────────────────────────
    if not is_valid_mt5_id(mt5_id):
        _log("ERROR", f"Invalid MT5 ID format for job {job_id}: {mt5_id!r}")
        _report_failure(job_id, "Invalid MT5 ID format")
        return

    # expiry_date of None means Lifetime license (no expiry)
    if expiry_date is None or str(expiry_date).lower() in ("", "none", "lifetime"):
        expiry_date = "lifetime"
        _log("INFO", f"Job {job_id}: expiry_date is None/empty — treating as LIFETIME license")

    if not plan:
        _log("WARNING", f"No plan in job payload for job {job_id} — defaulting to 'standard'")
        plan = "standard"

    # ── Step 0: Sync EA template ─────────────────────────────────────────────
    # Always pull the currently-active EA source before compiling so an
    # admin-side upload/replace takes effect on the very next job.
    sync_ea_template()

    # ── Step 1: Compile ───────────────────────────────────────────────────────
    _log("INFO", "Compilation started")
    ex5_path_str: str | None = None
    try:
        ex5_path_str = compile_ea(mt5_id, expiry_date, plan, license_uuid)
    except Exception as exc:
        _log("ERROR", f"MQ5 compilation failed for job {job_id}: {exc}")
        _report_failure(job_id, f"Compilation failed: {exc}")
        return

    ex5_path = Path(ex5_path_str).resolve()

    if not ex5_path.exists() or not ex5_path.is_file():
        _log("ERROR", f"EX5 was not generated for job {job_id}: {ex5_path}")
        _report_failure(job_id, f"EX5 file not found after compilation: {ex5_path}")
        return

    ex5_size = ex5_path.stat().st_size
    if ex5_size == 0:
        _log("ERROR", f"EX5 is empty (0 bytes) for job {job_id}: {ex5_path}")
        _report_failure(job_id, "EX5 file is empty after compilation")
        return

    _log("INFO", "Compilation successful")
    _log("INFO", f"EX5 generated: {ex5_path} ({ex5_size} bytes)")

    # ── Step 2: Deploy to MT5 Experts folder ─────────────────────────────────
    _log("INFO", "MT5 deployment started")
    try:
        deploy_result = deploy_ex5(ex5_path)
    except Exception as exc:
        _log("ERROR", f"deploy_ex5() raised an exception for job {job_id}: {exc}")
        _report_failure(job_id, f"MT5 deployment exception: {exc}")
        return

    if not deploy_result.get("success"):
        err = deploy_result.get("error", "Unknown deployment error")
        _log("ERROR", f"MT5 deployment failed for job {job_id}: {err}")
        _report_failure(job_id, f"MT5 deployment failed: {err}")
        return

    _log("INFO", "MT5 deployment successful")
    _log("INFO", f"Deployed to: {deploy_result['destination']}")
    _log("INFO", f"Size: {deploy_result['size']} bytes | SHA-256 match: {deploy_result['hash_match']}")

    # ── Step 3: Upload EX5 to Render/Supabase ────────────────────────────────
    _log("INFO", "Upload started")
    upload_filename = f"InfinityTrader_{mt5_id}.ex5"

    try:
        with ex5_path.open("rb") as fh:
            files = {
                "file": (upload_filename, fh, "application/octet-stream")
            }
            upload_resp = requests.post(
                f"{API_BASE_URL}/jobs/{job_id}/upload",
                files=files,
                headers=_headers(),
                timeout=60,
            )
    except requests.exceptions.Timeout:
        _log("ERROR", f"Upload timed out for job {job_id}")
        _report_failure(job_id, "Upload timed out")
        return
    except Exception as exc:
        _log("ERROR", f"Upload request failed for job {job_id}: {exc}")
        _report_failure(job_id, f"Upload request error: {exc}")
        return

    if upload_resp.status_code == 200:
        _log("INFO", "Upload successful")
        _log("SUCCESS", f"Job completed: {job_id}")
    else:
        _log("ERROR", f"Upload failed for job {job_id}: HTTP {upload_resp.status_code}")
        _log("ERROR", f"Response: {upload_resp.text[:300]}")
        _report_failure(
            job_id,
            f"Upload failed: HTTP {upload_resp.status_code} — {upload_resp.text[:200]}",
        )


# ---------------------------------------------------------------------------
# Poll loop
# ---------------------------------------------------------------------------

def run_worker() -> None:
    """Main poll loop. Runs indefinitely until the process is killed."""
    _log("INFO", "Starting")
    _log("INFO", f"Worker ID      : {WORKER_ID}")
    _log("INFO", f"API base URL   : {API_BASE_URL}")
    _log("INFO", f"Compiler dir   : {COMPILER_DIR}")
    _log("INFO", f"MetaEditor     : {METAEDITOR_PATH}")
    _log("INFO", f"Poll interval  : {POLL_INTERVAL}s")

    try:
        check_prerequisites()
    except SystemExit:
        raise
    except Exception as exc:
        _log("ERROR", f"Startup validation failed: {exc}")
        raise SystemExit(1)

    # Test API connectivity once at startup (non-fatal if Render is cold-starting)
    try:
        resp = requests.get(
            f"{API_BASE_URL}/jobs/pending",
            headers=_headers(),
            timeout=15,
        )
        if resp.status_code == 200:
            _log("INFO", "API connected")
        elif resp.status_code == 401:
            _log("ERROR", "API authentication failed — check WORKER_API_KEY matches INFINITY_WORKER_API_KEY on Render")
            raise SystemExit(1)
        else:
            _log("WARNING", f"API connectivity check returned HTTP {resp.status_code} — will retry in poll loop")
    except requests.exceptions.RequestException as exc:
        _log("WARNING", f"Initial API connectivity check failed (Render may be cold-starting): {exc}")

    # Pull the latest EA template once at startup too, so logs make it
    # obvious which version is loaded before the first job even arrives.
    sync_ea_template()

    _log("INFO", "Polling for jobs")

    while True:
        try:
            # ── Claim a job ──────────────────────────────────────────────────
            resp = requests.post(
                f"{API_BASE_URL}/jobs/claim",
                json={"worker_id": WORKER_ID},
                headers=_headers(),
                timeout=20,
            )

            if resp.status_code == 401:
                _log("ERROR", "Authentication failed — check WORKER_API_KEY. Sleeping 60s.")
                time.sleep(60)
                continue

            if resp.status_code == 429:
                _log("WARNING", "Rate limited by API (429). Sleeping 30s.")
                time.sleep(30)
                continue

            if resp.status_code >= 500:
                _log("WARNING", f"API server error {resp.status_code} (Render may be cold-starting). Sleeping 30s.")
                time.sleep(30)
                continue

            if resp.status_code != 200:
                _log("WARNING", f"Unexpected API response {resp.status_code}: {resp.text[:200]}. Sleeping {POLL_INTERVAL}s.")
                time.sleep(POLL_INTERVAL)
                continue

            data = resp.json()

            if data.get("status") == "empty":
                # No pending jobs — normal, keep polling silently
                time.sleep(POLL_INTERVAL)
                continue

            if data.get("status") != "success":
                _log("WARNING", f"Unexpected claim response: {data}. Sleeping {POLL_INTERVAL}s.")
                time.sleep(POLL_INTERVAL)
                continue

            # ── Extract job fields ───────────────────────────────────────────
            job = data.get("job", {})
            job_id   = job.get("job_id")
            mt5_id   = job.get("mt5_id")
            expiry   = job.get("expiry_date")
            plan     = job.get("plan", "standard")
            license_uuid = job.get("license_uuid", "")

            if not job_id or not mt5_id:
                _log("ERROR", f"Malformed job payload (missing job_id or mt5_id): {job}")
                time.sleep(POLL_INTERVAL)
                continue

            # expiry of None means Lifetime license
            if expiry is None:
                expiry = "lifetime"
                _log("INFO", f"Job {job_id}: expiry_date is None — treating as LIFETIME license")

            # ── Process ──────────────────────────────────────────────
            process_job(
                job_id=int(job_id),
                mt5_id=str(mt5_id),
                expiry_date=str(expiry),
                plan=str(plan),
                license_uuid=str(license_uuid or ""),
            )

        except requests.exceptions.ConnectionError as exc:
            _log("WARNING", f"Connection error while polling (network/Render cold start): {exc}. Sleeping {POLL_INTERVAL}s.")
        except requests.exceptions.Timeout:
            _log("WARNING", f"Request timed out while polling. Sleeping {POLL_INTERVAL}s.")
        except requests.exceptions.RequestException as exc:
            _log("ERROR", f"Request error: {exc}. Sleeping {POLL_INTERVAL}s.")
        except Exception as exc:
            _log("ERROR", f"Unexpected error in poll loop: {exc}. Sleeping {POLL_INTERVAL}s.")

        time.sleep(POLL_INTERVAL)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        run_worker()
    except SystemExit:
        raise
    except KeyboardInterrupt:
        _log("INFO", "Worker stopped by user (KeyboardInterrupt)")
        sys.exit(0)
