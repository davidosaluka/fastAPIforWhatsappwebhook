import os
import logging
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
        f"Status: *Preparing Meal 🍳*"
    )

    resp = await send_telegram_message(
        chat_id=chat_id,
        text=msg,
        parse_mode="Markdown",
        disable_notification=False
    )
    return bool(resp and resp.get("ok"))


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

    dispatch_text = (
        f"🛵 *NEW FOOD DELIVERY AVAILABLE!* 🍲💨\n\n"
        f"*Order #:* `{order.order_number}`\n"
        f"📍 *Pickup:* {restaurant_name} ({pickup_address})\n"
        f"🏁 *Dropoff:* {dropoff_address}\n"
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
                rider_msg = (
                    f"🟢 *GREEN LIGHT: PAYMENT CONFIRMED!* 🍲💨\n\n"
                    f"*Order #:* `{order.order_number}`\n"
                    f"Customer transfer of *₦{paid_amount:,}* has been verified!\n\n"
                    f"📍 *Pickup:* {order.pickup_location_name}\n"
                    f"🏁 *Dropoff:* {order.dropoff_location_name}\n\n"
                    f"👉 *Next Action:* Proceed to the restaurant kitchen now to collect the food package and deliver to the customer!"
                )
                await send_telegram_message(chat_id=rider_obj.telegram_chat_id, text=rider_msg, parse_mode="Markdown")
    except Exception as e:
        logger.warning(f"Error alerting rider of payment confirmation: {e}")


