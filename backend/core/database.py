# -*- coding: utf-8 -*-
"""
База данных для логирования и мониторинга
"""
import sqlite3
import json
import csv
import io
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
from contextlib import contextmanager
from loguru import logger

from config.settings import DATA_DIR


class DatabaseManager:
    """Управление базой данных SQLite"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DATA_DIR / "app.db")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()
        logger.info(f"DatabaseManager инициализирован: {self.db_path}")
    
    @contextmanager
    def _get_connection(self):
        """Контекстный менеджер для соединений"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_tables(self):
        """Инициализация таблиц"""
        with self._get_connection() as conn:
            # Логи взаимодействий
            conn.execute("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    source TEXT NOT NULL,
                    user_id TEXT,
                    username TEXT,
                    query TEXT NOT NULL,
                    response TEXT NOT NULL,
                    mode TEXT,
                    from_cache BOOLEAN DEFAULT 0,
                    response_time_ms INTEGER,
                    metadata TEXT
                )
            """)
            
            # Логи системных событий
            conn.execute("""
                CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    component TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details TEXT
                )
            """)
            
            # Метрики здоровья системы
            conn.execute("""
                CREATE TABLE IF NOT EXISTS health_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    component TEXT NOT NULL,
                    status TEXT NOT NULL,
                    response_time_ms INTEGER,
                    details TEXT
                )
            """)
            
            # Формы обратной связи
            conn.execute("""
                CREATE TABLE IF NOT EXISTS contact_forms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    subject TEXT,
                    message TEXT NOT NULL,
                    source_ip TEXT,
                    user_agent TEXT,
                    status TEXT DEFAULT 'new'
                )
            """)
            
            # Индексы
            conn.execute("CREATE INDEX IF NOT EXISTS idx_interactions_time ON interactions(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_interactions_user ON interactions(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_system_logs_time ON system_logs(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_health_time ON health_metrics(timestamp)")
    
    def log_interaction(
        self,
        query: str,
        response: str,
        source: str = "api",
        user_id: str = None,
        username: str = None,
        mode: str = None,
        from_cache: bool = False,
        response_time_ms: int = 0,
        metadata: Dict = None
    ):
        """Логирование взаимодействия с AI"""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO interactions 
                    (timestamp, source, user_id, username, query, response, mode, 
                     from_cache, response_time_ms, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(),
                    source,
                    user_id,
                    username,
                    query,
                    response,
                    mode,
                    from_cache,
                    response_time_ms,
                    json.dumps(metadata or {}, ensure_ascii=False)
                ))
        except Exception as e:
            logger.error(f"Ошибка логирования: {e}")
    
    def log_system_event(
        self,
        level: str,
        component: str,
        message: str,
        details: Dict = None
    ):
        """Логирование системного события"""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO system_logs (timestamp, level, component, message, details)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(),
                    level,
                    component,
                    message,
                    json.dumps(details or {}, ensure_ascii=False)
                ))
        except Exception as e:
            logger.error(f"Ошибка логирования события: {e}")
    
    def log_health_check(
        self,
        component: str,
        status: str,
        response_time_ms: int = 0,
        details: Dict = None
    ):
        """Логирование проверки здоровья"""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO health_metrics (timestamp, component, status, response_time_ms, details)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(),
                    component,
                    status,
                    response_time_ms,
                    json.dumps(details or {}, ensure_ascii=False)
                ))
        except Exception as e:
            logger.error(f"Ошибка логирования health check: {e}")
    
    def save_contact_form(
        self,
        name: str,
        email: str,
        message: str,
        subject: str = None,
        source_ip: str = None,
        user_agent: str = None
    ) -> int:
        """Сохранение формы обратной связи"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO contact_forms 
                    (timestamp, name, email, subject, message, source_ip, user_agent)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(),
                    name,
                    email,
                    subject,
                    message,
                    source_ip,
                    user_agent
                ))
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Ошибка сохранения формы: {e}")
            return None
    
    def get_contact_forms(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Получение форм обратной связи"""
        query = """
            SELECT 
                id,
                timestamp,
                name,
                email,
                subject,
                message,
                source_ip,
                user_agent
            FROM contact_forms 
            ORDER BY timestamp DESC 
            LIMIT ? OFFSET ?
        """
        
        with self._get_connection() as conn:
            cursor = conn.execute(query, (limit, offset))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def get_interactions(
        self,
        source: str = None,
        user_id: str = None,
        start_date: str = None,
        end_date: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Получение логов взаимодействий"""
        query = "SELECT * FROM interactions WHERE 1=1"
        params = []
        
        if source:
            query += " AND source = ?"
            params.append(source)
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)
        
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def get_stats(self, days: int = 7) -> Dict[str, Any]:
        """Получение статистики"""
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        with self._get_connection() as conn:
            # Общая статистика
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN from_cache = 1 THEN 1 ELSE 0 END) as cached,
                    AVG(response_time_ms) as avg_time
                FROM interactions
                WHERE timestamp >= ?
            """, (start_date,))
            row = cursor.fetchone()
            
            # Уникальные пользователи
            cursor = conn.execute("""
                SELECT COUNT(DISTINCT user_id) as unique_users
                FROM interactions
                WHERE timestamp >= ? AND user_id IS NOT NULL
            """, (start_date,))
            unique_row = cursor.fetchone()
            
            # По источникам
            cursor = conn.execute("""
                SELECT source, COUNT(*) as count
                FROM interactions
                WHERE timestamp >= ?
                GROUP BY source
            """, (start_date,))
            by_source = {row[0]: row[1] for row in cursor.fetchall()}
            
            return {
                "total_requests": row[0] or 0,
                "cached_requests": row[1] or 0,
                "avg_response_time_ms": row[2] or 0,
                "unique_users": unique_row[0] or 0,
                "by_source": by_source,
                "period_days": days
            }
    
    def export_to_csv(
        self,
        table: str = "interactions",
        start_date: str = None,
        end_date: str = None
    ) -> str:
        """Экспорт данных в CSV"""
        valid_tables = ["interactions", "system_logs", "health_metrics", "contact_forms"]
        if table not in valid_tables:
            raise ValueError(f"Недопустимая таблица: {table}")
        
        query = f"SELECT * FROM {table} WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)
        
        query += " ORDER BY timestamp DESC"
        
        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            
            if not rows:
                return ""
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Заголовки
            headers = [description[0] for description in cursor.description]
            writer.writerow(headers)
            
            # Данные
            for row in rows:
                writer.writerow(row)
            
            return output.getvalue()
    
    def cleanup_old_logs(self, days: int = 30):
        """Очистка старых логов"""
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        with self._get_connection() as conn:
            for table in ["interactions", "system_logs", "health_metrics"]:
                conn.execute(f"DELETE FROM {table} WHERE timestamp < ?", (cutoff_date,))
            
            logger.info(f"Очищены логи старше {days} дней")
