import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.api.config import settings
from services.api.database import Base, engine
from services.api.auth import seed_default_users
from services.api.database import SessionLocal
from services.api.routes import audit, auth, health, process, sync, tests

logging.basicConfig(level=logging.INFO if not settings.debug else logging.DEBUG)
logger = logging.getLogger("ardor_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_default_users(db)
    logger.info(f"ARDOR Pressure Test API v{settings.app_version} started.")
    yield
    logger.info("Shutting down ARDOR Pressure Test API.")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(audit.router)
app.include_router(tests.router)
app.include_router(sync.router)
app.include_router(process.router)
