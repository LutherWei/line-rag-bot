from fastapi import FastAPI, Request, BackgroundTasks, Response
from app.services.line_service import handle_webhook
import logging

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="LINE RAG Bot")

@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    result = await handle_webhook(request, background_tasks)
    if isinstance(result, tuple):
        return Response(content=result[0], status_code=result[1])
    return Response(content="OK", status_code=200)

# Scheduler disabled in favor of real-time TXT architecture
# @app.on_event("startup")
# async def startup_event():
#     from app.tasks import start_scheduler
#     start_scheduler()
