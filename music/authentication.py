from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import uuid
from datetime import datetime, timezone as dt_timezone
from functools import wraps
from urllib.parse import quote

import jwt
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

from .constants import ACCESS_COOKIE, ACCESS_TOKEN_TTL, JWT_AUDIENCE, JWT_ISSUER, REFRESH_COOKIE, REFRESH_TOKEN_TTL
from .models import Account, LoginSession

LEGACY_SCRYPT_RE = re.compile(r"^[0-9a-f]{32}:[0-9a-f]{128}$", re.IGNORECASE)
DUMMY_PASSWORD_HASH = make_password(secrets.token_urlsafe(32))


def _epoch(dt) -> int:
    return int(dt.timestamp())


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _verify_legacy_scrypt(password: str, stored_hash: str) -> bool:
    if not LEGACY_SCRYPT_RE.match(stored_hash or ""):
        return False
    salt_hex, expected_hex = stored_hash.split(":", 1)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt_hex.encode("utf-8"), n=16384, r=8, p=1, dklen=64)
    return hmac.compare_digest(derived.hex(), expected_hex.lower())


def verify_password_and_upgrade(account: Account | None, password: str) -> bool:
    if account is None:
        check_password(password, DUMMY_PASSWORD_HASH)
        return False

    stored = account.password_hash
    if LEGACY_SCRYPT_RE.match(stored or ""):
        if not _verify_legacy_scrypt(password, stored):
            return False
        new_hash = make_password(password)
        Account.objects.filter(pk=account.pk, password_hash=stored).update(password_hash=new_hash)
        account.password_hash = new_hash
        return True

    return check_password(password, stored)


def issue_access_token(user_id: uuid.UUID, session_id: uuid.UUID) -> str:
    now = timezone.now()
    expires = now + ACCESS_TOKEN_TTL
    payload = {
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "sub": str(user_id),
        "sid": str(session_id),
        "iat": _epoch(now),
        "exp": _epoch(expires),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_access_token(token: str) -> tuple[uuid.UUID, uuid.UUID]:
    payload = jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=["HS256"],
        audience=JWT_AUDIENCE,
        issuer=JWT_ISSUER,
        options={"require": ["iss", "aud", "sub", "sid", "iat", "exp"]},
    )
    return uuid.UUID(str(payload["sub"])), uuid.UUID(str(payload["sid"]))


def start_session(user: Account) -> tuple[LoginSession, str]:
    refresh_token = secrets.token_hex(32)
    session = LoginSession.objects.create(
        user=user,
        refresh_hash=hash_refresh_token(refresh_token),
        expires_at=timezone.now() + REFRESH_TOKEN_TTL,
    )
    return session, refresh_token


def renew_session(refresh_token: str | None) -> tuple[LoginSession, str] | None:
    if not refresh_token or not re.fullmatch(r"[0-9a-f]{64}", refresh_token):
        return None
    refresh_hash = hash_refresh_token(refresh_token)
    with transaction.atomic():
        session = (
            LoginSession.objects.select_for_update()
            .select_related("user")
            .filter(refresh_hash=refresh_hash, expires_at__gt=timezone.now())
            .first()
        )
        if session is None:
            return None
        new_token = secrets.token_hex(32)
        session.refresh_hash = hash_refresh_token(new_token)
        session.expires_at = timezone.now() + REFRESH_TOKEN_TTL
        session.save(update_fields=["refresh_hash", "expires_at"])
        return session, new_token


def set_auth_cookies(response, user: Account, session: LoginSession, refresh_token: str):
    secure = not settings.DEBUG
    access = issue_access_token(user.id, session.id)
    remaining = max(1, int((session.expires_at - timezone.now()).total_seconds()))
    response.set_cookie(ACCESS_COOKIE, access, max_age=int(ACCESS_TOKEN_TTL.total_seconds()), httponly=True, secure=secure, samesite="Strict", path="/")
    response.set_cookie(REFRESH_COOKIE, refresh_token, max_age=remaining, httponly=True, secure=secure, samesite="Strict", path="/")
    return response


def clear_auth_cookies(response):
    secure = not settings.DEBUG
    for name in [ACCESS_COOKIE, REFRESH_COOKIE]:
        response.delete_cookie(name, path="/", samesite="Strict")
    for name in ["mm_access", "mm_refresh"]:
        response.delete_cookie(name, path="/api", samesite="Strict")
        response.delete_cookie(name, path="/", samesite="Strict")
    return response


def authenticated(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.member is None:
            return redirect(f"/login/?next={quote(request.get_full_path())}")
        return view_func(request, *args, **kwargs)

    return wrapper


class JwtCookieAuthenticationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.member = None
        request.login_session = None
        request.pending_auth = None
        request.suppress_auth_cookies = False

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.path.startswith(settings.STATIC_URL):
            return None

        access = request.COOKIES.get(ACCESS_COOKIE)
        if access:
            try:
                user_id, session_id = decode_access_token(access)
                session = (
                    LoginSession.objects.select_related("user")
                    .filter(pk=session_id, user_id=user_id, expires_at__gt=timezone.now())
                    .first()
                )
                if session is not None:
                    request.member = session.user
                    request.login_session = session
                    return None
            except Exception:
                pass

        if request.path not in {"/logout/", "/refresh/"}:
            renewed = renew_session(request.COOKIES.get(REFRESH_COOKIE))
            if renewed is not None:
                session, refresh_token = renewed
                request.member = session.user
                request.login_session = session
                request.pending_auth = (session, refresh_token)
        return None

    def process_response(self, request, response):
        if getattr(request, "pending_auth", None) and not getattr(request, "suppress_auth_cookies", False):
            session, refresh_token = request.pending_auth
            set_auth_cookies(response, session.user, session, refresh_token)
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'none'; style-src 'self'; img-src 'self' data:; frame-src 'self'; form-action 'self'; base-uri 'self'; object-src 'none'",
        )
        return response
