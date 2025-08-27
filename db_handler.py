import psycopg2
import psycopg2.extras
import os
import hashlib
from dotenv import load_dotenv
from datetime import date
import re

# 載入 .env 檔案中的環境變數
load_dotenv()

# 從環境變數讀取資料庫設定
DB_CONFIG = {
    'dbname': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT'),
}

class DBHandler:
    """
    一個使用上下文管理器 (with 語句) 來安全處理資料庫連線的類別。
    """
    def __init__(self, config=None):
        """
        建構函式：僅儲存設定，不在此處建立連線。
        """
        self.config = config or DB_CONFIG
        self.conn = None

   
    def connect(self):
        if not self.conn or self.conn.closed:
            self.conn = psycopg2.connect(**self.config)
        return self.conn

    def close(self):
        if self.conn and not self.conn.closed:
            self.conn.close()


    def setup_database(self):
        self.conn = self.connect()
        """從 schema.sql 檔案讀取並執行 SQL 腳本"""
        if not self.conn: return
        try:
            with open('schema.sql', 'r', encoding='utf-8') as f:
                sql_script = f.read()
            with self.conn.cursor() as cur:
                cur.execute(sql_script)
            self.conn.commit()
            print("資料庫資料表已成功從 schema.sql 建立！")
        except Exception as e:
            print(f"執行 schema.sql 時發生錯誤: {e}")
            self.conn.rollback()

    # --- 安全性與使用者管理 ---
    def _hash_password(self, password):
        """使用 SHA-256 對密碼進行雜湊"""
        return hashlib.sha256(password.encode()).hexdigest()

    def create_user(self, name, account, password, permission='viewer', campus=None, department=None):
        self.conn = self.connect()
        """新增使用者，並將密碼雜湊後存入"""
        if not self.conn: return None

        if not re.match(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$', account):
            print(f"錯誤：帳號 '{account}' 不是有效的電子郵件格式。")
            return None
        password_hash = self._hash_password(password)
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (name, account, password_hash, permission, campus, department) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id;",
                    (name, account, password_hash, permission, campus, department)
                )
                user_id = cur.fetchone()[0]
            self.conn.commit()
            print(f"已建立使用者 '{name}' (權限: {permission})，ID: {user_id}")
            return user_id
        except psycopg2.IntegrityError:
            print(f"錯誤：帳號 '{account}' 已存在。")
            self.conn.rollback()
            return None
        except psycopg2.Error as e:
            print(f"新增使用者時發生錯誤: {e}")
            self.conn.rollback()
            return None
        
    def delete_user(self, user_id):
        """刪除使用者"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM users WHERE id = %s;", (user_id,))
                if cur.rowcount == 0:
                    print(f"刪除失敗：找不到 ID 為 {user_id} 的使用者。")
                    return False
            self.conn.commit()
            print(f"已成功刪除使用者 ID: {user_id}")
            return True
        except psycopg2.Error as e:
            print(f"刪除使用者時發生錯誤: {e}")
            self.conn.rollback()
            return False
        
    def find_user(self, user_id=None, account=None):
        """根據 ID 或帳號尋找使用者"""
        if not user_id and not account: return None
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                if user_id:
                    cur.execute("SELECT id, name, account, permission, department, campus FROM users WHERE id = %s;", (user_id,))
                else:
                    cur.execute("SELECT id, name, account, permission, department, campus FROM users WHERE account = %s;", (account,))
                user = cur.fetchone()
                return dict(user) if user else None
        except psycopg2.Error as e:
            print(f"尋找使用者時發生錯誤: {e}")
            return None
        
    def update_user(self, user_id, new_data):
        """更新使用者資料 (不包含密碼和帳號)"""
        fields = ['name', 'permission', 'department', 'campus']
        # 建立 SET 子句和參數列表
        set_clause = ", ".join([f"{key} = %s" for key in new_data if key in fields])
        params = [new_data[key] for key in new_data if key in fields]
        
        if not set_clause:
            print("沒有提供可更新的欄位。")
            return False
            
        params.append(user_id)
        sql = f"UPDATE users SET {set_clause} WHERE id = %s;"
        
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                if cur.rowcount == 0:
                    print(f"更新失敗：找不到 ID 為 {user_id} 的使用者。")
                    return False
            self.conn.commit()
            print(f"已成功更新使用者 ID: {user_id}")
            return True
        except psycopg2.Error as e:
            print(f"更新使用者時發生錯誤: {e}")
            self.conn.rollback()
            return False

    def get_user_permission(self, user_id):
        self.conn = self.connect()
        """取得指定使用者的權限等級"""
        try:
            user = self.find_user(user_id=user_id)
            return user['permission'] if user else None
        except psycopg2.Error as e:
            print(f"獲取權限時發生錯誤: {e}")
            return None
        

    # --- 分類管理 ---
    def create_parent_category(self, name: str):
        """
        新增一個頂層的父分類 (例如 '最新消息' 或 '說明文件')。
        這個名稱必須符合我們在資料庫中定義的 ENUM 型別。
        """
        if not self.conn: return None
        try:
            with self.conn.cursor() as cur:
                # 在新增時，我們同時填入 name 和 category_type 欄位
                sql = "INSERT INTO categories (name, category_type) VALUES (%s, %s) RETURNING id;"
                cur.execute(sql, (name, name))
                result = cur.fetchone()
                if result:
                    category_id = result[0]
                    self.conn.commit()
                    print(f"已成功建立父分類 '{name}' (ID: {category_id})")
                    return category_id
                return None
        except psycopg2.Error as e:
            # 如果 name 不符合 ENUM 的定義，資料庫會在這裡報錯
            print(f"新增父分類 '{name}' 時發生錯誤: {e}")
            self.conn.rollback()
            return None

    def create_subcategory(self, name: str, parent_id: int):
        """
        在一個合法的父分類底下，新增一個子分類。
        資料庫的 CHECK 約束會自動驗證 parent_id 是否合法。
        """
        if not self.conn: return None
        try:
            with self.conn.cursor() as cur:
                # 我們只需要提供 name 和 parent_id，category_type 保持 NULL
                sql = "INSERT INTO categories (name, parent_id) VALUES (%s, %s) RETURNING id;"
                cur.execute(sql, (name, parent_id))
                result = cur.fetchone()
                if result:
                    subcategory_id = result[0]
                    self.conn.commit()
                    print(f"已成功在父分類 ID {parent_id} 底下建立子分類 '{name}' (ID: {subcategory_id})")
                    return subcategory_id
                return None
        except psycopg2.Error as e:
            # 如果 parent_id 不合法，資料庫的 CHECK 約束會觸發錯誤
            print(f"新增子分類 '{name}' 時發生錯誤: {e}")
            self.conn.rollback()
            return None
        
    def delete_category(self, category_id):
        """刪除分類 (父或子)"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM categories WHERE id = %s;", (category_id,))
                if cur.rowcount == 0:
                    print(f"刪除失敗：找不到 ID 為 {category_id} 的分類。")
                    return False
            self.conn.commit()
            print(f"已成功刪除分類 ID: {category_id}")
            return True
        except psycopg2.Error as e:
            print(f"刪除分類時發生錯誤: {e}")
            self.conn.rollback()
            return False

    def get_subcategories(self, parent_id):
        """尋找父分類下的所有子分類"""
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("SELECT id, name FROM categories WHERE parent_id = %s;", (parent_id,))
                return [dict(row) for row in cur.fetchall()]
        except psycopg2.Error as e:
            print(f"尋找子分類時發生錯誤: {e}")
            return []

    # --- 文章 CRUD ---
    def create_post(self, user_id, category_id, title, content, **kwargs):
        self.conn = self.connect()
        """新增文章 (只有 manager 和 editor 可以新增)"""
        if not self.conn: return None
        permission = self.get_user_permission(user_id)
        if permission not in ['manager', 'editor']:
            print(f"權限不足：使用者 {user_id} (權限: {permission}) 無法新增文章。")
            return None
        try:
            with self.conn.cursor() as cur:
                # 1. 新增 Post
                sql_post = "INSERT INTO posts (user_id, category_id, title, content) VALUES (%s, %s, %s, %s) RETURNING id;"
                cur.execute(sql_post, (user_id, category_id, title, content))
                post_id = cur.fetchone()[0]

                # 2. 處理附件
                if attachments:
                    sql_attach = "INSERT INTO attachments (post_id, file_path, original_filename) VALUES (%s, %s, %s);"
                    attach_data = [(post_id, att['path'], att['name']) for att in attachments]
                    psycopg2.extras.execute_values(cur, sql_attach, attach_data)

                # 3. 處理標籤
                if hashtags:
                    tag_ids = []
                    for tag_name in hashtags:
                        cur.execute("SELECT id FROM hashtags WHERE tag_name = %s;", (tag_name,))
                        tag_result = cur.fetchone()
                        if tag_result:
                            tag_ids.append(tag_result[0])
                        else:
                            cur.execute("INSERT INTO hashtags (tag_name) VALUES (%s) RETURNING id;", (tag_name,))
                            tag_ids.append(cur.fetchone()[0])
                    
                    sql_post_tag = "INSERT INTO post_hashtags (post_id, hashtag_id) VALUES (%s, %s);"
                    post_tag_data = [(post_id, tag_id) for tag_id in tag_ids]
                    psycopg2.extras.execute_values(cur, sql_post_tag, post_tag_data)
            
            self.conn.commit()
            print(f"已成功建立文章 '{title}' (ID: {post_id})")
            return post_id
        except psycopg2.Error as e:
            print(f"新增文章時發生錯誤: {e}")
            self.conn.rollback()
            return None
        
    def delete_post(self, post_id):
        """刪除文章 (關聯的附件和標籤也會自動刪除)"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM posts WHERE id = %s;", (post_id,))
                if cur.rowcount == 0:
                    print(f"刪除失敗：找不到 ID 為 {post_id} 的文章。")
                    return False
            self.conn.commit()
            print(f"已成功刪除文章 ID: {post_id}")
            return True
        except psycopg2.Error as e:
            print(f"刪除文章時發生錯誤: {e}")
            self.conn.rollback()
            return False
    def update_post(self, post_id, new_data):
        """更新文章 (不含附件和標籤)"""
        fields = ['title', 'content', 'main_image_url', 'category_id']
        set_clause = ", ".join([f"{key} = %s" for key in new_data if key in fields])
        params = [new_data[key] for key in new_data if key in fields]
        
        if not set_clause: return False
        params.append(post_id)
        sql = f"UPDATE posts SET {set_clause}, updated_at = NOW() WHERE id = %s;"
        
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                if cur.rowcount == 0: return False
            self.conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"更新文章時發生錯誤: {e}")
            self.conn.rollback()
            return False
        
    def get_post(self, post_id):
        """根據 ID 尋找文章，包含附件和標籤"""
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                sql = """
                    SELECT p.*, u.name as author_name, c.name as category_name,
                           ARRAY_AGG(DISTINCT h.tag_name) FILTER (WHERE h.tag_name IS NOT NULL) as hashtags,
                           JSON_AGG(DISTINCT jsonb_build_object('path', a.file_path, 'name', a.original_filename)) FILTER (WHERE a.id IS NOT NULL) as attachments
                    FROM posts p
                    LEFT JOIN users u ON p.user_id = u.id
                    LEFT JOIN categories c ON p.category_id = c.id
                    LEFT JOIN post_hashtags ph ON p.id = ph.post_id
                    LEFT JOIN hashtags h ON ph.hashtag_id = h.id
                    LEFT JOIN attachments a ON p.id = a.post_id
                    WHERE p.id = %s
                    GROUP BY p.id, u.name, c.name;
                """
                cur.execute(sql, (post_id,))
                post = cur.fetchone()
                return dict(post) if post else None
        except psycopg2.Error as e:
            print(f"尋找文章時發生錯誤: {e}")
            return None
        
    def get_all_posts(self, order_by='announcement_date', limit=20, offset=0):
        """取得所有文章，可指定排序方式"""
        if order_by not in ['announcement_date', 'click_count']:
            order_by = 'announcement_date'
        
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                sql = f"SELECT id, title, click_count, announcement_date FROM posts ORDER BY {order_by} DESC LIMIT %s OFFSET %s;"
                cur.execute(sql, (limit, offset))
                return [dict(row) for row in cur.fetchall()]
        except psycopg2.Error as e:
            print(f"取得所有文章時發生錯誤: {e}")
            return []
    def search_posts_by_title(self, keyword):
        """根據標題關鍵字尋找文章"""
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                sql = "SELECT id, title FROM posts WHERE title ILIKE %s;"
                cur.execute(sql, (f"%{keyword}%",))
                return [dict(row) for row in cur.fetchall()]
        except psycopg2.Error as e:
            print(f"搜尋文章時發生錯誤: {e}")
            return []
    def get_posts_by_category(self, category_id, include_subcategories=False):
        """根據分類 ID 尋找文章"""
        target_ids = [category_id]
        if include_subcategories:
            sub_cats = self.get_subcategories(category_id)
            target_ids.extend([cat['id'] for cat in sub_cats])
        
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                sql = "SELECT id, title FROM posts WHERE category_id = ANY(%s);"
                cur.execute(sql, (target_ids,))
                return [dict(row) for row in cur.fetchall()]
        except psycopg2.Error as e:
            print(f"按分類尋找文章時發生錯誤: {e}")
            return []
    def search_posts(self, keyword, source_type=None):
        self.conn = self.connect()
        """
        使用 ILIKE 搜尋文章
        :param keyword: 搜尋關鍵字
        :param source_type: (可選) 指定來源，如 '布告欄'
        """
        if not self.conn: return []
        results = []
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # 使用 ILIKE 進行不分大小寫的模糊比對
                query = """
                    SELECT
                        p.id, p.title,
                        c.name as category_name,
                        COALESCE(parent_c.name, c.name) as source_type
                    FROM posts p
                    LEFT JOIN categories c ON p.category_id = c.id
                    LEFT JOIN categories parent_c ON c.parent_id = parent_c.id
                    WHERE p.title ILIKE %s
                """
                # 參數需要加上 '%' 萬用字元
                params = [f"%{keyword}%"]

                if source_type:
                    query += " AND COALESCE(parent_c.name, c.name) = %s"
                    params.append(source_type)
                
                query += ";"
                cur.execute(query, tuple(params))
                results = cur.fetchall()
        except psycopg2.Error as e:
            print(f"搜尋時發生錯誤: {e}")
        return results

    # --- 留言板CURD ---
    def insert_bulletin_message(self, author_name, content, department=None, campus=None):
        self.conn = self.connect()
        if not self.conn: return None
        if not content or not content.strip():
            print("錯誤：留言內容不可為空。")
            return None
        
        author_to_insert = author_name if author_name and author_name.strip() else None
        try:
            with self.conn.cursor() as cur:
                sql = "INSERT INTO bulletin_messages (author_name, content, department, campus) VALUES (%s, %s, %s, %s) RETURNING id;"
                params = (author_to_insert, content, department, campus)
                cur.execute(sql, params)
                
                # 【關鍵修正】先檢查 fetchone() 的結果
                result = cur.fetchone()
                if result:
                    message_id = result[0]
                    self.conn.commit()
                    print(f"感謝 '{author_to_insert or '匿名訪客'}' 的留言！ (ID: {message_id})")
                    return message_id
                else:
                    # 如果沒有返回結果，表示新增失敗
                    print("錯誤：新增留言後未能取得返回的 ID。")
                    self.conn.rollback()
                    return None
        except psycopg2.Error as e:
            print(f"新增留言時發生錯誤: {e}")
            self.conn.rollback()
            return None

    def get_all_bulletin_messages(self, page_size: int, offset: int) -> dict:
        self.conn = self.connect()
        """取得最新的留言板訊息"""
        if not self.conn: return []
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT id, author_name, content, campus, department, created_at FROM bulletin_messages ORDER BY created_at DESC LIMIT %s OFFSET %s;", (page_size, offset))
                rows = cur.fetchall()
                cur.execute("SELECT COUNT(*) FROM bulletin_messages")
                total = cur.fetchone()['count']
                return{'rows':rows, 'total':total}
        except psycopg2.Error as e:
            print(f"讀取留言時發生錯誤: {e}")
            return []
        

    def get_messages_by_date(self, target_date: date, page_size: int, offset: int):
        self.conn = self.connect()
        """【新功能】根據特定日期 (YYYY-MM-DD) 取得留言"""
        if not self.conn: return []
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # 使用 ::date 將 TIMESTAMPTZ 轉換為 DATE 型別進行比較
                sql = """
                    SELECT id, author_name, content, department, campus, created_at 
                    FROM guestbook_messages 
                    WHERE created_at::date = %s
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s;
                """
                cur.execute(sql, (target_date, page_size, offset))
                rows = cur.fetchall()
                cur.execute("SELECT COUNT(*) FROM bulletin_messages")
                total = cur.fetchone()['count']
                return{'rows':rows, 'total':total}
        except psycopg2.Error as e:
            print(f"按日期查詢留言時發生錯誤: {e}")
            return []

    def get_messages_by_campus_and_department(self, campus: str, department: str, page_size: int, offset: int):
        self.conn = self.connect()
        """【新功能】根據校區和系所取得留言 (兩者皆須提供)"""
        if not self.conn: return []
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                sql = """
                    SELECT id, author_name, content, department, campus, created_at 
                    FROM guestbook_messages 
                    WHERE campus = %s AND department = %s
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s;;
                """
                cur.execute(sql, (campus, department, page_size, offset))
                rows = cur.fetchall()
                cur.execute("SELECT COUNT(*) FROM bulletin_messages")
                total = cur.fetchone()['count']
                return{'rows':rows, 'total':total}
        except psycopg2.Error as e:
            print(f"按校區和系所查詢留言時發生錯誤: {e}")
            return []
        

    def delete_bulletin_message(self, message_id):
        self.conn = self.connect()
        """【Delete】刪除一則留言"""
        if not self.conn: return False
        try:
            with self.conn.cursor() as cur:
                sql = "DELETE FROM bulletin_messages WHERE id = %s;"
                cur.execute(sql, (message_id,))
                
                if cur.rowcount == 0:
                    print(f"刪除失敗：找不到 ID 為 {message_id} 的留言。")
                    self.conn.rollback()
                    return False

            self.conn.commit()
            print(f"ID 為 {message_id} 的留言已成功刪除。")
            return True
        except psycopg2.Error as e:
            print(f"刪除留言 (ID: {message_id}) 時發生錯誤: {e}")
            self.conn.rollback()
            return False

# --- 主執行區塊 ---
if __name__ == "__main__":
    if not os.path.exists('schema.sql'):
        print("錯誤: 'schema.sql' 檔案不存在。")
    else:
        try:
            # 使用 with 語句來管理 DBHandler 物件
            db = DBHandler()
            # --- 在這裡執行所有資料庫操作 ---
            
            # print("\n--- 1. 初始化資料庫 ---")
            # db.setup_database()

            # print("\n--- 2. 建立使用者 ---")
            # db.create_user("SHD", "manager01", "shdadmin", permission="manager")

            # print("\n--- 3. 示範留言板功能 ---")
            # db.create_bulletin_message("路人甲", "這個網站做得真不錯！", campus="義大醫院", department="智慧醫療部")
            # db.create_bulletin_message("熱心鄉民", "請問 AI 研討會什麼時候報名？", campus="義大癌治療醫院")

            # print("\n--- 4. 刪除指定布告欄訊息 ---")
            # db.delete_bulletin_message(1)

            # print("\n--- 5. 讀取留言板 ---")
            # messages = db.get_all_bulletin_messages(10,0)
            # if messages["total"]:
            #     print(f"顯示最新的 {messages['total']} 則留言：")
            #     for msg in messages['rows']:
            #         print(f"  [{msg['created_at'].strftime('%Y-%m-%d %H:%M')}] {msg['author_name']}: {msg['content']}")

            print("\n--- 6. 讀取留言板 ---")
            messages = db.get_bulletin_messages_by_date(10,0,date="2025-08-27")
            if messages["total"]:
                print(f"顯示最新的 {messages['total']} 則留言：")
                for msg in messages['rows']:
                    print(f"  [{msg['created_at'].strftime('%Y-%m-%d %H:%M')}] {msg['author_name']}: {msg['content']}")

            print("\n--- 7. 讀取留言板 ---")
            messages = db.get_all_bulletin_messages(10,0,campus="義大醫院",department="智慧醫療部")
            if messages["total"]:
                print(f"顯示最新的 {messages['total']} 則留言：")
                for msg in messages['rows']:
                    print(f"  [{msg['created_at'].strftime('%Y-%m-%d %H:%M')}] {msg['author_name']}: {msg['content']}")

        except psycopg2.OperationalError:  
            # 如果連線在 __enter__ 中就失敗了，會在這裡捕獲到
            print("程式因資料庫連線問題而終止。")
        except Exception as e:
            print(f"發生未預期的錯誤: {e}")

