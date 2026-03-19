#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт мониторинга и автоподъема portfolio-ai сервиса
Запускается каждые 30 минут через cron
"""

import subprocess
import requests
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
SERVICE_NAME = "portfolio-ai"
SITE_URL = "http://localhost:8000"
API_URL = "http://localhost:8000"

def send_telegram_alert(message: str):
    """Отправка оповещения в Telegram"""
    if not TELEGRAM_BOT_TOKEN or not ADMIN_TELEGRAM_ID:
        print("❌ TELEGRAM_BOT_TOKEN или ADMIN_TELEGRAM_ID не заданы", file=sys.stderr)
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": ADMIN_TELEGRAM_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            print("✅ Оповещение отправлено в Telegram")
            return True
        else:
            print(f"❌ Ошибка отправки в Telegram: {response.status_code}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"❌ Ошибка отправки в Telegram: {e}", file=sys.stderr)
        return False

def check_service_status():
    """Проверка статуса сервиса"""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", SERVICE_NAME],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout.strip() == "active"
    except Exception as e:
        print(f"❌ Ошибка проверки статуса сервиса: {e}", file=sys.stderr)
        return False

def check_site_health():
    """Проверка работоспособности сайта"""
    try:
        response = requests.get(SITE_URL, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Сайт недоступен: {e}", file=sys.stderr)
        return False

def restart_service():
    """Рестарт сервиса"""
    try:
        print("🔄 Рестарт сервиса...")
        result = subprocess.run(
            ["systemctl", "restart", SERVICE_NAME],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            print("✅ Сервис успешно перезапущен")
            return True
        else:
            print(f"❌ Ошибка рестарта: {result.stderr}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"❌ Ошибка рестарта: {e}", file=sys.stderr)
        return False

def get_logs(lines: int = 50):
    """Получение последних логов"""
    try:
        result = subprocess.run(
            ["journalctl", "-u", SERVICE_NAME, "-n", str(lines), "--no-pager"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout
    except Exception as e:
        print(f"❌ Ошибка получения логов: {e}", file=sys.stderr)
        return ""

def save_logs_to_file(logs: str):
    """Сохранение логов в файл"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f"/var/www/portfolio/logs/crash_{timestamp}.log"
        os.makedirs("/var/www/portfolio/logs", exist_ok=True)
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(logs)
        print(f"📝 Логи сохранены в {log_file}")
        return log_file
    except Exception as e:
        print(f"❌ Ошибка сохранения логов: {e}", file=sys.stderr)
        return None

def main():
    """Главная функция"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*60}")
    print(f"🔍 Мониторинг {SERVICE_NAME} - {timestamp}")
    print(f"{'='*60}\n")

    # Проверка статуса сервиса
    service_active = check_service_status()
    print(f"Статус сервиса: {'✅ Активен' if service_active else '❌ Неактивен'}")

    # Проверка работоспособности сайта
    site_healthy = check_site_health()
    print(f"Работоспособность сайта: {'✅ OK' if site_healthy else '❌ Недоступен'}")

    # Если все работает - завершаем
    if service_active and site_healthy:
        print("\n✅ Сервис работает нормально")
        sys.exit(0)

    # Сервис не работает - рестартуем
    print("\n⚠️ Сервис не работает, начинаем восстановление...")

    # Получаем логи до рестарта
    logs = get_logs(50)
    log_file = save_logs_to_file(logs)

    # Рестартуем сервис
    restart_success = restart_service()

    if restart_success:
        # Ждем 5 секунд и проверяем статус
        import time
        time.sleep(5)

        service_active = check_service_status()
        site_healthy = check_site_health()

        if service_active and site_healthy:
            print("\n✅ Сервис успешно восстановлен")

            # Отправляем оповещение в Telegram
            message = f"""
🚨 <b>Сайт {SERVICE_NAME} упал и был поднят</b>

📅 <b>Время:</b> {timestamp}
📝 <b>Логи:</b> {log_file if log_file else 'Не сохранены'}

<b>Последние логи:</b>
<pre>{logs[-1000:] if len(logs) > 1000 else logs}</pre>
"""
            send_telegram_alert(message)
            sys.exit(0)
        else:
            print("\n❌ Сервис не восстановился после рестарта")
            message = f"""
🚨 <b>Критическая ошибка: Сервис {SERVICE_NAME} не восстанавливается</b>

📅 <b>Время:</b> {timestamp}
📝 <b>Логи:</b> {log_file if log_file else 'Не сохранены'}

<b>Последние логи:</b>
<pre>{logs[-1000:] if len(logs) > 1000 else logs}</pre>
"""
            send_telegram_alert(message)
            sys.exit(1)
    else:
        print("\n❌ Не удалось перезапустить сервис")
        message = f"""
🚨 <b>Критическая ошибка: Не удалось перезапустить {SERVICE_NAME}</b>

📅 <b>Время:</b> {timestamp}
📝 <b>Логи:</b> {log_file if log_file else 'Не сохранены'}

<b>Последние логи:</b>
<pre>{logs[-1000:] if len(logs) > 1000 else logs}</pre>
"""
        send_telegram_alert(message)
        sys.exit(1)

if __name__ == "__main__":
    main()
