import os
import re
import io
import csv
import logging
import json
from datetime import datetime, date, time, timedelta, UTC
from typing import Optional, List, Dict, Any
import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import models

logger = logging.getLogger("telegram_service")

TELEGRAM_API_BASE = "https://api.telegram.org/bot"

def get_bot_token() -> str:
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

def get_fallback_restaurant_chat_id() -> str:
    return os.getenv("TELEGRAM_RESTAURANT_CHAT_ID", "").strip()


async def send_telegram_message(
    chat_id: str | int,
    text: str,
    parse_mode: str = "Markdown",
    reply_markup: Optional[Dict[str, Any]] = None,
    disable_notification: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Sends a message to a Telegram chat, group, or channel.
    """
    token = get_bot_token()
    if not token or not chat_id:
        logger.warning(f"Telegram send skipped: token missing or chat_id={chat_id}")
        return None

    url = f"{TELEGRAM_API_BASE}{token}/sendMessage"
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_notification": disable_notification
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
            if not data.get("ok") and parse_mode:
                logger.warning(f"Telegram sendMessage Markdown retry as plain text for {chat_id}: {data}")
                payload.pop("parse_mode", None)
                resp = await client.post(url, json=payload)
                data = resp.json()
            if not data.get("ok"):
                logger.error(f"Telegram sendMessage failed to {chat_id}: {data}")
            return data
    except Exception as e:
        logger.error(f"Error sending Telegram message to {chat_id}: {e}", exc_info=True)
        return None


async def edit_telegram_message(
    chat_id: str | int,
    message_id: int,
    text: str,
    parse_mode: str = "Markdown",
    reply_markup: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Edits an existing Telegram message in place.
    """
    token = get_bot_token()
    if not token:
        return None

    url = f"{TELEGRAM_API_BASE}{token}/editMessageText"
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            return resp.json()
    except Exception as e:
        logger.error(f"Error editing Telegram message {message_id} in {chat_id}: {e}")
        return None


async def edit_telegram_caption(
    chat_id: str | int,
    message_id: int,
    caption: str,
    parse_mode: str = "Markdown",
    reply_markup: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Edits the caption of an existing Telegram photo/media message in place.
    """
    token = get_bot_token()
    if not token:
        return None

    url = f"{TELEGRAM_API_BASE}{token}/editMessageCaption"
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "caption": caption,
        "parse_mode": parse_mode
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            return resp.json()
    except Exception as e:
        logger.error(f"Error editing Telegram caption {message_id} in {chat_id}: {e}")
        return None


async def answer_callback_query(
    callback_query_id: str,
    text: Optional[str] = None,
    show_alert: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Acknowledges a button tap callback query in Telegram.
    """
    token = get_bot_token()
    if not token:
        return None

    url = f"{TELEGRAM_API_BASE}{token}/answerCallbackQuery"
    payload: Dict[str, Any] = {
        "callback_query_id": callback_query_id,
        "show_alert": show_alert
    }
    if text:
        payload["text"] = text

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            return resp.json()
    except Exception as e:
        logger.error(f"Error answering callback query {callback_query_id}: {e}")
        return None


async def send_telegram_photo(
    chat_id: str | int,
    photo_bytes: bytes,
    caption: Optional[str] = None,
    parse_mode: str = "Markdown",
    reply_markup: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Sends a photo to a Telegram chat using multipart/form-data.
    """
    token = get_bot_token()
    if not token or not chat_id or not photo_bytes:
        return None

    url = f"{TELEGRAM_API_BASE}{token}/sendPhoto"
    files = {
        "photo": ("receipt.jpg", photo_bytes, "image/jpeg")
    }
    data: Dict[str, Any] = {
        "chat_id": str(chat_id),
    }
    if caption:
        data["caption"] = caption
        data["parse_mode"] = parse_mode
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, data=data, files=files)
            result = resp.json()
            if not result.get("ok"):
                logger.error(f"Telegram sendPhoto failed to {chat_id}: {result}")
            return result
    except Exception as e:
        logger.error(f"Error sending photo to Telegram {chat_id}: {e}")
        return None


async def send_telegram_document(
    chat_id: str | int,
    document_bytes: bytes,
    filename: str,
    caption: Optional[str] = None,
    parse_mode: str = "Markdown",
    mime_type: str = "text/csv"
) -> Optional[Dict[str, Any]]:
    """
    Sends a document/file (e.g. weekly CSV sales report) to a Telegram chat.
    """
    token = get_bot_token()
    if not token or not chat_id or not document_bytes:
        logger.warning(f"Telegram sendDocument skipped: token missing, chat_id={chat_id}, or empty file")
        return None

    url = f"{TELEGRAM_API_BASE}{token}/sendDocument"
    data: Dict[str, Any] = {
        "chat_id": str(chat_id),
    }
    if caption:
        data["caption"] = caption[:1024]
        if parse_mode:
            data["parse_mode"] = parse_mode

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {
                "document": (filename, document_bytes, mime_type)
            }
            resp = await client.post(url, data=data, files=files)
            result = resp.json()
            if not result.get("ok") and parse_mode and caption:
                logger.warning(f"Telegram sendDocument Markdown retry as plain text for {chat_id}: {result}")
                data.pop("parse_mode", None)
                files_retry = {
                    "document": (filename, document_bytes, mime_type)
                }
                resp = await client.post(url, data=data, files=files_retry)
                result = resp.json()
            if not result.get("ok"):
                logger.error(f"Telegram sendDocument failed to {chat_id}: {result}")
            return result
    except Exception as e:
        logger.error(f"Error sending document to Telegram {chat_id}: {e}")
        return None


RINGTONE_INSTRUCTIONS = (
    "🔔 *Custom InTime Order Alert Ringtone* 🎵\n\n"
    "Set this unique sound as your Telegram notification tone so you never miss an InTime order!\n\n"
    "📱 *How to set this as your ringtone:*\n"
    "1️⃣ Tap the *three dots (⋮)* on the audio message above.\n"
    "2️⃣ Select *\"Save for notifications\"* (or *Save sound*).\n"
    "3️⃣ Tap **InTime Dispatch** at the very top of this chat.\n"
    "4️⃣ Tap **Notifications** ➔ **Sound** (or *Customize*).\n"
    "5️⃣ Select **\"InTime Order Alert\"** from the sound list! 🎉"
)


async def send_telegram_audio(
    chat_id: str | int,
    audio_path_or_url: Optional[str] = None,
    caption: Optional[str] = None,
    title: str = "InTime Order Alert",
    performer: str = "InTime",
    parse_mode: str = "Markdown"
) -> Optional[Dict[str, Any]]:
    """
    Sends an MP3 audio file or link to a Telegram chat, which riders and restaurants
    can save as their custom order notification sound in Telegram.
    """
    token = get_bot_token()
    if not token or not chat_id:
        logger.warning(f"Telegram sendAudio skipped: token missing or chat_id={chat_id}")
        return None

    if not audio_path_or_url:
        audio_path_or_url = os.path.join(os.path.dirname(__file__), "..", "static", "intime_order_alert.mp3")

    url = f"{TELEGRAM_API_BASE}{token}/sendAudio"

    # 1. If it's a local file that exists on disk, upload it via multipart/form-data
    if os.path.exists(audio_path_or_url):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                with open(audio_path_or_url, "rb") as f:
                    file_bytes = f.read()
                files = {
                    "audio": ("intime_order_alert.mp3", file_bytes, "audio/mpeg")
                }
                data = {
                    "chat_id": str(chat_id),
                    "title": title,
                    "performer": performer,
                }
                if caption:
                    data["caption"] = caption
                    data["parse_mode"] = parse_mode
                resp = await client.post(url, data=data, files=files)
                result = resp.json()
                if not result.get("ok"):
                    logger.error(f"Telegram sendAudio (file) failed to {chat_id}: {result}")
                return result
        except Exception as e:
            logger.error(f"Error uploading Telegram audio file to {chat_id}: {e}", exc_info=True)
            return None

    # 2. Remote URL fallback
    remote_url = audio_path_or_url
    if not remote_url.startswith("http"):
        remote_url = "https://fastapiforwhatsappwebhook-production.up.railway.app/static/intime_order_alert.mp3"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {
                "chat_id": str(chat_id),
                "audio": remote_url,
                "title": title,
                "performer": performer,
            }
            if caption:
                payload["caption"] = caption
                payload["parse_mode"] = parse_mode
            resp = await client.post(url, json=payload)
            result = resp.json()
            if not result.get("ok"):
                logger.error(f"Telegram sendAudio (URL) failed to {chat_id}: {result}")
            return result
    except Exception as e:
        logger.error(f"Error sending Telegram audio URL to {chat_id}: {e}", exc_info=True)
        return None


async def notify_restaurant_food_order(
    order: models.Orders,
    restaurant_name: str,
    items_summary: str,
    subtotal: int,
    delivery_fee: int,
    grand_total: int,
    customer_phone: str,
    dropoff_address: str,
    db: AsyncSession
) -> bool:
    """
    Sends an instant, high-priority order ping to the restaurant's Telegram chat.
    Queries models.Restaurants dynamically first, with fallback to TELEGRAM_RESTAURANT_CHAT_ID.
    """
    chat_id = None

    # 1. Look up restaurant in database
    try:
        clean_name = (restaurant_name or "").strip()
        slug_guess = clean_name.lower().replace(" ", "_").replace("'", "")
        rest_stmt = select(models.Restaurants).where(
            (models.Restaurants.name.ilike(f"%{clean_name}%")) |
            (models.Restaurants.slug == slug_guess)
        )
        res = await db.execute(rest_stmt)
        restaurant_obj = res.scalars().first()
        if restaurant_obj and restaurant_obj.telegram_chat_id:
            chat_id = restaurant_obj.telegram_chat_id
    except Exception as e:
        logger.warning(f"Error querying restaurant {restaurant_name} from DB: {e}")

    # 2. Fallback to env var if not set in DB
    if not chat_id:
        chat_id = get_fallback_restaurant_chat_id()

    if not chat_id:
        logger.warning(f"No Telegram chat ID found for restaurant '{restaurant_name}'. Notification skipped.")
        return False

    # Format message
    clean_items = items_summary or order.package_description or "Food Items"
    msg = (
        f"🔔 *NEW FOOD ORDER RECEIVED!* 🍲✨\n\n"
        f"*Order #:* `{order.order_number}`\n"
        f"*Restaurant:* {restaurant_name}\n"
        f"*Customer Phone:* `{customer_phone}`\n"
        f"*Delivery Address:* {dropoff_address}\n\n"
        f"📋 *ORDER BREAKDOWN:*\n"
        f"{clean_items}\n\n"
        f"💵 *Food Subtotal:* ₦{subtotal:,}\n"
        f"🛵 *Delivery Fee:* ₦{delivery_fee:,}\n"
        f"💳 *Grand Total:* *₦{grand_total:,}*\n\n"
        f"Status: *Awaiting Kitchen Acceptance 🍳*"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "🍳 Accept & Start Cooking",
                    "callback_data": f"rest_accept:{order.order_number}"
                }
            ]
        ]
    }

    resp = await send_telegram_message(
        chat_id=chat_id,
        text=msg,
        parse_mode="Markdown",
        reply_markup=keyboard,
        disable_notification=False
    )
    return bool(resp and resp.get("ok"))


async def forward_receipt_to_restaurant(
    order: models.Orders,
    photo_bytes: bytes,
    amount: int,
    reference: Optional[str],
    customer_phone: str,
    db: AsyncSession
) -> bool:
    """
    Sends the customer's transfer receipt image directly to the restaurant's Telegram chat
    with 1-tap confirmation / dispute buttons.
    """
    try:
        clean_name = (order.pickup_location_name or "").replace(", Lagos", "").strip()
        slug_guess = clean_name.lower().replace(" ", "_").replace("'", "")
        rest_stmt = select(models.Restaurants).where(
            (models.Restaurants.name.ilike(f"%{clean_name}%")) |
            (models.Restaurants.slug == slug_guess)
        )
        res = await db.execute(rest_stmt)
        restaurant_obj = res.scalars().first()
        rest_chat = restaurant_obj.telegram_chat_id if restaurant_obj else get_fallback_restaurant_chat_id()
        if not rest_chat:
            return False

        bank_label = (restaurant_obj.bank_name if (restaurant_obj and restaurant_obj.bank_name) else "KUDA")
        ref_str = f"• *Ref:* `{reference}`\n" if reference else ""
        caption = (
            f"📸 *TRANSFER RECEIPT UPLOADED!* 🏦\n\n"
            f"• *Order #:* `{order.order_number}`\n"
            f"• *Amount:* *₦{amount:,}*\n"
            f"• *Customer Phone:* `{customer_phone}`\n"
            f"{ref_str}\n"
            f"Check your {bank_label} app/SMS to confirm credit:"
        )
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ Confirm Credited",
                        "callback_data": f"receipt_confirm:{order.order_number}"
                    },
                    {
                        "text": "❌ Not Credited",
                        "callback_data": f"receipt_reject:{order.order_number}"
                    }
                ]
            ]
        }
        resp = await send_telegram_photo(
            chat_id=rest_chat,
            photo_bytes=photo_bytes,
            caption=caption,
            reply_markup=keyboard
        )
        return bool(resp and resp.get("ok"))
    except Exception as e:
        logger.warning(f"Failed to forward receipt photo to restaurant Telegram: {e}")
        return False


async def dispatch_food_order_to_riders(
    order: models.Orders,
    restaurant_name: str,
    pickup_address: str,
    dropoff_address: str,
    pack_count: int,
    delivery_fee: int,
    db: AsyncSession
) -> int:
    """
    Sends private 1-on-1 delivery dispatch messages directly to all available,
    verified riders on Telegram with an interactive [🛵 Accept Delivery] button.
    Returns the number of riders pinged.
    """
    # Find all available riders who have linked their Telegram chat ID
    riders_res = await db.execute(
        select(models.Riders)
        .where(models.Riders.availability_status == "available")
        .where(models.Riders.kyc_status == "verified")
        .where(models.Riders.telegram_chat_id != None)
    )
    riders = list(riders_res.scalars().all())

    if not riders:
        logger.info(f"No active riders with linked Telegram found for order {order.order_number}.")
        return 0

    recipient_phone = getattr(order, "recipient_phone_number", None) or getattr(order, "sender_wa_number", None) or "Not provided"
    dispatch_text = (
        f"🛵 *NEW FOOD DELIVERY AVAILABLE!* 🍲💨\n\n"
        f"*Order #:* `{order.order_number}`\n"
        f"📍 *Pickup:* {restaurant_name} ({pickup_address})\n"
        f"🏁 *Dropoff:* {dropoff_address}\n"
        f"📞 *Recipient Phone:* `{recipient_phone}`\n"
        f"📦 *Size:* {pack_count} pack{'s' if pack_count > 1 else ''}\n\n"
        f"Tap below to claim this delivery:"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "🛵 Accept Delivery",
                    "callback_data": f"accept_food:{order.order_number}"
                }
            ]
        ]
    }

    sent_count = 0
    for rider in riders:
        chat_id = rider.telegram_chat_id
        if not chat_id:
            continue

        resp = await send_telegram_message(
            chat_id=chat_id,
            text=dispatch_text,
            parse_mode="Markdown",
            reply_markup=keyboard,
            disable_notification=False
        )

        if resp and resp.get("ok"):
            sent_count += 1
            msg_id = resp["result"]["message_id"]
            # Record offer in RiderOffer table for multi-rider editing on claim
            try:
                offer = models.RiderOffer(
                    order_number=order.order_number,
                    rider_wa_number=f"TG:{chat_id}:{msg_id}",
                    status="sent"
                )
                db.add(offer)
            except Exception as off_err:
                logger.warning(f"Failed to record RiderOffer for TG rider {chat_id}: {off_err}")

    if sent_count > 0:
        await db.commit()

    logger.info(f"Dispatched food order {order.order_number} to {sent_count} rider(s) on Telegram.")
    return sent_count


async def notify_payment_confirmed(
    order: models.Orders,
    paid_amount: int,
    db: AsyncSession
):
    """
    Alerts the restaurant and assigned rider on Telegram that the customer's
    transfer has been verified and food package is cleared for pickup.
    """
    # 1. Alert Restaurant
    try:
        clean_name = (order.pickup_location_name or "").replace(", Lagos", "").strip()
        slug_guess = clean_name.lower().replace(" ", "_").replace("'", "")
        rest_stmt = select(models.Restaurants).where(
            (models.Restaurants.name.ilike(f"%{clean_name}%")) |
            (models.Restaurants.slug == slug_guess)
        )
        res = await db.execute(rest_stmt)
        restaurant_obj = res.scalars().first()
        rest_chat = restaurant_obj.telegram_chat_id if restaurant_obj else get_fallback_restaurant_chat_id()
        if rest_chat:
            rest_msg = (
                f"🟢 *PAYMENT CONFIRMED FOR ORDER #{order.order_number}!* 🍲✨\n\n"
                f"Customer transfer of *₦{paid_amount:,}* has been verified!\n"
                f"Status: *Cleared for rider pickup!* 🍳📦"
            )
            await send_telegram_message(chat_id=rest_chat, text=rest_msg, parse_mode="Markdown")
    except Exception as e:
        logger.warning(f"Error alerting restaurant of payment confirmation: {e}")

    # 2. Alert Assigned Rider
    try:
        rider_wa = order.rider_wa_number
        if rider_wa:
            import replyhandler
            rider_stmt = select(models.Riders).where(
                (models.Riders.rider_wa_number == rider_wa) |
                (models.Riders.rider_wa_number.in_(replyhandler.get_phone_variants(rider_wa)))
            )
            r_res = await db.execute(rider_stmt)
            rider_obj = r_res.scalars().first()
            if rider_obj and rider_obj.telegram_chat_id:
                recipient_phone = getattr(order, "recipient_phone_number", None) or getattr(order, "sender_wa_number", None) or "Not provided"
                rider_msg = (
                    f"🟢 *GREEN LIGHT: PAYMENT CONFIRMED!* 🍲💨\n\n"
                    f"*Order #:* `{order.order_number}`\n"
                    f"Customer transfer of *₦{paid_amount:,}* has been verified!\n\n"
                    f"📍 *Pickup:* {order.pickup_location_name}\n"
                    f"🏁 *Dropoff:* {order.dropoff_location_name}\n"
                    f"📞 *Recipient Phone:* `{recipient_phone}`\n\n"
                    f"👉 *Next Action:* Proceed to the restaurant kitchen now to collect the food package and deliver to the customer!"
                )
                rider_keyboard = {
                    "inline_keyboard": [
                        [
                            {
                                "text": "📍 I Have Arrived at Kitchen",
                                "callback_data": f"rider_at_kitchen:{order.order_number}"
                            }
                        ]
                    ]
                }
                await send_telegram_message(
                    chat_id=rider_obj.telegram_chat_id,
                    text=rider_msg,
                    parse_mode="Markdown",
                    reply_markup=rider_keyboard
                )
    except Exception as e:
        logger.warning(f"Error alerting rider of payment confirmation: {e}")


# ---------------------------------------------------------------------------
# DAILY & WEEKLY RESTAURANT SALES REPORTS
# ---------------------------------------------------------------------------

LAGOS_UTC_OFFSET = timedelta(hours=1)


def _to_lagos_dt(dt: Optional[datetime]) -> datetime:
    if dt is None:
        return datetime.now(UTC) + LAGOS_UTC_OFFSET
    if dt.tzinfo is None:
        return dt + LAGOS_UTC_OFFSET
    return dt.astimezone(UTC) + LAGOS_UTC_OFFSET


def _calc_tiered_delivery_fee(pack_count: int) -> int:
    if pack_count <= 9:
        return 800
    if pack_count <= 15:
        return 1000
    if pack_count <= 24:
        return 1500
    return 2000


def extract_order_financials(order: models.Orders) -> Dict[str, Any]:
    """
    Extracts food_subtotal (total minus delivery fee), delivery_fee, gross_total,
    pack_count, and cleaned food item details for a food order.
    Uses stored food_subtotal/delivery_fee columns when populated, with smart parsing
    fallback for legacy orders.
    """
    raw_desc = str(order.package_description or "").strip()
    clean_items = re.sub(r'^Food Order from [^|]+\|\s*', '', raw_desc).strip()
    clean_items_plain = clean_items.replace("*", "").strip() or "Food Items"

    qty_matches = re.findall(r'\(x(\d+)\)', clean_items_plain)
    if qty_matches:
        pack_count = max(1, sum(int(q) for q in qty_matches))
    else:
        pack_count = max(1, clean_items_plain.count("📦"))

    explicit_sub = getattr(order, "food_subtotal", None) or 0
    explicit_fee = getattr(order, "delivery_fee", None) or 0

    if explicit_sub > 0:
        food_subtotal = int(explicit_sub)
        delivery_fee = int(explicit_fee) if explicit_fee > 0 else _calc_tiered_delivery_fee(pack_count)
        gross_total = food_subtotal + delivery_fee
    else:
        try:
            quoted = int(float(
                order.customer_initial_offered_price
                or order.final_price_agreed_by_cust_and_rider
                or order.paid_amount
                or 0
            ))
        except (ValueError, TypeError):
            quoted = 0

        pack_line_matches = re.findall(r'\(x\d+\)\s*[—–-]\s*₦([0-9,]+)', clean_items_plain)
        if not pack_line_matches:
            pack_line_matches = re.findall(r'[—–-]\s*₦([0-9,]+)', clean_items_plain)

        if pack_line_matches:
            food_subtotal = sum(int(val.replace(",", "")) for val in pack_line_matches)
            delivery_fee = (
                (quoted - food_subtotal)
                if quoted > food_subtotal
                else _calc_tiered_delivery_fee(pack_count)
            )
            gross_total = food_subtotal + delivery_fee
        else:
            delivery_fee = _calc_tiered_delivery_fee(pack_count) if quoted > 0 else 0
            food_subtotal = max(0, quoted - delivery_fee) if quoted > delivery_fee else quoted
            gross_total = food_subtotal + delivery_fee

    return {
        "food_subtotal": food_subtotal,
        "delivery_fee": delivery_fee,
        "gross_total": gross_total,
        "pack_count": pack_count,
        "clean_items": clean_items_plain,
    }


def _order_belongs_to_restaurant(order: models.Orders, restaurant_name: str, total_restaurants: int) -> bool:
    if total_restaurants <= 1:
        return True
    pickup = (order.pickup_location_name or "").lower()
    desc = (order.package_description or "").lower()
    short_name = (
        restaurant_name.lower()
        .replace("restaurant", "")
        .replace("kitchen", "")
        .strip()
    )
    if short_name and (short_name in pickup or short_name in desc):
        return True
    return restaurant_name.lower() in pickup or restaurant_name.lower() in desc


async def _fetch_food_orders_in_lagos_window(
    db: AsyncSession,
    start_date: date,
    end_date: date,
) -> List[models.Orders]:
    """
    Fetches all non-cancelled food orders whose Lagos (UTC+1) date is between
    start_date and end_date (inclusive).
    """
    start_utc = datetime.combine(start_date, time.min, tzinfo=UTC) - LAGOS_UTC_OFFSET - timedelta(hours=2)
    end_utc = datetime.combine(end_date, time.max, tzinfo=UTC) - LAGOS_UTC_OFFSET + timedelta(hours=2)

    stmt = (
        select(models.Orders)
        .where(models.Orders.package_image_id == "FOOD_ORDER")
        .where(models.Orders.status.notin_(["cancelled", "awaiting_cart_selection", "awaiting_dropoff_address"]))
        .where(models.Orders.created_at >= start_utc)
        .where(models.Orders.created_at <= end_utc)
        .order_by(models.Orders.created_at.asc())
    )
    res = await db.execute(stmt)
    candidates = list(res.scalars().all())

    filtered: List[models.Orders] = []
    for o in candidates:
        lagos_d = _to_lagos_dt(o.created_at).date()
        if start_date <= lagos_d <= end_date:
            filtered.append(o)
    return filtered


async def _resolve_restaurant_targets(
    db: AsyncSession,
    target_chat_id: Optional[str] = None
) -> tuple[List[tuple[str, str]], int]:
    rest_res = await db.execute(
        select(models.Restaurants).where(models.Restaurants.is_active == True)
    )
    restaurants = list(rest_res.scalars().all())

    if target_chat_id:
        chat_str = str(target_chat_id).strip()
        linked = [r for r in restaurants if str(r.telegram_chat_id or "").strip() == chat_str]
        if linked:
            return [(r.name, chat_str) for r in linked], len(restaurants)
        default_name = restaurants[0].name if restaurants else "Madam G Restaurant"
        return [(default_name, chat_str)], max(1, len(restaurants))

    targets: List[tuple[str, str]] = []
    seen = set()
    fallback_chat = get_fallback_restaurant_chat_id()
    for r in restaurants:
        cid = str(r.telegram_chat_id or fallback_chat or "").strip()
        if cid and (r.name, cid) not in seen:
            seen.add((r.name, cid))
            targets.append((r.name, cid))

    if not targets and fallback_chat:
        targets.append(("Madam G Restaurant", fallback_chat))

    return targets, max(1, len(restaurants))


async def send_daily_restaurant_sales_report(
    db: AsyncSession,
    target_date: Optional[date] = None,
    target_chat_id: Optional[str] = None,
) -> int:
    """
    Sends each active restaurant's daily sales breakdown to Telegram:
    lists each food order with food details, order total, delivery fee,
    and net food sales (total minus delivery fee).
    Returns the number of restaurant reports successfully dispatched.
    """
    report_date = target_date or (datetime.now(UTC) + LAGOS_UTC_OFFSET).date()
    date_label = report_date.strftime("%a, %d %b %Y")
    all_orders = await _fetch_food_orders_in_lagos_window(db, report_date, report_date)
    targets, total_restaurants = await _resolve_restaurant_targets(db, target_chat_id)

    sent_reports = 0
    for rest_name, chat_id in targets:
        rest_orders = [o for o in all_orders if _order_belongs_to_restaurant(o, rest_name, total_restaurants)]

        if not rest_orders:
            empty_msg = (
                f"📊 *DAILY SALES SUMMARY — {rest_name}*\n"
                f"📅 *Date:* {date_label}\n\n"
                f"No food orders were recorded for this date.\n\n"
                f"• *Total Orders:* `0`\n"
                f"• *Gross Sales:* `₦0`\n"
                f"• *Delivery Fees:* `₦0`\n"
                f"• *Net Food Sales (Minus Delivery):* *₦0*"
            )
            resp = await send_telegram_message(chat_id=chat_id, text=empty_msg, parse_mode="Markdown")
            if resp and resp.get("ok"):
                sent_reports += 1
            continue

        order_blocks: List[str] = []
        total_packs = 0
        total_gross = 0
        total_delivery = 0
        total_food_net = 0
        paid_count = 0

        for idx, o in enumerate(rest_orders, 1):
            fin = extract_order_financials(o)
            total_packs += fin["pack_count"]
            total_gross += fin["gross_total"]
            total_delivery += fin["delivery_fee"]
            total_food_net += fin["food_subtotal"]

            p_status = getattr(o, "payment_status", "pending_payment") or "pending_payment"
            if p_status == "paid":
                paid_count += 1
                pay_badge = "✅ Paid"
            elif p_status == "partial_payment":
                pay_badge = "⚠️ Partial"
            else:
                pay_badge = "⏳ Pending"

            wat_time = _to_lagos_dt(o.created_at).strftime("%I:%M %p")
            items_formatted = fin["clean_items"]
            if len(items_formatted) > 450:
                items_formatted = items_formatted[:447] + "..."

            block = (
                f"*{idx}. Order #{o.order_number}* ({wat_time} | {pay_badge})\n"
                f"{items_formatted}\n"
                f"💵 Food: `₦{fin['food_subtotal']:,}` | 🛵 Delivery: `₦{fin['delivery_fee']:,}` | Total: `₦{fin['gross_total']:,}`"
            )
            order_blocks.append(block)

        header = (
            f"📊 *DAILY SALES SUMMARY — {rest_name}*\n"
            f"📅 *Date:* {date_label}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        summary_block = (
            f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 *DAILY TOTALS*\n"
            f"• *Total Orders:* `{len(rest_orders)}` (`{paid_count}` paid, `{total_packs}` pack{'s' if total_packs != 1 else ''})\n"
            f"• *Total Sales (With Delivery):* `₦{total_gross:,}`\n"
            f"• *Less Delivery Fees:* `-₦{total_delivery:,}`\n"
            f"💰 *Food Sold Total (Minus Delivery Fee):* *₦{total_food_net:,}*"
        )

        # Chunk long days cleanly below Telegram's 4096-character limit
        chunks: List[str] = []
        current_chunk = header
        for block in order_blocks:
            addition = block + "\n\n"
            if len(current_chunk) + len(addition) > 3400:
                chunks.append(current_chunk.rstrip())
                current_chunk = f"📊 *DAILY SALES (Cont.) — {rest_name}*\n\n" + addition
            else:
                current_chunk += addition

        if len(current_chunk) + len(summary_block) <= 3950:
            chunks.append(current_chunk.rstrip() + summary_block)
        else:
            chunks.append(current_chunk.rstrip())
            chunks.append(summary_block.lstrip())

        all_ok = True
        for ch in chunks:
            resp = await send_telegram_message(chat_id=chat_id, text=ch, parse_mode="Markdown")
            if not (resp and resp.get("ok")):
                all_ok = False
        if all_ok:
            sent_reports += 1

    return sent_reports


async def send_weekly_restaurant_sales_report(
    db: AsyncSession,
    end_date: Optional[date] = None,
    target_chat_id: Optional[str] = None,
) -> int:
    """
    Generates an Excel-ready CSV document covering the 7-day week ending on end_date
    (Sunday through Saturday when scheduled on Saturdays) containing all orders,
    food item details, gross totals, delivery fees, and net food sales (total minus delivery fee),
    and sends it as a Telegram document to each active restaurant.
    """
    week_end = end_date or (datetime.now(UTC) + LAGOS_UTC_OFFSET).date()
    week_start = week_end - timedelta(days=6)
    period_label = f"{week_start.strftime('%d %b %Y')} - {week_end.strftime('%d %b %Y')}"

    all_orders = await _fetch_food_orders_in_lagos_window(db, week_start, week_end)
    targets, total_restaurants = await _resolve_restaurant_targets(db, target_chat_id)

    sent_docs = 0
    for rest_name, chat_id in targets:
        rest_orders = [o for o in all_orders if _order_belongs_to_restaurant(o, rest_name, total_restaurants)]

        total_packs = 0
        total_gross = 0
        total_delivery = 0
        total_food_net = 0
        paid_count = 0
        daily_rollup: Dict[date, Dict[str, int]] = {}

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([f"{rest_name} - Weekly Sales Report ({period_label})"])
        writer.writerow([])
        writer.writerow([
            "Date & Time (WAT)",
            "Order Number",
            "Order Status",
            "Payment Status",
            "Customer Phone",
            "Delivery Address",
            "Packs",
            "Food Sold Details",
            "Gross Total (NGN)",
            "Delivery Fee (NGN)",
            "Net Food Sales - Minus Delivery (NGN)",
            "Transaction Reference",
        ])

        for o in rest_orders:
            fin = extract_order_financials(o)
            wat_dt = _to_lagos_dt(o.created_at)
            o_date = wat_dt.date()

            total_packs += fin["pack_count"]
            total_gross += fin["gross_total"]
            total_delivery += fin["delivery_fee"]
            total_food_net += fin["food_subtotal"]

            p_status = getattr(o, "payment_status", "pending_payment") or "pending_payment"
            if p_status == "paid":
                paid_count += 1

            bucket = daily_rollup.setdefault(o_date, {"orders": 0, "packs": 0, "gross": 0, "delivery": 0, "net": 0})
            bucket["orders"] += 1
            bucket["packs"] += fin["pack_count"]
            bucket["gross"] += fin["gross_total"]
            bucket["delivery"] += fin["delivery_fee"]
            bucket["net"] += fin["food_subtotal"]

            flat_items = " | ".join(line.strip() for line in fin["clean_items"].splitlines() if line.strip())
            writer.writerow([
                wat_dt.strftime("%Y-%m-%d %H:%M"),
                o.order_number,
                o.status or "",
                p_status,
                o.recipient_phone_number or o.sender_wa_number or "",
                o.dropoff_location_name or "",
                fin["pack_count"],
                flat_items,
                fin["gross_total"],
                fin["delivery_fee"],
                fin["food_subtotal"],
                getattr(o, "transaction_reference", None) or "",
            ])

        writer.writerow([])
        writer.writerow(["WEEKLY TOTALS", "", "", "", "", "", total_packs, f"{len(rest_orders)} Orders ({paid_count} Paid)", total_gross, total_delivery, total_food_net, ""])
        writer.writerow([])
        writer.writerow(["DAILY BREAKDOWN", "Orders", "Packs", "Gross Total (NGN)", "Delivery Fees (NGN)", "Net Food Sales (NGN)"])
        cur_day = week_start
        while cur_day <= week_end:
            d_stats = daily_rollup.get(cur_day, {"orders": 0, "packs": 0, "gross": 0, "delivery": 0, "net": 0})
            writer.writerow([
                cur_day.strftime("%a %Y-%m-%d"),
                d_stats["orders"],
                d_stats["packs"],
                d_stats["gross"],
                d_stats["delivery"],
                d_stats["net"],
            ])
            cur_day += timedelta(days=1)

        csv_bytes = output.getvalue().encode("utf-8-sig")
        safe_slug = re.sub(r'[^a-z0-9]+', '_', rest_name.lower()).strip('_') or "restaurant"
        filename = f"{safe_slug}_weekly_sales_{week_start.isoformat()}_to_{week_end.isoformat()}.csv"

        caption = (
            f"📑 *WEEKLY SALES REPORT DOCUMENT — {rest_name}*\n"
            f"📅 *Week:* {period_label}\n\n"
            f"• *Total Orders:* `{len(rest_orders)}` (`{paid_count}` paid, `{total_packs}` pack{'s' if total_packs != 1 else ''})\n"
            f"• *Total Gross Sales (With Delivery):* `₦{total_gross:,}`\n"
            f"• *Less Total Delivery Fees:* `-₦{total_delivery:,}`\n"
            f"💰 *Weekly Net Food Sales (Minus Delivery):* *₦{total_food_net:,}*\n\n"
            f"📎 Open the attached CSV file (Excel / Google Sheets compatible) for every order's full food breakdown."
        )

        resp = await send_telegram_document(
            chat_id=chat_id,
            document_bytes=csv_bytes,
            filename=filename,
            caption=caption,
            parse_mode="Markdown",
            mime_type="text/csv",
        )
        if resp and resp.get("ok"):
            sent_docs += 1

    return sent_docs


