from db_handler import DBHandler
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import datetime

app = Flask(__name__)
CORS(app)


app.config['APPLICATION_ROOT'] = 'sh-department-api'
app.config['DOCUMENT_FOLDER'] = './static/'

db = DBHandler()

@app.route('/api/test')
def index():
    return jsonify({
        'status': 200,
        'message': "sh-department-api|Test endpoint is working",
        'result': [],
        'success': True
    }), 200

@app.route('/api/get_all_bulletin_messages', methods=['GET'])
def get_all_bulletin_messages():
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 10, type=int)
        offset = (page - 1) * page_size
        bulletins = db.get_all_bulletin_messages(page_size, offset)
        return jsonify({
            'status': 200,
            'message': "success",
            'result': bulletins,
            'success': True
        }), 200
    except Exception as e:
        return jsonify({
            'status': 400,
            'message': e,
            'result': [],
            'success': False
        }), 400

@app.route('/api/get_bulletin_messages_by_date', methods=['GET'])
def get_bulletin_messages_by_date():
    try:
        date_str = request.args.get('date')
        if not date_str:
            return jsonify({
                'status': 400, 
                'message': "必須提供 'date' 查詢參數 (格式: YYYY-MM-DD)", 
                'result': [],
                'success': False
            }), 400

        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()       
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 10, type=int)
        offset = (page - 1) * page_size
        bulletins = db.get_bulletin_messages_by_date(target_date, page_size, offset)
        
        return jsonify({
            'status': 200,
            'message': "success",
            'result': bulletins,
            'success': True
        }), 200
    except ValueError:
        return jsonify({
            'status': 400, 
            'message': "日期格式錯誤，請使用 YYYY-MM-DD",
            'result': [], 
            'success': False
        }), 400
    except Exception as e:
        return jsonify({
            'status': 400,
            'message': e,
            'result': [],
            'success': False
        }), 400


@app.route('/api/get_messages_by_campus_and_department', methods=['GET'])
def get_messages_by_campus_and_department():
    """【新路由】處理按校區和系所查詢的請求"""
    campus = request.args.get('campus')
    department = request.args.get('department')

    if not campus or not department:
        return jsonify({'status': 400, 'message': "必須同時提供 'campus' 和 'department' 查詢參數", 'success': False}), 400

    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 10, type=int)
        offset = (page - 1) * page_size
        messages = db.get_messages_by_campus_and_department(campus, department, page_size, offset)
            
        return jsonify({
            'status': 200,
            'message': "success",
            'result': messages,
            'success': True
        }), 200
    except Exception as e:
        return jsonify({
            'status': 400,
            'message': e,
            'result': [],
            'success': False
        }), 400

    
@app.route('/api/insert_bulletin_message', methods=['POST'])
def insert_bulletin_message():
    data = request.get_json()

    # 2. 檢查是否有收到資料，以及必要欄位 'content' 是否存在
    if not data:
        return jsonify({
            'status': 400,
            'message': "請求中未包含JSON資料",
            'result': [],
            'success': False}), 400
    
    content = data.get('content')
    if not content or not content.strip():
        return jsonify({
            'status': 400,
            'message': "必要欄位content不得為空",
            'result': [],
            'success': False}), 400

    # 3. 從 JSON 中取得其他選填欄位
    author_name = data.get('author_name')
    department = data.get('department')
    campus = data.get('campus')

    # 4. 使用 DBHandler 來處理資料庫操作
    try:
        message_id = db.insert_bulletin_message(
            author_name=author_name,
            content=content,
            department=department,
            campus=campus
        )
        if message_id:
            # 5. 如果成功，回傳成功的訊息和新增的 ID
            return jsonify({
                'status': 200,  
                "message": "bulletin insert success",
                "id": message_id,
                "succes": True
            }), 201 # 201 Created 是表示資源成功建立的標準 HTTP 狀態碼
        else:
            # 如果 create_guestbook_message 回傳 None，表示內部發生錯誤
            return jsonify({
            'status': 400,
            'message': "無法新增布告欄訊息",
            'result': [],
            'success': False}), 500

    except Exception as e:
        # 捕捉其他未預期的錯誤
        print(f"發生未預期的錯誤: {e}")
        return jsonify({
            'status': 400,
            'message': "伺服器內部發生未預期的錯誤",
            'result': [],
            'success': False}), 500
    
@app.route('/api/delete_bulletin_message', methods=['DELETE'])
def delete_bulletin_message():
    try:
        m_id = request.args.get('massage_id')
        if m_id:
            res = db.delete_bulletin_message(m_id)
        else:
            return jsonify({
            'status': 400,
            'message': 'argument m_id was required.',
            'success': False
        }), 400
        if res:
            return jsonify({
            'status': 200,
            'message': f"Meeting {m_id} deleted",
            'success': True
        }), 200
        else:
            return jsonify({
            'status': 404,
            'message': f"Meeting {m_id} already deleted",
            'success': False
        }), 404
    except Exception as e:
        return jsonify({
            'status': 400,
            'message': str(e),
            'success': False
        }), 400

if __name__ == "__main__":
    app.run(debug=True, port=5004)