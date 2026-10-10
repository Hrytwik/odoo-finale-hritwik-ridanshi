from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
OptText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None


def _not_a_boolean(value):
    # pydantic reads JSON true/false as 1.0/0.0 for a float; a quantity or price must never come from that
    if isinstance(value, bool):
        raise ValueError("Enter a number")
    return value


# Put NoBool in every numeric request field, AFTER Field(...): Annotated[float, Field(gt=0), NoBool]. In the other order
# pydantic writes "gt"/"le" into the OpenAPI schema instead of exclusiveMinimum/maximum, silently changing the contract.
NoBool = BeforeValidator(_not_a_boolean)
PositiveQty = Annotated[float, Field(gt=0, le=1_000_000), NoBool]
Money = Annotated[float, Field(gt=0, le=100_000_000), NoBool]


def _fits_bcrypt(value: str) -> str:
    # bcrypt rejects passwords longer than 72 BYTES (not characters); catch it before it becomes a 500
    if len(value.encode()) > 72:
        raise ValueError("Password is too long")
    return value


BcryptSafe = AfterValidator(_fits_bcrypt)


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Ref(Out):
    id: int
    name: str
