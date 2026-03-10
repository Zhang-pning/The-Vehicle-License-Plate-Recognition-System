const usernameRegex = /^[a-zA-Z0-9]+$/;
const passwordRegex = /^[a-zA-Z0-9!@#$%^&*()_\-+=\[\]{}|\\;:'",.<>/?]+$/;
const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

let currentEmail = '';
let countdownTimer = null;

document.getElementById('loginForm').addEventListener('submit', async function(e) {
    e.preventDefault();

    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    document.getElementById('usernameError').classList.remove('show');
    document.getElementById('passwordError').classList.remove('show');
    document.getElementById('loginError').classList.remove('show');

    if (username.includes('@')) {
        if (!emailRegex.test(username)) {
            document.getElementById('usernameError').textContent = '请输入有效的邮箱地址';
            document.getElementById('usernameError').classList.add('show');
            return;
        }
    } else {
        if (!usernameRegex.test(username)) {
            document.getElementById('usernameError').textContent = '用户名只能包含数字和字母';
            document.getElementById('usernameError').classList.add('show');
            return;
        }
    }

    if (!passwordRegex.test(password)) {
        document.getElementById('passwordError').textContent = '密码格式不正确';
        document.getElementById('passwordError').classList.add('show');
        return;
    }

    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (data.success) {
            alert('登录成功！');
            if (data.user.user_type === 'admin') {
                window.location.href = '/managerment';
            } else {
                window.location.href = '/parking';
            }
        } else {
            document.getElementById('loginError').textContent = data.message || '账号或密码错误';
            document.getElementById('loginError').classList.add('show');
        }
    } catch (error) {
        console.error('登录错误:', error);
        document.getElementById('loginError').textContent = '登录失败，请稍后重试';
        document.getElementById('loginError').classList.add('show');
    }
});
const modal = document.getElementById('forgotPasswordModal');
const forgotLink = document.getElementById('forgotPasswordLink');
const closeBtn = document.querySelector('.close');

forgotLink.addEventListener('click', function(e) {
    e.preventDefault();
    modal.classList.add('show');
});

closeBtn.addEventListener('click', function() {
    modal.classList.remove('show');
    resetModal();
});

window.addEventListener('click', function(e) {
    if (e.target === modal) {
        modal.classList.remove('show');
        resetModal();
    }
});
document.getElementById('sendCodeBtn').addEventListener('click', async function() {
    const btn = this; // 保存按钮引用
    const email = document.getElementById('resetEmail').value.trim().toLowerCase();
    const errorEl = document.getElementById('resetEmailError');

    btn.disabled = true;

    errorEl.classList.remove('show');

    if (!emailRegex.test(email)) {
        errorEl.textContent = '请输入有效的邮箱地址';
        errorEl.classList.add('show');
        btn.disabled = false;
        return;
    }

    try {
        const response = await fetch('/api/send-code', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email })
        });

        const data = await response.json();

        if (data.success) {
            currentEmail = email;
            alert('验证码已发送到您的邮箱');
            showStep(2);
            startCountdown();
        } else {
            errorEl.textContent = data.message;
            errorEl.classList.add('show');
            btn.disabled = false;
        }
    } catch (error) {
        console.error('发送验证码错误:', error);
        errorEl.textContent = '发送失败，请稍后重试';
        errorEl.classList.add('show');
        btn.disabled = false;
    }
});
document.getElementById('verifyCodeBtn').addEventListener('click', async function() {
    const code = document.getElementById('verifyCode').value.trim();

    document.getElementById('verifyCodeError').classList.remove('show');

    if (!code) {
        document.getElementById('verifyCodeError').textContent = '请输入验证码';
        document.getElementById('verifyCodeError').classList.add('show');
        return;
    }

    try {
        const response = await fetch('/api/forgot-password/verify', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email: currentEmail, code })
        });

        const data = await response.json();

        if (data.success) {
            document.getElementById('successMsg').classList.add('show');
            showStep(3);
        } else {
            document.getElementById('verifyCodeError').textContent = data.message;
            document.getElementById('verifyCodeError').classList.add('show');
        }
    } catch (error) {
        console.error('验证验证码错误:', error);
        document.getElementById('verifyCodeError').textContent = '验证失败，请稍后重试';
        document.getElementById('verifyCodeError').classList.add('show');
    }
});
document.getElementById('backToStep1').addEventListener('click', function() {
    clearCountdown();
    showStep(1);
});
document.getElementById('resetPasswordBtn').addEventListener('click', async function() {
    const newPassword = document.getElementById('newPassword').value.trim();
    const confirmPassword = document.getElementById('confirmNewPassword').value.trim();
    const code = document.getElementById('verifyCode').value.trim();

    document.getElementById('newPasswordError').classList.remove('show');
    document.getElementById('confirmNewPasswordError').classList.remove('show');

    if (!passwordRegex.test(newPassword)) {
        document.getElementById('newPasswordError').textContent = '密码格式不正确';
        document.getElementById('newPasswordError').classList.add('show');
        return;
    }

    if (newPassword.length < 8 || newPassword.length > 20) {
        document.getElementById('newPasswordError').textContent = '密码长度应为8-20位';
        document.getElementById('newPasswordError').classList.add('show');
        return;
    }

    if (newPassword !== confirmPassword) {
        document.getElementById('confirmNewPasswordError').textContent = '两次密码不一致';
        document.getElementById('confirmNewPasswordError').classList.add('show');
        return;
    }

    try {
        const response = await fetch('/api/forgot-password/reset', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                email: currentEmail,
                code: code,
                newPassword: newPassword
            })
        });

        const data = await response.json();

        if (data.success) {
            alert('密码重置成功，即将跳转到登录页面');
            modal.classList.remove('show');
            resetModal();
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            document.getElementById('newPasswordError').textContent = data.message;
            document.getElementById('newPasswordError').classList.add('show');
        }
    } catch (error) {
        console.error('重置密码错误:', error);
        document.getElementById('newPasswordError').textContent = '重置失败，请稍后重试';
        document.getElementById('newPasswordError').classList.add('show');
    }
});

function showStep(stepNumber) {
    document.querySelectorAll('.step').forEach(step => {
        step.classList.remove('active');
    });
    document.getElementById('step' + stepNumber).classList.add('active');
}
function resetModal() {
    showStep(1);
    currentEmail = '';
    document.getElementById('resetEmail').value = '';
    document.getElementById('verifyCode').value = '';
    document.getElementById('newPassword').value = '';
    document.getElementById('confirmNewPassword').value = '';
    document.querySelectorAll('.error-message').forEach(msg => {
        msg.classList.remove('show');
    });
    document.getElementById('successMsg').classList.remove('show');
    clearCountdown();
}
function startCountdown() {
    const btn = document.getElementById('sendCodeBtn');
    let countdown = 60;
    btn.disabled = true;
    btn.textContent = countdown + 's 后重发';

    countdownTimer = setInterval(() => {
        countdown--;
        btn.textContent = countdown + 's 后重发';
        if (countdown <= 0) {
            clearInterval(countdownTimer);
            countdownTimer = null;
            btn.disabled = false;
            btn.textContent = '发送验证码';
        }
    }, 1000);
}
function clearCountdown() {
    if (countdownTimer) {
        clearInterval(countdownTimer);
        countdownTimer = null;
    }
    const btn = document.getElementById('sendCodeBtn');
    btn.disabled = false;
    btn.textContent = '发送验证码';
}
document.getElementById('newPassword').addEventListener('input', function() {
    const password = this.value;
    const errorEl = document.getElementById('newPasswordError');
    const strengthEl = document.getElementById('newPasswordStrength');
    const strengthBar = document.getElementById('newStrengthBar');
    const strengthText = document.getElementById('newStrengthText');

    errorEl.classList.remove('show');

    if (password) {
        strengthEl.style.display = 'block';

        if (!passwordRegex.test(password)) {
            errorEl.textContent = '密码包含不允许的字符';
            errorEl.classList.add('show');
            strengthEl.style.display = 'none';
            return;
        }

        let strength = 0;
        if (password.length >= 8) strength++;
        if (password.length >= 12) strength++;
        if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength++;
        if (/\d/.test(password)) strength++;
        if (/[!@#$%^&*()_\-+=\[\]{}|\\;:'",.<>/?]/.test(password)) strength++;

        strengthBar.className = 'strength-bar-fill';
        if (strength <= 2) {
            strengthBar.classList.add('strength-weak');
            strengthText.textContent = '弱';
            strengthText.style.color = '#ff6666';
        } else if (strength <= 4) {
            strengthBar.classList.add('strength-medium');
            strengthText.textContent = '中';
            strengthText.style.color = '#ffaa66';
        } else {
            strengthBar.classList.add('strength-strong');
            strengthText.textContent = '强';
            strengthText.style.color = '#66ff66';
        }
    } else {
        strengthEl.style.display = 'none';
    }

    if (document.getElementById('confirmNewPassword').value) {
        checkNewPasswordMatch();
    }
});

document.getElementById('confirmNewPassword').addEventListener('input', checkNewPasswordMatch);

function checkNewPasswordMatch() {
    const newPassword = document.getElementById('newPassword').value;
    const confirmNewPassword = document.getElementById('confirmNewPassword').value;
    const errorEl = document.getElementById('confirmNewPasswordError');
    const successEl = document.getElementById('confirmNewPwdSuccess');

    errorEl.classList.remove('show');
    successEl.classList.remove('show');

    if (confirmNewPassword) {
        if (newPassword !== confirmNewPassword) {
            errorEl.textContent = '两次密码不一致';
            errorEl.classList.add('show');
        } else {
            successEl.classList.add('show');
        }
    }
}
window.addEventListener('beforeunload', function() {
    if (countdownTimer) {
        clearInterval(countdownTimer);
    }
});