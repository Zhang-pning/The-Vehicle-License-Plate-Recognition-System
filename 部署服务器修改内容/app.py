import base64
import os
import random
import re
from datetime import datetime, timedelta
from functools import wraps

import cv2
import torch
from flask import Flask, render_template, request, jsonify, session, redirect
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash

# 替换 flask-mysqldb 为原生 pymysql
import pymysql
from pymysql.cursors import DictCursor  # 保证返回字典格式

from config import Config
from plate_recognition import PlateRecognizer

recognizer = None
app = Flask(__name__)
app.config.from_object(Config)

# ==================== 替换 flask-mysqldb 的核心配置 ====================
# 1. 从配置中读取数据库信息（兼容原有 Config 配置）
DB_CONFIG = {
    'host': app.config.get('MYSQL_HOST', 'localhost'),
    'user': app.config.get('MYSQL_USER', 'Jack'),
    'password': app.config.get('MYSQL_PASSWORD', '######'),
    'database': app.config.get('MYSQL_DB', 'user_management'),
    'charset': app.config.get('MYSQL_CHARSET', 'utf8mb4'),
    'cursorclass': DictCursor  # 关键：返回字典格式，和 flask-mysqldb 一致
}

# 2. 封装数据库连接函数（替代 flask-mysqldb 的 MySQL 类）
def get_db_connection():
    """获取数据库连接（替代 mysql.connection）"""
    conn = pymysql.connect(**DB_CONFIG)
    # 保持和原有逻辑一致的自动提交（可选，根据业务调整）
    conn.autocommit(False)  # flask-mysqldb 默认关闭自动提交
    return conn

# 3. 兼容原有 mysql.connection.cursor() 写法的快捷函数
def get_db_cursor():
    """获取数据库游标（简化代码）"""
    conn = get_db_connection()
    return conn, conn.cursor()

# ==================== 原有配置保留 ====================
# 初始化邮件（无需修改）
mail = Mail(app)

# 正则表达式验证
USERNAME_REGEX = re.compile(r'^[a-zA-Z0-9]+$')
PASSWORD_REGEX = re.compile(r'^[a-zA-Z0-9!@#$%^&*()_\-+=\[\]{}|\\;:\'",.<>/?]+$')
EMAIL_REGEX = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')

# 管理员密钥（应该从环境变量或配置文件读取）
ADMIN_KEY = "Zhangkun*0914"  # 请修改为你的管理员密钥


def login_required(required_type=None):
    #登录验证装饰器
    #:param required_type: 可选，指定需要的用户类型，如 'admin'
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect('/')
            # 如果需要检查用户类型
            if required_type and session.get('user_type') != required_type:
                # 权限不足，可以返回403页面或重定向
                return "权限不足", 403
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def load_recognition_models():
    global recognizer
    try:
        detector_weights = 'weights/YOLOv5_weight/yolov5_best.pt'
        detector_hyp = 'data/hyp.yaml'
        detector_data = 'data/ccpd_datasets.yaml'
        recognizer_weights = 'weights/LPRNet_weight/lprnet_best.pth'
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        recognizer = PlateRecognizer(detector_weights, detector_hyp, detector_data, recognizer_weights, device)
        print("车牌识别模型加载成功")
    except Exception as e:
        print(f"车牌识别模型加载失败: {e}")
        recognizer = None


# 在应用上下文加载后执行
with app.app_context():
    load_recognition_models()


# ==================== 路由 ====================
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login')
def login_page():
    return render_template('login.html')


@app.route('/register')
def register_page():
    return render_template('register.html')


@app.route('/parking')
@login_required(required_type='normal')
def parking_page():
    username = session.get('username', '用户')
    return render_template('parking.html', username=username)


@app.route('/managerment')
@login_required(required_type='admin')
def managerment_page():
    username = session.get('username', '用户')
    return render_template('managerment.html', username=username)


# ==================== API端点 ====================
@app.route('/api/register', methods=['POST'])
def register():
    """用户注册"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        user_type = data.get('userType', 'normal')
        admin_key = data.get('adminKey', '').strip()
        email = data.get('email', '').strip().lower()
        code = data.get('code', '').strip()

        # 验证必填字段
        if not all([username, password, email, code]):
            return jsonify({'success': False, 'message': '请填写所有必填字段'}), 400

        # 验证用户名格式
        if not USERNAME_REGEX.match(username):
            return jsonify({'success': False, 'message': '用户名只能包含数字和字母'}), 400

        # 验证密码格式
        if not PASSWORD_REGEX.match(password):
            return jsonify({'success': False, 'message': '密码格式不正确'}), 400

        if len(password) < 8 or len(password) > 20:
            return jsonify({'success': False, 'message': '密码长度应为8-20位'}), 400

        # 验证邮箱格式
        if not EMAIL_REGEX.match(email):
            return jsonify({'success': False, 'message': '邮箱格式不正确'}), 400

        # 如果是管理员，验证管理密钥
        if user_type == 'admin':
            if admin_key != ADMIN_KEY:
                return jsonify({'success': False, 'message': '管理密钥错误'}), 400

        # 替换：使用原生 pymysql 连接
        conn = get_db_connection()
        cur = conn.cursor()

        try:
            # 检查用户名是否已存在
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cur.fetchone():
                return jsonify({'success': False, 'message': '用户名已存在'}), 400

            # 检查邮箱是否已注册
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                return jsonify({'success': False, 'message': '该邮箱已被注册'}), 400

            # 验证验证码
            cur.execute(
                "SELECT code, expired_at FROM verification_codes WHERE email = %s ORDER BY created_at DESC LIMIT 1",
                (email,)
            )
            code_record = cur.fetchone()

            if not code_record:
                return jsonify({'success': False, 'message': '请先获取验证码'}), 400

            stored_code = code_record['code']
            expired_at = code_record['expired_at']

            # 检查验证码是否过期
            if datetime.now() > expired_at:
                return jsonify({'success': False, 'message': '验证码已过期，请重新获取'}), 400

            # 检查验证码是否正确（严格区分大小写）
            if code != stored_code:
                return jsonify({'success': False, 'message': '验证码错误'}), 400

            # 密码加密
            hashed_password = generate_password_hash(password)

            # 插入用户数据
            cur.execute(
                "INSERT INTO users (username, password, email, user_type, state) VALUES (%s, %s, %s, %s, %s)",
                (username, hashed_password, email, user_type, '1')
            )

            # 删除已使用的验证码
            cur.execute("DELETE FROM verification_codes WHERE email = %s", (email,))

            # 提交事务（替代 mysql.connection.commit()）
            conn.commit()

            return jsonify({'success': True, 'message': '注册成功'}), 200
        finally:
            # 关闭游标和连接
            cur.close()
            conn.close()

    except Exception as e:
        print(f"注册错误: {str(e)}")
        return jsonify({'success': False, 'message': '注册失败，请稍后重试'}), 500


@app.route('/api/login', methods=['POST'])
def login():
    """用户登录（支持用户名或邮箱）"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        if not username or not password:
            return jsonify({'success': False, 'message': '请输入用户名和密码'}), 400

        # 替换：原生 pymysql 连接
        conn = get_db_connection()
        cur = conn.cursor()

        try:
            # 修改查询：同时匹配用户名或邮箱（邮箱忽略大小写）
            cur.execute("""
                SELECT id, username, password, user_type, state
                FROM users
                WHERE username = %s OR LOWER(email) = LOWER(%s)
            """, (username, username))
            user = cur.fetchone()

            if not user:
                return jsonify({'success': False, 'message': '账号或密码错误'}), 401

            # 验证密码
            if not check_password_hash(user['password'], password):
                return jsonify({'success': False, 'message': '账号或密码错误'}), 401
            # 检查用户状态
            if user['state'] == '0':
                return jsonify({'success': False, 'message': '账号已被禁用，请联系管理员'}), 403

            # 更新登录次数
            try:
                cur.execute("UPDATE users SET login_count = login_count + 1 WHERE id = %s", (user['id'],))
                conn.commit()
            except Exception as e:
                # 记录错误但不中断登录（仅打印日志）
                print(f"更新登录次数失败（用户ID: {user['id']}）: {e}")

            # 设置session
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['user_type'] = user['user_type']

            return jsonify({
                'success': True,
                'message': '登录成功',
                'user': {
                    'username': user['username'],
                    'user_type': user['user_type']
                }
            }), 200
        finally:
            cur.close()
            conn.close()

    except Exception as e:
        print(f"登录错误: {str(e)}")
        return jsonify({'success': False, 'message': '登录失败，请稍后重试'}), 500


@app.route('/api/send-code', methods=['POST'])
def send_code():
    """发送验证码"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()

        if not email:
            return jsonify({'success': False, 'message': '请输入邮箱地址'}), 400

        if not EMAIL_REGEX.match(email):
            return jsonify({'success': False, 'message': '邮箱格式不正确'}), 400

        # 生成验证码
        code = ''.join(random.choices(Config.ALLOWED_CHARS, k=Config.VERIFICATION_CODE_LENGTH))

        # 计算过期时间
        expired_at = datetime.now() + timedelta(minutes=Config.CODE_VALID_MINUTES)

        # 替换：原生 pymysql 保存验证码
        conn = get_db_connection()
        cur = conn.cursor()

        try:
            cur.execute(
                "INSERT INTO verification_codes (email, code, expired_at) VALUES (%s, %s, %s)",
                (email, code, expired_at)
            )
            conn.commit()

            # 发送邮件（原有逻辑不变）
            msg = Message(
                subject='车牌识别系统 - 验证码',
                sender=app.config['MAIL_USERNAME'],
                recipients=[email]
            )
            msg.html = f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: 'Segoe UI', 'Arial', sans-serif;
            line-height: 1.6;
            color: #e0e0e0;
            background-color: #050505;
            max-width: 600px;
            margin: 0 auto;
            padding: 30px 20px;
        }}
        .header {{
            text-align: center;
            border-bottom: 2px solid rgba(0, 242, 96, 0.3);
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            font-size: 28px;
            font-weight: 300;
            letter-spacing: 4px;
            background: linear-gradient(90deg, #00f260, #0575e6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            text-transform: uppercase;
            margin: 0;
        }}
        .code-container {{
            background: transparent;
            border: 2px solid #00f260;
            border-radius: 2px;
            padding: 30px;
            text-align: center;
            margin: 35px 0;
            font-size: 42px;
            font-weight: 300;
            letter-spacing: 10px;
            color: #00f260;
            box-shadow: 0 0 20px rgba(0, 242, 96, 0.8), 0 0 40px rgba(5, 117, 230, 0.6);
            transition: all 0.3s ease;
        }}
        .note {{
            background: transparent;
            border: 1px solid rgba(0, 242, 96, 0.7);
            border-radius: 2px;
            padding: 20px;
            margin: 25px 0;
            color: #ccc;
        }}
        .note strong {{
            color: #00f260;
            font-weight: 400;
            letter-spacing: 1px;
        }}
        .note ul {{
            margin-top: 10px;
            padding-left: 20px;
        }}
        .note li {{
            margin: 8px 0;
            color: #aaa;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid rgba(0, 242, 96, 0.3);
            font-size: 12px;
            color: rgba(255, 255, 255, 0.4);
            text-align: center;
        }}
        p {{
            color: #ccc;
        }}
        a {{
            color: #00f260;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>邮箱验证</h1>
    </div>

    <p>您好！</p>
    <p>感谢您注册车牌识别系统。请使用以下验证码完成注册：</p>

    <div class="code-container">
        {code}
    </div>

    <div class="note">
        <strong>温馨提示：</strong>
        <ul>
            <li>此验证码 <strong style="color:#00f260;">{Config.CODE_VALID_MINUTES}分钟</strong> 内有效</li>
            <li>请勿将验证码泄露给他人</li>
            <li>验证码严格区分大小写</li>
        </ul>
    </div>

    <p>如果这不是您的操作，请忽略此邮件。</p>

    <div class="footer">
        <p>此邮件由系统自动发送，请勿回复</p>
        <p>&copy; 2026 车牌识别系统. 保留所有权利.</p>
    </div>
</body>
</html>
'''
            mail.send(msg)

            return jsonify({'success': True, 'message': '验证码已发送到您的邮箱'}), 200
        finally:
            cur.close()
            conn.close()

    except Exception as e:
        print(f"发送验证码错误: {str(e)}")
        return jsonify({'success': False, 'message': '验证码发送失败，请稍后重试'}), 500


@app.route('/api/check-email', methods=['POST'])
def check_email():
    """检查邮箱是否已注册"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()

        if not email:
            return jsonify({'success': False, 'message': '请输入邮箱地址'}), 400

        if not EMAIL_REGEX.match(email):
            return jsonify({'success': False, 'message': '邮箱格式不正确'}), 400

        # 替换：原生 pymysql 查询
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            return jsonify({'success': False, 'message': '该邮箱已被注册', 'exists': True}), 200
        else:
            return jsonify({'success': True, 'message': '该邮箱可以使用', 'exists': False}), 200

    except Exception as e:
        print(f"检查邮箱错误: {str(e)}")
        return jsonify({'success': False, 'message': '检查失败，请稍后重试'}), 500


@app.route('/api/check-username', methods=['POST'])
def check_username():
    """检查用户名是否已存在"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()

        if not username:
            return jsonify({'success': False, 'message': '请输入用户名'}), 400

        # 替换：原生 pymysql 查询
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            return jsonify({'success': False, 'message': '用户名已存在', 'exists': True}), 200
        else:
            return jsonify({'success': True, 'message': '用户名可以使用', 'exists': False}), 200

    except Exception as e:
        print(f"检查用户名错误: {str(e)}")
        return jsonify({'success': False, 'message': '检查失败，请稍后重试'}), 500


@app.route('/api/forgot-password/verify', methods=['POST'])
def forgot_password_verify():
    """忘记密码 - 验证验证码"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        code = data.get('code', '').strip()

        if not email or not code:
            return jsonify({'success': False, 'message': '请输入邮箱和验证码'}), 400

        # 替换：原生 pymysql 查询
        conn = get_db_connection()
        cur = conn.cursor()

        # 检查邮箱是否存在
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        user = cur.fetchone()

        if not user:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': '该邮箱未注册'}), 400

        # 验证验证码
        cur.execute(
            "SELECT code, expired_at FROM verification_codes WHERE email = %s ORDER BY created_at DESC LIMIT 1",
            (email,)
        )
        code_record = cur.fetchone()
        cur.close()
        conn.close()

        if not code_record:
            return jsonify({'success': False, 'message': '请先获取验证码'}), 400

        stored_code = code_record['code']
        expired_at = code_record['expired_at']

        if datetime.now() > expired_at:
            return jsonify({'success': False, 'message': '验证码已过期，请重新获取'}), 400

        if code != stored_code:
            return jsonify({'success': False, 'message': '验证码错误'}), 400

        return jsonify({'success': True, 'message': '验证成功'}), 200

    except Exception as e:
        print(f"验证验证码错误: {str(e)}")
        return jsonify({'success': False, 'message': '验证失败，请稍后重试'}), 500


@app.route('/api/forgot-password/reset', methods=['POST'])
def forgot_password_reset():
    """忘记密码 - 重置密码"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        code = data.get('code', '').strip()
        new_password = data.get('newPassword', '').strip()

        if not all([email, code, new_password]):
            return jsonify({'success': False, 'message': '请填写所有必填字段'}), 400

        # 验证密码格式
        if not PASSWORD_REGEX.match(new_password):
            return jsonify({'success': False, 'message': '密码格式不正确'}), 400

        if len(new_password) < 8 or len(new_password) > 20:
            return jsonify({'success': False, 'message': '密码长度应为8-20位'}), 400

        # 替换：原生 pymysql 操作
        conn = get_db_connection()
        cur = conn.cursor()

        try:
            # 再次验证验证码
            cur.execute(
                "SELECT code, expired_at FROM verification_codes WHERE email = %s ORDER BY created_at DESC LIMIT 1",
                (email,)
            )
            code_record = cur.fetchone()

            if not code_record or code != code_record['code'] or datetime.now() > code_record['expired_at']:
                return jsonify({'success': False, 'message': '验证码无效或已过期'}), 400

            # 更新密码
            hashed_password = generate_password_hash(new_password)
            cur.execute("UPDATE users SET password = %s WHERE email = %s", (hashed_password, email))

            # 删除已使用的验证码
            cur.execute("DELETE FROM verification_codes WHERE email = %s", (email,))

            conn.commit()
            return jsonify({'success': True, 'message': '密码重置成功'}), 200
        finally:
            cur.close()
            conn.close()

    except Exception as e:
        print(f"重置密码错误: {str(e)}")
        return jsonify({'success': False, 'message': '重置失败，请稍后重试'}), 500


# ==================== 管理员 API（需登录且为管理员） ====================
@app.route('/api/admin/users', methods=['GET'])
@login_required(required_type='admin')
def admin_get_users():
    """获取用户列表，支持分页和过滤"""
    try:
        # 获取查询参数
        username = request.args.get('username', '')
        email = request.args.get('email', '')
        state = request.args.get('state', '')
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 15, type=int)

        # 确保 page 和 limit 为正整数
        if page < 1: page = 1
        if limit < 1: limit = 15

        # 替换：原生 pymysql 操作
        conn = get_db_connection()
        cur = conn.cursor()

        # 构建基础查询
        base_query = "FROM users WHERE 1=1"
        params = []

        if username:
            base_query += " AND username LIKE %s"
            params.append(f'%{username}%')
        if email:
            base_query += " AND email LIKE %s"
            params.append(f'%{email}%')
        if state in ('0', '1'):
            base_query += " AND state = %s"
            params.append(state)

        # 获取总记录数
        cur.execute(f"SELECT COUNT(*) as total {base_query}", params)
        total = cur.fetchone()['total']

        # 获取分页数据
        offset = (page - 1) * limit
        query = f"""
            SELECT id, username, email, user_type, login_count, state, created_at, updated_at
            {base_query}
            ORDER BY id DESC
            LIMIT %s OFFSET %s
        """
        cur.execute(query, params + [limit, offset])
        users = cur.fetchall()
        cur.close()
        conn.close()

        # 转换日期字段为 ISO 格式
        user_list = []
        for user in users:
            user_dict = dict(user)
            user_dict['created_at'] = user_dict['created_at'].isoformat() if user_dict['created_at'] else None
            user_dict['updated_at'] = user_dict['updated_at'].isoformat() if user_dict['updated_at'] else None
            user_list.append(user_dict)

        return jsonify({
            'success': True,
            'users': user_list,
            'total': total,
            'page': page,
            'limit': limit
        }), 200

    except Exception as e:
        print(f"获取用户列表错误: {str(e)}")
        return jsonify({'success': False, 'message': '获取用户列表失败'}), 500


@app.route('/api/admin/users/<int:user_id>/state', methods=['PUT'])
@login_required(required_type='admin')
def admin_update_user_state(user_id):
    """切换用户状态（禁用/启用）"""
    try:
        data = request.get_json()
        new_state = data.get('state')
        if new_state not in ('0', '1'):
            return jsonify({'success': False, 'message': '无效的状态值'}), 400

        # 禁止管理员修改自己的状态
        if user_id == session.get('user_id'):
            return jsonify({'success': False, 'message': '不能修改当前登录账号的状态'}), 400

        # 替换：原生 pymysql 操作
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET state = %s WHERE id = %s", (new_state, user_id))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({'success': True, 'message': '状态更新成功'}), 200

    except Exception as e:
        print(f"更新用户状态错误: {str(e)}")
        return jsonify({'success': False, 'message': '更新失败'}), 500


@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@login_required(required_type='admin')
def admin_delete_user(user_id):
    """删除指定用户"""
    try:
        # 禁止管理员删除自己
        if user_id == session.get('user_id'):
            return jsonify({'success': False, 'message': '不能删除当前登录的管理员账号'}), 400

        # 替换：原生 pymysql 操作
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({'success': True, 'message': '用户已删除'}), 200

    except Exception as e:
        print(f"删除用户错误: {str(e)}")
        return jsonify({'success': False, 'message': '删除失败'}), 500


@app.route('/api/admin/users', methods=['POST'])
@login_required(required_type='admin')
def admin_add_user():
    """新增用户（由管理员创建）"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        email = data.get('email', '').strip().lower()
        user_type = data.get('userType')  # 注意前端字段名为 userType
        state = data.get('state')  # '0' 或 '1'

        # 必填字段校验
        if not all([username, password, email, user_type, state]):
            return jsonify({'success': False, 'message': '缺少必要字段'}), 400

        # 格式校验
        if not USERNAME_REGEX.match(username):
            return jsonify({'success': False, 'field': 'username', 'message': '用户名只能包含数字和字母'}), 400

        if not PASSWORD_REGEX.match(password) or not (8 <= len(password) <= 20):
            return jsonify({'success': False, 'field': 'password', 'message': '密码格式不正确或长度不在8-20位'}), 400

        if not EMAIL_REGEX.match(email):
            return jsonify({'success': False, 'field': 'email', 'message': '邮箱格式不正确'}), 400

        if user_type not in ('normal', 'admin'):
            return jsonify({'success': False, 'field': 'userType', 'message': '用户类型无效'}), 400

        if state not in ('0', '1'):
            return jsonify({'success': False, 'field': 'state', 'message': '状态无效'}), 400

        # 替换：原生 pymysql 操作
        conn = get_db_connection()
        cur = conn.cursor()

        try:
            # 检查用户名是否已存在
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cur.fetchone():
                return jsonify({'success': False, 'field': 'username', 'message': '用户名已存在'}), 400

            # 检查邮箱是否已存在
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                return jsonify({'success': False, 'field': 'email', 'message': '邮箱已被注册'}), 400

            # 密码加密
            hashed_password = generate_password_hash(password)

            # 插入新用户
            cur.execute("""
                INSERT INTO users (username, password, email, user_type, state)
                VALUES (%s, %s, %s, %s, %s)
            """, (username, hashed_password, email, user_type, state))

            conn.commit()
            return jsonify({'success': True, 'message': '用户添加成功'}), 200
        finally:
            cur.close()
            conn.close()

    except Exception as e:
        print(f"添加用户错误: {str(e)}")
        return jsonify({'success': False, 'message': '添加用户失败'}), 500


# ==================== 普通用户 API ====================
@app.route('/api/parking/examples', methods=['GET'])
@login_required(required_type='normal')
def get_example_images():
    """返回示例图片文件名列表"""
    import os
    # 修改为指向子目录 images
    example_dir = os.path.join(app.static_folder, 'images_demo', 'images')
    try:
        if not os.path.exists(example_dir):
            return jsonify({'success': True, 'examples': []})  # 目录不存在时返回空列表
        files = [f for f in os.listdir(example_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
        return jsonify({'success': True, 'examples': files})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/parking/recognize', methods=['POST'])
@login_required(required_type='normal')
def recognize_plate():
    """车牌识别接口"""
    if recognizer is None:
        return jsonify({'success': False, 'message': '识别模型未加载'}), 500

    # 获取上传的图片文件
    if 'image' not in request.files:
        return jsonify({'success': False, 'message': '请上传图片'}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'message': '文件名为空'}), 400

    # 保存临时文件
    import tempfile
    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        # 调用识别器
        annotated_img, plates_info = recognizer.recognize(tmp_path, conf_thres=0.25)

        # 将标注图像编码为 base64
        _, buffer = cv2.imencode('.jpg', annotated_img)
        img_base64 = base64.b64encode(buffer).decode('utf-8')

        return jsonify({
            'success': True,
            'image': f'data:image/jpeg;base64,{img_base64}',
            'plates': plates_info
        })
    except Exception as e:
        print(f"识别错误: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        os.unlink(tmp_path)


@app.route('/api/logout', methods=['POST'])
def logout():
    """用户登出"""
    session.clear()
    return jsonify({'success': True, 'message': '登出成功'}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
