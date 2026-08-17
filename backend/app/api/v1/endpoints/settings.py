from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Dict, Any

from app.db.database import get_db
from app.models import AdminSettings
from app.core.security import verify_admin_key
from pydantic import BaseModel

router = APIRouter()

class SettingUpdate(BaseModel):
    setting_value: str

@router.get("/")
async def get_all_settings(db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(AdminSettings))
        settings = result.scalars().all()
        return {s.setting_key: s.setting_value for s in settings}
    except Exception as e:
        import logging
        logging.error(f"Error fetching all settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error occurred while fetching settings")

@router.get("/{key}")
async def get_setting(key: str, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(AdminSettings).filter(AdminSettings.setting_key == key))
        setting = result.scalars().first()
        if not setting:
            raise HTTPException(status_code=404, detail="Setting not found")
        return {"key": setting.setting_key, "value": setting.setting_value}
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"Error fetching setting '{key}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error occurred while fetching setting '{key}'")

@router.put("/{key}")
async def update_setting(key: str, payload: SettingUpdate, db: AsyncSession = Depends(get_db), _admin: str = Depends(verify_admin_key)):
    try:
        result = await db.execute(select(AdminSettings).filter(AdminSettings.setting_key == key))
        setting = result.scalars().first()
        
        if not setting:
            # Create it if it doesn't exist
            setting = AdminSettings(setting_key=key, setting_value=payload.setting_value)
            db.add(setting)
        else:
            setting.setting_value = payload.setting_value
            
        await db.commit()
        return {"status": "success", "key": key, "value": setting.setting_value}
    except Exception as e:
        await db.rollback()
        import logging
        logging.error(f"Error updating setting '{key}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error occurred while updating setting '{key}'")
