import datetime as dt
from typing import Annotated, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.core.enums import Role, Stage, WorkerRole
from app.core.schemas import BcryptSafe, Money, NonBlank, NoBool, Out

Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)] | None
Rate = Annotated[float, Field(gt=0, le=100_000), NoBool]
NonNegMoney = Annotated[float, Field(ge=0, le=1_000_000), NoBool]


class SupplierIn(BaseModel):
    name: NonBlank
    phone: Phone = None
    lead_time_days: Annotated[int, Field(ge=0, le=365)] = 7


class SupplierPatch(BaseModel):
    name: NonBlank | None = None
    phone: Phone = None
    lead_time_days: Annotated[int, Field(ge=0, le=365)] | None = None


class SupplierOut(Out):
    id: int
    name: str
    phone: str | None
    lead_time_days: int


class BuyerIn(BaseModel):
    name: NonBlank
    contact_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    phone: Phone = None
    email: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None


class BuyerPatch(BuyerIn):
    name: NonBlank | None = None


class BuyerOut(Out):
    id: int
    name: str
    contact_name: str | None
    phone: str | None
    email: str | None


class YarnTypeIn(BaseModel):
    code: Code
    name: NonBlank
    colour: NonBlank
    reorder_level_kg: Annotated[float, Field(ge=0, le=1_000_000), NoBool] = 0


class YarnTypePatch(BaseModel):
    code: Code | None = None
    name: NonBlank | None = None
    colour: NonBlank | None = None
    reorder_level_kg: Annotated[float, Field(ge=0, le=1_000_000), NoBool] | None = None


class YarnTypeOut(Out):
    id: int
    code: str
    name: str
    colour: str
    reorder_level_kg: float


class RecipeLineIn(BaseModel):
    yarn_type_id: int
    kg_per_metre: Annotated[float, Field(gt=0, le=10), NoBool]


class RecipeLineOut(Out):
    yarn_type_id: int
    yarn_type_code: str
    kg_per_metre: float


def _check_recipe(recipe: list[RecipeLineIn] | None) -> None:
    if recipe is None:
        return
    ids = [line.yarn_type_id for line in recipe]
    if len(ids) != len(set(ids)):
        raise ValueError("Each yarn type can appear only once in a recipe")


class FabricTypeIn(BaseModel):
    name: NonBlank
    width_in: Annotated[float, Field(gt=0, le=200), NoBool]
    wastage_pct: Annotated[float, Field(ge=0, le=50), NoBool] = 5
    recipe: Annotated[list[RecipeLineIn], Field(min_length=1, max_length=10)]

    @model_validator(mode="after")
    def unique_yarns(self) -> Self:
        _check_recipe(self.recipe)
        return self


class FabricTypePatch(BaseModel):
    name: NonBlank | None = None
    width_in: Annotated[float, Field(gt=0, le=200), NoBool] | None = None
    wastage_pct: Annotated[float, Field(ge=0, le=50), NoBool] | None = None
    recipe: Annotated[list[RecipeLineIn], Field(min_length=1, max_length=10)] | None = None

    @model_validator(mode="after")
    def unique_yarns(self) -> Self:
        _check_recipe(self.recipe)
        return self


class FabricTypeOut(Out):
    id: int
    name: str
    width_in: float
    wastage_pct: float
    recipe: list[RecipeLineOut]


class MachineIn(BaseModel):
    code: Code
    name: NonBlank
    stage: Stage
    rated_output_per_hour: Rate
    running_cost_per_hour: NonNegMoney = 0
    active: bool = True


class MachinePatch(BaseModel):
    code: Code | None = None
    name: NonBlank | None = None
    rated_output_per_hour: Rate | None = None
    running_cost_per_hour: NonNegMoney | None = None
    active: bool | None = None


class MachineOut(Out):
    id: int
    code: str
    name: str
    stage: Stage
    rated_output_per_hour: float
    running_cost_per_hour: float
    active: bool


class WorkerIn(BaseModel):
    code: Code
    name: NonBlank
    role: WorkerRole
    daily_wage: Money
    active: bool = True


class WorkerPatch(BaseModel):
    name: NonBlank | None = None
    role: WorkerRole | None = None
    daily_wage: Money | None = None
    active: bool | None = None


class WorkerOut(Out):
    id: int
    code: str
    name: str
    role: WorkerRole
    daily_wage: float
    active: bool


class ShiftIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10)]
    start_time: dt.time
    end_time: dt.time

    @model_validator(mode="after")
    def times_differ(self) -> Self:
        if self.start_time == self.end_time:
            raise ValueError("Start and end time must differ")
        return self


class ShiftPatch(BaseModel):
    start_time: dt.time | None = None
    end_time: dt.time | None = None


class ShiftOut(Out):
    id: int
    name: str
    start_time: dt.time
    end_time: dt.time


Password = Annotated[str, StringConstraints(min_length=6, max_length=72), BcryptSafe]


class UserIn(BaseModel):
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    password: Password
    role: Role
    worker_id: int | None = None
    buyer_id: int | None = None

    @model_validator(mode="after")
    def links(self) -> Self:
        if (self.role == "buyer") != (self.buyer_id is not None):
            raise ValueError("A buyer login needs a buyer, and only buyer logins may have one")
        if self.role == "qc" and self.worker_id is None:
            raise ValueError("A QC login needs a linked worker")
        return self


class UserPatch(BaseModel):
    password: Password | None = None
    worker_id: int | None = None


class UserOut(Out):
    id: int
    username: str
    role: Role
    worker_id: int | None
    buyer_id: int | None
