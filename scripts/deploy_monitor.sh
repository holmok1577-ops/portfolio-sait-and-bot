#!/bin/bash
# Скрипт деплоя мониторинга portfolio-ai

echo "🚀 Деплой мониторинга portfolio-ai..."

# Создаем директорию для скриптов
mkdir -p /var/www/portfolio/scripts

# Копируем скрипт мониторинга
cp scripts/monitor.py /var/www/portfolio/scripts/monitor.py

# Делаем скрипт исполняемым
chmod +x /var/www/portfolio/scripts/monitor.py

# Создаем директорию для логов крашей
mkdir -p /var/www/portfolio/logs

# Настраиваем cron job для запуска каждые 30 минут
(crontab -l 2>/dev/null | grep -v "monitor.py"; echo "*/30 * * * * cd /var/www/portfolio && /var/www/portfolio/venv/bin/python scripts/monitor.py >> /var/www/portfolio/logs/monitor.log 2>&1") | crontab -

echo "✅ Мониторинг развернут"
echo "📅 Cron job настроен на запуск каждые 30 минут"
echo "📝 Логи мониторинга: /var/www/portfolio/logs/monitor.log"
echo "📝 Логи крашей: /var/www/portfolio/logs/crash_*.log"

# Проверяем cron job
echo ""
echo "📋 Текущий cron job:"
crontab -l | grep monitor.py
