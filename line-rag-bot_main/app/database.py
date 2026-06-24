from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.config import settings

engine = create_async_engine(
    settings.cleaned_database_url, 
    echo=False,
    connect_args={"ssl": "require"} if "neon.tech" in settings.database_url else {}
)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


Base = declarative_base()

async def get_db():
    async with async_session() as session:
        yield session
