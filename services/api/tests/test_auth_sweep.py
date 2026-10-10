"""Every endpoint except the three public ones must refuse a request that carries no login.

This walks the API's own list of paths, so an endpoint added later without a login check fails here.
"""
import re

import pytest

from app.main import app

PUBLIC = {("GET", "/api/health"), ("POST", "/api/auth/login"), ("POST", "/api/auth/logout"), ("POST", "/api/auth/signup")}


def _endpoints():
    for path, operations in app.openapi()["paths"].items():
        for method in operations:
            if method in ("get", "post", "put", "patch", "delete"):
                yield method.upper(), path


@pytest.mark.parametrize("method,path", sorted(_endpoints()))
def test_no_login_no_answer(client, method, path):
    if (method, path) in PUBLIC:
        pytest.skip("public by design")
    url = re.sub(r"\{[^}]+\}", "X-1", path)
    client.cookies.clear()
    response = client.request(method, url, json={} if method in ("POST", "PUT", "PATCH") else None)
    assert response.status_code == 401, f"{method} {path} answered {response.status_code} without a login"


def test_the_public_list_is_exactly_what_is_meant():
    assert {e for e in _endpoints() if e in PUBLIC} == PUBLIC
