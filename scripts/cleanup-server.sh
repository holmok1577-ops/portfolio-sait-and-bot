#!/bin/bash
# -*- coding: utf-8 -*-
# Скрипт очистки старого проекта на сервере

echo "🧹 ОЧИСТКА СТАРОГО ПРОЕКТА НА СЕРВЕРЕ"
echo "====================================="
echo ""
echo "⚠️  ВНИМАНИЕ: Это удалит старый проект!"
echo ""

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PROJECT_DIR="/opt/portfolio-ai"
OLD_DIRS=(
    "/root/venv"
    "/root/old_project"
    "/opt/old-portfolio"
    "$HOME/portfolio-old"
)

# Функция подтверждения
confirm() {
    read -p "Вы уверены? (yes/N): " response
    case "$response" in
        [yY][eE][sS] ) true ;;
        * ) false ;;
    esac
}

# 1. Остановка старых сервисов
echo -e "${YELLOW}1. Остановка старых сервисов...${NC}"
systemctl stop portfolio-ai 2>/dev/null || true
systemctl stop portfolio-old 2>/dev/null || true
docker stop portfolio-old 2>/dev/null || true
docker stop old-bot 2>/dev/null || true

# 2. Удаление старых Docker контейнеров
echo -e "${YELLOW}2. Удаление старых Docker контейнеров...${NC}"
docker ps -a | grep -E "(portfolio|bot|old)" | awk '{print $1}' | xargs -r docker rm -f 2>/dev/null || true

# 3. Удаление старых образов
echo -e "${YELLOW}3. Удаление старых Docker образов...${NC}"
docker images | grep -E "(portfolio|bot|old)" | awk '{print $3}' | xargs -r docker rmi -f 2>/dev/null || true

# 4. Очистка Docker
echo -e "${YELLOW}4. Очистка Docker...${NC}"
docker system prune -f

# 5. Удаление старых systemd сервисов
echo -e "${YELLOW}5. Удаление старых systemd сервисов...${NC}"
OLD_SERVICES=(
    "/etc/systemd/system/portfolio-ai.service"
    "/etc/systemd/system/portfolio-old.service"
    "/etc/systemd/system/old-bot.service"
)

for service in "${OLD_SERVICES[@]}"; do
    if [ -f "$service" ]; then
        systemctl stop $(basename "$service") 2>/dev/null || true
        systemctl disable $(basename "$service") 2>/dev/null || true
        rm -f "$service"
        echo "   Удален: $service"
    fi
done

systemctl daemon-reload

# 6. Удаление старых директорий
echo -e "${YELLOW}6. Удаление старых директорий...${NC}"
echo "   Будут удалены:"

# Главная директория проекта
if [ -d "$PROJECT_DIR" ]; then
    echo "     - $PROJECT_DIR"
fi

# Другие возможные директории
for dir in "${OLD_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo "     - $dir"
    fi
done

# Виртуальные окружения
echo "   Будут удалены виртуальные окружения:"
find /root -name "venv" -type d 2>/dev/null | head -5
find /opt -name "venv" -type d 2>/dev/null | head -5

echo ""
if confirm; then
    # Удаление главной директории
    if [ -d "$PROJECT_DIR" ]; then
        rm -rf "$PROJECT_DIR"
        echo -e "   ${GREEN}✓ Удален: $PROJECT_DIR${NC}"
    fi
    
    # Удаление других директорий
    for dir in "${OLD_DIRS[@]}"; do
        if [ -d "$dir" ]; then
            rm -rf "$dir"
            echo -e "   ${GREEN}✓ Удален: $dir${NC}"
        fi
    done
    
    # Удаление виртуальных окружений
    find /root -name "venv" -type d -exec rm -rf {} + 2>/dev/null || true
    find /opt -name "venv" -type d -exec rm -rf {} + 2>/dev/null || true
    
    echo ""
    echo -e "${GREEN}✅ Очистка завершена!${NC}"
else
    echo ""
    echo -e "${YELLOW}⚠️  Очистка отменена${NC}"
    exit 0
fi

# 7. Проверка
echo ""
echo -e "${YELLOW}7. Проверка...${NC}"
echo "   Оставшиеся процессы:"
ps aux | grep -E "(portfolio|python.*bot)" | grep -v grep | head -3 || echo "   Нет запущенных процессов"

echo ""
echo "   Оставшиеся Docker контейнеры:"
docker ps -a | grep -E "(portfolio|bot)" || echo "   Нет контейнеров"

echo ""
echo -e "${GREEN}✅ Сервер готов к установке нового проекта!${NC}"
echo ""
echo "Следующий шаг:"
echo "  ./scripts/deploy.sh"
