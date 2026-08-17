"""
pipeline_test.py
================
End-to-end pipeline: compile -> deploy -> verify.
MQ5 -> MetaEditor -> EX5 -> discover MT5 -> shutil.copy2() -> SHA-256 verify.
No AutoTrading. No trades. No account changes.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from compile import compile_ea
from mt5_deploy import deploy_ex5

print("=" * 60)
print("FULL PIPELINE: compile -> deploy -> verify")
print("=" * 60)
print()

# ── Step 1: Compile ──────────────────────────────────────────────────────────
print("[INFO] Step 1: Compiling InfinityTrader_TEST001_2026-12-31")
ex5_path = compile_ea("TEST001", "2026-12-31", "premium")
print()

# ── Step 2: Deploy ───────────────────────────────────────────────────────────
print("[INFO] Step 2: Deploying to MT5 Experts folder")
result = deploy_ex5(ex5_path)
print()

# ── Step 3: Report ───────────────────────────────────────────────────────────
print("=" * 60)
print("PIPELINE RESULT")
print("=" * 60)
print(f"  Success          : {result['success']}")
print(f"  Source           : {result['source']}")
print(f"  Destination      : {result['destination']}")
print(f"  File size        : {result['size']} bytes")
print(f"  Source SHA-256   : {result['source_sha256']}")
print(f"  Dest SHA-256     : {result['destination_sha256']}")
print(f"  Hash match       : {result['hash_match']}")
print(f"  Verified         : {result['verified']}")
print(f"  Overwritten      : {result['overwritten']}")
print(f"  Instance ID      : {result.get('instance_id', 'N/A')}")
print()

if result["success"]:
    print("[SUCCESS] EX5 deployment completed")
else:
    print(f"[ERROR] Deployment failed: {result.get('error')}")
    sys.exit(1)
