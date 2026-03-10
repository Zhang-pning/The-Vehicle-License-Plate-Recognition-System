const usernameRegex = /^[a-zA-Z0-9]+$/;
const passwordRegex = /^[a-zA-Z0-9!@#$%^&*()_\-+=\[\]{}|\\;:'",.<>/?]+$/;
const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

let currentUsers = [];
let currentPage = 1;
let pageSize = 10;
let totalUsers = 0;

const userTableBody = document.getElementById('userTableBody');
const searchUsername = document.getElementById('searchUsername');
const searchEmail = document.getElementById('searchEmail');
const searchState = document.getElementById('searchState');
const searchBtn = document.getElementById('searchBtn');
const resetBtn = document.getElementById('resetBtn');
const addUserBtn = document.getElementById('addUserBtn');
const modal = document.getElementById('addUserModal');
const closeModal = document.getElementById('closeModal');
const addUserForm = document.getElementById('addUserForm');
const prevPageBtn = document.getElementById('prevPage');
const nextPageBtn = document.getElementById('nextPage');
const pageInfo = document.getElementById('pageInfo');

document.addEventListener('DOMContentLoaded', () => {
    loadUsers({}, 1);
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', logout);
    }
});
async function loadUsers(params = {}, page = currentPage) {
    userTableBody.innerHTML = '<tr><td colspan="9" class="loading">加载中...</td></tr>';

    params.page = page;
    params.limit = pageSize;

    const query = new URLSearchParams(params).toString();
    try {
        const response = await fetch(`/api/admin/users?${query}`, {
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            currentUsers = data.users;
            totalUsers = data.total;
            currentPage = data.page;
            renderTable(currentUsers);
            updatePagination();
        } else {
            userTableBody.innerHTML = `<tr><td colspan="9" class="loading">加载失败：${data.message}</td></tr>`;
        }
    } catch (error) {
        console.error('获取用户列表失败:', error);
        userTableBody.innerHTML = '<tr><td colspan="9" class="loading">请求失败，请检查网络</td></tr>';
    }
}
function updatePagination() {
    const totalPages = Math.ceil(totalUsers / pageSize);
    pageInfo.textContent = `第 ${currentPage} 页 / 共 ${totalPages} 页`;

    prevPageBtn.disabled = currentPage <= 1;
    nextPageBtn.disabled = currentPage >= totalPages;
}
function renderTable(users) {
    if (!users || users.length === 0) {
        userTableBody.innerHTML = '<tr><td colspan="9" class="loading">暂无数据</td></tr>';
        return;
    }

    let html = '';
    users.forEach(user => {
        const stateClass = user.state === '1' ? 'state-active' : 'state-disabled';
        const stateText = user.state === '1' ? '活跃' : '禁用';
        const toggleText = user.state === '1' ? '禁用' : '启用';

        html += `
            <tr data-id="${user.id}">
                <td>${user.id}</td>
                <td>${escapeHtml(user.username)}</td>
                <td>${escapeHtml(user.email)}</td>
                <td>${user.user_type === 'admin' ? '管理员' : '普通用户'}</td>
                <td>${user.login_count}</td>
                <td><span class="state-badge ${stateClass}">${stateText}</span></td>
                <td>${formatDateTime(user.created_at)}</td>
                <td>${formatDateTime(user.updated_at)}</td>
                <td>
                    <div class="operation-btns">
                        <button class="btn-toggle" data-id="${user.id}" data-state="${user.state}">${toggleText}</button>
                        <button class="btn-delete" data-id="${user.id}">删除</button>
                    </div>
                </td>
            </tr>
        `;
    });
    userTableBody.innerHTML = html;
    document.querySelectorAll('.btn-toggle').forEach(btn => {
        btn.addEventListener('click', toggleUserState);
    });
    document.querySelectorAll('.btn-delete').forEach(btn => {
        btn.addEventListener('click', deleteUser);
    });
}
function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/[&<>"]/g, function(m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        if (m === '"') return '&quot;';
        return m;
    });
}
function formatDateTime(timestamp) {
    if (!timestamp) return '-';
    const date = new Date(timestamp);
    return date.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).replace(/\//g, '-');
}
async function toggleUserState(e) {
    const btn = e.currentTarget;
    const userId = btn.dataset.id;
    const currentState = btn.dataset.state;
    const newState = currentState === '1' ? '0' : '1';
    const action = newState === '1' ? '启用' : '禁用';

    if (!confirm(`确定要${action}该用户吗？`)) return;

    try {
        const response = await fetch(`/api/admin/users/${userId}/state`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ state: newState })
        });
        const data = await response.json();

        if (data.success) {
            alert(`用户已${action}`);
            // 刷新列表（保持当前查询条件）
            const params = {};
            if (searchUsername.value.trim()) params.username = searchUsername.value.trim();
            if (searchEmail.value.trim()) params.email = searchEmail.value.trim();
            if (searchState.value) params.state = searchState.value;
            await loadUsers(params, currentPage);
        } else {
            alert(`操作失败：${data.message}`);
        }
    } catch (error) {
        console.error('修改状态失败:', error);
        alert('网络错误，请稍后重试');
    }

}
async function deleteUser(e) {
    const btn = e.currentTarget;
    const userId = btn.dataset.id;

    if (!confirm('确定要永久删除该用户吗？此操作不可恢复。')) return;

    try {
        const response = await fetch(`/api/admin/users/${userId}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            alert('用户已删除');
            const params = {};
            if (searchUsername.value.trim()) params.username = searchUsername.value.trim();
            if (searchEmail.value.trim()) params.email = searchEmail.value.trim();
            if (searchState.value) params.state = searchState.value;
            await loadUsers(params, currentPage);
        } else {
            alert(`删除失败：${data.message}`);
        }
    } catch (error) {
        console.error('删除用户失败:', error);
        alert('网络错误，请稍后重试');
    }
}
function performSearch() {
    const params = {};
    if (searchUsername.value.trim()) params.username = searchUsername.value.trim();
    if (searchEmail.value.trim()) params.email = searchEmail.value.trim();
    if (searchState.value) params.state = searchState.value;
    // 重置到第一页
    currentPage = 1;
    loadUsers(params, 1);
}
searchBtn.addEventListener('click', performSearch);
resetBtn.addEventListener('click', () => {
    searchUsername.value = '';
    searchEmail.value = '';
    searchState.value = '';
    currentPage = 1;
    loadUsers({}, 1);
});
prevPageBtn.addEventListener('click', () => {
    if (currentPage > 1) {
        currentPage--;
        const params = {};
        if (searchUsername.value.trim()) params.username = searchUsername.value.trim();
        if (searchEmail.value.trim()) params.email = searchEmail.value.trim();
        if (searchState.value) params.state = searchState.value;
        loadUsers(params, currentPage);
    }
});

nextPageBtn.addEventListener('click', () => {
    const totalPages = Math.ceil(totalUsers / pageSize);
    if (currentPage < totalPages) {
        currentPage++;
        const params = {};
        if (searchUsername.value.trim()) params.username = searchUsername.value.trim();
        if (searchEmail.value.trim()) params.email = searchEmail.value.trim();
        if (searchState.value) params.state = searchState.value;
        loadUsers(params, currentPage);
    }
});
addUserBtn.addEventListener('click', () => {
    modal.classList.add('show');
    addUserForm.reset();
    clearAddFormErrors();
});
closeModal.addEventListener('click', () => {
    modal.classList.remove('show');
});
window.addEventListener('click', (e) => {
    if (e.target === modal) modal.classList.remove('show');
});
function clearAddFormErrors() {
    document.querySelectorAll('#addUserForm .error-message').forEach(el => {
        el.classList.remove('show');
    });
    document.getElementById('addConfirmPasswordSuccess').classList.remove('show');
}
addUserForm.addEventListener('submit', async function(e) {
    e.preventDefault();
    clearAddFormErrors();

    const username = document.getElementById('addUsername').value.trim();
    const password = document.getElementById('addPassword').value.trim();
    const confirmPassword = document.getElementById('addConfirmPassword').value.trim();
    const email = document.getElementById('addEmail').value.trim().toLowerCase();
    const userType = document.getElementById('addUserType').value;
    const state = document.getElementById('addState').value;

    let hasError = false;

    if (!usernameRegex.test(username)) {
        showError('addUsernameError', '用户名只能包含数字和字母');
        hasError = true;
    }

    if (!passwordRegex.test(password) || password.length < 8 || password.length > 20) {
        showError('addPasswordError', '密码格式不正确或长度不在8-20位');
        hasError = true;
    }

    if (password !== confirmPassword) {
        showError('addConfirmPasswordError', '两次密码不一致');
        hasError = true;
    }

    if (!emailRegex.test(email)) {
        showError('addEmailError', '请输入有效的邮箱地址');
        hasError = true;
    }

    if (hasError) return;

    try {
        const response = await fetch('/api/admin/users', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ username, password, email, userType, state })
        });
        const data = await response.json();

        if (data.success) {
            alert('用户添加成功');
            modal.classList.remove('show');
            currentPage = 1;
            await loadUsers({}, 1);
        } else {
            if (data.field === 'username') {
                showError('addUsernameError', data.message);
            } else if (data.field === 'email') {
                showError('addEmailError', data.message);
            } else if (data.field === 'password') {
                showError('addPasswordError', data.message);
            } else {
                alert(data.message);
            }
        }
    } catch (error) {
        console.error('添加用户失败:', error);
        alert('网络错误，请稍后重试');
    }
});

function showError(elementId, message) {
    const el = document.getElementById(elementId);
    el.textContent = message;
    el.classList.add('show');
}
document.getElementById('addConfirmPassword').addEventListener('input', function() {
    const password = document.getElementById('addPassword').value;
    const confirm = this.value;
    const errorEl = document.getElementById('addConfirmPasswordError');
    const successEl = document.getElementById('addConfirmPasswordSuccess');

    errorEl.classList.remove('show');
    successEl.classList.remove('show');

    if (confirm) {
        if (password !== confirm) {
            errorEl.textContent = '两次密码不一致';
            errorEl.classList.add('show');
        } else {
            successEl.classList.add('show');
        }
    }
});
async function logout() {
    if (!confirm('确定要退出登录吗？')) return;
    try {
        const response = await fetch('/api/logout', {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();
        if (data.success) {
            window.location.href = '/login';
        } else {
            alert('退出失败：' + data.message);
        }
    } catch (error) {
        console.error('登出错误:', error);
        alert('网络错误，请稍后重试');
    }
}