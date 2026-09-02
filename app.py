"""Точка входа Flask-приложения MusicMatch."""

import logging
import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt_identity,
    jwt_required,
)
from werkzeug.middleware.proxy_fix import ProxyFix

from backend.auth import login_user, register_user
from backend.database import SessionLocal, init_db
from backend.models import User
from backend.yandex_auth_flow import auth_flow_manager
from backend.yandex_music_service import (
    disconnect as yandex_disconnect,
    get_connection_status as yandex_get_connection_status,
    save_token as yandex_save_token,
    sync_favorite_artists as yandex_sync_favorite_artists,
)

load_dotenv()
logger = logging.getLogger(__name__)


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Environment variable {name!r} is required. "
            "Copy .env.template to .env and fill in the required values."
        )
    return value


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="frontend/templates",
        static_folder="frontend/static",
    )

    app.config.update(
        SECRET_KEY=_required_env("SECRET_KEY"),
        JWT_SECRET_KEY=_required_env("JWT_SECRET_KEY"),
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(hours=24),
    )

    # Cookies are not currently used for JWT transport, but these defaults
    # keep Flask session cookies safe if sessions are introduced later.
    app.config.update(
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )

    if os.getenv("TRUST_PROXY", "false").lower() == "true":
        # One Nginx reverse proxy is expected in the documented deployment.
        # Do not enable this unless the application is actually behind a
        # trusted proxy that overwrites the X-Forwarded-* headers.
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=1,
            x_proto=1,
            x_host=1,
            x_prefix=1,
        )

    cors_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()]
    if cors_origins:
        CORS(app, resources={r"/api/*": {"origins": cors_origins}})

    JWTManager(app)
    init_db()

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/register", methods=["POST"])
    def api_register():
        data = request.get_json(silent=True) or {}

        required_fields = ["username", "email", "password", "gender"]
        missing = [field for field in required_fields if not data.get(field)]
        if missing:
            return jsonify({"error": f"Обязательные поля: {', '.join(missing)}"}), 400

        if len(data["password"]) < 8:
            return jsonify({"error": "Пароль должен быть минимум 8 символов"}), 400

        result = register_user(
            username=data["username"],
            email=data["email"],
            password=data["password"],
            gender=data["gender"],
            age=data.get("age"),
            bio=data.get("bio", ""),
        )

        if not result["success"]:
            return jsonify({"error": result["error"]}), 400

        access_token = create_access_token(identity=result["user_id"])
        return jsonify({
            "message": "Регистрация успешна",
            "access_token": access_token,
            "user_id": result["user_id"],
        }), 201

    @app.route("/api/login", methods=["POST"])
    def api_login():
        data = request.get_json(silent=True) or {}
        if not data.get("email") or not data.get("password"):
            return jsonify({"error": "Email и пароль обязательны"}), 400

        result = login_user(email=data["email"], password=data["password"])
        if not result["success"]:
            return jsonify({"error": result["error"]}), 401

        access_token = create_access_token(identity=result["user_id"])
        return jsonify({
            "message": "Вход выполнен",
            "access_token": access_token,
            "user_id": result["user_id"],
        }), 200

    @app.route("/api/profile", methods=["GET"])
    @jwt_required()
    def api_profile():
        current_user_id = get_jwt_identity()
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == current_user_id).first()
            if not user:
                return jsonify({"error": "Пользователь не найден"}), 404

            return jsonify({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "gender": user.gender,
                "age": user.age,
                "bio": user.bio,
                "avatar_url": user.avatar_url,
            }), 200
        finally:
            db.close()

    # Yandex Music integration.
    # The third-party library is LGPL-3.0; see THIRD_PARTY_NOTICES.md.
    @app.route("/api/yandex-music/connect", methods=["POST"])
    @jwt_required()
    def api_yandex_music_connect():
        user_id = get_jwt_identity()
        auth_flow_manager.start(user_id)
        status = auth_flow_manager.get_status(user_id, wait_seconds=3.0)
        return jsonify(status), 200

    @app.route("/api/yandex-music/connect/status", methods=["GET"])
    @jwt_required()
    def api_yandex_music_connect_status():
        user_id = get_jwt_identity()
        status = auth_flow_manager.get_status(user_id, wait_seconds=2.0)

        if status.get("status") == "success":
            token = auth_flow_manager.pop_token_if_ready(user_id)
            if token:
                db = SessionLocal()
                try:
                    yandex_save_token(db, user_id, token)
                finally:
                    db.close()
            return jsonify({"status": "connected"}), 200

        if status.get("status") == "error":
            auth_flow_manager.clear_error(user_id)

        return jsonify(status), 200

    @app.route("/api/yandex-music/status", methods=["GET"])
    @jwt_required()
    def api_yandex_music_status():
        user_id = get_jwt_identity()
        db = SessionLocal()
        try:
            return jsonify(yandex_get_connection_status(db, user_id)), 200
        finally:
            db.close()

    @app.route("/api/yandex-music/sync", methods=["POST"])
    @jwt_required()
    def api_yandex_music_sync():
        user_id = get_jwt_identity()
        force = bool((request.get_json(silent=True) or {}).get("force", False))
        db = SessionLocal()
        try:
            result = yandex_sync_favorite_artists(db, user_id, force=force)
        finally:
            db.close()

        if not result["success"]:
            status_code = 409 if result.get("code") == "reauth_required" else 502
            if result.get("code") == "not_connected":
                status_code = 400
            return jsonify(result), status_code

        return jsonify(result), 200

    @app.route("/api/yandex-music/disconnect", methods=["DELETE"])
    @jwt_required()
    def api_yandex_music_disconnect():
        user_id = get_jwt_identity()
        db = SessionLocal()
        try:
            removed = yandex_disconnect(db, user_id)
        finally:
            db.close()
        if not removed:
            return jsonify({"error": "Яндекс.Музыка не была подключена"}), 404
        return jsonify({"success": True}), 200

    @app.route("/api/health")
    def health():
        return jsonify({"status": "healthy", "version": "1.0.0"})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5001")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )
