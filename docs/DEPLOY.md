# Пошаговая инструкция по деплою

## Предварительные требования

- Python 3.8.10 (для тестирования)
- Docker и Docker Compose
- Доступ к серверу: `ssh root@95.81.123.214`
- Git репозиторий: `https://github.com/holmok1577-ops/portfolio-sait-and-bot`

## Шаг 1: Локальное тестирование

```bash
# 1.1 Запуск тестов
./scripts/test-before-deploy.sh

# 1.2 Проверка работы локально
docker-compose up -d

# 1.3 Проверка health endpoint
curl http://localhost:8000/health

# 1.4 Остановка
docker-compose down
```

## Шаг 2: Подготовка GitHub

```bash
# 2.1 Инициализация git (если не сделано)
git init
git add .
git commit -m "Initial commit: Portfolio AI v1.0.0"

# 2.2 Добавление remote (если нужно)
git remote add origin https://github.com/holmok1577-ops/portfolio-sait-and-bot.git

# 2.3 Пуш на GitHub
git branch -M main
git push -u origin main
```

## Шаг 3: Деплой на сервер

### Вариант А: Автоматический деплой

```bash
# Запуск скрипта деплоя
./scripts/deploy.sh
```

### Вариант Б: Ручной деплой

```bash
# 3.1 Подключение к серверу
ssh root@95.81.123.214

# 3.2 Обновление системы
apt-get update && apt-get upgrade -y

# 3.3 Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
usermod -aG docker root
systemctl enable docker
systemctl start docker

# 3.4 Создание директории
mkdir -p /opt/portfolio-ai
cd /opt/portfolio-ai

# 3.5 Клонирование репозитория
git clone https://github.com/holmok1577-ops/portfolio-sait-and-bot.git .

# 3.6 Настройка окружения
cp .env.example .env
nano .env  # Отредактируйте переменные!

# 3.7 Запуск
docker-compose up -d

# 3.8 Проверка
curl http://localhost:8000/health
```

## Шаг 4: Настройка окружения (.env)

Обязательно настройте на сервере:

```env
# API ключи
PROXY_API_KEY=your_actual_key_here
TELEGRAM_BOT_TOKEN=your_actual_bot_token_here
ADMIN_TELEGRAM_ID=your_telegram_id_here

# Безопасность (смените!)
SECRET_KEY=random-strong-secret-key-$(openssl rand -hex 32)
ADMIN_PASSWORD=your-strong-admin-password

# Мониторинг
HEALTH_CHECK_INTERVAL=60
ALERT_COOLDOWN=300
AUTO_RESTART=true
```

## Шаг 5: Настройка автозапуска (systemd)

```bash
# 5.1 Копирование сервиса
cp scripts/portfolio-ai.service /etc/systemd/system/

# 5.2 Обновление путей в сервисе (если нужно)
sed -i 's|/opt/portfolio-ai|/opt/portfolio-ai|g' /etc/systemd/system/portfolio-ai.service

# 5.3 Активация
systemctl daemon-reload
systemctl enable portfolio-ai
systemctl start portfolio-ai

# 5.4 Проверка статуса
systemctl status portfolio-ai
```

## Шаг 6: Настройка бэкапов

```bash
# 6.1 Создание первого бэкапа
python scripts/backup.py create

# 6.2 Настройка cron для автоматических бэкапов
crontab -e

# Добавить строку:
0 3 * * * cd /opt/portfolio-ai && docker-compose --profile backup run --rm backup >> /var/log/backup.log 2>&1

# 6.3 Создание директории для логов
mkdir -p /var/log/portfolio-ai
touch /var/log/portfolio-ai/backup.log
```

## Шаг 7: Загрузка документов в RAG

```bash
# 7.1 Проверка UTF-8
python scripts/upload_docs.py docs/ --validate

# 7.2 Загрузка FAQ
python scripts/upload_docs.py docs/faq/ --batch --category faq

# 7.3 Загрузка документации
python scripts/upload_docs.py docs/documentation/ --batch --category documentation

# 7.4 Или через Docker
docker-compose exec app python scripts/upload_docs.py docs/ --batch
```

## Шаг 8: Проверка работоспособности

```bash
# 8.1 Проверка компонентов
curl http://95.81.123.214:8000/health

# 8.2 Проверка API
curl -X POST http://95.81.123.214:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Привет", "user_id": "test"}'

# 8.3 Проверка сайта
# Откройте в браузере: http://95.81.123.214:8000

# 8.4 Проверка Telegram бота
# Напишите боту: /start
```

## Шаг 9: Настройка мониторинга

После запуска бот автоматически:
- Отправит уведомление о запуске
- Начнет мониторинг каждые 60 секунд
- Отправит алерт при падении

Проверьте что получили уведомление в Telegram.

## Шаг 10: Настройка SSL (опционально)

```bash
# Установка certbot
apt-get install certbot

# Получение сертификата
certbot certonly --standalone -d your-domain.com

# Настройка nginx (если используется)
# См. nginx.conf для конфигурации
```

## Решение проблем

### Сервис не запускается

```bash
# Проверка логов
docker-compose logs app

# Проверка ошибок Python
journalctl -u portfolio-ai -f

# Перезапуск
systemctl restart portfolio-ai
```

### Ошибка подключения к БД

```bash
# Создание директорий данных
mkdir -p data chroma_db
docker-compose restart app
```

### Telegram бот не отвечает

```bash
# Проверка токена
curl https://api.telegram.org/bot<TOKEN>/getMe

# Перезапуск бота
docker-compose restart app
```

## Обновление после деплоя

```bash
# На сервере
cd /opt/portfolio-ai
git pull origin main
docker-compose down
docker-compose up -d --build

# Проверка
curl http://localhost:8000/health
```

## Откат изменений

```bash
# Откат git
git log --oneline -10
git reset --hard HEAD~1

# Или восстановление из бэкапа
python scripts/backup.py list
python scripts/backup.py restore --file backup_20260318_120000.tar.gz --yes
```

## Полезные команды

```bash
# Логи в реальном времени
docker-compose logs -f app

# Статистика
curl http://localhost:8000/api/stats

# Экспорт логов
curl http://localhost:8000/api/admin/export/interactions > logs.csv

# Бэкап вручную
./scripts/backup.sh

# Очистка Docker
./scripts/cleanup.sh
```

## Чек-лист перед деплоем

- [ ] Все тесты пройдены (`./scripts/test-before-deploy.sh`)
- [ ] `.env` настроен с реальными ключами
- [ ] Документы загружены в RAG
- [ ] Git push выполнен
- [ ] Доступ к серверу проверен (`ssh root@95.81.123.214`)
- [ ] Домен настроен (если используется)

## Контакты для поддержки

При возникновении проблем:
1. Проверьте логи: `docker-compose logs`
2. Проверьте статус: `systemctl status portfolio-ai`
3. Свяжитесь через Telegram или email

---

**Последнее обновление**: Март 2026  
**Версия**: 1.0.0
