import asyncio
from sqlalchemy import select
from app.database import async_session
from app.models import RawMessage

async def list_messages():
    print("正在從資料庫讀取目前的訊息記錄...")
    async with async_session() as session:
        stmt = select(RawMessage).order_by(RawMessage.timestamp.desc())
        result = await session.execute(stmt)
        messages = result.scalars().all()
        
        if not messages:
            print("目前資料庫中沒有任何訊息記錄。")
            return
            
        print(f"\n找到 {len(messages)} 則訊息：")
        print("-" * 50)
        for msg in messages:
            source = f"Group: {msg.group_id}" if msg.group_id else "Private"
            print(f"[{msg.timestamp}] {source} | {msg.user_name}: {msg.content} (Processed: {msg.is_processed})")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(list_messages())
