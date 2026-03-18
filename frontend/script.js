// Portfolio AI Assistant - Frontend JavaScript

// Конфигурация API
const API_BASE_URL = window.location.origin;
let currentUserId = null;
let currentMode = 'rag';

// Генерация уникального ID пользователя
function getUserId() {
    if (!currentUserId) {
        currentUserId = localStorage.getItem('user_id');
        if (!currentUserId) {
            currentUserId = 'web_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('user_id', currentUserId);
        }
    }
    return currentUserId;
}

// Управление чат-виджетом
function toggleChat() {
    const widget = document.getElementById('chatWidget');
    const toggle = document.getElementById('chatToggle');
    
    widget.classList.toggle('active');
    toggle.classList.toggle('hidden');
    
    if (widget.classList.contains('active')) {
        document.getElementById('chatInput').focus();
        loadUserMode();
    }
}

// Загрузка режима пользователя
async function loadUserMode() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/mode/${getUserId()}`);
        if (response.ok) {
            const data = await response.json();
            currentMode = data.mode;
            updateModeButton();
        }
    } catch (e) {
        console.error('Ошибка загрузки режима:', e);
    }
}

// Обновление кнопки режима
function updateModeButton() {
    const modeBtn = document.getElementById('modeToggle');
    if (currentMode === 'rag') {
        modeBtn.textContent = '📚 RAG';
        modeBtn.title = 'Режим RAG (база знаний). Нажмите для переключения';
    } else {
        modeBtn.textContent = '💬 AI';
        modeBtn.title = 'Режим AI помощника. Нажмите для переключения';
    }
}

// Переключение режима
async function toggleMode() {
    const newMode = currentMode === 'rag' ? 'assistant' : 'rag';
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/mode`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: getUserId(),
                mode: newMode
            })
        });
        
        if (response.ok) {
            currentMode = newMode;
            updateModeButton();
            
            // Добавляем системное сообщение
            const modeText = newMode === 'rag' ? 'RAG режим (база знаний)' : 'AI помощник';
            addSystemMessage(`Режим переключен: ${modeText}`);
        }
    } catch (e) {
        console.error('Ошибка переключения режима:', e);
        showToast('Ошибка переключения режима', 'error');
    }
}

// Добавление сообщения в чат
function addMessage(text, isUser = false, isSystem = false) {
    const chatBody = document.getElementById('chatBody');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat__message chat__message--${isUser ? 'user' : 'bot'}`;
    
    if (isSystem) {
        messageDiv.innerHTML = `
            <div class="message__bubble" style="background: var(--bg-light); font-size: 0.75rem; color: var(--text-muted);">
                ${escapeHtml(text)}
            </div>
        `;
    } else {
        messageDiv.innerHTML = `
            <div class="message__avatar">${isUser ? '👤' : '🤖'}</div>
            <div class="message__bubble">${formatMessage(text)}</div>
        `;
    }
    
    chatBody.appendChild(messageDiv);
    chatBody.scrollTop = chatBody.scrollHeight;
    
    return messageDiv;
}

// Добавление системного сообщения
function addSystemMessage(text) {
    return addMessage(text, false, true);
}

// Форматирование сообщения (ссылки, переносы строк)
function formatMessage(text) {
    if (!text) return '';
    
    // Экранирование HTML
    text = escapeHtml(text);
    
    // Преобразование ссылок
    text = text.replace(
        /(https?:\/\/[^\s]+)/g,
        '<a href="$1" target="_blank" rel="noopener">$1</a>'
    );
    
    // Переносы строк
    text = text.replace(/\n/g, '<br>');
    
    return text;
}

// Экранирование HTML
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Показать индикатор печати
function showTyping() {
    const typing = document.getElementById('chatTyping');
    typing.style.display = 'flex';
    document.getElementById('chatBody').scrollTop = document.getElementById('chatBody').scrollHeight;
}

// Скрыть индикатор печати
function hideTyping() {
    document.getElementById('chatTyping').style.display = 'none';
}

// Отправка сообщения
async function sendMessage() {
    const input = document.getElementById('chatInput');
    const text = input.value.trim();
    
    if (!text) return;
    
    // Очистка поля
    input.value = '';
    
    // Добавление сообщения пользователя
    addMessage(text, true);
    
    // Показать индикатор печати
    showTyping();
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: text,
                mode: currentMode,
                user_id: getUserId()
            })
        });
        
        hideTyping();
        
        if (response.ok) {
            const data = await response.json();
            
            // Добавление ответа бота
            addMessage(data.answer, false);
            
            // Индикатор кэша
            if (data.metadata && data.metadata.from_cache) {
                addSystemMessage('💾 Ответ из кэша');
            }
            
            // Обновление режима если он изменился
            if (data.mode && data.mode !== currentMode) {
                currentMode = data.mode;
                updateModeButton();
            }
        } else {
            const error = await response.json();
            addMessage('❌ Ошибка: ' + (error.detail || 'Не удалось получить ответ'), false);
        }
        
    } catch (e) {
        hideTyping();
        console.error('Ошибка отправки:', e);
        addMessage('❌ Ошибка соединения. Пожалуйста, попробуйте позже.', false);
    }
}

// Toast уведомления
function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    
    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.textContent = message;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 5000);
}

// Обработка формы обратной связи
async function submitContactForm(e) {
    e.preventDefault();
    
    const form = e.target;
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Отправка...';
    
    try {
        const formData = {
            name: document.getElementById('name')?.value || document.getElementById('formName')?.value,
            email: document.getElementById('email')?.value || document.getElementById('formEmail')?.value,
            service: document.getElementById('service')?.value || document.getElementById('formService')?.value,
            message: document.getElementById('message')?.value || document.getElementById('formMessage')?.value
        };
        
        const response = await fetch(`${API_BASE_URL}/api/contact`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });
        
        if (response.ok) {
            showToast('✅ Сообщение отправлено! Я свяжусь с вами в течение 24 часов.');
            form.reset();
        } else {
            const error = await response.json();
            showToast('❌ ' + (error.detail || 'Ошибка отправки'), 'error');
        }
        
    } catch (e) {
        console.error('Ошибка:', e);
        showToast('❌ Ошибка соединения. Попробуйте позже.', 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
    }
}

// Инициализация
document.addEventListener('DOMContentLoaded', function() {
    // Форма чата
    const chatForm = document.getElementById('chatForm');
    if (chatForm) {
        chatForm.addEventListener('submit', function(e) {
            e.preventDefault();
            sendMessage();
        });
    }
    
    // Кнопка переключения режима
    const modeBtn = document.getElementById('modeToggle');
    if (modeBtn) {
        modeBtn.addEventListener('click', toggleMode);
    }
    
    // Форма обратной связи
    const contactForm = document.getElementById('contactForm');
    if (contactForm) {
        contactForm.addEventListener('submit', submitContactForm);
    }
    
    // Обработка Enter в поле чата
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
        chatInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }
    
    // Загрузка режима при старте
    loadUserMode();
    
    // Проверка здоровья системы
    checkHealth();
    
    // Автопроверка каждые 30 секунд
    setInterval(checkHealth, 30000);
});

// Проверка здоровья системы
async function checkHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (!response.ok) {
            console.warn('Система может быть недоступна');
        }
    } catch (e) {
        // Тихая ошибка - не показываем пользователю
    }
}

// Экспорт функций для использования в других скриптах
window.PortfolioAI = {
    toggleChat,
    toggleMode,
    sendMessage,
    showToast,
    getUserId,
    currentMode
};
