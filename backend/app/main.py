from __future__ import annotations

import os
from functools import lru_cache

from fastapi import FastAPI

from backend.app.api.v1.router import build_router
from backend.app.core.config import AppSettings, load_settings
from backend.app.core.database import create_schema, make_engine, make_session_factory
from backend.app.services.case_service import CaseService
from backend.chimera_model.benchmark import BenchmarkProbabilityModel, INTERACTION_FEATURE_SCHEMA_VERSION
from backend.chimera_simulator.config import SimulatorConfig


def create_app(database_url: str | None = None, *, create_tables: bool = True) -> FastAPI:
    settings = load_settings()
    if database_url is not None:
        settings = AppSettings(database_url=database_url, api_environment=settings.api_environment, model_artifact_path=settings.model_artifact_path, simulator_config_path=settings.simulator_config_path)
    engine = make_engine(settings.database_url)
    if create_tables:
        create_schema(engine)
    session_factory = make_session_factory(engine)
    simulator_config = SimulatorConfig.from_file(settings.simulator_config_path)

    @lru_cache(maxsize=1)
    def compatibility_status() -> str:
        try:
            BenchmarkProbabilityModel.load(settings.model_artifact_path, expected_simulator_version=simulator_config.simulator_version, expected_config_hash=simulator_config.config_hash)
            return "compatible"
        except Exception:
            return "incompatible"

    def service_factory(session):
        return CaseService(session, simulator_config, settings.model_artifact_path)

    def health_factory():
        return engine, settings, compatibility_status()

    app = FastAPI(title="CHIMERA API", version="1.0.0")
    router = build_router(session_factory=session_factory, service_factory=service_factory, health_factory=health_factory)
    app.include_router(router, prefix="/api/v1")
    app.include_router(router, prefix="")
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.settings = settings
    return app


# Keep module importable for local tests and schema tooling when PostgreSQL's
# optional driver is not installed. Deployments set DATABASE_URL explicitly.
app = create_app(database_url=os.getenv("DATABASE_URL", "sqlite+pysqlite:///:memory:"), create_tables=False)
