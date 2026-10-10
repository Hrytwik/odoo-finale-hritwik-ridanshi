from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
OptText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None
PositiveQty = Annotated[float, Field(gt=0, le=1_000_000)]
Money = Annotated[float, Field(gt=0, le=100_000_000)]


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Ref(Out):
    id: int
    name: str
