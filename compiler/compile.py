"""
compile.py
==========
MT5 MQ5 → EX5 compiler for the InfinityTrader licensing system.

Generates a licensed EA by:
    1. Reading bot.mq5 template.
    2. Injecting MT5_ID, EXPIRY (normalized to YYYY-MM-DD), and PLAN.
    3. Writing a named .mq5 to the output directory.
    4. Invoking MetaEditor64.exe to compile it to .ex5.

Does NOT enable AutoTrading, place trades, or modify account settings.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Paths — always absolute, built with pathlib
# ---------------------------------------------------------------------------
METAEDITOR = Path(r"C:\Program Files\MetaTrader 5\MetaEditor64.exe")

BASE_DIR    = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
OUTPUT_DIR   = BASE_DIR / "output"


# ---------------------------------------------------------------------------
# Structured logger
# ---------------------------------------------------------------------------
def _log(level: str, message: str) -> None:
    """Emit a structured log line to stdout."""
    print(f"[{level}] {message}")


# ---------------------------------------------------------------------------
# Expiry normalisation
# ---------------------------------------------------------------------------
def normalize_expiry(expiry: str) -> str:
    """
    Normalize an expiry date string to ISO 8601 YYYY-MM-DD format.

    Handles malformed inputs produced by the legacy code:

        "2026-1-2-31"  →  "2026-12-31"

    The erroneous 4-part format arises when a two-digit month such as "12"
    is inadvertently split into two separate tokens "1" and "2" before being
    joined with dashes.  This function detects that pattern by concatenating
    the two middle tokens and re-parsing as a valid date.

    Accepted input formats (in priority order):
        YYYY-MM-DD              standard ISO — returned as-is after validation
        YYYY-M-D                single-digit month/day — zero-padded
        YYYY-P1-P2-DD           4-part: P1+P2 concatenated form the month

    Args:
        expiry: Raw expiry string from the job payload.

    Returns:
        Normalized string in "YYYY-MM-DD" format.

    Raises:
        ValueError: If the string cannot be parsed into a valid calendar date.
    """
    expiry = expiry.strip()

    # ── Lifetime license — no expiry date ────────────────────────────────────
    if expiry.lower() in ("lifetime", "none", ""):
        _log("INFO", "Expiry is LIFETIME — no expiry date will be embedded")
        return "lifetime"

    # ── Attempt 1: standard YYYY-MM-DD (also handles YYYY-M-D via %Y-%m-%d) ─
    for fmt in ("%Y-%m-%d",):
        try:
            dt = datetime.strptime(expiry, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # ── Attempt 2: 4-part format YYYY-P1-P2-DD ──────────────────────────────
    #   Example: "2026-1-2-31"
    #     parts  = ["2026", "1", "2", "31"]
    #     month  = "1" + "2" = "12"   (December)
    #     result = "2026-12-31"
    parts = expiry.split("-")
    if len(parts) == 4:
        year_str, p1, p2, day_str = parts
        month_str = p1 + p2  # concatenate the two middle tokens
        try:
            year  = int(year_str)
            month = int(month_str)
            day   = int(day_str)
            dt = datetime(year, month, day)
            normalized = dt.strftime("%Y-%m-%d")
            _log("INFO",
                 f"Expiry normalized: {expiry!r} → {normalized!r}  "
                 f"(4-part format detected; month reconstructed from '{p1}'+'{p2}')")
            return normalized
        except (ValueError, TypeError):
            pass  # Fall through to raise

    raise ValueError(
        f"Cannot normalize expiry date: {expiry!r}\n"
        "  Supported formats: YYYY-MM-DD, YYYY-M-D, or YYYY-P1-P2-DD\n"
        "  Example of YYYY-P1-P2-DD: '2026-1-2-31'  →  '2026-12-31'"
    )


# ---------------------------------------------------------------------------
# Compiler
# ---------------------------------------------------------------------------
def compile_ea(mt5_id: str, expiry: str, plan: str, license_uuid: str = "") -> str:
    """
    Compile an InfinityTrader EA from the bot.mq5 template.

    Licensing tokens injected into the compiled EA:
        {{MT5_ID}}       →  mt5_id        (e.g. "TEST001")
        {{EXPIRY}}       →  expiry, normalized to YYYY-MM-DD
        {{PLAN}}         →  plan          (e.g. "premium")
        {{LICENSE_UUID}} →  license_uuid  (used for the server-side revocation check)
        {{API_BASE_URL}} →  API_BASE_URL env var, or the production API as a fallback

    Args:
        mt5_id: Customer MT5 account ID.
        expiry: License expiry date (any supported format — will be normalized).
        plan:   License plan name.
        license_uuid: The license's unique token, used by the compiled EA to
            call the /api/v1/licenses/status/{license_uuid} heartbeat endpoint.
            Optional so existing callers that don't pass it still work; the
            resulting EA just won't have server-side revocation, only the
            local account/expiry check.

    Returns:
        Absolute path string to the generated .ex5 file.

    Raises:
        FileNotFoundError: If MetaEditor or the template is missing.
        ValueError:        If the expiry date cannot be normalized.
        RuntimeError:      If MetaEditor does not produce an EX5 file.
    """
    _log("INFO", "Starting compilation")
    _log("INFO", f"Source MQ5 template : {TEMPLATE_DIR / 'bot.mq5'}")
    _log("INFO", f"MT5 ID              : {mt5_id}")
    _log("INFO", f"Plan                : {plan}")
    _log("INFO", f"Expiry (raw)        : {expiry!r}")

    # ── Normalize expiry ─────────────────────────────────────────────────────
    try:
        normalized_expiry = normalize_expiry(expiry)
    except ValueError as exc:
        _log("ERROR", f"MQ5 compilation failed — invalid expiry: {exc}")
        raise

    _log("INFO", f"Expiry (normalized) : {normalized_expiry}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    template_path = TEMPLATE_DIR / "bot.mq5"

    if not METAEDITOR.exists():
        _log("ERROR", f"MQ5 compilation failed — MetaEditor not found: {METAEDITOR}")
        raise FileNotFoundError(f"MetaEditor not found: {METAEDITOR}")

    if not template_path.exists():
        _log("ERROR", f"MQ5 compilation failed — template not found: {template_path}")
        raise FileNotFoundError(f"EA template not found: {template_path}")

    # ── Build output file names ───────────────────────────────────────────────
    # For lifetime licenses, use "lifetime" in the filename instead of a date
    file_label = normalized_expiry  # either "YYYY-MM-DD" or "lifetime"
    output_name = f"InfinityTrader_{mt5_id}_{file_label}.ex5"
    source_name = f"InfinityTrader_{mt5_id}_{file_label}.mq5"

    source_path = OUTPUT_DIR / source_name
    ex5_path    = OUTPUT_DIR / output_name

    _log("INFO", f"Output MQ5 : {source_path}")
    _log("INFO", f"Output EX5 : {ex5_path}")

    # ── Read and patch template ──────────────────────────────────────────────
    source_code = template_path.read_text(encoding="utf-8")
    source_code = source_code.replace("{{MT5_ID}}", str(mt5_id))
    source_code = source_code.replace("{{EXPIRY}}", normalized_expiry)
    source_code = source_code.replace("{{PLAN}}",   str(plan))
    source_code = source_code.replace("{{LICENSE_UUID}}", str(license_uuid or ""))

    api_base_url = os.getenv("API_BASE_URL", "https://infinity-trader-api.onrender.com/api/v1")
    source_code = source_code.replace("{{API_BASE_URL}}", api_base_url)

    source_path.write_text(source_code, encoding="utf-8")

    # ── Remove stale EX5 so we can detect fresh compilation ─────────────────
    if ex5_path.exists():
        ex5_path.unlink()

    # ── Invoke MetaEditor ────────────────────────────────────────────────────
    command = [str(METAEDITOR), f"/compile:{source_path}", "/log"]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=120,
    )

    # ── Validate EX5 was produced ────────────────────────────────────────────
    if not ex5_path.exists():
        _log("ERROR", "EX5 was not generated — MetaEditor did not produce the expected file")
        _log("ERROR", f"  MQ5          : {source_path}")
        _log("ERROR", f"  Return code  : {result.returncode}")
        if result.stdout:
            _log("ERROR", f"  STDOUT       : {result.stdout[:500]}")
        if result.stderr:
            _log("ERROR", f"  STDERR       : {result.stderr[:500]}")
        raise RuntimeError(
            "MetaEditor did not produce the expected EX5 file.\n"
            f"MQ5: {source_path}\n"
            f"Return code: {result.returncode}\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )

    ex5_size = ex5_path.stat().st_size
    _log("INFO",  "Compilation successful")
    _log("INFO",  f"EX5 generated : {ex5_path}")
    _log("INFO",  f"EX5 size      : {ex5_size} bytes")

    return str(ex5_path)