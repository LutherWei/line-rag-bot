import re
from fastapi import Request, BackgroundTasks
from linebot.v3 import WebhookParser
from linebot.v3.messaging import (
    AsyncApiClient, AsyncMessagingApi, Configuration,
    ReplyMessageRequest, PushMessageRequest, TextMessage
)
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from app.config import settings
from app.database import async_session
from app.models import RawMessage
import os
from app.services.crawler_service import process_url
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

configuration = Configuration(access_token=settings.line_channel_access_token)
_async_api_client = None
_messaging_api = None

def get_messaging_api() -> AsyncMessagingApi:
    global _async_api_client, _messaging_api
    if _messaging_api is None:
        _async_api_client = AsyncApiClient(configuration)
        _messaging_api = AsyncMessagingApi(_async_api_client)
    return _messaging_api

parser = WebhookParser(settings.line_channel_secret)

URL_REGEX = re.compile(r'(https?://[^\s]+)')

USAGE_MESSAGE = (
    "📖 使用方式：\n"
    "輸入 @help <你的問題>\n"
    "例如：@help 明天有練習嗎？\n\n"
    "Bot 會根據群組聊天記錄和連結內容來回答你的問題。"
)
LOADING_MESSAGE = (
    "正在處理中，請稍候...\n"
    "Loading..."
)


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

        source_type = event.source.type  # "user", "group", or "room"
        text = event.message.text

        if source_type == "group":
            # ── Group message: silent collection only ──
            await _handle_group_message(event, text, background_tasks)

        elif source_type == "user":
            # ── Friend (1-on-1) message: respond to queries ──
            await _handle_friend_message(event, text, background_tasks)

        else:
            # Room or other source types — ignore
            logger.info(f"Ignoring message from source type: {source_type}")

    return "OK"


async def _handle_group_message(event, text: str, background_tasks: BackgroundTasks):
    """
    Handle messages from groups: silently store chat logs and process URLs.
    Never reply in the group.
    """
    group_id = event.source.group_id
    user_id = event.source.user_id

    # Check if this group is in the allowed list
    allowed = settings.allowed_group_id_list
    if allowed and group_id not in allowed:
        logger.info(f"Ignoring message from non-allowed group: {group_id}")
        return

    logger.info(f"[Group Silent] group={group_id} user={user_id} text={text[:50]}")

    user_name = f"User_{user_id[-4:]}" if user_id else "Unknown"
    if user_id:
        try:
            api = get_messaging_api()
            profile = await api.get_group_member_profile(group_id, user_id)
            if profile and profile.display_name:
                user_name = profile.display_name
        except Exception as e:
            logger.warning(f"Could not fetch profile for {user_id}: {e}")
            
    timestamp = datetime.utcfromtimestamp(event.timestamp / 1000.0)

    # 1. URL Detection — process in background
    urls = URL_REGEX.findall(text)
    if urls:
        for url in urls:
            background_tasks.add_task(process_url, group_id, url)

    # 2. Store chat message (skip @help in group — just store as regular msg)
    async with async_session() as session:
        msg = RawMessage(
            group_id=group_id,
            user_name=user_name,
            content=text,
            timestamp=timestamp
        )
        session.add(msg)
        await session.commit()

    # 2b. Vectorize message in real-time in background
    from app.services.llm_service import vectorize_and_store_message
    background_tasks.add_task(vectorize_and_store_message, group_id, user_name, text, timestamp)
    
    # 3. Append to local TXT file for real-time RAG context
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, f"group_{group_id}.txt")
    
    # Format: [YYYY-MM-DD HH:MM:SS] User: Message
    log_line = f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {user_name}: {text}\n"
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(log_line)


async def _handle_friend_message(event, text: str, background_tasks: BackgroundTasks):
    """
    Handle 1-on-1 friend messages: respond to @help queries using Push Message API.
    """
    user_id = event.source.user_id
    logger.info(f"[Friend Message] user={user_id} text={text[:1000]}")

    if text.startswith('@help'):
        clean_query = text[5:].strip()
        if not clean_query:
            await send_push_message(user_id, USAGE_MESSAGE)
            return

        # Determine which group's knowledge base to search
        allowed = settings.allowed_group_id_list
        logger.info(f"[DEBUG] allowed_group_ids raw='{settings.allowed_group_ids}' list={allowed}")
        if len(allowed) == 1:
            target_group_id = allowed[0]
        elif len(allowed) > 1:
            # For now, search across the first allowed group
            # TODO: support multi-group selection in the future
            target_group_id = allowed[0]
            logger.info(f"Multiple allowed groups; defaulting to first: {target_group_id}")
        else:
            await send_push_message(user_id, "⚠️ 尚未設定監聽群組，無法查詢。")
            return

        logger.info(f"[Friend Query] user={user_id} query={clean_query} group={target_group_id}")

        # Send LOADING message first before calling RAG pipeline
        await send_push_message(user_id, LOADING_MESSAGE)

        # Forward to RAG engine in background
        from app.services.llm_service import process_rag_query
        background_tasks.add_task(process_rag_query, target_group_id, clean_query, user_id)
    else:
        # Not a query — reply with usage instructions
        await send_push_message(user_id, USAGE_MESSAGE)


async def send_reply(reply_token: str, message: str):
    """Reply using reply token (kept for backward compatibility)."""
    api = get_messaging_api()
    await api.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=message)]
        )
    )


async def send_push_message(user_id: str, message: str):
    """Send a push message to a specific user (friend)."""
    api = get_messaging_api()
    await api.push_message(
        PushMessageRequest(
            to=user_id,
            messages=[TextMessage(text=message)]
        )
    )
