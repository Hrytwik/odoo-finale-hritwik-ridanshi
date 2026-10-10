from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")

    database_url: str = "postgresql+psycopg://localhost:5432/everest"
    test_database_url: str = "postgresql+psycopg://localhost:5432/everest_test"
    jwt_secret: str = "dev-only-secret-set-JWT_SECRET-in-env-file"
    jwt_ttl_hours: int = 12
    cookie_secure: bool = False
    upload_dir: str = "../../data/uploads"
    demo_data: bool = False
    llm_key_secret: str = ""

    # intelligence (spec 8): the spec's values are the defaults
    qc_days: int = 1                       # days a delivery date allows for quality check
    dispatch_days: int = 1                 # days it allows for dispatch
    default_efficiency: float = 0.8        # used while a stage has under efficiency_min_hours of recent run time
    efficiency_window_days: int = 7
    efficiency_min_hours: float = 1
    stage_shifts: str = ""                 # shifts run per stage, e.g. "weaving=2,dyeing=2"; a stage not listed runs all
    root_cause_min_group: int = 5
    root_cause_alpha: float = 0.05
    reorder_round_kg: int = 50

    @field_validator("stage_shifts")
    @classmethod
    def _check_stage_shifts(cls, value: str) -> str:
        for part in filter(None, (p.strip() for p in value.split(","))):
            stage, _, count = part.partition("=")
            if stage.strip() not in ("spinning", "weaving", "dyeing") or not count.strip().isdigit() or int(count) < 1:
                raise ValueError(f"STAGE_SHIFTS must look like weaving=2,dyeing=1 (stage=number of shifts); got {part!r}")
        return value


settings = Settings()
