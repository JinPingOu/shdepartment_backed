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
├── static/            # 靜態文件資料夾
└── uploads/
    ├── attachments    # 公告附件 
    ├── images         # 公告主視覺圖
    └── files          # 上傳文件
```

## API 說明

- **prefix**:`sh-department-api`
  在`app.py` _app.config['APPLICATION_ROOT']_ 調整

### 類別
### 1. 取得某父類別下的類別

- **方法**：GET
- **路徑**：`/api/categories`
- **Query 參數**：
  - `category_type`（str, 選填）："instructions"(說明文件) / "latest_news"(最新消息) / (不選就都輸出)
- **回傳格式**：

```json
{
  "status": 200,
  "message": "success",
  "result": {
    "rows": [
      {
        "id": 1,
        "name": "人資 Q&A 助手",
        "category_type": "instructions"
      }
    ],
    "total": 100
  },
  "success": true
}
```

- **功能描述**：取得instructions(說明文件) 或 latest_news(最新消息) 或 全部 的子類別。
- total: 用於前端。

---


### 2. 新增類別

- **方法**：POST
- **路徑**：`/api/categories`
- **Body**：`application/json`
  - `name`（str, 必填）: 類別名稱
  - `category_type`（str, 必填）：instructions 或 latest_news
- **回傳格式**：

```json
{
  "status": 200,
  "message": "分類建立成功",
  "id": 123, 
  "success": true
}
```

- **功能描述**：新增最新消息或說明文件的類別。

---

### 3. 刪除指定類別

- **方法**：DELETE
- **路徑**：`/api/categories/<string:category_name>`
- **URL 參數**：
  - `category_name`（str, 必填）：類別名
- **回傳格式**：

```json
{
  "status": 200,
  "message": "分類刪除成功",
  "success": true
}
```

- **功能描述**：刪除指定的類別。

---

### 上傳檔案
### 1. 上傳檔案

- **方法**：POST
- **路徑**：`/api/upload`
- **Body**：`multipart/form`
  - `files`（file list, 必填）： 補助文件
  - `file_type`: images(主視覺圖) 或 attachments(附件) 或 files(補助文件)  
- **回傳格式**：

```json
{
  "status": 200,
  "message": "upload success",
  "file_records": [
    {
      "id": 123,
      "path": "/uploads/files/123_test.pdf",
      "original_filename": "test.pdf"
    }
  ], 
  "success": true
}
```

- **功能描述**：上傳補助文件，或在新增公告的頁面，選擇上傳主視覺圖或附件，前端再儲存id成list傳給/api/posts做新增posts，注意因為怕重複文件存入檔名會變。

---

### 2. 取得某公告/某特定檔名/全部的主視覺圖或附件 或 取得某特定檔名/全部的補助文件

- **方法**：GET
- **路徑**：`/api/files`
- **Query 參數**：
  - `post_id`（int, 選填）：主視覺圖或附件所屬的公告 ID 或 補助文件不用填 (None)
  - `file_type`（int, 選填）：類別名 - images(主視覺圖) /attachments(附件) /files(補助文件)
  - `original_filename`（int, 選填）：上傳時的檔案標題名稱 (考慮要不要刪掉 或 改成關鍵字搜尋)
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
        "post_id": 123,
        "file_type": "attachments",
        "file_path": "./uploads/attachments/123_test.pdf",
        "original_filename": "test.pdf"
      }
    ],
    "total": 100
  },
  "success": true
}
```

- **功能描述**：分頁取得某公告/某特定檔名/全部的主視覺圖或附件 或 取得某特定檔名/全部的補助文件 (/api/posts也可以取得images/attachments)。
- total: 用於前端分頁用。

---

### 3. 刪除指定的附件/主視覺圖/補助文件

- **方法**：DELETE
- **路徑**：`/api/posts/<int:file_id>`
- **URL 參數**：
  - `file_id`（int, 必填）：要刪除的附件/主視覺圖/補助文件
- **回傳格式**：

```json
{
  "status": 200,
  "message": "檔案刪除成功",
  "success": true
}
```

- **功能描述**：刪除指定的附件/主視覺圖/補助文件。


---

### 4. 下載附件/主視覺圖/補助文件

- **方法**：GET
- **路徑**：`/api/download/files/<int:file_id>`
- **Param 參數**：
  - file_id（int, 必填）：附件/主視覺圖/補助文件 ID
- **回傳格式**：

```url
`./static/slides/2025/test.pdf`
```

- **功能描述**：取得附件/主視覺圖/補助文件url。(考慮刪掉這個或get中的url)

---



### 公告
### 1. 取得某標題/某父子類別/某發布者/某狀態/全部的公告

- **方法**：GET
- **路徑**：`/api/posts`
- **Query 參數**：
  - `category_type` (str, 選填) : 父類別名 ("latest_news" 或 "instructions")
  - `category_name`（str, 選填）：類別名
  - `title_keyword`（str, 選填）：搜尋標題的關鍵字
  - `user_id`（int, 選填）：公告發布者 ID
  - `status` (str, 選填) : 公告狀態 ('published' 或 'draft' 或 'archived')
  - `order_by`(str, 選填) :排序方式 ("announcement_date" 或 "click_count", 預設announcement_date)
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
        "title": "人資 Q&A 助手 - 說明文件",
        "content": "<h1>...</h1>",
        "user_id": 1,
        "catrgory_name": "人資 Q&A 助手",
        "status": "draft",
        "click_count": 13,
        "announcement_date": "2025-08-27 11:57",
        "attachments":[
          {
            "id": 1,
            "post_id": 123,
            "file_type": "attachments",
            "file_path": "./uploads/attachments/123_test.pdf",
            "original_filename": "test.pdf"
          } 
        ],
        "images": [
          {
            "id": 1,
            "post_id": 123,
            "file_type": "attachments",
            "file_path": "./uploads/attachments/123_test.pdf",
            "original_filename": "test.pdf"
          }
        ],
        "hashtags": [
          {
            "id": 1,
            "tag_name": "QA"
          }
        ]
      }
    ],
    "total": 100
  },
  "success": true
}
```

- **功能描述**：分頁取得某標題/某父子類別/某發布者/某狀態/全部的公告。
- total: 用於前端分頁用。

---

### 2. 新增公告

- **方法**：POST
- **路徑**：`/api/posts`
- **Body**：`application/json`
    - `title`（str, 必填）：公告標題
    - `content`（str, 必填）：公告內容
    - `category_name`（str, 必填）：子類別名
    - `status` (str, 必填) : 公告狀態 ('published' 或 'draft' 或 'archived', 預設draft)
    - `hashtags`（str list, 選填）：標籤列表
    - `file_ids` (int list, 選填) : 附件/主視覺圖 list

- **回傳格式**：

```json
{
  "status": 200,
  "message": "文章建立成功",
  "id": 123, 
  "success": true
}
```

- **功能描述**：新增公告。

---

### 3. 取得指定的公告

- **方法**：GET
- **路徑**：`/api/posts/<int:post_id>`
- **URL 參數**：
  - `post_id`（int, 必填）：搜尋某公告的ID
- **回傳格式**：

```json
{
  "status": 200,
  "message": "success",
  "result": {
    "id": 1,
    "title": "人資 Q&A 助手 - 說明文件",
    "content": "<h1>...</h1>",
    "user_id": 1,
    "catrgory_name": "人資 Q&A 助手",
    "status": "draft",
    "click_count": 13,
    "announcement_date": "2025-08-27 11:57",
    "attachments":[
      {
        "id": 1,
        "post_id": 123,
        "file_type": "attachments",
        "file_path": "./uploads/attachments/123_test.pdf",
        "original_filename": "test.pdf"
      } 
    ],
    "images": [
      {
        "id": 1,
        "post_id": 123,
        "file_type": "attachments",
        "file_path": "./uploads/attachments/123_test.pdf",
        "original_filename": "test.pdf"
      }
    ],
    "hashtags": [
      {
        "id": 1,
        "tag_name": "QA"
      }
    ]
  },
  "success": true
}
```

- **功能描述**：取得指定的公告。

### 4. 更新指定的公告

- **方法**：PUT
- **路徑**：`/api/posts/<int:post_id>`
- **URL 參數**：
  - `post_id`（int, 必填）：更新某公告的ID
- **Body**：`application/json`
    - `title`（str, 必填）：公告標題
    - `content`（str, 必填）：公告內容
    - `category_name`（str, 必填）：子類別名
    - `status` (str, 必填) : 公告狀態 ('published' 或 'draft' 或 'archived', 預設draft)
    - `hashtags`（str list, 選填）：標籤列表
    - `file_ids` (int list, 選填) : 附件/主視覺圖 list

```json
{
  "status": 200,
  "message": "文章更新成功",
  "success": true
}
```

- **功能描述**：更新指定的公告。

---
### 5. 刪除指定的公告

- **方法**：DELETE
- **路徑**：`/api/posts/<int:post_id>`
- **URL 參數**：
  - `post_id`（int, 必填）：刪除公告的ID
- **回傳格式**：

```json
{
  "status": 200,
  "message": "文章刪除成功",
  "success": true
}
```

- **功能描述**：刪除指定的公告。


---

### 布告欄
### 1. 取得某天或某部門或全部的布告欄訊息

- **方法**：GET
- **路徑**：`/api/bulletin_messages`
- **Query 參數**：
  - `campus`（str, 選填）：院區
  - `department`（str, 選填）：部門
  - `date`（str, 選填）：要尋找的日子(格式: YYYY-MM-DD)
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

### 2. 新增布告欄訊息

- **方法**：POST
- **路徑**：`/api/bulletin_messages`
- **Body**：`application/json`
  - `author_name`（str, 選填）:發布者名稱 或 None
  - `content`（str, 必填）：布告欄訊息
  - `campus`（str, 選填）：院區名稱
  - `department`（str, 選填）：部門名稱
- **回傳格式**：

```json
{
  "status": 200,
  "message": "留言新增成功",
  "id": 123, 
  "success": true
}
```

- **功能描述**：新增布告欄訊息。

---

### 3. 刪除指定布告欄訊息

- **方法**：DELETE
- **路徑**：`/api/bulletin_messages/<int:message_id>`
- **URL 參數**：
  - `message_id`（int, 必填）：訊息 ID
- **回傳格式**：

```json
{
  "status": 200,
  "message": "留言刪除成功",
  "success": true
}
```

- **功能描述**：刪除指定的會議記錄。

---