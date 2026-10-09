from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live():
    """Process liveness; never touches the database."""
    return {"status": "ok"}


@router.get("/ready")
def ready(response: Response, db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        head = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:
        response.status_code = 503
        return {"status": "unavailable"}
    return {"status": "ok", "schema": head}
