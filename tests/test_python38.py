# -*- coding: utf-8 -*-
"""
Тесты для Python 3.8.10 совместимости
"""
import sys
import unittest
from pathlib import Path
import tempfile
import json

# Проверка версии Python
print(f"Python version: {sys.version}")
assert sys.version_info >= (3, 8), "Требуется Python 3.8+"
assert sys.version_info < (3, 9), "Должен быть Python 3.8.x для тестирования"

# Добавляем корень проекта
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPython38Compatibility(unittest.TestCase):
    """Тесты совместимости с Python 3.8"""
    
    def test_imports(self):
        """Проверка импортов всех модулей"""
        try:
            from backend.core.ai_core import UnifiedAssistant, AICore, RAGProcessor
            from backend.core.cache import ResponseCache
            from backend.core.database import DatabaseManager
            from backend.core.embeddings import EmbeddingStore
            from backend.core.monitoring import AlertManager, HealthChecker
            from backend.bot.telegram_bot import TelegramBot
            from backend.api.main_api import app
            from config.settings import APP_VERSION
            print("✅ Все импорты успешны")
        except ImportError as e:
            self.fail(f"Ошибка импорта: {e}")
    
    def test_type_hints(self):
        """Проверка type hints (Python 3.8 не поддерживает | синтаксис)"""
        # Проверяем что не используется новый синтаксис типов Python 3.10+
        import ast
        
        backend_dir = Path(__file__).parent.parent / "backend"
        
        for py_file in backend_dir.rglob("*.py"):
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Проверка на использование Python 3.10+ синтаксиса
            # X | Y вместо Union[X, Y] или Optional[X]
            if " | " in content and "from __future__" not in content:
                # Это может быть допустимо если используется __future__
                # Проверим конкретные паттерны
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    if " | " in line and not line.strip().startswith('#'):
                        # Пропускаем строки внутри строк
                        if '" | "' not in line and "' | '" not in line:
                            print(f"⚠️  Возможно Python 3.10+ синтаксис в {py_file}:{i}: {line.strip()}")
    
    def test_utf8_encoding(self):
        """Проверка UTF-8 кодировки всех файлов"""
        project_dir = Path(__file__).parent.parent
        
        python_files = list(project_dir.rglob("*.py"))
        
        for py_file in python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    f.read()
            except UnicodeDecodeError:
                self.fail(f"Файл не в UTF-8: {py_file}")
        
        print(f"✅ Проверено {len(python_files)} Python файлов в UTF-8")
    
    def test_config_loading(self):
        """Проверка загрузки конфигурации"""
        from config.settings import (
            APP_VERSION, APP_NAME, HOST, PORT,
            RAG_TOP_K, CACHE_ENABLED
        )
        
        self.assertIsInstance(APP_VERSION, str)
        self.assertIsInstance(APP_NAME, str)
        self.assertIsInstance(HOST, str)
        self.assertIsInstance(PORT, int)
        print(f"✅ Конфигурация загружена: {APP_NAME} v{APP_VERSION}")


class TestDatabaseOperations(unittest.TestCase):
    """Тесты работы с базой данных"""
    
    def setUp(self):
        """Создание временной БД для тестов"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
    
    def test_database_initialization(self):
        """Проверка инициализации БД"""
        from backend.core.database import DatabaseManager
        
        db = DatabaseManager(str(self.db_path))
        
        # Проверяем что таблицы созданы
        stats = db.get_stats(days=1)
        self.assertIsInstance(stats, dict)
        
        print("✅ База данных инициализирована")
    
    def test_log_interaction(self):
        """Проверка логирования"""
        from backend.core.database import DatabaseManager
        
        db = DatabaseManager(str(self.db_path))
        
        db.log_interaction(
            query="Тестовый запрос",
            response="Тестовый ответ",
            source="test",
            user_id="test_user",
            mode="rag",
            from_cache=False,
            response_time_ms=100
        )
        
        # Проверяем что запись добавлена
        logs = db.get_interactions(source="test", limit=1)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["query"], "Тестовый запрос")
        
        print("✅ Логирование работает")
    
    def tearDown(self):
        """Очистка"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)


class TestCacheOperations(unittest.TestCase):
    """Тесты кэша"""
    
    def setUp(self):
        """Создание временного кэша"""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_file = Path(self.temp_dir) / "cache.json"
    
    def test_cache_operations(self):
        """Проверка операций кэша"""
        from backend.core.cache import ResponseCache
        
        cache = ResponseCache(str(self.cache_file))
        
        # Добавление
        cache.set("test_query", "test_response")
        
        # Получение
        result = cache.get("test_query")
        self.assertEqual(result, "test_response")
        
        # Статистика
        self.assertEqual(cache.size(), 1)
        
        print("✅ Кэш работает")
    
    def tearDown(self):
        """Очистка"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)


class TestUTF8Documents(unittest.TestCase):
    """Тесты загрузки документов с UTF-8"""
    
    def test_unicode_filenames(self):
        """Проверка работы с Unicode именами файлов"""
        from scripts.upload_docs import normalize_filename
        
        # Тесты нормализации
        test_cases = [
            ("document.txt", "document.txt"),
            ("Документ.txt", "Документ.txt"),
            ("file:with:chars.txt", "file_with_chars.txt"),
            ("café.txt", "café.txt"),  # Unicode
        ]
        
        for input_name, expected in test_cases:
            result = normalize_filename(input_name)
            self.assertEqual(result, expected)
        
        print("✅ Нормализация имен файлов работает")
    
    def test_encoding_detection(self):
        """Проверка определения кодировки"""
        from scripts.upload_docs import detect_encoding
        
        # Создаем тестовые файлы
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("Тест UTF-8 текста с кириллицей")
            utf8_file = f.name
        
        try:
            encoding = detect_encoding(Path(utf8_file))
            self.assertIn(encoding.lower(), ['utf-8', 'utf-8-sig', 'ascii'])
            print("✅ Определение кодировки работает")
        finally:
            import os
            os.unlink(utf8_file)


class TestBackupSystem(unittest.TestCase):
    """Тесты системы бэкапов"""
    
    def setUp(self):
        """Создание временной структуры"""
        self.temp_dir = tempfile.mkdtemp()
        self.backup_dir = Path(self.temp_dir) / "backups"
        self.data_dir = Path(self.temp_dir) / "data"
        self.chroma_dir = Path(self.temp_dir) / "chroma_db"
        
        # Создаем тестовые данные
        self.data_dir.mkdir()
        self.chroma_dir.mkdir()
        
        (self.data_dir / "test.db").write_text("test data")
        (self.chroma_dir / "test.json").write_text('{"test": true}')
    
    def test_backup_creation(self):
        """Проверка создания бэкапа"""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from scripts.backup import create_backup, list_backups
        
        # Переопределяем пути
        import scripts.backup as backup_module
        original_backup_dir = backup_module.BACKUP_DIR
        original_data_dir = backup_module.DATA_DIR
        original_chroma_dir = backup_module.CHROMA_DIR
        
        try:
            backup_module.BACKUP_DIR = self.backup_dir
            backup_module.DATA_DIR = self.data_dir
            backup_module.CHROMA_DIR = self.chroma_dir
            
            backup_path = create_backup()
            
            self.assertIsNotNone(backup_path)
            self.assertTrue(backup_path.exists())
            
            # Проверяем что архив создан
            backups = list_backups()
            self.assertEqual(len(backups), 1)
            
            print("✅ Создание бэкапа работает")
            
        finally:
            backup_module.BACKUP_DIR = original_backup_dir
            backup_module.DATA_DIR = original_data_dir
            backup_module.CHROMA_DIR = original_chroma_dir
    
    def tearDown(self):
        """Очистка"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)


def run_tests():
    """Запуск всех тестов"""
    print("\n" + "="*60)
    print("ЗАПУСК ТЕСТОВ PYTHON 3.8.10 СОВМЕСТИМОСТИ")
    print("="*60 + "\n")
    
    # Создаем test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Добавляем тесты
    suite.addTests(loader.loadTestsFromTestCase(TestPython38Compatibility))
    suite.addTests(loader.loadTestsFromTestCase(TestDatabaseOperations))
    suite.addTests(loader.loadTestsFromTestCase(TestCacheOperations))
    suite.addTests(loader.loadTestsFromTestCase(TestUTF8Documents))
    suite.addTests(loader.loadTestsFromTestCase(TestBackupSystem))
    
    # Запускаем
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Итог
    print("\n" + "="*60)
    if result.wasSuccessful():
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("Проект совместим с Python 3.8.10")
    else:
        print("❌ ЕСТЬ ОШИБКИ!")
        print(f"Ошибок: {len(result.errors)}")
        print(f"Провалов: {len(result.failures)}")
    print("="*60 + "\n")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
