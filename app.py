from db_handler import DBHandler
from flask import Flask, jsonify, request, send_from_directory, g, url_for
from flask_cors import CORS
from datetime import datetime, timedelta, timezone
import os
import uuid
from werkzeug.utils import secure_filename
import requests
from bs4 import BeautifulSoup
import base64
import re
import binascii
from functools import wraps
import json
import jwt
from dotenv import load_dotenv


app = Flask(__name__)
CORS(app)
load_dotenv()

app.config['APPLICATION_ROOT'] = 'sh-department-api'
app.config['DOCUMENT_FOLDER'] = './static/'
app.config['JSON_AS_ASCII'] = False

# --- 【關鍵】JWT 設定 ---
# 這個密鑰在正式環境中，絕對不能寫死在程式碼裡，應該從環境變數讀取
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=15)
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=7)

# --- File Upload Configuration ---
UPLOAD_FOLDER = './uploads/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'zip'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# 建立上傳資料夾 (如果不存在)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'images'), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'attachments'), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'files'), exist_ok=True)

# def allowed_file(filename):
#     return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# def save_base64_file(file_data, subfolder):
#     try:
#         filename = file_data.get('filename')
#         base64_str = file_data.get('data')
#         if not all([filename, base64_str]): return None
#         _, encoded = base64_str.split(",", 1)
#         data = base64.b64decode(encoded)
#         unique_filename = f"{uuid.uuid4().hex}_{secure_filename(filename)}"
#         save_path = os.path.join(app.config['UPLOAD_FOLDER'], subfolder, unique_filename)
#         with open(save_path, "wb") as f: f.write(data)
#         return os.path.join(subfolder, unique_filename).replace("\\", "/")
#     except Exception as e:
#         print(f"Base64 解碼或儲存失敗: {e}")
#         return None
# def save_uploaded_file(file, subfolder):
#     """安全地儲存上傳的檔案並返回其相對路徑"""
#     if file and file.filename != '' and allowed_file(file.filename):
#         original_filename = secure_filename(file.filename)
#         unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
#         save_path = os.path.join(app.config['UPLOAD_FOLDER'], subfolder, unique_filename)
#         file.save(save_path)
#         return os.path.join(subfolder, unique_filename).replace("\\", "/")
#     return None



# def scrape_and_save_image(html_content):
#     """從 HTML 內容中解析、下載並儲存第一張圖片"""
#     soup = BeautifulSoup(html_content, 'html.parser')
#     img_tag = soup.find('img')
    
#     if not img_tag or not img_tag.get('src'):
#         return None

#     image_url = img_tag['src']
#     try:
#         response = requests.get(image_url, stream=True, timeout=5)
#         response.raise_for_status()
        
#         original_filename = secure_filename(image_url.split('/')[-1].split('?')[0])
#         if not original_filename: original_filename = "scraped_image.jpg"

#         unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
#         save_path = os.path.join(app.config['UPLOAD_FOLDER'], 'images', unique_filename)
        
#         with open(save_path, 'wb') as f:
#             for chunk in response.iter_content(chunk_size=8192):
#                 f.write(chunk)
        
#         print(f"成功從 {image_url} 抓取圖片")
#         return os.path.join('images', unique_filename).replace("\\", "/")
#     except requests.RequestException as e:
#         print(f"抓取圖片失敗: {e}")
#         return None

# --- 【新】JWT 權杖驗證裝飾器 ---
# def token_required(f):
#     @wraps(f)
#     def decorated(*args, **kwargs):
#         token = None
#         # 檢查 'Authorization' 標頭是否存在，並以 'Bearer ' 開頭
#         if 'Authorization' in request.headers:
#             auth_header = request.headers['Authorization']
#             try:
#                 token = auth_header.split(" ")[1]
#             except IndexError:
#                 return jsonify({'status': 401, 'message': '無效的 Token 格式', 'success': False}), 401
        
#         if not token:
#             return jsonify({'status': 401, 'message': '未提供 Token', 'success': False}), 401

#         try:
#             # 解碼並驗證 Token
#             payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
#             # 將使用者資訊存入 g，方便後續路由使用
#             g.user = {'id': payload['sub'], 'permission': payload['permission']}
#         except jwt.ExpiredSignatureError:
#             return jsonify({'status': 401, 'message': 'Token 已過期', 'success': False}), 401
#         except jwt.InvalidTokenError:
#             return jsonify({'status': 401, 'message': '無效的 Token', 'success': False}), 401
        
#         return f(*args, **kwargs)
#     return decorated


def token_required(required_permissions=None):
    if required_permissions is None:
        required_permissions = []
    elif isinstance(required_permissions, str):
        required_permissions = [required_permissions]

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = None
            if 'Authorization' in request.headers:
                auth_header = request.headers['Authorization']
                try:
                    token = auth_header.split(" ")[1]
                except IndexError:
                    return jsonify({'status': 401, 'message': '無效的 Token 格式 (應為 Bearer <token>)', 'success': False}), 401
            
            if not token:
                return jsonify({'status': 401, 'message': '未提供 Token', 'success': False}), 401

            try:
                payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
                g.user = {'id': payload['sub'], 'permission': payload['permission']}

                # 【新】在這裡直接進行權限等級檢查
                if required_permissions and g.user['permission'] not in required_permissions:
                    return jsonify({'status': 403, 'message': f"權限不足，此操作需要 {required_permissions} 等級。", 'success': False}), 403

            except jwt.ExpiredSignatureError:
                return jsonify({'status': 401, 'message': 'Token 已過期', 'success': False}), 401
            except jwt.InvalidTokenError:
                return jsonify({'status': 401, 'message': '無效的 Token', 'success': False}), 401
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/api/test')
def index():
    return jsonify({
        'status': 200,
        'message': "sh-department-api|Test endpoint is working",
        'result': [],
        'success': True
    }), 200

# --- 【新功能】Login Route ---
@app.route('/api/login', methods=['POST'])
def login_route():
    data = request.get_json()
    if not data or not data.get('account') or not data.get('password'):
        return jsonify({'status': 400, 'message': '缺少帳號或密碼', 'success': False}), 400

    with DBHandler() as db:
        user = db.check_password(data['account'], data['password'])
        if user:
            access_token_payload = {
                'sub': user['id'],
                'permission': user['permission'],
                'iat': datetime.now(timezone.utc),                                              # create
                'exp': datetime.now(timezone.utc) + app.config['JWT_ACCESS_TOKEN_EXPIRES']      # access expire
            }
            access_token = jwt.encode(access_token_payload, app.config['SECRET_KEY'], algorithm="HS256")

            refresh_token = str(uuid.uuid4())
            refresh_token_exp = datetime.now(timezone.utc) + app.config['JWT_REFRESH_TOKEN_EXPIRES']    # refresh expire
            db.store_refresh_token(user['id'], refresh_token, refresh_token_exp)
            
            db.create_log(user['id'], 'login', ip_address=request.remote_addr)

            return jsonify({
                'status': 200,
                'message': '登入成功',
                'access_token': access_token,
                'refresh_token': refresh_token,
                'success': True
            })
        else:
            return jsonify({'status': 401, 'message': '帳號或密碼錯誤', 'success': False}), 401

@app.route('/api/refresh', methods=['POST'])
def refresh_route():
    data = request.get_json()
    refresh_token = data.get('refresh_token')
    if not refresh_token:
        return jsonify({'status': 400, 'message': '未提供 Refresh Token', 'success': False}), 400
        
    with DBHandler() as db:
        user_id = db.validate_refresh_token(refresh_token)
        if user_id:
            user = db.find_user(user_id=user_id)
            access_token_payload = {
                'sub': user['id'],
                'permission': user['permission'],
                'iat': datetime.now(timezone.utc),
                'exp': datetime.now(timezone.utc) + app.config['JWT_ACCESS_TOKEN_EXPIRES']
            }
            access_token = jwt.encode(access_token_payload, app.config['SECRET_KEY'], algorithm="HS256")
            
            return jsonify({'status': 200, 'access_token': access_token, 'success': True})
        else:
            return jsonify({'status': 401, 'message': '無效或已過期的 Refresh Token', 'success': False}), 401

@app.route('/api/logout', methods=['POST'])
def logout_route():
    data = request.get_json()
    refresh_token = data.get('refresh_token')
    user_id = data.get('id')
    if refresh_token:
        with DBHandler() as db:
            db.delete_refresh_token(refresh_token)
            db.create_log(user_id, 'logout', ip_address=request.remote_addr)
    return jsonify({'status': 200, 'message': '登出成功', 'success': True})

@app.route('/api/signup', method=['POST'])
def signup_route():
    return None

@app.route('/api/signout', method=['DELETE'])
def signup_route():
    return None


# --- category CURD ---

# 新增父分類: 要手動新增enum type
@app.route('/api/categories', methods=['GET', 'POST'])
def handle_categories():
    if request.method == 'GET':
        category_type = request.args.get('category_type')
        with DBHandler() as db:
            categories = db.get_categories_by_type(category_type)
            
            return jsonify({'status': 200, 'message': "success", 'result': categories, 'success': True})

    if request.method == 'POST':
        @permission_required('manager')
        def create():
            data = request.get_json()
            if not data or not all(k in data for k in ['name', 'category_type']):
                return jsonify({'status': 400, 'message': "缺少欄位: name, category_type", 'success': False}), 400
            with DBHandler() as db:
                cat_id = db.insert_category(data['name'], data['category_type'])
                if cat_id:
                    return jsonify({'status': 200, 'message': '分類建立成功', 'id': cat_id, 'success': True}), 200
                else:
                    return jsonify({'status': 400, 'message': '無法建立分類', 'success': False}), 400
        return create()

@app.route('/api/categories/<string:category_name>', methods=['DELETE'])
@permission_required('manager')
def handle_delete_category(category_name):
    with DBHandler() as db:
        success = db.delete_category(category_name)
        if success:
            return jsonify({'status': 200, 'message': '分類刪除成功', 'success': True})
        else:
            return jsonify({'status': 404, 'message': '找不到要刪除的分類', 'success': False}), 404

# --- upload file / attachment / image_url ---

@app.route('/api/upload', methods=['POST'])
@permission_required(['manager', 'editor']) # 建議加上權限控管
def upload_file():
    """
    專門用來處理檔案上傳的 API。
    接收一個 multipart/form-data 請求，其中包含一個名為 'file' 的檔案。
    """
    if 'files' not in request.files:
        return jsonify({'status': 400, 'message': '請求中未包含檔案', 'success': False}), 400
    
    uploaded_files = request.files.getlist('files')
    if not uploaded_files:
        return jsonify({'status': 400, 'message': '未選擇檔案', 'success': False}), 400

    file_records = []
    try:
        with DBHandler() as db:
            for file in uploaded_files:
                original_filename = secure_filename(file.filename)
                subfolder = request.args.get("file_type")
                
                unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
                relative_path = os.path.join(subfolder, unique_filename).replace("\\", "/")
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], relative_path)
                file.save(save_path)

                # 存入資料庫並取得 file_id
                file_id = db.upload_file(save_path, original_filename, subfolder)
                file_records = []
                if file_id:
                    file_records.append({
                        'id': file_id,
                        'path': save_path,
                        'original_filename': original_filename
                    })
    except Exception as e:
        return jsonify({'status': 500, 'message': f"檔案處理時發生錯誤: {e}", 'success': False}), 500
    
    return jsonify({'status': 200, 'message': 'upload success', 'files': file_records, 'success': True}), 200

@app.route('/api/files', methods=['GET'])
def get_unattached_files_route():
    """【新功能】取得所有未關聯到文章的檔案 (媒體庫)"""
    try:
        filters = {k: v for k, v in request.args.items() if k in ['post_id', 'file_type', 'original_filename']}
        page_size = request.args.get('page_size', 10, type=int)
        page = request.args.get('page', 1, type=int)
        offset = (page - 1) * page_size
        with DBHandler() as db:
            files = db.get_files(filters=filters, page_size=page_size, offset=offset)

            return jsonify({'status': 200, 'message': 'success', 'files': files, 'success': True})
    except Exception as e:
        return jsonify({'status': 500, 'message': str(e), 'success': False}), 500

@app.route('/api/files/<int:file_id>', methods=['DELETE'])
@permission_required(['manager', 'editor'])
def delete_file_route(file_id):
    """【新功能】刪除單一檔案紀錄及其在伺服器上的實體檔案"""
    try:
        with DBHandler() as db:
            # 權限檢查：只有 manager 或檔案擁有者可以刪除
            owner_id = db.get_file_owner(file_id)
            # 如果 owner_id 是 None，表示檔案未關聯或不存在，只有 manager 能刪除
            if owner_id is not None and g.user['permission'] != 'manager' and g.user['id'] != owner_id:
                 return jsonify({'status': 403, 'message': '權限不足，只能刪除自己文章中的檔案', 'success': False}), 403
            
            # 刪除實體檔案 (此為可選步驟，但建議執行)
            # ... 這裡應加入根據 file_id 查詢 file_path 並從硬碟刪除檔案的邏輯 ...
            file = db.get_file(file_id)
            full_path_to_file = os.path.join(app.config['UPLOAD_FOLDER'], file["file_path"])
            os.remove(full_path_to_file)

            # 從資料庫刪除紀錄
            success = db.delete_file(file_id)
        
        if success:
            return jsonify({'status': 200, 'message': '檔案刪除成功', 'success': True})
        else:
            return jsonify({'status': 404, 'message': '找不到要刪除的檔案', 'success': False}), 404
    except Exception as e:
        return jsonify({'status': 500, 'message': str(e), 'success': False}), 500


# --- Static File Route ---
# 當前端讀取到HTML的<img src=...>，就會自動向您的伺服器發送一個新的 GET 請求，請求的網址就是 /uploads/<path:filepath>
@app.route('/uplo/<int:file_id>')
def serve_uploaded_file(file_id):
    """提供一個路由來讓外界可以存取 uploads 資料夾中的檔案"""
    try:
        with DBHandler() as db:
            file = db.get_file(file_id)
            folder = os.path.join(app.config['UPLOAD_FOLDER'], file['file_type'])
            print(folder)
            return send_from_directory(folder, os.path.split(file['file_path']))
    except Exception as e:
        return jsonify({
                'status': 404,
                'error': "檔案不存在",
                'success': False
            }), 404
 

# --- posts CURD ---
@app.route('/api/posts', methods=['GET', 'POST'])
def handle_posts():
    if request.method == 'GET':
        filters = {}
        category_type = request.args.get('category_type')
        if category_type:
            with DBHandler() as db:
                categories = db.get_categories_by_type(category_type)
                filters['category_name'] = [c['name'] for c in categories]
        else:
            category_names = request.args.get('category_name')
            if category_names:
                filters['category_name'] = category_names

        if request.args.get('title_keyword'):
            filters['title_keyword'] = request.args.get('title_keyword')
        if request.args.get('user_id'):
            filters['user_id'] = request.args.get('user_id', type=int)
        if request.args.get('status'):
            filters['status'] = request.args.get('status')

        order_by = request.args.get('order_by', 'announcement_date', type=str)
        page_size = request.args.get('page_size', 10, type=int)
        page = request.args.get('page', 1, type=int)
        offset = (page - 1) * page_size
        try:
            with DBHandler() as db:
                posts = db.get_posts(filters=filters, order_by = order_by, page_size=page_size, offset=offset)
                
                # for post in posts.get('rows', []):
                #     if post.get('attchments'):
                #         for f in post['attchments']:
                #             f['url'] = os.path.join(app.config['UPLOAD_FOLDER'], f['file_path'])

                #     if post.get('images'):
                #         for f in post['images']:
                #             f['url'] = os.path.join(app.config['UPLOAD_FOLDER'], f['file_path'])
                
                return jsonify({'status': 200, 'result': posts, 'success': True})
        except Exception as e:
            return jsonify({'status': 500, 'message': str(e), 'success': False}), 500

    if request.method == 'POST':
        @permission_required(['manager', 'editor'])
        def create():
            data = request.get_json()
            
            required = ['title', 'content', 'category_name', 'status']
            if not data or not all(k in data for k in required):
                return jsonify({'status': 400, 'message': f"缺少欄位: {required}", 'success': False}), 400
            
            # 處理 main_image
            # soup = BeautifulSoup(data['content'], 'html.parser')
            # img_tag = soup.find('img')
            # main_image_url = img_tag['src'] if img_tag else None
            # main_image_url = save_uploaded_file(request.files['main_image'], 'images') if 'main_image_url' in request.file else scrape_and_save_image(data.get('content'))
            
            # 處理 hashtag
            hashtags_list = [f for f in data.get('hashtags', [])]

            # 處理 file id, main image 和 attachments放同個list
            file_id_list = [f for f in data.get('file_ids', [])]


            with DBHandler() as db:
                post_id = db.create_post(
                    title=data['title'],
                    content=data['content'],
                    user_id=g.user['id'],
                    category_name=data['category_name'],
                    status = data['status'],
                    # main_image_url=main_image_url,
                    # attachments=attachments_list,
                    hash_tags = hashtags_list,
                    file_ids = file_id_list
                    )
            if post_id:
                return jsonify({'status': 200, 'message': "文章建立成功", 'id': post_id, 'success': True}), 201
            else:
                return jsonify({'status': 500, 'message': "無法建立文章", 'success': False}), 500
        return create()

@app.route('/api/posts/<int:post_id>', methods=['GET', 'PUT', 'DELETE'])
def handle_post_by_id(post_id):
    if request.method == 'GET':
        try:
            with DBHandler() as db:
                post = db.get_post(post_id)

            if post:
                # 將檔案路徑轉換為完整的 URL
                # if post.get('attchments'):
                #     for f in post['attchments']:
                #         f['url'] = os.path.join(app.config['UPLOAD_FOLDER'], f['file_path'])

                #     if post.get('images'):
                #         for f in post['images']:
                #            f['url'] = os.path.join(app.config['UPLOAD_FOLDER'], f['file_path'])
                return jsonify({'status': 200, 'result': post, 'success': True})
            else:
                return jsonify({'status': 404, 'message': '找不到文章', 'success': False}), 404
        except Exception as e:
            return jsonify({'status': 500, 'message': str(e), 'success': False}), 500
        
    @permission_required(['manager', 'editor'])
    def protected_operation():
        with DBHandler() as db:
            owner_id = db.get_post_owner(post_id)
            if not owner_id:
                return jsonify({'status': 404, 'message': '找不到文章', 'success': False}), 404
            
            if g.user['permission'] != 'manager' and g.user['id'] != owner_id:
                return jsonify({'status': 403, 'message': '權限不足，只能操作自己的文章', 'success': False}), 403

            if request.method == 'PUT':
                data = request.get_json()

                required = ['title', 'content', 'category_name']
                if not data or not all(k in data for k in required):
                    return jsonify({'status': 400, 'message': f"缺少欄位: {required}", 'success': False}), 400
            
                # 準備要傳遞給 DBHandler 的資料
                update_data_for_db = {}
                
                # 處理基本欄位
                for field in required:
                    if field in data:
                        update_data_for_db[field] = data[field]
                
                # 處理主圖
                # soup = BeautifulSoup(data['content'], 'html.parser')
                # img_tag = soup.find('img')
                # main_image_url = img_tag['src'] if img_tag else None
                # update_data_for_db['main_image_url'] = save_uploaded_file(request.files['main_image'], 'images') if 'main_image_url' in request.file else scrape_and_save_image(data.get('content'))
                
                
                # 處理標籤
                hashtags_list = [f for f in data.get('hashtags', [])]
                update_data_for_db['hashtags'] = hashtags_list

                success = db.update_post(post_id, update_data_for_db)
                return jsonify({'status': 200, 'message': '文章更新成功', 'success': True}) if success else jsonify({'status': 500, 'message': '更新失敗', 'success': False}), 500

            if request.method == 'DELETE':
                success = db.delete_post(post_id)
                return jsonify({'status': 200, 'message': '文章刪除成功', 'success': True}) if success else jsonify({'status': 404, 'message': '刪除失敗', 'success': False}), 404
    return protected_operation()

# --- bulletin CURD ---

@app.route('/api/bulletin_messages', methods=['GET', 'POST'])
def handle_bulletin_messages():
    if request.method == 'GET':
        try:
            target_date_str = request.args.get('date')
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date() if target_date_str else None
            page = request.args.get('page', 1, type=int)
            page_size = request.args.get('page_size', 10, type=int)
            offset = (page - 1) * page_size
            with DBHandler() as db:
                bulletins = db.get_bulletin_messages(
                    target_date=target_date, campus=request.args.get('campus'),
                    department=request.args.get('department'), page_size=page_size, offset=offset
                )
            return jsonify({'status': 200, "message": "success", 'result': bulletins, 'success': True})
        except Exception as e:
            return jsonify({'status': 400, 'message': str(e), 'success': False}), 400

    if request.method == 'POST':
        data = request.get_json()
        if not data or not data.get('content'):
            return jsonify({'status': 400, 'message': "缺少 content 欄位", 'success': False}), 400
        with DBHandler() as db:
            message_id = db.insert_bulletin_message(
                author_name=data.get('author_name'), content=data.get('content'),
                department=data.get('department'), campus=data.get('campus')
            )
        if message_id:
            return jsonify({'status': 201, 'message': "留言新增成功", 'id': message_id, 'success': True}), 201
        else:
            return jsonify({'status': 500, 'message': "無法新增留言", 'success': False}), 500
  

@app.route('/api/bulletin_messages/<int:message_id>', methods=['DELETE'])
def handle_delete_bulletin_message(message_id):
    try:
        with DBHandler() as db:
            success = db.delete_bulletin_message(message_id)
            if success:
                return jsonify({'status': 200, 'message': "留言刪除成功", 'success': True})
            else:
                return jsonify({'status': 404, 'message': "找不到要刪除的留言或刪除失敗", 'success': False}), 404
    except Exception as e:
        return jsonify({'status': 500, 'message': '伺服器發生未預期的錯誤'}), 500
    
if __name__ == "__main__":
    app.run(debug=True, port=5004)