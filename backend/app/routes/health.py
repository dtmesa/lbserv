from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.problems import problem_responses
from app.schemas import HealthStatus

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", operation_id="getHealth")
async def health() -> HealthStatus:
    """Liveness probe (no dependencies)."""
    return HealthStatus()


@router.get("/ready", operation_id="getReadiness", responses=problem_responses(500))
async def ready(session: AsyncSession = Depends(get_session)) -> HealthStatus:
    """Readiness probe: verifies database connectivity."""
    await session.execute(text("SELECT 1"))
    return HealthStatus()
