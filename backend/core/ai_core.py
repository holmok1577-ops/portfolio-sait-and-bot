# -*- coding: utf-8 -*-
"""
Ядро AI ассистента с поддержкой RAG и обычного режима
"""
import os
import time
from typing import List, Tuple, Optional, Dict, Any
from loguru import logger
import openai

from config.settings import (
    PROXY_API_KEY, PROXY_API_BASE, AI_MODEL, AI_TEMPERATURE,
    RAG_TOP_K, RAG_SIMILARITY_THRESHOLD, CACHE_ENABLED
)


class AICore:
    """Унифицированное ядро для работы с AI в режимах RAG и обычного помощника"""
    
    def __init__(self, embedding_store=None):
        self.embedding_store = embedding_store
        self.client = openai.OpenAI(
            api_key=PROXY_API_KEY,
            base_url=PROXY_API_BASE
        )
        self.model = AI_MODEL
        self.temperature = AI_TEMPERATURE
        
        # Системные промпты для разных режимов
        self.system_prompts = {
            "rag": """Ты AI-ассистент с доступом к базе знаний. 
Используй предоставленный контекст для ответа на вопросы.
Если в контексте нет релевантной информации, скажи об этом честно.
Отвечай на русском языке, кратко и по делу.""",
            
            "assistant": """Ты полезный AI-помощник. 
Отвечай на вопросы пользователя полно и понятно.
Если не знаешь ответ - скажи об этом.
Отвечай на русском языке."""
        }
        
        logger.info("AI Core инициализирован")
    
    def generate_response(
        self, 
        query: str, 
        mode: str = "rag",
        context: Optional[List[Dict[str, Any]]] = None,
        conversation_history: Optional[List[Dict]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Генерация ответа в зависимости от режима
        
        Args:
            query: Запрос пользователя
            mode: 'rag' или 'assistant'
            context: Контекст для RAG режима
            conversation_history: История разговора
            
        Returns:
            (ответ, метаданные)
        """
        start_time = time.time()
        
        try:
            messages = self._build_messages(query, mode, context, conversation_history)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=2000
            )
            
            answer = response.choices[0].message.content
            
            metadata = {
                "mode": mode,
                "response_time_ms": int((time.time() - start_time) * 1000),
                "model": self.model,
                "tokens_used": response.usage.total_tokens if response.usage else 0,
                "context_used": bool(context) if mode == "rag" else False
            }
            
            logger.info(f"Ответ сгенерирован: mode={mode}, time={metadata['response_time_ms']}ms")
            return answer, metadata
            
        except Exception as e:
            logger.error(f"Ошибка генерации ответа: {e}")
            raise
    
    def _build_messages(
        self, 
        query: str, 
        mode: str,
        context: Optional[List[Dict[str, Any]]],
        history: Optional[List[Dict]]
    ) -> List[Dict[str, str]]:
        """Формирование сообщений для API"""
        messages = []
        
        # Системный промпт
        system_prompt = self.system_prompts.get(mode, self.system_prompts["assistant"])
        
        # Добавляем контекст для RAG режима
        if mode == "rag" and context:
            context_text = "\n\n".join([
                f"[Документ {i+1}]\n{doc.get('text', doc.get('content', ''))}"
                for i, doc in enumerate(context)
            ])
            system_prompt += f"\n\nКонтекст:\n{context_text}"
        
        messages.append({"role": "system", "content": system_prompt})
        
        # История разговора
        if history:
            messages.extend(history[-10:])  # Последние 10 сообщений
        
        # Текущий запрос
        messages.append({"role": "user", "content": query})
        
        return messages


class RAGProcessor:
    """Обработчик RAG запросов с поиском по векторной базе"""
    
    def __init__(self, embedding_store):
        self.embedding_store = embedding_store
        self.ai_core = AICore(embedding_store)
        logger.info("RAG Processor инициализирован")
    
    def process_query(
        self, 
        query: str, 
        top_k: int = None,
        similarity_threshold: float = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Обработка RAG запроса
        
        Returns:
            (ответ, метаданные включая найденные документы)
        """
        top_k = top_k or RAG_TOP_K
        threshold = similarity_threshold or RAG_SIMILARITY_THRESHOLD
        
        logger.info(f"RAG запрос: '{query}', top_k={top_k}, threshold={threshold}")
        
        # Поиск релевантных документов
        search_results = self.embedding_store.search(query, top_k=top_k)
        logger.info(f"Найдено документов: {len(search_results)}")
        
        # Фильтрация по порогу схожести
        relevant_docs = [
            doc for doc in search_results 
            if doc.get('score', 0) >= threshold
        ]
        logger.info(f"Релевантных документов (score >= {threshold}): {len(relevant_docs)}")
        
        if relevant_docs:
            for i, doc in enumerate(relevant_docs):
                score = doc.get('score', 0)
                source = doc.get('metadata', {}).get('source', 'unknown')
                logger.info(f"Документ {i+1}: score={score:.3f}, source={source}")
        
        # Генерация ответа
        answer, ai_metadata = self.ai_core.generate_response(
            query=query,
            mode="rag",
            context=relevant_docs if relevant_docs else None
        )
        
        metadata = {
            **ai_metadata,
            "documents_found": len(search_results),
            "documents_used": len(relevant_docs),
            "sources": [doc.get('metadata', {}).get('source', 'unknown') for doc in relevant_docs]
        }
        
        return answer, metadata


class AssistantProcessor:
    """Обычный AI помощник без RAG"""
    
    def __init__(self):
        self.ai_core = AICore()
        self.conversations: Dict[str, List[Dict]] = {}
        logger.info("Assistant Processor инициализирован")
    
    def process_query(
        self, 
        query: str, 
        user_id: str = "default",
        reset_history: bool = False
    ) -> Tuple[str, Dict[str, Any]]:
        """Обработка запроса к AI помощнику"""
        
        # Управление историей разговора
        if reset_history or user_id not in self.conversations:
            self.conversations[user_id] = []
        
        history = self.conversations[user_id]
        
        # Генерация ответа
        answer, metadata = self.ai_core.generate_response(
            query=query,
            mode="assistant",
            conversation_history=history
        )
        
        # Сохранение в историю
        history.append({"role": "user", "content": query})
        history.append({"role": "assistant", "content": answer})
        
        # Ограничение истории
        if len(history) > 20:
            self.conversations[user_id] = history[-20:]
        
        metadata["history_length"] = len(history)
        return answer, metadata
    
    def clear_history(self, user_id: str = "default"):
        """Очистка истории разговора"""
        if user_id in self.conversations:
            self.conversations[user_id] = []
            logger.info(f"История очищена для пользователя {user_id}")


class UnifiedAssistant:
    """
    Унифицированный ассистент с переключением между RAG и обычным режимом
    """
    
    def __init__(self, embedding_store=None):
        self.rag_processor = RAGProcessor(embedding_store) if embedding_store else None
        self.assistant_processor = AssistantProcessor()
        self.user_modes: Dict[str, str] = {}  # Хранение режима по пользователю
        logger.info("Unified Assistant инициализирован")
    
    def set_mode(self, user_id: str, mode: str):
        """Установка режима для пользователя"""
        if mode not in ["rag", "assistant"]:
            raise ValueError(f"Неизвестный режим: {mode}")
        
        self.user_modes[user_id] = mode
        logger.info(f"Режим {mode} установлен для пользователя {user_id}")
    
    def get_mode(self, user_id: str) -> str:
        """Получение текущего режима пользователя"""
        return self.user_modes.get(user_id, "rag")  # По умолчанию RAG
    
    def process_query(
        self, 
        query: str, 
        user_id: str = "default",
        force_mode: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Обработка запроса в текущем или указанном режиме
        
        Args:
            query: Запрос пользователя
            user_id: ID пользователя
            force_mode: Принудительный режим (иначе используется текущий)
            
        Returns:
            (ответ, метаданные)
        """
        mode = force_mode or self.get_mode(user_id)
        
        start_time = time.time()
        
        if mode == "rag":
            if not self.rag_processor:
                logger.warning("RAG не доступен, переключение на assistant")
                answer, metadata = self.assistant_processor.process_query(query, user_id)
                mode = "assistant"
            else:
                answer, metadata = self.rag_processor.process_query(query)
        else:
            answer, metadata = self.assistant_processor.process_query(query, user_id)
        
        # Общие метаданные
        metadata.update({
            "mode": mode,
            "user_id": user_id,
            "total_time_ms": int((time.time() - start_time) * 1000)
        })
        
        return answer, metadata
    
    def get_available_modes(self) -> List[Dict[str, str]]:
        """Список доступных режимов"""
        modes = [
            {
                "id": "rag",
                "name": "RAG Ассистент",
                "description": "Отвечает на основе базы знаний с документами",
                "available": self.rag_processor is not None
            },
            {
                "id": "assistant",
                "name": "AI Помощник", 
                "description": "Общий AI помощник с памятью разговора",
                "available": True
            }
        ]
        return modes
