from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.models import User
from app.db.session import get_db
from app.modules.dispatch import schemas as s
from app.modules.dispatch import service

router = APIRouter(tags=["dispatch"])
clerks = require_roles("dispatch", "owner")
invoice_readers = require_roles("dispatch", "accountant", "owner", "buyer")


@router.get("/dispatches", response_model=list[s.DispatchOut], dependencies=[Depends(clerks)])
def list_dispatches(state: str | None = None, db: Session = Depends(get_db)) -> list[s.DispatchOut]:
    return service.list_dispatches(db, state)


@router.post("/dispatches", response_model=s.DispatchOut, status_code=201, dependencies=[Depends(clerks)])
def create_dispatch(body: s.DispatchIn, db: Session = Depends(get_db)) -> s.DispatchOut:
    return service.dispatch_out(db, service.create_dispatch(db, body))


@router.get("/dispatches/{dispatch_code}", response_model=s.DispatchOut, dependencies=[Depends(clerks)])
def get_dispatch(dispatch_code: str, db: Session = Depends(get_db)) -> s.DispatchOut:
    return service.dispatch_out(db, service.get_dispatch_or_404(db, dispatch_code))


@router.post("/dispatches/{dispatch_code}/items", response_model=s.DispatchOut, dependencies=[Depends(clerks)])
def scan_roll(dispatch_code: str, body: s.ScanIn, db: Session = Depends(get_db)) -> s.DispatchOut:
    return service.dispatch_out(db, service.scan_roll(db, dispatch_code, body))


@router.delete("/dispatches/{dispatch_code}/items/{roll_code}", response_model=s.DispatchOut,
               dependencies=[Depends(clerks)])
def unload_roll(dispatch_code: str, roll_code: str, db: Session = Depends(get_db)) -> s.DispatchOut:
    return service.dispatch_out(db, service.unload_roll(db, dispatch_code, roll_code))


@router.post("/dispatches/{dispatch_code}/confirm", response_model=s.DispatchOut, dependencies=[Depends(clerks)])
def confirm_dispatch(dispatch_code: str, db: Session = Depends(get_db)) -> s.DispatchOut:
    return service.dispatch_out(db, service.confirm_dispatch(db, dispatch_code))


@router.get("/invoices/{invoice_no}", response_model=s.InvoiceOut)
def get_invoice(invoice_no: str, db: Session = Depends(get_db), user: User = Depends(invoice_readers)) -> s.InvoiceOut:
    return service.invoice_out(db, user, invoice_no)
