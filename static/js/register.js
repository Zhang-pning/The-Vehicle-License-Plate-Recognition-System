const usernameRegex = /^[a-zA-Z0-9]+$/;
const passwordRegex = /^[a-zA-Z0-9!@#$%^&*()_\-+=\[\]{}|\\;:'",.<>/?]+$/;
const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

let countdown = 0;
let countdownTimer = null;

document.getElementById('username').addEventListener('input', function() {
    const username = this.value;
    const errorEl = document.getElementById('usernameError');

    errorEl.classList.remove('show');

    if (username && !usernameRegex.test(username)) {
        errorEl.textContent = '用户名只能包含数字和字母';
        errorEl.classList.add('show');
    }
});
document.getElementById('username').addEventListener('blur', async function() {
    const username = this.value.trim();
    const errorEl = document.getElementById('usernameError');
    const successEl = document.getElementById('usernameSuccess');

    successEl.classList.remove('show');

    if (!username) {
        errorEl.textContent = '请输入用户名';
        errorEl.classList.add('show');
        return;
    }

    if (errorEl.classList.contains('show')) {
        return;
    }

    try {
        errorEl.textContent = '检查中...';
        errorEl.classList.add('show');

        const response = await fetch('/api/check-username', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username })
        });

        const data = await response.json();

        errorEl.classList.remove('show');

        if (data.exists) {
            errorEl.textContent = '用户名已存在';
            errorEl.classList.add('show');
        } else {
            successEl.classList.add('show');
        }
    } catch (error) {
        console.error('检查用户名错误:', error);
        errorEl.textContent = '检查失败，请稍后重试';
        errorEl.classList.add('show');
    }
});
document.getElementById('password').addEventListener('input', function() {
    const password = this.value;
    const errorEl = document.getElementById('passwordError');
    const strengthEl = document.getElementById('passwordStrength');
    const strengthBar = document.getElementById('strengthBar');
    const strengthText = document.getElementById('strengthText');

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

    if (document.getElementById('confirmPassword').value) {
        checkPasswordMatch();
    }
});

document.getElementById('confirmPassword').addEventListener('input', checkPasswordMatch);

function checkPasswordMatch() {
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    const errorEl = document.getElementById('confirmPasswordError');
    const successEl = document.getElementById('confirmPasswordSuccess');

    errorEl.classList.remove('show');
    successEl.classList.remove('show');

    if (confirmPassword) {
        if (password !== confirmPassword) {
            errorEl.textContent = '两次密码不一致';
            errorEl.classList.add('show');
        } else {
            successEl.classList.add('show');
        }
    }
}

document.getElementById('userType').addEventListener('change', function() {
    const adminKeyGroup = document.getElementById('adminKeyGroup');
    const adminKey = document.getElementById('adminKey');

    if (this.value === 'admin') {
        adminKeyGroup.classList.add('show');
        adminKey.required = true;
    } else {
        adminKeyGroup.classList.remove('show');
        adminKey.required = false;
        adminKey.value = '';
    }
});

document.getElementById('email').addEventListener('blur', async function() {
    const email = this.value.trim().toLowerCase();
    const errorEl = document.getElementById('emailError');
    const successEl = document.getElementById('emailSuccess');

    errorEl.classList.remove('show');
    successEl.classList.remove('show');

    if (!email) return;

    if (!emailRegex.test(email)) {
        errorEl.textContent = '请输入有效的邮箱地址';
        errorEl.classList.add('show');
        return;
    }

    try {
        const response = await fetch('/api/check-email', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email })
        });

        const data = await response.json();

        if (data.exists) {
            errorEl.textContent = '该邮箱已被注册';
            errorEl.classList.add('show');
        } else {
            successEl.classList.add('show');
        }
    } catch (error) {
        console.error('检查邮箱错误:', error);
    }
});

document.getElementById('sendCodeBtn').addEventListener('click', async function() {
    const btn = this;
    const email = document.getElementById('email').value.trim().toLowerCase();
    const errorEl = document.getElementById('emailError');

    btn.disabled = true;

    errorEl.classList.remove('show');

    if (!email) {
        errorEl.textContent = '请先输入邮箱地址';
        errorEl.classList.add('show');
        btn.disabled = false;
        return;
    }

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
            alert('验证码已发送到您的邮箱，请注意查收');
            startCountdown();
        } else {
            errorEl.textContent = data.message;
            errorEl.classList.add('show');
            btn.disabled = false;
        }
    } catch (error) {
        console.error('发送验证码错误:', error);
        errorEl.textContent = '验证码发送失败，请稍后重试';
        errorEl.classList.add('show');
        btn.disabled = false;
    }
});

function startCountdown() {
    countdown = 60;
    const btn = document.getElementById('sendCodeBtn');
    btn.disabled = true;

    countdownTimer = setInterval(() => {
        countdown--;
        btn.textContent = countdown + 's 后重发';

        if (countdown <= 0) {
            clearInterval(countdownTimer);
            btn.disabled = false;
            btn.textContent = '获取验证码';
        }
    }, 1000);
}

document.getElementById('registerForm').addEventListener('submit', async function(e) {
    e.preventDefault();

    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value.trim();
    const confirmPassword = document.getElementById('confirmPassword').value.trim();
    const userType = document.getElementById('userType').value;
    const adminKey = document.getElementById('adminKey').value.trim();
    const email = document.getElementById('email').value.trim().toLowerCase();
    const code = document.getElementById('verificationCode').value.trim();
    const agreeTerms = document.getElementById('agreeTerms').checked;

    document.querySelectorAll('.error-message').forEach(el => {
        el.classList.remove('show');
    });

    let hasError = false;

    if (!usernameRegex.test(username)) {
        document.getElementById('usernameError').textContent = '用户名只能包含数字和字母';
        document.getElementById('usernameError').classList.add('show');
        hasError = true;
    }

    if (!passwordRegex.test(password)) {
        document.getElementById('passwordError').textContent = '密码格式不正确';
        document.getElementById('passwordError').classList.add('show');
        hasError = true;
    }

    if (password.length < 8 || password.length > 20) {
        document.getElementById('passwordError').textContent = '密码长度应为8-20位';
        document.getElementById('passwordError').classList.add('show');
        hasError = true;
    }

    if (password !== confirmPassword) {
        document.getElementById('confirmPasswordError').textContent = '两次密码不一致';
        document.getElementById('confirmPasswordError').classList.add('show');
        hasError = true;
    }

    if (userType === 'admin' && !adminKey) {
        document.getElementById('adminKeyError').textContent = '请输入管理密钥';
        document.getElementById('adminKeyError').classList.add('show');
        hasError = true;
    }

    if (!emailRegex.test(email)) {
        document.getElementById('emailError').textContent = '请输入有效的邮箱地址';
        document.getElementById('emailError').classList.add('show');
        hasError = true;
    }

    if (!code) {
        document.getElementById('codeError').textContent = '请输入验证码';
        document.getElementById('codeError').classList.add('show');
        hasError = true;
    }

    if (!agreeTerms) {
        alert('请阅读并同意用户协议和隐私政策');
        hasError = true;
    }

    if (hasError) return;

    try {
        const response = await fetch('/api/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username,
                password,
                userType,
                adminKey,
                email,
                code
            })
        });

        const data = await response.json();

        if (data.success) {
            alert('注册成功！即将跳转到登录页面');
            setTimeout(() => {
                window.location.href = '/login';
            }, 1000);
        } else {
            if (data.message.includes('用户名')) {
                document.getElementById('usernameError').textContent = data.message;
                document.getElementById('usernameError').classList.add('show');
            } else if (data.message.includes('密码')) {
                document.getElementById('passwordError').textContent = data.message;
                document.getElementById('passwordError').classList.add('show');
            } else if (data.message.includes('邮箱')) {
                document.getElementById('emailError').textContent = data.message;
                document.getElementById('emailError').classList.add('show');
            } else if (data.message.includes('验证码')) {
                document.getElementById('codeError').textContent = data.message;
                document.getElementById('codeError').classList.add('show');
            } else if (data.message.includes('管理密钥')) {
                document.getElementById('adminKeyError').textContent = data.message;
                document.getElementById('adminKeyError').classList.add('show');
            } else {
                alert(data.message);
            }
        }
    } catch (error) {
        console.error('注册错误:', error);
        alert('注册失败，请稍后重试');
    }
});

window.addEventListener('beforeunload', function() {
    if (countdownTimer) {
        clearInterval(countdownTimer);
    }
});