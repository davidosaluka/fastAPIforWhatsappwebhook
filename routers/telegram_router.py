import os
import re
import logging
from typing import Dict, Any
from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
import models
import httpx
from services.telegram_service import (
    send_telegram_message,
    edit_telegram_message,
    answer_callback_query,
    get_bot_token,
    TELEGRAM_API_BASE
)
import replyhandler

logger = logging.getLogger("telegram_router")
router = APIRouter()

AUTH = os.getenv("AUTH")
GRAPH_URL = os.getenv("GRAPH_URL")


@router.get("/set-webhook")
async def set_telegram_webhook(request: Request):
    """
    Convenience endpoint to configure Telegram webhook automatically.
    Points to https://<host>/telegram/webhook
    """
    token = get_bot_token()
    if not token:
        return {"status": "error", "message": "TELEGRAM_BOT_TOKEN is not set in environment."}

    # Build public webhook URL
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    proto = request.headers.get("x-forwarded-proto") or "https"
    webhook_url = f"{proto}://{host}/telegram/webhook"

    url = f"{TELEGRAM_API_BASE}{token}/setWebhook"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={"url": webhook_url})
            return {
                "configured_url": webhook_url,
                "telegram_response": resp.json()
            }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.post("/webhook")
async def telegram_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Primary Telegram Webhook handling commands, contact sharing, and order acceptance clicks.
    """
    try:
        update_data = await request.json()
    except Exception:
        return Response(status_code=200)

    # 1. Handle Messages (text commands or contact shares)
    message = update_data.get("message")
    if message:
        await handle_telegram_message(message, db)
        return Response(status_code=200)

    # 2. Handle Callback Queries (Rider taps [Accept Delivery] button)
    callback_query = update_data.get("callback_query")
    if callback_query:
        await handle_telegram_callback(callback_query, db)
        return Response(status_code=200)

    return Response(status_code=200)


async def handle_telegram_message(message: Dict[str, Any], db: AsyncSession):
    chat = message.get("chat", {})
    chat_id = str(chat.get("id"))
    text = (message.get("text") or "").strip()
    contact = message.get("contact")

    # --- A. RESTAURANT 1-CLICK ONBOARDING LINK (/start restaurant_<slug>) ---
    if text.startswith("/start restaurant_"):
        slug = text.replace("/start restaurant_", "").strip().lower()
        rest_res = await db.execute(
            select(models.Restaurants).where(models.Restaurants.slug == slug)
        )
        restaurant = rest_res.scalars().first()
        if not restaurant:
            # Auto-create restaurant if new
            pretty_name = slug.replace("_", " ").title()
            if "restaurant" not in pretty_name.lower():
                pretty_name += " Restaurant"
            restaurant = models.Restaurants(
                name=pretty_name,
                slug=slug,
                telegram_chat_id=chat_id,
                is_active=True
            )
            db.add(restaurant)
            await db.commit()
            await db.refresh(restaurant)
            await send_telegram_message(
                chat_id=chat_id,
                text=f"🎉 *New Restaurant Registered & Linked!*\n\nThis chat is now linked to receive incoming food orders for *{restaurant.name}* (`{slug}`)! 🍲✨\n\nYou will receive order pings with loud sound alerts right here.",
                parse_mode="Markdown"
            )
            return
        else:
            restaurant.telegram_chat_id = chat_id
            await db.commit()
            await send_telegram_message(
                chat_id=chat_id,
                text=f"🎉 *Success!*\n\nThis chat is now linked to receive incoming food orders for *{restaurant.name}*! 🍲✨\n\nYou will receive order pings with loud sound alerts right here.",
                parse_mode="Markdown"
            )
            return

    # --- B. RESTAURANT GROUP LINK COMMAND (/link_restaurant <slug>) ---
    if text.startswith("/link_restaurant"):
        parts = text.split()
        if len(parts) >= 2:
            slug = parts[1].strip().lower()
            rest_res = await db.execute(
                select(models.Restaurants).where(models.Restaurants.slug == slug)
            )
            restaurant = rest_res.scalars().first()
            if not restaurant:
                # Auto-create restaurant if new
                pretty_name = slug.replace("_", " ").title()
                if "restaurant" not in pretty_name.lower():
                    pretty_name += " Restaurant"
                restaurant = models.Restaurants(
                    name=pretty_name,
                    slug=slug,
                    telegram_chat_id=chat_id,
                    is_active=True
                )
                db.add(restaurant)
                await db.commit()
                await db.refresh(restaurant)
                await send_telegram_message(
                    chat_id=chat_id,
                    text=f"✅ *New Kitchen Registered & Linked!*\n\nIncoming orders for *{restaurant.name}* (`{slug}`) will now be dispatched to this chat. 🍲",
                    parse_mode="Markdown"
                )
                return
            else:
                restaurant.telegram_chat_id = chat_id
                await db.commit()
                await send_telegram_message(
                    chat_id=chat_id,
                    text=f"✅ *Kitchen Chat Linked!*\n\nIncoming orders for *{restaurant.name}* will now be dispatched to this chat. 🍲",
                    parse_mode="Markdown"
                )
                return
        else:
            await send_telegram_message(chat_id=chat_id, text="Usage: `/link_restaurant <slug>` (e.g. `/link_restaurant madam_g`)")
            return

    # --- C. RESTAURANT UNLINK COMMAND (/unlink_restaurant [slug]) ---
    if text.startswith("/unlink_restaurant"):
        parts = text.split()
        slug = parts[1].strip().lower() if len(parts) >= 2 else None
        if slug:
            rest_stmt = select(models.Restaurants).where(models.Restaurants.slug == slug)
        else:
            rest_stmt = select(models.Restaurants).where(models.Restaurants.telegram_chat_id == chat_id)

        rest_res = await db.execute(rest_stmt)
        restaurants = rest_res.scalars().all()
        if restaurants:
            for r in restaurants:
                r.telegram_chat_id = None
            await db.commit()
            await send_telegram_message(
                chat_id=chat_id,
                text="✅ *Unlinked Successfully!*\n\nThis chat will no longer receive restaurant orders. If you are a rider, send `/start` to link your rider account.",
                parse_mode="Markdown"
            )
            return
        else:
            await send_telegram_message(
                chat_id=chat_id,
                text="ℹ️ This chat is not currently linked to any restaurant.",
                parse_mode="Markdown"
            )
            return

    # --- C. RIDER PHONE NUMBER SHARING (Contact Card) ---
    if contact:
        raw_phone = contact.get("phone_number", "")
        clean_phone = re.sub(r'[^\d]', '', str(raw_phone))
        last_10 = clean_phone[-10:] if len(clean_phone) >= 10 else clean_phone
        phone_variants = replyhandler.get_phone_variants(raw_phone)

        # Look for rider in models.Riders
        rider_res = await db.execute(
            select(models.Riders).where(
                (models.Riders.rider_wa_number.in_(phone_variants)) |
                (models.Riders.rider_phonenumber_2.in_(phone_variants)) |
                (models.Riders.rider_wa_number.like(f"%{last_10}%"))
            )
        )
        rider = rider_res.scalars().first()
        if rider:
            rider.telegram_chat_id = chat_id
            await db.commit()
            await send_telegram_message(
                chat_id=chat_id,
                text=(
                    f"✅ *Profile Linked Successfully!*\n\n"
                    f"Welcome aboard, *{rider.first_name} {rider.last_name}*! 🛵💨\n\n"
                    f"You will now receive private 1-on-1 food delivery dispatch pings directly here.\n"
                    f"💡 *Tip:* Set a loud custom notification sound for this bot in Telegram so orders stand out!"
                ),
                parse_mode="Markdown",
                reply_markup={"remove_keyboard": True}
            )
        else:
            await send_telegram_message(
                chat_id=chat_id,
                text=(
                    f"⚠️ No registered InTime rider was found for phone *{raw_phone}*.\n\n"
                    f"Please ensure you are registered on InTime with this phone number or contact support at +234 815 103 3428."
                ),
                parse_mode="Markdown"
            )
        return

    # --- D. NORMAL RIDER /start COMMAND ---
    if text == "/start":
        # Check if already linked
        rider_res = await db.execute(
            select(models.Riders).where(models.Riders.telegram_chat_id == chat_id)
        )
        rider = rider_res.scalars().first()
        if rider:
            await send_telegram_message(
                chat_id=chat_id,
                text=(
                    f"Welcome back, *{rider.first_name}*! 🛵\n\n"
                    f"Your InTime rider account is active. You will receive direct 1-on-1 food delivery dispatch requests here."
                ),
                parse_mode="Markdown"
            )
        else:
            # Prompt rider to share phone number with 1 tap
            contact_keyboard = {
                "keyboard": [
                    [
                        {
                            "text": "📱 Share Phone Number",
                            "request_contact": True
                        }
                    ]
                ],
                "resize_keyboard": True,
                "one_time_keyboard": True
            }
            await send_telegram_message(
                chat_id=chat_id,
                text=(
                    f"👋 *Welcome to InTime Delivery!*\n\n"
                    f"To start receiving private food delivery requests on Telegram, tap the button below to link your registered phone number:"
                ),
                parse_mode="Markdown",
                reply_markup=contact_keyboard
            )
        return


async def handle_telegram_callback(callback_query: Dict[str, Any], db: AsyncSession):
    cq_id = callback_query["id"]
    data = callback_query.get("data", "")
    from_user = callback_query.get("from", {})
    user_id = str(from_user.get("id"))
    username = from_user.get("username")
    first_name = from_user.get("first_name", "Rider")
    user_display = f"@{username}" if username else first_name

    msg = callback_query.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    message_id = msg.get("message_id")

    if data.startswith("accept_food:"):
        order_num = data.split(":", 1)[1].strip()

        # Fetch order from DB
        ord_res = await db.execute(
            select(models.Orders).where(models.Orders.order_number == order_num)
        )
        order = ord_res.scalars().first()

        if not order:
            await answer_callback_query(cq_id, text="⚠️ Order not found.", show_alert=True)
            return

        # Check if order is already claimed by someone else
        if order.status != "confirmed":
            await answer_callback_query(
                cq_id,
                text=f"⚠️ Order #{order_num} has already been accepted by another rider!",
                show_alert=True
            )
            if chat_id and message_id:
                await edit_telegram_message(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"❌ *Order #{order_num} was claimed by another rider.*",
                    parse_mode="Markdown"
                )
            return

        # Look up rider record in models.Riders
        r_res = await db.execute(
            select(models.Riders).where(models.Riders.telegram_chat_id == user_id)
        )
        rider_obj = r_res.scalars().first()
        rider_phone = rider_obj.rider_wa_number if rider_obj else f"TG:@{username or user_id}"
        rider_display_name = f"{rider_obj.first_name} {rider_obj.last_name}" if rider_obj else user_display

        # 1. Lock and assign order in DB
        order.status = "rider_accepted"
        order.rider_wa_number = rider_phone
        order.delivery_progression_status = "awaiting_pickup"
        await db.commit()
        await db.refresh(order)

        # 2. Acknowledge button click
        await answer_callback_query(cq_id, text="✅ Order Accepted! Head to the restaurant for pickup.")

        # 3. Update winning rider's message with full trip details
        fare_display = order.customer_initial_offered_price or "800"
        try:
            fare_formatted = f"₦{int(fare_display):,}"
        except ValueError:
            fare_formatted = f"₦{fare_display}"

        # Clean meal details: strip individual pack/item prices for rider checklist
        raw_desc = order.package_description or ""
        clean_desc = re.sub(r'^Food Order from [^|]+ \|\s*', '', raw_desc)
        clean_desc = re.sub(r'\s*[-–—]\s*[₦N]?[\d,]+(?=\s*(?:\n|$))', '', clean_desc)
        clean_desc = re.sub(r'\s*\([₦N]?[\d,]+\)', '', clean_desc)

        winning_text = (
            f"✅ *YOU ACCEPTED THIS ORDER!* 🛵💨\n\n"
            f"*Order #:* `{order.order_number}`\n"
            f"📍 *Pickup Restaurant:* {order.pickup_location_name}\n"
            f"🏁 *Dropoff Destination:* {order.dropoff_location_name}\n\n"
            f"📋 *Meal Checklist:*\n{clean_desc}\n\n"
            f"💳 *Total Order Amount:* *{fare_formatted}*\n\n"
            f"👉 *Next Action:* Proceed to the restaurant now to collect the food package!"
        )
        if chat_id and message_id:
            await edit_telegram_message(
                chat_id=chat_id,
                message_id=message_id,
                text=winning_text,
                parse_mode="Markdown"
            )

        # 4. Edit other riders' messages who also received this offer
        try:
            offers_res = await db.execute(
                select(models.RiderOffer).where(models.RiderOffer.order_number == order_num)
            )
            offers = offers_res.scalars().all()
            for off in offers:
                if off.rider_wa_number.startswith("TG:"):
                    parts = off.rider_wa_number.split(":")
                    if len(parts) >= 3:
                        other_chat = parts[1]
                        other_msg = int(parts[2])
                        if str(other_chat) != str(chat_id):
                            await edit_telegram_message(
                                chat_id=other_chat,
                                message_id=other_msg,
                                text=f"❌ *Order #{order_num} was claimed by another rider.*",
                                parse_mode="Markdown"
                            )
        except Exception as edit_err:
            logger.warning(f"Failed to edit peer rider messages for order {order_num}: {edit_err}")

        # 5. Notify Customer on WhatsApp
        try:
            rest_clean = order.pickup_location_name.replace(", Lagos", "")
            cust_msg = (
                f"🛵 *Rider Assigned to Your Food Order!* 🍲💨\n\n"
                f"Great news! Dispatch rider *{rider_display_name}* has accepted your order from *{rest_clean}* and is on the way to pick it up.\n\n"
                f"Order #: *{order.order_number}*\n"
                f"We will notify you as soon as the meal is picked up and en route to your address!"
            )
            await replyhandler.send_custom_message(order.sender_wa_number, cust_msg, AUTH, GRAPH_URL)
        except Exception as cust_err:
            logger.warning(f"Failed to send customer WhatsApp notification on TG claim: {cust_err}")

        # 6. Ping Restaurant on Telegram
        try:
            # Query restaurant chat ID
            rest_name_clean = order.pickup_location_name.replace(", Lagos", "").strip()
            rest_db_res = await db.execute(
                select(models.Restaurants).where(models.Restaurants.name.ilike(f"%{rest_name_clean}%"))
            )
            rest_obj = rest_db_res.scalars().first()
            rest_chat_id = rest_obj.telegram_chat_id if rest_obj else os.getenv("TELEGRAM_RESTAURANT_CHAT_ID")

            if rest_chat_id:
                rest_alert = (
                    f"🛵 *RIDER ASSIGNED!* 🍲\n\n"
                    f"Dispatch rider *{rider_display_name}* (`{rider_phone}`) has accepted *Order #{order.order_number}* and is en route to the kitchen for pickup!"
                )
                await send_telegram_message(chat_id=rest_chat_id, text=rest_alert, parse_mode="Markdown")
        except Exception as r_alert_err:
            logger.warning(f"Failed to alert restaurant on TG rider claim: {r_alert_err}")

