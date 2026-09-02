// front/static/js/main.js
class AuthManager {
    constructor() {
        this.token = localStorage.getItem('auth_token');
        this.userId = localStorage.getItem('user_id');
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Обработка формы входа
        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.handleLogin();
        });

        // Обработка формы регистрации
        document.getElementById('registerForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.handleRegister();
        });
    }

    async handleLogin() {
        const email = document.getElementById('loginEmail').value;
        const password = document.getElementById('loginPassword').value;

        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ email, password })
            });

            const data = await response.json();

            if (response.ok) {
                this.saveToken(data.access_token, data.user_id);
                this.onAuthSuccess();
            } else {
                this.showError(data.error || 'Ошибка входа');
            }
        } catch (error) {
            this.showError('Ошибка соединения с сервером');
        }
    }

    async handleRegister() {
        const username = document.getElementById('registerName').value;
        const email = document.getElementById('registerEmail').value;
        const password = document.getElementById('registerPassword').value;
        const gender = document.querySelector('input[name="gender"]:checked').value;

        try {
            const response = await fetch('/api/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, email, password, gender })
            });

            const data = await response.json();

            if (response.ok) {
                this.saveToken(data.access_token, data.user_id);
                this.onAuthSuccess();
            } else {
                this.showError(data.error || 'Ошибка регистрации');
            }
        } catch (error) {
            this.showError('Ошибка соединения с сервером');
        }
    }

    saveToken(token, userId) {
        this.token = token;
        this.userId = userId;
        localStorage.setItem('auth_token', token);
        localStorage.setItem('user_id', userId);
    }

    onAuthSuccess() {
        // Закрываем модальное окно
        closeAuthModal();
        // Показываем приветствие
        alert('Добро пожаловать в Волну!');
        // Здесь можно перенаправить на страницу выбора артистов
        // window.location.href = '/select-artists';
    }

    showError(message) {
        // Создаем уведомление об ошибке
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-notification';
        errorDiv.textContent = message;
        errorDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #ff4757;
            color: white;
            padding: 15px 20px;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            z-index: 1000;
            animation: slideIn 0.3s ease;
        `;
        document.body.appendChild(errorDiv);

        setTimeout(() => {
            errorDiv.remove();
        }, 3000);
    }

    isAuthenticated() {
        return !!this.token;
    }

    logout() {
        this.token = null;
        this.userId = null;
        localStorage.removeItem('auth_token');
        localStorage.removeItem('user_id');
    }
}

// Инициализация
const authManager = new AuthManager();

// Экспортируем для использования в других скриптах
window.authManager = authManager;