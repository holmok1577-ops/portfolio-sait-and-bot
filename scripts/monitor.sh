#!/bin/bash
# -*- coding: utf-8 -*-
# Скрипт мониторинга и автоподъема

APP_NAME="portfolio-ai"
CHECK_INTERVAL=60
MAX_RETRIES=3

LOG_FILE="/var/log/${APP_NAME}-monitor.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

check_health() {
    curl -sf http://localhost:8000/health > /dev/null 2>&1
    return $?
}

restart_app() {
    log "🔄 Перезапуск приложения..."
    cd /opt/portfolio-ai
    docker-compose restart app
    sleep 10
}

send_alert() {
    local message="$1"
    # Здесь можно добавить отправку уведомлений
    log "🚨 ALERT: $message"
}

main() {
    log "🚀 Мониторинг запущен"
    
    local fail_count=0
    
    while true; do
        if ! check_health; then
            fail_count=$((fail_count + 1))
            log "⚠️ Health check failed ($fail_count/$MAX_RETRIES)"
            
            if [ $fail_count -ge $MAX_RETRIES ]; then
                send_alert "Сервис недоступен после $MAX_RETRIES попыток"
                restart_app
                fail_count=0
            fi
        else
            if [ $fail_count -gt 0 ]; then
                log "✅ Сервис восстановлен"
            fi
            fail_count=0
        fi
        
        sleep $CHECK_INTERVAL
    done
}

# Запуск
main
