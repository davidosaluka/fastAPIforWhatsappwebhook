# scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, update
import logging
import os
from database import AsyncSessionLocal
import models
import replyhandler


logger = logging.getLogger(__name__)

AUTH = os.getenv("AUTHORIZATION")
GRAPH_URL = os.getenv("GRAPH_URL")

LAST_CHECKIN_DATE = None

async def send_daily_rider_templates():
    """Sends WhatsApp check-in template to all riders daily at 8:00 AM and sets their status to offline until they check in."""
    global LAST_CHECKIN_DATE
    lagos_tz = datetime.now(UTC).date()
    if LAST_CHECKIN_DATE == lagos_tz:
        logger.info(f"Daily check-in already sent today ({lagos_tz}). Skipping duplicate execution.")
        return

    LAST_CHECKIN_DATE = lagos_tz

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(models.Riders))
        riders = result.scalars().all()

        for rider in riders:
            try:
                await replyhandler.send_daily_rider_checkin_template(
                    rider_wa_number=rider.rider_wa_number,
                    auth=AUTH,
                    graph_url=GRAPH_URL
                )
                logger.info(f"Sent daily check-in template to rider {rider.id}")             
                possible_numbers = replyhandler.get_phone_variants(rider.rider_wa_number)
                await session.execute(
                    update(models.Riders)
                    .where(models.Riders.rider_wa_number.in_(possible_numbers))
                    .values(availability_status="offline")
                )
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to send template or update rider status {rider.id}: {e}")

def start_scheduler():
    scheduler = AsyncIOScheduler(timezone="Africa/Lagos")
    scheduler.add_job(
        send_daily_rider_templates,
        trigger=CronTrigger(hour=10, minute=0),
        id="daily_rider_template",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
