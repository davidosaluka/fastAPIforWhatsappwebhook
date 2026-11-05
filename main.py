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
from routers import createAPIrequest, flow_endpoint, telegram_router
from scheduler import start_scheduler
from fastapi.staticfiles import StaticFiles
import os

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
                await conn.execute(text('ALTER TABLE orders ALTER COLUMN package_description TYPE TEXT;'))
                await conn.execute(text('ALTER TABLE orders ALTER COLUMN dropoff_location_name TYPE TEXT;'))
                print("🟢 [MIGRATION] orders.package_description and dropoff_location_name expanded to TEXT.")
        except Exception as e:
            print(f"Migration note (orders add/alter cols): {e}")

        # users.is_deleted (soft-delete flag) and address column
        try:
            async with engine.begin() as conn:
                await conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE;'))
                await conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS address TEXT;'))
                print("🟢 [MIGRATION] users.is_deleted and users.address columns ensured.")
        except Exception as e:
            print(f"Migration note (users columns): {e}")

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
        # riders.telegram_chat_id
        try:
            async with engine.begin() as conn:
                await conn.execute(text('ALTER TABLE riders ADD COLUMN IF NOT EXISTS telegram_chat_id VARCHAR(50);'))
                await conn.execute(text('CREATE INDEX IF NOT EXISTS ix_riders_telegram_chat_id ON riders (telegram_chat_id);'))
                print("🟢 [MIGRATION] riders.telegram_chat_id column ensured.")
        except Exception as e:
            print(f"Migration note (riders telegram_chat_id): {e}")

        # restaurants table
        try:
            async with engine.begin() as conn:
                await conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS restaurants (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100) NOT NULL UNIQUE,
                        slug VARCHAR(50) NOT NULL UNIQUE,
                        telegram_chat_id VARCHAR(50),
                        address TEXT,
                        phone_number VARCHAR(50),
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );
                '''))
                await conn.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS ix_restaurants_slug ON restaurants (slug);'))
                init_chat = os.getenv("TELEGRAM_RESTAURANT_CHAT_ID", "").strip() or None
                await conn.execute(text('''
                    INSERT INTO restaurants (name, slug, telegram_chat_id, address, is_active)
                    VALUES ('Madam G Restaurant', 'madam_g', :chat_id, 'Madam G Kitchen, Lagos', TRUE)
                    ON CONFLICT (slug) DO UPDATE SET telegram_chat_id = COALESCE(restaurants.telegram_chat_id, EXCLUDED.telegram_chat_id);
                '''), {"chat_id": init_chat})
                print("🟢 [MIGRATION] restaurants table ensured.")
        except Exception as e:
            print(f"Migration note (restaurants table): {e}")

        # payment, credit_balance, and restaurant bank accounts
        try:
            async with engine.begin() as conn:
                await conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS credit_balance INTEGER NOT NULL DEFAULT 0;'))
                await conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_status VARCHAR(50) DEFAULT 'pending_payment';"))
                await conn.execute(text('ALTER TABLE orders ADD COLUMN IF NOT EXISTS paid_amount INTEGER DEFAULT 0;'))
                await conn.execute(text('ALTER TABLE orders ADD COLUMN IF NOT EXISTS receipt_image_id TEXT;'))
                await conn.execute(text('ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS account_name VARCHAR(100);'))
                await conn.execute(text('ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS account_number VARCHAR(50);'))
                await conn.execute(text('ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS bank_name VARCHAR(100);'))
                await conn.execute(text("""
                    UPDATE restaurants 
                    SET account_name = COALESCE(account_name, 'Christiana Adamu'),
                        account_number = COALESCE(account_number, '5330778741'),
                        bank_name = COALESCE(bank_name, 'Moniepoint')
                    WHERE slug = 'madam_g';
                """))
                print("🟢 [MIGRATION] payment, credit_balance, and restaurant bank columns ensured.")
        except Exception as e:
            print(f"Migration note (payment cols): {e}")



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
            'ALTER TABLE users ADD COLUMN credit_balance INTEGER DEFAULT 0;',
            'ALTER TABLE orders ADD COLUMN payment_status VARCHAR(50) DEFAULT "pending_payment";',
            'ALTER TABLE orders ADD COLUMN paid_amount INTEGER DEFAULT 0;',
            'ALTER TABLE orders ADD COLUMN receipt_image_id TEXT;',
            'ALTER TABLE restaurants ADD COLUMN account_name VARCHAR(100);',
            'ALTER TABLE restaurants ADD COLUMN account_number VARCHAR(50);',
            'ALTER TABLE restaurants ADD COLUMN bank_name VARCHAR(100);',
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

        try:
            async with engine.begin() as conn:
                await conn.execute(text('ALTER TABLE riders ADD COLUMN telegram_chat_id VARCHAR(50);'))
        except Exception:
            pass
        try:
            async with engine.begin() as conn:
                await conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS restaurants (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name VARCHAR(100) NOT NULL UNIQUE,
                        slug VARCHAR(50) NOT NULL UNIQUE,
                        telegram_chat_id VARCHAR(50),
                        address TEXT,
                        phone_number VARCHAR(50),
                        is_active BOOLEAN NOT NULL DEFAULT 1,
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
app.include_router(flow_endpoint.router, prefix="/api", tags=["flow_endpoint"])
app.include_router(telegram_router.router, prefix="/telegram", tags=["telegram"])

# Mount static directory for restaurant logos
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")



