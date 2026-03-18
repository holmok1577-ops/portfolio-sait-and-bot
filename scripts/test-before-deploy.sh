#!/bin/bash
# -*- coding: utf-8 -*-
# Полный скрипт тестирования перед деплоем

set -e

echo "=========================================="
echo "ПОЛНОЕ ТЕСТИРОВАНИЕ ПЕРЕД ДЕПЛОЕМ"
echo "=========================================="
echo ""

# Проверка версии Python
echo "1. Проверка версии Python..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "   Python: $python_version"

if [[ ! $python_version == 3.8.* ]]; then
    echo "   ⚠️  ВНИМАНИЕ: Рекомендуется Python 3.8.10 для тестирования"
    echo "   На сервере установлена версия 3.8.10"
    read -p "Продолжить? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Проверка виртуального окружения
echo ""
echo "2. Проверка виртуального окружения..."
if [ -d "venv" ]; then
    echo "   ✅ venv найден"
    source venv/bin/activate || source venv/Scripts/activate
else
    echo "   🔄 Создание venv..."
    python3 -m venv venv
    source venv/bin/activate || source venv/Scripts/activate
fi

# Установка зависимостей
echo ""
echo "3. Установка зависимостей..."
pip install -q -r requirements.txt
echo "   ✅ Зависимости установлены"

# Проверка кодировки файлов
echo ""
echo "4. Проверка UTF-8 кодировки..."
python3 << 'PYEOF'
import sys
from pathlib import Path

errors = []
for f in Path('.').rglob('*.py'):
    try:
        with open(f, 'r', encoding='utf-8') as file:
            file.read()
    except UnicodeDecodeError as e:
        errors.append((f, e))

if errors:
    print(f"   ❌ {len(errors)} файлов не в UTF-8:")
    for f, e in errors[:5]:
        print(f"      - {f}: {e}")
    sys.exit(1)
else:
    print(f"   ✅ Все Python файлы в UTF-8")
PYEOF

# Запуск тестов Python 3.8
echo ""
echo "5. Запуск тестов Python 3.8 совместимости..."
python tests/test_python38.py || {
    echo "   ❌ Тесты не пройдены"
    exit 1
}

# Проверка .env
echo ""
echo "6. Проверка .env файла..."
if [ -f ".env" ]; then
    echo "   ✅ .env найден"
    
    # Проверка наличия ключевых переменных
    if grep -q "PROXY_API_KEY=" .env && ! grep -q "PROXY_API_KEY=your_proxy" .env; then
        echo "   ✅ PROXY_API_KEY настроен"
    else
        echo "   ⚠️  PROXY_API_KEY не настроен (можно настроить на сервере)"
    fi
    
    if grep -q "TELEGRAM_BOT_TOKEN=" .env && ! grep -q "TELEGRAM_BOT_TOKEN=your_telegram" .env; then
        echo "   ✅ TELEGRAM_BOT_TOKEN настроен"
    else
        echo "   ⚠️  TELEGRAM_BOT_TOKEN не настроен (можно настроить на сервере)"
    fi
else
    echo "   ⚠️  .env не найден, будет создан из .env.example"
    cp .env.example .env
fi

# Проверка документов
echo ""
echo "7. Проверка документов RAG..."
if [ -d "docs" ]; then
    doc_count=$(find docs -type f \( -name "*.txt" -o -name "*.md" \) | wc -l)
    echo "   ✅ Найдено документов: $doc_count"
else
    echo "   ⚠️  Директория docs не найдена"
fi

# Проверка Docker
echo ""
echo "8. Проверка Docker..."
if command -v docker &> /dev/null; then
    docker --version
    echo "   ✅ Docker установлен"
    
    if command -v docker-compose &> /dev/null; then
        docker-compose --version
        echo "   ✅ Docker Compose установлен"
    else
        echo "   ⚠️  Docker Compose не найден"
    fi
else
    echo "   ⚠️  Docker не установлен (будет установлен на сервере)"
fi

# Сборка Docker образа
echo ""
echo "9. Сборка Docker образа..."
docker-compose build || {
    echo "   ❌ Ошибка сборки Docker образа"
    exit 1
}
echo "   ✅ Docker образ собран"

# Проверка структуры
echo ""
echo "10. Проверка структуры проекта..."
required_dirs="backend frontend config scripts docs data chroma_db logs backups"
missing=0

for dir in $required_dirs; do
    if [ -d "$dir" ]; then
        echo "   ✅ $dir/"
    else
        echo "   ⚠️  $dir/ - создается"
        mkdir -p "$dir"
    fi
done

# Итог
echo ""
echo "=========================================="
echo "✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО УСПЕШНО!"
echo "=========================================="
echo ""
echo "Готово к деплою на сервер."
echo "Следующие шаги:"
echo "1. git push origin main"
echo "2. ./scripts/deploy.sh"
echo ""
echo "Или вручную:"
echo "ssh root@95.81.123.214"
echo "cd /opt/portfolio-ai && docker-compose up -d"
echo ""
