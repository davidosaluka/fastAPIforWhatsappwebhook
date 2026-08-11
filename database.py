from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from dotenv import load_dotenv
import os

load_dotenv()


'''postGres/Supabase config'''
DB_URL = os.getenv("DATABASE_URL")
if DB_URL:
    if DB_URL.startswith("postgres://"):
        DB_URL = DB_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    elif DB_URL.startswith("postgresql://") and not DB_URL.startswith("postgresql+asyncpg://"):
        DB_URL = DB_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    engine = create_async_engine(
        DB_URL,     
        connect_args={
            "statement_cache_size": 0
        }
    )
else:
    '''sqlite config fallback'''
    DB_URL = "sqlite+aiosqlite:///./intime.db"
    engine = create_async_engine(DB_URL, connect_args={"check_same_thread": False})

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
