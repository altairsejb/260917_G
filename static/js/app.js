/**
 * TaskFlow - Frontend Application Logic
 * Modern, responsive task management system
 */

// Application State
const state = {
    todos: [],
    stats: {},
    filterStatus: 'all',
    category: 'all',
    priority: 'all',
    search: '',
    sortBy: 'created_at',
    order: 'desc',
    theme: localStorage.getItem('taskflow_theme') || 'dark',
    editingId: null
};

// DOM Elements
const elements = {
    // Stats
    statTotal: document.getElementById('stat-total'),
    statPending: document.getElementById('stat-pending'),
    statCompleted: document.getElementById('stat-completed'),
    statRateText: document.getElementById('stat-rate-text'),
    statProgressFill: document.getElementById('stat-progress-fill'),
    statRateDesc: document.getElementById('stat-rate-desc'),
    listCountBadge: document.getElementById('list-count-badge'),

    // Search & Filters
    searchInput: document.getElementById('search-input'),
    clearSearchBtn: document.getElementById('clear-search'),
    statusTabs: document.querySelectorAll('.tab-btn'),
    categoryFilter: document.getElementById('category-filter'),
    priorityFilter: document.getElementById('priority-filter'),
    sortFilter: document.getElementById('sort-filter'),
    categoryChips: document.querySelectorAll('.chip'),
    cleanCompletedBtn: document.getElementById('clean-completed-btn'),

    // List & Empty State
    todoList: document.getElementById('todo-list'),
    emptyState: document.getElementById('empty-state'),
    emptyAddBtn: document.getElementById('empty-add-btn'),

    // Modal & Form
    todoModal: document.getElementById('todo-modal'),
    modalTitle: document.getElementById('modal-title'),
    openAddModalBtn: document.getElementById('open-add-modal-btn'),
    closeModalBtn: document.getElementById('close-modal-btn'),
    cancelModalBtn: document.getElementById('cancel-modal-btn'),
    todoForm: document.getElementById('todo-form'),
    todoIdInput: document.getElementById('todo-id'),
    todoTitleInput: document.getElementById('todo-title-input'),
    todoDescInput: document.getElementById('todo-desc-input'),
    todoCategoryInput: document.getElementById('todo-category-input'),
    todoDueInput: document.getElementById('todo-due-input'),

    // Theme & Header
    themeToggle: document.getElementById('theme-toggle'),
    themeIcon: document.getElementById('theme-icon'),
    headerDate: document.getElementById('header-date'),
    toastContainer: document.getElementById('toast-container')
};

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initDate();
    initEventListeners();
    loadData();
});

// Setup Theme
function initTheme() {
    document.documentElement.setAttribute('data-theme', state.theme);
    updateThemeIcon();
}

function updateThemeIcon() {
    if (state.theme === 'light') {
        elements.themeIcon.className = 'fa-solid fa-sun';
    } else {
        elements.themeIcon.className = 'fa-solid fa-moon';
    }
}

function toggleTheme() {
    state.theme = state.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('taskflow_theme', state.theme);
    document.documentElement.setAttribute('data-theme', state.theme);
    updateThemeIcon();
    showToast(`${state.theme === 'dark' ? '다크' : '라이트'} 모드로 전환되었습니다.`, 'info');
}

// Setup Current Date in Header
function initDate() {
    const now = new Date();
    const options = { year: 'numeric', month: '2-digit', day: '2-digit', weekday: 'short' };
    elements.headerDate.textContent = now.toLocaleDateString('ko-KR', options);
}

// Event Listeners
function initEventListeners() {
    // Theme Switch
    elements.themeToggle.addEventListener('click', toggleTheme);

    // Modal Triggers
    elements.openAddModalBtn.addEventListener('click', () => openModal());
    elements.emptyAddBtn.addEventListener('click', () => openModal());
    elements.closeModalBtn.addEventListener('click', closeModal);
    elements.cancelModalBtn.addEventListener('click', closeModal);

    // Close modal on backdrop click
    elements.todoModal.addEventListener('click', (e) => {
        if (e.target === elements.todoModal) closeModal();
    });

    // Keyboard Shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && elements.todoModal.classList.contains('active')) {
            closeModal();
        }
    });

    // Form Submit
    elements.todoForm.addEventListener('submit', handleFormSubmit);

    // Search Input with Debounce
    let debounceTimer;
    elements.searchInput.addEventListener('input', (e) => {
        const val = e.target.value;
        elements.clearSearchBtn.style.display = val ? 'block' : 'none';
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            state.search = val;
            loadData();
        }, 300);
    });

    elements.clearSearchBtn.addEventListener('click', () => {
        elements.searchInput.value = '';
        elements.clearSearchBtn.style.display = 'none';
        state.search = '';
        loadData();
    });

    // Status Tabs
    elements.statusTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            elements.statusTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            state.filterStatus = tab.dataset.status;
            loadData();
        });
    });

    // Category Filter (Dropdown)
    elements.categoryFilter.addEventListener('change', (e) => {
        state.category = e.target.value;
        syncCategoryChips(state.category);
        loadData();
    });

    // Category Chips (Quick Select)
    elements.categoryChips.forEach(chip => {
        chip.addEventListener('click', () => {
            elements.categoryChips.forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            state.category = chip.dataset.cat;
            elements.categoryFilter.value = state.category;
            loadData();
        });
    });

    // Priority Filter
    elements.priorityFilter.addEventListener('change', (e) => {
        state.priority = e.target.value;
        loadData();
    });

    // Sort Filter
    elements.sortFilter.addEventListener('change', (e) => {
        const selectedOption = e.target.options[e.target.selectedIndex];
        state.sortBy = e.target.value;
        state.order = selectedOption.dataset.order || 'desc';
        loadData();
    });

    // Clear Completed Button
    elements.cleanCompletedBtn.addEventListener('click', handleCleanCompleted);
}

function syncCategoryChips(category) {
    elements.categoryChips.forEach(chip => {
        chip.classList.toggle('active', chip.dataset.cat === category);
    });
}

// Data Fetching & Rendering
async function loadData() {
    try {
        await Promise.all([fetchTodos(), fetchStats()]);
    } catch (err) {
        console.error('Error loading data:', err);
        showToast('데이터를 불러오는 중 오류가 발생했습니다.', 'error');
    }
}

async function fetchTodos() {
    const params = new URLSearchParams({
        status: state.filterStatus,
        category: state.category,
        priority: state.priority,
        search: state.search,
        sort_by: state.sortBy,
        order: state.order
    });

    const res = await fetch(`/api/todos?${params.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch todos');
    state.todos = await res.json();
    renderTodos(state.todos);
}

async function fetchStats() {
    const res = await fetch('/api/stats');
    if (!res.ok) throw new Error('Failed to fetch stats');
    state.stats = await res.json();
    renderStats(state.stats);
}

// Render Todo Items
function renderTodos(todos) {
    elements.listCountBadge.textContent = todos.length;

    if (!todos || todos.length === 0) {
        elements.todoList.innerHTML = '';
        elements.emptyState.style.display = 'flex';
        return;
    }

    elements.emptyState.style.display = 'none';
    elements.todoList.innerHTML = todos.map(todo => createTodoCardHTML(todo)).join('');

    // Bind event listeners to rendered cards
    todos.forEach(todo => {
        const card = document.getElementById(`todo-${todo.id}`);
        if (!card) return;

        // Checkbox Toggle
        const checkbox = card.querySelector('.todo-checkbox-input');
        checkbox.addEventListener('change', () => toggleTodoStatus(todo.id));

        // Edit Button
        const editBtn = card.querySelector('.edit-btn');
        editBtn.addEventListener('click', () => openModal(todo));

        // Delete Button
        const deleteBtn = card.querySelector('.delete-btn');
        deleteBtn.addEventListener('click', () => confirmDeleteTodo(todo.id, todo.title));
    });
}

// Generate Todo Card HTML
function createTodoCardHTML(todo) {
    const isChecked = todo.completed === 1;
    const priorityClass = `priority-${todo.priority}`;
    const priorityLabel = {
        high: '🔴 높음',
        medium: '🟡 중간',
        low: '🟢 낮음'
    }[todo.priority] || '중간';

    // Due Date Badge
    let dueBadgeHTML = '';
    if (todo.due_date) {
        const dueInfo = formatDueStatus(todo.due_date);
        dueBadgeHTML = `<span class="badge badge-due ${dueInfo.className}">
            <i class="fa-regular fa-calendar-check"></i> ${dueInfo.text}
        </span>`;
    }

    return `
        <article class="todo-card glass-card ${priorityClass} ${isChecked ? 'is-completed' : ''}" id="todo-${todo.id}">
            <div class="todo-main-content">
                <label class="custom-checkbox">
                    <input type="checkbox" class="todo-checkbox-input" ${isChecked ? 'checked' : ''} aria-label="할일 완료 여부">
                    <span class="checkmark"></span>
                </label>
                <div class="todo-text-wrap">
                    <h4 class="todo-title">${escapeHTML(todo.title)}</h4>
                    ${todo.description ? `<p class="todo-desc">${escapeHTML(todo.description)}</p>` : ''}
                </div>
            </div>

            <div class="todo-meta-footer">
                <div class="todo-badges">
                    <span class="badge badge-category">📁 ${escapeHTML(todo.category || '일반')}</span>
                    <span class="badge badge-priority-${todo.priority}">${priorityLabel}</span>
                    ${dueBadgeHTML}
                </div>
                <div class="todo-card-actions">
                    <button class="action-btn edit-btn" title="할일 수정" aria-label="수정">
                        <i class="fa-regular fa-pen-to-square"></i>
                    </button>
                    <button class="action-btn delete-btn" title="할일 삭제" aria-label="삭제">
                        <i class="fa-regular fa-trash-can"></i>
                    </button>
                </div>
            </div>
        </article>
    `;
}

// Due Date Calculation
function formatDueStatus(dueDateStr) {
    if (!dueDateStr) return { text: '', className: '' };

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const [year, month, day] = dueDateStr.split('-').map(Number);
    const dueDate = new Date(year, month - 1, day);
    dueDate.setHours(0, 0, 0, 0);

    const diffDays = Math.ceil((dueDate - today) / (1000 * 60 * 60 * 24));

    if (diffDays < 0) {
        return { text: `${dueDateStr} (지남)`, className: 'due-urgent' };
    } else if (diffDays === 0) {
        return { text: '오늘 마감', className: 'due-today' };
    } else if (diffDays === 1) {
        return { text: '내일 마감 (D-1)', className: 'due-today' };
    } else {
        return { text: `${dueDateStr} (D-${diffDays})`, className: '' };
    }
}

// Render Stats & Progress
function renderStats(stats) {
    elements.statTotal.textContent = stats.total || 0;
    elements.statPending.textContent = stats.pending || 0;
    elements.statCompleted.textContent = stats.completed || 0;

    const rate = stats.completion_rate || 0;
    elements.statRateText.textContent = `${rate}%`;
    elements.statProgressFill.style.width = `${rate}%`;

    if (rate === 100 && stats.total > 0) {
        elements.statRateDesc.textContent = '🎉 모든 할일을 완벽하게 끝마쳤습니다!';
    } else if (rate >= 50) {
        elements.statRateDesc.textContent = '🔥 절반 이상 달성! 조금만 더 힘내세요.';
    } else {
        elements.statRateDesc.textContent = '오늘도 한 걸음씩 차근차근 전진해봐요!';
    }
}

// Modal Handlers
function openModal(todo = null) {
    if (todo) {
        state.editingId = todo.id;
        elements.modalTitle.textContent = '할일 수정';
        elements.todoIdInput.value = todo.id;
        elements.todoTitleInput.value = todo.title;
        elements.todoDescInput.value = todo.description || '';
        elements.todoCategoryInput.value = todo.category || '일반';
        elements.todoDueInput.value = todo.due_date || '';

        const radio = document.querySelector(`input[name="priority"][value="${todo.priority}"]`);
        if (radio) radio.checked = true;
    } else {
        state.editingId = null;
        elements.modalTitle.textContent = '새 할일 추가';
        elements.todoForm.reset();
        elements.todoIdInput.value = '';
        
        // Default priority: medium
        const medRadio = document.querySelector('input[name="priority"][value="medium"]');
        if (medRadio) medRadio.checked = true;

        // Default due date: tomorrow or today
        const todayStr = new Date().toISOString().split('T')[0];
        elements.todoDueInput.value = todayStr;
    }

    elements.todoModal.classList.add('active');
    setTimeout(() => elements.todoTitleInput.focus(), 100);
}

function closeModal() {
    elements.todoModal.classList.remove('active');
    state.editingId = null;
    elements.todoForm.reset();
}

// Handle Form Submission (Create or Update)
async function handleFormSubmit(e) {
    e.preventDefault();

    const title = elements.todoTitleInput.value.trim();
    if (!title) {
        showToast('제목을 입력해주세요.', 'error');
        return;
    }

    const payload = {
        title: title,
        description: elements.todoDescInput.value.trim(),
        category: elements.todoCategoryInput.value,
        due_date: elements.todoDueInput.value,
        priority: document.querySelector('input[name="priority"]:checked')?.value || 'medium'
    };

    try {
        if (state.editingId) {
            // Update
            const res = await fetch(`/api/todos/${state.editingId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!res.ok) throw new Error('수정 실패');
            showToast('할일이 성공적으로 수정되었습니다.', 'success');
        } else {
            // Create
            const res = await fetch('/api/todos', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!res.ok) throw new Error('추가 실패');
            showToast('새로운 할일이 등록되었습니다.', 'success');
        }

        closeModal();
        loadData();
    } catch (err) {
        console.error('Submit error:', err);
        showToast('요청 처리 중 오류가 발생했습니다.', 'error');
    }
}

// Toggle Completed Status
async function toggleTodoStatus(id) {
    try {
        const res = await fetch(`/api/todos/${id}/toggle`, { method: 'PATCH' });
        if (!res.ok) throw new Error('상태 변경 실패');
        const updated = await res.json();
        
        showToast(
            updated.completed ? '🎉 할일을 완료했습니다!' : '할일 상태를 진행 중으로 변경했습니다.',
            'success'
        );
        loadData();
    } catch (err) {
        console.error('Toggle error:', err);
        showToast('상태 변경 중 오류가 발생했습니다.', 'error');
    }
}

// Delete Single Todo
async function confirmDeleteTodo(id, title) {
    if (!confirm(`'${title}' 항목을 삭제하시겠습니까?`)) return;

    try {
        const res = await fetch(`/api/todos/${id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('삭제 실패');
        showToast('할일이 삭제되었습니다.', 'info');
        loadData();
    } catch (err) {
        console.error('Delete error:', err);
        showToast('삭제 중 오류가 발생했습니다.', 'error');
    }
}

// Clean All Completed Todos
async function handleCleanCompleted() {
    const completedCount = state.stats.completed || 0;
    if (completedCount === 0) {
        showToast('정리할 완료된 할일이 없습니다.', 'info');
        return;
    }

    if (!confirm(`완료된 항목 ${completedCount}개를 모두 정리하시겠습니까?`)) return;

    try {
        const res = await fetch('/api/todos/completed', { method: 'DELETE' });
        if (!res.ok) throw new Error('일괄 삭제 실패');
        const data = await res.json();
        showToast(`완료 항목 ${data.deleted_count}개가 정리되었습니다.`, 'success');
        loadData();
    } catch (err) {
        console.error('Clean completed error:', err);
        showToast('정리 중 오류가 발생했습니다.', 'error');
    }
}

// Toast Notification Utility
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    let iconClass = 'fa-solid fa-circle-info';
    if (type === 'success') iconClass = 'fa-solid fa-circle-check';
    if (type === 'error') iconClass = 'fa-solid fa-triangle-exclamation';

    toast.innerHTML = `
        <i class="${iconClass}"></i>
        <span>${escapeHTML(message)}</span>
    `;

    elements.toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px) scale(0.95)';
        setTimeout(() => toast.remove(), 300);
    }, 3200);
}

// Helper: Escape HTML string to prevent XSS
function escapeHTML(str) {
    if (!str) return '';
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
