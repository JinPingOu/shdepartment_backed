import psycopg2
import psycopg2.extras
import os
import hashlib
from dotenv import load_dotenv
from datetime import date, datetime
import re
import json

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
    def __init__(self, config=None):
        self.config = config or DB_CONFIG
        self.conn = None

    def __enter__(self):
        """進入 'with' 區塊時自動建立連線。"""
        try:
            self.conn = psycopg2.connect(**self.config)
            return self
        except psycopg2.OperationalError as e:
            print(f"錯誤：無法連接到資料庫 '{self.config.get('dbname')}'.\n{e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """離開 'with' 區塊時自動關閉連線。"""
        if self.conn:
            self.conn.close()

    def setup_database(self):
        """從 schema.sql 檔案讀取並執行 SQL 腳本"""
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

    # --- Users Management ---
    def find_user(self, user_id=None, account=None):
        """根據 ID 或帳號尋找使用者"""
        if not user_id and not account: return None
        if user_id and account:
            print("could not find id and account at the same time")
            return None
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if user_id:
                    cur.execute("SELECT * FROM users WHERE id = %s;", (user_id,))
                else:
                    cur.execute("SELECT * FROM users WHERE account = %s;", (account,))
                user = cur.fetchone()
                return dict(user) if user else None
        except psycopg2.Error as e:
            print(f"尋找使用者時發生錯誤: {e}")
            return None
        
            
    def get_user_permission(self, user_id):
        """取得指定使用者的權限等級"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT permission FROM users WHERE id = %s;", (user_id,))
                result = cur.fetchone()
                return result[0] if result else None
        except psycopg2.Error as e:
            print(f"獲取權限時發生錯誤: {e}")
            return None
        
    def check_password(self, account, password):
        """【新功能】檢查帳號密碼是否正確"""
        user = self.find_user(account=account)
        if not user:
            return None
        
        password_hash = self._hash_password(password)
        if password_hash == user['password_hash']:
            # 不回傳密碼雜湊
            user.pop('password_hash', None)
            return user
        return None

    def _hash_password(self, password):
        """使用 SHA-256 對密碼進行雜湊"""
        return hashlib.sha256(password.encode()).hexdigest()

    def create_user(self, name, account, password, permission='viewer', campus=None, department=None):

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
    
    # --- 【新功能】Refresh Token Management ---
    def store_refresh_token(self, user_id, token, expires_at):
        """儲存 Refresh Token 到資料庫"""
        try:
            with self.conn.cursor() as cur:
                sql = "INSERT INTO refresh_tokens (user_id, token, expires_at) VALUES (%s, %s, %s);"
                cur.execute(sql, (user_id, token, expires_at))
            self.conn.commit()
            return True
        except psycopg2.Error as e:
            self.conn.rollback()
            print(f"儲存 Refresh Token 時發生錯誤: {e}")
            return False

    def validate_refresh_token(self, token):
        """驗證 Refresh Token 是否有效且未過期"""
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                sql = "SELECT user_id FROM refresh_tokens WHERE token = %s AND expires_at > %s;"
                cur.execute(sql, (token, datetime.now(datetime.timezone.utc)))
                result = cur.fetchone()
                return result['user_id'] if result else None
        except psycopg2.Error as e:
            print(f"驗證 Refresh Token 時發生錯誤: {e}")
            return None

    def delete_refresh_token(self, token):
        """從資料庫中刪除 Refresh Token (用於登出)"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM refresh_tokens WHERE token = %s;", (token,))
            self.conn.commit()
            return True
        except psycopg2.Error as e:
            self.conn.rollback()
            print(f"刪除 Refresh Token 時發生錯誤: {e}")
            return False    

    # --- User Logging ---
    def create_log(self, user_id, action, details=None, ip_address=None):
        """新增一筆使用者活動日誌"""
        try:
            with self.conn.cursor() as cur:
                details_json = json.dumps(details) if details is not None else None
                sql = "INSERT INTO user_logs (user_id, action, details, ip_address) VALUES (%s, %s, %s, %s);"
                cur.execute(sql, (user_id, action, details_json, ip_address))
            self.conn.commit()
            return True
        except psycopg2.Error as e:
            self.conn.rollback()
            print(f"新增日誌時發生錯誤: {e}")
            return False
        
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

        

    # --- 分類管理 ---
    # --- 父分類: latest_news、instructions ---

    def insert_category(self, name: str, category_type: str):
        try:
            with self.conn.cursor() as cur:
                # sql 最後沒加上 RETURNING 就不會回傳
                sql = "INSERT INTO categories (name, category_type) VALUES (%s, %s);"
                cur.execute(sql, (name, category_type))
                self.conn.commit()
                return True
        except psycopg2.Error as e:
            print(f"新增分類時發生錯誤: {e}")
            self.conn.rollback()
            return False
        except Exception as e:
            print(f"發生未預期的錯誤: {e}")
            self.conn.rollback()
            return False

    def delete_category(self, category_name):
        try:
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM categories WHERE name = %s;", (category_name,))
                if cur.rowcount > 0:
                    self.conn.commit()
                    return True
            print(f"找不到叫做 {category_name} 的子類型")
            return False
        except psycopg2.Error as e:
            self.conn.rollback()
            print(f"刪除分類 '{category_name}' 時發生資料庫錯誤: {e}")
            return False
    
    def get_type_by_category(self, category_name):
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT category_type FROM categories WHERE name = %s;", (category_name,))
                result = cur.fetchone()
                if result:
                    return result['category_type']
                print(f"找不到子分類 {category_name}")
                return None
        except psycopg2.Error as e:
            print(f"尋找子分類時發生錯誤: {e}")
            return None
        
    def get_categories_by_type(self, category_type = None):
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if category_type:
                    cur.execute("SELECT name, category_type FROM categories WHERE category_type = %s;", (category_type,))
                else:
                    cur.execute("SELECT name, category_type FROM categories;")
                return cur.fetchall()
                
        except psycopg2.Error as e:
            print(f"尋找分類時發生錯誤: {e}")
            return []
    
    # --- 上傳文件 ---
    def upload_file(self, file_path, original_filename, file_type="files"):
        """
        新增一筆獨立的檔案紀錄到 files 表，post_id 預設為 NULL。
        回傳新建立的 file_id。
        """
        try:
            with self.conn.cursor() as cur:
                sql = """
                    INSERT INTO files (file_path, original_filename, file_type)
                    VALUES (%s, %s, %s) RETURNING id;
                """
                cur.execute(sql, (file_path, original_filename, file_type))
                file_id = cur.fetchone()[0]
                self.conn.commit()
                return file_id
        except psycopg2.Error as e:
            print(f"上傳檔案時發生錯誤: {e}")
            self.conn.rollback()
            return None
        
    def get_files(self, filters=None, page_size=10, offset=0):
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                where_clauses = []
                params = []

                if filters:
                    if 'post_id' in filters:
                        where_clauses.append("post_id = %s")
                        params.append(f"%{filters['post_id']}%")
                    if 'file_type' in filters:
                        where_clauses.append("file_type = %s")
                        params.append(filters['file_type'])
                    if 'original_filename' in filters:
                        where_clauses.append("original_filename = %s")
                        params.append(filters['original_filename'])
                
                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
            
                count_sql = f"SELECT COUNT(*) as total FROM files WHERE {where_sql} ;"
                cur.execute(count_sql)
                total = cur.fetchone()['total']
                
                sql = f"""
                    SELECT id, post_id, file_type, file_path, original_filename
                    FROM files
                    WHERE {where_sql}
                    LIMIT %s OFFSET %s;
                """
                params.extend([page_size, offset])
                
                cur.execute(sql, tuple(params))
                messages = [dict(row) for row in cur.fetchall()]
                return {'total': total, 'rows': messages}
        except psycopg2.Error as e:
            print(f"取得檔案時發生錯誤: {e}")
            return []
    
    def get_file(self, file_id):
        try:
            with self.conn.cursor() as cur:
                sql = "SELECT id, post_id, file_type, file_path, original_filename FROM files WHERE id = %s"
                cur.execute(sql, (file_id,))
                result = cur.fetchone()
                return dict(result) if result else None
        except psycopg2.Error as e:
            print(f"取得檔案時發生錯誤: {e}")
            return None

    def get_file_owner(self, file_id):
        """【新功能】根據 file_id 查找其所屬文章的作者 user_id。"""
        try:
            with self.conn.cursor() as cur:
                # 透過 JOIN 查詢 post 的 user_id
                sql = """
                    SELECT p.user_id FROM posts p
                    JOIN files f ON p.id = f.post_id
                    WHERE f.id = %s;
                """
                cur.execute(sql, (file_id,))
                result = cur.fetchone()
                # 如果檔案未關聯到任何文章，或找不到檔案，則回傳 None
                return result[0] if result else None
        except psycopg2.Error as e:
            print(f"查找檔案擁有者時發生錯誤: {e}")
            return None

    def delete_file(self, file_id):
        """【新功能】從 files 資料表中刪除一筆檔案紀錄。"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM files WHERE id = %s;", (file_id,))
                if cur.rowcount == 0:
                    return False # 找不到要刪除的檔案
            self.conn.commit()
            return True
        except psycopg2.Error as e:
            self.conn.rollback()
            print(f"刪除檔案紀錄 (ID: {file_id}) 時發生錯誤: {e}")
            return False

    # --- 文章 CRUD ---
    def insert_post(self, title, content, user_id, category_name, status="draft", hashtags=None, file_ids=None):
        try:
            with self.conn.cursor() as cur:
                # 新增 post 主體並取得返回的 post ID
                post_sql = """
                    INSERT INTO posts (title, content, user_id, category_name, status)
                VALUES (%s, %s, %s, %s, %s) RETURNING id;
                """
                cur.execute(post_sql, (title, content, user_id, category_name, status))
                
                result = cur.fetchone()
                if not result:
                    raise Exception("新增 Post 後未能取得返回的 ID")
                post_id = result[0]

                # 關聯檔案 (透過更新 post_id)
                if file_ids and isinstance(file_ids, list):
                    # 使用 ANY 語法可以高效地更新多筆紀錄
                    update_files_sql = "UPDATE files SET post_id = %s WHERE id = ANY(%s);"
                    cur.execute(update_files_sql, (post_id, file_ids))

                # 處理標籤
                if hashtags and isinstance(hashtags, list):
                    tag_sql = "INSERT INTO hashtags (tag_name) VALUES (%s) ON CONFLICT (tag_name) DO UPDATE SET tag_name=EXCLUDED.tag_name RETURNING id;"
                    tag_ids = []
                    for name in hashtags:
                        cur.execute(tag_sql, (name,))
                        tag_ids.append(cur.fetchone()[0])
                    
                    post_tag_sql = "INSERT INTO post_hashtags (post_id, hashtag_id) VALUES %s;"
                    post_tag_data = [(post_id, tag_id) for tag_id in tag_ids]
                    psycopg2.extras.execute_values(cur, post_tag_sql, post_tag_data)
            
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
        """
        【擴充功能】更新文章，包含文字、主圖、附件和標籤。
        這是一個完整的交易操作。
        """
        try:
            with self.conn.cursor() as cur:
                # 步驟 1: 更新 posts 表中的基本欄位
                update_fields = ['title', 'content', 'category_name', 'status']
                set_parts = [f"{field} = %s" for field in update_fields if field in new_data]
                if set_parts:
                    params = [new_data[field] for field in update_fields if field in new_data]
                    params.append(post_id)
                    sql = f"UPDATE posts SET {', '.join(set_parts)}, announcement_date = NOW() WHERE id = %s;"
                    cur.execute(sql, tuple(params))

                if 'file_ids' in new_data:
                    # 解除所有舊檔案的關聯 (將 post_id 設為 NULL)
                    cur.execute("UPDATE files SET post_id = NULL WHERE post_id = %s;", (post_id,))
                    # 關聯新檔案
                    new_file_ids = new_data['file_ids']
                    if new_file_ids and isinstance(new_file_ids, list):
                        cur.execute("UPDATE files SET post_id = %s WHERE id = ANY(%s);", (post_id, new_file_ids))

                # 步驟 3: 如果提供了 hashtags，則完全取代舊的
                if 'hashtags' in new_data:
                    # 先刪除所有舊的標籤關聯
                    cur.execute("DELETE FROM post_hashtags WHERE post_id = %s;", (post_id,))
                    # 如果新標籤列表不為空，則新增它們
                    new_hashtags = new_data['hashtags']
                    if new_hashtags and isinstance(new_hashtags, list):
                        tag_ids = []
                        for tag_name in new_hashtags:
                            # 查找或新增標籤，並取得 ID
                            cur.execute("INSERT INTO hashtags (tag_name) VALUES (%s) ON CONFLICT (tag_name) DO UPDATE SET tag_name=EXCLUDED.tag_name RETURNING id;", (tag_name,))
                            tag_id = cur.fetchone()[0]
                            tag_ids.append(tag_id)
                        
                        # 建立新的關聯
                        post_tag_sql = "INSERT INTO post_hashtags (post_id, hashtag_id) VALUES %s;"
                        post_tag_data = [(post_id, tag_id) for tag_id in tag_ids]
                        psycopg2.extras.execute_values(cur, post_tag_sql, post_tag_data)

            # 如果所有操作都成功，提交交易
            self.conn.commit()
            return True
        except psycopg2.Error as e:
            # 如果任何步驟出錯，回滾所有操作
            print(f"更新文章 (ID: {post_id}) 時發生錯誤: {e}")
            self.conn.rollback()
            return False
        
        
      
    def get_post(self, post_id):
        try:
            with self.conn.cursor(psycopg2.extras.RealDictCursor) as cur:
                cur.execute("UPDATE posts SET click_count = click_count + 1 WHERE id = %s RETURNING *;", (post_id,))
                result = cur.fetchone()
                if not result:
                    self.conn.rollback()
                    return None
                
                cur.execute("SELECT id, file_path, original_filename FROM files WHERE post_id = %s AND file_type = 'attachments'", (post_id,))
                result['attachments'] = cur.fetchall()

                cur.execute("SELECT id, file_path, original_filename FROM files WHERE post_id = %s AND file_type = 'images'", (post_id,))
                result['images'] = cur.fetchall()

                cur.execute("SELECT t.tag_name FROM hashtags t JOIN post_hashtags pt ON t.id = pt.hashtag_id WHERE pt.post_id = %s;", (post_id,))
                result['hashtags'] = [row['tag_name'] for row in cur.fetchall()]

                self.conn.commit()
                return result
        except psycopg2.Error as e:
            self.conn.rollback()
            print(f"取得所有文章時發生錯誤: {e}")
            return None
            
        

    def get_posts(self, filters=None, order_by='announcement_date', page_size=10, offset=0):
        """
        【新功能】根據多種條件動態查詢文章。
        filters 是一個字典，例如: {'title_keyword': '競賽'}, {'category_name': 補助文件}, {'user_id': 1}
        """
        if order_by not in ['announcement_date', 'click_count']:
            order_by = 'announcement_date'
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                where_clauses = []
                params = []

                if filters:
                    if 'title_keyword' in filters:
                        where_clauses.append("title ILIKE %s")
                        params.append(f"%{filters['title_keyword']}%")
                    if 'category_name' in filters:
                        where_clauses.append("category_name = ANY(%s)")
                        params.append(filters['category_name'])
                    if 'user_id' in filters:
                        where_clauses.append("user_id = %s")
                        params.append(filters['user_id'])
                    if 'status' in filters:
                        where_clauses.append("status = %s")
                        params.append(filters['status'])
                
                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
            
                count_sql = f"SELECT COUNT(*) as total FROM categories WHERE {where_sql} ;"
                cur.execute(count_sql, tuple(params))
                total = cur.fetchone()['total']

                if total == 0:
                    return {'total': 0, "rows": []}
                
                sql = f"""
                    SELECT *
                    FROM posts
                    WHERE {where_sql}
                    ORDER BY {order_by} DESC
                    LIMIT %s OFFSET %s;
                """
                params.extend([page_size, offset])
                
                cur.execute(sql, tuple(params))
                posts = cur.fetchall()
                post_ids = [p['id'] for p in posts]

                if not post_ids:
                    return {'total': total, 'rows': []}

                # 步驟 2: 一次性查詢所有相關的檔案
                cur.execute("SELECT * FROM files WHERE post_id = ANY(%s) AND file_type = 'attachments';", (post_ids,))
                attachments = cur.fetchall()
                attachments_map = {pid: [] for pid in post_ids}
                for f in attachments:
                    attachments_map[f['post_id']].append(f)

                cur.execute("SELECT * FROM files WHERE post_id = ANY(%s) AND file_type = 'images';", (post_ids,))
                images = cur.fetchall()
                images_map = {pid: [] for pid in post_ids}
                for f in images:
                    images_map[f['post_id']].append(f)

                # 步驟 3: 一次性查詢所有相關的標籤
                cur.execute("""
                    SELECT t.* FROM hashtags t
                    JOIN post_hashtags pt ON t.id = pt.hashtag_id
                    WHERE pt.post_id = ANY(%s);
                """, (post_ids,))
                hashtags = cur.fetchall()
                hashtags_map = {pid: [] for pid in post_ids}
                for h in hashtags:
                    hashtags_map[h['post_id']].append(h['tag_name'])
                
                # 步驟 4: 組合結果
                for p in posts:
                    p['attachments'] = attachments_map.get(p['id'], [])
                    p['images'] = images_map.get(p['id'], [])
                    p['hashtags'] = hashtags_map.get(p['id'], [])
                
                return {'total': total, 'rows': posts}
        except psycopg2.Error as e:
            print(f"查詢文章時發生錯誤: {e}")
            return []
    
    # --- 留言板CURD ---
    def insert_bulletin_message(self, content, author_name=None, department=None, campus=None):
        try:
            with self.conn.cursor() as cur:
                sql = "INSERT INTO bulletin_messages (author_name, content, department, campus) VALUES (%s, %s, %s, %s) RETURNING id;"
                author_to_insert = author_name if author_name else "匿名訪客"
                author_to_insert = author_to_insert if author_to_insert and author_to_insert.strip() else None

                cur.execute(sql, (author_to_insert, content, department, campus))
                result = cur.fetchone()
                if result:
                    self.conn.commit()
                    return result[0]
            return None
        except psycopg2.Error as e:
            self.conn.rollback()
            return None

    def get_bulletin_messages(self, target_date=None, campus=None, department=None, page_size=10, offset=0):
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                where_clauses, params = [], []
                if target_date:
                    where_clauses.append("created_at::date = %s")
                    params.append(target_date)
                if campus:
                    where_clauses.append("campus = %s")
                    params.append(campus)
                if department:
                    where_clauses.append("department = %s")
                    params.append(department)
                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
                
                count_sql = f"SELECT COUNT(*) as total FROM bulletin_messages WHERE {where_sql};"
                cur.execute(count_sql, tuple(params))
                total = cur.fetchone()['total']
                
                data_sql = f"SELECT * FROM bulletin_messages WHERE {where_sql} ORDER BY created_at DESC LIMIT %s OFFSET %s;"
                params.extend([page_size, offset])
                cur.execute(data_sql, tuple(params))
                messages = [dict(row) for row in cur.fetchall()]
                return {'total': total, 'rows': messages}
        except psycopg2.Error as e:
            print(f"查詢留言時發生錯誤: {e}")
            return {'total': 0, 'data': []}

    def delete_bulletin_message(self, message_id):
        try:
            with self.conn.cursor() as cur:
                # 注意：您 schema 中的 table 名稱為 bulletin_messages
                cur.execute("DELETE FROM bulletin_messages WHERE id = %s;", (message_id,))
                if cur.rowcount > 0:
                    self.conn.commit()
                    return True
                print("沒有指定id")
            return False
        except psycopg2.Error as e:
            self.conn.rollback()
            print(f"查詢留言時發生錯誤: {e}")
            return False



# --- 主執行區塊 ---
if __name__ == "__main__":
    if not os.path.exists('schema.sql'):
        print("錯誤: 'schema.sql' 檔案不存在。")
    else:
        try:
            # 使用 with 語句來管理 DBHandler 物件
            with DBHandler() as db:
                # --- 在這裡執行所有資料庫操作 --------------------------------------------------------------------
                
                # print("\n--- 1. 初始化資料庫 ---")
                # db.setup_database()

                # print("\n--- 2. 建立使用者 ---")
                # db.create_user("SHD", "edah.sh.department@gmail.com", "shdadmin", permission="manager")

                
                # --- 在這裡執行留言板操作 ------------------------------------------------------------------------

                # print("\n--- 1. 示範留言板功能 ---")
                # db.insert_bulletin_message("路人甲", "這個網站做得真不錯！", campus="義大醫院", department="智慧醫療部")
                # db.insert_bulletin_message("熱心鄉民", "請問 AI 研討會什麼時候報名？", campus="義大癌治療醫院")

                # print("\n--- 2. 刪除指定布告欄訊息 ---")
                # db.delete_bulletin_message(13)

                # print("\n--- 3. 讀取留言板 ---")
                # messages = db.get_bulletin_messages(page_size=10, offset=0, campus=None, department=None)
                # if messages["total"]:
                #     print(f"顯示 {messages['total']} 則留言：")

                #     for msg in messages['rows']:
                #         print(f"  [{msg['created_at'].strftime('%Y-%m-%d %H:%M')}] {msg['author_name']}: {msg['content']}")


                # --- 在這裡執行category操作------------------------------------------------------------------

                # print("\n--- 1. 新增類別 ---")
                # db.insert_category('營養科指標', 'instructions')
                # db.insert_category('人資 Q&A 助手', 'instructions')
                # db.insert_category('評鑑資料查詢系統', 'instructions')
                # db.insert_category('補助文件', 'latest_news')

                # print("\n--- 2. 刪除類別 ---")
                # db.delete_category('補助文件')

                # print("\n--- 3. 顯示類別 ---")
                # messages = db.get_categories_by_type()
                # if messages["total"]:
                #     print(f"顯示 {messages['total']} 個子分類：")

                #     for msg in messages['rows']:
                #         # print(msg)
                #         print(f"類型: {msg['category_type']}, 子分類: {msg['name']}")

                # print("\n--- 4. 顯示某子類別的父類別 ---")
                # messages = db.get_type_by_category('評鑑資料查詢系統')
                # print(messages)

                # --- 在這裡執行post操作------------------------------------------------------------------
                
                # print("\n--- 1. 新增post ---")
                # db.insert_post(title="test", content="<h1>標題^^</h1>", user_id=1, category_name="補助文件", main_image_url=None, attachments=[{'path': 'attachments/a1b2c3d4e5f6_會議記錄.pdf','original_filename':'會議記錄.pdf'}], hashtags=["補助"])

                # print("\n--- 2. 刪除post ---")
                # db.delete_post(13)

                # print("\n--- 3. 更新post ---")
                # db.update_post(post_id=3, new_data={'content':'<p>...</p>','hashtags':['tset1','test2'],'attachments':[{'path':'attachments/123_補助文件.pdf','original_filename':'補助文件.pdf'}]})

                # print("\n--- 4. 顯示post ---")
                # message = db.get_all_posts()
                # print(message)

                # message = db.get_post(3)
                # print(message)

                # message = db.get_posts()
                # print(message)
                print()

        except psycopg2.OperationalError:  
            # 如果連線在 __enter__ 中就失敗了，會在這裡捕獲到
            print("程式因資料庫連線問題而終止。")
        except Exception as e:
            print(f"發生未預期的錯誤: {e}")