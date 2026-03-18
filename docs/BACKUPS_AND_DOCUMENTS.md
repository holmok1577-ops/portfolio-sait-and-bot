# Руководство по бэкапам и загрузке документов

## Бэкапы

### Автоматические бэкапы

Бэкапы создаются автоматически при запуске сервиса backup:

```bash
# Создать бэкап вручную
docker-compose --profile backup run --rm backup

# Или через скрипт
python scripts/backup.py create
```

### Ручное управление бэкапами

```bash
# Создать бэкап
python scripts/backup.py create

# Список бэкапов
python scripts/backup.py list

# Восстановить из бэкапа
python scripts/backup.py restore --file backup_20260318_120000.tar.gz --yes

# Очистка старых бэкапов
python scripts/backup.py cleanup
```

### Настройка автоматических бэкапов (cron)

```bash
# Редактируем crontab
crontab -e

# Добавляем строку для бэкапа каждый день в 3:00
0 3 * * * cd /opt/portfolio-ai && docker-compose --profile backup run --rm backup
```

### Что включается в бэкап

- База данных SQLite (`data/`)
- Векторная база ChromaDB (`chroma_db/`)
- Документы (`docs/`)
- Метаданные бэкапа

### Где хранятся бэкапы

```
backups/
├── backup_20260318_120000.tar.gz
├── backup_20260317_120000.tar.gz
└── ...
```

Настройки в `.env`:
```env
MAX_BACKUPS=10          # Хранить последние 10 бэкапов
KEEP_BACKUP_DAYS=30     # Удалять старше 30 дней
```

## Загрузка документов в RAG

### Поддерживаемые форматы

- `.txt` - текстовые файлы
- `.md` - Markdown файлы
- `.json` - JSON документы

### Кодировки

Все файлы автоматически конвертируются в UTF-8. Поддерживаются:
- UTF-8
- UTF-8 with BOM
- UTF-16
- Windows-1251 (кириллица)
- Windows-1252
- KOI8-R
- ISO-8859-5
- И другие

### Имена файлов

Имена файлов с кириллицей полностью поддерживаются:
```bash
# Работает корректно
python scripts/upload_docs.py "документ.txt"
python scripts/upload_docs.py "инструкция по эксплуатации.md"
```

### Способы загрузки

#### 1. Через админ-панель (веб)

1. Откройте http://localhost:8000/admin.html
2. Перейдите в раздел "Документы"
3. Нажмите "Загрузить документ"
4. Выберите файл и укажите категорию

#### 2. Через скрипт (CLI)

```bash
# Один файл
python scripts/upload_docs.py docs/myfile.txt --source documentation --category faq

# Пакетная загрузка директории
python scripts/upload_docs.py docs/ --batch --pattern "*.txt" --category general

# Загрузка Markdown файлов
python scripts/upload_docs.py docs/ --batch --pattern "*.md" --category documentation
```

#### 3. Через API

```bash
curl -X POST -F "file=@document.txt" \
  -F "metadata={\"source\":\"docs\",\"category\":\"faq\"}" \
  http://localhost:8000/api/admin/upload
```

### Категории документов

- `general` - общие документы
- `documentation` - документация
- `faq` - часто задаваемые вопросы
- `blog` - блог посты

### Разбиение на чанки

Большие документы автоматически разбиваются на части:

```bash
# Размер чанка (по умолчанию 1000 символов)
python scripts/upload_docs.py large.txt --chunk-size 2000

# Без разбиения
python scripts/upload_docs.py small.txt --no-chunks
```

### Проверка UTF-8 перед загрузкой

```bash
# Проверить все файлы в директории
python scripts/upload_docs.py docs/ --validate
```

### Структура директории для документов

Рекомендуемая структура:
```
docs/
├── faq/
│   ├── общие_вопросы.txt
│   ├── техническая_поддержка.txt
│   └── pricing.txt
├── documentation/
│   ├── api_reference.md
│   └── setup_guide.md
└── blog/
    └── articles/
```

### Примеры загрузки

```bash
# Пример 1: Загрузка FAQ
python scripts/upload_docs.py docs/faq/ --batch --category faq

# Пример 2: Загрузка документации с разбиением на чанки
python scripts/upload_docs.py docs/api.md --category documentation --chunk-size 1500

# Пример 3: Загрузка с автоматическим определением категории
python scripts/upload_docs.py docs/ --batch --pattern "*.txt"

# Пример 4: Проверка и загрузка
python scripts/upload_docs.py docs/ --validate
python scripts/upload_docs.py docs/ --batch
```

### Управление документами в админке

**Просмотр:**
- Список всех документов с ID
- Превью текста
- Категория и источник

**Удаление:**
- Индивидуальное удаление по ID
- Удаляются также все чанки документа

### Проверка загруженных документов

```bash
# Через API
curl http://localhost:8000/api/admin/documents

# В Telegram боте
/stats - показывает количество документов
```

### Восстановление из бэкапа

Если нужно восстановить документы из бэкапа:

```bash
# 1. Остановить сервис
docker-compose down

# 2. Восстановить из бэкапа
python scripts/backup.py restore --file backup_20260318_120000.tar.gz --yes

# 3. Запустить сервис
docker-compose up -d
```

## Рекомендации

1. **Регулярные бэкапы:** Настройте автоматические бэкапы через cron
2. **Проверка загрузки:** Всегда проверяйте UTF-8 перед массовой загрузкой
3. **Структура:** Организуйте документы по категориям для лучшего поиска
4. **Размер файлов:** Очень большие файлы (>10MB) разбивайте на части
5. **Тестирование:** После загрузки протестируйте поиск через чат-бота
