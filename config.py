class Config:
    # Flask配置
    SECRET_KEY = 'Zhang-pning'

    # MySQL数据库配置
    MYSQL_HOST = 'localhost'  # mysql数据库ip
    MYSQL_USER = 'root'  #mysql登录用户
    MYSQL_PASSWORD = '########'  #mysql登录密码
    MYSQL_DB = 'user_management'  #mysql数据库名
    MYSQL_CURSORCLASS = 'DictCursor'  #让数据库查询结果以字典形式返回（不要动）

    # 邮箱配置 - 替换为你的QQ邮箱信息
    MAIL_SERVER = 'smtp.qq.com'  #不需要动
    MAIL_PORT = 587  #不需要动
    MAIL_USE_TLS = True #不需要动
    MAIL_USERNAME = '########'  # 发送验证码邮件的QQ邮箱（不需要动）
    MAIL_PASSWORD = '########'  # 发送验证码邮件的QQ邮箱的SMTP授权码（不需要动）

    # 验证码配置
    VERIFICATION_CODE_LENGTH = 6  #邮箱验证码位数
    CODE_VALID_MINUTES = 5  #邮箱验证码有效时间（min）
    # 排除的字符：O, o, 0, 1, l（不包含这五种字符）
    ALLOWED_CHARS = '23456789ABCDEFGHIJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz'

