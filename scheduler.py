# scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, update
from datetime import datetime, UTC
import logging
import os
from database import AsyncSessionLocal
import models
import replyhandler


from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

LAST_CHECKIN_DATE = None

def get_graph_url() -> str:
    url = (os.getenv("GRAPH_URL") or "").strip()
    if url.startswith("GRAPH_URL="):
        url = url[len("GRAPH_URL="):].strip()
    url = url.strip("\"'")
    if not url:
        phone_id = os.getenv("PHONE_NUMBER_ID", "1089747250880518")
        return f"https://graph.facebook.com/v21.0/{phone_id}/messages"
    if url.isdigit():
        return f"https://graph.facebook.com/v21.0/{url}/messages"
    if not url.startswith("http://") and not url.startswith("https://"):
        return f"https://{url}"
    return url

def get_auth_token() -> str:
    auth = (os.getenv("AUTHORIZATION") or "").strip()
    if auth.startswith("Bearer "):
        auth = auth[len("Bearer "):].strip()
    if auth.startswith("AUTHORIZATION="):
        auth = auth[len("AUTHORIZATION="):].strip()
    return auth.strip("\"'")

async def send_daily_rider_templates():
    """Sends WhatsApp check-in template to all riders daily at 7:00 AM and sets their status to offline until they check in."""
    global LAST_CHECKIN_DATE
    lagos_tz = datetime.now(UTC).date()
    if LAST_CHECKIN_DATE == lagos_tz:
        logger.info(f"Daily check-in already sent today ({lagos_tz}). Skipping duplicate execution.")
        return

    LAST_CHECKIN_DATE = lagos_tz
    auth = get_auth_token()
    graph_url = get_graph_url()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(models.Riders))
        riders = result.scalars().all()
        # Unpack as plain records so session.rollback() never triggers MissingGreenlet on expired attributes
        rider_records = [(r.id, r.rider_wa_number) for r in riders]

        for rider_id, rider_wa_number in rider_records:
            if not rider_wa_number:
                continue
            try:
                await replyhandler.send_daily_rider_checkin_template(
                    rider_wa_number=rider_wa_number,
                    auth=auth,
                    graph_url=graph_url
                )
                logger.info(f"Sent daily check-in template to rider {rider_id}")             
                possible_numbers = replyhandler.get_phone_variants(rider_wa_number)
                await session.execute(
                    update(models.Riders)
                    .where(models.Riders.rider_wa_number.in_(possible_numbers))
                    .values(availability_status="offline")
                )
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to send template or update rider status {rider_id}: {e}")

def start_scheduler():
    scheduler = AsyncIOScheduler(timezone="Africa/Lagos")
    scheduler.add_job(
        send_daily_rider_templates,
        trigger=CronTrigger(hour=7, minute=0, timezone="Africa/Lagos"),
        id="daily_rider_template",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
