"""Fail-closed route matrix (ADR-005 §10, docs/ACCESS_PLAN_R4-R7.md stage 3).

Every API route must depend on an authentication check unless it is in the explicit
public allowlist below. A new route without auth makes this test fail.
"""
import os

os.environ.setdefault("ARDOR_ENV", "local")

from fastapi.routing import APIRoute

from services.api.main import app

PUBLIC_ROUTES = {
    ("GET", "/health"),
    ("GET", "/api/v1/health"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/desktop/login"),
    ("POST", "/api/v1/desktop/token/refresh"),
    ("GET", "/api/v1/auth/password-links/{token}"),
    ("POST", "/api/v1/auth/password-links/{token}"),
    ("GET", "/api/v1/public/shares/{token}"),
    ("GET", "/api/v1/public/shares/{token}/artifacts/{artifact_id}"),
    ("GET", "/api/v1/public/shares/{token}/zip"),
    ("GET", "/api/v1/public/shares/{token}/preview.jpg"),
    ("GET", "/api/v1/public/legacy/{log_no}"),
    ("GET", "/api/v1/public/preview-page/{kind}/{ident}"),
}
AUTH_DEPENDENCIES = {
    "role_checker",
    "require_authenticated_user",
    "require_authentication_context",
    "require_mutating_authentication_context",
}


def _dependency_names(dependant):
    names = set()
    for sub in dependant.dependencies:
        if sub.call is not None:
            names.add(getattr(sub.call, "__name__", ""))
        names |= _dependency_names(sub)
    return names


def _routes():
    """Effective (method, path, APIRoute) triples, including routes of included routers."""
    try:  # FastAPI >= 0.14x keeps included routers lazy (_IncludedRouter)
        from fastapi.routing import iter_route_contexts
        entries = [(ctx.methods or set(), ctx.path, ctx.route) for ctx in iter_route_contexts(app.routes)]
    except ImportError:
        entries = [(route.methods, route.path, route) for route in app.routes]
    for methods, path, route in entries:
        if isinstance(route, APIRoute):
            for method in set(methods) - {"HEAD", "OPTIONS"}:
                yield method, path, route


def test_route_discovery_sees_the_whole_application():
    paths = {path for _, path, _ in _routes()}
    assert len(paths) > 50
    assert "/api/v1/tests/{log_no}" in paths and "/api/v1/public/shares/{token}" in paths


def test_every_non_public_route_requires_authentication():
    unguarded = [
        f"{method} {path}"
        for method, path, route in _routes()
        if (method, path) not in PUBLIC_ROUTES and not (_dependency_names(route.dependant) & AUTH_DEPENDENCIES)
    ]
    assert unguarded == []


def test_public_allowlist_has_no_stale_entries():
    existing = {(method, path) for method, path, _ in _routes()}
    assert PUBLIC_ROUTES - existing == set()


def test_public_routes_are_only_auth_entry_points_and_share_links():
    for method, path in PUBLIC_ROUTES:
        assert path in ("/health", "/api/v1/health") or path.startswith(
            ("/api/v1/auth/login", "/api/v1/desktop/", "/api/v1/auth/password-links/", "/api/v1/public/")
        ), path
