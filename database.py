from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from dotenv import load_dotenv
import os

load_dotenv()


'''postGres/Supabase config'''
DB_URL = os.getenv("DATABASE_URL")
engine = create_async_engine(
        DB_URL,     
        connect_args={
        "statement_cache_size": 0
    })

'''sqlite config below'''
#DB_URL = "sqlite+aiosqlite:///./intime.db"
#engine = create_async_engine(DB_URL, connect_args={"check_same_thread": False})

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
