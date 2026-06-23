# LINE Group RAG Bot

This project is a FastAPI-based RAG bot for LINE Groups, equipped with:
- Asynchronous PostgreSQL for logging chats.
- ChromaDB for vector storage.
- APScheduler for scheduled summaries.
- Web content tracking using Jina Reader.
- LLM powered by Google Gemini (flash for generation/summarization, text-embedding-004 for search).

## Setup
1. `pip install -r requirements.txt`
2. Configure `.env` from `.env.example`.
3. Set up a local PostgreSQL DB.
4. Provide Google API and LINE bot configurations.
5. Initialize the DB tables (use Alembic or manually via SQLAlchemy models).

## Run
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
