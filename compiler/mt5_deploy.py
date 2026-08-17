"""
mt5_deploy.py
=============
MT5 terminal data-folder discovery and EX5 deployment module.

Provides two public functions:

    discover_mt5_data_folder()  →  dict
    deploy_ex5(ex5_path, experts_dir_override=None)  →  dict

Design constraints:
  - Uses pathlib.Path throughout — no string-concatenation path building.
  - Uses shutil.copy2() for file copy — no CMD copy / xcopy.
  - Uses Path.exists() + Path.stat() for verification — no CMD dir.
  - Uses hashlib.sha256() for integrity verification.
  - Never hard-codes a terminal instance ID.
  - Does NOT enable AutoTrading, open trades, or modify account settings.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
_logger = logging.getLogger(__name__)


def _log(level: str, message: str) -> None:
    """Emit a structured log line to both stdout and the Python logger."""
    print(f"[{level}] {message}")
    if level in ("INFO", "SUCCESS"):
        _logger.info(message)
    elif level == "WARNING":
        _logger.warning(message)
    elif level == "ERROR":
        _logger.error(message)


# ---------------------------------------------------------------------------
# Constants — only the *root* is referenced; instance IDs are discovered.
# ---------------------------------------------------------------------------
_METAQUOTES_ROOT = Path(r"C:\Users\infinityadmin\AppData\Roaming\MetaQuotes\Terminal")

# Known valid MT5 installation paths for origin.txt cross-referencing.
_KNOWN_MT5_INSTALLS: list[Path] = [
    Path(r"C:\Program Files\MetaTrader 5"),
    Path(r"C:\Program Files (x86)\MetaTrader 5"),
]

# Folder names inside the MetaQuotes\Terminal root that are NOT instance IDs.
_NON_INSTANCE_FOLDERS: frozenset[str] = frozenset({"Common", "Community"})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sha256_file(path: Path) -> str:
    """Return the lowercase hex SHA-256 digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65_536), b""):
            h.update(chunk)
    return h.hexdigest()


def _score_instance(candidate: Path) -> Optional[tuple]:
    """
    Score a MetaQuotes Terminal instance directory.

    Scoring (additive):
        +30  origin.txt references a known MT5 install path
        +10  origin.txt is present (even if path unknown)
        +15  InfinityTrader*.ex5 already exists in MQL5\\Experts
          0  mtime used as a float tiebreaker (appended to tuple)

    Returns:
        None                         — not a valid MT5 instance
        (score, mtime_float,
         instance_id, data_folder,
         experts_folder)             — valid instance, ready to sort
    """
    if not candidate.is_dir():
        return None
    if candidate.name in _NON_INSTANCE_FOLDERS:
        return None

    experts_folder = candidate / "MQL5" / "Experts"
    if not experts_folder.is_dir():
        # MQL5\Experts is a hard requirement.
        return None

    score = 0

    # ── origin.txt ──────────────────────────────────────────────────────────
    origin_file = candidate / "origin.txt"
    if origin_file.is_file():
        score += 10
        try:
            # MT5 writes origin.txt as UTF-16 with BOM.
            origin_text = origin_file.read_text(encoding="utf-16", errors="ignore").strip()
            origin_path = Path(origin_text)
            for known in _KNOWN_MT5_INSTALLS:
                # Case-insensitive comparison for Windows paths.
                if origin_path.resolve() == known.resolve():
                    score += 30
                    break
                if str(origin_path).lower() == str(known).lower():
                    score += 30
                    break
        except Exception:
            pass  # Malformed origin.txt — still give the base +10

    # ── InfinityTrader EA already deployed ──────────────────────────────────
    try:
        if any(experts_folder.glob("InfinityTrader*.ex5")):
            score += 15
    except Exception:
        pass

    # ── Modification time (tiebreaker) ──────────────────────────────────────
    try:
        mtime = candidate.stat().st_mtime
    except Exception:
        mtime = 0.0

    return (score, mtime, candidate.name, candidate, experts_folder)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def discover_mt5_data_folder(
    metaquotes_root: Optional[Path] = None,
) -> dict:
    """
    Automatically discover the active/valid MT5 terminal data folder.

    Algorithm:
        1. Enumerate all subdirectories of MetaQuotes\\Terminal.
        2. Skip 'Common' and 'Community' (not instance folders).
        3. Require MQL5\\Experts to exist (hard filter).
        4. Score remaining candidates:
             - origin.txt pointing to a known MT5 install  → +30
             - origin.txt present (any content)            → +10
             - InfinityTrader*.ex5 in MQL5\\Experts        → +15
             - most-recently-modified instance             → tiebreaker
        5. Select the highest-scored instance.

    Returns:
        {
            "data_folder"   : Path  — absolute path to terminal instance dir
            "experts_folder": Path  — absolute path to MQL5\\Experts
            "instance_id"   : str   — the instance folder name (UUID-like)
            "origin"        : str   — content of origin.txt, or ""
        }

    Raises:
        RuntimeError  — if MetaQuotes root is missing or no valid instance found.
    """
    root = Path(metaquotes_root) if metaquotes_root else _METAQUOTES_ROOT

    _log("INFO", f"Discovering MT5 data folder under: {root}")

    if not root.is_dir():
        raise RuntimeError(
            f"[ERROR] MetaQuotes Terminal root not found: {root}\n"
            "Ensure MetaTrader 5 is installed and has been run at least once."
        )

    candidates: list[tuple] = []
    examined: list[str] = []

    for entry in root.iterdir():
        examined.append(entry.name)
        result = _score_instance(entry)
        if result is not None:
            candidates.append(result)

    _log("INFO", f"Examined folders: {examined}")
    _log("INFO", f"Valid MT5 instances found: {len(candidates)}")

    if not candidates:
        raise RuntimeError(
            f"No valid MT5 terminal instance found under: {root}\n"
            "Expected at least one instance folder containing MQL5\\Experts."
        )

    # Sort: primary = score descending, secondary = mtime descending.
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)

    if len(candidates) > 1:
        _log("INFO", f"{len(candidates)} instances found — selecting highest-scored.")
        for c in candidates:
            _log("INFO", f"  Instance {c[2]}  score={c[0]}")

    best = candidates[0]
    score, mtime, instance_id, data_folder, experts_folder = best

    # Read origin.txt for reporting (already parsed during scoring).
    origin_content = ""
    origin_file = data_folder / "origin.txt"
    if origin_file.is_file():
        try:
            # MT5 writes origin.txt as UTF-16 with BOM.
            origin_content = origin_file.read_text(encoding="utf-16", errors="ignore").strip()
        except Exception:
            pass

    _log("INFO", f"Selected MT5 instance: {instance_id}  (score={score})")
    _log("INFO", f"MT5 data folder  : {data_folder}")
    _log("INFO", f"Experts folder   : {experts_folder}")
    if origin_content:
        _log("INFO", f"origin.txt points to MT5 install: {origin_content}")

    return {
        "data_folder": data_folder.resolve(),
        "experts_folder": experts_folder.resolve(),
        "instance_id": instance_id,
        "origin": origin_content,
    }


def deploy_ex5(
    ex5_path,
    experts_dir_override: Optional[Path] = None,
) -> dict:
    """
    Deploy an EX5 file to the MT5 MQL5\\Experts directory.

    Workflow (in order — every step must pass before the next runs):
        1.  Resolve source to an absolute Path.
        2.  Verify source exists.
        3.  Verify source is a regular file.
        4.  Read source file size via Path.stat() — must be > 0.
        5.  Discover MT5 data folder (or use experts_dir_override).
        6.  Create Experts directory if it does not yet exist.
        7.  Resolve absolute destination path.
        8.  Record whether destination file already exists (overwrite flag).
        9.  Compute source SHA-256 before copying.
        10. Copy with shutil.copy2().
        11. Verify destination exists via Path.exists().
        12. Verify destination is a regular file via Path.is_file().
        13. Read destination file size via Path.stat().
        14. Compare source and destination file sizes.
        15. Compute destination SHA-256.
        16. Compare source and destination SHA-256 hashes.
        17. Return structured success result.

    Args:
        ex5_path: Path-like or str pointing to the source EX5 file.
        experts_dir_override: Optional Path to override the discovered
            MQL5\\Experts directory (useful for testing).

    Returns:
        {
            "success"           : bool
            "source"            : str   — absolute source path
            "destination"       : str   — absolute destination path
            "size"              : int   — verified file size in bytes
            "source_sha256"     : str   — hex SHA-256 of source
            "destination_sha256": str   — hex SHA-256 of destination
            "hash_match"        : bool
            "verified"          : bool  — True only if ALL checks passed
            "overwritten"       : bool  — True if destination existed before copy
            "error"             : str   — present only on failure
        }
    """
    _log("INFO", "=" * 60)
    _log("INFO", "Starting EX5 deployment")
    _log("INFO", "=" * 60)

    source = Path(ex5_path).resolve()

    # ── Step 1–4: Validate source ────────────────────────────────────────────
    _log("INFO", f"Source EX5       : {source}")

    if not source.exists():
        _log("ERROR", f"EX5 was not generated — source file not found: {source}")
        return {"success": False, "verified": False, "error": f"Source EX5 not found: {source}"}

    if not source.is_file():
        _log("ERROR", f"Source path is not a regular file: {source}")
        return {"success": False, "verified": False, "error": f"Source is not a file: {source}"}

    source_size = source.stat().st_size
    if source_size == 0:
        _log("ERROR", f"Source EX5 is empty (0 bytes): {source}")
        return {"success": False, "verified": False, "error": "Source EX5 is empty"}

    _log("INFO", f"Source size      : {source_size} bytes")

    # ── Step 5: Discover / resolve Experts directory ─────────────────────────
    if experts_dir_override is not None:
        experts_folder = Path(experts_dir_override).resolve()
        instance_id = "override"
        _log("INFO", f"Using overridden Experts directory: {experts_folder}")
    else:
        _log("INFO", "Discovering MT5 data folder...")
        try:
            mt5_info = discover_mt5_data_folder()
        except RuntimeError as exc:
            _log("ERROR", f"MT5 data folder not found: {exc}")
            return {"success": False, "verified": False, "error": str(exc)}
        experts_folder = mt5_info["experts_folder"]
        instance_id = mt5_info["instance_id"]

    # ── Step 6: Create directory if needed ───────────────────────────────────
    if not experts_folder.exists():
        _log("INFO", f"Creating Experts directory: {experts_folder}")
        try:
            experts_folder.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            _log("ERROR", f"MQL5\\Experts folder could not be created: {exc}")
            return {"success": False, "verified": False, "error": f"mkdir failed: {exc}"}

    # ── Step 7–8: Resolve destination ────────────────────────────────────────
    destination = (experts_folder / source.name).resolve()
    _log("INFO", f"Destination path : {destination}")

    overwritten = destination.exists()
    if overwritten:
        _log("INFO", "Destination file already exists — will overwrite safely")

    # ── Step 9: Source SHA-256 BEFORE copy ───────────────────────────────────
    _log("INFO", "Calculating source SHA-256...")
    try:
        source_sha256 = _sha256_file(source)
    except Exception as exc:
        _log("ERROR", f"EX5 copy failed (source hash error): {exc}")
        return {"success": False, "verified": False, "error": f"Source hash failed: {exc}"}
    _log("INFO", f"Source SHA-256   : {source_sha256}")

    # ── Step 10: Copy ────────────────────────────────────────────────────────
    _log("INFO", "Copying EX5 with shutil.copy2()...")
    try:
        shutil.copy2(str(source), str(destination))
    except Exception as exc:
        _log("ERROR", f"EX5 copy failed: {exc}")
        return {"success": False, "verified": False, "error": f"Copy failed: {exc}"}

    # ── Step 11–12: Verify destination exists and is a file ──────────────────
    if not destination.exists():
        _log("ERROR", f"Destination verification failed — file not found after copy: {destination}")
        return {
            "success": False, "verified": False,
            "error": f"Destination not found after copy: {destination}",
        }

    if not destination.is_file():
        _log("ERROR", f"Destination exists but is not a regular file: {destination}")
        return {
            "success": False, "verified": False,
            "error": "Destination is not a regular file",
        }

    # ── Step 13–14: Compare file sizes ───────────────────────────────────────
    dest_size = destination.stat().st_size
    _log("INFO", f"Destination size : {dest_size} bytes")

    if dest_size != source_size:
        _log("ERROR", f"Size mismatch — source: {source_size} bytes, destination: {dest_size} bytes")
        return {
            "success": False, "verified": False,
            "source": str(source), "destination": str(destination),
            "source_size": source_size, "destination_size": dest_size,
            "error": f"File size mismatch: source={source_size}, dest={dest_size}",
        }

    _log("INFO", "File sizes match [OK]")

    # ── Step 15: Destination SHA-256 ─────────────────────────────────────────
    _log("INFO", "Calculating destination SHA-256...")
    try:
        dest_sha256 = _sha256_file(destination)
    except Exception as exc:
        _log("ERROR", f"Destination verification failed (hash error): {exc}")
        return {"success": False, "verified": False, "error": f"Destination hash failed: {exc}"}
    _log("INFO", f"Destination SHA-256: {dest_sha256}")

    # ── Step 16: Compare hashes ──────────────────────────────────────────────
    hash_match = (source_sha256 == dest_sha256)

    if not hash_match:
        _log("ERROR", "Source/destination hash mismatch")
        _log("ERROR", f"  Source      : {source_sha256}")
        _log("ERROR", f"  Destination : {dest_sha256}")
        return {
            "success": False, "verified": False,
            "source": str(source),
            "destination": str(destination),
            "size": dest_size,
            "source_sha256": source_sha256,
            "destination_sha256": dest_sha256,
            "hash_match": False,
            "overwritten": overwritten,
            "error": "SHA-256 hash mismatch after copy",
        }

    _log("INFO", "SHA-256 hashes match [OK]")

    # ── Step 17: Success ─────────────────────────────────────────────────────
    _log("SUCCESS", "EX5 deployment completed")
    _log("INFO", "=" * 60)

    return {
        "success": True,
        "source": str(source),
        "destination": str(destination),
        "size": dest_size,
        "source_sha256": source_sha256,
        "destination_sha256": dest_sha256,
        "hash_match": True,
        "verified": True,
        "overwritten": overwritten,
        "instance_id": instance_id,
    }
