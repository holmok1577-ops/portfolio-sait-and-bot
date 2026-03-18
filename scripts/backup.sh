#!/bin/bash
# -*- coding: utf-8 -*-
# Скрипт создания бэкапа через Docker

set -e

echo "📦 Создание бэкапа..."

# Проверяем что мы в директории проекта
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Ошибка: запустите из корня проекта"
    exit 1
fi

# Создаем бэкап
docker-compose --profile backup run --rm backup

echo "✅ Бэкап создан!"
echo ""
echo "📂 Расположение: ./backups/"
ls -la backups/ | tail -5
