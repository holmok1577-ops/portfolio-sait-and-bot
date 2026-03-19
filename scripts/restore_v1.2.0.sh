#!/bin/bash
# Recovery script for Portfolio AI v1.2.0 (Stable Working Version)
# Use this script to restore the working version in case of critical errors

set -e

echo "🚨 Восстановление Portfolio AI v1.2.0 (Стабильная рабочая версия)"
echo "=============================================================="

# 1. Проверка текущего состояния
echo "📊 Проверка текущего состояния..."
cd /var/www/portfolio
CURRENT_VERSION=$(git describe --tags --always 2>/dev/null || echo "unknown")
echo "   Текущая версия: $CURRENT_VERSION"

# 2. Создание бэкапа текущей версии
echo "💾 Создание бэкапа текущей версии..."
BACKUP_DIR="/var/www/portfolio_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -r /var/www/portfolio/data "$BACKUP_DIR/" 2>/dev/null || true
cp -r /var/www/portfolio/logs "$BACKUP_DIR/" 2>/dev/null || true
cp /var/www/portfolio/.env "$BACKUP_DIR/" 2>/dev/null || true
echo "   Бэкап сохранен в: $BACKUP_DIR"

# 3. Остановка сервиса
echo "⏹️  Остановка сервиса..."
systemctl stop portfolio-ai || true
sleep 2

# 4. Переключение на стабильную версию v1.2.0
echo "🔄 Переключение на v1.2.0..."
git fetch --tags
git checkout v1.2.0
git reset --hard v1.2.0

# 5. Восстановление конфигурации
echo "⚙️  Восстановление конфигурации..."
if [ -f "$BACKUP_DIR/.env" ]; then
    cp "$BACKUP_DIR/.env" /var/www/portfolio/.env
    echo "   Конфигурация восстановлена"
fi

# 6. Установка зависимостей (если нужно)
echo "📦 Проверка зависимостей..."
source venv/bin/activate
pip install -q -r requirements.txt 2>/dev/null || echo "   Зависимости уже установлены"

# 7. Запуск сервиса
echo "🚀 Запуск сервиса..."
systemctl start portfolio-ai
sleep 5

# 8. Проверка статуса
echo "📊 Проверка статуса..."
if systemctl is-active --quiet portfolio-ai; then
    echo "   ✅ Сервис успешно запущен"
    echo ""
    echo "🎉 Восстановление завершено успешно!"
    echo "   Версия: v1.2.0 (Стабильная рабочая версия)"
    echo "   Бэкап: $BACKUP_DIR"
    echo ""
    echo "📝 Для проверки статуса:"
    echo "   systemctl status portfolio-ai"
else
    echo "   ❌ Ошибка запуска сервиса"
    echo ""
    echo "📝 Для диагностики:"
    echo "   journalctl -u portfolio-ai -n 50"
    echo "   systemctl status portfolio-ai"
    exit 1
fi
