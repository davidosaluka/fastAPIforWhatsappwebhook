# scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, update
import logging
import os
from database import AsyncSessionLocal
from models import Riders
from replyhandler import send_daily_rider_checkin_template


logger = logging.getLogger(__name__)

AUTH = os.getenv("AUTHORIZATION")
GRAPH_URL = os.getenv("GRAPH_URL")

async def send_daily_rider_templates():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Riders))
        riders = result.scalars().all()

        for rider in riders:
            try:
                await send_daily_rider_checkin_template(
                    rider_wa_number=rider.rider_wa_number,
                    auth=AUTH,
                    graph_url=GRAPH_URL
                )
                logger.info(f"Sent daily template to rider {rider.id}")             
                await session.execute(
            update(Riders)
            .where(Riders.rider_wa_number == rider.rider_wa_number)
            .values(availabilty_status="offline")
            )
                await session.commit()

                
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to send template or update rider status {rider.id}: {e}")

def start_scheduler():
    scheduler = AsyncIOScheduler(timezone="Africa/Lagos")
    scheduler.add_job(
        send_daily_rider_templates,
        trigger=CronTrigger(hour=18, minute=50),
        id="daily_rider_template",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler