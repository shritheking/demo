"""
EA source/version management.

This is what lets the client hand over a new EA (.mq5) file later and have
it replace the compiled EA without anyone touching code:

  - Admin (web UI) uploads a new .mq5 file -> stored as a new version row.
  - Exactly one version is marked is_active at a time.
  - The windows-worker fetches the active version's source before each
    compile job (GET /current, worker-key protected) and writes it to its
    local templates/bot.mq5, which compile.py already reads from.

Only plain-text .mq5 source is handled here (no binary blobs) so it lives
directly in the database - no separate object storage is required.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update as sa_update
from typing import List, Optional
from pydantic import BaseModel
import datetime

from app.db.database import get_db
from app.models import EaTemplate
from app.core.security import verify_admin_key
from app.api.v1.endpoints.jobs import verify_worker_api_key

router = APIRouter()

MAX_TEMPLATE_SIZE_BYTES = 2 * 1024 * 1024  # 2MB is generous for a .mq5 file
ALLOWED_EXTENSIONS = (".mq5", ".mqh", ".txt")


class EaTemplateSummary(BaseModel):
    id: int
    version_label: Optional[str] = None
    filename: Optional[str] = None
    file_size: int = 0
    is_active: bool = False
    notes: Optional[str] = None
    uploaded_by: Optional[str] = None
    created_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True


class EaTemplateDetail(EaTemplateSummary):
    source_code: str


async def _deactivate_all(db: AsyncSession):
    await db.execute(sa_update(EaTemplate).values(is_active=False))


@router.post("/admin/upload", response_model=EaTemplateDetail)
async def upload_ea_template(
    file: UploadFile = File(...),
    version_label: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    uploaded_by: Optional[str] = Form(None),
    activate: bool = Form(True),
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(verify_admin_key),
):
    """Upload a new EA source file as a new version. Activated by default
    so the very next compile job picks it up - pass activate=false to
    stage it without going live yet."""
    if not file.filename or not file.filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Only .mq5 / .mqh / .txt source files are allowed")

    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    if len(raw) > MAX_TEMPLATE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File too large for an EA source template")

    try:
        source_code = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded text (.mq5 source)")

    if activate:
        await _deactivate_all(db)

    template = EaTemplate(
        version_label=version_label,
        filename=file.filename,
        source_code=source_code,
        file_size=len(raw),
        is_active=activate,
        notes=notes,
        uploaded_by=uploaded_by,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


@router.get("/admin/list", response_model=List[EaTemplateSummary])
async def list_ea_templates(db: AsyncSession = Depends(get_db), _admin: str = Depends(verify_admin_key)):
    result = await db.execute(select(EaTemplate).order_by(EaTemplate.created_at.desc()))
    return result.scalars().all()


@router.get("/admin/{template_id}", response_model=EaTemplateDetail)
async def get_ea_template(template_id: int, db: AsyncSession = Depends(get_db), _admin: str = Depends(verify_admin_key)):
    result = await db.execute(select(EaTemplate).filter(EaTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.post("/admin/{template_id}/activate", response_model=EaTemplateDetail)
async def activate_ea_template(template_id: int, db: AsyncSession = Depends(get_db), _admin: str = Depends(verify_admin_key)):
    """Make this version the one the worker fetches for the next compile job."""
    result = await db.execute(select(EaTemplate).filter(EaTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    await _deactivate_all(db)
    template.is_active = True
    await db.commit()
    await db.refresh(template)
    return template


@router.delete("/admin/{template_id}")
async def delete_ea_template(template_id: int, db: AsyncSession = Depends(get_db), _admin: str = Depends(verify_admin_key)):
    result = await db.execute(select(EaTemplate).filter(EaTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.is_active:
        raise HTTPException(status_code=400, detail="Cannot delete the active version. Activate another version first.")

    await db.delete(template)
    await db.commit()
    return {"status": "success", "message": "Template version deleted"}


@router.get("/current", response_model=EaTemplateDetail)
async def get_current_ea_template(db: AsyncSession = Depends(get_db), _worker: str = Depends(verify_worker_api_key)):
    """Called by the windows-worker before compiling to fetch whichever EA
    source version the admin currently has active."""
    result = await db.execute(select(EaTemplate).filter(EaTemplate.is_active == True).limit(1))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="No active EA template configured")
    return template
