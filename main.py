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


#Base.metadata.create_all(bind=engine)
@asynccontextmanager
async def lifespan(_app: FastAPI):
    #startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    scheduler = start_scheduler() 
    yield

    #shutdown
    scheduler.shutdown()
    await engine.dispose()

app = FastAPI(lifespan=lifespan)

#@app.get("/")
#@app.post("/webhook/sendMessage", response_model=apiPostRequestResponse, status_code=status.HTTP_200_OK)

app.include_router(createAPIrequest.router, prefix="/webhook", tags=["createAPIrequest"])



