#!/bin/bash
# -*- coding: utf-8 -*-
# Скрипт деплоя на удаленный сервер

set -e

# Конфигурация
SERVER="root@95.81.123.214"
PROJECT_DIR="/opt/portfolio-ai"
REPO_URL="https://github.com/holmok1577-ops/portfolio-sait-and-bot.git"

echo "🚀 Начинаем деплой Portfolio AI..."

# Подключение к серверу и выполнение команд
ssh ${SERVER} << 'EOF'
    echo "📦 Обновление системы..."
    apt-get update && apt-get upgrade -y
    
    echo "🐳 Установка Docker..."
    if ! command -v docker &> /dev/null; then
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
        usermod -aG docker root
        systemctl enable docker
        systemctl start docker
    fi
    
    echo "📁 Подготовка директории..."
    mkdir -p ${PROJECT_DIR}
    cd ${PROJECT_DIR}
    
    echo "📥 Клонирование/обновление репозитория..."
    if [ -d ".git" ]; then
        git pull origin main
    else
        git clone ${REPO_URL} .
    fi
    
    echo "🔧 Настройка окружения..."
    if [ ! -f ".env" ]; then
        cp .env.example .env
        echo "⚠️  Не забудьте отредактировать .env файл!"
    fi
    
    echo "🚀 Запуск приложения..."
    docker-compose down || true
    docker-compose pull
    docker-compose up -d --build
    
    echo "⏳ Ожидание запуска..."
    sleep 30
    
    echo "✅ Проверка статуса..."
    curl -f http://localhost:8000/health || echo "⚠️  Сервис не отвечает"
    
    echo "🧹 Очистка..."
    docker system prune -f
    
    echo "✅ Деплой завершен!"
EOF

echo "🎉 Деплой успешно выполнен!"
echo "🌐 Сайт доступен по адресу: http://95.81.123.214:8000"
