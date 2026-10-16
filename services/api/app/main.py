from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from app.config import settings
from app.core.demo_readonly import DemoReadOnly
from app.core.errors import install_error_handlers
from app.core.security_headers import SecurityHeaders
from app.modules.auth.router import router as auth_router
from app.modules.events.router import router as events_router
from app.modules.costing.router import router as costing_router
from app.modules.dispatch.router import router as dispatch_router
from app.modules.floor.router import router as floor_router
from app.modules.insights.router import router as insights_router
from app.modules.llm.router import router as llm_router
from app.modules.master.router import router as master_router
from app.modules.money.router import router as money_router
from app.modules.notices.router import router as notices_router
from app.modules.orders.router import router as orders_router
from app.modules.passport.router import router as passport_router
from app.modules.people.router import router as people_router
from app.modules.portal.router import router as portal_router
from app.modules.rolls.router import router as rolls_router
from app.modules.qc.router import router as qc_router
from app.modules.qclog.router import router as qclog_router
from app.modules.store.router import router as store_router
from app.modules.uploads.router import router as uploads_router


class Health(BaseModel):
    status: str
    demo_data: bool


def create_app() -> FastAPI:
    application = FastAPI(title="Everest Textile Mills API", version="0.1.0")
    install_error_handlers(application)
    application.add_middleware(SecurityHeaders)
    application.add_middleware(DemoReadOnly)
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
    api.include_router(floor_router)
    api.include_router(qc_router)
    api.include_router(qclog_router)
    api.include_router(passport_router)
    api.include_router(dispatch_router)
    api.include_router(money_router)
    api.include_router(costing_router)
    api.include_router(insights_router)
    api.include_router(portal_router)
    api.include_router(notices_router)
    api.include_router(rolls_router)
    api.include_router(people_router)
    api.include_router(llm_router)
    application.include_router(api)
    return application


app = create_app()
