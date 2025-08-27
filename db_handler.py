import psycopg2
import psycopg2.extras
import os
import hashlib
from dotenv import load_dotenv
from datetime import date

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

    def __enter__(self):
        """
        進入 'with' 區塊時自動呼叫此方法，建立並返回資料庫連線。
        """
        try:
            print("正在嘗試連接到資料庫...")
            self.conn = psycopg2.connect(**self.config)
            print("資料庫連接成功！")
            return self  # 返回物件本身，以便在 with 區塊中呼叫其方法
        except psycopg2.OperationalError as e:
            print(f"錯誤：無法連接到資料庫 '{self.config.get('dbname')}'.\n{e}")
            # 拋出異常，這樣 with 區塊外的 try...except 才能捕獲到
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        離開 'with' 區塊時自動呼叫此方法，確保連線被關閉。
        """
        if self.conn:
            self.conn.close()
            print("\n資料庫連線已自動關閉。")

    def setup_database(self):
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

    def create_user(self, name, account, password, permission='viewer', department=None):
        """新增使用者，並將密碼雜湊後存入"""
        if not self.conn: return None
        password_hash = self._hash_password(password)
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (name, account, password_hash, permission, department) VALUES (%s, %s, %s, %s, %s) RETURNING id;",
                    (name, account, password_hash, permission, department)
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

    def get_user_permission(self, user_id):
        """取得指定使用者的權限等級"""
        if not self.conn: return None
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT permission FROM users WHERE id = %s;", (user_id,))
                result = cur.fetchone()
                return result[0] if result else None
        except psycopg2.Error as e:
            print(f"獲取權限時發生錯誤: {e}")
            return None

    # --- 文章 CRUD ---
    def create_post(self, user_id, category_id, title, content, **kwargs):
        """新增文章 (只有 manager 和 editor 可以新增)"""
        if not self.conn: return None
        permission = self.get_user_permission(user_id)
        if permission not in ['manager', 'editor']:
            print(f"權限不足：使用者 {user_id} (權限: {permission}) 無法新增文章。")
            return None
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO posts (user_id, category_id, title, content) VALUES (%s, %s, %s, %s) RETURNING id;",
                    (user_id, category_id, title, content)
                )
                post_id = cur.fetchone()[0]
            self.conn.commit()
            print(f"文章 '{title}' 已成功建立，ID: {post_id}")
            return post_id
        except psycopg2.Error as e:
            print(f"新增文章時發生錯誤: {e}")
            self.conn.rollback()
            return None
    def search_posts(self, keyword, source_type=None):
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
    def create_bulletin_message(self, author_name, content, department=None, campus=None):
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
            with DBHandler(DB_CONFIG) as db:
                # --- 在這裡執行所有資料庫操作 ---
                
                # print("\n--- 1. 初始化資料庫 ---")
                # db.setup_database()

                # print("\n--- 2. 建立使用者 ---")
                # db.create_user("SHD", "manager01", "shdadmin", permission="manager")

                # print("\n--- 3. 示範留言板功能 ---")
                # db.create_bulletin_message("路人甲", "這個網站做得真不錯！", campus="義大醫院", department="智慧醫療部")
                # db.create_bulletin_message("熱心鄉民", "請問 AI 研討會什麼時候報名？", campus="義大癌治療醫院")

                print("\n--- 4. 讀取留言板 ---")
                messages = db.get_all_bulletin_messages(10,0)
                if messages["total"]:
                    print(f"顯示最新的 {messages['total']} 則留言：")
                    for msg in messages['rows']:
                        print(f"  [{msg['created_at'].strftime('%Y-%m-%d %H:%M')}] {msg['author_name']}: {msg['content']}")

        except psycopg2.OperationalError:  
            # 如果連線在 __enter__ 中就失敗了，會在這裡捕獲到
            print("程式因資料庫連線問題而終止。")
        except Exception as e:
            print(f"發生未預期的錯誤: {e}")

