#!/bin/bash
# Deploy script for Portfolio AI Assistant v1.0.1
# Run on server: bash deploy.sh

set -e

echo "🚀 Начинаем деплой Portfolio AI v1.0.1..."

# 1. Очистка старых проектов
echo "🧹 Очистка старых проектов..."
cd /
rm -rf /root/old_projects/* 2>/dev/null || true
rm -rf /root/portfolio-* 2>/dev/null || true
rm -rf /root/venv* 2>/dev/null || true
rm -rf /var/www/html/* 2>/dev/null || true

# 2. Установка зависимостей системы
echo "📦 Установка системных зависимостей..."
apt-get update
apt-get install -y python3-pip python3-venv git curl sqlite3 nginx

# 3. Клонирование проекта
echo "📥 Клонирование проекта..."
cd /root
PROJECT_DIR="/root/portfolio-ai"
rm -rf $PROJECT_DIR
git clone https://github.com/holmok1577-ops/portfolio-sait-and-bot.git $PROJECT_DIR
cd $PROJECT_DIR

# 4. Создание виртуального окружения
echo "🐍 Создание виртуального окружения..."
python3 -m venv venv
source venv/bin/activate

# 5. Установка Python зависимостей
echo "⬇️ Установка Python зависимостей..."
pip install --upgrade pip
pip install -r requirements.txt

# 6. Создание директорий для данных
echo "📁 Создание директорий..."
mkdir -p data logs chroma_db frontend/images/portfolio

# 7. Создание .env файла (админ должен заполнить свои данные!)
echo "⚙️ Создание .env файла..."
cat > .env << 'EOF'
# API Keys - ЗАПОЛНИТЕ СВОИ ДАННЫЕ!
PROXY_API_KEY=your_proxy_api_key_here
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
ADMIN_TELEGRAM_ID=your_admin_telegram_id_here

# Настройки сервера
HOST=0.0.0.0
PORT=8000
DEBUG=false

# Настройки базы данных
DATABASE_URL=sqlite:///data/app.db

# AI Настройки
AI_MODEL=gpt-3.5-turbo
AI_TEMPERATURE=0.7
EMBEDDING_MODEL=text-embedding-3-small
PROXY_API_BASE=https://api.proxyapi.ru/openai/v1

# RAG Настройки
RAG_TOP_K=3
RAG_SIMILARITY_THRESHOLD=0.7

# Безопасность
SECRET_KEY=change-this-secret-key-in-production
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123

# Мониторинг
HEALTH_CHECK_INTERVAL=60
ALERT_COOLDOWN=300
AUTO_RESTART=true

# Кэш
CACHE_ENABLED=true
CACHE_TTL=3600
EOF

echo "⚠️ ВАЖНО: Отредактируйте файл /root/portfolio-ai/.env и добавьте свои API ключи!"

# 8. Создание systemd сервиса
echo "🔧 Создание systemd сервиса..."
cat > /etc/systemd/system/portfolio-ai.service << 'EOF'
[Unit]
Description=Portfolio AI Assistant v1.0.1
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/portfolio-ai
Environment=PYTHONPATH=/root/portfolio-ai
ExecStart=/root/portfolio-ai/venv/bin/python run.py --mode server
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 9. Настройка Nginx
echo "🌐 Настройка Nginx..."
cat > /etc/nginx/sites-available/portfolio-ai << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    location /static/ {
        alias /root/portfolio-ai/frontend/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /images/ {
        alias /root/portfolio-ai/frontend/images/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
EOF

ln -sf /etc/nginx/sites-available/portfolio-ai /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t

# 10. Запуск сервисов
echo "▶️ Запуск сервисов..."
systemctl daemon-reload
systemctl enable portfolio-ai
systemctl restart nginx
systemctl start portfolio-ai

# 11. Проверка статуса
echo "✅ Проверка деплоя..."
sleep 5
systemctl status portfolio-ai --no-pager

echo ""
echo "🎉 Деплой завершен!"
echo "📍 Сайт доступен по адресу: http://95.81.123.214"
echo "📍 Админка: http://95.81.123.214/admin.html"
echo "⚠️ Не забудьте отредактировать /root/portfolio-ai/.env и перезапустить: systemctl restart portfolio-ai"
