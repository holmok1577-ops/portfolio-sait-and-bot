# -*- coding: utf-8 -*-
"""
Конфигурация проекта Portfolio + AI Assistant
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Базовые пути
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
CHROMA_DIR = BASE_DIR / "chroma_db"
DOCS_DIR = BASE_DIR / "docs"

# Создание директорий при необходимости
for dir_path in [DATA_DIR, LOGS_DIR, CHROMA_DIR]:
    dir_path.mkdir(exist_ok=True)

# API Keys
PROXY_API_KEY = os.getenv("PROXY_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID", "")

# Настройки базы данных
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/app.db")
LOGS_DB_PATH = str(DATA_DIR / "logs.db")

# Настройки AI
AI_MODEL = os.getenv("AI_MODEL", "gpt-3.5-turbo")
AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.7"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
PROXY_API_BASE = os.getenv("PROXY_API_BASE", "https://api.proxyapi.ru/openai/v1")

# Настройки RAG
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))
RAG_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.6"))

# Настройки сервера
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Настройки безопасности
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

# Настройки мониторинга
HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "60"))
ALERT_COOLDOWN = int(os.getenv("ALERT_COOLDOWN", "300"))  # 5 минут между алертами
AUTO_RESTART = os.getenv("AUTO_RESTART", "true").lower() == "true"

# Настройки кэша
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))  # 1 час

# Версия приложения
APP_VERSION = "1.0.1"
APP_NAME = "Portfolio AI Assistant"
