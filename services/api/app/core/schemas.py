from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
OptText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None
PositiveQty = Annotated[float, Field(gt=0, le=1_000_000)]
Money = Annotated[float, Field(gt=0, le=100_000_000)]


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
