# -*- coding: utf-8 -*-
"""
Telegram бот для взаимодействия с AI ассистентом
"""
import asyncio
from typing import Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
from loguru import logger

from config.settings import TELEGRAM_BOT_TOKEN, ADMIN_TELEGRAM_ID
from backend.core.ai_core import UnifiedAssistant
from backend.core.cache import ResponseCache
from backend.core.database import DatabaseManager


class TelegramBot:
    """Telegram бот с поддержкой RAG и AI режимов"""
    
    def __init__(
        self,
        assistant: UnifiedAssistant,
        cache: ResponseCache,
        db: DatabaseManager
    ):
        self.assistant = assistant
        self.cache = cache
        self.db = db
        
        if not TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN не настроен")
        
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self._setup_handlers()
        
        # Хранение режимов пользователей
        self.user_modes: Dict[int, str] = {}
        
        logger.info("Telegram бот инициализирован")
    
    def _setup_handlers(self):
        """Настройка обработчиков команд"""
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(CommandHandler("mode", self.cmd_mode))
        self.application.add_handler(CommandHandler("stats", self.cmd_stats))
        self.application.add_handler(CommandHandler("clear", self.cmd_clear))
        self.application.add_handler(CommandHandler("logs", self.cmd_logs))
        
        # Callback для кнопок
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Текстовые сообщения
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
    
    def _get_welcome_text(self) -> str:
        """Текст приветствия"""
        return """🤖 *Добро пожаловать в AI Ассистент!*

Я могу работать в двух режимах:

📚 *RAG режим* — отвечаю на основе базы знаний с документами
💬 *AI Помощник* — общий искусственный интеллект с памятью

*Доступные команды:*
/mode — переключить режим
/stats — статистика системы
/clear — очистить историю разговора
/help — справка

Просто напишите мне, и я постараюсь помочь!"""
    
    def _get_help_text(self) -> str:
        """Текст справки"""
        return """📚 *Справка по использованию*

*Режимы работы:*
• /mode — переключить между RAG и AI помощником
• РAG использует базу знаний для точных ответов
• AI помощник ведет разговор с памятью контекста

*Управление:*
• /clear — очистить историю текущего разговора
• /stats — показать статистику системы
• /logs — получить свои логи (только для вас)

*Советы:*
• В RAG режиме задавайте конкретные вопросы
• В режиме помощника можно вести длинные диалоги
• История сохраняется между сессиями"""
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик /start"""
        await update.message.reply_text(
            self._get_welcome_text(),
            parse_mode="Markdown"
        )
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик /help"""
        await update.message.reply_text(
            self._get_help_text(),
            parse_mode="Markdown"
        )
    
    async def cmd_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик /mode — переключение режима"""
        user_id = update.effective_user.id
        current_mode = self.assistant.get_mode(str(user_id))
        
        # Кнопки выбора режима
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{'✅ ' if current_mode == 'rag' else ''}RAG Ассистент",
                    callback_data="mode_rag"
                ),
                InlineKeyboardButton(
                    f"{'✅ ' if current_mode == 'assistant' else ''}AI Помощник",
                    callback_data="mode_assistant"
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        mode_description = {
            "rag": "📚 Ответы на основе базы знаний",
            "assistant": "💬 Общий AI с памятью разговора"
        }
        
        await update.message.reply_text(
            f"🔄 *Текущий режим:* {current_mode.upper()}\n\n"
            f"{mode_description.get(current_mode, '')}\n\n"
            f"Выберите режим:",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик callback кнопок"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        if query.data.startswith("mode_"):
            mode = query.data.replace("mode_", "")
            self.assistant.set_mode(str(user_id), mode)
            
            mode_names = {
                "rag": "📚 RAG Ассистент",
                "assistant": "💬 AI Помощник"
            }
            
            await query.edit_message_text(
                f"✅ Режим изменен на: *{mode_names.get(mode, mode)}*",
                parse_mode="Markdown"
            )
    
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик /stats — статистика"""
        try:
            stats = self.db.get_stats(days=7)
            
            # Информация о режимах
            user_id = update.effective_user.id
            current_mode = self.assistant.get_mode(str(user_id))
            
            stats_text = f"""📊 *Статистика системы*

🤖 *Твой режим:* {current_mode.upper()}

📈 *За последние 7 дней:*
• Всего запросов: {stats['total_requests']}
• Из кэша: {stats['cached_requests']}
• Уникальных пользователей: {stats['unique_users']}
• Среднее время ответа: {stats['avg_response_time_ms']:.0f} мс

📊 *По источникам:*
"""
            for source, count in stats['by_source'].items():
                stats_text += f"• {source}: {count}\n"
            
            await update.message.reply_text(stats_text, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            await update.message.reply_text("❌ Ошибка получения статистики")
    
    async def cmd_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик /clear — очистка истории"""
        user_id = update.effective_user.id
        self.assistant.assistant_processor.clear_history(str(user_id))
        await update.message.reply_text("🗑 История разговора очищена!")
    
    async def cmd_logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик /logs — экспорт логов"""
        user_id = update.effective_user.id
        
        try:
            # Проверяем, это админ или обычный пользователь
            is_admin = str(user_id) == ADMIN_TELEGRAM_ID
            
            if is_admin:
                # Админ получает все логи
                csv_data = self.db.export_to_csv("interactions")
            else:
                # Обычный пользователь — только свои
                csv_data = self.db.export_to_csv(
                    "interactions",
                    start_date=None,
                    end_date=None
                )
                # TODO: фильтр по user_id
            
            if not csv_data:
                await update.message.reply_text("📝 Логов пока нет")
                return
            
            # Отправка файла
            from io import BytesIO
            file_obj = BytesIO(csv_data.encode('utf-8'))
            file_obj.name = f"logs_{user_id}_{int(asyncio.get_event_loop().time())}.csv"
            
            await update.message.reply_document(
                document=file_obj,
                caption="📊 Ваши логи взаимодействий"
            )
            
        except Exception as e:
            logger.error(f"Ошибка экспорта логов: {e}")
            await update.message.reply_text("❌ Ошибка при получении логов")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        user = update.effective_user
        user_id = user.id
        message_text = update.message.text
        
        # Показываем "печатает"
        await update.message.chat.send_action(action="typing")
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Получаем режим пользователя
            mode = self.assistant.get_mode(str(user_id))
            
            # Проверяем кэш
            cached = self.cache.get(message_text)
            from_cache = cached is not None
            
            if cached:
                answer = cached
            else:
                # Обработка через ассистент
                answer, metadata = self.assistant.process_query(
                    query=message_text,
                    user_id=str(user_id)
                )
                
                # Сохраняем в кэш
                self.cache.set(message_text, answer, metadata)
            
            response_time = int((asyncio.get_event_loop().time() - start_time) * 1000)
            
            # Логирование
            self.db.log_interaction(
                query=message_text,
                response=answer,
                source="telegram",
                user_id=str(user_id),
                username=user.username or user.first_name,
                mode=mode,
                from_cache=from_cache,
                response_time_ms=response_time
            )
            
            # Отправка ответа (разбиваем если длинный)
            if len(answer) <= 4000:
                await update.message.reply_text(answer)
            else:
                # Разбиваем на части
                for i in range(0, len(answer), 4000):
                    await update.message.reply_text(answer[i:i+4000])
            
            # Индикатор кэша
            if from_cache:
                await update.message.reply_text(
                    "💾 Ответ из кэша",
                    reply_to_message_id=update.message.message_id
                )
            
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при обработке запроса. Попробуйте позже."
            )
            
            # Логируем ошибку
            self.db.log_interaction(
                query=message_text,
                response=f"ERROR: {str(e)}",
                source="telegram",
                user_id=str(user_id),
                username=user.username or user.first_name,
                mode="unknown",
                from_cache=False,
                response_time_ms=0
            )
    
    def run(self):
        """Запуск бота"""
        logger.info("Запуск Telegram бота...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)
    
    async def start_async(self):
        """Асинхронный запуск (для использования с веб-сервером)"""
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        logger.info("Telegram бот запущен (async)")
    
    async def stop_async(self):
        """Асинхронная остановка"""
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
        logger.info("Telegram бот остановлен")
