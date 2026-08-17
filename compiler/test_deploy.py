"""
test_deploy.py
==============
Standalone deployment test for the MT5 EX5 deployment pipeline.

Tests (in order):
    T1  Source EX5 file exists
    T2  Source EX5 is a non-zero file
    T3  MT5 installation discovery succeeds
    T4  Experts directory is discovered and is valid
    T5  Discovered Experts path is absolute
    T6  Deploy to TEMP directory succeeds (non-destructive first pass)
    T7  Destination file exists after copy
    T8  Source and destination sizes match
    T9  Source and destination SHA-256 hashes match
    T10 deploy_ex5() returns success=True

This test does NOT modify the production Experts directory on the first pass.
It deploys to a controlled temporary directory inside the compiler output tree.

Usage:
    cd C:\\mt5-license-system\\compiler
    python test_deploy.py

To also test the live Experts deployment (second pass), run:
    python test_deploy.py --live

AutoTrading is NOT enabled. No trades are placed. No account settings are changed.
"""

from __future__ import annotations

import argparse
import sys
import tempfile

# Ensure UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

# Ensure the compiler directory is on sys.path so mt5_deploy imports cleanly.
_COMPILER_DIR = Path(__file__).resolve().parent
if str(_COMPILER_DIR) not in sys.path:
    sys.path.insert(0, str(_COMPILER_DIR))

from mt5_deploy import deploy_ex5, discover_mt5_data_folder  # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SOURCE_EX5 = _COMPILER_DIR / "output" / "InfinityTrader_TEST001_2026-1-2-31.ex5"

PASS = "PASS"
FAIL = "FAIL"


# ---------------------------------------------------------------------------
# Test runner helpers
# ---------------------------------------------------------------------------

class TestResult:
    def __init__(self):
        self.results: list[tuple[str, str, str]] = []  # (id, status, detail)

    def record(self, test_id: str, passed: bool, detail: str = "") -> None:
        status = PASS if passed else FAIL
        marker = "✓" if passed else "✗"
        print(f"  [{marker}] {test_id}: {status}  {detail}")
        self.results.append((test_id, status, detail))

    def summary(self) -> None:
        total = len(self.results)
        passed = sum(1 for _, s, _ in self.results if s == PASS)
        failed = total - passed
        print()
        print("=" * 60)
        print(f"TEST SUMMARY:  {passed}/{total} passed  |  {failed} failed")
        print("=" * 60)
        if failed == 0:
            print("[SUCCESS] All tests passed.")
        else:
            print("[FAILURE] One or more tests failed.")
            for tid, status, detail in self.results:
                if status == FAIL:
                    print(f"  FAILED: {tid}  —  {detail}")


# ---------------------------------------------------------------------------
# Main test
# ---------------------------------------------------------------------------

def run_tests(live: bool = False) -> int:
    """
    Run all deployment tests.

    Args:
        live: If True, also run a second deployment to the real Experts dir.

    Returns:
        Exit code: 0 = all pass, 1 = one or more failures.
    """
    tr = TestResult()

    print()
    print("=" * 60)
    print("MT5 EX5 DEPLOYMENT TEST SUITE")
    print("=" * 60)
    print(f"Source EX5 : {SOURCE_EX5}")
    print()

    # ------------------------------------------------------------------
    # T1: Source EX5 exists
    # ------------------------------------------------------------------
    print("── T1: Source EX5 exists ──────────────────────────────────")
    source_exists = SOURCE_EX5.exists()
    tr.record("T1", source_exists,
              str(SOURCE_EX5) if source_exists else f"NOT FOUND: {SOURCE_EX5}")

    # ------------------------------------------------------------------
    # T2: Source EX5 is a non-zero file
    # ------------------------------------------------------------------
    print("── T2: Source EX5 is non-zero ─────────────────────────────")
    if source_exists and SOURCE_EX5.is_file():
        source_size = SOURCE_EX5.stat().st_size
        t2_pass = source_size > 0
        tr.record("T2", t2_pass, f"{source_size} bytes")
    else:
        source_size = 0
        tr.record("T2", False, "Source file missing or not a file")

    # ------------------------------------------------------------------
    # T3: MT5 discovery
    # ------------------------------------------------------------------
    print("── T3: MT5 instance discovery ─────────────────────────────")
    mt5_info = None
    try:
        mt5_info = discover_mt5_data_folder()
        tr.record("T3", True,
                  f"instance={mt5_info['instance_id']}  "
                  f"origin={mt5_info.get('origin', '')!r}")
    except RuntimeError as exc:
        tr.record("T3", False, str(exc))

    # ------------------------------------------------------------------
    # T4: Experts directory discovered and exists
    # ------------------------------------------------------------------
    print("── T4: Experts directory exists ───────────────────────────")
    if mt5_info:
        experts = mt5_info["experts_folder"]
        t4_pass = experts.is_dir()
        tr.record("T4", t4_pass, str(experts))
    else:
        tr.record("T4", False, "MT5 discovery failed — cannot check Experts dir")
        experts = None

    # ------------------------------------------------------------------
    # T5: Discovered Experts path is absolute
    # ------------------------------------------------------------------
    print("── T5: Experts path is absolute ───────────────────────────")
    if experts is not None:
        t5_pass = experts.is_absolute()
        tr.record("T5", t5_pass, str(experts))
    else:
        tr.record("T5", False, "Experts dir unavailable")

    # ------------------------------------------------------------------
    # T6–T10: Deploy to a TEMP directory (safe, non-destructive)
    # ------------------------------------------------------------------
    print()
    print("── T6–T10: TEMP deployment (non-destructive) ──────────────")
    print(f"  Deploying to a temporary directory (NOT the live Experts folder)")
    print()

    temp_result: dict = {}
    with tempfile.TemporaryDirectory(prefix="mt5_deploy_test_") as tmp_dir:
        tmp_path = Path(tmp_dir).resolve()
        print(f"  Temp dir: {tmp_path}")

        if source_exists and source_size > 0:
            temp_result = deploy_ex5(SOURCE_EX5, experts_dir_override=tmp_path)
        else:
            temp_result = {"success": False, "error": "Source EX5 unavailable for testing"}

        # T6: deploy_ex5() called without exception (success key exists)
        print("── T6: Copy to temp destination succeeded ─────────────────")
        t6_pass = temp_result.get("success", False)
        tr.record("T6", t6_pass, temp_result.get("error", ""))

        # T7: Destination file exists
        print("── T7: Destination file exists ────────────────────────────")
        dest_path_str = temp_result.get("destination", "")
        if dest_path_str:
            dest_path = Path(dest_path_str)
            t7_pass = dest_path.exists() and dest_path.is_file()
            tr.record("T7", t7_pass, dest_path_str)
        else:
            tr.record("T7", False, "Destination path missing from result")

        # T8: Source and destination sizes match
        print("── T8: Source and destination sizes match ─────────────────")
        if t6_pass:
            result_size = temp_result.get("size", -1)
            t8_pass = (result_size == source_size) and (result_size > 0)
            tr.record("T8", t8_pass, f"size={result_size}")
        else:
            tr.record("T8", False, "Deployment failed — size check skipped")

        # T9: SHA-256 hashes match
        print("── T9: SHA-256 hashes match ───────────────────────────────")
        if t6_pass:
            hash_match = temp_result.get("hash_match", False)
            src_hash = temp_result.get("source_sha256", "")
            dst_hash = temp_result.get("destination_sha256", "")
            tr.record("T9", hash_match,
                      f"src={src_hash[:16]}…  dst={dst_hash[:16]}…")
        else:
            tr.record("T9", False, "Deployment failed — hash check skipped")

        # T10: deploy_ex5() result.success is True
        print("── T10: deploy_ex5() reported success=True ────────────────")
        tr.record("T10", temp_result.get("success", False),
                  temp_result.get("error", "OK"))

    # ------------------------------------------------------------------
    # Optional live deployment (--live flag)
    # ------------------------------------------------------------------
    if live:
        print()
        print("── LIVE deployment to real Experts folder ─────────────────")
        if source_exists and source_size > 0 and mt5_info:
            print(f"  Target: {mt5_info['experts_folder']}")
            live_result = deploy_ex5(SOURCE_EX5)
            live_pass = live_result.get("success", False)
            print()
            if live_pass:
                print("[SUCCESS] Live deployment verified.")
                print(f"  Destination : {live_result['destination']}")
                print(f"  Size        : {live_result['size']} bytes")
                print(f"  Source hash : {live_result['source_sha256']}")
                print(f"  Dest hash   : {live_result['destination_sha256']}")
                print(f"  Overwritten : {live_result['overwritten']}")
            else:
                print(f"[ERROR] Live deployment failed: {live_result.get('error')}")
        else:
            print("[ERROR] Skipped live deployment — prerequisites not met.")

    # ------------------------------------------------------------------
    # Print detailed results table
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    print("DETAILED RESULTS")
    print("=" * 60)
    print(f"  Source EX5      : {SOURCE_EX5}")
    print(f"  Source size     : {source_size} bytes")
    if mt5_info:
        print(f"  Instance ID     : {mt5_info['instance_id']}")
        print(f"  Data folder     : {mt5_info['data_folder']}")
        print(f"  Experts folder  : {mt5_info['experts_folder']}")
        print(f"  origin.txt      : {mt5_info.get('origin', '')!r}")
    if temp_result.get("source_sha256"):
        print(f"  Source SHA-256  : {temp_result['source_sha256']}")
    if temp_result.get("destination_sha256"):
        print(f"  Dest SHA-256    : {temp_result['destination_sha256']}")
    if "hash_match" in temp_result:
        print(f"  Hash match      : {temp_result['hash_match']}")
    if "destination" in temp_result:
        print(f"  Temp destination: {temp_result['destination']}")

    tr.summary()

    failed = sum(1 for _, s, _ in tr.results if s == FAIL)
    return 0 if failed == 0 else 1


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="MT5 EX5 deployment test suite. Does NOT enable AutoTrading."
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "After the safe temp-dir test, also deploy to the real "
            "MQL5\\Experts folder. The existing file will be overwritten safely."
        ),
    )
    args = parser.parse_args()

    exit_code = run_tests(live=args.live)
    sys.exit(exit_code)
