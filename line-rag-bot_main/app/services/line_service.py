import re
from fastapi import Request, BackgroundTasks
from linebot.v3 import WebhookParser
from linebot.v3.messaging import AsyncApiClient, AsyncMessagingApi, Configuration, ReplyMessageRequest, TextMessage
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from app.config import settings
from app.database import async_session
from app.models import RawMessage
from app.services.crawler_service import process_url
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

configuration = Configuration(access_token=settings.line_channel_access_token)
async_api_client = AsyncApiClient(configuration)
messaging_api = AsyncMessagingApi(async_api_client)
parser = WebhookParser(settings.line_channel_secret)

URL_REGEX = re.compile(r'(https?://[^\s]+)')

async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    signature = request.headers.get('X-Line-Signature', '')
    body = await request.body()
    body_text = body.decode('utf-8')

    try:
        events = parser.parse(body_text, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature.")
        return "Invalid signature", 400

    for event in events:
        if not isinstance(event, MessageEvent):
            continue
        if not isinstance(event.message, TextMessageContent):
            continue
            
        group_id = event.source.group_id if hasattr(event.source, 'group_id') else getattr(event.source, 'room_id', event.source.user_id)
        user_id = event.source.user_id
        text = event.message.text
        # Normally would need to fetch user profile, but caching or simplified processing
        # Let's just use user_id as user_name for now, or assume Line bot can get profile
        user_name = f"User_{user_id[-4:]}" # simplifying to avoid extra API call block
        timestamp = datetime.utcfromtimestamp(event.timestamp / 1000.0)

        # 1. URL Detection
        urls = URL_REGEX.findall(text)
        if urls:
            for url in urls:
                background_tasks.add_task(process_url, group_id, url)

        # 2. Wake Word Detection
        from app.services.llm_service import process_rag_query
        if text.startswith('@help'):
            clean_query = text[5:].strip()
            # Forward to RAG Engine in background or direct
            background_tasks.add_task(process_rag_query, group_id, clean_query, event.reply_token)
        else:
            # 3. General Chat
            async with async_session() as session:
                msg = RawMessage(
                    group_id=group_id,
                    user_name=user_name,
                    content=text,
                    timestamp=timestamp
                )
                session.add(msg)
                await session.commit()

    return "OK"

async def send_reply(reply_token: str, message: str):
    await messaging_api.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=message)]
        )
    )
