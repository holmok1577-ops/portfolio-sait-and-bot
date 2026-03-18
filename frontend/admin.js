// Admin Panel JavaScript

const API_BASE_URL = window.location.origin;
let currentPage = 1;
const pageSize = 20;

// Показать таб
def window.showTab(tabName) {
    // Скрыть все табы
    document.querySelectorAll('.tab__content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Убрать активность с кнопок
    document.querySelectorAll('.nav__btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Показать нужный таб
    document.getElementById(tabName).classList.add('active');
    
    // Активировать кнопку
    event.target.classList.add('active');
    
    // Загрузить данные
    if (tabName === 'dashboard') loadDashboard();
    if (tabName === 'logs') loadLogs();
    if (tabName === 'documents') loadDocuments();
    if (tabName === 'health') checkHealth();
    if (tabName === 'contacts') loadContacts();
}

// Загрузка дашборда
async function loadDashboard() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/stats?days=7`);
        if (!response.ok) throw new Error('Failed to load stats');
        
        const stats = await response.json();
        
        document.getElementById('statTotal').textContent = stats.total_requests || 0;
        document.getElementById('statCached').textContent = stats.cached_requests || 0;
        document.getElementById('statUsers').textContent = stats.unique_users || 0;
        document.getElementById('statAvgTime').textContent = 
            Math.round(stats.avg_response_time_ms || 0) + ' мс';
        
        // Заполнить таблицу по источникам
        const tbody = document.querySelector('#sourceStatsTable tbody');
        tbody.innerHTML = '';
        
        const total = stats.total_requests || 1;
        
        if (stats.by_source) {
            for (const [source, count] of Object.entries(stats.by_source)) {
                const row = document.createElement('tr');
                const percentage = ((count / total) * 100).toFixed(1);
                
                row.innerHTML = `
                    <td>${escapeHtml(source)}</td>
                    <td>${count}</td>
                    <td>
                        <div style="display: flex; align-items: center; gap: 0.5rem;">
                            <div style="flex: 1; background: var(--bg); height: 8px; border-radius: 4px; overflow: hidden;">
                                <div style="width: ${percentage}%; height: 100%; background: var(--primary);"></div>
                            </div>
                            <span style="font-size: 0.75rem;">${percentage}%</span>
                        </div>
                    </td>
                `;
                tbody.appendChild(row);
            }
        }
        
    } catch (e) {
        console.error('Error loading dashboard:', e);
        showError('Ошибка загрузки статистики');
    }
}

function refreshStats() {
    loadDashboard();
}

// Логи
async function loadLogs() {
    try {
        const response = await fetch(
            `${API_BASE_URL}/api/admin/logs?limit=${pageSize}&offset=${(currentPage - 1) * pageSize}`
        );
        if (!response.ok) throw new Error('Failed to load logs');
        
        const data = await response.json();
        renderLogsTable(data.logs || []);
        renderPagination(data.total || 0);
        
    } catch (e) {
        console.error('Error loading logs:', e);
        showError('Ошибка загрузки логов');
    }
}

function renderLogsTable(logs) {
    const tbody = document.querySelector('#logsTable tbody');
    tbody.innerHTML = '';
    
    logs.forEach(log => {
        const row = document.createElement('tr');
        const date = new Date(log.timestamp).toLocaleString('ru-RU');
        
        row.innerHTML = `
            <td>${date}</td>
            <td>
                <span class="badge ${log.source === 'web' ? 'badge--success' : 'badge--warning'}">
                    ${escapeHtml(log.source)}
                </span>
            </td>
            <td>${escapeHtml(log.username || log.user_id || 'N/A')}</td>
            <td>${escapeHtml(log.mode || 'N/A')}</td>
            <td title="${escapeHtml(log.query)}">${escapeHtml(log.query.substring(0, 50))}...</td>
            <td>${log.response_time_ms} мс</td>
            <td>${log.from_cache ? '✓' : '-'}</td>
        `;
        tbody.appendChild(row);
    });
}

function renderPagination(total) {
    const totalPages = Math.ceil(total / pageSize);
    const pagination = document.getElementById('logsPagination');
    pagination.innerHTML = '';
    
    for (let i = 1; i <= totalPages; i++) {
        const btn = document.createElement('button');
        btn.textContent = i;
        btn.onclick = () => { currentPage = i; loadLogs(); };
        if (i === currentPage) {
            btn.style.background = 'var(--primary)';
        }
        pagination.appendChild(btn);
    }
}

function filterLogs() {
    currentPage = 1;
    loadLogs();
}

function refreshLogs() {
    loadLogs();
}

async function exportLogs() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/admin/export/interactions`);
        if (!response.ok) throw new Error('Failed to export');
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `logs_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
    } catch (e) {
        console.error('Error exporting logs:', e);
        showError('Ошибка экспорта');
    }
}

// Документы
async function loadDocuments() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/admin/documents`);
        if (!response.ok) throw new Error('Failed to load documents');
        
        const data = await response.json();
        document.getElementById('docCount').textContent = data.total || 0;
        
        const tbody = document.querySelector('#documentsTable tbody');
        tbody.innerHTML = '';
        
        data.documents.forEach(doc => {
            const row = document.createElement('tr');
            const text = doc.text || '';
            const meta = doc.metadata || {};
            
            row.innerHTML = `
                <td>${doc.id.substring(0, 8)}...</td>
                <td>${escapeHtml(meta.source || 'N/A')}</td>
                <td>${escapeHtml(meta.category || 'N/A')}</td>
                <td title="${escapeHtml(text)}">${escapeHtml(text.substring(0, 100))}...</td>
                <td>
                    <button class="btn btn--danger" onclick="deleteDocument('${doc.id}')">
                        Удалить
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });
        
    } catch (e) {
        console.error('Error loading documents:', e);
        showError('Ошибка загрузки документов');
    }
}

function refreshDocuments() {
    loadDocuments();
}

async function deleteDocument(docId) {
    if (!confirm('Удалить этот документ?')) return;
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/admin/documents/${docId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            loadDocuments();
            showSuccess('Документ удален');
        } else {
            showError('Ошибка удаления');
        }
        
    } catch (e) {
        console.error('Error deleting document:', e);
        showError('Ошибка удаления');
    }
}

// Модал загрузки
function showUploadModal() {
    document.getElementById('uploadModal').classList.add('active');
}

function hideUploadModal() {
    document.getElementById('uploadModal').classList.remove('active');
    document.getElementById('uploadForm').reset();
}

// Загрузка документа
document.getElementById('uploadForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const file = document.getElementById('docFile').files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    const metadata = {
        source: document.getElementById('docSource').value || file.name,
        category: document.getElementById('docCategory').value
    };
    formData.append('metadata', JSON.stringify(metadata));
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/admin/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            hideUploadModal();
            loadDocuments();
            showSuccess('Документ загружен');
        } else {
            const error = await response.json();
            showError(error.detail || 'Ошибка загрузки');
        }
        
    } catch (e) {
        console.error('Error uploading:', e);
        showError('Ошибка загрузки');
    }
});

// Здоровье системы
async function checkHealth() {
    const healthStatus = document.getElementById('healthStatus');
    healthStatus.innerHTML = '<p>Проверка...</p>';
    
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        const data = await response.json();
        
        healthStatus.innerHTML = '';
        
        for (const [component, info] of Object.entries(data.components || {})) {
            const div = document.createElement('div');
            div.className = 'health__item';
            
            const isOk = info.status === 'ok';
            const statusClass = isOk ? 'status--ok' : 'status--error';
            
            div.innerHTML = `
                <h4>
                    <span class="status__indicator ${statusClass}"></span>
                    ${escapeHtml(component)}
                </h4>
                <p style="color: ${isOk ? 'var(--success)' : 'var(--error)'};">
                    ${isOk ? '✓ Работает' : '✗ Ошибка'}
                </p>
                ${info.response_time_ms ? `<p style="font-size: 0.75rem; color: var(--text-muted);">
                    Время ответа: ${info.response_time_ms} мс
                </p>` : ''}
                ${info.error ? `<p style="font-size: 0.75rem; color: var(--error);">
                    ${escapeHtml(info.error)}
                </p>` : ''}
            `;
            healthStatus.appendChild(div);
        }
        
    } catch (e) {
        console.error('Error checking health:', e);
        healthStatus.innerHTML = '<p class="text--error">Ошибка проверки статуса</p>';
    }
}

// Заявки
async function loadContacts() {
    // TODO: API endpoint для заявок
    showInfo('Загрузка заявок пока не реализована');
}

function refreshContacts() {
    loadContacts();
}

// Утилиты
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showSuccess(msg) {
    showToast(msg, 'success');
}

function showError(msg) {
    showToast(msg, 'error');
}

function showInfo(msg) {
    showToast(msg, 'info');
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 1.5rem;
        background: ${type === 'error' ? 'var(--error)' : type === 'success' ? 'var(--success)' : 'var(--primary)'};
        color: white;
        border-radius: 8px;
        z-index: 10000;
        animation: slideIn 0.3s ease;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Загрузка при старте
document.addEventListener('DOMContentLoaded', () => {
    loadDashboard();
    
    // Обновление каждые 30 секунд
    setInterval(() => {
        const activeTab = document.querySelector('.tab__content.active');
        if (activeTab?.id === 'dashboard') loadDashboard();
        if (activeTab?.id === 'health') checkHealth();
    }, 30000);
});

// Закрытие модала по клику вне его
window.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal')) {
        e.target.classList.remove('active');
    }
});
