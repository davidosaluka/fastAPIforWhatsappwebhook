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
        except Exception as e:
            print(f"Migration note (orders add cols): {e}")

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
        try:
            async with engine.begin() as conn:
                await conn.execute(text('ALTER TABLE orders ADD COLUMN customer_initial_offered_price VARCHAR(50);'))
                await conn.execute(text('ALTER TABLE orders ADD COLUMN is_drug BOOLEAN DEFAULT 0;'))
                await conn.execute(text('ALTER TABLE orders ADD COLUMN is_urgent BOOLEAN DEFAULT 0;'))
                await conn.execute(text('ALTER TABLE orders ADD COLUMN is_priority BOOLEAN DEFAULT 0;'))
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



