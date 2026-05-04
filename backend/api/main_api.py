# -*- coding: utf-8 -*-
"""
FastAPI приложение — веб-сервер и API для AI ассистента
"""
import os
import time
import io
import re
import asyncio
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request, File, UploadFile, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel
from loguru import logger
from PIL import Image

from config.settings import DEBUG, APP_VERSION, APP_NAME
from backend.core.ai_core import UnifiedAssistant
from backend.core.embeddings import EmbeddingStore, get_sample_documents
from backend.core.cache import ResponseCache
from backend.core.database import DatabaseManager
from backend.core.monitoring import AlertManager, HealthChecker


# Pydantic модели
class QueryRequest(BaseModel):
    query: str
    mode: Optional[str] = None  # 'rag' или 'assistant'
    user_id: Optional[str] = "web"


class QueryResponse(BaseModel):
    answer: str
    mode: str
    metadata: Dict[str, Any]


class ModeSwitchRequest(BaseModel):
    user_id: str
    mode: str  # 'rag' или 'assistant'


class ContactFormRequest(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    service: Optional[str] = None  # услуга из селекта
    message: str


class LogFilterRequest(BaseModel):
    source: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: int = 100
    offset: int = 0


# Глобальные объекты (инициализируются при старте)
embedding_store: Optional[EmbeddingStore] = None
assistant: Optional[UnifiedAssistant] = None
cache: Optional[ResponseCache] = None
db: Optional[DatabaseManager] = None
alert_manager: Optional[AlertManager] = None
health_checker: Optional[HealthChecker] = None

# Состояние эскалации по пользователям веб-чата.
# Хранится в памяти процесса: для MVP этого достаточно, история заявок сохраняется в БД.
escalation_state: Dict[str, Dict[str, Any]] = {}

GREETING_MESSAGES = {
    "привет",
    "здравствуйте",
    "добрый день",
    "доброе утро",
    "добрый вечер",
    "hello",
    "hi",
}


def _get_escalation_state(user_id: str) -> Dict[str, Any]:
    return escalation_state.setdefault(user_id or "web", {
        "miss_count": 0,
        "awaiting_contact": False,
        "last_question": ""
    })


def _reset_escalation_state(user_id: str):
    escalation_state[user_id or "web"] = {
        "miss_count": 0,
        "awaiting_contact": False,
        "last_question": ""
    }


def _is_greeting(query: str) -> bool:
    normalized = " ".join(
        (query or "")
        .lower()
        .replace("!", " ")
        .replace(".", " ")
        .replace(",", " ")
        .split()
    )
    return normalized in GREETING_MESSAGES


def _build_greeting_answer(user_id: str) -> str:
    _reset_escalation_state(user_id)
    return (
        "Привет! Я AI-ассистент Станислава. Могу ответить на вопросы о проектах, "
        "услугах, RAG, Telegram-ботах, промпт-инжиниринге, стоимости и процессе работы."
    )


def _extract_contact_payload(text: str) -> Dict[str, str]:
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text or "")
    phone_match = re.search(r"(\+?\d[\d\s().-]{7,}\d)", text or "")

    email = email_match.group(0) if email_match else ""
    phone = phone_match.group(0).strip() if phone_match else ""
    name_text = text or ""
    if email:
        name_text = name_text.replace(email, " ")
    if phone:
        name_text = name_text.replace(phone, " ")
    name_text = re.sub(r"\b(телефон|почта|email|имя|зовут|мой|моя)\b", " ", name_text, flags=re.IGNORECASE)
    name = " ".join(name_text.split())[:80]

    return {
        "name": name or "Не указано",
        "email": email or "Не указано",
        "phone": phone or "Не указано",
        "raw": text or ""
    }


def _send_alert_background(message: str, alert_type: str = "info", force: bool = False) -> None:
    """Отправляет Telegram-уведомление без блокировки ответа пользователю."""
    if not alert_manager:
        return

    async def _send():
        try:
            await alert_manager.send_alert(message, alert_type, force=force)
        except Exception as exc:
            logger.error(f"Ошибка фоновой отправки алерта: {exc}")

    try:
        asyncio.create_task(_send())
    except RuntimeError as exc:
        logger.error(f"Не удалось создать задачу отправки алерта: {exc}")


def _log_system_event(level: str, component: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Пишет системное событие в БД, если менеджер БД уже инициализирован."""
    if not db:
        return
    try:
        db.log_system_event(level=level, component=component, message=message, details=details)
    except Exception as exc:
        logger.error(f"Ошибка записи системного лога: {exc}")


async def _handle_contact_escalation(user_id: str, contact_text: str, request: Request = None) -> str:
    state = _get_escalation_state(user_id)
    contact = _extract_contact_payload(contact_text)
    last_question = state.get("last_question", "")

    message = (
        f"Заявка из эскалации AI-ассистента\n\n"
        f"Последний вопрос пользователя:\n{last_question}\n\n"
        f"Контактные данные:\n{contact['raw']}\n\n"
        f"Телефон: {contact['phone']}\n"
        f"Email: {contact['email']}"
    )

    if db:
        db.save_contact_form(
            name=contact["name"],
            email=contact["email"],
            phone=contact["phone"],
            subject="AI escalation consultation",
            message=message,
            source_ip=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent", "") if request else None
        )

    if alert_manager:
        _send_alert_background(
            f"<b>Новая заявка после эскалации</b>\n\n"
            f"<b>Пользователь:</b> {user_id}\n"
            f"<b>Имя:</b> {contact['name']}\n"
            f"<b>Телефон:</b> {contact['phone']}\n"
            f"<b>Email:</b> {contact['email']}\n\n"
            f"<b>Вопрос:</b>\n{last_question[:800]}\n\n"
            f"<b>Исходное сообщение с контактами:</b>\n{contact['raw'][:800]}",
            "info",
            force=True
        )

    _reset_escalation_state(user_id)
    return (
        "Спасибо, я передал заявку Станиславу. Он сможет посмотреть ваш вопрос "
        "и связаться с вами по указанным контактам. Если хотите ускорить связь, "
        "напишите напрямую в Telegram: @stanislav_prompt."
    )


def _apply_rag_escalation(user_id: str, query: str, answer: str, metadata: Dict[str, Any]) -> str:
    if metadata.get("mode") != "rag":
        _reset_escalation_state(user_id)
        return answer

    documents_used = metadata.get("documents_used")
    if documents_used is None or documents_used > 0:
        _reset_escalation_state(user_id)
        return answer

    state = _get_escalation_state(user_id)
    state["miss_count"] += 1
    state["last_question"] = query
    metadata["escalation"] = f"missing_context_step_{state['miss_count']}"

    if state["miss_count"] == 1:
        return (
            "Я не нашел точной информации по этому вопросу в базе знаний. "
            "Попробуйте уточнить вопрос: например, указать, интересует ли вас RAG, "
            "Telegram-бот, промпт-инжиниринг, стоимость, проекты или процесс работы."
        )

    if state["miss_count"] == 2:
        return (
            "Я снова не нашел подходящий ответ в базе знаний. Возможно, вопрос не относится "
            "к моим компетенциям или в документах пока нет такой информации. "
            "Можете переформулировать вопрос ближе к AI-ассистентам, RAG, ботам, "
            "автоматизации или проектам Станислава."
        )

    state["awaiting_contact"] = True
    return (
        "Я не знаю точный ответ на этот вопрос по базе знаний. Могу записать вас "
        "на консультацию к Станиславу: напишите одним сообщением ваше имя, телефон "
        "и email. Я передам контакты и ваш последний вопрос в Telegram."
    )


async def log_critical_error(level: str, message: str, details: str = None, component: str = "backend"):
    """Логирование критической ошибки с отправкой в Telegram"""
    _log_system_event(level=level, component=component, message=message, details={"details": details} if details else None)
    try:
        if alert_manager and level in ["error", "critical"]:
            await alert_manager.send_error_alert(
                component=component,
                error=message,
                details=details
            )
    except Exception as e:
        logger.error(f"Ошибка отправки алерта: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global embedding_store, assistant, cache, db, alert_manager, health_checker
    
    # Startup
    logger.info("🚀 Инициализация приложения...")
    
    # Инициализация компонентов
    db = DatabaseManager()
    cache = ResponseCache()
    _log_system_event("info", "startup", "Инициализация приложения началась")
    
    # Векторное хранилище
    embedding_store = EmbeddingStore()
    
    # Загрузка документов из папки data/rag_documents/
    def load_documents_from_folder():
        """Загрузка документов из папки data/rag_documents/"""
        rag_folder = os.path.join(os.path.dirname(__file__), "..", "..", "data", "rag_documents")
        if not os.path.exists(rag_folder):
            logger.info(f"Папка {rag_folder} не найдена")
            return
        
        # Получаем список файлов в папке
        files = [f for f in os.listdir(rag_folder) if f.endswith(('.md', '.txt'))]
        if not files:
            logger.info(f"В папке {rag_folder} нет документов")
            return

        existing_docs = embedding_store.get_all_documents(limit=1000)
        existing_filenames = [
            doc.get('metadata', {}).get('filename')
            for doc in existing_docs
            if isinstance(doc, dict)
        ]
        folder_filenames = set(files)

        for doc in existing_docs:
            metadata = doc.get('metadata', {}) if isinstance(doc, dict) else {}
            filename = metadata.get('filename')
            source = metadata.get('source')
            category = metadata.get('category')
            is_folder_doc = (
                source == "rag_documents_folder"
                or category == "portfolio_knowledge_base"
            )
            if is_folder_doc and filename and filename not in folder_filenames:
                embedding_store.delete_document(doc["id"])
                logger.info(f"Удален устаревший документ из RAG: {filename}")
        
        # Загружаем каждый файл
        loaded_count = 0
        for filename in files:
            filepath = os.path.join(rag_folder, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if filename in existing_filenames:
                    logger.info(f"Документ {filename} уже загружен")
                    continue
                
                # Добавляем документ в базу
                meta = {
                    "filename": filename,
                    "content_type": "text/markdown" if filename.endswith('.md') else "text/plain",
                    "uploaded_at": str(time.time()),
                    "source": os.path.splitext(filename)[0],
                    "category": "portfolio_knowledge_base"
                }
                
                doc_id = embedding_store.add_document(content, meta)
                loaded_count += 1
                logger.info(f"Загружен документ: {filename} (ID: {doc_id})")
            except Exception as e:
                logger.error(f"Ошибка загрузки документа {filename}: {e}")
        
        if loaded_count > 0:
            logger.info(f"Загружено {loaded_count} документов из папки {rag_folder}")
    
    # Загружаем документы из папки
    load_documents_from_folder()
    
    # Если база пуста — добавляем примеры
    if embedding_store.count() == 0:
        logger.info("Добавление примеров документов...")
        sample_docs = get_sample_documents()
        embedding_store.add_documents(sample_docs)
    
    # Ждем завершения загрузки документов
    time.sleep(1)
    logger.info(f"Всего документов в базе: {embedding_store.count()}")
    
    # AI ассистент
    assistant = UnifiedAssistant(embedding_store)
    
    # Мониторинг
    alert_manager = AlertManager()
    health_checker = HealthChecker(db, alert_manager)
    
    # Уведомление о запуске
    await alert_manager.send_startup_notification({
        "web_server": "ok",
        "database": "ok",
        "vector_db": "ok",
        "ai_service": "ok"
    })
    _log_system_event("info", "startup", "Приложение готово к работе", {
        "documents_count": embedding_store.count(),
        "version": APP_VERSION
    })
    logger.info("✅ Приложение готово к работе")
    
    yield
    
    # Shutdown
    logger.info("🛑 Завершение работы...")
    if health_checker:
        health_checker.stop_monitoring()
    _log_system_event("info", "shutdown", "Приложение остановлено")
    logger.info("👋 Приложение остановлено")


# Создание приложения
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs" if DEBUG else None,
    redoc_url="/api/redoc" if DEBUG else None
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if DEBUG else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === API Endpoints ===

@app.get("/health")
async def health_check():
    """Проверка здоровья системы"""
    if health_checker:
        status = health_checker.get_status()
        return status
    return {"status": "unknown"}


@app.post("/api/query", response_model=QueryResponse)
async def process_query(request_data: QueryRequest, request: Request):
    """Обработка запроса к AI ассистенту"""
    start_time = time.time()
    
    try:
        user_id = request_data.user_id or "web"
        state = _get_escalation_state(user_id)

        if _is_greeting(request_data.query):
            answer = _build_greeting_answer(user_id)
            response_time_ms = int((time.time() - start_time) * 1000)
            metadata = {
                "mode": "rag",
                "intent": "greeting",
                "documents_used": 0,
                "response_time_ms": response_time_ms
            }
            db.log_interaction(
                query=request_data.query,
                response=answer,
                source="web",
                user_id=user_id,
                mode="rag",
                from_cache=False,
                response_time_ms=response_time_ms,
                metadata=metadata
            )
            return QueryResponse(answer=answer, mode="rag", metadata=metadata)

        if state.get("awaiting_contact"):
            answer = await _handle_contact_escalation(user_id, request_data.query, request)
            response_time_ms = int((time.time() - start_time) * 1000)
            metadata = {
                "mode": "rag",
                "escalation": "contact_sent",
                "response_time_ms": response_time_ms
            }
            db.log_interaction(
                query=request_data.query,
                response=answer,
                source="web",
                user_id=user_id,
                mode="rag",
                from_cache=False,
                response_time_ms=response_time_ms,
                metadata=metadata
            )
            return QueryResponse(answer=answer, mode="rag", metadata=metadata)

        # Проверка кэша
        cached = cache.get(request_data.query) if cache else None
        
        if cached:
            answer = cached
            metadata = {"from_cache": True, "mode": request_data.mode or "rag"}
        else:
            # Обработка через ассистент
            answer, metadata = assistant.process_query(
                query=request_data.query,
                user_id=user_id,
                force_mode=request_data.mode
            )

            answer = _apply_rag_escalation(user_id, request_data.query, answer, metadata)
            
            # Сохранение в кэш
            if cache and not metadata.get("escalation"):
                cache.set(request_data.query, answer, metadata)
        
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Логирование
        db.log_interaction(
            query=request_data.query,
            response=answer,
            source="web",
            user_id=user_id,
            mode=metadata.get("mode", "unknown"),
            from_cache=metadata.get("from_cache", False),
            response_time_ms=response_time_ms,
            metadata=metadata
        )
        
        return QueryResponse(
            answer=answer,
            mode=metadata.get("mode", "unknown"),
            metadata={
                **metadata,
                "response_time_ms": response_time_ms
            }
        )
        
    except Exception as e:
        logger.error(f"Ошибка обработки запроса: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/modes")
async def get_available_modes():
    """Получение доступных режимов работы"""
    return {
        "modes": assistant.get_available_modes() if assistant else [],
        "default": "rag"
    }


@app.post("/api/mode")
async def switch_mode(request: ModeSwitchRequest):
    """Переключение режима для пользователя"""
    try:
        assistant.set_mode(request.user_id, request.mode)
        return {
            "user_id": request.user_id,
            "mode": request.mode,
            "status": "ok"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/mode/{user_id}")
async def get_user_mode(user_id: str):
    """Получение текущего режима пользователя"""
    mode = assistant.get_mode(user_id) if assistant else "rag"
    return {"user_id": user_id, "mode": mode}


@app.get("/api/stats")
async def get_stats(days: int = 7):
    """Получение статистики"""
    try:
        stats = db.get_stats(days=days)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/contact")
async def submit_contact_form(
    request: Request,
    form_data: ContactFormRequest
):
    """Прием формы обратной связи"""
    try:
        # Получение IP и User-Agent
        client_ip = request.client.host
        user_agent = request.headers.get("user-agent", "")
        
        # Сохранение в БД
        form_id = db.save_contact_form(
            name=form_data.name,
            email=form_data.email,
            phone=form_data.phone,
            subject=form_data.service,
            message=form_data.message,
            source_ip=client_ip,
            user_agent=user_agent
        )
        
        # Уведомление админу отправляем в фоне: заявка уже сохранена в БД,
        # а проблемы с Telegram не должны замедлять ответ пользователю.
        if alert_manager:
            _send_alert_background(
                f"📧 *Новая заявка с сайта*\n\n"
                f"*От:* {form_data.name}\n"
                f"*Email:* {form_data.email}\n"
                f"*Телефон:* {form_data.phone or 'Не указан'}\n"
                f"*Тема:* {form_data.service or 'Без темы'}\n\n"
                f"_Сообщение:_\n{form_data.message[:300]}...",
                "info"
            )
        _log_system_event("info", "contact_form", "Получена новая заявка с сайта", {
            "form_id": form_id,
            "email": form_data.email,
            "service": form_data.service,
            "has_phone": bool(form_data.phone)
        })
        
        return {
            "status": "ok",
            "form_id": form_id,
            "message": "Сообщение отправлено!"
        }
        
    except Exception as e:
        logger.error(f"Ошибка обработки формы: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# === Admin API ===

@app.get("/api/admin/logs")
async def get_logs(
    source: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """Получение логов (для админки)"""
    try:
        logs = db.get_interactions(
            source=source,
            limit=limit,
            offset=offset
        )
        return {
            "logs": logs,
            "total": len(logs)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/system-logs")
async def get_system_logs(
    level: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """Получение системных логов (для админки)"""
    try:
        logs = db.get_system_logs(
            level=level,
            limit=limit,
            offset=offset
        )
        return {
            "logs": logs,
            "total": len(logs)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/admin/system-logs")
async def clear_system_logs():
    """Очистка системных логов"""
    try:
        db.clear_system_logs()
        return {"status": "ok", "message": "System logs cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/crash-logs")
async def get_crash_logs():
    """Получение логов крашей (для админки)"""
    try:
        import glob
        logs_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
        crash_logs = glob.glob(os.path.join(logs_dir, "crash_*.log"))
        
        crash_logs_data = []
        for log_file in sorted(crash_logs, reverse=True)[:10]:  # Последние 10 логов
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    content = f.read()
                crash_logs_data.append({
                    "filename": os.path.basename(log_file),
                    "content": content,
                    "size": len(content)
                })
            except Exception as e:
                logger.error(f"Ошибка чтения лога {log_file}: {e}")
        
        return {
            "logs": crash_logs_data,
            "total": len(crash_logs_data)
        }
    except Exception as e:
        logger.error(f"Ошибка получения логов крашей: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/contact-forms")
async def get_contact_forms(
    limit: int = 100,
    offset: int = 0
):
    """Получение форм обратной связи (для админки)"""
    try:
        forms = db.get_contact_forms(
            limit=limit,
            offset=offset
        )
        return {
            "forms": forms,
            "total": len(forms)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/export/{table}")
async def export_table(table: str):
    """Экспорт данных в CSV"""
    try:
        csv_data = db.export_to_csv(table)
        if not csv_data:
            raise HTTPException(status_code=404, detail="No data")
        
        # Возвращаем как файл
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={table}.csv"}
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/upload")
async def upload_document(
    file: UploadFile = File(...),
    metadata: Optional[str] = Form("")
):
    """Загрузка документа в базу знаний"""
    try:
        content = await file.read()
        text = content.decode('utf-8')
        
        # Парсинг метаданных
        meta = {}
        if metadata:
            import json
            meta = json.loads(metadata)
        
        meta.update({
            "filename": file.filename,
            "content_type": file.content_type,
            "uploaded_at": str(time.time())
        })
        
        # Добавление в векторную базу
        doc_id = embedding_store.add_document(text, meta)
        
        return {
            "status": "ok",
            "doc_id": doc_id,
            "filename": file.filename
        }
        
    except Exception as e:
        logger.error(f"Ошибка загрузки документа: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/documents")
async def list_documents(limit: int = 100, offset: int = 0):
    """Список документов в базе знаний"""
    try:
        docs = embedding_store.get_all_documents(limit=limit, offset=offset)
        return {
            "documents": docs,
            "total": embedding_store.count()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/admin/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Удаление документа"""
    try:
        embedding_store.delete_document(doc_id)
        return {"status": "ok", "message": "Документ удален"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/clear-cache")
async def clear_assistant_cache():
    """Очистка кэша ассистента"""
    try:
        cache.clear()
        logger.info("Кэш ассистента очищен")
        return {"status": "ok", "message": "Кэш ассистента очищен"}
    except Exception as e:
        logger.error(f"Ошибка очистки кэша: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# API для сохранения данных сайта из админки
@app.post("/api/admin/site-data")
async def save_site_data(data: dict):
    """Сохранение данных сайта из админ-панели"""
    try:
        import json
        # Сохраняем в файл
        data_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "site_data.json")
        os.makedirs(os.path.dirname(data_path), exist_ok=True)
        
        with open(data_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info("Данные сайта сохранены через админ-панель")
        return {"status": "ok", "message": "Данные сохранены"}
    except Exception as e:
        logger.error(f"Ошибка сохранения данных сайта: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/site-data")
async def get_site_data():
    """Получение данных сайта"""
    try:
        import json
        data_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "site_data.json")
        
        if os.path.exists(data_path):
            with open(data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        else:
            # Возвращаем дефолтные данные
            return {
                "profile": {"name": "Станислав", "title": "Промпт-инженер", "about": "Создаю AI-решения"},
                "services": [],
                "skills": [],
                "portfolio": [],
                "contacts": {"telegram": "@stanislav_prompt", "github": "", "docker": ""}
            }
    except Exception as e:
        logger.error(f"Ошибка получения данных сайта: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# === File Upload API ===

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "images")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "portfolio"), exist_ok=True)


def compress_image(image_bytes: bytes, max_size: tuple = (800, 800), quality: int = 85, format: str = "JPEG") -> bytes:
    """
    Сжатие изображения
    
    Args:
        image_bytes: исходные байты изображения
        max_size: максимальные размеры (ширина, высота)
        quality: качество сжатия (1-100)
        format: формат выходного файла
    
    Returns:
        bytes: сжатое изображение
    """
    try:
        # Открываем изображение из байтов
        img = Image.open(io.BytesIO(image_bytes))
        
        # Конвертируем в RGB если необходимо (для PNG с прозрачностью)
        if format == "JPEG" and img.mode in ("RGBA", "P"):
            # Создаем белый фон для прозрачных изображений
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = background
        
        # Изменяем размер если изображение слишком большое
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Сохраняем в буфер
        output = io.BytesIO()
        
        # Для JPEG используем качество, для PNG используем оптимизацию
        if format == "JPEG":
            img.save(output, format=format, quality=quality, optimize=True)
        elif format == "PNG":
            img.save(output, format=format, optimize=True)
        elif format == "WEBP":
            img.save(output, format=format, quality=quality, method=6)
        else:
            img.save(output, format=format)
        
        output.seek(0)
        compressed_bytes = output.getvalue()
        
        # Логируем результаты сжатия
        original_size = len(image_bytes) / 1024  # KB
        compressed_size = len(compressed_bytes) / 1024  # KB
        compression_ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
        
        logger.info(f"Изображение сжато: {original_size:.1f}KB -> {compressed_size:.1f}KB ({compression_ratio:.1f}% уменьшено)")
        
        return compressed_bytes
        
    except Exception as e:
        logger.error(f"Ошибка сжатия изображения: {e}")
        # В случае ошибки возвращаем оригинальные байты
        return image_bytes


@app.post("/api/admin/upload-profile-photo")
async def upload_profile_photo(file: UploadFile = File(...)):
    """Загрузка фото профиля с автоматическим сжатием"""
    try:
        # Проверяем тип файла
        allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="Только изображения (JPEG, PNG, GIF, WEBP)")
        
        # Читаем содержимое
        content = await file.read()
        
        # Проверяем размер (макс 20MB до сжатия)
        if len(content) > 20 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Файл слишком большой (макс 20MB)")
        
        # Определяем формат для сжатия
        if file.content_type == "image/png":
            output_format = "PNG"
            ext = "png"
        elif file.content_type == "image/webp":
            output_format = "WEBP"
            ext = "webp"
        else:
            output_format = "JPEG"
            ext = "jpg"
        
        # Сжимаем изображение (400x400 для профиля, качество 90%)
        compressed_content = compress_image(
            content, 
            max_size=(400, 400), 
            quality=90, 
            format=output_format
        )
        
        # Удаляем старое фото профиля если есть
        for old_ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
            old_file = os.path.join(UPLOAD_DIR, f"profile.{old_ext}")
            if os.path.exists(old_file):
                os.remove(old_file)
        
        # Генерируем имя файла
        filename = f"profile.{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        
        # Сохраняем сжатый файл
        with open(filepath, "wb") as f:
            f.write(compressed_content)
        
        logger.info(f"Фото профиля загружено и сжато: {filename}")
        
        # Обновляем site_data.json с путем к фото профиля
        try:
            import json
            data_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "site_data.json")
            os.makedirs(os.path.dirname(data_path), exist_ok=True)
            
            site_data = {}
            if os.path.exists(data_path):
                with open(data_path, 'r', encoding='utf-8') as f:
                    site_data = json.load(f)
            
            if 'profile' not in site_data:
                site_data['profile'] = {}
            site_data['profile']['photo'] = f"/images/{filename}"
            
            with open(data_path, 'w', encoding='utf-8') as f:
                json.dump(site_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Путь к фото профиля обновлен в site_data.json")
        except Exception as e:
            logger.error(f"Ошибка обновления site_data.json: {e}")
        
        return {
            "status": "ok",
            "filename": filename,
            "path": f"/images/{filename}",
            "original_size": len(content),
            "compressed_size": len(compressed_content),
            "message": "Фото профиля загружено и оптимизировано"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка загрузки фото профиля: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/upload-portfolio-image")
async def upload_portfolio_image(file: UploadFile = File(...)):
    """Загрузка фото для проекта портфолио с автоматическим сжатием"""
    try:
        # Проверяем тип файла
        allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="Только изображения (JPEG, PNG, GIF, WEBP)")
        
        # Читаем содержимое
        content = await file.read()
        
        # Проверяем размер (макс 20MB до сжатия)
        if len(content) > 20 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Файл слишком большой (макс 20MB)")
        
        # Определяем формат для сжатия
        if file.content_type == "image/png":
            output_format = "PNG"
            ext = "png"
        elif file.content_type == "image/webp":
            output_format = "WEBP"
            ext = "webp"
        else:
            output_format = "JPEG"
            ext = "jpg"
        
        # Сжимаем изображение (1200x800 для портфолио, качество 85%)
        compressed_content = compress_image(
            content, 
            max_size=(1200, 800), 
            quality=85, 
            format=output_format
        )
        
        # Генерируем уникальное имя файла
        timestamp = int(time.time())
        filename = f"portfolio_{timestamp}.{ext}"
        filepath = os.path.join(UPLOAD_DIR, "portfolio", filename)
        
        # Сохраняем сжатый файл
        with open(filepath, "wb") as f:
            f.write(compressed_content)
        
        logger.info(f"Фото проекта загружено и сжато: {filename}")
        
        return {
            "status": "ok",
            "filename": filename,
            "path": f"/images/portfolio/{filename}",
            "original_size": len(content),
            "compressed_size": len(compressed_content),
            "message": "Фото проекта загружено и оптимизировано"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка загрузки фото проекта: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/images")
async def list_images():
    """Получение списка загруженных изображений"""
    try:
        images = {
            "profile": None,
            "portfolio": []
        }
        
        # Проверяем фото профиля
        profile_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp']
        for ext in profile_extensions:
            profile_path = os.path.join(UPLOAD_DIR, f"profile.{ext}")
            if os.path.exists(profile_path):
                images["profile"] = f"/images/profile.{ext}"
                break
        
        # Получаем фото проектов
        portfolio_dir = os.path.join(UPLOAD_DIR, "portfolio")
        if os.path.exists(portfolio_dir):
            for filename in os.listdir(portfolio_dir):
                if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                    images["portfolio"].append({
                        "filename": filename,
                        "path": f"/images/portfolio/{filename}"
                    })
        
        return images
        
    except Exception as e:
        logger.error(f"Ошибка получения списка изображений: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/admin/images/{image_type}/{filename}")
async def delete_image(image_type: str, filename: str):
    """Удаление изображения"""
    try:
        # Базовая директория
        if image_type == "profile":
            filepath = os.path.join(UPLOAD_DIR, filename)
        elif image_type == "portfolio":
            filepath = os.path.join(UPLOAD_DIR, "portfolio", filename)
        else:
            raise HTTPException(status_code=400, detail="Неверный тип изображения")
        
        # Проверяем что файл внутри разрешенной директории (безопасность)
        real_path = os.path.realpath(filepath)
        if not real_path.startswith(os.path.realpath(UPLOAD_DIR)):
            raise HTTPException(status_code=403, detail="Доступ запрещен")
        
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Изображение удалено: {filepath}")
            return {"status": "ok", "message": "Изображение удалено"}
        else:
            raise HTTPException(status_code=404, detail="Файл не найден")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка удаления изображения: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# === Static Files ===

# Проверка существования frontend директории
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")
    
    @app.get("/{path:path}")
    async def serve_spa(path: str):
        """SPA fallback"""
        index_path = os.path.join(frontend_dir, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        raise HTTPException(status_code=404)
else:
    @app.get("/")
    async def root():
        return {"message": f"{APP_NAME} API", "version": APP_VERSION}

# Монтируем директорию uploads для изображений
if os.path.exists(UPLOAD_DIR):
    app.mount("/images", StaticFiles(directory=UPLOAD_DIR), name="images")


if __name__ == "__main__":
    import uvicorn
    from config.settings import HOST, PORT
    
    uvicorn.run(app, host=HOST, port=PORT)
