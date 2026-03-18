# -*- coding: utf-8 -*-
"""
Векторное хранилище документов на базе ChromaDB
"""
import sys
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

import os
import hashlib
from typing import List, Dict, Any, Optional
from loguru import logger
import chromadb
from chromadb.config import Settings

from config.settings import CHROMA_DIR, EMBEDDING_MODEL, PROXY_API_KEY


class EmbeddingStore:
    """Хранилище документов с векторными эмбеддингами"""
    
    def __init__(
        self, 
        collection_name: str = "documents",
        persist_directory: str = None,
        embedding_model: str = None
    ):
        self.collection_name = collection_name
        self.persist_directory = persist_directory or str(CHROMA_DIR)
        self.embedding_model = embedding_model or EMBEDDING_MODEL
        
        # Инициализация клиента ChromaDB (новый API)
        self.client = chromadb.PersistentClient(path=self.persist_directory)
        
        # Получение или создание коллекции
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        logger.info(f"EmbeddingStore инициализирован: {collection_name}")
    
    def add_document(
        self, 
        text: str, 
        metadata: Dict[str, Any] = None,
        doc_id: str = None
    ) -> str:
        """
        Добавление документа в хранилище
        
        Args:
            text: Текст документа
            metadata: Метаданные документа
            doc_id: ID документа (если не указан - генерируется автоматически)
            
        Returns:
            ID документа
        """
        if not doc_id:
            doc_id = hashlib.md5(text.encode()).hexdigest()
        
        metadata = metadata or {}
        metadata.update({
            "source": metadata.get("source", "unknown"),
            "added_at": metadata.get("added_at", str(os.path.getctime(__file__) if os.path.exists(__file__) else 0))
        })
        
        try:
            self.collection.add(
                ids=[doc_id],
                documents=[text],
                metadatas=[metadata]
            )
            logger.info(f"Документ добавлен: {doc_id}")
            return doc_id
            
        except Exception as e:
            logger.error(f"Ошибка добавления документа: {e}")
            raise
    
    def add_documents(self, documents: List[Dict[str, Any]]) -> List[str]:
        """Пакетное добавление документов"""
        ids = []
        texts = []
        metadatas = []
        
        for doc in documents:
            text = doc.get("text", doc.get("content", ""))
            if not text:
                continue
                
            doc_id = doc.get("id") or hashlib.md5(text.encode()).hexdigest()
            metadata = doc.get("metadata", {})
            
            ids.append(doc_id)
            texts.append(text)
            metadatas.append(metadata)
        
        if ids:
            self.collection.add(
                ids=ids,
                documents=texts,
                metadatas=metadatas
            )
            logger.info(f"Добавлено {len(ids)} документов")
        
        return ids
    
    def search(
        self, 
        query: str, 
        top_k: int = 3,
        filter_dict: Dict = None
    ) -> List[Dict[str, Any]]:
        """
        Поиск релевантных документов
        
        Args:
            query: Поисковый запрос
            top_k: Количество результатов
            filter_dict: Фильтр по метаданным
            
        Returns:
            Список документов со score
        """
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where=filter_dict
            )
            
            documents = []
            if results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    documents.append({
                        "id": doc_id,
                        "text": results["documents"][0][i] if results["documents"] else "",
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "score": results["distances"][0][i] if results["distances"] else 0.0
                    })
            
            return documents
            
        except Exception as e:
            logger.error(f"Ошибка поиска: {e}")
            return []
    
    def delete_document(self, doc_id: str) -> bool:
        """Удаление документа"""
        try:
            self.collection.delete(ids=[doc_id])
            logger.info(f"Документ удален: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления документа: {e}")
            return False
    
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Получение документа по ID"""
        try:
            result = self.collection.get(ids=[doc_id])
            if result["ids"]:
                return {
                    "id": result["ids"][0],
                    "text": result["documents"][0] if result["documents"] else "",
                    "metadata": result["metadatas"][0] if result["metadatas"] else {}
                }
            return None
        except Exception as e:
            logger.error(f"Ошибка получения документа: {e}")
            return None
    
    def get_all_documents(
        self, 
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Получение всех документов с пагинацией"""
        try:
            result = self.collection.get(
                limit=limit,
                offset=offset
            )
            
            documents = []
            for i, doc_id in enumerate(result["ids"]):
                documents.append({
                    "id": doc_id,
                    "text": result["documents"][i] if result["documents"] else "",
                    "metadata": result["metadatas"][i] if result["metadatas"] else {}
                })
            
            return documents
            
        except Exception as e:
            logger.error(f"Ошибка получения документов: {e}")
            return []
    
    def count(self) -> int:
        """Количество документов в коллекции"""
        return self.collection.count()


# Пример документов для начальной загрузки
SAMPLE_DOCUMENTS = [
    {
        "text": """Python — это высокоуровневый язык программирования общего назначения. 
Он был создан Гвидо ван Россумом и впервые выпущен в 1991 году. 
Python известен своей читаемостью кода и простым синтаксисом.
Он используется для веб-разработки, анализа данных, машинного обучения, автоматизации и многого другого.""",
        "metadata": {"source": "about_python", "category": "programming"}
    },
    {
        "text": """RAG (Retrieval-Augmented Generation) — это метод, который объединяет 
поиск информации с генерацией текста. Система сначала находит релевантные документы 
из базы знаний, а затем использует их как контекст для генерации ответа языковой моделью.
Это позволяет получать более точные и актуальные ответы, основанные на конкретных документах.""",
        "metadata": {"source": "about_rag", "category": "ai"}
    },
    {
        "text": """Векторные базы данных хранят данные в виде векторов (эмбеддингов) — 
числовых представлений текста, изображений или других данных. Это позволяет 
выполнять семантический поиск, находя похожие данные по смыслу, а не только по ключевым словам.
Примеры: ChromaDB, Pinecone, Weaviate, Qdrant.

Что такое RAG? RAG (Retrieval-Augmented Generation) — это метод, который объединяет 
поиск информации с генерацией текста. Система сначала находит релевантные документы 
из базы знаний, а затем использует их как контекст для генерации ответа языковой моделью.
Это позволяет получать более точные и актуальные ответы, основанные на конкретных документах.""",
        "metadata": {"source": "about_vector_db", "category": "databases"}
    }
]


def get_sample_documents() -> List[Dict[str, Any]]:
    """Получение примеров документов"""
    return SAMPLE_DOCUMENTS.copy()
