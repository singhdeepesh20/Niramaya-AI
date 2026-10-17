import hmac
import secrets
from urllib.parse import urlsplit

from fastapi import Request

from app.core.config import settings
from app.core.errors import APIError

CSRF_EXEMPT_PATHS = {
    "/api/v1/users/login",
    "/api/v1/users/register",
    "/api/v1/users/logout",
    "/api/v1/users/csrf",
}


def generate_csrf_token() -> str:
    """Generate a cryptographically secure random token for double-submit cookie verification."""
    return secrets.token_urlsafe(32)


def verify_csrf_origin(request: Request) -> bool:
    """Verify that the request's Origin or Referer matches an authorized frontend origin or self."""
    source_origin = request.headers.get("origin")
    if not source_origin:
        referer = request.headers.get("referer")
        if referer:
            parsed = urlsplit(referer)
            source_origin = f"{parsed.scheme}://{parsed.netloc}"

    if not source_origin:
        # If no origin/referer header was provided, proceed to token validation
        return True

    source_origin = source_origin.rstrip("/")

    # Check against configured frontend origins
    allowed = set(settings.FRONTEND_ORIGINS)

    # Support test client origins
    allowed.add("http://testserver")
    allowed.add("https://testserver")

    # Also allow server's own origin
    server_origin = f"{request.url.scheme}://{request.url.netloc}".rstrip("/")
    allowed.add(server_origin)
    # Also support localhost variants
    if "127.0.0.1" in server_origin:
        allowed.add(server_origin.replace("127.0.0.1", "localhost"))
    elif "localhost" in server_origin:
        allowed.add(server_origin.replace("localhost", "127.0.0.1"))

    return source_origin in allowed


def validate_csrf(request: Request) -> None:
    """
    Validate CSRF for state-changing HTTP requests.
    Enforces double-submit cookie matching and origin validation whenever session cookies are present.
    """
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return

    # Check if this route is exempt from pre-existing CSRF tokens
    path = request.url.path.rstrip("/")
    if path in CSRF_EXEMPT_PATHS:
        return

    # If the request explicitly presents an Authorization: Bearer token, it is authenticated
    # by explicit header (which cannot be forged cross-origin by a browser without CORS approval).
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return

    # If the client did not send a session cookie (e.g., unauthenticated request),
    # ambient-credential CSRF is not possible.
    auth_cookie = request.cookies.get(settings.COOKIE_NAME)
    if not auth_cookie:
        return

    # 1. Validate Origin / Referer if present
    if not verify_csrf_origin(request):
        raise APIError(
            403,
            "csrf_origin_mismatch",
            "Cross-site request origin is not allowed.",
        )

    # 2. Validate double-submit token match
    header_token = request.headers.get(settings.CSRF_HEADER_NAME)
    cookie_token = request.cookies.get(settings.CSRF_COOKIE_NAME)

    if not header_token or not cookie_token:
        raise APIError(
            403,
            "csrf_validation_failed",
            "CSRF token is missing from request header or cookie.",
        )

    if not hmac.compare_digest(header_token, cookie_token):
        raise APIError(
            403,
            "csrf_validation_failed",
            "CSRF token in header does not match cookie.",
        )
