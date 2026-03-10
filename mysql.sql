-- 创建数据库
CREATE DATABASE IF NOT EXISTS user_management DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE user_management;

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '用户ID',
    username VARCHAR(50) UNIQUE NOT NULL COMMENT '用户名（唯一）',
    password VARCHAR(255) NOT NULL COMMENT '密码（加密存储）',
    email VARCHAR(255) UNIQUE NOT NULL COMMENT '邮箱（唯一）',
    user_type ENUM('normal', 'admin') DEFAULT 'normal' NOT NULL COMMENT '用户类型：normal-普通用户, admin-管理员',
    login_count INT DEFAULT 0 COMMENT '用户登录次数',
    state ENUM('0','1') DEFAULT 1 NOT NULL COMMENT '用户状态：0-被禁用，1-活跃',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_username (username),
    INDEX idx_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- 验证码表
CREATE TABLE IF NOT EXISTS verification_codes (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '验证码ID',
    email VARCHAR(255) NOT NULL COMMENT '邮箱地址',
    code VARCHAR(10) NOT NULL COMMENT '验证码',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    expired_at TIMESTAMP NOT NULL COMMENT '过期时间',
    INDEX idx_email (email),
    INDEX idx_expired_at (expired_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='验证码表';

-- 插入20条随机用户数据，做测试
INSERT INTO users (username, password, email, user_type, login_count, state, created_at, updated_at)
WITH RECURSIVE numbers(n) AS (
    SELECT 1
    UNION ALL
    SELECT n + 1 FROM numbers WHERE n < 20
)
SELECT
    CONCAT('user', n) AS username,                                 -- 用户名：user1 ~ user20
    MD5(RAND()) AS password,                                        -- 随机密码哈希（32位十六进制）
    CONCAT('user', n, '@example.com') AS email,                     -- 邮箱：user1@example.com 等
    ELT(1 + FLOOR(RAND() * 2), 'normal', 'admin') AS user_type,    -- 随机类型：normal 或 admin
    FLOOR(RAND() * 100) AS login_count,                             -- 登录次数：0~99
    ELT(1 + FLOOR(RAND() * 2), '0', '1') AS state,                  -- 状态：0（禁用）或 1（活跃）
    NOW() - INTERVAL FLOOR(RAND() * 365) DAY AS created_at,         -- 创建时间：最近365天内随机
    NOW() - INTERVAL FLOOR(RAND() * 30) DAY AS updated_at           -- 更新时间：最近30天内随机
FROM numbers;