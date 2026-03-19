# Portfolio Site & AI Assistant

Современный сайт-портфолио с интегрированным AI-ассистентом, работающим в двух режимах: RAG (на основе базы знаний) и обычный AI-помощник.

## Возможности

### Сайт
- 🎨 Современный дизайн с темной темой
- 📱 Адаптивная верстка
- 📝 Форма обратной связи с уведомлениями
- 👤 Админ-панель с логами и статистикой

### AI Ассистент
- 🤖 Два режима работы:
  - **RAG**: Ответы на основе загруженных документов
  - **AI Помощник**: Общий разговорный AI с памятью
- 💾 Кэширование ответов
- 📊 Логирование всех взаимодействий
- 🔄 Переключение режимов в чате

### Telegram Бот
- 📱 Полная интеграция с Telegram
- 🔄 Общая база знаний с сайтом
- 📊 Команды статистики и управления
- 🔔 Уведомления администратору

### Инфраструктура
- 🐳 Docker + Docker Compose
- 📊 Мониторинг 24/7
- 🚨 Автоматические уведомления о сбоях
- 📦 Автоподъем после падений
- 🔄 Бэкапы и версионирование через Git

## Технологии

- **Backend**: Python 3.8.10, FastAPI, SQLAlchemy
- **AI**: OpenAI API (ProxyAPI), LangChain, ChromaDB
- **Бот**: python-telegram-bot
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Инфраструктура**: Docker, Nginx (опционально)

## Быстрый старт

### 1. Клонирование репозитория

```bash
git clone https://github.com/holmok1577-ops/portfolio-sait-and-bot.git
cd portfolio-sait-and-bot
```

### 2. Настройка окружения

```bash
cp .env.example .env
# Отредактируйте .env файл с вашими ключами
```

Обязательные переменные:
```env
PROXY_API_KEY=your_proxyapi_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
ADMIN_TELEGRAM_ID=your_telegram_id_for_alerts
```

### 3. Запуск с Docker

```bash
docker-compose up -d
```

Или локально:

```bash
pip install -r requirements.txt
python run.py --mode combined
```

### 4. Доступ

- Сайт: http://localhost:8000
- API документация: http://localhost:8000/api/docs
- Админ панель: http://localhost:8000/admin.html

## Режимы работы

### Режимы запуска

```bash
# Веб-сервер + Telegram бот (по умолчанию)
python run.py --mode combined

# Только веб-сервер
python run.py --mode server

# Только Telegram бот
python run.py --mode bot
```

### Docker режимы

```bash
# Базовый запуск
docker-compose up -d

# С Nginx (SSL/проксирование)
docker-compose --profile with-nginx up -d
```

## Деплой на сервер

### Автоматический деплой

```bash
./scripts/deploy.sh
```

### Ручной деплой

1. Подключитесь к серверу:
```bash
ssh root@95.81.123.214
```

2. Выполните команды из скрипта deploy.sh

### Настройка автозапуска (systemd)

```bash
sudo cp scripts/portfolio-ai.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable portfolio-ai
sudo systemctl start portfolio-ai
```

## API Endpoints

### Публичные

- `GET /health` — Проверка здоровья системы
- `POST /api/query` — Запрос к AI ассистенту
- `GET /api/modes` — Список доступных режимов
- `POST /api/mode` — Переключение режима
- `POST /api/contact` — Форма обратной связи

### Административные

- `GET /api/stats` — Статистика
- `GET /api/admin/logs` — Логи взаимодействий
- `GET /api/admin/export/{table}` — Экспорт в CSV
- `POST /api/admin/upload` — Загрузка документа
- `GET /api/admin/documents` — Список документов
- `DELETE /api/admin/documents/{id}` — Удаление документа

## Структура проекта

```
portfolio-sait-and-bot/
├── backend/
│   ├── api/           # FastAPI endpoints
│   ├── bot/           # Telegram бот
│   └── core/          # Ядро: AI, кэш, БД, мониторинг
├── frontend/          # HTML/CSS/JS
├── config/            # Конфигурация
├── data/              # Данные SQLite
├── chroma_db/         # Векторная база
├── logs/              # Логи
├── scripts/           # Скрипты деплоя
├── docs/              # Документы для RAG
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `PROXY_API_KEY` | Ключ ProxyAPI | - |
| `TELEGRAM_BOT_TOKEN` | Токен Telegram бота | - |
| `ADMIN_TELEGRAM_ID` | ID админа для уведомлений | - |
| `AI_MODEL` | Модель OpenAI | gpt-3.5-turbo |
| `HOST` | Хост сервера | 0.0.0.0 |
| `PORT` | Порт | 8000 |
| `DEBUG` | Режим отладки | false |
| `AUTO_RESTART` | Автоподъем | true |

## Мониторинг

### Health Check
```bash
curl http://localhost:8000/health
```

### Логи
```bash
# Docker
docker-compose logs -f app

# Файлы
ls -la logs/
```

### Метрики в админке
- Общее количество запросов
- Процент кэшированных ответов
- Уникальные пользователи
- Среднее время ответа
- Статус компонентов

## Управление документами RAG

### Через админ-панель
1. Перейдите в раздел "Документы"
2. Нажмите "Загрузить документ"
3. Выберите .txt или .md файл
4. Укажите источник и категорию

### Через API
```bash
curl -X POST -F "file=@document.txt" \
  -F "metadata={\"source\":\"docs\",\"category\":\"faq\"}" \
  http://localhost:8000/api/admin/upload
```

## Безопасность

- Все файлы в UTF-8
- Валидация входных данных
- Ограничение размера загружаемых файлов
- Защита от XSS (экранирование)

## Лицензия

MIT License

## Поддержка

При возникновении проблем:
1. Проверьте логи: `docker-compose logs`
2. Проверьте статус: `curl http://localhost:8000/health`
3. Убедитесь что все переменные окружения настроены

## Разработка

### Установка зависимостей
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Запуск в режиме разработки
```bash
python run.py --mode combined
```

---

**Версия**: 1.2.1  
**Python**: 3.8.10  
**Обновлено**: Март 2026
