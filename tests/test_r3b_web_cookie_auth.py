"""Static guards for the R3 web cutover from localStorage Bearer to cookies."""

from pathlib import Path


WEB_SRC = Path("apps/web/src")


def _web_sources():
    return list(WEB_SRC.rglob("*.ts")) + list(WEB_SRC.rglob("*.tsx"))


def test_web_never_stores_or_reads_the_old_auth_token():
    combined = "\n".join(path.read_text() for path in _web_sources())
    assert "ardor_token" not in combined
    assert "Authorization" not in combined
    assert "Bearer " not in combined
    assert "admin123" not in combined
    assert "foreman123" not in combined
    assert "operator123" not in combined


def test_every_web_fetch_goes_through_the_single_security_wrapper():
    direct_fetches = []
    for path in _web_sources():
        text = path.read_text()
        if "fetch(" in text and path != WEB_SRC / "authFetch.ts":
            direct_fetches.append(str(path))
    assert direct_fetches == []

    wrapper = (WEB_SRC / "authFetch.ts").read_text()
    assert "window.fetch(" in wrapper
    assert "credentials: 'same-origin'" in wrapper


def test_security_wrapper_adds_csrf_only_to_unsafe_methods():
    wrapper = (WEB_SRC / "authFetch.ts").read_text()
    assert "new Set(['POST', 'PUT', 'PATCH', 'DELETE'])" in wrapper
    assert "if (UNSAFE_METHODS.has(method))" in wrapper
    assert "headers.set('X-CSRF-Token', csrfToken)" in wrapper
    assert "__Host-ardor_csrf" in wrapper
    assert "ardor_csrf" in wrapper


def test_auth_context_bootstraps_me_login_and_logout_through_cookie_fetch():
    context = (WEB_SRC / "context" / "AuthContext.tsx").read_text()
    assert "authFetch('/api/v1/auth/me')" in context
    assert "authFetch('/api/v1/auth/login'" in context
    assert "'X-Ardor-Session-Mode': 'browser'" in context
    assert "authFetch('/api/v1/auth/logout', { method: 'POST' })" in context
    assert "localStorage" not in context
