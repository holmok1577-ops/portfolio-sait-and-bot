#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Система бэкапов и версионирования данных
"""
import os
import sys
import shutil
import tarfile
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from loguru import logger

# Пути
BACKUP_DIR = Path("/app/backups") if os.path.exists("/app/backups") else Path("backups")
DATA_DIR = Path("/app/data") if os.path.exists("/app/data") else Path("data")
CHROMA_DIR = Path("/app/chroma_db") if os.path.exists("/app/chroma_db") else Path("chroma_db")
DOCS_DIR = Path("/app/docs") if os.path.exists("/app/docs") else Path("docs")

# Настройки
MAX_BACKUPS = int(os.getenv("MAX_BACKUPS", "10"))  # Хранить последние 10 бэкапов
KEEP_DAYS = int(os.getenv("KEEP_BACKUP_DAYS", "30"))  # Удалять старше 30 дней


def ensure_dirs():
    """Создание необходимых директорий"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Директория бэкапов: {BACKUP_DIR}")


def create_backup() -> Optional[Path]:
    """Создание бэкапа всех данных"""
    ensure_dirs()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_{timestamp}.tar.gz"
    backup_path = BACKUP_DIR / backup_name
    
    logger.info(f"Создание бэкапа: {backup_name}")
    
    try:
        # Создаем архив
        with tarfile.open(backup_path, "w:gz") as tar:
            # База данных
            if DATA_DIR.exists():
                logger.info("Архивирование базы данных...")
                tar.add(DATA_DIR, arcname="data")
            
            # Векторная база
            if CHROMA_DIR.exists():
                logger.info("Архивирование векторной базы...")
                tar.add(CHROMA_DIR, arcname="chroma_db")
            
            # Документы
            if DOCS_DIR.exists():
                logger.info("Архивирование документов...")
                tar.add(DOCS_DIR, arcname="docs")
            
            # Метаданные бэкапа
            metadata = {
                "created_at": datetime.now().isoformat(),
                "version": "1.0.0",
                "files": {
                    "data": DATA_DIR.exists(),
                    "chroma_db": CHROMA_DIR.exists(),
                    "docs": DOCS_DIR.exists()
                }
            }
            
            # Записываем метаданные в архив
            import io
            metadata_bytes = json.dumps(metadata, ensure_ascii=False).encode('utf-8')
            metadata_info = tarfile.TarInfo(name="backup_metadata.json")
            metadata_info.size = len(metadata_bytes)
            tar.addfile(metadata_info, io.BytesIO(metadata_bytes))
        
        logger.info(f"✅ Бэкап создан: {backup_path}")
        logger.info(f"   Размер: {backup_path.stat().st_size / 1024 / 1024:.2f} MB")
        
        return backup_path
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания бэкапа: {e}")
        return None


def list_backups() -> List[Path]:
    """Список всех бэкапов"""
    if not BACKUP_DIR.exists():
        return []
    
    backups = sorted(
        [f for f in BACKUP_DIR.iterdir() if f.suffix == '.gz' or f.name.endswith('.tar.gz')],
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    return backups


def cleanup_old_backups():
    """Очистка старых бэкапов"""
    backups = list_backups()
    
    if len(backups) > MAX_BACKUPS:
        # Удаляем старые бэкапы, оставляем MAX_BACKUPS
        to_delete = backups[MAX_BACKUPS:]
        for backup in to_delete:
            try:
                backup.unlink()
                logger.info(f"🗑 Удален старый бэкап: {backup.name}")
            except Exception as e:
                logger.error(f"Ошибка удаления {backup.name}: {e}")
    
    # Удаляем бэкапы старше KEEP_DAYS
    cutoff = datetime.now() - timedelta(days=KEEP_DAYS)
    
    for backup in backups:
        try:
            mtime = datetime.fromtimestamp(backup.stat().st_mtime)
            if mtime < cutoff:
                backup.unlink()
                logger.info(f"🗑 Удален устаревший бэкап: {backup.name}")
        except Exception as e:
            logger.error(f"Ошибка проверки {backup.name}: {e}")


def restore_backup(backup_path: Path) -> bool:
    """Восстановление из бэкапа"""
    if not backup_path.exists():
        logger.error(f"Бэкап не найден: {backup_path}")
        return False
    
    logger.warning(f"⚠️ Восстановление из бэкапа: {backup_path.name}")
    logger.warning("Текущие данные будут перезаписаны!")
    
    try:
        # Распаковка
        with tarfile.open(backup_path, "r:gz") as tar:
            # Проверяем метаданные
            try:
                metadata_file = tar.extractfile("backup_metadata.json")
                if metadata_file:
                    metadata = json.loads(metadata_file.read().decode('utf-8'))
                    logger.info(f"Версия бэкапа: {metadata.get('version', 'unknown')}")
                    logger.info(f"Создан: {metadata.get('created_at', 'unknown')}")
            except:
                pass
            
            # Извлекаем
            tar.extractall(path=".")
        
        logger.info(f"✅ Восстановление завершено!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка восстановления: {e}")
        return False


def get_backup_info(backup_path: Path) -> dict:
    """Получение информации о бэкапе"""
    try:
        stat = backup_path.stat()
        return {
            "name": backup_path.name,
            "size_mb": round(stat.st_size / 1024 / 1024, 2),
            "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "age_days": (datetime.now() - datetime.fromtimestamp(stat.st_mtime)).days
        }
    except:
        return {}


def main():
    """Основная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Backup system")
    parser.add_argument("action", choices=["create", "list", "restore", "cleanup"], 
                       help="Действие")
    parser.add_argument("--file", help="Имя файла бэкапа для восстановления")
    parser.add_argument("--yes", action="store_true", help="Подтвердить восстановление")
    
    args = parser.parse_args()
    
    # Настройка логирования
    logger.remove()
    logger.add(sys.stdout, format="{time:HH:mm:ss} | {level} | {message}")
    
    if args.action == "create":
        backup = create_backup()
        if backup:
            cleanup_old_backups()
            sys.exit(0)
        else:
            sys.exit(1)
    
    elif args.action == "list":
        backups = list_backups()
        if not backups:
            print("Бэкапов не найдено")
            return
        
        print(f"\n{'='*60}")
        print(f"{'Имя':<30} {'Размер':<10} {'Создан':<20}")
        print(f"{'='*60}")
        
        for backup in backups:
            info = get_backup_info(backup)
            if info:
                created = info['created'][:16].replace('T', ' ')
                print(f"{info['name']:<30} {info['size_mb']:<10.2f} {created:<20}")
        
        print(f"{'='*60}")
        print(f"Всего бэкапов: {len(backups)}")
    
    elif args.action == "restore":
        if not args.file:
            print("Укажите --file для восстановления")
            backups = list_backups()
            if backups:
                print("\nДоступные бэкапы:")
                for i, b in enumerate(backups[:5], 1):
                    print(f"  {i}. {b.name}")
            sys.exit(1)
        
        backup_path = BACKUP_DIR / args.file
        
        if not args.yes:
            confirm = input(f"Восстановить из {args.file}? Это перезапишет текущие данные! [y/N]: ")
            if confirm.lower() != 'y':
                print("Отменено")
                sys.exit(0)
        
        success = restore_backup(backup_path)
        sys.exit(0 if success else 1)
    
    elif args.action == "cleanup":
        cleanup_old_backups()
        print("Очистка завершена")


if __name__ == "__main__":
    main()
