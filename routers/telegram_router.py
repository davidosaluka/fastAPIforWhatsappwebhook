import os
import re
import logging
import string
import random
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
    edit_telegram_caption,
    answer_callback_query,
    send_telegram_audio,
    RINGTONE_INSTRUCTIONS,
    get_bot_token,
    TELEGRAM_API_BASE
)
import replyhandler

logger = logging.getLogger("telegram_router")
router = APIRouter()

def get_auth_token() -> str:
    auth = (os.getenv("AUTHORIZATION") or os.getenv("AUTH") or os.getenv("WHATSAPP_TOKEN") or "").strip()
    if auth.startswith("Bearer "):
        auth = auth[len("Bearer "):].strip()
    if auth.startswith("AUTHORIZATION="):
        auth = auth[len("AUTHORIZATION="):].strip()
    return auth.strip("\"'")


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


AUTH = get_auth_token()
GRAPH_URL = get_graph_url()


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
    AUTH = get_auth_token()
    GRAPH_URL = get_graph_url()
    chat = message.get("chat", {})
    chat_id = str(chat.get("id"))
    from_user = message.get("from", {})
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
            await send_telegram_audio(chat_id=chat_id, caption=RINGTONE_INSTRUCTIONS)
            return
        else:
            restaurant.telegram_chat_id = chat_id
            await db.commit()
            await send_telegram_message(
                chat_id=chat_id,
                text=f"🎉 *Success!*\n\nThis chat is now linked to receive incoming food orders for *{restaurant.name}*! 🍲✨\n\nYou will receive order pings with loud sound alerts right here.",
                parse_mode="Markdown"
            )
            await send_telegram_audio(chat_id=chat_id, caption=RINGTONE_INSTRUCTIONS)
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
                await send_telegram_audio(chat_id=chat_id, caption=RINGTONE_INSTRUCTIONS)
                return
            else:
                restaurant.telegram_chat_id = chat_id
                await db.commit()
                await send_telegram_message(
                    chat_id=chat_id,
                    text=f"✅ *Kitchen Chat Linked!*\n\nIncoming orders for *{restaurant.name}* will now be dispatched to this chat. 🍲",
                    parse_mode="Markdown"
                )
                await send_telegram_audio(chat_id=chat_id, caption=RINGTONE_INSTRUCTIONS)
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
            rest_stmt = select(models.Restaurants).where(
                (models.Restaurants.telegram_chat_id == chat_id) |
                (models.Restaurants.telegram_chat_id == str(chat_id).strip())
            )

        rest_res = await db.execute(rest_stmt)
        restaurants = rest_res.scalars().all()
        if restaurants:
            for r in restaurants:
                r.telegram_chat_id = None
            await db.commit()
            await send_telegram_message(
                chat_id=chat_id,
                text="✅ *Unlinked Successfully!*\n\nThis chat will no longer receive restaurant orders for Madam G Restaurant.\n\n👉 *To set this account as a Rider:* Type `/start` and tap *Share Phone Number*.",
                parse_mode="Markdown"
            )
            return
        else:
            await send_telegram_message(
                chat_id=chat_id,
                text="ℹ️ No linked restaurant was found to unlink. To connect as a rider, send `/start`.",
                parse_mode="Markdown"
            )
            return

    # --- C2. RIDER UNLINK COMMAND (/unlink_rider [phone]) ---
    if text.startswith("/unlink_rider"):
        parts = text.split()
        phone_arg = parts[1].strip() if len(parts) >= 2 else None
        if phone_arg:
            phone_variants = replyhandler.get_phone_variants(phone_arg)
            rider_stmt = select(models.Riders).where(
                (models.Riders.rider_wa_number.in_(phone_variants)) |
                (models.Riders.rider_phonenumber_2.in_(phone_variants))
            )
        else:
            rider_stmt = select(models.Riders).where(models.Riders.telegram_chat_id == chat_id)

        r_res = await db.execute(rider_stmt)
        riders_to_unlink = r_res.scalars().all()
        if riders_to_unlink:
            for r in riders_to_unlink:
                r.telegram_chat_id = None
            await db.commit()
            await send_telegram_message(
                chat_id=chat_id,
                text="✅ *Rider Profile Unlinked!*\n\nThis Telegram chat will no longer receive rider delivery orders.\n\n👉 Send `/start` at any time to link again or link a new phone number.",
                parse_mode="Markdown"
            )
            return
        else:
            await send_telegram_message(
                chat_id=chat_id,
                text="ℹ️ This chat is not currently linked to any rider account. Send `/start` to link as a rider.",
                parse_mode="Markdown"
            )
            return

    # --- C3. MASTER UNLINK COMMAND (/unlink) ---
    if text == "/unlink":
        # Unlink restaurants
        rest_stmt = select(models.Restaurants).where(
            (models.Restaurants.telegram_chat_id == chat_id) |
            (models.Restaurants.telegram_chat_id == str(chat_id).strip())
        )
        r_res = await db.execute(rest_stmt)
        restaurants = r_res.scalars().all()
        for r in restaurants:
            r.telegram_chat_id = None

        # Unlink riders
        rider_stmt = select(models.Riders).where(models.Riders.telegram_chat_id == chat_id)
        rd_res = await db.execute(rider_stmt)
        riders_to_unlink = rd_res.scalars().all()
        for rd in riders_to_unlink:
            rd.telegram_chat_id = None

        await db.commit()
        await send_telegram_message(
            chat_id=chat_id,
            text=(
                "✅ *Account Reset & Unlinked Successfully!*\n\n"
                "This Telegram chat is now cleared of all linked roles.\n\n"
                "• To connect as a **Rider:** Send `/start` and tap *Share Phone Number*.\n"
                "• To connect as a **Restaurant:** Open your onboarding link (e.g. `/start restaurant_madam_g`)."
            ),
            parse_mode="Markdown"
        )
        return

    # --- D. RESTAURANT SET BANK COMMAND (/set_bank <bank_name> <account_number> <account_name>) ---
    if text.startswith("/set_bank"):
        parts = text.split(maxsplit=3)
        if len(parts) >= 4:
            b_name = parts[1].strip()
            a_num = parts[2].strip()
            a_name = parts[3].strip()

            rest_res = await db.execute(
                select(models.Restaurants).where(
                    (models.Restaurants.telegram_chat_id == chat_id) |
                    (models.Restaurants.telegram_chat_id == str(chat_id).strip())
                )
            )
            restaurant = rest_res.scalars().first()
            if restaurant:
                restaurant.bank_name = b_name
                restaurant.account_number = a_num
                restaurant.account_name = a_name
                await db.commit()
                await send_telegram_message(
                    chat_id=chat_id,
                    text=(
                        f"✅ *Bank Details Updated for {restaurant.name}!* 🏦\n\n"
                        f"• *Bank:* {b_name}\n"
                        f"• *Account Number:* `{a_num}`\n"
                        f"• *Account Name:* {a_name}\n\n"
                        f"Customers ordering from {restaurant.name} will now see these payment details on WhatsApp."
                    ),
                    parse_mode="Markdown"
                )
            else:
                await send_telegram_message(
                    chat_id=chat_id,
                    text="⚠️ This chat is not currently linked to any restaurant. First send `/link_restaurant <slug>` to link.",
                    parse_mode="Markdown"
                )
            return
        else:
            await send_telegram_message(
                chat_id=chat_id,
                text="Usage: `/set_bank <Bank_Name> <Account_Number> <Account_Name>`\nExample: `/set_bank KUDA 3004582800 INTIME TECHNOLOGIES LIMITED`",
                parse_mode="Markdown"
            )
            return

    # --- E. STATUS / WHOAMI COMMAND (/status, /whoami) ---
    if text in ["/status", "/whoami", "/id"]:
        rider_res = await db.execute(
            select(models.Riders).where(models.Riders.telegram_chat_id == chat_id)
        )
        rider = rider_res.scalars().first()

        rest_res = await db.execute(
            select(models.Restaurants).where(models.Restaurants.telegram_chat_id == chat_id)
        )
        linked_restaurants = rest_res.scalars().all()

        msg = f"🔍 *Your Account Status:*\n\n• *Telegram Chat ID:* `{chat_id}`\n"
        if rider:
            msg += f"• *Rider Account:* ✅ Linked as *{rider.first_name} {rider.last_name}* (`{rider.rider_wa_number}`)\n"
        else:
            msg += "• *Rider Account:* ❌ Not linked as a rider (Send `/start` to link)\n"

        if linked_restaurants:
            r_details = []
            for r in linked_restaurants:
                b_info = f" (Bank: {r.bank_name or 'KUDA'}, Acct: {r.account_number or '3004582800'})"
                r_details.append(f"*{r.name}*{b_info}")
            msg += f"• *Restaurant:* ✅ Linked to {', '.join(r_details)}\n"
        else:
            msg += "• *Restaurant:* ❌ Not linked to any restaurant\n"

        msg += "\n💡 *Useful Commands:*\n"
        msg += "• `/ringtone` — Get your custom InTime order alarm audio\n"
        msg += "• `/order_code [order_no]` — View 5-digit verification code for an order\n"
        msg += "• `/unlock_code <order_no>` — Reset 3-attempt verification lockout\n"
        msg += "• `/unlink` — Clear this chat from all roles\n"
        if rider:
            msg += "• `/unlink_rider` — Disconnect your rider profile\n"
        if linked_restaurants:
            msg += "• `/unlink_restaurant` — Disconnect restaurant kitchen alerts\n"

        await send_telegram_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
        return

    # --- E. RIDER MANUAL REGISTRATION COMMAND (/register_rider <phone> [First] [Last]) ---
    if text.startswith("/register_rider"):
        parts = text.split(maxsplit=3)
        if len(parts) >= 2:
            phone_arg = parts[1].strip()
            clean_arg_phone = re.sub(r'[^\d]', '', phone_arg)
            if clean_arg_phone.startswith("0") and len(clean_arg_phone) == 11:
                formatted_arg_phone = "234" + clean_arg_phone[1:]
            elif len(clean_arg_phone) == 10:
                formatted_arg_phone = "234" + clean_arg_phone
            else:
                formatted_arg_phone = clean_arg_phone

            f_name = parts[2].strip() if len(parts) >= 3 else (from_user.get("first_name") or "InTime").strip()
            l_name = parts[3].strip() if len(parts) >= 4 else (from_user.get("last_name") or "Rider").strip()

            # Check if rider already exists
            r_res = await db.execute(
                select(models.Riders).where(
                    (models.Riders.rider_wa_number.in_(replyhandler.get_phone_variants(formatted_arg_phone))) |
                    (models.Riders.telegram_chat_id == chat_id)
                )
            )
            existing_rider = r_res.scalars().first()
            if existing_rider:
                existing_rider.telegram_chat_id = chat_id
                existing_rider.availability_status = "available"
                existing_rider.kyc_status = "verified"
                await db.commit()
                await send_telegram_message(
                    chat_id=chat_id,
                    text=f"✅ *Rider Profile Linked!*\n\nProfile for *{existing_rider.first_name} {existing_rider.last_name}* (`{formatted_arg_phone}`) is now linked to this chat! 🛵💨",
                    parse_mode="Markdown"
                )
                await send_telegram_audio(chat_id=chat_id, caption=RINGTONE_INSTRUCTIONS)
            else:
                new_r = models.Riders(
                    first_name=f_name,
                    last_name=l_name,
                    rider_wa_number=formatted_arg_phone,
                    rider_phonenumber_2=formatted_arg_phone,
                    availability_status="available",
                    kyc_status="verified",
                    telegram_chat_id=chat_id
                )
                db.add(new_r)
                await db.commit()
                await send_telegram_message(
                    chat_id=chat_id,
                    text=f"🎉 *Rider Onboarded Successfully!*\n\nWelcome *{f_name} {l_name}* (`{formatted_arg_phone}`)! You are now registered and will receive direct food delivery orders. 🛵💨",
                    parse_mode="Markdown"
                )
                await send_telegram_audio(chat_id=chat_id, caption=RINGTONE_INSTRUCTIONS)
            return
        else:
            await send_telegram_message(
                chat_id=chat_id,
                text="Usage: `/register_rider <phone_number> [First_Name] [Last_Name]`\nExample: `/register_rider 08123456789 John Doe`",
                parse_mode="Markdown"
            )
            return

    # --- F. RIDER PHONE NUMBER SHARING (Contact Card) ---
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
            rider.availability_status = "available"
            rider.kyc_status = "verified"
            await db.commit()
            await send_telegram_message(
                chat_id=chat_id,
                text=(
                    f"✅ *Profile Linked Successfully!*\n\n"
                    f"Welcome aboard, *{rider.first_name} {rider.last_name}*! 🛵💨\n\n"
                    f"You will now receive private 1-on-1 food delivery dispatch pings directly here."
                ),
                parse_mode="Markdown",
                reply_markup={"remove_keyboard": True}
            )
            await send_telegram_audio(chat_id=chat_id, caption=RINGTONE_INSTRUCTIONS)
        else:
            # Auto-register new rider from contact card!
            c_first = (contact.get("first_name") or from_user.get("first_name") or "InTime").strip()
            c_last = (contact.get("last_name") or from_user.get("last_name") or "Rider").strip()
            formatted_phone = clean_phone
            if clean_phone.startswith("0") and len(clean_phone) == 11:
                formatted_phone = "234" + clean_phone[1:]
            elif len(clean_phone) == 10:
                formatted_phone = "234" + clean_phone

            new_rider = models.Riders(
                first_name=c_first,
                last_name=c_last,
                rider_wa_number=formatted_phone,
                rider_phonenumber_2=formatted_phone,
                availability_status="available",
                kyc_status="verified",
                telegram_chat_id=chat_id
            )
            db.add(new_rider)
            await db.commit()
            await db.refresh(new_rider)

            await send_telegram_message(
                chat_id=chat_id,
                text=(
                    f"🎉 *Rider Onboarded Successfully!*\n\n"
                    f"Welcome aboard, *{new_rider.first_name} {new_rider.last_name}*! 🛵💨\n\n"
                    f"Your rider profile has been created and verified for phone `{formatted_phone}`.\n"
                    f"You will now receive private 1-on-1 food delivery dispatch pings directly here!"
                ),
                parse_mode="Markdown",
                reply_markup={"remove_keyboard": True}
            )
            await send_telegram_audio(chat_id=chat_id, caption=RINGTONE_INSTRUCTIONS)
        return

    # --- G. CUSTOM RINGTONE COMMAND (/ringtone, /sound, /alert) ---
    if text in ["/ringtone", "/sound", "/alert"]:
        await send_telegram_audio(chat_id=chat_id, caption=RINGTONE_INSTRUCTIONS)
        return

    # --- H. NORMAL RIDER /start COMMAND ---
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
            await send_telegram_audio(chat_id=chat_id, caption=RINGTONE_INSTRUCTIONS)
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

    # --- H2. SUPPORT TROUBLESHOOTING: ORDER CODE LOOKUP & UNLOCK (/order_code, /unlock_code) ---
    if text.startswith(("/order_code", "/lookup_code", "/find_code")):
        parts = text.split(maxsplit=1)
        order_arg = parts[1].strip().lstrip("#") if len(parts) >= 2 else ""

        if order_arg:
            ord_res = await db.execute(
                select(models.Orders).where(models.Orders.order_number.ilike(order_arg))
            )
            order = ord_res.scalars().first()
            if not order:
                await send_telegram_message(
                    chat_id=chat_id,
                    text=f"⚠️ No order found matching `{order_arg}`.",
                    parse_mode="Markdown"
                )
                return

            if not order.verification_code:
                order.verification_code = ''.join(random.choices(string.digits, k=5))
                await db.commit()
                await db.refresh(order)

            attempts = getattr(order, "verification_attempts", 0) or 0
            lock_note = " 🚫 *(LOCKED)*" if attempts >= 3 else ""
            prog = order.delivery_progression_status or "not_started"
            info_msg = (
                f"🔐 *Order Verification Details*\n\n"
                f"• *Order #:* `{order.order_number}`\n"
                f"• *Status:* `{order.status}` (`{prog}`)\n"
                f"• *5-Digit Code:* `{order.verification_code}`\n"
                f"• *Attempts:* `{attempts}/3`{lock_note}\n"
                f"• *Customer Phone:* `{order.sender_wa_number or 'N/A'}`\n"
                f"• *Recipient Phone:* `{order.recipient_phone_number or 'N/A'}`\n"
                f"• *Rider Phone:* `{order.rider_wa_number or 'Unassigned'}`\n"
            )
            if attempts >= 3:
                info_msg += f"\n👉 Run `/unlock_code {order.order_number}` to reset attempts."
            await send_telegram_message(chat_id=chat_id, text=info_msg, parse_mode="Markdown")
            return
        else:
            active_res = await db.execute(
                select(models.Orders)
                .where(models.Orders.status.in_(["confirmed", "rider_accepted", "in_transit", "awaiting_pickup", "awaiting_dropoff"]))
                .order_by(models.Orders.created_at.desc())
                .limit(5)
            )
            active_orders = active_res.scalars().all()
            if not active_orders:
                await send_telegram_message(
                    chat_id=chat_id,
                    text="ℹ️ No active orders found right now. Pass a specific order number: `/order_code <ORDER_NO>`",
                    parse_mode="Markdown"
                )
                return

            lines = ["🔐 *Recent Active Orders & Codes:*\n"]
            for o in active_orders:
                code_disp = f"`{o.verification_code}`" if o.verification_code else "_Not set yet_"
                attempts = getattr(o, "verification_attempts", 0) or 0
                lines.append(
                    f"• `{o.order_number}` | `{o.status}` | Code: {code_disp} | Attempts: `{attempts}/3`"
                )
            lines.append("\n💡 Inspect one: `/order_code <ORDER_NO>`\n🔓 Unlock locked order: `/unlock_code <ORDER_NO>`")
            await send_telegram_message(chat_id=chat_id, text="\n".join(lines), parse_mode="Markdown")
            return

    if text.startswith("/unlock_code"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            await send_telegram_message(
                chat_id=chat_id,
                text="Usage: `/unlock_code <ORDER_NUMBER>`",
                parse_mode="Markdown"
            )
            return

        order_arg = parts[1].strip().lstrip("#")
        ord_res = await db.execute(
            select(models.Orders).where(models.Orders.order_number.ilike(order_arg))
        )
        order = ord_res.scalars().first()
        if not order:
            await send_telegram_message(
                chat_id=chat_id,
                text=f"⚠️ No order found matching `{order_arg}`.",
                parse_mode="Markdown"
            )
            return

        if not order.verification_code:
            order.verification_code = ''.join(random.choices(string.digits, k=5))
        order.verification_attempts = 0
        await db.commit()
        await db.refresh(order)

        await send_telegram_message(
            chat_id=chat_id,
            text=(
                f"🔓 *Order Verification Unlocked!*\n\n"
                f"• *Order #:* `{order.order_number}`\n"
                f"• *Attempts Reset:* `0/3`\n"
                f"• *Active 5-Digit Code:* `{order.verification_code}`\n\n"
                f"The rider can now enter the verification code again."
            ),
            parse_mode="Markdown"
        )
        return

    # --- I. RIDER DELIVERY CONFIRMATION CODE COMMAND (/code <5-digit> or plain 5 digits) ---
    code_match = re.search(r'\b(\d{5})\b', text)
    if code_match and (text.startswith("/code") or len(text.strip()) == 5):
        submitted_code = code_match.group(1).strip()
        # Find active rider
        r_stmt = select(models.Riders).where(models.Riders.telegram_chat_id == chat_id)
        r_res = await db.execute(r_stmt)
        rider_record = r_res.scalars().first()
        if not rider_record:
            await send_telegram_message(chat_id=chat_id, text="⚠️ You are not registered as an active rider.")
            return

        # Find in-transit food order assigned to this rider
        rider_phones = replyhandler.get_phone_variants(rider_record.rider_wa_number)
        ord_stmt = select(models.Orders).where(
            (models.Orders.rider_wa_number.in_(rider_phones)) |
            (models.Orders.rider_wa_number == f"TG:@{from_user.get('username') or chat_id}") |
            (models.Orders.rider_wa_number == rider_record.rider_wa_number)
        ).where(
            models.Orders.status.in_(["rider_accepted", "in_transit", "awaiting_pickup"])
        ).order_by(models.Orders.created_at.desc())

        ord_res = await db.execute(ord_stmt)
        active_order = ord_res.scalars().first()
        if not active_order:
            await send_telegram_message(
                chat_id=chat_id,
                text="ℹ️ No active in-transit delivery found assigned to you to verify."
            )
            return

        expected_code = str(active_order.verification_code or "").strip()
        if not expected_code:
            await send_telegram_message(
                chat_id=chat_id,
                text="⚠️ This order does not have an active verification code set yet. Please make sure you tapped *Food Collected* first!"
            )
            return

        if (getattr(active_order, "verification_attempts", 0) or 0) >= 3:
            await send_telegram_message(
                chat_id=chat_id,
                text=(
                    f"🚫 *Maximum Verification Attempts Reached (3/3)!*\n\n"
                    f"Order *#{active_order.order_number}* code verification is locked for security.\n"
                    f"Please contact support or ask an admin to run `/unlock_code {active_order.order_number}`."
                ),
                parse_mode="Markdown"
            )
            return

        if submitted_code == expected_code:
            active_order.delivery_progression_status = "package_delivered"
            active_order.status = "completed"
            await db.commit()

            # 1. Notify rider on Telegram
            rider_success_msg = (
                f"🎉 *DELIVERY COMPLETED SUCCESSFULLY!* 🛵💨\n\n"
                f"*Order #:* `{active_order.order_number}`\n"
                f"Code `{submitted_code}` verified successfully! The customer has been notified and prompted for rating.\n\n"
                f"Thank you for your fantastic hustle! 💪✨"
            )
            await send_telegram_message(chat_id=chat_id, text=rider_success_msg, parse_mode="Markdown")

            # 2. Send Customer WhatsApp Prompt #5 (Delivered & Rating)
            cust_complete_msg = (
                f"🎉🥳 *Order Delivered!* 🍲✨\n\n"
                f"Your meal from *{active_order.pickup_location_name or 'Madam G'}* (Order *#{active_order.order_number}*) has been safely delivered! Enjoy your meal! 😋\n\n"
                f"⭐ *Rate Your Rider*\n"
                f"How was your delivery service today? Please reply with a rating from *1* to *5* ⭐ to rate your rider."
            )
            await replyhandler.send_custom_message(active_order.sender_wa_number, cust_complete_msg, AUTH, GRAPH_URL)

            # If recipient phone is distinct from sender, notify recipient too
            if active_order.recipient_phone_number:
                norm_recip = replyhandler.normalize_phone_number(active_order.recipient_phone_number) or active_order.recipient_phone_number
                sender_norm = replyhandler.normalize_phone_number(active_order.sender_wa_number)
                if norm_recip and norm_recip != sender_norm:
                    await replyhandler.send_details_to_recipients(
                        sender_wa_number=norm_recip,
                        message=cust_complete_msg,
                        auth=AUTH,
                        graph_url=GRAPH_URL
                    )

            # 3. Alert Restaurant on Telegram that delivery is finished
            try:
                clean_rname = (active_order.pickup_location_name or "").replace(", Lagos", "").strip()
                r_stmt = select(models.Restaurants).where(models.Restaurants.name.ilike(f"%{clean_rname}%"))
                r_res = await db.execute(r_stmt)
                r_obj = r_res.scalars().first()
                r_chat = r_obj.telegram_chat_id if r_obj else os.getenv("TELEGRAM_RESTAURANT_CHAT_ID")
                if r_chat:
                    await send_telegram_message(
                        chat_id=r_chat,
                        text=f"✅ *DELIVERY COMPLETED!* 🍲🎉\n\nOrder *#{active_order.order_number}* has been verified and successfully delivered to the customer.",
                        parse_mode="Markdown"
                    )
            except Exception as r_done_err:
                logger.warning(f"Failed to alert kitchen on delivery complete: {r_done_err}")

            return
        else:
            attempts = (getattr(active_order, "verification_attempts", 0) or 0) + 1
            active_order.verification_attempts = attempts
            await db.commit()
            remaining = max(0, 3 - attempts)
            if remaining > 0:
                await send_telegram_message(
                    chat_id=chat_id,
                    text=(
                        f"❌ *Incorrect Verification Code!* (Attempt {attempts}/3)\n\n"
                        f"Code `{submitted_code}` did not match.\n"
                        f"👉 You have *{remaining}* attempt{'s' if remaining > 1 else ''} remaining.\n"
                        f"Please ask the customer to check the 5-digit code sent to their WhatsApp and reply `/code <5-digit>`."
                    ),
                    parse_mode="Markdown"
                )
            else:
                await send_telegram_message(
                    chat_id=chat_id,
                    text=(
                        f"🚫 *Maximum Verification Attempts Reached (3/3)!*\n\n"
                        f"Order *#{active_order.order_number}* code verification is locked. Please contact support or have customer confirm reception."
                    ),
                    parse_mode="Markdown"
                )
            return


async def handle_telegram_callback(callback_query: Dict[str, Any], db: AsyncSession):
    AUTH = get_auth_token()
    GRAPH_URL = get_graph_url()
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

        # 1. Atomically lock and assign order in DB (prevents two riders claiming simultaneously)
        claim_res = await db.execute(
            update(models.Orders)
            .where(models.Orders.order_number == order_num)
            .where(models.Orders.status == "confirmed")
            .values(
                status="rider_accepted",
                rider_wa_number=rider_phone,
                delivery_progression_status="awaiting_pickup"
            )
        )
        await db.commit()
        if claim_res.rowcount == 0:
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

        is_paid = (getattr(order, "payment_status", "pending_payment") == "paid")
        if is_paid:
            payment_status_line = (
                "🟢 *Payment Status:* PAID & CONFIRMED\n\n"
                "👉 *Next Action:* Proceed to the restaurant now to collect the food package!"
            )
            rider_action_keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "📍 I Have Arrived at Kitchen",
                            "callback_data": f"rider_at_kitchen:{order.order_number}"
                        }
                    ]
                ]
            }
        else:
            payment_status_line = (
                "⏳ *Payment Status:* Awaiting customer bank transfer\n\n"
                "👉 *Next Action:* Please stand by! You will receive an instant green light notification here as soon as the transfer is verified to collect the food package."
            )
            rider_action_keyboard = None

        recipient_phone = getattr(order, "recipient_phone_number", None) or getattr(order, "sender_wa_number", None) or "Not provided"
        winning_text = (
            f"✅ *YOU ACCEPTED THIS ORDER!* 🛵💨\n\n"
            f"*Order #:* `{order.order_number}`\n"
            f"📍 *Pickup Restaurant:* {order.pickup_location_name}\n"
            f"🏁 *Dropoff Destination:* {order.dropoff_location_name}\n"
            f"📞 *Recipient Phone:* `{recipient_phone}`\n\n"
            f"📋 *Meal Checklist:*\n{clean_desc}\n\n"
            f"💳 *Total Order Amount:* *{fare_formatted}*\n\n"
            f"{payment_status_line}"
        )
        if chat_id and message_id:
            await edit_telegram_message(
                chat_id=chat_id,
                message_id=message_id,
                text=winning_text,
                parse_mode="Markdown",
                reply_markup=rider_action_keyboard
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

        # 5. Ping Restaurant on Telegram
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

    # --- II. RIDER AT KITCHEN CALLBACK ---
    elif data.startswith("rider_at_kitchen:"):
        order_num = data.split(":", 1)[1].strip()
        ord_res = await db.execute(
            select(models.Orders).where(models.Orders.order_number == order_num)
        )
        order = ord_res.scalars().first()
        if not order:
            await answer_callback_query(cq_id, text="⚠️ Order not found.", show_alert=True)
            return

        order.delivery_progression_status = "rider_at_kitchen"
        await db.commit()

        await answer_callback_query(cq_id, text="📍 Arrived at restaurant! Tap below once meal is collected.")

        recipient_phone = getattr(order, "recipient_phone_number", None) or getattr(order, "sender_wa_number", None) or "Not provided"
        kitchen_msg = (
            f"📍 *ARRIVED AT KITCHEN* 🍲\n\n"
            f"*Order #:* `{order.order_number}`\n"
            f"📍 *Restaurant:* {order.pickup_location_name}\n"
            f"🏁 *Dropoff Destination:* {order.dropoff_location_name}\n"
            f"📞 *Recipient Phone:* `{recipient_phone}`\n\n"
            f"👉 *Next Action:* Once the kitchen gives you the packed meal, tap *Food Collected & On The Way* below!"
        )
        next_keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "📦 Food Collected & On The Way",
                        "callback_data": f"rider_picked_up:{order.order_number}"
                    }
                ]
            ]
        }
        if chat_id and message_id:
            await edit_telegram_message(
                chat_id=chat_id,
                message_id=message_id,
                text=kitchen_msg,
                parse_mode="Markdown",
                reply_markup=next_keyboard
            )

        # Alert restaurant on Telegram
        try:
            rest_name_clean = (order.pickup_location_name or "").replace(", Lagos", "").strip()
            rest_db_res = await db.execute(
                select(models.Restaurants).where(models.Restaurants.name.ilike(f"%{rest_name_clean}%"))
            )
            rest_obj = rest_db_res.scalars().first()
            rest_chat_id = rest_obj.telegram_chat_id if rest_obj else os.getenv("TELEGRAM_RESTAURANT_CHAT_ID")
            if rest_chat_id:
                await send_telegram_message(
                    chat_id=rest_chat_id,
                    text=f"🛵 *RIDER AT KITCHEN!* 🍲\n\nDispatch rider {user_display} has arrived at the kitchen to pick up *Order #{order.order_number}*.",
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.warning(f"Failed to alert kitchen of rider arrival: {e}")

    # --- III. RIDER PICKED UP & EN ROUTE CALLBACK ---
    elif data.startswith("rider_picked_up:"):
        order_num = data.split(":", 1)[1].strip()
        ord_res = await db.execute(
            select(models.Orders).where(models.Orders.order_number == order_num)
        )
        order = ord_res.scalars().first()
        if not order:
            await answer_callback_query(cq_id, text="⚠️ Order not found.", show_alert=True)
            return

        # Generate 5-digit verification code if not set
        code_to_set = order.verification_code or ''.join(random.choices(string.digits, k=5))
        order.verification_code = code_to_set
        order.delivery_progression_status = "package_picked_up"
        order.status = "in_transit"
        await db.commit()

        await answer_callback_query(cq_id, text="📦 Food collected! Safe delivery.")

        recipient_phone = getattr(order, "recipient_phone_number", None) or getattr(order, "sender_wa_number", None) or "Not provided"
        depart_msg = (
            f"📦 *FOOD COLLECTED & ON THE WAY!* 🛵💨\n\n"
            f"*Order #:* `{order.order_number}`\n"
            f"🏁 *Dropoff Destination:* {order.dropoff_location_name}\n"
            f"📞 *Recipient Phone:* `{recipient_phone}`\n\n"
            f"👉 *Next Action:*\n"
            f"• Head to the customer's delivery location.\n"
            f"• When you arrive at the address, tap *Arrived at Dropoff* below!"
        )
        dropoff_keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "📍 Arrived at Dropoff",
                        "callback_data": f"rider_at_dropoff:{order.order_number}"
                    }
                ]
            ]
        }
        if chat_id and message_id:
            await edit_telegram_message(
                chat_id=chat_id,
                message_id=message_id,
                text=depart_msg,
                parse_mode="Markdown",
                reply_markup=dropoff_keyboard
            )

        # WhatsApp Prompt #3 to Customer (Food en route + 5-digit verification code)
        try:
            rest_clean = (order.pickup_location_name or "Madam G").replace(", Lagos", "").strip()
            prompt3_msg = (
                f"🛵💨 *Your Meal is On The Way!* 🍲✨\n\n"
                f"Your dispatch rider has picked up your food order from *{rest_clean}* (Order *#{order.order_number}*) and is en route to your delivery address!\n\n"
                f"🔐 *Your Delivery Verification Code:*\n"
                f"👉  *{code_to_set}*  👈\n\n"
                f"📋 *Instructions:*\n"
                f"• Share this *5-digit code* with the rider when they arrive to securely receive your food package. 🤝\n\n"
                f"Thank you for choosing *InTime*! 🌟"
            )
            await replyhandler.send_custom_message(order.sender_wa_number, prompt3_msg, AUTH, GRAPH_URL)

            if order.recipient_phone_number:
                norm_recip = replyhandler.normalize_phone_number(order.recipient_phone_number) or order.recipient_phone_number
                sender_norm = replyhandler.normalize_phone_number(order.sender_wa_number)
                if norm_recip and norm_recip != sender_norm:
                    await replyhandler.send_details_to_recipients(
                        sender_wa_number=norm_recip,
                        message=prompt3_msg,
                        auth=AUTH,
                        graph_url=GRAPH_URL
                    )
        except Exception as p3_err:
            logger.warning(f"Failed to send customer Prompt #3 on rider pickup: {p3_err}")

        # Notify Restaurant on Telegram
        try:
            rest_name_clean = (order.pickup_location_name or "").replace(", Lagos", "").strip()
            rest_db_res = await db.execute(
                select(models.Restaurants).where(models.Restaurants.name.ilike(f"%{rest_name_clean}%"))
            )
            rest_obj = rest_db_res.scalars().first()
            rest_chat_id = rest_obj.telegram_chat_id if rest_obj else os.getenv("TELEGRAM_RESTAURANT_CHAT_ID")
            if rest_chat_id:
                await send_telegram_message(
                    chat_id=rest_chat_id,
                    text=f"🛵💨 *ORDER DEPARTED!* 🍲\n\nRider has collected *Order #{order.order_number}* and is en route to the customer.",
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.warning(f"Failed to alert kitchen of order departure: {e}")

    # --- IV. RIDER ARRIVED AT DROPOFF CALLBACK ---
    elif data.startswith("rider_at_dropoff:"):
        order_num = data.split(":", 1)[1].strip()
        ord_res = await db.execute(
            select(models.Orders).where(models.Orders.order_number == order_num)
        )
        order = ord_res.scalars().first()
        if not order:
            await answer_callback_query(cq_id, text="⚠️ Order not found.", show_alert=True)
            return

        order.delivery_progression_status = "arrived_at_dropoff"
        await db.commit()

        await answer_callback_query(cq_id, text="📍 Arrived at dropoff! Ask customer for their 5-digit code.")

        recipient_phone = getattr(order, "recipient_phone_number", None) or getattr(order, "sender_wa_number", None) or "Not provided"
        arrived_msg = (
            f"📍 *ARRIVED AT DROPOFF LOCATION!* 🛵🏠\n\n"
            f"*Order #:* `{order.order_number}`\n"
            f"🏁 *Address:* {order.dropoff_location_name}\n"
            f"📞 *Recipient Phone:* `{recipient_phone}`\n\n"
            f"🔐 *Final Step to Complete Delivery:*\n"
            f"1️⃣ Meet customer / call `{recipient_phone}`\n"
            f"2️⃣ Ask them for the *5-digit verification code* sent to their WhatsApp\n"
            f"3️⃣ Reply here with: `/code <5-digit>` (e.g. `/code 12345` or simply the 5 digits)\n\n"
            f"⚠️ *Note:* You have 3 attempts to enter the correct code."
        )
        if chat_id and message_id:
            await edit_telegram_message(
                chat_id=chat_id,
                message_id=message_id,
                text=arrived_msg,
                parse_mode="Markdown",
                reply_markup=None
            )

        # WhatsApp Prompt #4 to Customer (Rider has arrived)
        try:
            rest_clean = (order.pickup_location_name or "Madam G").replace(", Lagos", "").strip()
            prompt4_msg = (
                f"📍 *Rider Has Arrived!* 🛵🍲\n\n"
                f"Your dispatch rider has arrived at your delivery address with your meal from *{rest_clean}* (Order *#{order.order_number}*)!\n\n"
                f"👉 Please meet the rider and provide your *5-digit verification code* (*{order.verification_code}*) to receive your delicious meal. 😋✨"
            )
            await replyhandler.send_custom_message(order.sender_wa_number, prompt4_msg, AUTH, GRAPH_URL)

            if order.recipient_phone_number:
                norm_recip = replyhandler.normalize_phone_number(order.recipient_phone_number) or order.recipient_phone_number
                sender_norm = replyhandler.normalize_phone_number(order.sender_wa_number)
                if norm_recip and norm_recip != sender_norm:
                    await replyhandler.send_details_to_recipients(
                        sender_wa_number=norm_recip,
                        message=prompt4_msg,
                        auth=AUTH,
                        graph_url=GRAPH_URL
                    )
        except Exception as p4_err:
            logger.warning(f"Failed to send customer Prompt #4 on rider dropoff: {p4_err}")

    # --- V. RESTAURANT KITCHEN STATUS BUTTONS ---
    elif data.startswith("rest_accept:"):
        order_num = data.split(":", 1)[1].strip()
        ord_res = await db.execute(
            select(models.Orders).where(models.Orders.order_number == order_num)
        )
        order = ord_res.scalars().first()
        if not order:
            await answer_callback_query(cq_id, text="⚠️ Order not found.", show_alert=True)
            return

        order.kitchen_status = "preparing"
        await db.commit()

        await answer_callback_query(cq_id, text="🍳 Order accepted! Kitchen preparing.")

        packed_keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "📦 Meal Packed & Ready",
                        "callback_data": f"rest_packed:{order.order_number}"
                    }
                ]
            ]
        }
        orig_text = msg.get("text", "")
        updated_text = (
            f"{orig_text}\n\n"
            f"🍳 *Kitchen Status:* PREPARING MEAL...\n"
            f"Tap below once meal is packed and ready for pickup!"
        ) if "Kitchen Status:" not in orig_text else orig_text
        if chat_id and message_id:
            await edit_telegram_message(
                chat_id=chat_id,
                message_id=message_id,
                text=updated_text,
                parse_mode="Markdown",
                reply_markup=packed_keyboard
            )

    elif data.startswith("rest_packed:"):
        order_num = data.split(":", 1)[1].strip()
        ord_res = await db.execute(
            select(models.Orders).where(models.Orders.order_number == order_num)
        )
        order = ord_res.scalars().first()
        if not order:
            await answer_callback_query(cq_id, text="⚠️ Order not found.", show_alert=True)
            return

        order.kitchen_status = "ready_for_pickup"
        await db.commit()

        await answer_callback_query(cq_id, text="📦 Marked as packed & ready!")

        handed_keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "🤝 Handed to Rider",
                        "callback_data": f"rest_handed:{order.order_number}"
                    }
                ]
            ]
        }
        orig_text = msg.get("text", "")
        updated_text = re.sub(
            r'🍳 \*Kitchen Status:\*.*',
            '📦 *Kitchen Status:* PACKED & READY FOR PICKUP!',
            orig_text,
            flags=re.DOTALL
        )
        if "Kitchen Status:" not in updated_text:
            updated_text = f"{orig_text}\n\n📦 *Kitchen Status:* PACKED & READY FOR PICKUP!"

        if chat_id and message_id:
            await edit_telegram_message(
                chat_id=chat_id,
                message_id=message_id,
                text=updated_text,
                parse_mode="Markdown",
                reply_markup=handed_keyboard
            )

        # Alert assigned rider on Telegram that food is packed
        try:
            if order.rider_wa_number:
                r_stmt = select(models.Riders).where(
                    (models.Riders.rider_wa_number == order.rider_wa_number) |
                    (models.Riders.rider_wa_number.in_(replyhandler.get_phone_variants(order.rider_wa_number)))
                )
                r_res = await db.execute(r_stmt)
                rider_obj = r_res.scalars().first()
                if rider_obj and rider_obj.telegram_chat_id:
                    await send_telegram_message(
                        chat_id=rider_obj.telegram_chat_id,
                        text=f"🍳 *Kitchen Update:* Order *#{order.order_number}* is packed and ready for pickup at the counter!",
                        parse_mode="Markdown"
                    )
        except Exception as e:
            logger.warning(f"Failed to alert rider of packed food: {e}")

    elif data.startswith("rest_handed:"):
        order_num = data.split(":", 1)[1].strip()
        ord_res = await db.execute(
            select(models.Orders).where(models.Orders.order_number == order_num)
        )
        order = ord_res.scalars().first()
        if not order:
            await answer_callback_query(cq_id, text="⚠️ Order not found.", show_alert=True)
            return

        order.kitchen_status = "handed_to_rider"
        await db.commit()

        await answer_callback_query(cq_id, text="🤝 Handed to rider!")

        orig_text = msg.get("text", "")
        updated_text = re.sub(
            r'📦 \*Kitchen Status:\*.*',
            '🤝 *Kitchen Status:* HANDED TO RIDER ✅',
            orig_text,
            flags=re.DOTALL
        )
        if "Kitchen Status:" not in updated_text:
            updated_text = f"{orig_text}\n\n🤝 *Kitchen Status:* HANDED TO RIDER ✅"

        if chat_id and message_id:
            await edit_telegram_message(
                chat_id=chat_id,
                message_id=message_id,
                text=updated_text,
                parse_mode="Markdown",
                reply_markup=None
            )

    # --- VI. KITCHEN RECEIPT CONFIRMATION / DISPUTE BUTTONS ---
    elif data.startswith("receipt_confirm:"):
        order_num = data.split(":", 1)[1].strip()
        await answer_callback_query(cq_id, text="✅ Receipt confirmed credited! Thank you.")
        caption = msg.get("caption", "")
        updated_caption = f"{caption}\n\n✅ *RECEIPT CONFIRMED CREDITED BY KITCHEN* (Verified by {user_display})"
        if chat_id and message_id:
            await edit_telegram_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=updated_caption,
                parse_mode="Markdown",
                reply_markup=None
            )

    elif data.startswith("receipt_reject:"):
        order_num = data.split(":", 1)[1].strip()
        await answer_callback_query(
            cq_id,
            text="⚠️ Receipt flagged as NOT credited. Support has been alerted for manual review.",
            show_alert=True
        )
        caption = msg.get("caption", "")
        updated_caption = f"{caption}\n\n❌ *DISPUTE: KITCHEN FLAGGED AS NOT CREDITED* (Reported by {user_display})"
        if chat_id and message_id:
            await edit_telegram_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=updated_caption,
                parse_mode="Markdown",
                reply_markup=None
            )
        admin_chat = os.getenv("TELEGRAM_ADMIN_CHAT_ID") or os.getenv("TELEGRAM_FALLBACK_CHAT_ID")
        if admin_chat:
            await send_telegram_message(
                chat_id=admin_chat,
                text=(
                    f"🚨 *RECEIPT DISPUTE ALERT!* 🚨\n\n"
                    f"Restaurant kitchen flagged that transfer for *Order #{order_num}* was *NOT CREDITED* to the bank account!\n"
                    f"Please investigate immediately."
                ),
                parse_mode="Markdown"
            )

