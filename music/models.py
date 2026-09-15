from __future__ import annotations

import uuid

from django.db import models
from django.utils import timezone


class Account(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=254, unique=True)
    password_hash = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "users"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.email

    @property
    def is_authenticated(self) -> bool:
        return True


class Genre(models.Model):
    name = models.CharField(max_length=40, primary_key=True)

    class Meta:
        db_table = "genres"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Profile(models.Model):
    user = models.OneToOneField(Account, primary_key=True, db_column="user_id", on_delete=models.CASCADE, related_name="profile")
    name = models.CharField(max_length=40)
    genre = models.ForeignKey(Genre, db_column="genre", on_delete=models.PROTECT)
    photo = models.TextField()
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "profiles"
        indexes = [models.Index(fields=["genre"], name="profiles_genre_idx")]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class LoginSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(Account, db_column="user_id", on_delete=models.CASCADE, related_name="login_sessions")
    refresh_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "sessions"
        indexes = [
            models.Index(fields=["user"], name="sessions_user_idx"),
            models.Index(fields=["expires_at"], name="sessions_expiry_idx"),
        ]


class Decision(models.Model):
    pk = models.CompositePrimaryKey("user", "target")
    user = models.ForeignKey(Account, db_column="user_id", on_delete=models.CASCADE, related_name="decisions_made")
    target = models.ForeignKey(Account, db_column="target_id", on_delete=models.CASCADE, related_name="decisions_received")
    action = models.CharField(max_length=4, choices=[("like", "Нравится"), ("skip", "Пропустить")])
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "decisions"


class Match(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_low = models.ForeignKey(Account, db_column="user_low", on_delete=models.CASCADE, related_name="matches_as_low")
    user_high = models.ForeignKey(Account, db_column="user_high", on_delete=models.CASCADE, related_name="matches_as_high")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "matches"
        unique_together = [("user_low", "user_high")]
        indexes = [models.Index(fields=["user_high"], name="matches_high_idx")]
        ordering = ["-created_at"]


class Message(models.Model):
    id = models.BigAutoField(primary_key=True)
    match = models.ForeignKey(Match, db_column="match_id", on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(Account, db_column="sender_id", on_delete=models.CASCADE, related_name="sent_messages")
    text = models.CharField(max_length=2000)
    created_at = models.DateTimeField(default=timezone.now)
    submission_id = models.UUIDField(null=True, blank=True, unique=True)

    class Meta:
        db_table = "messages"
        indexes = [models.Index(fields=["match", "-id"], name="messages_match_id_idx")]
        ordering = ["id"]


class RateBucket(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    hits = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "music_rate_buckets"
