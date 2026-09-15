from __future__ import annotations

import uuid
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed, JsonResponse
from django.middleware.csrf import rotate_token
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.contrib.auth.hashers import make_password

from .authentication import authenticated, clear_auth_cookies, renew_session, set_auth_cookies, start_session, verify_password_and_upgrade
from .constants import REFRESH_COOKIE
from .forms import CredentialsForm, DecisionForm, MessageForm, ProfileForm
from .models import Account, Genre, LoginSession, Profile
from .services import account_stats, allow_request, client_ip, decide, feed_for, match_for_user, matches_for, partner_profile, profile_for, recent_messages, reset_skips, send_message


def safe_next(request) -> str:
    url = request.POST.get("next") or request.GET.get("next") or "/"
    if url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}, require_https=not settings.DEBUG):
        return url
    return "/"


def rate_limited(request, scope: str, *, limit: int, window: timedelta):
    ok, retry_after = allow_request(scope, client_ip(request), limit=limit, window=window)
    if ok:
        return None
    response = render(request, "music/error.html", {"title": "Слишком много запросов", "message": "Подождите немного и попробуйте ещё раз."}, status=429)
    response.headers["Retry-After"] = str(retry_after)
    return response


@require_GET
def home(request):
    if request.member is None:
        return render(request, "music/home_guest.html")
    if profile_for(request.member) is None:
        return redirect("profile")
    return render(request, "music/feed.html", {"profiles": feed_for(request.member)})


@require_http_methods(["GET", "POST"])
def signup(request):
    if request.member is not None:
        return redirect("home")
    form = CredentialsForm(request.POST or None)
    if request.method == "POST":
        limited = rate_limited(request, "auth", limit=30, window=timedelta(minutes=15))
        if limited:
            return limited
        if form.is_valid():
            try:
                with transaction.atomic():
                    account = Account.objects.create(email=form.cleaned_data["email"], password_hash=make_password(form.cleaned_data["password"]))
                    session, refresh_token = start_session(account)
            except IntegrityError:
                form.add_error("email", "Пользователь с таким email уже существует.")
            else:
                rotate_token(request)
                response = redirect("profile")
                request.suppress_auth_cookies = True
                return set_auth_cookies(response, account, session, refresh_token)
    return render(request, "music/auth.html", {"form": form, "mode": "signup", "next": safe_next(request)})


@require_http_methods(["GET", "POST"])
def login(request):
    if request.member is not None:
        return redirect("home")
    form = CredentialsForm(request.POST or None)
    if request.method == "POST":
        limited = rate_limited(request, "auth", limit=30, window=timedelta(minutes=15))
        if limited:
            return limited
        if form.is_valid():
            account = Account.objects.filter(email=form.cleaned_data["email"]).first()
            if account and verify_password_and_upgrade(account, form.cleaned_data["password"]):
                session, refresh_token = start_session(account)
                rotate_token(request)
                request.suppress_auth_cookies = True
                return set_auth_cookies(redirect(safe_next(request)), account, session, refresh_token)
            form.add_error(None, "Неверный email или пароль.")
    return render(request, "music/auth.html", {"form": form, "mode": "login", "next": safe_next(request)})


@require_POST
def logout(request):
    refresh = request.COOKIES.get(REFRESH_COOKIE)
    if request.login_session is not None:
        LoginSession.objects.filter(pk=request.login_session.pk).delete()
    elif refresh:
        from .authentication import hash_refresh_token

        LoginSession.objects.filter(refresh_hash=hash_refresh_token(refresh)).delete()
    rotate_token(request)
    request.suppress_auth_cookies = True
    return clear_auth_cookies(redirect("home"))


@require_POST
def refresh(request):
    renewed = renew_session(request.COOKIES.get(REFRESH_COOKIE))
    request.suppress_auth_cookies = True
    if renewed is None:
        return clear_auth_cookies(HttpResponse("Сессия истекла", status=401))
    session, refresh_token = renewed
    return set_auth_cookies(redirect("home"), session.user, session, refresh_token)


@authenticated
@require_http_methods(["GET", "POST"])
def profile(request):
    current = profile_for(request.member)
    initial = {}
    if current is not None:
        initial = {"name": current.name, "genre": current.genre_id}
    form = ProfileForm(request.POST or None, request.FILES or None, initial=initial, current_photo=current.photo if current else None)
    if request.method == "POST":
        limited = rate_limited(request, "profile", limit=30, window=timedelta(minutes=15))
        if limited:
            return limited
        if form.is_valid():
            Genre.objects.get_or_create(name=form.cleaned_data["genre"])
            Profile.objects.update_or_create(
                user=request.member,
                defaults={
                    "name": form.cleaned_data["name"],
                    "genre_id": form.cleaned_data["genre"],
                    "photo": form.cleaned_data["photo"],
                    "updated_at": timezone.now(),
                },
            )
            messages.success(request, "Профиль сохранён.")
            return redirect("home")
    return render(request, "music/profile.html", {"form": form, "profile": current})


@authenticated
@require_GET
def account(request):
    return render(request, "music/account.html", {"stats": account_stats(request.member), "profile": profile_for(request.member)})


@authenticated
@require_POST
def decision(request, target_id: uuid.UUID):
    if profile_for(request.member) is None:
        return redirect("profile")
    limited = rate_limited(request, "decision", limit=90, window=timedelta(minutes=15))
    if limited:
        return limited
    form = DecisionForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest("Некорректное действие")
    _, match, created = decide(request.member, target_id, form.cleaned_data["action"])
    if match is not None:
        messages.success(request, "У вас новый мэтч! Можно написать сообщение.")
        return redirect("chat", match_id=match.id)
    if not created:
        messages.info(request, "Этот профиль уже был обработан.")
    return redirect("home")


@authenticated
@require_POST
def reset_feed(request):
    count = reset_skips(request.member)
    messages.success(request, f"Сброшено пропусков: {count}.")
    return redirect("home")


@authenticated
@require_GET
def matches(request):
    return render(request, "music/matches.html", {"matches": matches_for(request.member)})


@authenticated
@require_http_methods(["GET", "POST"])
def chat(request, match_id: uuid.UUID):
    match = match_for_user(request.member, match_id)
    partner = partner_profile(match, request.member)
    if request.method == "POST":
        limited = rate_limited(request, "message", limit=60, window=timedelta(minutes=15))
        if limited:
            return limited
        form = MessageForm(request.POST)
        if form.is_valid():
            send_message(match, request.member, form.cleaned_data["text"], form.cleaned_data["submission_id"])
            return redirect("chat", match_id=match.id)
    else:
        form = MessageForm()
    return render(request, "music/chat.html", {"match": match, "partner": partner, "form": form})


@require_GET
def chat_messages(request, match_id: uuid.UUID):
    if request.member is None:
        return render(request, "music/session_expired.html", status=401)
    match = match_for_user(request.member, match_id)
    before_value = request.GET.get("before")
    before = None
    if before_value:
        if not before_value.isdecimal():
            return HttpResponseBadRequest("bad cursor")
        before = int(before_value)
    messages_list = recent_messages(match, before=before)
    return render(
        request,
        "music/messages.html",
        {"match": match, "messages_list": messages_list, "live": before is None, "member": request.member},
    )


@require_GET
def health(request):
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return JsonResponse({"ok": True})


def csrf_failure(request, reason=""):
    return render(request, "music/error.html", {"title": "Форма устарела", "message": "Обновите страницу и попробуйте ещё раз."}, status=403)


def bad_request(request, exception=None):
    return render(request, "music/error.html", {"title": "Некорректный запрос", "message": "Проверьте адрес страницы."}, status=400)


def permission_denied(request, exception=None):
    return render(request, "music/error.html", {"title": "Нет доступа", "message": "У вас нет доступа к этой странице."}, status=403)


def not_found(request, exception=None):
    return render(request, "music/error.html", {"title": "Страница не найдена", "message": "Такой страницы нет."}, status=404)


def server_error(request):
    return HttpResponse("Внутренняя ошибка сервера", status=500, content_type="text/plain; charset=utf-8")
