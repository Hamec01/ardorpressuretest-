import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.api.config import settings
from services.api.database import Base, engine
from services.api.auth import seed_default_users
from services.api.database import SessionLocal
from services.api.http_security import clear_browser_auth_cookies
from services.api.routes import audit, auth, health, planned_tests, process, records, sync, tests

logging.basicConfig(level=logging.INFO if not settings.debug else logging.DEBUG)
logger = logging.getLogger("ardor_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    if settings.seed_default_users:
        logger.warning(
            "ARDOR_SEED_DEFAULT_USERS is enabled - seeding built-in demo accounts. "
            "This must never be set outside local development."
        )
        with SessionLocal() as db:
            seed_default_users(db)
    logger.info(f"ARDOR Pressure Test API v{settings.app_version} started.")
    yield
    logger.info("Shutting down ARDOR Pressure Test API.")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.is_local_environment else None,
    redoc_url="/redoc" if settings.is_local_environment else None,
    openapi_url="/openapi.json" if settings.is_local_environment else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def clear_rejected_browser_session_cookies(request, call_next):
    """Stop a rejected browser session from being resent on every later request."""
    response = await call_next(request)
    if response.headers.get("x-ardor-clear-session") == "1":
        del response.headers["x-ardor-clear-session"]
        clear_browser_auth_cookies(response)
    return response

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(audit.router)
app.include_router(tests.router)
app.include_router(planned_tests.router)
app.include_router(records.router)
app.include_router(sync.router)
app.include_router(process.router)
