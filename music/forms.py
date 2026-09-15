from __future__ import annotations

import io
import uuid

from django import forms
from PIL import Image, ImageOps, UnidentifiedImageError

from .constants import GENRES

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MAX_STORED_PHOTO_BYTES = 1_400_000


class CredentialsForm(forms.Form):
    email = forms.EmailField(max_length=254, label="Email")
    password = forms.CharField(min_length=8, max_length=128, label="Пароль", widget=forms.PasswordInput(render_value=False))

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class ProfileForm(forms.Form):
    name = forms.CharField(min_length=2, max_length=40, label="Имя")
    genre = forms.ChoiceField(choices=[(genre, genre) for genre in GENRES], label="Любимый жанр", widget=forms.RadioSelect)
    photo = forms.ImageField(label="Фото", required=False)

    def __init__(self, *args, current_photo: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_photo = current_photo
        self.fields["photo"].required = not bool(current_photo)

    def clean_name(self):
        return " ".join(self.cleaned_data["name"].strip().split())

    def clean_photo(self):
        upload = self.cleaned_data.get("photo")
        if upload is None:
            if self.current_photo:
                return self.current_photo
            raise forms.ValidationError("Загрузите фотографию профиля.")
        raw = upload.read()
        if len(raw) > MAX_IMAGE_BYTES:
            raise forms.ValidationError("Фото должно быть меньше 10 МБ.")
        try:
            image = Image.open(io.BytesIO(raw))
            image.verify()
            image = Image.open(io.BytesIO(raw))
        except (UnidentifiedImageError, OSError):
            raise forms.ValidationError("Загрузите изображение JPEG, PNG или WebP.")
        if image.width * image.height > MAX_IMAGE_PIXELS:
            raise forms.ValidationError("Фото слишком большое по размеру изображения.")
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((720, 720))
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=82, optimize=True)
        encoded = output.getvalue()
        if len(encoded) > MAX_STORED_PHOTO_BYTES:
            raise forms.ValidationError("После обработки фото получилось слишком большим.")
        import base64

        return "data:image/jpeg;base64," + base64.b64encode(encoded).decode("ascii")


class DecisionForm(forms.Form):
    action = forms.ChoiceField(choices=[("like", "Нравится"), ("skip", "Пропустить")])


class MessageForm(forms.Form):
    text = forms.CharField(max_length=2000, label="Сообщение", widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Напишите сообщение"}))
    submission_id = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.initial.get("submission_id"):
            self.initial["submission_id"] = uuid.uuid4()

    def clean_text(self):
        text = self.cleaned_data["text"].strip()
        if not text:
            raise forms.ValidationError("Сообщение не может быть пустым.")
        return text
