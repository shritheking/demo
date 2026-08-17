from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.db.database import get_db
from app.models import Product
from app.schemas import ProductResponse, ProductCreate, ProductUpdate
from app.core.security import verify_admin_key

router = APIRouter()

@router.get("/", response_model=List[ProductResponse])
async def list_products(db: AsyncSession = Depends(get_db)):
    # Public listing. Installment is a private arrangement the admin sets
    # up per-order after purchase (see /installments), never a purchasable
    # plan of its own - defense in depth so it can never leak into the
    # public catalog even if someone mistakenly names/tags a product that
    # way.
    result = await db.execute(
        select(Product).filter(
            Product.active == True,
            Product.type.in_(["EA", "VPS"]),
        )
    )
    products = result.scalars().all()
    return [p for p in products if "installment" not in (p.name or "").lower()]

@router.post("/", response_model=ProductResponse)
async def create_product(product: ProductCreate, db: AsyncSession = Depends(get_db), _admin: str = Depends(verify_admin_key)):
    db_product = Product(**product.dict())
    db.add(db_product)
    await db.commit()
    await db.refresh(db_product)
    return db_product

@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(product_id: int, product_update: ProductUpdate, db: AsyncSession = Depends(get_db), _admin: str = Depends(verify_admin_key)):
    result = await db.execute(select(Product).filter(Product.id == product_id))
    db_product = result.scalar_one_or_none()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
        
    update_data = product_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_product, key, value)
        
    await db.commit()
    await db.refresh(db_product)
    return db_product

@router.delete("/{product_id}")
async def delete_product(product_id: int, db: AsyncSession = Depends(get_db), _admin: str = Depends(verify_admin_key)):
    result = await db.execute(select(Product).filter(Product.id == product_id))
    db_product = result.scalar_one_or_none()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
        
    # Soft delete
    db_product.active = False
    await db.commit()
    return {"status": "success", "message": "Product deleted successfully"}
