from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
import datetime
from dateutil.relativedelta import relativedelta

from app.db.database import get_db
from app.models import TrialSetting, TrialActivation, License, CompileJob
from pydantic import BaseModel
from app.core.azure_vm import start_azure_vm_if_needed

router = APIRouter()

class TrialSettingSchema(BaseModel):
    enabled: bool
    duration_days: int
    max_trials_per_month: int
    allow_existing_customers: bool
    trial_plan_name: str
    
    class Config:
        from_attributes = True

class TrialRequest(BaseModel):
    telegram_user_id: str
    mt5_id: str

@router.get("/settings", response_model=TrialSettingSchema)
async def get_trial_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TrialSetting).limit(1))
    settings = result.scalar_one_or_none()
    if not settings:
        # Return defaults if not seeded. Must match the enforced business
        # rule: 3 days, once per Telegram ID per calendar month.
        return TrialSettingSchema(
            enabled=True,
            duration_days=3,
            max_trials_per_month=1,
            allow_existing_customers=False,
            trial_plan_name="Trial EA"
        )
    return settings

@router.put("/settings", response_model=TrialSettingSchema)
async def update_trial_settings(settings_in: TrialSettingSchema, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TrialSetting).limit(1))
    settings = result.scalar_one_or_none()
    
    if not settings:
        settings = TrialSetting(
            enabled=settings_in.enabled,
            duration_days=settings_in.duration_days,
            max_trials_per_month=settings_in.max_trials_per_month,
            allow_existing_customers=settings_in.allow_existing_customers,
            trial_plan_name=settings_in.trial_plan_name
        )
        db.add(settings)
    else:
        settings.enabled = settings_in.enabled
        settings.duration_days = settings_in.duration_days
        settings.max_trials_per_month = settings_in.max_trials_per_month
        settings.allow_existing_customers = settings_in.allow_existing_customers
        settings.trial_plan_name = settings_in.trial_plan_name
        
    await db.commit()
    await db.refresh(settings)
    return settings

@router.post("/request")
async def request_free_trial(req: TrialRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    # 1. Check if trial is globally enabled
    settings_res = await db.execute(select(TrialSetting).limit(1))
    settings = settings_res.scalar_one_or_none()
    
    # Defaults if missing. Must match the enforced business rule exactly:
    # 3-day trial, 1 trial per Telegram ID per calendar month. These must
    # never drift from the TrialSetting model defaults / get_trial_settings()
    # above - a mismatch here is what silently broke the "change it in the
    # DB" workflow before.
    enabled = settings.enabled if settings else True
    duration_days = settings.duration_days if settings else 3
    max_trials = settings.max_trials_per_month if settings else 1
    allow_existing = settings.allow_existing_customers if settings else False
    plan_name = settings.trial_plan_name if settings else "Trial EA"

    if not enabled:
        raise HTTPException(status_code=400, detail="Free Trial is currently unavailable. Please check again later.")

    # 2. Check if MT5 ID has an active paid license
    if not allow_existing:
        existing_paid = await db.execute(
            select(License).filter(
                License.mt5_id == req.mt5_id,
                License.license_type == "paid",
                License.status == "active"
            )
        )
        if existing_paid.scalars().first():
            raise HTTPException(status_code=400, detail="This MT5 ID already has an active license.")

    # 3. Check Monthly limits (STRICT 1 PER CALENDAR MONTH RULE)
    import datetime as dt
    current_time = datetime.datetime.now(dt.timezone.utc)
    month_key = current_time.strftime("%Y-%m")
    
    from app.models import TrialClaim
    
    # Check if a TrialClaim already exists for this telegram ID in this month
    claim_res = await db.execute(
        select(TrialClaim).filter(
            TrialClaim.telegram_id == req.telegram_user_id,
            TrialClaim.claim_month == month_key
        )
    )
    if claim_res.scalars().first():
        raise HTTPException(status_code=400, detail="ALREADY_CLAIMED")

    # duration_days was already loaded from TrialSetting above (defaulting
    # to 3 if unseeded). We no longer silently override it here - the
    # config and the enforcement must agree, otherwise changing the admin
    # setting has no effect, which is exactly the ambiguity we're fixing.
    # Calculate exact expiry
    expiry = current_time + relativedelta(days=duration_days)
    
    # 4. Invalidate any previous trials for this MT5 ID
    prev_trials = await db.execute(
        select(License).filter(
            License.mt5_id == req.mt5_id,
            License.license_type == "trial",
            License.status == "active"
        )
    )
    for t in prev_trials.scalars().all():
        t.status = "expired"
        
    # 5. Create License
    import uuid
    lic = License(
        user_id=None, # Trial user might not be in DB yet fully if they bypassed, but we track by TG ID
        mt5_id=req.mt5_id,
        license_type="trial",
        status="generating",
        expiry_date=expiry,
        license_uuid=str(uuid.uuid4())
    )
    
    # To link correctly to a user, fetch user by telegram_id
    from app.models import User
    user_res = await db.execute(select(User).filter(User.telegram_id == req.telegram_user_id))
    user = user_res.scalar_one_or_none()
    if user:
        lic.user_id = user.id
        
    db.add(lic)
    await db.flush() # Need license ID
    
    # Create TrialClaim record
    claim = TrialClaim(
        telegram_id=req.telegram_user_id,
        claim_month=month_key,
        license_id=lic.id,
        mt5_id=req.mt5_id
    )
    db.add(claim)
    
    # Create TrialActivation (legacy compatibility)
    activation = TrialActivation(
        telegram_user_id=req.telegram_user_id,
        mt5_id=req.mt5_id,
        license_id=lic.id,
        expires_at=expiry,
        month_key=month_key,
        status="active"
    )
    db.add(activation)
    await db.commit()

    # 5. Enqueue compile job
    job = CompileJob(license_id=lic.id, status="pending")
    db.add(job)
    await db.commit()

    background_tasks.add_task(start_azure_vm_if_needed)
    
    return {
        "status": "success",
        "message": "Trial Approved! Preparing EA...",
        "license_id": lic.id,
        "expiry_date": expiry.strftime("%d %b %Y"),
        "duration_days": duration_days
    }
