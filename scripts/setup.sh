#!/bin/bash
# -*- coding: utf-8 -*-
# Скрипт установки для локальной разработки

set -e

echo "🚀 Установка Portfolio AI Assistant..."

# Проверка Python версии
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "📦 Python версия: $python_version"

# Создание виртуального окружения
echo "🐍 Создание виртуального окружения..."
python3 -m venv venv
source venv/bin/activate

# Установка зависимостей
echo "📥 Установка зависимостей..."
pip install --upgrade pip
pip install -r requirements.txt

# Создание директорий
echo "📁 Создание директорий..."
mkdir -p data logs chroma_db docs

# Копирование .env если не существует
if [ ! -f ".env" ]; then
    echo "⚙️  Создание .env файла..."
    cp .env.example .env
    echo "⚠️  Не забудьте отредактировать .env файл!"
fi

echo "✅ Установка завершена!"
echo ""
echo "📝 Следующие шаги:"
echo "1. Отредактируйте файл .env"
echo "2. Запустите: python run.py --mode combined"
echo "3. Откройте: http://localhost:8000"
