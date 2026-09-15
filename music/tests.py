from __future__ import annotations

import base64
import hashlib
import io
import uuid
from datetime import timedelta

import jwt
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from music.authentication import ACCESS_COOKIE, REFRESH_COOKIE, hash_refresh_token, issue_access_token
from music.constants import GENRES
from music.models import Account, Decision, Genre, LoginSession, Match, Message, Profile
from music.services import decide


def image_file(name="avatar.png"):
    data = io.BytesIO()
    Image.new("RGB", (40, 40), "purple").save(data, format="PNG")
    data.seek(0)
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(name, data.read(), content_type="image/png")


def photo_data_url():
    data = io.BytesIO()
    Image.new("RGB", (12, 12), "blue").save(data, format="JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(data.getvalue()).decode("ascii")


def legacy_hash(password: str, salt_hex: str = "0123456789abcdef0123456789abcdef") -> str:
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt_hex.encode("utf-8"), n=16384, r=8, p=1, dklen=64)
    return f"{salt_hex}:{digest.hex()}"


@override_settings(ALLOWED_HOSTS=["testserver", "127.0.0.1", "localhost"], DJANGO_DEBUG=True, DEBUG=True)
class MusicAppTests(TestCase):
    def setUp(self):
        for genre in GENRES:
            Genre.objects.get_or_create(name=genre)

    def create_account(self, email="a@example.com", password="password123", *, name=None, genre="Рок"):
        account = Account.objects.create(email=email, password_hash=make_password(password))
        if name:
            Profile.objects.create(user=account, name=name, genre_id=genre, photo=photo_data_url())
        return account

    def login(self, email="a@example.com", password="password123"):
        return self.client.post(reverse("login"), {"email": email, "password": password})

    def test_signup_sets_jwt_cookies_and_profile_saves(self):
        response = self.client.post(reverse("signup"), {"email": "New@Example.COM", "password": "password123"})
        self.assertEqual(response.status_code, 302)
        self.assertIn(ACCESS_COOKIE, response.cookies)
        self.assertIn(REFRESH_COOKIE, response.cookies)
        account = Account.objects.get(email="new@example.com")
        self.assertTrue(check_password("password123", account.password_hash))

        response = self.client.post(reverse("profile"), {"name": "Влад", "genre": "Рок", "photo": image_file()}, follow=True)
        self.assertContains(response, "Выберите")
        self.assertTrue(Profile.objects.filter(user=account, name="Влад").exists())

    def test_login_rejects_bad_password_and_external_next(self):
        self.create_account(email="a@example.com")
        response = self.client.post(reverse("login"), {"email": "a@example.com", "password": "wrong-password", "next": "https://evil.example/"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Неверный")
        response = self.client.post(reverse("login"), {"email": "a@example.com", "password": "password123", "next": "https://evil.example/"})
        self.assertEqual(response["Location"], "/")

    def test_legacy_password_upgrades_after_successful_login(self):
        account = Account.objects.create(email="old@example.com", password_hash=legacy_hash("old-password"))
        response = self.client.post(reverse("login"), {"email": "old@example.com", "password": "old-password"})
        self.assertEqual(response.status_code, 302)
        account.refresh_from_db()
        self.assertNotIn(":", account.password_hash)
        self.assertTrue(check_password("old-password", account.password_hash))

    def test_jwt_validation_and_refresh_rotation(self):
        account = self.create_account(email="jwt@example.com", name="Jwt")
        session = LoginSession.objects.create(user=account, refresh_hash=hash_refresh_token("a" * 64), expires_at=timezone.now() + timedelta(days=1))
        old_access = issue_access_token(account.id, session.id)
        self.client.cookies[ACCESS_COOKIE] = old_access
        response = self.client.get(reverse("account"))
        self.assertContains(response, "jwt@example.com")

        bad = jwt.encode({"sub": str(account.id), "sid": str(session.id), "exp": timezone.now() + timedelta(minutes=5)}, "wrong", algorithm="HS256")
        self.client.cookies[ACCESS_COOKIE] = bad
        self.client.cookies[REFRESH_COOKIE] = "a" * 64
        response = self.client.get(reverse("account"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(REFRESH_COOKIE, response.cookies)
        session.refresh_from_db()
        self.assertNotEqual(session.refresh_hash, hash_refresh_token("a" * 64))

    def test_feed_decisions_match_and_messages(self):
        alice = self.create_account("alice@example.com", name="Alice", genre="Рок")
        bob = self.create_account("bob@example.com", name="Bob", genre="Рок")
        carl = self.create_account("carl@example.com", name="Carl", genre="Джаз")
        self.login("alice@example.com")
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Bob")
        self.assertContains(response, "Carl")

        decision, match, created = decide(alice, bob.id, "like")
        self.assertIsNone(match)
        decision, match, created = decide(bob, alice.id, "like")
        self.assertIsNotNone(match)
        self.assertEqual(Match.objects.count(), 1)
        again = decide(bob, alice.id, "like")
        self.assertFalse(again[2])
        self.assertEqual(Match.objects.count(), 1)

        match = Match.objects.get()
        response = self.client.post(reverse("chat", args=[match.id]), {"text": "<b>hello</b>", "submission_id": str(uuid.uuid4())})
        self.assertEqual(response.status_code, 302)
        response = self.client.get(reverse("chat_messages", args=[match.id]))
        self.assertContains(response, "&lt;b&gt;hello&lt;/b&gt;")

    def test_profile_photo_is_preserved_when_editing(self):
        self.create_account("a@example.com", name="Old")
        self.login("a@example.com")
        old_photo = Profile.objects.get(name="Old").photo
        response = self.client.post(reverse("profile"), {"name": "New", "genre": "Инди"})
        self.assertEqual(response.status_code, 302)
        profile = Profile.objects.get(name="New")
        self.assertEqual(profile.photo, old_photo)

    def test_csrf_and_csp_are_enabled(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("signup"), {"email": "x@example.com", "password": "password123"})
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse("home"))
        self.assertIn("script-src 'none'", response.headers["Content-Security-Policy"])

    def test_logout_requires_post_and_revokes_session(self):
        account = self.create_account("logout@example.com")
        self.login("logout@example.com")
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertEqual(LoginSession.objects.filter(user=account).count(), 1)
        response = self.client.post(reverse("logout"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(LoginSession.objects.filter(user=account).count(), 0)

    def test_rate_limit_blocks_repeated_auth_attempts(self):
        for idx in range(30):
            response = self.client.post(reverse("login"), {"email": f"missing{idx}@example.com", "password": "password123"})
            self.assertNotEqual(response.status_code, 429)
        response = self.client.post(reverse("login"), {"email": "blocked@example.com", "password": "password123"})
        self.assertEqual(response.status_code, 429)

    def test_health(self):
        response = self.client.get(reverse("health"))
        self.assertJSONEqual(response.content, {"ok": True})
