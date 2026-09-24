import os
from pathlib import Path
from urllib.parse import urlparse
from pydantic import BaseModel, model_validator

INSECURE_DEFAULT_SECRET = "ardor-local-secret-key-change-in-prod"
LOCAL_ENVIRONMENTS = ("local", "dev", "development", "test", "testing")
DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
DEFAULT_PUBLIC_ORIGIN = "http://localhost:5173"


class Settings(BaseModel):
    app_name: str = "ARDOR Pressure Test API"
    app_version: str = "1.0.0"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    # ARDOR_ENV controls how strictly startup validates the rest of the config below.
    # Fail-closed: an unset ARDOR_ENV is NOT treated as local. Only an explicit
    # local/dev/test value opts out of the strict checks below - anything else,
    # including a missing variable, is treated as a real server deployment.
    environment: str = os.getenv("ARDOR_ENV", "")

    database_url: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./ardor_local.db"
    )

    storage_dir: Path = Path(os.getenv("STORAGE_DIR", "./storage"))
    secret_key: str = os.getenv("SECRET_KEY", INSECURE_DEFAULT_SECRET)
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Automatic seeding of the built-in demo accounts (admin/foreman_matti/operator_pekka)
    # is opt-in and intended for local development only; see main.py lifespan.
    seed_default_users: bool = os.getenv("ARDOR_SEED_DEFAULT_USERS", "false").lower() == "true"

    # Comma-separated browser origins allowed to call the API with credentials.
    cors_allowed_origins: str = os.getenv("ARDOR_CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    public_origin: str = os.getenv("ARDOR_PUBLIC_ORIGIN", DEFAULT_PUBLIC_ORIGIN)

    @property
    def is_local_environment(self) -> bool:
        return self.environment.strip().lower() in LOCAL_ENVIRONMENTS

    @property
    def cors_origin_list(self) -> list:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def session_cookie_name(self) -> str:
        return "ardor_session" if self.is_local_environment else "__Host-ardor_session"

    @property
    def csrf_cookie_name(self) -> str:
        return "ardor_csrf" if self.is_local_environment else "__Host-ardor_csrf"

    @property
    def secure_cookies(self) -> bool:
        return not self.is_local_environment

    @model_validator(mode="after")
    def _enforce_server_mode_requirements(self) -> "Settings":
        """Fail closed on startup for any non-local ARDOR_ENV with unsafe configuration.

        A misconfigured server must refuse to start with a clear error rather than
        silently running with a known default secret, a local SQLite file, automatic
        seeding of known accounts, or an unrestricted/default CORS origin list.
        """
        if self.is_local_environment:
            return self

        problems = []
        if self.secret_key == INSECURE_DEFAULT_SECRET:
            problems.append(
                "SECRET_KEY is not set (falls back to the insecure development default)"
            )
        if self.database_url.startswith("sqlite"):
            problems.append(
                "DATABASE_URL resolves to SQLite "
                "(expected PostgreSQL for a server deployment)"
            )
        if self.seed_default_users:
            problems.append(
                "ARDOR_SEED_DEFAULT_USERS is enabled outside a local/dev environment "
                "(would auto-create accounts with known passwords on every restart)"
            )
        origins = self.cors_origin_list
        if not origins:
            problems.append("ARDOR_CORS_ORIGINS resolves to an empty origin list")
        elif any(o == "*" for o in origins):
            problems.append(
                "ARDOR_CORS_ORIGINS contains a wildcard '*' origin "
                "(rejected in any position in the list, not only as the sole value)"
            )
        elif self.cors_allowed_origins.strip() == DEFAULT_CORS_ORIGINS:
            problems.append(
                "ARDOR_CORS_ORIGINS was not explicitly set (still the local-dev default "
                f"'{DEFAULT_CORS_ORIGINS}') - a server deployment must set its real origin(s)"
            )

        try:
            parsed_origin = urlparse(self.public_origin)
            parsed_port = parsed_origin.port
        except (TypeError, ValueError):
            parsed_origin = None
            parsed_port = None
        if (
            parsed_origin is None
            or parsed_origin.scheme != "https"
            or not parsed_origin.hostname
            or parsed_origin.path
            or parsed_origin.params
            or parsed_origin.query
            or parsed_origin.fragment
            or parsed_origin.username
            or parsed_origin.password
            or self.public_origin != self.public_origin.strip()
            or parsed_port == 0
        ):
            problems.append(
                "ARDOR_PUBLIC_ORIGIN must be one canonical HTTPS origin without "
                "credentials, path, query, or fragment"
            )

        if problems:
            env_label = self.environment if self.environment else "<unset>"
            raise RuntimeError(
                f"Refusing to start: ARDOR_ENV='{env_label}' requires safe "
                "configuration, but found: " + "; ".join(problems)
            )
        return self


settings = Settings()
