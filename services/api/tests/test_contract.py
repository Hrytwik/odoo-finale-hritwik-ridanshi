from app.main import app


def test_openapi_lists_core_paths():
    paths = app.openapi()["paths"]
    for p in ["/api/health", "/api/auth/login", "/api/auth/me", "/api/uploads", "/api/events"]:
        assert p in paths
