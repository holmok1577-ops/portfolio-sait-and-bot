#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Основной скрипт запуска приложения Portfolio + AI Assistant
Запускает веб-сервер и Telegram бот вместе
"""
import asyncio
import signal
import sys
from contextlib import asynccontextmanager

from loguru import logger
import uvicorn

from config.settings import HOST, PORT, DEBUG, TELEGRAM_BOT_TOKEN
from backend.api.main_api import app, embedding_store, assistant, cache, db, alert_manager, health_checker
from backend.bot.telegram_bot import TelegramBot


class ApplicationManager:
    """Управление жизненным циклом приложения"""
    
    def __init__(self):
        self.telegram_bot = None
        self.shutdown_event = asyncio.Event()
        
    async def start_telegram_bot(self):
        """Запуск Telegram бота"""
        if not TELEGRAM_BOT_TOKEN:
            logger.warning("TELEGRAM_BOT_TOKEN не настроен, бот не будет запущен")
            return
        
        try:
            self.telegram_bot = TelegramBot(assistant, cache, db)
            await self.telegram_bot.start_async()
            logger.info("✅ Telegram бот запущен")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска Telegram бота: {e}")
            if alert_manager:
                await alert_manager.send_error_alert("Telegram Bot", str(e))
    
    async def stop_telegram_bot(self):
        """Остановка Telegram бота"""
        if self.telegram_bot:
            try:
                await self.telegram_bot.stop_async()
                logger.info("Telegram бот остановлен")
            except Exception as e:
                logger.error(f"Ошибка остановки Telegram бота: {e}")
    
    async def start_monitoring(self):
        """Запуск мониторинга"""
        if health_checker:
            asyncio.create_task(health_checker.start_monitoring())
    
    def setup_signal_handlers(self):
        """Настройка обработчиков сигналов"""
        def signal_handler(sig, frame):
            logger.info(f"Получен сигнал {sig}, начинаем graceful shutdown...")
            self.shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def run(self):
        """Основной цикл приложения"""
        self.setup_signal_handlers()
        
        # Запуск Telegram бота
        await self.start_telegram_bot()
        
        # Запуск мониторинга
        await self.start_monitoring()
        
        # Ожидание сигнала завершения
        await self.shutdown_event.wait()
        
        # Graceful shutdown
        logger.info("Выполняется graceful shutdown...")
        await self.stop_telegram_bot()
        
        if health_checker:
            health_checker.stop_monitoring()
        
        if embedding_store:
            embedding_store.persist()
        
        logger.info("✅ Приложение остановлено")


# Создание менеджера приложения
app_manager = ApplicationManager()


@asynccontextmanager
async def lifespan(app):
    """Управление жизненным циклом FastAPI"""
    # Startup уже выполнен в main_api.py
    
    yield
    
    # Shutdown
    logger.info("FastAPI shutdown...")


def run_server():
    """Запуск только веб-сервера"""
    logger.info(f"🚀 Запуск веб-сервера на {HOST}:{PORT}")
    uvicorn.run(
        "run:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level="info" if DEBUG else "warning"
    )


def run_bot_only():
    """Запуск только Telegram бота"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не настроен!")
        sys.exit(1)
    
    from backend.core.embeddings import EmbeddingStore, get_sample_documents
    from backend.core.cache import ResponseCache
    from backend.core.database import DatabaseManager
    from backend.core.ai_core import UnifiedAssistant
    
    # Инициализация компонентов
    db = DatabaseManager()
    cache = ResponseCache()
    embedding_store = EmbeddingStore()
    
    if embedding_store.count() == 0:
        sample_docs = get_sample_documents()
        embedding_store.add_documents(sample_docs)
    
    assistant = UnifiedAssistant(embedding_store)
    
    # Запуск бота
    bot = TelegramBot(assistant, cache, db)
    logger.info("🤖 Запуск только Telegram бота...")
    bot.run()


async def run_combined():
    """Запуск веб-сервера и бота вместе"""
    # Инициализация компонентов выполняется в lifespan main_api.py
    
    # Запуск менеджера приложения (Telegram бот + мониторинг)
    asyncio.create_task(app_manager.run())
    
    # Запуск веб-сервера
    config = uvicorn.Config(
        "backend.api.main_api:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level="info" if DEBUG else "warning"
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Portfolio AI Assistant")
    parser.add_argument(
        "--mode",
        choices=["server", "bot", "combined"],
        default="combined",
        help="Режим запуска: server (только веб), bot (только Telegram), combined (оба)"
    )
    
    args = parser.parse_args()
    
    if args.mode == "server":
        run_server()
    elif args.mode == "bot":
        run_bot_only()
    else:
        # Combined mode - используем asyncio
        try:
            asyncio.run(run_combined())
        except KeyboardInterrupt:
            logger.info("Прервано пользователем")
            sys.exit(0)
