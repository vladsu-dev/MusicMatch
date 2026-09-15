from __future__ import annotations

import io

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from PIL import Image
from playwright.sync_api import sync_playwright, expect

from music.constants import GENRES
from music.models import Genre


def make_photo(path):
    image = Image.new("RGB", (80, 80), "purple")
    image.save(path, format="PNG")


@override_settings(ALLOWED_HOSTS=["localhost", "127.0.0.1", "testserver"], DEBUG=True, DJANGO_DEBUG=True, SECURE_SSL_REDIRECT=False)
class BrowserNoJavascriptTests(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        super().tearDownClass()

    def setUp(self):
        for genre in GENRES:
            Genre.objects.get_or_create(name=genre)
        self.photo_path = self._temp_file("avatar.png")
        make_photo(self.photo_path)

    def _temp_file(self, name):
        import tempfile
        from pathlib import Path

        path = Path(tempfile.gettempdir()) / name
        return str(path)

    def signup(self, page, email, name):
        page.goto(self.live_server_url + "/signup/")
        page.get_by_label("Email").fill(email)
        page.get_by_label("Пароль").fill("password123")
        page.get_by_role("button", name="Зарегистрироваться").click()
        page.get_by_label("Имя").fill(name)
        page.get_by_label("Рок").check()
        page.get_by_label("Фото").set_input_files(self.photo_path)
        page.get_by_role("button", name="Сохранить").click()
        expect(page.get_by_text("Выберите")).to_be_visible()

    def test_core_flow_without_javascript(self):
        context_a = self.browser.new_context(java_script_enabled=False)
        context_b = self.browser.new_context(java_script_enabled=False)
        try:
            a = context_a.new_page()
            b = context_b.new_page()
            self.signup(a, "a@example.com", "Alice")
            self.signup(b, "b@example.com", "Bob")

            a.reload()
            a.get_by_role("button", name="Нравится").click()
            b.reload()
            b.get_by_role("button", name="Нравится").click()
            expect(b.get_by_text("У вас новый мэтч")).to_be_visible()
            b.get_by_label("Сообщение").fill("Привет из Python")
            b.get_by_role("button", name="Отправить").click()
            expect(b.frame_locator("iframe").get_by_text("Привет из Python")).to_be_visible(timeout=12000)

            a.get_by_role("link", name="Мэтчи").click()
            a.get_by_role("link", name="Bob").click()
            expect(a.frame_locator("iframe").get_by_text("Привет из Python")).to_be_visible(timeout=12000)
            a.get_by_label("Сообщение").fill("Ответ без JS")
            a.get_by_role("button", name="Отправить").click()
            expect(a.frame_locator("iframe").get_by_text("Ответ без JS")).to_be_visible(timeout=12000)
            self.assertEqual(a.locator("script").count(), 0)
        finally:
            context_a.close()
            context_b.close()
