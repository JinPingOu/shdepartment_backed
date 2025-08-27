-- 刪除舊有的資料表 (如果存在)，CASCADE 會一併移除相關的相依性
DROP TABLE IF EXISTS bulletin_messages, post_hashtags, attachments, posts, users, categories, hashtags CASCADE;
DROP TYPE IF EXISTS user_permission; -- 如果 ENUM 型別已存在，先刪除

-- 建立一個自訂的 ENUM 型別來限制 permission 欄位的值
CREATE TYPE user_permission AS ENUM ('manager', 'editor', 'viewer');

-- 使用者資料表 (增加帳號、密碼雜湊、權限)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    account VARCHAR(100) NOT NULL UNIQUE, -- 登入帳號，必須唯一
    password_hash TEXT NOT NULL, -- 儲存雜湊後的密碼，長度較長
    permission user_permission NOT NULL DEFAULT 'viewer', -- 權限欄位，使用自訂型別
    department VARCHAR(100),
    campus VARCHAR(100)
);

-- 分類資料表 (維持階層結構)
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    parent_id INT,
    CONSTRAINT fk_parent_category FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE SET NULL
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
    main_image_url VARCHAR(2083),
    user_id INT NOT NULL,
    category_id INT,
    click_count INT NOT NULL DEFAULT 0, -- 點擊計數，預設為 0
    announcement_date TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

-- 附件資料表
CREATE TABLE attachments (
    id SERIAL PRIMARY KEY,
    post_id INT NOT NULL,
    file_path VARCHAR(1024) NOT NULL,
    original_filename VARCHAR(255),
    file_extension VARCHAR(10),
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
    author_name VARCHAR(100) NOT NULL DEFAULT '匿名訪客', -- 留言者名稱，提供預設值
    content TEXT NOT NULL, -- 留言內容，不允許空白
    department VARCHAR(100),
    campus VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW() -- 留言時間 (對應您的 date 需求)
);


-- 建立索引
CREATE INDEX idx_categories_parent_id ON categories(parent_id);
-- CREATE INDEX idx_posts_title ON posts USING GIN (to_tsvector('chinese', title));
CREATE INDEX idx_bulletin_created_at ON bulletin_messages(created_at DESC); -- 為留言板時間建立索引