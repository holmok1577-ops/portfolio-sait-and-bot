#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Утилита загрузки документов в базу знаний с гарантированной UTF-8 кодировкой
Поддерживает: .txt, .md, .json, документы с кириллицей в названиях
"""
import os
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger
import unicodedata

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.embeddings import EmbeddingStore
from backend.core.database import DatabaseManager


def normalize_filename(filename: str) -> str:
    """
    Нормализация имени файла для UTF-8
    Заменяет проблемные символы и нормализует Unicode
    """
    # NFC нормализация Unicode
    normalized = unicodedata.normalize('NFC', filename)
    
    # Замена проблемных символов
    replacements = {
        '\\': '_',
        '/': '_',
        ':': '_',
        '*': '_',
        '?': '_',
        '"': "'",
        '<': '_',
        '>': '_',
        '|': '_',
    }
    
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    
    return normalized


def detect_encoding(file_path: Path) -> str:
    """Определение кодировки файла"""
    import chardet
    
    with open(file_path, 'rb') as f:
        raw_data = f.read()
    
    result = chardet.detect(raw_data)
    encoding = result.get('encoding', 'utf-8')
    confidence = result.get('confidence', 0)
    
    logger.debug(f"Определена кодировка: {encoding} (confidence: {confidence:.2f})")
    
    # Если кодировка не utf-8 и не ascii, пробуем utf-8-sig
    if encoding and encoding.lower() not in ['utf-8', 'ascii']:
        try:
            raw_data.decode('utf-8-sig')
            return 'utf-8-sig'
        except:
            pass
    
    return encoding or 'utf-8'


def read_file_utf8(file_path: Path) -> Optional[str]:
    """
    Чтение файла с гарантированным декодированием в UTF-8
    Пробует несколько кодировок
    """
    encodings_to_try = [
        'utf-8',
        'utf-8-sig',
        'utf-16',
        'utf-16-le',
        'utf-16-be',
        'cp1251',  # Windows Cyrillic
        'cp1252',  # Windows Western
        'koi8-r',  # Russian
        'iso-8859-5',  # Cyrillic
        'iso-8859-1',  # Western
        'latin1',
        'gb2312',  # Chinese
        'shift_jis',  # Japanese
        'euc-kr',  # Korean
    ]
    
    # Сначала пробуем chardet
    detected = detect_encoding(file_path)
    if detected:
        encodings_to_try.insert(0, detected)
    
    for encoding in encodings_to_try:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
            
            # Проверка что текст валидный UTF-8
            content.encode('utf-8')
            
            logger.info(f"✅ Успешно прочитан с кодировкой: {encoding}")
            return content
            
        except UnicodeDecodeError:
            continue
        except Exception as e:
            logger.debug(f"Ошибка с кодировкой {encoding}: {e}")
            continue
    
    # Последняя попытка - читаем как бинарный и заменяем ошибки
    try:
        with open(file_path, 'rb') as f:
            raw = f.read()
        # Декодируем с заменой ошибочных символов
        content = raw.decode('utf-8', errors='replace')
        logger.warning(f"⚠️ Использована замена ошибочных символов для: {file_path}")
        return content
    except Exception as e:
        logger.error(f"❌ Не удалось прочитать файл {file_path}: {e}")
        return None


def process_document(
    file_path: Path,
    embedding_store: EmbeddingStore,
    source: str = None,
    category: str = "general",
    split_chunks: bool = True,
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> Optional[str]:
    """
    Обработка и загрузка документа в базу знаний
    
    Args:
        file_path: Путь к файлу
        embedding_store: Хранилище эмбеддингов
        source: Источник документа
        category: Категория документа
        split_chunks: Разбивать ли на чанки
        chunk_size: Размер чанка
        chunk_overlap: Перекрытие чанков
    """
    logger.info(f"📄 Обработка: {file_path.name}")
    
    # Чтение файла
    content = read_file_utf8(file_path)
    if not content:
        return None
    
    # Нормализация названия
    safe_name = normalize_filename(file_path.name)
    
    # Определение источника
    doc_source = source or safe_name
    
    # Метаданные
    metadata = {
        "source": doc_source,
        "filename": safe_name,
        "original_filename": file_path.name,
        "category": category,
        "file_size": file_path.stat().st_size,
        "encoding": "utf-8",
    }
    
    # Разбиение на чанки если нужно
    if split_chunks and len(content) > chunk_size:
        logger.info(f"📦 Разбиение на чанки (size={chunk_size}, overlap={chunk_overlap})")
        
        # Простое разбиение по параграфам
        paragraphs = content.split('\n\n')
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            if len(current_chunk) + len(para) < chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        logger.info(f"   Создано {len(chunks)} чанков")
        
        # Добавление каждого чанка
        doc_ids = []
        for i, chunk in enumerate(chunks):
            chunk_metadata = {
                **metadata,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "chunk_id": f"{safe_name}_chunk_{i}"
            }
            
            doc_id = embedding_store.add_document(
                text=chunk,
                metadata=chunk_metadata,
                doc_id=chunk_metadata["chunk_id"]
            )
            doc_ids.append(doc_id)
        
        logger.info(f"✅ Загружено {len(doc_ids)} чанков")
        return doc_ids[0]  # Возвращаем ID первого чанка
        
    else:
        # Одним документом
        doc_id = embedding_store.add_document(
            text=content,
            metadata=metadata,
            doc_id=f"doc_{safe_name}"
        )
        
        logger.info(f"✅ Документ загружен: {doc_id}")
        return doc_id


def batch_upload(
    directory: Path,
    embedding_store: EmbeddingStore,
    pattern: str = "*.txt",
    source: str = None,
    category: str = "general"
) -> List[str]:
    """
    Пакетная загрузка документов из директории
    """
    logger.info(f"📁 Пакетная загрузка из: {directory}")
    logger.info(f"   Паттерн: {pattern}")
    
    uploaded = []
    failed = []
    
    files = list(directory.glob(pattern))
    logger.info(f"   Найдено файлов: {len(files)}")
    
    for file_path in files:
        if not file_path.is_file():
            continue
        
        try:
            doc_id = process_document(
                file_path=file_path,
                embedding_store=embedding_store,
                source=source or file_path.parent.name,
                category=category
            )
            
            if doc_id:
                uploaded.append(str(file_path))
            else:
                failed.append(str(file_path))
                
        except Exception as e:
            logger.error(f"❌ Ошибка обработки {file_path}: {e}")
            failed.append(str(file_path))
    
    logger.info(f"✅ Успешно: {len(uploaded)}, ❌ Ошибок: {len(failed)}")
    
    if failed:
        logger.warning(f"Не загружены:\n" + "\n".join(f"  - {f}" for f in failed))
    
    return uploaded


def validate_utf8_all_filenames(directory: Path) -> Dict[str, Any]:
    """
    Проверка что все имена файлов в директории корректны UTF-8
    """
    issues = []
    valid = []
    
    for item in directory.rglob("*"):
        try:
            # Проверка что имя файла - валидный UTF-8
            name_bytes = item.name.encode('utf-8')
            decoded = name_bytes.decode('utf-8')
            
            # Проверка на нормализацию
            normalized = unicodedata.normalize('NFC', decoded)
            if normalized != decoded:
                issues.append({
                    "path": str(item),
                    "issue": "Ненормализованное Unicode имя",
                    "suggestion": normalized
                })
            else:
                valid.append(str(item))
                
        except UnicodeEncodeError as e:
            issues.append({
                "path": str(item),
                "issue": f"Не UTF-8 кодировка: {e}",
                "suggestion": None
            })
    
    return {
        "total": len(valid) + len(issues),
        "valid": len(valid),
        "issues": len(issues),
        "details": issues
    }


def main():
    """CLI интерфейс"""
    parser = argparse.ArgumentParser(
        description="Загрузка документов в RAG базу знаний (UTF-8)"
    )
    parser.add_argument("path", help="Путь к файлу или директории")
    parser.add_argument("--source", "-s", help="Источник документа")
    parser.add_argument("--category", "-c", default="general", 
                       help="Категория (general, documentation, faq, blog)")
    parser.add_argument("--batch", "-b", action="store_true",
                       help="Пакетная загрузка директории")
    parser.add_argument("--pattern", "-p", default="*.txt",
                       help="Паттерн для пакетной загрузки")
    parser.add_argument("--no-chunks", action="store_true",
                       help="Не разбивать на чанки")
    parser.add_argument("--chunk-size", type=int, default=1000,
                       help="Размер чанка")
    parser.add_argument("--validate", "-v", action="store_true",
                       help="Проверить UTF-8 имена файлов")
    
    args = parser.parse_args()
    
    # Настройка логирования
    logger.remove()
    logger.add(sys.stdout, format="{time:HH:mm:ss} | {level} | {message}")
    
    target_path = Path(args.path)
    
    if not target_path.exists():
        logger.error(f"❌ Путь не найден: {target_path}")
        sys.exit(1)
    
    # Валидация имен файлов
    if args.validate:
        logger.info("🔍 Проверка UTF-8 имен файлов...")
        result = validate_utf8_all_filenames(target_path)
        
        print(f"\n{'='*60}")
        print(f"Всего файлов: {result['total']}")
        print(f"Валидных: {result['valid']}")
        print(f"С проблемами: {result['issues']}")
        
        if result['details']:
            print(f"\n{'Проблемы:'}")
            for issue in result['details'][:10]:  # Показываем первые 10
                print(f"  ⚠️  {issue['path']}")
                print(f"      {issue['issue']}")
                if issue['suggestion']:
                    print(f"      Предлагается: {issue['suggestion']}")
        
        print(f"{'='*60}")
        sys.exit(0)
    
    # Инициализация
    logger.info("🚀 Инициализация...")
    embedding_store = EmbeddingStore()
    
    if args.batch or target_path.is_dir():
        # Пакетная загрузка
        uploaded = batch_upload(
            directory=target_path,
            embedding_store=embedding_store,
            pattern=args.pattern,
            source=args.source,
            category=args.category
        )
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ Загрузка завершена: {len(uploaded)} файлов")
        logger.info(f"{'='*60}")
        
    else:
        # Одиночная загрузка
        doc_id = process_document(
            file_path=target_path,
            embedding_store=embedding_store,
            source=args.source,
            category=args.category,
            split_chunks=not args.no_chunks,
            chunk_size=args.chunk_size
        )
        
        if doc_id:
            logger.info(f"\n{'='*60}")
            logger.info(f"✅ Документ загружен: {doc_id}")
            logger.info(f"{'='*60}")
        else:
            logger.error("❌ Ошибка загрузки документа")
            sys.exit(1)
    
    # Сохранение векторной базы
    embedding_store.persist()
    logger.info("💾 Векторная база сохранена")


if __name__ == "__main__":
    main()
