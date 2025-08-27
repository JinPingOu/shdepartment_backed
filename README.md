# 智慧醫療部網頁

## 專案簡介



---

## 主要功能

- 使用者登入、權限管理
- 管理最新消息
- 管理說明文件
- 管理布告欄
- 提供網頁前端介面[前端 React 專案]()

## 安裝步驟

1. 下載或 clone 此專案
2. 安裝依賴套件：
   ```bash
   pip install -r requirements.txt
   ```
3. 設定資料庫與環境變數（見下方）
   請在專案根目錄建立 `.env` 檔案，內容如下（以 PostgreSQL 為例）：

```
DB_HOST=localhost or VM_IP
DB_PORT=5432
DB_USER=db_user
DB_PASSWORD=db_password
DB_NAME=meeting_system
```

資料庫建立

## 啟動方式

### 開發模式

```bash
python app.py
```

預設會在 http://localhost:5004 運行。

### 正式部署

1. 執行 `wsgi.py`：
   ```bash
   python wsgi.py
   ```
2. 使用 gunicorn 啟動（Linux）：
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5003 wsgi:app
   ```

---

## 目錄結構簡介

- `app.py`：主程式，Flask API 入口
- `db_handler.py`：資料庫操作模組
- `static/`:靜態文件資料夾

## 專案結構

```
meeting_system_backend/
├── app.py             # 主應用程式、所有的服務、路由控制在這，未來要擴充api都是在這裡擴充(開發時可在這裡啟動 debug)
├── wsgi.py            # 正式上線時啟動wsgi server
├── db_handler.py      # DB 資料庫操作
├── requirements.txt   # 相依套件列表
└── static/            # 靜態文件資料夾

```

## API 說明

- **prefix**:`sh-department-api`
  在`app.py` _app.config['APPLICATION_ROOT']_ 調整

### 1. 取得所有布告欄訊息

- **方法**：GET
- **路徑**：`/api/get_all_bulletin_messages`
- **Query 參數**：
  - `page`（int, 選填，預設 1）：分頁頁碼
  - `page_size`（int, 選填，預設 10）：每頁筆數
- **回傳格式**：

```json
{
  "status": 200,
  "message": "success",
  "result": {
    "rows": [
      {
        "id": 1,
        "author_name": "路人甲",
        "content": "我好餓TT",
        "campus": "義大醫院",
        "department": "智慧醫療部",
        "create_at": "2025-08-27 11:57"
      }
    ],
    "total": 100
  },
  "success": true
}
```

- **功能描述**：分頁取得所有布告欄訊息。
- total: 用於前端分頁用。

---

### 2. 取得某天時間的布告欄訊息

- **方法**：GET
- **路徑**：`/api/get_bulletin_messages_by_date`
- **Query 參數**：
  - `page`（int, 選填，預設 1）：分頁頁碼
  - `page_size`（int, 選填，預設 10）：每頁筆數
  - `date`（str, 必填）：要尋找的日子(格式: YYYY-MM-DD)
- **回傳格式**：

```json
{
  "status": 200,
  "message": "success",
  "result": {
    "rows": [
      {
        "id": 1,
        "author_name": "路人甲",
        "content": "我好餓TT",
        "campus": "義大醫院",
        "department": "智慧醫療部",
        "create_at": "2025-08-27 11:57"
      }
    ],
    "total": 100
  },
  "success": true
}
```

- **功能描述**：取得指定會議的詳細資料與所有章節內容。

---

### 3. 取得單一會議及其章節內容

- **方法**：GET
- **路徑**：`/api/get_meeting`
- **Query 參數**：
  - `meeting_id`（int, 必填）：會議 ID
- **回傳格式**：

```json
{
  "status": 200,
  "message": "success",
  "result": {
    "meeting": { ... },
    "subject": [
      { "主題": "...", "內容": "..." }
    ]
  },
  "success": true
}
```

- **功能描述**：取得指定會議的詳細資料與所有章節內容。

---

### 4. 新增布告欄訊息

- **方法**：POST
- **路徑**：`/api/insert_bulletin_message`
- **Body**：`application/json`
  - `author_name`:發布者名稱 或 None
  - `content`：布告欄訊息
  - `campus`：院區名稱
  - `department`：部門名稱
- **回傳格式**：

```json
{
  "status": 200,
  "message": "file saved and inserted successfully",
  "id": 123, 
  "success": true
}
```

- **功能描述**：新增布告欄訊息。
