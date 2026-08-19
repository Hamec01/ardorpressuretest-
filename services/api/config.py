import os
from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "ARDOR Pressure Test API"
    app_version: str = "1.0.0"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    database_url: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./ardor_local.db"
    )
    
    storage_dir: Path = Path(os.getenv("STORAGE_DIR", "./storage"))
    secret_key: str = os.getenv("SECRET_KEY", "ardor-local-secret-key-change-in-prod")
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days


settings = Settings()
