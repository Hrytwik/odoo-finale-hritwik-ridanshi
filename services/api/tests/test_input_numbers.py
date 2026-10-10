"""Every numeric request field must refuse true/false: pydantic's default float parsing reads `true` as 1.0, which would
silently become a real quantity or price."""
import importlib
import inspect
import pkgutil
import typing

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

import app.modules as modules


def _mentions_float(annotation) -> bool:
    return annotation is float or any(_mentions_float(a) for a in typing.get_args(annotation))


def _input_float_fields():
    found = []
    for info in pkgutil.iter_modules(modules.__path__):
        try:
            mod = importlib.import_module(f"app.modules.{info.name}.schemas")
        except ModuleNotFoundError:
            continue
        for name, cls in inspect.getmembers(mod, inspect.isclass):
            if cls.__module__ != mod.__name__ or not issubclass(cls, BaseModel) or not name.endswith(("In", "Patch")):
                continue
            for field, fi in cls.model_fields.items():
                if _mentions_float(fi.annotation):
                    found.append(pytest.param(cls, field, id=f"{info.name}.{name}.{field}"))
    return found


FIELDS = _input_float_fields()


def test_the_scan_finds_the_numeric_input_fields():
    assert len(FIELDS) >= 20  # lots, movements, orders, payments, master data, floor


@pytest.mark.parametrize("cls, field", FIELDS)
def test_numeric_inputs_refuse_booleans(cls, field):
    fi = cls.model_fields[field]
    adapter = TypeAdapter(typing.Annotated[(fi.annotation, *fi.metadata)] if fi.metadata else fi.annotation)
    for raw in ("true", "false"):
        with pytest.raises(ValidationError):
            adapter.validate_json(raw)
