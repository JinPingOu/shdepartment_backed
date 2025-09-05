-- 刪除舊有的資料表 (如果存在)，CASCADE 會一併移除相關的相依性
DROP TABLE IF EXISTS bulletin_messages,
post_hashtags,
attachments,
posts,
users,
categories,
hashtags CASCADE;
DROP TYPE IF EXISTS user_permission, category_enum, post_status_enum, file_enum;
-- 如果 ENUM 型別已存在，先刪除
-- 建立一個自訂的 ENUM 型別來限制 permission 欄位的值
CREATE TYPE user_permission AS ENUM ('manager', 'editor', 'viewer');
CREATE TYPE category_enum AS ENUM ('latest_news', 'instructions');
CREATE TYPE post_status_enum AS ENUM ('published', 'draft', 'archived');
CREATE TYPE file_enum AS ENUM ('files', 'images', 'attachments');
-- 使用者資料表 (增加帳號、密碼雜湊、權限)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    account VARCHAR(100) NOT NULL UNIQUE,
    -- 登入帳號，必須唯一
    password_hash TEXT NOT NULL,
    -- 儲存雜湊後的密碼，長度較長
    permission user_permission NOT NULL DEFAULT 'viewer',
    -- 權限欄位，使用自訂型別
    department VARCHAR(100),
    campus VARCHAR(100),
    CONSTRAINT chk_account_is_email CHECK (
        account ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'
    )
);

-- 【新功能】使用者活動日誌資料表
CREATE TABLE user_logs (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    action_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    action VARCHAR(50) NOT NULL, -- e.g., 'login', 'create_post', 'view_post'
    details JSONB, -- 儲存詳細資訊，例如存取的 post_id 或搜尋條件
    ip_address VARCHAR(45), -- 儲存使用者的 IP 位址
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
-- 【新功能】Refresh Tokens 資料表
CREATE TABLE refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    token VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
-- 【新】單一分類資料表
CREATE TABLE categories (
    name VARCHAR(50) NOT NULL PRIMARY KEY,
    category_type category_enum NOT NULL
);
-- 標籤資料表
CREATE TABLE hashtags (
    id SERIAL PRIMARY KEY,
    tag_name VARCHAR(50) NOT NULL UNIQUE
);
-- 公告主資料表 (增加點擊計數)
CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT,
    user_id INT NOT NULL,
    category_name VARCHAR(50), -- 允許為空，以防分類被刪除
    status post_status_enum NOT NULL DEFAULT 'draft',
    click_count INT NOT NULL DEFAULT 0,
    -- 點擊計數，預設為 0
    announcement_date TIMESTAMP NOT NULL DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id),
    -- ON UPDATE CASCADE 確保當 category 名稱更新時，這裡會自動同步
    FOREIGN KEY (category_name) REFERENCES categories(name) ON UPDATE CASCADE ON DELETE SET NULL
);
-- 附件資料表
CREATE TABLE files (
    id SERIAL PRIMARY KEY,
    post_id INT NULL, -- post id 初始為 NULL
    file_type file_enum NOT NULL,
    file_path VARCHAR(1024) NOT NULL UNIQUE, -- 【關鍵修正】儲存檔案的相對路徑，必須唯一
    original_filename VARCHAR(255),
    --- file_extension VARCHAR(10),
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
);
-- 公告與標籤的關聯表
CREATE TABLE post_hashtags (
    post_id INT NOT NULL,
    hashtag_id INT NOT NULL,
    PRIMARY KEY (post_id, hashtag_id),
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (hashtag_id) REFERENCES hashtags(id) ON DELETE CASCADE
);
-- 【新增】留言板資料表
CREATE TABLE bulletin_messages (
    id SERIAL PRIMARY KEY,
    author_name VARCHAR(100) NOT NULL DEFAULT '匿名訪客',
    -- 留言者名稱，提供預設值
    content TEXT NOT NULL,
    -- 留言內容，不允許空白
    department VARCHAR(100),
    campus VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW() -- 留言時間 (對應您的 date 需求)
);