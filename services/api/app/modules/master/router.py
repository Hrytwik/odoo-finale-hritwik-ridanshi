from collections.abc import Callable

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import STAFF, hash_password, require_roles
from app.core.errors import AppError, commit
from app.core.passwords import check_new_password
from app.db.models import Buyer, FabricRecipeLine, FabricType, Machine, Shift, Supplier, User, Worker, YarnType
from app.db.session import get_db
from app.modules.master import schemas as s

router = APIRouter(tags=["master data"])
read_any_staff = require_roles(*STAFF)
owner_only = require_roles("owner")


def _get_or_404(db: Session, model, item_id: int):
    obj = db.get(model, item_id)
    if obj is None:
        raise AppError("NOT_FOUND", f"{model.__name__} not found", status=404)
    return obj


def register_crud(path: str, model, In: type[BaseModel], Patch: type[BaseModel], OutModel: type[BaseModel],
                  order_by, read_dep: Callable = read_any_staff) -> None:
    @router.get(path, response_model=list[OutModel], name=f"list{path}")
    def list_items(db: Session = Depends(get_db), _=Depends(read_dep)):
        return db.scalars(select(model).order_by(order_by)).all()

    @router.post(path, response_model=OutModel, status_code=201, name=f"create{path}")
    def create_item(body: In, db: Session = Depends(get_db), _=Depends(owner_only)):  # type: ignore[valid-type]
        obj = model(**body.model_dump())
        db.add(obj)
        commit(db)
        db.refresh(obj)
        return obj

    @router.patch(path + "/{item_id}", response_model=OutModel, name=f"update{path}")
    def update_item(item_id: int, body: Patch, db: Session = Depends(get_db), _=Depends(owner_only)):  # type: ignore[valid-type]
        obj = _get_or_404(db, model, item_id)
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(obj, key, value)
        commit(db)
        db.refresh(obj)
        return obj


register_crud("/suppliers", Supplier, s.SupplierIn, s.SupplierPatch, s.SupplierOut, Supplier.name)
register_crud("/buyers", Buyer, s.BuyerIn, s.BuyerPatch, s.BuyerOut, Buyer.name)
register_crud("/yarn-types", YarnType, s.YarnTypeIn, s.YarnTypePatch, s.YarnTypeOut, YarnType.code)
register_crud("/machines", Machine, s.MachineIn, s.MachinePatch, s.MachineOut, Machine.code)
register_crud("/workers", Worker, s.WorkerIn, s.WorkerPatch, s.WorkerOut, Worker.code)
register_crud("/shifts", Shift, s.ShiftIn, s.ShiftPatch, s.ShiftOut, Shift.start_time)


def _fabric_out(ft: FabricType) -> s.FabricTypeOut:
    return s.FabricTypeOut(
        id=ft.id, name=ft.name, width_in=float(ft.width_in), wastage_pct=float(ft.wastage_pct),
        recipe=[s.RecipeLineOut(yarn_type_id=line.yarn_type_id, yarn_type_code=line.yarn_type.code,
                                kg_per_metre=float(line.kg_per_metre)) for line in ft.recipe_lines],
    )


def _set_recipe(db: Session, ft: FabricType, recipe: list[s.RecipeLineIn]) -> None:
    for line in recipe:
        _get_or_404(db, YarnType, line.yarn_type_id)
    ft.recipe_lines.clear()
    db.flush()
    for line in recipe:
        ft.recipe_lines.append(FabricRecipeLine(yarn_type_id=line.yarn_type_id, kg_per_metre=line.kg_per_metre))


@router.get("/fabric-types", response_model=list[s.FabricTypeOut])
def list_fabric_types(db: Session = Depends(get_db), _=Depends(read_any_staff)):
    return [_fabric_out(ft) for ft in db.scalars(select(FabricType).order_by(FabricType.name))]


@router.post("/fabric-types", response_model=s.FabricTypeOut, status_code=201)
def create_fabric_type(body: s.FabricTypeIn, db: Session = Depends(get_db), _=Depends(owner_only)):
    ft = FabricType(name=body.name, width_in=body.width_in, wastage_pct=body.wastage_pct)
    db.add(ft)
    _set_recipe(db, ft, body.recipe)
    commit(db)
    db.refresh(ft)
    return _fabric_out(ft)


@router.patch("/fabric-types/{item_id}", response_model=s.FabricTypeOut)
def update_fabric_type(item_id: int, body: s.FabricTypePatch, db: Session = Depends(get_db), _=Depends(owner_only)):
    ft = _get_or_404(db, FabricType, item_id)
    data = body.model_dump(exclude_unset=True)
    recipe = data.pop("recipe", None)
    for key, value in data.items():
        setattr(ft, key, value)
    if recipe is not None:
        _set_recipe(db, ft, body.recipe)
    commit(db)
    db.refresh(ft)
    return _fabric_out(ft)


def _check_password(password: str, username: str) -> None:
    """A login the owner creates or resets follows the same rules as one a person chooses for themselves."""
    problem = check_new_password(password, username)
    if problem:
        raise AppError("WEAK_PASSWORD", problem, field="password", status=422)


@router.get("/users", response_model=list[s.UserOut])
def list_users(db: Session = Depends(get_db), _=Depends(owner_only)):
    return db.scalars(select(User).order_by(User.username)).all()


@router.post("/users", response_model=s.UserOut, status_code=201)
def create_user(body: s.UserIn, db: Session = Depends(get_db), _=Depends(owner_only)):
    data = body.model_dump()
    _check_password(data["password"], data["username"])
    # the owner chose this password, so its owner must replace it before doing anything else
    user = User(password_hash=hash_password(data.pop("password")), must_change_password=True, **data)
    db.add(user)
    commit(db)
    db.refresh(user)
    return user


@router.patch("/users/{item_id}", response_model=s.UserOut)
def update_user(item_id: int, body: s.UserPatch, db: Session = Depends(get_db), owner: User = Depends(owner_only)):
    user = _get_or_404(db, User, item_id)
    data = body.model_dump(exclude_unset=True)
    if "password" in data:
        _check_password(data["password"], user.username)
        user.password_hash = hash_password(data.pop("password"))
        if user.id != owner.id:           # a reset for someone else is a temporary password; the owner's own is their choice
            user.must_change_password = True
    for key, value in data.items():
        setattr(user, key, value)
    commit(db)
    db.refresh(user)
    return user
