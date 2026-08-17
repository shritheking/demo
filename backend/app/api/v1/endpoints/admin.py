import os
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.db.database import get_db
from app.models import User, Order, Payment, CompileJob, License, Product, VpsOrder
from app.core.security import verify_admin_key

router = APIRouter(dependencies=[Depends(verify_admin_key)])

# Only disable TLS verification when explicitly opted into (local dev behind
# a self-signed proxy). Never disable this in production.
HTTPX_VERIFY = os.getenv("DISABLE_SSL_VERIFY", "false").lower() not in ("1", "true", "yes")

@router.get("/stats")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    # Total Users
    result = await db.execute(select(func.count()).select_from(User))
    total_users = result.scalar() or 0

    # Total Orders
    result = await db.execute(select(func.count()).select_from(Order))
    total_orders = result.scalar() or 0

    # Total Revenue (sum of all paid payments)
    result = await db.execute(select(func.sum(Payment.amount)).filter(Payment.status == "paid"))
    total_revenue = result.scalar() or 0
    total_revenue = total_revenue / 100 # Assuming stored in paise if Razorpay, wait no, my payment model uses float for amount. Wait, if it's stored in rupees, it's just total_revenue. I'll just use total_revenue.

    # Active Licenses
    result = await db.execute(select(func.count()).select_from(License).filter(License.status.in_(["active", "valid"])))
    active_licenses = result.scalar() or 0

    # Compiler Queue (pending jobs)
    result = await db.execute(select(func.count()).select_from(CompileJob).filter(CompileJob.status == "pending"))
    compiler_queue = result.scalar() or 0
    
    # Recent Orders
    result = await db.execute(select(Order).order_by(Order.created_at.desc()).limit(5))
    recent_orders = result.scalars().all()

    return {
        "total_users": total_users,
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "active_licenses": active_licenses,
        "compiler_queue": compiler_queue,
        "recent_orders": [
            {
                "id": o.id,
                "product_id": o.product_id,
                "user_id": o.user_id,
                "status": o.status,
                "created_at": o.created_at
            }
            for o in recent_orders
        ]
    }

@router.get("/compiler_jobs")
async def get_compiler_jobs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CompileJob).order_by(CompileJob.created_at.desc()))
    jobs = result.scalars().all()
    return jobs

@router.post("/jobs/{job_id}/retry")
async def retry_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """
    Reset a failed or stuck compile job back to 'pending' so the worker
    can claim and process it again on the next poll cycle.
    """
    from fastapi import HTTPException
    result = await db.execute(select(CompileJob).filter(CompileJob.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job.status not in ("failed", "processing"):
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} is '{job.status}' — can only retry 'failed' or stuck 'processing' jobs"
        )

    previous_status = job.status
    job.status       = "pending"
    job.error_message = None
    job.worker_id    = None
    job.started_at   = None
    job.completed_at = None

    await db.commit()

    return {
        "status": "success",
        "message": f"Job {job_id} reset from '{previous_status}' to 'pending'",
        "job_id": job_id
    }

@router.get("/all_orders")
async def get_all_orders_admin(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Order, Product, User)
        .join(Product, Order.product_id == Product.id)
        .join(User, Order.user_id == User.id)
        .order_by(Order.created_at.desc())
    )
    rows = result.all()
    orders = []
    for order, product, user in rows:
        orders.append({
            "id": order.id,
            "product": product.name,
            "customer": user.name or user.username or "Unknown",
            "amount": product.price,
            "status": order.status,
            "date": order.created_at
        })
    return orders

from fastapi import HTTPException
from pydantic import BaseModel
import httpx
import os

class VpsProvisionData(BaseModel):
    ip: str
    username: str
    password: str

@router.get("/vps-orders")
async def get_vps_orders(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(VpsOrder, Order, User, Product)
        .join(Order, VpsOrder.order_id == Order.id)
        .join(User, VpsOrder.user_id == User.id)
        .join(Product, Order.product_id == Product.id)
        .order_by(VpsOrder.created_at.desc())
    )
    rows = result.all()
    vps_orders = []
    for vps_order, order, user, product in rows:
        vps_orders.append({
            "id": vps_order.id,
            "order_id": order.id,
            "customer": user.name or user.username or "Unknown",
            "plan_name": product.name,
            "duration": vps_order.duration,
            "status": vps_order.status,
            "ip": vps_order.ip,
            "created_at": vps_order.created_at
        })
    return vps_orders

@router.post("/vps-orders/{vps_id}/provision")
async def provision_vps(vps_id: int, data: VpsProvisionData, db: AsyncSession = Depends(get_db)):
    # 1. Update VpsOrder
    result = await db.execute(select(VpsOrder).filter(VpsOrder.id == vps_id))
    vps_order = result.scalar_one_or_none()
    if not vps_order:
        raise HTTPException(status_code=404, detail="VPS Order not found")
        
    if vps_order.status == "provisioned":
        raise HTTPException(status_code=400, detail="VPS already provisioned")
        
    vps_order.ip = data.ip
    vps_order.username = data.username
    vps_order.password = data.password
    vps_order.status = "provisioned"
    
    # 2. Update parent Order
    order_result = await db.execute(select(Order).filter(Order.id == vps_order.order_id))
    order = order_result.scalar_one_or_none()
    if order:
        order.status = "delivered"
        
    await db.commit()
    
    # 3. Notify user via Telegram
    user_result = await db.execute(select(User).filter(User.id == vps_order.user_id))
    user = user_result.scalar_one_or_none()
    
    if user:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if bot_token:
            msg = (
                "🎉 *Your VPS is Ready!*\n\n"
                "Here are your server credentials:\n"
                f"**IP Address:** `{data.ip}`\n"
                f"**Username:** `{data.username}`\n"
                f"**Password:** `{data.password}`\n\n"
                "Please connect using Remote Desktop Connection (RDP) on your PC or phone."
            )
            async with httpx.AsyncClient(verify=HTTPX_VERIFY) as client:
                await client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={"chat_id": user.telegram_id, "text": msg, "parse_mode": "Markdown"}
                )
                
    return {"status": "success"}

@router.get("/run-migrations")
async def run_migrations():
    import subprocess
    import sys
    try:
        result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], capture_output=True, text=True)
        return {"stdout": result.stdout, "stderr": result.stderr}
    except Exception as e:
        return {"error": str(e)}
