from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Any

from ..db.database import get_db
from ..db import crud, models

router = APIRouter(prefix="/api/apartments/{apartment_id}/rules", tags=["rules"])


class RuleCreate(BaseModel):
    name: str
    rule_type: str
    adjustment_pct: Optional[float] = None
    fixed_value: Optional[float] = None
    condition: Optional[Any] = None
    priority: int = 1
    description: Optional[str] = None


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    adjustment_pct: Optional[float] = None
    fixed_value: Optional[float] = None
    condition: Optional[Any] = None
    priority: Optional[int] = None
    description: Optional[str] = None


def _rule(r: models.PricingRule) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "rule_type": r.rule_type,
        "adjustment_pct": r.adjustment_pct,
        "fixed_value": r.fixed_value,
        "condition": r.condition,
        "priority": r.priority,
        "is_active": r.is_active,
        "description": r.description,
    }


@router.get("")
def list_rules(apartment_id: int, db: Session = Depends(get_db)):
    # Include anche regole disattive per la UI
    rules = (
        db.query(models.PricingRule)
        .filter(models.PricingRule.apartment_id == apartment_id)
        .order_by(models.PricingRule.priority)
        .all()
    )
    return [_rule(r) for r in rules]


@router.post("")
def create_rule(apartment_id: int, data: RuleCreate, db: Session = Depends(get_db)):
    if not crud.get_apartment(db, apartment_id):
        raise HTTPException(404)
    rule = models.PricingRule(apartment_id=apartment_id, **data.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _rule(rule)


@router.patch("/{rule_id}")
def update_rule(
    apartment_id: int, rule_id: int, data: RuleUpdate, db: Session = Depends(get_db)
):
    rule = (
        db.query(models.PricingRule)
        .filter(
            models.PricingRule.id == rule_id,
            models.PricingRule.apartment_id == apartment_id,
        )
        .first()
    )
    if not rule:
        raise HTTPException(404)
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(rule, k, v)
    db.commit()
    return _rule(rule)


@router.delete("/{rule_id}")
def delete_rule(apartment_id: int, rule_id: int, db: Session = Depends(get_db)):
    rule = (
        db.query(models.PricingRule)
        .filter(
            models.PricingRule.id == rule_id,
            models.PricingRule.apartment_id == apartment_id,
        )
        .first()
    )
    if not rule:
        raise HTTPException(404)
    db.delete(rule)
    db.commit()
    return {"ok": True}
