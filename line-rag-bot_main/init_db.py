import asyncio
from app.database import engine, Base
from app.models import RawMessage, ExtractedUrl

async def init_db():
    print("正在連線至資料庫並建立資料表...")
    try:
        async with engine.begin() as conn:
            # 建立所有繼承自 Base 的資料表
            await conn.run_sync(Base.metadata.create_all)
        print("資料表建立成功！")
    except Exception as e:
        print(f"建立資料表時發生錯誤: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(init_db())
