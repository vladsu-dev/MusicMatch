# front/app.py
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from backend.database import init_db, SessionLocal
from backend.models import User
from backend.auth import register_user, login_user
from backend.yandex_auth_flow import auth_flow_manager
from backend.yandex_music_service import (
    disconnect as yandex_disconnect,
    get_connection_status as yandex_get_connection_status,
    save_token as yandex_save_token,
    sync_favorite_artists as yandex_sync_favorite_artists,
)
import logging
import os
from dotenv import load_dotenv
from datetime import timedelta
import bcrypt

logger = logging.getLogger(__name__)

load_dotenv()


def create_app():
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

    # Настройки
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)

    # Инициализация расширений
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    jwt = JWTManager(app)

    # Инициализация базы данных
    init_db()

    # Главная страница
    @app.route('/')
    def index():
        return render_template('index.html')

    # API для регистрации
    @app.route('/api/register', methods=['POST'])
    def api_register():
        data = request.get_json()

        # Валидация данных
        required_fields = ['username', 'email', 'password', 'gender']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Поле {field} обязательно'}), 400

        # Проверка пароля
        if len(data['password']) < 8:
            return jsonify({'error': 'Пароль должен быть минимум 8 символов'}), 400

        # Регистрация пользователя
        result = register_user(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            gender=data['gender'],
            age=data.get('age'),
            bio=data.get('bio', '')
        )

        if result['success']:
            # Создаем JWT токен
            access_token = create_access_token(identity=result['user_id'])
            return jsonify({
                'message': 'Регистрация успешна',
                'access_token': access_token,
                'user_id': result['user_id']
            }), 201
        else:
            return jsonify({'error': result['error']}), 400

    # API для входа
    @app.route('/api/login', methods=['POST'])
    def api_login():
        data = request.get_json()

        if 'email' not in data or 'password' not in data:
            return jsonify({'error': 'Email и пароль обязательны'}), 400

        result = login_user(
            email=data['email'],
            password=data['password']
        )

        if result['success']:
            access_token = create_access_token(identity=result['user_id'])
            return jsonify({
                'message': 'Вход выполнен',
                'access_token': access_token,
                'user_id': result['user_id']
            }), 200
        else:
            return jsonify({'error': result['error']}), 401

    # Защищенный эндпоинт (пример)
    @app.route('/api/profile', methods=['GET'])
    @jwt_required()
    def api_profile():
        current_user_id = get_jwt_identity()
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == current_user_id).first()
            if not user:
                return jsonify({'error': 'Пользователь не найден'}), 404

            return jsonify({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'gender': user.gender,
                'age': user.age,
                'bio': user.bio,
                'avatar_url': user.avatar_url
            }), 200
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Интеграция с Яндекс.Музыкой
    #
    # Библиотека yandex-music-api — неофициальная (LGPL-3.0), см.
    # THIRD_PARTY_NOTICES.md по лицензии и docs/YANDEX_MUSIC_INTEGRATION.md
    # по устройству этого флоу (почему авторизация в два шага).
    # ------------------------------------------------------------------

    @app.route('/api/yandex-music/connect', methods=['POST'])
    @jwt_required()
    def api_yandex_music_connect():
        """Запускает OAuth Device Flow в фоновом потоке и почти сразу
        отдаёт verification_url + user_code, которые нужно показать пользователю."""
        user_id = get_jwt_identity()
        auth_flow_manager.start(user_id)
        status = auth_flow_manager.get_status(user_id, wait_seconds=3.0)
        return jsonify(status), 200

    @app.route('/api/yandex-music/connect/status', methods=['GET'])
    @jwt_required()
    def api_yandex_music_connect_status():
        """Фронтенд опрашивает этот эндпоинт, пока status не станет
        success/error. При success — токен сохраняется в БД (в зашифрованном виде)."""
        user_id = get_jwt_identity()
        status = auth_flow_manager.get_status(user_id, wait_seconds=2.0)

        if status.get('status') == 'success':
            token = auth_flow_manager.pop_token_if_ready(user_id)
            if token:
                db = SessionLocal()
                try:
                    yandex_save_token(db, user_id, token)
                finally:
                    db.close()
            return jsonify({'status': 'connected'}), 200

        if status.get('status') == 'error':
            auth_flow_manager.clear_error(user_id)

        return jsonify(status), 200

    @app.route('/api/yandex-music/status', methods=['GET'])
    @jwt_required()
    def api_yandex_music_status():
        """Текущее состояние подключения (для отображения в профиле)."""
        user_id = get_jwt_identity()
        db = SessionLocal()
        try:
            return jsonify(yandex_get_connection_status(db, user_id)), 200
        finally:
            db.close()

    @app.route('/api/yandex-music/sync', methods=['POST'])
    @jwt_required()
    def api_yandex_music_sync():
        """Забирает любимых исполнителей из Яндекс.Музыки и добавляет их в профиль.
        Ограничен интервалом MIN_SYNC_INTERVAL — см. backend/yandex_music_service.py."""
        user_id = get_jwt_identity()
        force = bool((request.get_json(silent=True) or {}).get('force', False))
        db = SessionLocal()
        try:
            result = yandex_sync_favorite_artists(db, user_id, force=force)
        finally:
            db.close()

        if not result['success']:
            status_code = 409 if result.get('code') == 'reauth_required' else 502
            if result.get('code') == 'not_connected':
                status_code = 400
            return jsonify(result), status_code

        return jsonify(result), 200

    @app.route('/api/yandex-music/disconnect', methods=['DELETE'])
    @jwt_required()
    def api_yandex_music_disconnect():
        """Отключает Яндекс.Музыку и удаляет сохранённый токен пользователя."""
        user_id = get_jwt_identity()
        db = SessionLocal()
        try:
            removed = yandex_disconnect(db, user_id)
        finally:
            db.close()
        if not removed:
            return jsonify({'error': 'Яндекс.Музыка не была подключена'}), 404
        return jsonify({'success': True}), 200

    # Health check
    @app.route('/api/health')
    def health():
        return jsonify({'status': 'healthy', 'version': '1.0.0'})

    return app


app = create_app()

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=5001,
        debug=True
    )