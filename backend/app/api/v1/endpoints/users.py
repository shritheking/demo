from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.db.database import get_db
from app.models import User
from pydantic import BaseModel
from datetime import datetime

from typing import Optional

class UserCreate(BaseModel):
    telegram_id: str
    name: str
    username: str
    phone: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    telegram_id: str
    name: str
    username: str
    phone: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

router = APIRouter()

@router.post("/", response_model=UserResponse)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.telegram_id == user.telegram_id))
    db_user = result.scalar_one_or_none()
    
    if db_user:
        # Update name if provided
        db_user.name = user.name
        if user.username:
            db_user.username = user.username
        await db.commit()
        await db.refresh(db_user)
        return db_user
        
    db_user = User(**user.dict())
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

@router.get("/by-id/{user_id}", response_model=UserResponse)
async def get_user_by_id(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.get("/{telegram_id}", response_model=UserResponse)
async def get_user(telegram_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

class PhoneUpdate(BaseModel):
    phone: str

@router.put("/{user_id}/phone")
async def update_phone(user_id: int, payload: PhoneUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.phone = payload.phone
    await db.commit()
    return {"status": "success"}
