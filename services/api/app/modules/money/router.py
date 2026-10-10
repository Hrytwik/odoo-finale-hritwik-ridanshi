from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.modules.money import schemas as s
from app.modules.money import service

router = APIRouter(tags=["money"])
accounts = require_roles("accountant", "owner")


@router.get("/money/receivables", response_model=list[s.ReceivableRow], dependencies=[Depends(accounts)])
def receivables(db: Session = Depends(get_db)) -> list[s.ReceivableRow]:
    return service.receivables(db)


@router.get("/money/payables", response_model=list[s.PayableRow], dependencies=[Depends(accounts)])
def payables(db: Session = Depends(get_db)) -> list[s.PayableRow]:
    return service.payables(db)


@router.post("/payments/buyer", response_model=s.ReceivableRow, status_code=201, dependencies=[Depends(accounts)])
def record_buyer_payment(body: s.BuyerPaymentIn, db: Session = Depends(get_db)) -> s.ReceivableRow:
    return service.record_buyer_payment(db, body)


@router.post("/payments/supplier", response_model=s.PayableRow, status_code=201, dependencies=[Depends(accounts)])
def record_supplier_payment(body: s.SupplierPaymentIn, db: Session = Depends(get_db)) -> s.PayableRow:
    return service.record_supplier_payment(db, body)
