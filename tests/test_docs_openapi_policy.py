"""R1 regression guard: /docs, /redoc, /openapi.json must be closed outside local/dev/test.

services.api.main builds the FastAPI `app` singleton once, at first import, from the
process-wide `settings` singleton - so the only reliable way to compare its docs_url/
redoc_url/openapi_url across different ARDOR_ENV values is to import it fresh in a
separate subprocess per case, not via importlib.reload (which risks duplicate
SQLAlchemy table/route registration in-process).
"""
import json
import os
import subprocess
import sys
import tempfile

import pytest

_PROBE_CODE = (
    "import json\n"
    "from services.api.main import app\n"
    "print(json.dumps({'docs_url': app.docs_url, 'redoc_url': app.redoc_url, "
    "'openapi_url': app.openapi_url}))\n"
)


def _docs_urls_for(environment):
    env = os.environ.copy()
    if environment is None:
        env.pop("ARDOR_ENV", None)
    else:
        env["ARDOR_ENV"] = environment

    with tempfile.TemporaryDirectory() as storage_tmp:
        # Force these regardless of what the outer test runner's own env happens to
        # have (e.g. the outer pytest invocation's own temporary sqlite DATABASE_URL) -
        # setdefault() would silently inherit and defeat the point of this probe.
        env["STORAGE_DIR"] = storage_tmp
        # Postgres-shaped but unreachable - only app.docs_url is inspected, no query runs.
        env["DATABASE_URL"] = "postgresql://probe_user:probe_pass@127.0.0.1:1/probe_db"
        env["SECRET_KEY"] = "subprocess-probe-secret-value"
        env["ARDOR_CORS_ORIGINS"] = "https://example.ardor.internal"
        env["ARDOR_PUBLIC_ORIGIN"] = "https://example.ardor.internal"
        env["ARDOR_SHARE_SECRET"] = "subprocess-probe-share-secret-value-0123456789"

        result = subprocess.run(
            [sys.executable, "-c", _PROBE_CODE],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
    assert result.returncode == 0, f"subprocess failed: {result.stderr}"
    last_line = result.stdout.strip().splitlines()[-1]
    return json.loads(last_line)


@pytest.mark.parametrize("environment", ["local", "dev", "development", "test", "testing"])
def test_docs_open_in_local_environments(environment):
    urls = _docs_urls_for(environment)
    assert urls == {"docs_url": "/docs", "redoc_url": "/redoc", "openapi_url": "/openapi.json"}


@pytest.mark.parametrize("environment", ["staging", "production", "Staging"])
def test_docs_closed_outside_local_environments(environment):
    urls = _docs_urls_for(environment)
    assert urls == {"docs_url": None, "redoc_url": None, "openapi_url": None}


def test_docs_closed_when_ardor_env_is_unset():
    urls = _docs_urls_for(None)
    assert urls == {"docs_url": None, "redoc_url": None, "openapi_url": None}
