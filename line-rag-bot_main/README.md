# LINE 群組 RAG 機器人 (LINE Group RAG Bot)

## 📌 專案簡介
本專案是一個基於 **FastAPI** 的 LINE 群組 RAG (Retrieval-Augmented Generation，檢索增強生成) 機器人。它具備以下核心功能：
- **異步 PostgreSQL 資料庫**：用於紀錄群組對話記錄，防止高併發下的數據丟失。
- **ChromaDB 向量資料庫**：儲存向量化的網頁內容與群組對話摘要，支援群組權限隔離檢索。
- **自動對話摘要（APScheduler）**：定期彙整未處理對話，交由 Google Gemini 產出結構化摘要並儲存至向量庫。
- **網頁內容爬取追蹤**：自動辨識對話中的連結，透過 Jina Reader API 抓取網頁 Markdown 內容並儲存於 ChromaDB。
- **智慧 RAG 問答**：當收到喚醒詞 `@help` 時，檢索該群組專屬知識庫，並使用 Gemini 生成回答，最後附上引用來源（對話記錄/外部網頁）。

---

## 🛠️ 環境需求
- Python 3.10+
- PostgreSQL 資料庫

---

## 🚀 快速啟動與開發指南

### 1. 建立並啟動虛擬環境 (Virtual Environment)
在專案根目錄下，建議使用內建的 `venv` 模組：
```bash
# 進入專案目錄
cd line-rag-bot_main

# 建立虛擬環境 (若尚未建立)
python3 -m venv venv

# 啟動虛擬環境
# macOS / Linux:
source venv/bin/activate

# Windows (Command Prompt):
# .\venv\Scripts\activate
# Windows (PowerShell):
# .\venv\Scripts\Activate.ps1
```

### 2. 安裝依賴套件
確保虛擬環境已啟用，接著安裝所需的依賴套件：
```bash
pip install -r requirements.txt
```

### 3. 設定環境變數
將 `.env.example` 複製為 `.env` 並填入對應的 API 密鑰與連線設定：
```bash
cp .env.example .env
```
編輯 `.env` 檔案填入以下內容：
- `DATABASE_URL`: PostgreSQL 異步連線字串（使用 `asyncpg` 協定，例如 `postgresql+asyncpg://...`）
- `LINE_CHANNEL_ACCESS_TOKEN`: LINE Bot 的 Channel Access Token
- `LINE_CHANNEL_SECRET`: LINE Bot 的 Channel Secret
- `GOOGLE_API_KEY`: Google Gemini API Key
- `CHROMADB_PATH`: ChromaDB 本地儲存路徑（預設 `./chroma_data`）
- `ALLOWED_GROUP_IDS`: 允許機器人讀取/處理訊息的 LINE 群組 ID（多個用逗號 `,` 隔開，未授權的群組訊息將被過濾）

### 4. 初始化資料庫資料表
首次啟動前，請執行以下腳本以在 PostgreSQL 中建立所需的資料表：
```bash
python init_db.py
```

### 5. 啟動 FastAPI 服務
使用 `uvicorn` 啟動伺服器：
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
啟動後，API 服務將運行在 `http://localhost:8000`。

### 6. 外網對接與 Webhook 設定 (開發偵錯)
由於 LINE Webhook 需要 HTTPS 格式的外網 URL，推薦使用 `ngrok` 進行本機偵錯：
```bash
ngrok http 8000
```
啟動後會得到一個 HTTPS 的外網網址（例如：`https://xxxx-xx-xx.ngrok-free.app`）。
請前往 [LINE Developers Console](https://developers.line.biz/) 將 Webhook URL 設定為：
```text
https://xxxx-xx-xx.ngrok-free.app/webhook
```
並確保啟用 **"Use webhook"** 選項。

---

## 🔍 輔助工具與管理腳本
- **`list_db_messages.py`**:
  可以用於在終端機查看資料庫目前已儲存的群組對話記錄，便於排查訊息是否有正確寫入資料庫：
  ```bash
  python list_db_messages.py
  ```
