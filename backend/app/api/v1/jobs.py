from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from ...database import get_db
from ... import models, schemas

router = APIRouter()


@router.get("/jobs/{job_id}")
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    query = select(models.Job).where(models.Job.id == job_id)
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": job.id,
        "document_id": job.document_id,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }
