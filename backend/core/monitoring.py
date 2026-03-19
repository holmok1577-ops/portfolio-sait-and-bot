# -*- coding: utf-8 -*-
"""
Система мониторинга и уведомлений
"""
import asyncio
import aiohttp
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from loguru import logger

from config.settings import (
    TELEGRAM_BOT_TOKEN, ADMIN_TELEGRAM_ID,
    HEALTH_CHECK_INTERVAL, ALERT_COOLDOWN, AUTO_RESTART
)


class AlertManager:
    """Управление уведомлениями в Telegram"""
    
    def __init__(self):
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.admin_id = ADMIN_TELEGRAM_ID
        self.last_alerts: Dict[str, datetime] = {}
        self.alert_cooldown = timedelta(seconds=ALERT_COOLDOWN)
        
        if not self.bot_token or not self.admin_id:
            logger.warning("AlertManager: не настроены TELEGRAM_BOT_TOKEN или ADMIN_TELEGRAM_ID")
    
    async def send_alert(self, message: str, alert_type: str = "general", force: bool = False):
        """Отправка уведомления администратору"""
        if not self.bot_token or not self.admin_id:
            logger.warning(f"Алерт не отправлен (не настроен): {message}")
            return False
        
        # Проверка cooldown
        if not force:
            last_alert = self.last_alerts.get(alert_type)
            if last_alert and datetime.now() - last_alert < self.alert_cooldown:
                logger.debug(f"Алерт {alert_type} в cooldown")
                return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            # Добавляем emoji в зависимости от типа
            emoji_map = {
                "error": "❌",
                "warning": "⚠️",
                "info": "ℹ️",
                "recovery": "✅",
                "startup": "🚀"
            }
            emoji = emoji_map.get(alert_type, "🔔")
            
            full_message = f"{emoji} <b>{alert_type.upper()}</b>\n\n{message}\n\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={
                    "chat_id": self.admin_id,
                    "text": full_message,
                    "parse_mode": "HTML"
                }) as response:
                    if response.status == 200:
                        self.last_alerts[alert_type] = datetime.now()
                        logger.info(f"Алерт отправлен: {alert_type}")
                        return True
                    else:
                        logger.error(f"Ошибка отправки алерта: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Ошибка отправки алерта: {e}")
            return False
    
    async def send_startup_notification(self, components: Dict[str, str]):
        """Уведомление о запуске системы"""
        message = "🚀 *Система запущена*\n\n"
        for component, status in components.items():
            emoji = "✅" if status == "ok" else "❌"
            message += f"{emoji} {component}: {status}\n"
        
        await self.send_alert(message, "startup", force=True)
    
    async def send_error_alert(self, component: str, error: str, details: str = None):
        """Уведомление об ошибке"""
        message = f"❌ *Ошибка в компоненте: {component}*\n\n{error}"
        if details:
            message += f"\n\n_Детали:_ {details[:500]}"
        
        await self.send_alert(message, "error")
    
    async def send_recovery_notification(self, component: str):
        """Уведомление о восстановлении"""
        message = f"✅ *Компонент восстановлен: {component}*\n\nСервис снова работает нормально."
        await self.send_alert(message, "recovery")


class HealthChecker:
    """Проверка здоровья компонентов системы"""
    
    def __init__(self, db_manager, alert_manager: AlertManager):
        self.db = db_manager
        self.alerts = alert_manager
        self.components: Dict[str, Dict[str, Any]] = {
            "web_server": {"status": "unknown", "last_check": None},
            "telegram_bot": {"status": "unknown", "last_check": None},
            "ai_service": {"status": "unknown", "last_check": None},
            "database": {"status": "unknown", "last_check": None},
            "vector_db": {"status": "unknown", "last_check": None}
        }
        self.failed_components: set = set()
        self._running = False
        
        logger.info("HealthChecker инициализирован")
    
    async def check_web_server(self, url: str = "http://localhost:8000/health") -> bool:
        """Проверка веб-сервера"""
        try:
            start_time = time.time()
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    response_time = int((time.time() - start_time) * 1000)
                    
                    is_healthy = response.status == 200
                    self._update_component_status("web_server", is_healthy, response_time)
                    return is_healthy
                    
        except Exception as e:
            self._update_component_status("web_server", False, error=str(e))
            return False
    
    async def check_telegram_bot(self) -> bool:
        """Проверка Telegram бота (через API)"""
        if not TELEGRAM_BOT_TOKEN:
            self._update_component_status("telegram_bot", False, error="No token")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    is_healthy = response.status == 200
                    self._update_component_status("telegram_bot", is_healthy)
                    return is_healthy
                    
        except Exception as e:
            self._update_component_status("telegram_bot", False, error=str(e))
            return False
    
    async def check_ai_service(self) -> bool:
        """Проверка доступности AI API"""
        from config.settings import PROXY_API_KEY, PROXY_API_BASE
        
        if not PROXY_API_KEY:
            self._update_component_status("ai_service", False, error="No API key")
            return False
        
        try:
            import openai
            client = openai.OpenAI(api_key=PROXY_API_KEY, base_url=PROXY_API_BASE)
            # Пробный запрос
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5
            )
            self._update_component_status("ai_service", True)
            return True
            
        except Exception as e:
            self._update_component_status("ai_service", False, error=str(e))
            return False
    
    async def check_database(self) -> bool:
        """Проверка базы данных"""
        try:
            # Пробный запрос
            self.db.get_stats(days=1)
            self._update_component_status("database", True)
            return True
            
        except Exception as e:
            self._update_component_status("database", False, error=str(e))
            return False
    
    def _update_component_status(self, component: str, is_healthy: bool, 
                                  response_time: int = 0, error: str = None):
        """Обновление статуса компонента"""
        old_status = self.components[component]["status"]
        new_status = "ok" if is_healthy else "error"
        
        self.components[component].update({
            "status": new_status,
            "last_check": datetime.now().isoformat(),
            "response_time_ms": response_time,
            "error": error
        })
        
        # Логирование в БД
        self.db.log_health_check(
            component=component,
            status=new_status,
            response_time_ms=response_time,
            details={"error": error} if error else None
        )
        
        # Уведомления о изменении статуса
        if old_status != new_status:
            if new_status == "error" and component not in self.failed_components:
                self.failed_components.add(component)
                asyncio.create_task(
                    self.alerts.send_error_alert(
                        component, 
                        f"Компонент недоступен", 
                        error
                    )
                )
            elif new_status == "ok" and component in self.failed_components:
                self.failed_components.discard(component)
                asyncio.create_task(
                    self.alerts.send_recovery_notification(component)
                )
    
    async def run_health_checks(self):
        """Запуск всех проверок"""
        await self.check_web_server()
        await self.check_telegram_bot()
        await self.check_database()
        # AI проверку делаем реже (каждые 5 минут)
        if not hasattr(self, '_last_ai_check') or \
           time.time() - self._last_ai_check > 300:
            await self.check_ai_service()
            self._last_ai_check = time.time()
    
    async def start_monitoring(self):
        """Запуск постоянного мониторинга"""
        self._running = True
        logger.info("Health monitoring запущен")
        
        while self._running:
            try:
                await self.run_health_checks()
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            except Exception as e:
                logger.error(f"Ошибка в health monitoring: {e}")
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)
    
    def stop_monitoring(self):
        """Остановка мониторинга"""
        self._running = False
        logger.info("Health monitoring остановлен")
    
    def get_status(self) -> Dict[str, Any]:
        """Получение текущего статуса всех компонентов"""
        return {
            "components": self.components,
            "failed_count": len(self.failed_components),
            "overall_status": "healthy" if not self.failed_components else "degraded",
            "timestamp": datetime.now().isoformat()
        }
