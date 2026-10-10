from fastapi import APIRouter, Depends

from app.core.auth import require_roles
from app.modules.dispatch import examples as ex
from app.modules.dispatch import schemas as s

router = APIRouter(tags=["dispatch"])
clerks = require_roles("dispatch", "owner")
invoice_readers = require_roles("dispatch", "accountant", "owner", "buyer")


@router.get("/dispatches", response_model=list[s.DispatchOut], dependencies=[Depends(clerks)])
def list_dispatches(state: str | None = None) -> list[s.DispatchOut]:
    return [ex.LOADING, ex.DISPATCH]


@router.post("/dispatches", response_model=s.DispatchOut, status_code=201, dependencies=[Depends(clerks)])
def create_dispatch(body: s.DispatchIn) -> s.DispatchOut:
    return ex.LOADING.model_copy(update={"rolls": [], "orders": [], "total_metres": 0})


@router.get("/dispatches/{dispatch_code}", response_model=s.DispatchOut, dependencies=[Depends(clerks)])
def get_dispatch(dispatch_code: str) -> s.DispatchOut:
    return ex.DISPATCH


@router.post("/dispatches/{dispatch_code}/items", response_model=s.DispatchOut, dependencies=[Depends(clerks)])
def scan_roll(dispatch_code: str, body: s.ScanIn) -> s.DispatchOut:
    return ex.LOADING


@router.delete("/dispatches/{dispatch_code}/items/{roll_code}", response_model=s.DispatchOut,
               dependencies=[Depends(clerks)])
def unload_roll(dispatch_code: str, roll_code: str) -> s.DispatchOut:
    return ex.LOADING


@router.post("/dispatches/{dispatch_code}/confirm", response_model=s.DispatchOut, dependencies=[Depends(clerks)])
def confirm_dispatch(dispatch_code: str) -> s.DispatchOut:
    return ex.DISPATCH


@router.get("/invoices/{invoice_no}", response_model=s.InvoiceOut, dependencies=[Depends(invoice_readers)])
def get_invoice(invoice_no: str) -> s.InvoiceOut:
    return ex.INVOICE
