from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from app.config import settings
from app.core.errors import install_error_handlers
from app.modules.auth.router import router as auth_router
from app.modules.events.router import router as events_router
from app.modules.master.router import router as master_router
from app.modules.orders.router import router as orders_router
from app.modules.store.router import router as store_router
from app.modules.uploads.router import router as uploads_router


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

    api.include_router(auth_router)
    api.include_router(events_router)
    api.include_router(uploads_router)
    api.include_router(master_router)
    api.include_router(store_router)
    api.include_router(orders_router)
    application.include_router(api)
    return application


app = create_app()
