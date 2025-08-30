from db_handler import DBHandler
from flask import Flask, jsonify, request, send_from_directory, g, url_for
from flask_cors import CORS
from datetime import datetime, date
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

app = Flask(__name__)
CORS(app)


app.config['APPLICATION_ROOT'] = 'sh-department-api'
app.config['DOCUMENT_FOLDER'] = './static/'
app.config['JSON_AS_ASCII'] = False

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


# --- Permission Decorator (安全驗證) ---
def permission_required(required_permissions):
    if isinstance(required_permissions, str):
        required_permissions = [required_permissions]
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # user_id = request.headers.get('X-User-ID')
            # if not user_id:
            #     return jsonify({'status': 401, 'message': '未提供使用者身分 (缺少 X-User-ID 標頭)', 'success': False}), 401
            # try:
            #     with DBHandler() as db:
            #         user = db.find_user(user_id=int(user_id))
            #     if not user:
            #         return jsonify({'status': 401, 'message': '無效的使用者 ID', 'success': False}), 401
            #     g.user = user
            #     if user['permission'] not in required_permissions and user['permission'] != 'manager':
            #         return jsonify({'status': 403, 'message': f"權限不足，此操作需要 {required_permissions} 等級。", 'success': False}), 403
            # except Exception as e:
            #     return jsonify({'status': 500, 'message': f"驗證使用者身分時發生錯誤: {e}", 'success': False}), 500
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

@app.route('/api/categories/<int:category_id>', methods=['DELETE'])
@permission_required('manager')
def handle_delete_category(category_id):
    with DBHandler() as db:
        success = db.delete_category(category_id)
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
    if 'file' not in request.files:
        return jsonify({'status': 400, 'message': '請求中未包含檔案', 'success': False}), 400
    
    files = request.files.getlist('files', [])
    if files == []:
        return jsonify({'status': 400, 'message': '未選擇檔案', 'success': False}), 400

    if files:
        subfolder = request.form.get('subfolder')

        attachments_list = []    
        for file in files:
            original_filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], subfolder, unique_filename)
            file.save(save_path)

            # 產生一個可以讓前端直接使用的公開 URL
            # 注意：這需要您設定一個靜態檔案路由 (如下面的 /uploads/<path:filename>))
            attachments_list.append({
                            'path': url_for('serve_uploaded_file', filename=f"{subfolder}/{unique_filename}", _external=True),
                            'original_filename': original_filename
                        })

        if subfolder in ['attachments','files']:
            with DBHandler() as db:
                success = db.upload_file(files)
                if not success: return jsonify({'status': 500, 'message': '檔案上傳資料庫失敗', 'success': False}), 500

        return jsonify({
            'status': 201,
            'message': '檔案上傳成功',
            'url': attachments_list,
            'success': True
        }), 201
    
    return jsonify({'status': 500, 'message': '檔案上傳失敗', 'success': False}), 500



# --- Static File Route ---
@app.route('/uploads/<path:filename>')
def serve_uploaded_file(filename):
    """提供一個路由來讓外界可以存取 uploads 資料夾中的檔案"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
 

# --- posts CURD ---
@app.route('/api/posts', methods=['GET', 'POST'])
def handle_posts():
    if request.method == 'GET':
        filters = {k: v for k, v in request.args.items() if k in ['title_keyword', 'category_id', 'user_id']}
        order_by = request.args.get('order_by', 'announcement_date', type=str)
        page_size = request.args.get('page_size', 10, type=int)
        page = request.args.get('page', 1, type=int)
        offset = (page - 1) * page_size
        with DBHandler() as db:
            posts = db.get_posts(filters=filters, order_by = order_by, page_size=page_size, offset=offset)
            return jsonify({'status': 200, 'message': "success", 'result': posts, 'success': True})

    if request.method == 'POST':
        @permission_required(['manager', 'editor'])
        def create():
            # 1. 從 request.form 中取得 JSON 字串
            metadata_str = request.form.get('metadata')
            if not metadata_str:
                return jsonify({'message': '缺少 metadata 欄位'}), 400
            try:
                data = json.loads(metadata_str)
            except json.JSONDecodeError:
                return jsonify({'message': 'metadata 格式錯誤，無法解析為 JSON'}), 400

            required = ['title', 'content', 'category_id']
            if not data or not all(k in data for k in required):
                return jsonify({'status': 400, 'message': f"缺少欄位: {required}", 'success': False}), 400
            
            # 處理 main_image
            soup = BeautifulSoup(data['content'], 'html.parser')
            img_tag = soup.find('img')
            main_image_url = img_tag['src'] if img_tag else None
            # main_image_url = save_uploaded_file(request.files['main_image'], 'images') if 'main_image_url' in request.file else scrape_and_save_image(data.get('content'))
            
            hashtags_list = [f for f in data.get('hashtags', [])]
            

            with DBHandler() as db:
                post_id = db.create_post(
                    title=data['title'],
                    content=data['content'],
                    user_id=g.user['id'],
                    category_id=data['category_id'],
                    main_image_url=main_image_url,
                    # attachments=attachments_list,
                    hash_tags = hashtags_list
                    )
            if post_id:
                return jsonify({'status': 200, 'message': "文章建立成功", 'id': post_id, 'success': True}), 201
            else:
                return jsonify({'status': 500, 'message': "無法建立文章", 'success': False}), 500
        return create()

@app.route('/api/posts/<int:post_id>', methods=['GET', 'PUT', 'DELETE'])
def handle_post_by_id(post_id):
    if request.method == 'GET':
        with DBHandler() as db:
            post = db.get_post(post_id)
            return jsonify({'status': 200, "message": "success", 'result': post, 'success': True}) if post else jsonify({'status': 404, 'message': '找不到文章', 'success': False}), 404

    @permission_required(['manager', 'editor'])
    def protected_operation():
        with DBHandler() as db:
            owner_id = db.get_post_owner(post_id)
            if not owner_id:
                return jsonify({'status': 404, 'message': '找不到文章', 'success': False}), 404
            
            if g.user['permission'] != 'manager' and g.user['id'] != owner_id:
                return jsonify({'status': 403, 'message': '權限不足，只能操作自己的文章', 'success': False}), 403

            if request.method == 'PUT':
                metadata_str = request.form.get('metadata')
                if not metadata_str:
                    return jsonify({'message': '缺少 metadata 欄位'}), 400
                try:
                    data = json.loads(metadata_str)
                except json.JSONDecodeError:
                    return jsonify({'message': 'metadata 格式錯誤，無法解析為 JSON'}), 400

                required = ['title', 'content', 'category_id']
                if not data or not all(k in data for k in required):
                    return jsonify({'status': 400, 'message': f"缺少欄位: {required}", 'success': False}), 400
            
                # 準備要傳遞給 DBHandler 的資料
                update_data_for_db = {}
                
                # 處理基本欄位
                for field in ['title', 'content', 'category_id']:
                    if field in data:
                        update_data_for_db[field] = data[field]
                
                # 處理主圖
                soup = BeautifulSoup(data['content'], 'html.parser')
                img_tag = soup.find('img')
                main_image_url = img_tag['src'] if img_tag else None
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