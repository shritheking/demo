from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
import datetime
from dateutil.relativedelta import relativedelta

from app.db.database import get_db
from app.models import Order, InstallmentPayment, License, Product, User, CompileJob
from app.schemas.installments import InstallmentCreate, InstallmentCustomerResponse, InstallmentPaymentRecord, InstallmentPayRequest
from app.core.azure_vm import start_azure_vm_if_needed
from app.core.security import verify_admin_key

router = APIRouter()

@router.post("/create")
async def create_installment_arrangement(payload: InstallmentCreate, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db), _admin: str = Depends(verify_admin_key)):
    result = await db.execute(select(Order).filter(Order.id == payload.order_id))
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    order.installment_enabled = True
    order.installment_total_amount = payload.total_amount
    order.installment_amount = payload.installment_amount
    order.installment_count = payload.installment_count
    order.installments_paid = 1 # We consider first payment done at creation
    order.amount_paid = payload.first_payment_amount
    order.amount_remaining = payload.total_amount - payload.first_payment_amount
    order.license_period_days = payload.license_period_days
    
    # Calculate next due date and expiry
    from datetime import timezone
    current_time = datetime.datetime.now(timezone.utc)
    order.next_due_date = current_time + relativedelta(days=payload.license_period_days)
    # Record first payment
    payment = InstallmentPayment(
        order_id=order.id,
        amount=payload.first_payment_amount,
        payment_number=1,
        status="confirmed"
    )
    db.add(payment)
    
    # Verify license exists or create it
    lic_res = await db.execute(select(License).filter(License.order_id == order.id))
    lic = lic_res.scalar_one_or_none()
    
    # The EA's embedded expiry (and the /licenses/status heartbeat) both key
    # off License.expiry_date directly, so it must already include the
    # grace period — otherwise the binary and the heartbeat cut the
    # customer off at next_due_date, 5 days before the cron job
    # (expire_licenses.py) actually marks the license defaulted.
    expiry = order.next_due_date + relativedelta(days=order.grace_days)
    if not lic:
        if not order.mt5_id:
            raise HTTPException(status_code=400, detail="Order is missing MT5 ID")
        import uuid
        lic = License(
            order_id=order.id,
            user_id=order.user_id,
            mt5_id=order.mt5_id,
            expiry_date=expiry,
            status="generating",
            license_type="paid",
            license_uuid=str(uuid.uuid4())
        )
        db.add(lic)
        await db.flush()
    else:
        lic.expiry_date = expiry
        lic.status = "generating"
        
    job = CompileJob(license_id=lic.id, status="pending")
    db.add(job)
    
    order.status = "compiling"
    
    await db.commit()
    background_tasks.add_task(start_azure_vm_if_needed)
    
    return {"status": "success", "message": "Installment arrangement created and first payment recorded"}

@router.post("/pay")
async def pay_installment(payload: InstallmentPayRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db), _admin: str = Depends(verify_admin_key)):
    result = await db.execute(select(Order).filter(Order.id == payload.order_id))
    order = result.scalar_one_or_none()
    
    if not order or not order.installment_enabled:
        raise HTTPException(status_code=404, detail="Order not found or not installment enabled")
    
    # Guard: block overpayment
    if order.installment_status == "completed":
        raise HTTPException(status_code=400, detail="All installments for this order are already paid. No further payments needed.")
    
    if order.installments_paid >= order.installment_count:
        raise HTTPException(status_code=400, detail=f"All {order.installment_count} installments are already recorded. Cannot add more.")
        
    # Update order stats
    order.installments_paid += 1
    order.amount_paid += payload.amount
    order.amount_remaining = max(0, order.installment_total_amount - order.amount_paid)
    
    is_final = order.installments_paid >= order.installment_count or order.amount_remaining <= 0
    
    if is_final:
        order.installment_status = "completed"
        order.next_due_date = None
        order.amount_remaining = 0
    else:
        from datetime import timezone
        current_time = datetime.datetime.now(timezone.utc)
        order.next_due_date = current_time + relativedelta(days=order.license_period_days)
        
    # Record payment
    payment = InstallmentPayment(
        order_id=order.id,
        amount=payload.amount,
        payment_number=order.installments_paid,
        status="confirmed"
    )
    db.add(payment)
    
    # Update license
    lic_res = await db.execute(select(License).filter(License.order_id == order.id))
    lic = lic_res.scalar_one_or_none()
    
    if lic:
        if is_final:
            lic.expiry_date = None
            lic.license_type = "paid"
        else:
            lic.expiry_date = order.next_due_date + relativedelta(days=order.grace_days)
        lic.status = "generating"
        
        job = CompileJob(license_id=lic.id, status="pending")
        db.add(job)
        
    await db.commit()
    background_tasks.add_task(start_azure_vm_if_needed)
    
    return {"status": "success", "message": "Payment recorded"}

@router.get("/customer/{telegram_id}", response_model=InstallmentCustomerResponse)
async def get_customer_installment(telegram_id: str, db: AsyncSession = Depends(get_db)):
    # Find user
    u_res = await db.execute(select(User).filter(User.telegram_id == telegram_id))
    user = u_res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Find the customer's ongoing installment order. Exclude completed (and
    # defaulted) arrangements so a finished plan doesn't shadow a newer,
    # still-active one - or vice versa - when a customer has had more than
    # one installment arrangement over time.
    o_res = await db.execute(
        select(Order).filter(
            Order.user_id == user.id,
            Order.installment_enabled == True,
            Order.installment_status.notin_(["completed", "defaulted"])
        ).order_by(Order.id.desc())
    )
    order = o_res.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="No active installment arrangement found")
        
    p_res = await db.execute(select(Product).filter(Product.id == order.product_id))
    product = p_res.scalar_one_or_none()
    
    lic_res = await db.execute(select(License).filter(License.order_id == order.id))
    lic = lic_res.scalar_one_or_none()
    
    pmt_res = await db.execute(select(InstallmentPayment).filter(InstallmentPayment.order_id == order.id).order_by(InstallmentPayment.payment_number.asc()))
    payments = pmt_res.scalars().all()
    
    return InstallmentCustomerResponse(
        order_id=order.id,
        mt5_id=lic.mt5_id if lic else order.mt5_id,
        product_name=product.name if product else "EA",
        total_amount=order.installment_total_amount or 0,
        installment_amount=order.installment_amount or 0,
        amount_paid=order.amount_paid or 0,
        amount_remaining=order.amount_remaining or 0,
        installments_paid=order.installments_paid or 0,
        installment_count=order.installment_count or 0,
        license_status=lic.status if lic else "None",
        license_expiry=lic.expiry_date if lic else None,
        next_due_date=order.next_due_date,
        installment_status=order.installment_status or "active",
        license_period_days=order.license_period_days,
        payments=[InstallmentPaymentRecord.model_validate(p) for p in payments]
    )

@router.get("/admin/{order_id}", response_model=InstallmentCustomerResponse)
async def get_admin_installment(order_id: int, db: AsyncSession = Depends(get_db), _admin: str = Depends(verify_admin_key)):
    result = await db.execute(select(Order).filter(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order or not order.installment_enabled:
        raise HTTPException(status_code=404, detail="Installment arrangement not found")
        
    p_res = await db.execute(select(Product).filter(Product.id == order.product_id))
    product = p_res.scalar_one_or_none()
    
    lic_res = await db.execute(select(License).filter(License.order_id == order.id))
    lic = lic_res.scalar_one_or_none()
    
    pmt_res = await db.execute(select(InstallmentPayment).filter(InstallmentPayment.order_id == order.id).order_by(InstallmentPayment.payment_number.asc()))
    payments = pmt_res.scalars().all()
    
    return InstallmentCustomerResponse(
        order_id=order.id,
        mt5_id=lic.mt5_id if lic else order.mt5_id,
        product_name=product.name if product else "EA",
        total_amount=order.installment_total_amount or 0,
        installment_amount=order.installment_amount or 0,
        amount_paid=order.amount_paid or 0,
        amount_remaining=order.amount_remaining or 0,
        installments_paid=order.installments_paid or 0,
        installment_count=order.installment_count or 0,
        license_status=lic.status if lic else "None",
        license_expiry=lic.expiry_date if lic else None,
        next_due_date=order.next_due_date,
        installment_status=order.installment_status or "active",
        license_period_days=order.license_period_days,
        payments=[InstallmentPaymentRecord.model_validate(p) for p in payments]
    )
