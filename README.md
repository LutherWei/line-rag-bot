# 🤖 LINE Group RAG Bot (LINE 群組 RAG 機器人)

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql)](https://www.postgresql.org/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-007ACC?style=for-the-badge)](https://www.trychroma.com/)
[![Google Gemini](https://img.shields.io/badge/Google_Gemini-8E75C2?style=for-the-badge&logo=google-gemini&logoColor=white)](https://deepmind.google/technologies/gemini/)

本專案是一個基於 **FastAPI** 的 LINE 群組 RAG (Retrieval-Augmented Generation，檢索增強生成) 機器人。專案能儲存群組內部的聊天訊息，並在後台進行自動化摘要及網頁鏈接內容爬取，最後透過向量資料庫（ChromaDB）及 Google Gemini LLM 為群組成員提供具備智慧上下文檢索與精準引用來源的問答服務。

---

## 🏗️ 系統架構與核心功能

*   **異步 PostgreSQL 儲存**：使用 `asyncpg` 與 `SQLAlchemy 2.0` 以高併發且非阻塞方式記錄群組聊天訊息（`raw_messages`）與已追蹤的 URL（`extracted_urls`）。
*   **ChromaDB 向量知識庫**：隔離群組資料，只在相同 `group_id` 的資料庫範圍內執行相似度檢索，確保隱私安全。
*   **自動化定時對話摘要**：透過 `APScheduler` 排程定時整合未處理的訊息，交由 `gemini-1.5-flash` 產出結構化摘要，並呼叫 `text-embedding-004` 存入向量資料庫。
*   **網頁自動追蹤與爬取**：即時識別聊天中的 URL 連結，利用 `FastAPI BackgroundTasks` 呼叫 Jina Reader API (`https://r.jina.ai/{URL}`) 爬取內容並自動向量化儲存。
*   **智慧 Q&A 與引用標註**：當偵測到群組內的喚醒詞 `@help`，系統會從知識庫中檢索 Top-K 最相關的上下文，並使用 Gemini 生成回答，最後於回答末端標註所有引用的討論日期、參與者或外部網頁網址。

---

## 📁 專案目錄結構

```text
line-rag-bot/
├── line-rag-bot_main/          # 專案程式碼主目錄
│   ├── app/                    # FastAPI 應用程式核心
│   │   ├── main.py             # Webhook 路由與啟動入口
│   │   ├── config.py           # 系統設定與 Pydantic 環境變數管理
│   │   ├── database.py         # PostgreSQL 異步連接與 Session 管理
│   │   ├── models.py           # SQLAlchemy 2.0 資料模型
│   │   ├── schemas.py          # Pydantic 數據校驗模式
│   │   ├── tasks.py            # APScheduler 排程任務 (定時對話摘要)
│   │   └── services/           # 業務邏輯服務層
│   │       ├── line_service.py # LINE 訊息接收、簽章驗證與回覆
│   │       ├── llm_service.py  # Gemini 生成、摘要與 Embedding 封裝
│   │       ├── vector_service.py # ChromaDB 向量讀寫與群組隔離檢索
│   │       └── crawler_service.py # Jina Reader API 網頁爬蟲與處理
│   ├── data/                   # 儲存本地 SQLite 或向量庫數據 (可選)
│   ├── init_db.py              # 初始化 PostgreSQL 資料表腳本
│   ├── list_db_messages.py     # 終端機對話紀錄查詢工具
│   ├── requirements.txt        # Python 依賴清單
│   └── .env.example            # 環境變數範本
├── spec.md                     # 開發規格說明書
└── README.md                   # 本說明文件 (根目錄)
```

---

## 🚀 快速啟動與環境設定

> [!IMPORTANT]
> 所有的開發與執行指令，**均需在 `line-rag-bot_main` 目錄下執行**。
> 如果在根目錄下直接執行，會導致 `ModuleNotFoundError: No module named 'app'` 或是無法讀取到 `.env` 設定檔等路徑錯誤。

### Step 1: 進入主專案目錄並建立/啟動虛擬環境

```bash
# 1. 進入主專案目錄
cd line-rag-bot_main

# 2. 建立 Python 虛擬環境 (若尚未建立)
python3 -m venv venv

# 3. 啟用虛擬環境
# macOS / Linux:
source venv/bin/activate

# Windows (Command Prompt):
# .\venv\Scripts\activate
# Windows (PowerShell):
# .\venv\Scripts\Activate.ps1
```

### Step 2: 安裝依賴套件

在虛擬環境啟用狀態下，安裝 `requirements.txt` 中所列的所有套件：

```bash
pip install -r requirements.txt
```

### Step 3: 設定環境變數

複製環境變數範本並進行編輯：

```bash
cp .env.example .env
```

請編輯新建立的 `.env` 檔案，填入以下必填參數：

| 環境變數名稱 | 說明 | 範例 / 預設值 |
| :--- | :--- | :--- |
| `DATABASE_URL` | PostgreSQL 異步連線字串 (需使用 `asyncpg`) | `postgresql+asyncpg://user:pass@localhost:5432/dbname` |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Developers 申請的 Access Token | `ey...` |
| `LINE_CHANNEL_SECRET` | LINE Developers 申請的 Channel Secret | `a1b2...` |
| `GOOGLE_API_KEY` | Google Gemini API Key | `AIzaSy...` |
| `CHROMADB_PATH` | ChromaDB 本地儲存資料的路徑 | `./chroma_data` |
| `ALLOWED_GROUP_IDS` | 允許 Bot 處理的 LINE 群組 ID (多個請用 `,` 隔開) | `C123456...,C789101...` |

### Step 4: 初始化資料表

首次啟動專案前，必須先在資料庫中建立所需的 Table。請執行以下腳本：

```bash
python init_db.py
```

### Step 5: 啟動 FastAPI 服務

使用 `uvicorn` 啟動 Web 服務。

```bash
# 使用 uvicorn 啟動並開啟自動重新載入 (Reload)
uvicorn app.main:app --host 0.0.0.0 --port 7414 --reload
```

*   服務啟動後，API 文件可以透過 `http://localhost:7414/docs` 訪問。

### Step 6: 外部網路對接 (Webhook 設定)

由於 LINE 伺服器必須透過 HTTPS 傳送 Webhook 事件至您的伺服器，在本機開發時推薦使用 `ngrok`：

```bash
# 對外暴露 7414 連接埠
ngrok http 7414
```

啟動後 `ngrok` 會提供一組 `https://xxxx.ngrok-free.app` 的網址。請登入 [LINE Developers Console](https://developers.line.biz/)：
1. 將 Webhook URL 設定為：`https://xxxx.ngrok-free.app/webhook`。
2. 點擊 **Verify** 驗證連線是否成功。
3. 開啟 **Use Webhook** 選項。

---

## 🛠️ 常見錯誤排查 (Troubleshooting)

### ❌ `ModuleNotFoundError: No module named 'app'`
*   **原因**：這通常是因為您是在 `line-rag-bot` 根目錄下直接執行 `uvicorn app.main:app`。
*   **解決方法 1 (推薦)**：先切換至專案主目錄再啟動：
    ```bash
    cd line-rag-bot_main
    uvicorn app.main:app --host 0.0.0.0 --port 7414 --reload
    ```
*   **解決方法 2**：若堅持要在根目錄下啟動，需指定 `--app-dir` 參數，以便 uvicorn 能正確將 `line-rag-bot_main` 加入 PYTHONPATH 中：
    ```bash
    line-rag-bot_main/venv/bin/uvicorn app.main:app --app-dir line-rag-bot_main --host 0.0.0.0 --port 7414 --reload
    ```
    *注意：使用解決方法 2 時，請確保 `.env` 與 `chroma_data` 在您目前執行的根目錄下亦有一份，否則 `pydantic-settings` 會因找不到 `.env` 而報錯或讀取到錯誤的配置。*

### ❌ 偵測不到環境變數
*   請檢查 `.env` 檔案是否確實放置於 `line-rag-bot_main/` 下（或您執行 uvicorn 時的當前工作目錄下）。
*   若連接 PostgreSQL 發生 `driver` 錯誤，請確認 `DATABASE_URL` 開頭是否為 `postgresql+asyncpg://`。
