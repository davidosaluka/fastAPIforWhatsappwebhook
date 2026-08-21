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

from sqlalchemy import text

#Base.metadata.create_all(bind=engine)
@asynccontextmanager
async def lifespan(_app: FastAPI):
    #startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            if engine.dialect.name == "postgresql":
                await conn.execute(text('ALTER TABLE "apiRequests" ADD COLUMN IF NOT EXISTS wamid TEXT;'))
                await conn.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS ix_apiRequests_wamid ON "apiRequests" (wamid);'))
                try:
                    await conn.execute(text('ALTER TABLE riders RENAME COLUMN availabilty_status TO availability_status;'))
                except Exception:
                    pass
                try:
                    await conn.execute(text('ALTER TABLE riders ADD COLUMN IF NOT EXISTS availability_status VARCHAR(50);'))
                except Exception:
                    pass
                try:
                    await conn.execute(text('ALTER TABLE orders RENAME COLUMN customer_intital_offered_price TO customer_initial_offered_price;'))
                except Exception:
                    pass
                try:
                    await conn.execute(text('ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_initial_offered_price VARCHAR(50);'))
                except Exception:
                    pass
            elif engine.dialect.name == "sqlite":
                try:
                    await conn.execute(text('ALTER TABLE "apiRequests" ADD COLUMN wamid TEXT;'))
                    await conn.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS ix_apiRequests_wamid ON "apiRequests" (wamid);'))
                except Exception:
                    pass
                try:
                    await conn.execute(text('ALTER TABLE riders ADD COLUMN availability_status VARCHAR(50);'))
                except Exception:
                    pass
                try:
                    await conn.execute(text('ALTER TABLE orders ADD COLUMN customer_initial_offered_price VARCHAR(50);'))
                except Exception:
                    pass
        except Exception as e:
            print(f"Migration check warning: {e}")
    yield
    #shutdown
    await engine.dispose()

app = FastAPI(lifespan=lifespan)

#@app.get("/")
#@app.post("/webhook/sendMessage", response_model=apiPostRequestResponse, status_code=status.HTTP_200_OK)

app.include_router(createAPIrequest.router, prefix="/webhook", tags=["createAPIrequest"])



