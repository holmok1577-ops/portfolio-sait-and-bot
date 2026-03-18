# -*- coding: utf-8 -*-
"""
Система кэширования ответов
"""
import json
import hashlib
import time
from typing import Optional, Dict, Any
from pathlib import Path
from loguru import logger

from config.settings import CACHE_ENABLED, CACHE_TTL


class ResponseCache:
    """Кэш для хранения ответов AI"""
    
    def __init__(self, cache_file: str = None, ttl: int = None):
        self.cache_file = cache_file or "cache.json"
        self.ttl = ttl or CACHE_TTL
        self.cache: Dict[str, Dict[str, Any]] = {}
        self._load()
        
        logger.info(f"Cache инициализирован: {self.cache_file}")
    
    def _get_key(self, query: str) -> str:
        """Генерация ключа кэша"""
        return hashlib.md5(query.lower().strip().encode()).hexdigest()
    
    def _load(self):
        """Загрузка кэша из файла"""
        try:
            if Path(self.cache_file).exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                # Очистка устаревших записей
                self._cleanup()
        except Exception as e:
            logger.error(f"Ошибка загрузки кэша: {e}")
            self.cache = {}
    
    def _save(self):
        """Сохранение кэша в файл"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения кэша: {e}")
    
    def _cleanup(self):
        """Очистка устаревших записей"""
        current_time = time.time()
        expired_keys = [
            key for key, value in self.cache.items()
            if current_time - value.get("timestamp", 0) > self.ttl
        ]
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.info(f"Очищено {len(expired_keys)} устаревших записей")
    
    def get(self, query: str) -> Optional[str]:
        """Получение ответа из кэша"""
        if not CACHE_ENABLED:
            return None
        
        key = self._get_key(query)
        if key in self.cache:
            entry = self.cache[key]
            # Проверка TTL
            if time.time() - entry.get("timestamp", 0) <= self.ttl:
                logger.debug(f"Cache hit: {key[:8]}...")
                return entry.get("response")
            else:
                # Удаление устаревшей записи
                del self.cache[key]
        
        return None
    
    def set(self, query: str, response: str, metadata: Dict = None):
        """Сохранение ответа в кэш"""
        if not CACHE_ENABLED:
            return
        
        key = self._get_key(query)
        self.cache[key] = {
            "response": response,
            "timestamp": time.time(),
            "query": query[:100],  # Сохраняем часть запроса для отладки
            "metadata": metadata or {}
        }
        
        self._save()
        logger.debug(f"Cache set: {key[:8]}...")
    
    def clear(self):
        """Очистка всего кэша"""
        self.cache.clear()
        self._save()
        logger.info("Кэш очищен")
    
    def size(self) -> int:
        """Количество записей в кэше"""
        return len(self.cache)
    
    def get_stats(self) -> Dict[str, Any]:
        """Статистика кэша"""
        return {
            "size": len(self.cache),
            "ttl": self.ttl,
            "file": self.cache_file
        }
