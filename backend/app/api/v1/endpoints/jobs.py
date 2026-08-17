from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Header, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
import os
import uuid
import httpx
from datetime import datetime

# Only disable TLS verification when explicitly opted into (local dev behind
# a self-signed proxy). Never disable this in production.
HTTPX_VERIFY = os.getenv("DISABLE_SSL_VERIFY", "false").lower() not in ("1", "true", "yes")

from app.db.database import get_db, AsyncSessionLocal
from app.models import CompileJob, License, Order, Product, User, InstallmentPayment, Payment, TrialActivation, TrialClaim, LicenseMt5History, BrokerChangeRequest, VpsOrder
from sqlalchemy import text
from app.core.security import verify_admin_key

router = APIRouter()

@router.post("/wipe_production_db")
async def wipe_production_db(db: AsyncSession = Depends(get_db), _admin: str = Depends(verify_admin_key)):
    """
    Temporary endpoint to wipe the database since we cannot connect to the internal Render URL from outside.
    """
    await db.execute(text("TRUNCATE TABLE users CASCADE;"))
    await db.execute(text("TRUNCATE TABLE orders CASCADE;"))
    await db.commit()
    return {"status": "success", "message": "Production database completely wiped (users, orders, licenses, jobs, etc)."}

def verify_worker_api_key(infinity_worker_api_key: Optional[str] = Header(None)):
    expected_key = os.getenv("INFINITY_WORKER_API_KEY")
    if not expected_key:
        # If no key configured on server, reject all for safety
        raise HTTPException(status_code=500, detail="Server missing worker API key configuration")
    if not infinity_worker_api_key or infinity_worker_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid worker API key")
    return infinity_worker_api_key

@router.get("/pending")
async def get_pending_jobs(db: AsyncSession = Depends(get_db), api_key: str = Depends(verify_worker_api_key)):
    """
    Optional: Just list pending jobs for debugging. 
    Workers should prefer calling POST /claim directly.
    """
    result = await db.execute(select(CompileJob).filter(CompileJob.status == "pending").limit(10))
    jobs = result.scalars().all()
    
    response_jobs = []
    for job in jobs:
        lic_res = await db.execute(select(License).filter(License.id == job.license_id))
        lic = lic_res.scalar_one_or_none()
        if lic:
            response_jobs.append({
                "job_id": job.id,
                "license_id": job.license_id,
                "mt5_id": lic.mt5_id,
                "created_at": job.created_at
            })
            
    return response_jobs

@router.post("/reset-stuck")
async def reset_stuck_jobs(db: AsyncSession = Depends(get_db), api_key: str = Depends(verify_worker_api_key)):
    """
    Reset all 'processing' jobs back to 'pending' so the worker can retry them.
    Skips permanently failed jobs (PERMANENTLY_SKIPPED error) and jobs with no MT5 ID.
    """
    from sqlalchemy import update as sql_update
    
    # Find stuck processing/failed jobs that are NOT permanently skipped
    result = await db.execute(
        select(CompileJob).where(
            CompileJob.status.in_(["processing", "failed"]),
            ~CompileJob.error_message.like("PERMANENTLY_SKIPPED%") if CompileJob.error_message is not None else True
        )
    )
    stuck_jobs = result.scalars().all()
    
    reset_count = 0
    skipped_count = 0
    for job in stuck_jobs:
        # Skip permanently failed
        if job.error_message and job.error_message.startswith("PERMANENTLY_SKIPPED"):
            skipped_count += 1
            continue
        # Check if the license has a valid MT5 ID
        lic_res = await db.execute(select(License).filter(License.id == job.license_id))
        lic = lic_res.scalar_one_or_none()
        if not lic or not lic.mt5_id or lic.mt5_id.strip() == "":
            # Mark as permanently failed so it doesn't keep cycling
            job.status = "failed"
            job.error_message = "PERMANENTLY_SKIPPED: License has no MT5 ID."
            skipped_count += 1
            continue
        job.status = "pending"
        job.worker_id = None
        job.started_at = None
        job.attempt_count = 0
        reset_count += 1
    
    await db.commit()
    return {
        "status": "success",
        "reset_count": reset_count,
        "skipped_count": skipped_count,
        "message": f"Reset {reset_count} stuck jobs to pending. Skipped {skipped_count} jobs (no MT5 ID or permanently failed)."
    }

@router.get("/status")
async def get_jobs_status(db: AsyncSession = Depends(get_db), api_key: str = Depends(verify_worker_api_key)):
    """
    Get count of jobs in each state for monitoring.
    """
    from sqlalchemy import func
    result = await db.execute(
        select(CompileJob.status, func.count(CompileJob.id).label("count"))
        .group_by(CompileJob.status)
    )
    rows = result.all()
    return {row[0]: row[1] for row in rows}

from pydantic import BaseModel
class ClaimRequest(BaseModel):
    worker_id: str

@router.post("/claim")
async def claim_job(req: ClaimRequest, db: AsyncSession = Depends(get_db), api_key: str = Depends(verify_worker_api_key)):
    """
    Atomically claim a single pending job.
    """
    # Select ONE pending job FOR UPDATE SKIP LOCKED
    stmt = (
        select(CompileJob)
        .filter(CompileJob.status == "pending")
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    
    if not job:
        return {"status": "empty", "message": "No pending jobs available"}
        
    job.status = "processing"
    job.worker_id = req.worker_id
    job.started_at = datetime.utcnow()
    job.attempt_count = job.attempt_count + 1
    
    # Get associated license for mt5_id, expiry_date
    lic_res = await db.execute(select(License).filter(License.id == job.license_id))
    lic = lic_res.scalar_one_or_none()

    # Get Order → Product to resolve the plan name
    prod = None
    if lic:
        ord_res = await db.execute(select(Order).filter(Order.id == lic.order_id))
        ord_obj = ord_res.scalar_one_or_none()
        if ord_obj:
            prod_res = await db.execute(select(Product).filter(Product.id == ord_obj.product_id))
            prod = prod_res.scalar_one_or_none()

    await db.commit()

    # Format expiry as YYYY-MM-DD for compile_ea()
    expiry_str = None
    if lic and lic.expiry_date:
        expiry_str = lic.expiry_date.strftime("%Y-%m-%d")

    return {
        "status": "success",
        "job": {
            "job_id": job.id,
            "license_id": job.license_id,
            "mt5_id": lic.mt5_id if lic else None,
            "expiry_date": expiry_str,
            "plan": prod.name if prod else "standard",
            "license_uuid": lic.license_uuid if lic else None
        }
    }

async def notify_admin_compile_failed(license_id: int, error_message: str):
    """Spec section 29: admin must be notified when a compile job fails."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    admin_chat_id = os.getenv("ADMIN_CHAT_ID")
    if not bot_token or not admin_chat_id:
        return
    try:
        lic_res = None
        async with AsyncSessionLocal() as db:
            lic_res = await db.execute(select(License).filter(License.id == license_id))
            lic = lic_res.scalar_one_or_none()
        mt5_id = lic.mt5_id if lic else "unknown"
        msg = (
            f"🔴 *Compilation Failed*\n\n"
            f"License ID: {license_id}\n"
            f"MT5 ID: `{mt5_id}`\n\n"
            f"Error: {error_message[:500]}"
        )
        async with httpx.AsyncClient(verify=HTTPX_VERIFY, timeout=15.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": admin_chat_id, "text": msg, "parse_mode": "Markdown"}
            )
    except Exception as e:
        print(f"Failed to notify admin of compile failure: {e}")


async def notify_telegram_bot(license_id: int):
    # Force the production URL, ignoring any potentially broken env vars on Render
    bot_webhook_url = "https://infinity-trader-telegram-bot.onrender.com/internal/delivery"
    try:
        import httpx
        async with httpx.AsyncClient(verify=HTTPX_VERIFY, timeout=15.0) as client:
            resp = await client.post(bot_webhook_url, json={"license_id": license_id})
            if resp.status_code != 200:
                print(f"Telegram bot webhook returned {resp.status_code}: {resp.text}")
            else:
                print(f"Successfully notified Telegram bot for license {license_id}")
    except Exception as e:
        print(f"Failed to notify Telegram bot: {e}")

@router.post("/{job_id}/upload")
async def upload_compiled_file(
    job_id: int, 
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...), 
    db: AsyncSession = Depends(get_db), 
    api_key: str = Depends(verify_worker_api_key)
):
    """
    Worker uploads the compiled .ex5 file.
    """
    if not file.filename.endswith('.ex5') and not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only .ex5 or .zip files allowed")

    # We do not use skip_locked here because we specifically want this exact job
    result = await db.execute(select(CompileJob).filter(CompileJob.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if job.status != "processing":
        raise HTTPException(status_code=400, detail="Job is not in processing state")
        
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty")
        
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SECRET_KEY")
    
    if not supabase_url or not supabase_key:
        raise HTTPException(status_code=500, detail="Supabase not configured on server")
        
    try:
        from supabase import create_client
        supabase = create_client(supabase_url, supabase_key)
        bucket_name = "licenses"
        
        # Attempt to auto-create the public bucket in case it was deleted or never created
        try:
            supabase.storage.create_bucket(bucket_name, {"public": True})
        except Exception:
            pass
        
        # licenses/{license_id}/{job_id}/bot.ex5
        ext = ".zip" if file.filename.endswith('.zip') else ".ex5"
        file_path = f"{job.license_id}/{job.id}/bot{ext}"
        
        res = supabase.storage.from_(bucket_name).upload(file_path, content)
        
        # supabase-py sometimes returns an error dict instead of throwing an exception
        if isinstance(res, dict) and res.get('error'):
            raise Exception(res.get('error'))
        if hasattr(res, 'error') and res.error:
            raise Exception(res.error)
        if hasattr(res, 'status_code') and res.status_code >= 400:
            raise Exception(f"HTTP {res.status_code}")
            
    except Exception as e:
        print(f"Failed to upload to Supabase: {e}")
        raise HTTPException(status_code=500, detail=f"Storage error: {e}")
            
    # Update Job
    job.status = "completed"
    job.completed_at = datetime.utcnow()
    
    # Update License & Order
    lic_res = await db.execute(select(License).filter(License.id == job.license_id))
    lic = lic_res.scalar_one_or_none()
    if lic:
        lic.generated_filename = file_path # Save the Supabase path
        lic.status = "active"
        
        ord_res = await db.execute(select(Order).filter(Order.id == lic.order_id))
        ord_obj = ord_res.scalar_one_or_none()
        if ord_obj:
            ord_obj.status = "delivered"
            
    await db.commit()
    
    # Trigger background push to Telegram
    background_tasks.add_task(notify_telegram_bot, job.license_id)
    
    return {"status": "success", "message": "File uploaded and completed"}

class FailRequest(BaseModel):
    worker_id: str
    error_message: str

@router.post("/{job_id}/fail")
async def fail_job(job_id: int, req: FailRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db), api_key: str = Depends(verify_worker_api_key)):
    """
    Worker reports a compilation failure.
    """
    result = await db.execute(select(CompileJob).filter(CompileJob.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if job.status != "processing":
        raise HTTPException(status_code=400, detail="Job is not in processing state")
        
    job.status = "failed"
    job.error_message = req.error_message
    job.completed_at = datetime.utcnow()
    
    await db.commit()

    background_tasks.add_task(notify_admin_compile_failed, job.license_id, req.error_message)

    return {"status": "success"}
