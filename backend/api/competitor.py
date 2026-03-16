from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..db.database import get_db
from ..db import models

router = APIRouter(prefix="/api/competitor", tags=["competitor"])


@router.get("/snapshots")
def get_snapshots(zone: str = None, limit: int = 60, db: Session = Depends(get_db)):
    query = db.query(models.CompetitorSnapshot).order_by(
        desc(models.CompetitorSnapshot.snapshot_date)
    )
    if zone:
        query = query.filter(models.CompetitorSnapshot.zone == zone)
    snapshots = query.limit(limit).all()
    return [
        {
            "id": s.id,
            "zone": s.zone,
            "snapshot_date": s.snapshot_date.isoformat(),
            "avg_price": s.avg_price,
            "min_price": s.min_price,
            "max_price": s.max_price,
            "median_price": s.median_price,
            "sample_count": s.sample_count,
            "source": s.source,
        }
        for s in snapshots
    ]


@router.get("/zones")
def get_zones(db: Session = Depends(get_db)):
    zones = db.query(models.CompetitorSnapshot.zone).distinct().all()
    return [z[0] for z in zones]
