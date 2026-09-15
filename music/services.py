from __future__ import annotations

import hashlib
import uuid
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import Case, IntegerField, Q, Value, When
from django.http import Http404
from django.utils import timezone

from .models import Account, Decision, LoginSession, Match, Message, Profile, RateBucket


def client_ip(request) -> str:
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


def allow_request(scope: str, identity: str, *, limit: int, window: timedelta) -> tuple[bool, int]:
    key = hashlib.sha256(f"{scope}:{identity}".encode("utf-8")).hexdigest()
    expires = timezone.now() + window
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM music_rate_buckets WHERE expires_at < now()")
        cursor.execute(
            """
            INSERT INTO music_rate_buckets (key, hits, expires_at)
            VALUES (%s, 1, %s)
            ON CONFLICT (key)
            DO UPDATE SET hits = music_rate_buckets.hits + 1
            RETURNING hits, expires_at
            """,
            [key, expires],
        )
        hits, expires_at = cursor.fetchone()
    retry_after = max(1, int((expires_at - timezone.now()).total_seconds()))
    return hits <= limit, retry_after


def profile_for(user: Account) -> Profile | None:
    return Profile.objects.select_related("genre", "user").filter(user=user).first()


def feed_for(user: Account, *, limit: int = 20):
    excluded_ids = Decision.objects.filter(user=user).values("target_id")
    user_profile = profile_for(user)
    qs = (
        Profile.objects.select_related("user", "genre")
        .exclude(user=user)
        .exclude(user_id__in=excluded_ids)
    )
    if user_profile is not None:
        qs = qs.annotate(
            genre_priority=Case(
                When(genre=user_profile.genre, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        ).order_by("genre_priority", "user_id")
    else:
        qs = qs.order_by("user_id")
    return list(qs[:limit])


def matches_for(user: Account):
    return (
        Match.objects.select_related("user_low", "user_high", "user_low__profile", "user_high__profile")
        .filter(Q(user_low=user) | Q(user_high=user))
        .order_by("-created_at")
    )


def match_for_user(user: Account, match_id: uuid.UUID) -> Match:
    match = (
        Match.objects.select_related("user_low", "user_high", "user_low__profile", "user_high__profile")
        .filter(pk=match_id)
        .first()
    )
    if match is None or user.id not in {match.user_low_id, match.user_high_id}:
        raise Http404("match not found")
    return match


def partner_profile(match: Match, user: Account) -> Profile:
    partner = match.user_high if match.user_low_id == user.id else match.user_low
    return partner.profile


def decide(user: Account, target_id: uuid.UUID, action: str) -> tuple[Decision, Match | None, bool]:
    if action not in {"like", "skip"}:
        raise ValidationError("Неизвестное действие.")
    if user.id == target_id:
        raise PermissionDenied("Нельзя выбрать свой профиль.")

    target_profile = Profile.objects.select_related("user").filter(user_id=target_id).first()
    if target_profile is None:
        raise Http404("profile not found")
    target = target_profile.user
    low, high = sorted([user, target], key=lambda account: account.id)

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", [f"{low.id}:{high.id}"])
        decision, created = Decision.objects.get_or_create(
            user=user,
            target=target,
            defaults={"action": action},
        )
        if not created:
            return decision, None, False
        if action != "like":
            return decision, None, True
        mutual = Decision.objects.filter(user=target, target=user, action="like").exists()
        if not mutual:
            return decision, None, True
        match, _ = Match.objects.get_or_create(user_low=low, user_high=high)
        return decision, match, True


def reset_skips(user: Account) -> int:
    deleted, _ = Decision.objects.filter(user=user, action="skip").delete()
    return deleted


def send_message(match: Match, sender: Account, text: str, submission_id: uuid.UUID) -> Message:
    if sender.id not in {match.user_low_id, match.user_high_id}:
        raise PermissionDenied("Нет доступа к чату.")
    text = text.strip()
    if not text:
        raise ValidationError("Сообщение не может быть пустым.")
    if len(text) > 2000:
        raise ValidationError("Сообщение слишком длинное.")
    try:
        message, created = Message.objects.get_or_create(
            submission_id=submission_id,
            defaults={"match": match, "sender": sender, "text": text},
        )
    except IntegrityError:
        message = Message.objects.get(submission_id=submission_id)
        created = False
    if message.match_id != match.id or message.sender_id != sender.id:
        raise PermissionDenied("Нельзя использовать чужую отправку.")
    return message


def recent_messages(match: Match, *, before: int | None = None, limit: int = 50):
    qs = Message.objects.select_related("sender", "sender__profile").filter(match=match)
    if before is not None:
        qs = qs.filter(id__lt=before)
    return list(qs.order_by("-id")[:limit])[::-1]


def account_stats(user: Account) -> dict[str, int]:
    return {
        "likes": Decision.objects.filter(user=user, action="like").count(),
        "skips": Decision.objects.filter(user=user, action="skip").count(),
        "matches": matches_for(user).count(),
        "messages": Message.objects.filter(sender=user).count(),
        "sessions": LoginSession.objects.filter(user=user, expires_at__gt=timezone.now()).count(),
    }
