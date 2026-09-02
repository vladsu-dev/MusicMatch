# front/app.py
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from database.database import init_db, SessionLocal
from backend.models import User
from backend.auth import register_user, login_user
import os
from dotenv import load_dotenv
from datetime import timedelta
import bcrypt

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