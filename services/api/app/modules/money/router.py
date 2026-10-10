from fastapi import APIRouter, Depends

from app.core.auth import require_roles
from app.modules.money import examples as ex
from app.modules.money import schemas as s

router = APIRouter(tags=["money"])
accounts = require_roles("accountant", "owner")


@router.get("/money/receivables", response_model=list[s.ReceivableRow], dependencies=[Depends(accounts)])
def receivables() -> list[s.ReceivableRow]:
    return [ex.RECEIVABLE]


@router.get("/money/payables", response_model=list[s.PayableRow], dependencies=[Depends(accounts)])
def payables() -> list[s.PayableRow]:
    return [ex.PAYABLE]


@router.post("/payments/buyer", response_model=s.ReceivableRow, status_code=201, dependencies=[Depends(accounts)])
def record_buyer_payment(body: s.BuyerPaymentIn) -> s.ReceivableRow:
    return ex.RECEIVABLE


@router.post("/payments/supplier", response_model=s.PayableRow, status_code=201, dependencies=[Depends(accounts)])
def record_supplier_payment(body: s.SupplierPaymentIn) -> s.PayableRow:
    return ex.PAYABLE
