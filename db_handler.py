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
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
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

        

    # --- 分類管理 ---
    # --- 父分類: latest_news、instructions ---

    def insert_category(self, name: str, category_type: str):
        try:
            with self.conn.cursor() as cur:
                sql = "INSERT INTO categories (name, category_type) VALUES (%s, %s) RETURNING id;"
                cur.execute(sql, (name, category_type))
                result = cur.fetchone()
                if result:
                    self.conn.commit()
                    return result[0]
                return None
        except psycopg2.Error as e:
            print(f"新增分類時發生錯誤: {e}")
            self.conn.rollback()
            return None

    def delete_category(self, category_id):
        try:
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM categories WHERE id = %s;", (category_id,))
                if cur.rowcount > 0:
                    self.conn.commit()
                    return True
            return False
        except psycopg2.Error as e:
            self.conn.rollback()
            return False

    def get_categories_by_type(self, category_type: str):
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if category_type:
                    count_sql = f"SELECT COUNT(*) as total FROM categories WHERE category_type = %s;"
                    cur.execute(count_sql, (category_type,))
                    total = cur.fetchone()['total']

                    cur.execute("SELECT id, name FROM categories WHERE category_type = %s;", (category_type,))
                    messages = [dict(row) for row in cur.fetchall()]
                    return {'total': total, 'rows': messages}   
                else:
                    count_sql = f"SELECT COUNT(*) as total FROM categories;"
                    cur.execute(count_sql)
                    total = cur.fetchone()['total']

                    cur.execute("SELECT id, name, category_type FROM categories;")
                    messages = [dict(row) for row in cur.fetchall()]
                    return {'total': total, 'rows': messages}
                
        except psycopg2.Error as e:
            print(f"尋找分類時發生錯誤: {e}")
            return []

    # --- 文章 CRUD ---
    def insert_post(self, title, content, user_id, category_id, main_image_url=None, attachments=None, hashtags=None):
        try:
            with self.conn.cursor() as cur:
                # 新增 post 主體並取得返回的 post ID
                post_sql = """
                    INSERT INTO posts (title, content, user_id, category_id, main_image_url)
                    VALUES (%s, %s, %s, %s, %s) RETURNING id;
                """
                cur.execute(post_sql, (title, content, user_id, category_id, main_image_url))
                
                result = cur.fetchone()
                if not result:
                    raise Exception("新增 Post 後未能取得返回的 ID")
                post_id = result[0]

                # 如果有提供附件，則將它們新增到 attachments 表
                if attachments and isinstance(attachments, list):
                    attachment_sql = "INSERT INTO attachments (post_id, file_path, original_filename) VALUES %s;"
                    args_list = [(post_id, att.get('path'), att.get('original_filename')) for att in attachments]
                    psycopg2.extras.execute_values(cur, attachment_sql, args_list)

                # 處理標籤
                if hashtags and isinstance(hashtags, list):
                    tag_ids = []
                    for tag_name in hashtags:
                        cur.execute("SELECT id FROM hashtags WHERE tag_name = %s;", (tag_name,))
                        tag_result = cur.fetchone()
                        if tag_result:
                            tag_ids.append(tag_result[0])
                        else:
                            cur.execute("INSERT INTO hashtags (tag_name) VALUES (%s) RETURNING id;", (tag_name,))
                            tag_ids.append(cur.fetchone()[0])

                    sql_post_tag = "INSERT INTO post_hashtags (post_id, hashtag_id) VALUES %s;"
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
        """
        【擴充功能】更新文章，包含文字、主圖、附件和標籤。
        這是一個完整的交易操作。
        """
        if not self.conn: return False
        try:
            with self.conn.cursor() as cur:
                # 步驟 1: 更新 posts 表中的基本欄位
                updatable_fields = ['title', 'content', 'main_image_url', 'category_id']
                set_parts = []
                params = []
                for field in updatable_fields:
                    if field in new_data:
                        set_parts.append(f"{field} = %s")
                        params.append(new_data[field])
                
                if set_parts:
                    params.append(post_id)
                    sql_update_post = f"UPDATE posts SET {', '.join(set_parts)}, updated_at = NOW() WHERE id = %s;"
                    cur.execute(sql_update_post, tuple(params))

                # 步驟 2: 如果提供了 attachments，則完全取代舊的
                if 'attachments' in new_data:
                    # 先刪除所有舊附件
                    cur.execute("DELETE FROM attachments WHERE post_id = %s;", (post_id,))
                    # 如果新附件列表不為空，則新增它們
                    new_attachments = new_data['attachments']
                    if new_attachments and isinstance(new_attachments, list):
                        attach_sql = "INSERT INTO attachments (post_id, file_path, original_filename) VALUES %s;"
                        attach_data = [(post_id, att.get('path'), att.get('original_filename')) for att in new_attachments]
                        psycopg2.extras.execute_values(cur, attach_sql, attach_data)

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
        
        
    def get_all_posts(self, order_by='announcement_date', page_size=10, offset=0):
        """取得所有文章，可指定排序方式"""
        if order_by not in ['announcement_date', 'click_count']:
            order_by = 'announcement_date'
        
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                sql = f"SELECT id, title, content, main_image_url, user_id, category_id, click_count, announcement_date FROM posts ORDER BY {order_by} DESC LIMIT %s OFFSET %s;"
                cur.execute(sql, (page_size, offset))
                return [dict(row) for row in cur.fetchall()]
        except psycopg2.Error as e:
            print(f"取得所有文章時發生錯誤: {e}")
            return []
        
    def get_post(self, post_id):
        try:
            with self.conn.cursor(psycopg2.extras.RealDictCursor) as cur:
                sql = f"SELECT id, title, content, main_image_url, user_id, category_id, click_count, announcement_date FROM posts WHERE id = %s;"
                cur.execute(sql, (post_id))
                return cur.fetchall()
        except psycopg2.Error as e:
            print(f"取得所有文章時發生錯誤: {e}")
            return None
            
        

    def get_posts(self, filters=None, page_size=10, offset=0):
        """
        【新功能】根據多種條件動態查詢文章。
        filters 是一個字典，例如: {'title_keyword': '競賽'}, {'category_id': 1}, {'user_id': 1}
        """
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                where_clauses = []
                params = []

                if filters:
                    if 'title_keyword' in filters:
                        where_clauses.append("title ILIKE %s")
                        params.append(f"%{filters['title_keyword']}%")
                    if 'category_id' in filters:
                        where_clauses.append("category_id = %s")
                        params.append(filters['category_id'])
                    if 'user_id' in filters:
                        where_clauses.append("user_id = %s")
                        params.append(filters['user_id'])
                
                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
                
                sql = f"""
                    SELECT id, title, content, main_image_url, user_id, category_id, click_count, announcement_date
                    FROM posts
                    WHERE {where_sql}
                    ORDER BY announcement_date DESC
                    LIMIT %s OFFSET %s;
                """
                params.extend([page_size, offset])
                
                cur.execute(sql, tuple(params))
                return [dict(row) for row in cur.fetchall()]
        except psycopg2.Error as e:
            print(f"查詢文章時發生錯誤: {e}")
            return []
    
    # --- 留言板CURD ---
    def insert_bulletin_message(self, author_name, content, department=None, campus=None):
        try:
            with self.conn.cursor() as cur:
                sql = "INSERT INTO bulletin_messages (author_name, content, department, campus) VALUES (%s, %s, %s, %s) RETURNING id;"
                author_to_insert = author_name if author_name and author_name.strip() else None
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
            return False
        except psycopg2.Error as e:
            self.conn.rollback()
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
                # db.delete_bulletin_message(2)

                # print("\n--- 3. 讀取留言板 ---")
                # messages = db.get_bulletin_messages(page_size=10,offset=0,campus='義大醫院')
                # if messages["total"]:
                #     print(f"顯示'義大醫院' 的 {messages['total']} 則留言：")

                #     for msg in messages['rows']:
                #         print(f"  [{msg['created_at'].strftime('%Y-%m-%d %H:%M')}] {msg['author_name']}: {msg['content']}")


                # --- 在這裡執行category操作------------------------------------------------------------------

                # print("\n--- 1. 新增類別 ---")
                # db.insert_category('營養科指標-說明文件', 'instructions')
                # db.insert_category('人資 Q&A 助手-說明文件', 'instructions')
                # db.insert_category('評鑑資料查詢系統-說明文件', 'instructions')
                # db.insert_category('補助文件下載', 'latest_news')

                # print("\n--- 2. 刪除類別 ---")
                # db.delete_category(4)

                # print("\n--- 3. 顯示類別 ---")
                # messages = db.get_categories_by_type('latest_news')
                # if messages["total"]:
                #     print(f"顯示'義大醫院' 的 {messages['total']} 則留言：")

                #     for msg in messages['rows']:
                #         print(msg)

                # --- 在這裡執行post操作------------------------------------------------------------------
                
                # print("\n--- 1. 新增post ---")
                # db.insert_post(title="test", content="<h1>標題^^</h1>", user_id=1, category_id=2, main_image_url=None, attachments=[{'path': 'attachments/a1b2c3d4e5f6_會議記錄.pdf','original_filename':'會議記錄.pdf'}], hashtags=["補助"])

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