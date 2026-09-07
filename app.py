# app.py
import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import insert, select
from backend.database import engine
from backend.models import users, metadata

load_dotenv()
metadata.create_all(engine)

app = Flask(__name__,
            template_folder='frontend/templates',
            static_folder='frontend/static',
            static_url_path='/static')
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')





@app.route('/')
def home():
    return render_template('index.html')

@app.route('/discover')
def discover():
    if 'user_id' not in session:
        flash('Пожалуйста, войдите', 'warning')
        return redirect(url_for('home'))
    return render_template('discover.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# ------------------- API (JSON) -------------------
@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Нет данных'}), 400

    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')

    # Валидация
    if not username or not email or not password:
        return jsonify({'error': 'Все поля обязательны'}), 400

    # Проверка длины пароля
    if len(password) < 8:
        return jsonify({'error': 'Пароль должен содержать минимум 8 символов'}), 400

    with engine.connect() as conn:
        # Проверяем email
        existing = conn.execute(select(users).where(users.c.email == email)).first()
        if existing:
            return jsonify({'error': 'Email уже зарегистрирован'}), 400

        # Хешируем пароль
        hashed = generate_password_hash(password)
        stmt = insert(users).values(
            first_name=username,
            last_name='',
            email=email,
            gender='',
            password=hashed
        )
        result = conn.execute(stmt)
        conn.commit()
        user_id = result.inserted_primary_key[0]

    # Сохраняем в сессию
    session['user_id'] = user_id
    session['user_name'] = username

    return jsonify({
        'access_token': 'fake-jwt-token',  # можно заменить на реальный JWT позже
        'user_id': user_id,
        'username': username
    }), 200




@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Нет данных'}), 400

    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email и пароль обязательны'}), 400

    with engine.connect() as conn:
        user = conn.execute(select(users).where(users.c.email == email)).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_name'] = user.first_name
            return jsonify({
                'access_token': 'fake-jwt-token',
                'user_id': user.id,
                'username': user.first_name
            }), 200
        else:
            return jsonify({'error': 'Неверный email или пароль'}), 401

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        flash('Пожалуйста, войдите', 'warning')
        return redirect(url_for('home'))
    return render_template('profile.html')

if __name__ == '__main__':
    app.run(debug=True,
            host='0.0.0.0',
            port=80)