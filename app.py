from db_handler import DBHandler
from flask import Flask, jsonify, request, send_from_directory, g
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

app = Flask(__name__)
CORS(app)


app.config['APPLICATION_ROOT'] = 'sh-department-api'
app.config['DOCUMENT_FOLDER'] = './static/'
app.config['JSON_AS_ASCII'] = False

# --- File Upload Configuration ---
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'zip'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# 建立上傳資料夾 (如果不存在)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'images'), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'attachments'), exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_base64_file(file_data, subfolder):
    try:
        filename = file_data.get('filename')
        base64_str = file_data.get('data')
        if not all([filename, base64_str]): return None
        _, encoded = base64_str.split(",", 1)
        data = base64.b64decode(encoded)
        unique_filename = f"{uuid.uuid4().hex}_{secure_filename(filename)}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], subfolder, unique_filename)
        with open(save_path, "wb") as f: f.write(data)
        return os.path.join(subfolder, unique_filename).replace("\\", "/")
    except Exception as e:
        print(f"Base64 解碼或儲存失敗: {e}")
        return None


def scrape_and_save_image(html_content):
    """從 HTML 內容中解析、下載並儲存第一張圖片"""
    soup = BeautifulSoup(html_content, 'html.parser')
    img_tag = soup.find('img')
    
    if not img_tag or not img_tag.get('src'):
        return None

    image_url = img_tag['src']
    try:
        response = requests.get(image_url, stream=True, timeout=5)
        response.raise_for_status()
        
        original_filename = secure_filename(image_url.split('/')[-1].split('?')[0])
        if not original_filename: original_filename = "scraped_image.jpg"

        unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], 'images', unique_filename)
        
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"成功從 {image_url} 抓取圖片")
        return os.path.join('images', unique_filename).replace("\\", "/")
    except requests.RequestException as e:
        print(f"抓取圖片失敗: {e}")
        return None


# --- Permission Decorator (安全驗證) ---
def permission_required(required_permissions):
    if isinstance(required_permissions, str):
        required_permissions = [required_permissions]
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = request.headers.get('X-User-ID')
            if not user_id:
                return jsonify({'status': 401, 'message': '未提供使用者身分 (缺少 X-User-ID 標頭)', 'success': False}), 401
            try:
                with DBHandler() as db:
                    user = db.find_user(user_id=int(user_id))
                if not user:
                    return jsonify({'status': 401, 'message': '無效的使用者 ID', 'success': False}), 401
                g.user = user
                if user['permission'] not in required_permissions and user['permission'] != 'manager':
                    return jsonify({'status': 403, 'message': f"權限不足，此操作需要 {required_permissions} 等級。", 'success': False}), 403
            except Exception as e:
                return jsonify({'status': 500, 'message': f"驗證使用者身分時發生錯誤: {e}", 'success': False}), 500
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
            return jsonify({'status': 200, 'result': categories, 'success': True})

    if request.method == 'POST':
        @permission_required('manager')
        def create():
            data = request.get_json()
            if not data or not all(k in data for k in ['name', 'category_type']):
                return jsonify({'status': 400, 'message': "缺少欄位: name, category_type", 'success': False}), 400
            with DBHandler() as db:
                cat_id = db.insert_category(data['name'], data['category_type'])
                if cat_id:
                    return jsonify({'status': 201, 'message': '分類建立成功', 'id': cat_id, 'success': True}), 201
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

    
# --- posts CURD ---
@app.route('/api/posts', methods=['GET', 'POST'])
def handle_posts():
    if request.method == 'GET':
        filters = {k: v for k, v in request.args.items() if k in ['title_keyword', 'category_id', 'user_id']}
        page_size = request.args.get('page_size', 10, type=int)
        page = request.args.get('page', 1, type=int)
        offset = (page - 1) * page_size
        with DBHandler() as db:
            posts = db.get_posts(filters=filters, page_size=page_size, offset=offset)
            return jsonify({'status': 200, 'result': posts, 'success': True})

    if request.method == 'POST':
        @permission_required(['manager', 'editor'])
        def create():
            data = request.get_json()
            required = ['title', 'content', 'user_id', 'category_id']
            if not data or not all(k in data for k in required):
                return jsonify({'status': 400, 'message': f"缺少欄位: {required}", 'success': False}), 400
            
            main_image_path = save_base64_file(data.get('main_image'), 'images') if data.get('main_image') else scrape_and_save_image(data['content'])
            attachments_list = [save_base64_file(f, 'attachments') for f in data.get('attachments', [])]
            
            with DBHandler() as db:
                post_id = db.create_post(
                    title=data['title'], content=data['content'], user_id=data['user_id'],
                    category_id=data['category_id'], main_image_url=main_image_path,
                    attachments=[{'path': p, 'original_filename': f.get('filename')} for p, f in zip(attachments_list, data.get('attachments', [])) if p]
                )
            if post_id:
                return jsonify({'status': 201, 'message': "文章建立成功", 'id': post_id, 'success': True}), 201
            else:
                return jsonify({'status': 500, 'message': "無法建立文章", 'success': False}), 500
        return create()

@app.route('/api/posts/<int:post_id>', methods=['GET', 'PUT', 'DELETE'])
def handle_post_by_id(post_id):
    if request.method == 'GET':
        with DBHandler(DB_CONFIG) as db:
            post = db.get_post(post_id)
            return jsonify({'status': 200, 'result': post, 'success': True}) if post else jsonify({'status': 404, 'message': '找不到文章', 'success': False}), 404

    @permission_required(['manager', 'editor'])
    def protected_operation():
        with DBHandler(DB_CONFIG) as db:
            owner_id = db.get_post_owner(post_id)
            if not owner_id:
                return jsonify({'status': 404, 'message': '找不到文章', 'success': False}), 404
            
            if g.user['permission'] != 'manager' and g.user['id'] != owner_id:
                return jsonify({'status': 403, 'message': '權限不足，只能操作自己的文章', 'success': False}), 403

            if request.method == 'PUT':
                data = request.get_json()
                if not data:
                    return jsonify({'status': 400, 'message': "未包含更新資料", 'success': False}), 400
                
                # 準備要傳遞給 DBHandler 的資料
                update_data_for_db = {}
                
                # 處理基本欄位
                for field in ['title', 'content', 'category_id']:
                    if field in data:
                        update_data_for_db[field] = data[field]
                
                # 處理主圖
                if 'main_image' in data:
                    if data['main_image'] is None:
                        # 當前端傳入 null 時，從 content 重新抓取圖片
                        content_to_scrape = data.get('content')
                        update_data_for_db['main_image_url'] = scrape_and_save_image(content_to_scrape)
                    elif isinstance(data['main_image'], dict):
                        # 當前端傳入 Base64 物件時，儲存新圖片
                        update_data_for_db['main_image_url'] = save_base64_file(data['main_image'], 'images')
                
                # 處理附件
                if 'attachments' in data:
                    new_attachments = []
                    if isinstance(data['attachments'], list):
                        for file_data in data['attachments']:
                            path = save_base64_file(file_data, 'attachments')
                            if path:
                                new_attachments.append({
                                    'path': path,
                                    'original_filename': secure_filename(file_data.get('filename'))
                                })
                    update_data_for_db['attachments'] = new_attachments
                
                # 處理標籤
                if 'hashtags' in data:
                    update_data_for_db['hashtags'] = data['hashtags']

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
            return jsonify({'status': 200, 'result': bulletins, 'success': True})
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
    with DBHandler() as db:
        success = db.delete_bulletin_message(message_id)
        return jsonify({'status': 200, 'message': "留言刪除成功", 'success': True}) if success else jsonify({'status': 404, 'message': "找不到要刪除的留言", 'success': False}), 404


if __name__ == "__main__":
    app.run(debug=True, port=5004)