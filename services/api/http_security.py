"""HTTP-only security helpers shared by auth routes and response middleware."""

from fastapi import Response

from services.api.config import settings
from services.api.session_service import SESSION_ABSOLUTE_LIFETIME


COOKIE_MAX_AGE_SECONDS = int(SESSION_ABSOLUTE_LIFETIME.total_seconds())


def set_browser_auth_cookies(
    response: Response,
    session_secret: str,
    csrf_secret: str,
) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_secret,
        max_age=COOKIE_MAX_AGE_SECONDS,
        path="/",
        secure=settings.secure_cookies,
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_secret,
        max_age=COOKIE_MAX_AGE_SECONDS,
        path="/",
        secure=settings.secure_cookies,
        httponly=False,
        samesite="lax",
    )


def clear_browser_auth_cookies(response: Response) -> None:
    for key, httponly in (
        (settings.session_cookie_name, True),
        (settings.csrf_cookie_name, False),
    ):
        response.set_cookie(
            key=key,
            value="",
            max_age=0,
            expires=0,
            path="/",
            secure=settings.secure_cookies,
            httponly=httponly,
            samesite="lax",
        )
