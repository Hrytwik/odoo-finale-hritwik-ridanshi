from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from app.config import settings
from app.core.errors import install_error_handlers


class Health(BaseModel):
    status: str
    demo_data: bool


def create_app() -> FastAPI:
    application = FastAPI(title="Everest Textile Mills API", version="0.1.0")
    install_error_handlers(application)
    api = APIRouter(prefix="/api")

    @api.get("/health", response_model=Health, tags=["system"])
    def health() -> Health:
        return Health(status="ok", demo_data=settings.demo_data)

    application.include_router(api)
    return application


app = create_app()
