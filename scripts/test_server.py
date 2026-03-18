#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый сервер для локального просмотра без AI зависимостей
Запускает веб-интерфейс с мок-ответами
"""
import http.server
import socketserver
import json
import random
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PORT = 8000

# Простые мок-ответы
MOCK_RESPONSES = {
    "rag": [
        "На основе базы знаний: RAG (Retrieval-Augmented Generation) объединяет поиск с генерацией текста.",
        "Согласно документации: Система использует векторный поиск ChromaDB для точных ответов.",
        "Из FAQ: Да, бот работает и в Telegram, и на сайте с общей базой знаний.",
    ],
    "assistant": [
        "Привет! Я AI-помощник. Чем могу помочь?",
        "Интересный вопрос! Давайте разберемся вместе.",
        "Я могу помочь с информацией о проекте и услугах.",
        "Это демо-режим. Полная версия будет на сервере с реальным AI.",
    ]
}


class TestHandler(http.server.SimpleHTTPRequestHandler):
    """Обработчик тестового сервера"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).parent.parent / "frontend"), **kwargs)
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()
    
    def do_POST(self):
        """Обработка POST запросов (API)"""
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
        except:
            data = {}
        
        path = urlparse(self.path).path
        
        if path == '/api/query':
            # Мок ответа от AI
            mode = data.get('mode', 'rag')
            query = data.get('query', '')
            
            responses = MOCK_RESPONSES.get(mode, MOCK_RESPONSES['rag'])
            answer = random.choice(responses)
            
            # Добавляем контекст запроса
            if query:
                answer = f"Вы спросили: '{query}'\n\n{answer}"
            
            response = {
                "answer": answer,
                "mode": mode,
                "metadata": {
                    "from_cache": False,
                    "response_time_ms": 150,
                    "demo": True
                }
            }
            
            self.send_json_response(response)
            
        elif path == '/api/contact':
            # Мок формы обратной связи
            self.send_json_response({
                "status": "ok",
                "form_id": 123,
                "message": "Сообщение отправлено! (ДЕМО режим)"
            })
            
        elif path == '/api/mode':
            # Мок переключения режима
            self.send_json_response({
                "user_id": data.get('user_id', 'test'),
                "mode": data.get('mode', 'rag'),
                "status": "ok"
            })
            
        else:
            self.send_error(404)
    
    def do_GET(self):
        """Обработка GET запросов"""
        path = urlparse(self.path).path
        
        if path == '/health':
            self.send_json_response({
                "status": "healthy",
                "demo": True,
                "components": {
                    "web_server": {"status": "ok"},
                    "database": {"status": "demo"},
                    "ai_service": {"status": "demo"},
                    "telegram_bot": {"status": "demo"}
                }
            })
            
        elif path == '/api/modes':
            self.send_json_response({
                "modes": [
                    {"id": "rag", "name": "RAG Ассистент", "description": "Ответы из базы знаний", "available": True},
                    {"id": "assistant", "name": "AI Помощник", "description": "Общий AI", "available": True}
                ],
                "default": "rag"
            })
            
        elif path == '/api/stats':
            self.send_json_response({
                "total_requests": 42,
                "cached_requests": 5,
                "unique_users": 3,
                "avg_response_time_ms": 120,
                "by_source": {"web": 25, "telegram": 17},
                "period_days": 7
            })
            
        elif path == '/api/admin/logs':
            self.send_json_response({
                "logs": [
                    {
                        "timestamp": "2026-03-18T10:00:00",
                        "source": "web",
                        "query": "Тестовый запрос",
                        "mode": "rag",
                        "response_time_ms": 100
                    }
                ],
                "total": 1
            })
            
        elif path == '/api/admin/documents':
            self.send_json_response({
                "documents": [
                    {"id": "doc_1", "text": "Пример документа...", "metadata": {"source": "demo"}}
                ],
                "total": 1
            })
            
        elif path.startswith('/api/'):
            # API endpoints возвращаем JSON
            self.send_json_response({"error": "Demo endpoint"}, status=404)
            
        else:
            # Статические файлы
            super().do_GET()
    
    def send_json_response(self, data, status=200):
        """Отправка JSON ответа"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))


def run_test_server():
    """Запуск тестового сервера"""
    import os
    os.chdir(str(Path(__file__).parent.parent))
    
    with socketserver.TCPServer(("", PORT), TestHandler) as httpd:
        print(f"🚀 Тестовый сервер запущен!")
        print(f"🌐 http://localhost:{PORT}")
        print(f"")
        print(f"Доступные страницы:")
        print(f"  - Сайт: http://localhost:{PORT}/")
        print(f"  - Админка: http://localhost:{PORT}/admin.html")
        print(f"  - Health: http://localhost:{PORT}/health")
        print(f"")
        print(f"⚠️  Это ДЕМО режим без реального AI")
        print(f"   Ответы генерируются случайно из шаблонов")
        print(f"")
        print(f"Нажмите Ctrl+C для остановки")
        print(f"{'='*50}")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n👋 Сервер остановлен")


if __name__ == "__main__":
    run_test_server()
