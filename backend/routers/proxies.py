from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
import models, schemas

router = APIRouter(prefix="/api/proxies", tags=["proxies"])


@router.get("/", response_model=List[schemas.ProxyOut])
def list_proxies(db: Session = Depends(get_db)):
    return db.query(models.Proxy).order_by(models.Proxy.id.desc()).all()


@router.post("/", response_model=schemas.ProxyOut, status_code=201)
def create_proxy(data: schemas.ProxyCreate, db: Session = Depends(get_db)):
    proxy = models.Proxy(**data.model_dump())
    db.add(proxy)
    db.commit()
    db.refresh(proxy)
    return proxy


@router.patch("/{proxy_id}", response_model=schemas.ProxyOut)
def update_proxy(proxy_id: int, data: schemas.ProxyUpdate, db: Session = Depends(get_db)):
    proxy = db.query(models.Proxy).filter(models.Proxy.id == proxy_id).first()
    if not proxy:
        raise HTTPException(status_code=404, detail="Proxy not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(proxy, field, value)
    db.commit()
    db.refresh(proxy)
    return proxy


@router.delete("/{proxy_id}", status_code=204)
def delete_proxy(proxy_id: int, db: Session = Depends(get_db)):
    proxy = db.query(models.Proxy).filter(models.Proxy.id == proxy_id).first()
    if not proxy:
        raise HTTPException(status_code=404, detail="Proxy not found")
    db.delete(proxy)
    db.commit()
