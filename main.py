from typing import Annotated
from contextlib import asynccontextmanager
from fastapi import FastAPI, status, Request, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
import models
import json
from database import Base, engine, get_db
from schemas import apiPostRequestResponse, apiRequestCreate
from routers import createAPIrequest
from scheduler import start_scheduler

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from sqlalchemy import text

#Base.metadata.create_all(bind=engine)
@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 1. Base tables creation
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Schema DDL Migrations (each in isolated transaction block)
    if engine.dialect.name == "postgresql":
        # apiRequests.wamid
        try:
            async with engine.begin() as conn:
                await conn.execute(text('ALTER TABLE "apiRequests" ADD COLUMN IF NOT EXISTS wamid TEXT;'))
                await conn.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS ix_apiRequests_wamid ON "apiRequests" (wamid);'))
        except Exception as e:
            print(f"Migration note (apiRequests wamid): {e}")

        # riders.availability_status (rename legacy typo availabilty_status)
        try:
            async with engine.begin() as conn:
                await conn.execute(text('ALTER TABLE riders RENAME COLUMN availabilty_status TO availability_status;'))
                print("🟢 [MIGRATION] Successfully renamed riders.availabilty_status -> availability_status")
        except Exception as e:
            print(f"Migration note (riders rename): {e}")

        try:
            async with engine.begin() as conn:
                await conn.execute(text('ALTER TABLE riders ADD COLUMN IF NOT EXISTS availability_status VARCHAR(50);'))
        except Exception as e:
            print(f"Migration note (riders add col): {e}")

        # orders.customer_initial_offered_price (rename legacy typo customer_intital_offered_price)
        try:
            async with engine.begin() as conn:
                await conn.execute(text('ALTER TABLE orders RENAME COLUMN customer_intital_offered_price TO customer_initial_offered_price;'))
                print("🟢 [MIGRATION] Successfully renamed orders.customer_intital_offered_price -> customer_initial_offered_price")
        except Exception as e:
            print(f"Migration note (orders rename): {e}")

        try:
            async with engine.begin() as conn:
                await conn.execute(text('ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_initial_offered_price VARCHAR(50);'))
                await conn.execute(text('ALTER TABLE orders ADD COLUMN IF NOT EXISTS is_drug BOOLEAN DEFAULT FALSE;'))
                await conn.execute(text('ALTER TABLE orders ADD COLUMN IF NOT EXISTS is_urgent BOOLEAN DEFAULT FALSE;'))
                await conn.execute(text('ALTER TABLE orders ADD COLUMN IF NOT EXISTS is_priority BOOLEAN DEFAULT FALSE;'))
                await conn.execute(text('ALTER TABLE orders ADD COLUMN IF NOT EXISTS verification_code VARCHAR(10);'))
                await conn.execute(text('ALTER TABLE orders ADD COLUMN IF NOT EXISTS verification_attempts INTEGER DEFAULT 0;'))
        except Exception as e:
            print(f"Migration note (orders add cols): {e}")

        # users.is_deleted (soft-delete flag)
        try:
            async with engine.begin() as conn:
                await conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE;'))
                print("🟢 [MIGRATION] users.is_deleted column ensured.")
        except Exception as e:
            print(f"Migration note (users is_deleted): {e}")

        # rider_ratings table
        try:
            async with engine.begin() as conn:
                await conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS rider_ratings (
                        id SERIAL PRIMARY KEY,
                        rider_wa_number VARCHAR(50) NOT NULL,
                        order_number VARCHAR(50) NOT NULL UNIQUE,
                        rating INTEGER NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );
                '''))
                await conn.execute(text('CREATE INDEX IF NOT EXISTS ix_rider_ratings_rider_wa_number ON rider_ratings (rider_wa_number);'))
                await conn.execute(text('CREATE INDEX IF NOT EXISTS ix_rider_ratings_order_number ON rider_ratings (order_number);'))
                print("🟢 [MIGRATION] rider_ratings table ensured.")
        except Exception as e:
            print(f"Migration note (rider_ratings): {e}")

    elif engine.dialect.name == "sqlite":
        try:
            async with engine.begin() as conn:
                await conn.execute(text('ALTER TABLE "apiRequests" ADD COLUMN wamid TEXT;'))
                await conn.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS ix_apiRequests_wamid ON "apiRequests" (wamid);'))
        except Exception:
            pass
        try:
            async with engine.begin() as conn:
                await conn.execute(text('ALTER TABLE riders ADD COLUMN availability_status VARCHAR(50);'))
        except Exception:
            pass
        for col_stmt in [
            'ALTER TABLE orders ADD COLUMN customer_initial_offered_price VARCHAR(50);',
            'ALTER TABLE orders ADD COLUMN is_drug BOOLEAN DEFAULT 0;',
            'ALTER TABLE orders ADD COLUMN is_urgent BOOLEAN DEFAULT 0;',
            'ALTER TABLE orders ADD COLUMN is_priority BOOLEAN DEFAULT 0;',
            'ALTER TABLE orders ADD COLUMN verification_code VARCHAR(10);',
            'ALTER TABLE orders ADD COLUMN verification_attempts INTEGER DEFAULT 0;',
        ]:
            try:
                async with engine.begin() as conn:
                    await conn.execute(text(col_stmt))
            except Exception:
                pass
        try:
            async with engine.begin() as conn:
                await conn.execute(text('ALTER TABLE users ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0;'))
        except Exception:
            pass
        try:
            async with engine.begin() as conn:
                await conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS rider_ratings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        rider_wa_number VARCHAR(50) NOT NULL,
                        order_number VARCHAR(50) NOT NULL UNIQUE,
                        rating INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                '''))
        except Exception:
            pass

    scheduler = start_scheduler()
    yield
    # Shutdown
    scheduler.shutdown()
    await engine.dispose()

app = FastAPI(lifespan=lifespan)

#@app.get("/")
#@app.post("/webhook/sendMessage", response_model=apiPostRequestResponse, status_code=status.HTTP_200_OK)

app.include_router(createAPIrequest.router, prefix="/webhook", tags=["createAPIrequest"])



