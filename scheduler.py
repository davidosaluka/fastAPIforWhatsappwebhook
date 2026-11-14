# scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, update
from datetime import datetime, UTC, timedelta
import logging
import os
from database import AsyncSessionLocal
import models
import replyhandler
from services import telegram_service


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
    enable_checkin = os.getenv("ENABLE_RIDER_CHECKIN_SCHEDULER", "false").lower() in ("true", "1", "yes")
    if not enable_checkin:
        logger.info("Daily rider check-in worker is currently PAUSED. Skipping execution.")
        return

    global LAST_CHECKIN_DATE
    lagos_tz = (datetime.now(UTC) + timedelta(hours=1)).date()
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

async def run_daily_restaurant_sales_report():
    """Sends the daily restaurant sales summary to active restaurant Telegram chats."""
    logger.info("Running scheduled daily restaurant sales report...")
    try:
        async with AsyncSessionLocal() as db:
            sent_count = await telegram_service.send_daily_restaurant_sales_report(db)
            logger.info(f"Daily restaurant sales report sent to {sent_count} chat(s).")
    except Exception as e:
        logger.error(f"Error in run_daily_restaurant_sales_report: {e}")


async def run_weekly_restaurant_sales_report():
    """Sends the weekly restaurant sales CSV report every Saturday on Telegram."""
    logger.info("Running scheduled weekly Saturday restaurant sales report...")
    try:
        async with AsyncSessionLocal() as db:
            sent_count = await telegram_service.send_weekly_restaurant_sales_report(db)
            logger.info(f"Weekly Saturday restaurant sales report sent to {sent_count} chat(s).")
    except Exception as e:
        logger.error(f"Error in run_weekly_restaurant_sales_report: {e}")


def start_scheduler():
    scheduler = AsyncIOScheduler(timezone="Africa/Lagos")
    enable_checkin = os.getenv("ENABLE_RIDER_CHECKIN_SCHEDULER", "false").lower() in ("true", "1", "yes")
    if enable_checkin:
        scheduler.add_job(
            send_daily_rider_templates,
            trigger=CronTrigger(hour=7, minute=0, timezone="Africa/Lagos"),
            id="daily_rider_template",
            replace_existing=True,
        )
        logger.info("Daily rider check-in scheduler is ACTIVE (7:00 AM Lagos).")
    else:
        logger.info("Daily rider check-in scheduler worker is currently PAUSED.")

    daily_hour = int(os.getenv("DAILY_SALES_REPORT_HOUR", "21"))
    daily_minute = int(os.getenv("DAILY_SALES_REPORT_MINUTE", "0"))
    scheduler.add_job(
        run_daily_restaurant_sales_report,
        trigger=CronTrigger(hour=daily_hour, minute=daily_minute, timezone="Africa/Lagos"),
        id="daily_restaurant_sales_report",
        replace_existing=True,
    )
    logger.info(f"Daily restaurant sales report scheduled at {daily_hour:02d}:{daily_minute:02d} Africa/Lagos.")

    weekly_hour = int(os.getenv("WEEKLY_SALES_REPORT_HOUR", "21"))
    weekly_minute = int(os.getenv("WEEKLY_SALES_REPORT_MINUTE", "5"))
    scheduler.add_job(
        run_weekly_restaurant_sales_report,
        trigger=CronTrigger(day_of_week="sat", hour=weekly_hour, minute=weekly_minute, timezone="Africa/Lagos"),
        id="weekly_restaurant_sales_report",
        replace_existing=True,
    )
    logger.info(f"Weekly Saturday restaurant sales report scheduled at {weekly_hour:02d}:{weekly_minute:02d} Africa/Lagos.")

    scheduler.start()
    return scheduler
