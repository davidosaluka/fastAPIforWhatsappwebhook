import asyncio
from datetime import UTC, datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import json
import requests
import models
import httpx
import os
import re
from groq import AsyncGroq


async def send_default_template(sender_wa_number, username, auth, graph_url):
    
    req_body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": sender_wa_number,
            "type": "template",
            "template": {
                "name": "default_message",
                "language": { "code": "en" },
                   "components": [
                    {
                        "type": "header",
                        "parameters": [
                        {
                            "type": "text",
                            "text": username
                        }
                        ]
                    }
                    ]
            }
            }
    headers = {
        "Authorization": f"Bearer {auth}",
        "Content-Type": "application/json"

    }
    
    print(req_body)
    async with httpx.AsyncClient() as client:
        response = await client.post(graph_url, json=req_body, headers=headers)
        print(response.status_code, response.text)
    return

async def send_something_went_wrong_template(sender_wa_number, auth, graph_url):
    
    req_body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": sender_wa_number,
            "type": "template",
            "template": {
                "name": "start_over_template",
                "language": { "code": "en" }      
            }
            }
    headers = {
        "Authorization": f"Bearer {auth}",
        "Content-Type": "application/json"

    }
    
    print(req_body)
    async with httpx.AsyncClient() as client:
        response = await client.post(graph_url, json=req_body, headers=headers)
        print(response.status_code, response.text)
    return


async def send_daily_rider_checkin_template(rider_wa_number, auth, graph_url):
    """Dispatches daily 9:00 AM WhatsApp check-in template to riders."""
    target_number = normalize_phone_number(rider_wa_number) or rider_wa_number
    req_body = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": target_number,
        "type": "template",
        "template": {
            "name": "rider_checkin",
            "language": { "code": "en" }      
        }
    }
    headers = {
        "Authorization": f"Bearer {auth}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(graph_url, json=req_body, headers=headers)
        print("Rider check-in template dispatched:", response.status_code, response.text)
    return


async def send_custom_message(sender_wa_number, message, auth, graph_url):
    target_number = normalize_phone_number(sender_wa_number) or sender_wa_number
    req_body = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": target_number,
        "type": "text",
        "text": {
            "body": message
        }
    }
    headers = {
        "Authorization": f"Bearer {auth}",
        "Content-Type": "application/json"
    }
      
    async with httpx.AsyncClient() as client:
        response = await client.post(graph_url, json=req_body, headers=headers)
        print("custom message sent", response.status_code, response.text)
    return

async def send_details_to_recipients(sender_wa_number, message, auth, graph_url):
    """Sends delivery notifications specifically to package recipients, ensuring phone format normalization."""
    await send_custom_message(sender_wa_number=sender_wa_number, message=message, auth=auth, graph_url=graph_url)

async def send_image(sender_wa_number, auth, graph_url, image_id):
    target_number = normalize_phone_number(sender_wa_number) or sender_wa_number
    req_body = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": target_number,
        "type": "image",
        "image": {
            "id": image_id
        }
    }
    headers = {
        "Authorization": f"Bearer {auth}",
        "Content-Type": "application/json"
    }
      
    async with httpx.AsyncClient() as client:
        await client.post(graph_url, json=req_body, headers=headers)

    return


async def send_custom_flow(wa_number, flow_token, message, header, flow_id, flow_cta, screen_name, auth, graph_url):
    target_number = normalize_phone_number(wa_number) or wa_number
    req_body = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": target_number,
            "type": "interactive",
            "interactive": {
                "type": "flow",
                "header": { "type": "text", "text": header },
                "body": { "text": message },
                "action": {
                "name": "flow",
                "parameters": {
                    "flow_message_version": "3",
                    "flow_token": json.dumps(flow_token), 
                    "flow_id": flow_id,
                    "flow_cta": flow_cta,
                    "flow_action": "navigate",
                    "flow_action_payload": {
                    "screen": screen_name
                    }
                }
                }
            }
        }
    
    print("req_body")
    print(req_body)
    headers = {
        "Authorization": f"Bearer {auth}",
        "Content-Type": "application/json"

         }
      
    async with httpx.AsyncClient() as client:
        response = await client.post(graph_url, json=req_body, headers=headers)


    return


async def schedule_registration_reminder(sender_wa_number: str, auth: str, graph_url: str):
    """
    Monitors user registration inactivity.
    Sends a friendly reminder after 5 minutes if user hasn't completed registration or placed an order.
    """
    try:
        await asyncio.sleep(300)

        from database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            registered = await is_user_registered(sender_wa_number, db)
            if registered:
                return  # Stop if user already registered!

            possible_numbers = get_phone_variants(sender_wa_number)
            has_order = await db.execute(
                select(models.Orders).where(models.Orders.sender_wa_number.in_(possible_numbers))
            )
            if has_order.scalars().first() is not None:
                return

            reminder_msg = (
                "⏰ *Registration Reminder*\n\n"
                "We noticed you haven't completed your registration yet.\n\n"
                "Please type 'Send an Order' in this chat to complete your sign-up so you can start sending packages!"
            )
            await send_custom_message(sender_wa_number, reminder_msg, auth, graph_url)
    except Exception as e:
        print(f"schedule_registration_reminder background task error: {e}")


async def send_registration_template(sender_wa_number, auth, graph_url):
    
    req_body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": sender_wa_number,
            "type": "template",
            "template": {
                "name": "w",
                "language": { "code": "en" },
                "components": [
                {
                    "type": "button",
                    "sub_type": "flow",
                    "index": "0"
                    
                }
                ]
            }
            }
    headers = {
        "Authorization": f"Bearer {auth}",
        "Content-Type": "application/json"

    }
    

    async with httpx.AsyncClient() as client:
        response = await client.post(graph_url, json=req_body, headers=headers)
        print(response.status_code, response.text)
        #print(response.text[0]["messages"][0]["id"])

    asyncio.create_task(schedule_registration_reminder(sender_wa_number, auth, graph_url))
    return


async def reply_user_that_has_just_registered(sender_wa_number, auth, graph_url):
    
    req_body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": sender_wa_number,
            "type": "template",
            "template": {
                "name": "other_details",
                "language": { "code": "en" },
                "components": [
                {
                    "type": "button",
                    "sub_type": "flow",
                    "index": "0"
                    
                }
                ]
            }
            }
    headers = {
        "Authorization": f"Bearer {auth}",
        "Content-Type": "application/json"

    }
    

    async with httpx.AsyncClient() as client:
        response = await client.post(graph_url, json=req_body, headers=headers)
        print(response.status_code, response.text)
        #print(response.text[0]["messages"][0]["id"])
    return

'''async def request_package_image (sender_wa_number, auth, graph_url):
    req_body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": sender_wa_number,
            "type": "image",
            "image": {
                "id": "1474439550701963"
            }
        }'''

async def request_pickup_location (sender_wa_number, auth, graph_url):
    req_body = {
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "type": "interactive",
  "to": sender_wa_number,
  "interactive": {
    "type": "location_request_message",
    "body": {
      "text": "📍 Please share your *PICKUP LOCATION* so we can get things moving!"
    },
    "action": {
      "name": "send_location"
    }
  }
}

    headers = {
        "Authorization": f"Bearer {auth}",
        "Content-Type": "application/json"

    }
    async with httpx.AsyncClient() as client:
        response = await client.post(graph_url, json=req_body, headers=headers)
        print(response.status_code, response.text)
        #print(response.text[0]["messages"][0]["id"])
    return

# async def request_dropoff_location (sender_wa_number, auth, graph_url):
#     req_body = {
#   "messaging_product": "whatsapp",
#   "recipient_type": "individual",
#   "type": "interactive",
#   "to": sender_wa_number,
#   "interactive": {
#     "type": "location_request_message",
#     "body": {
#       "text": "Please select your DROP-OFF location "
#     },
#     "action": {
#       "name": "send_location"
#     }
#   }
# }

#     headers = {
#         "Authorization": f"Bearer {auth}",
#         "Content-Type": "application/json"

#     }
#     async with httpx.AsyncClient() as client:
#         response = await client.post(graph_url, json=req_body, headers=headers)
#         print(response.status_code, response.text)
#         #print(response.text[0]["messages"][0]["id"])
#     return


def normalize_phone_number(phone: str) -> str:
    """
    Converts any Nigerian phone number into canonical WhatsApp format (2348151033428).
    Handles 080..., 081..., 090..., 070..., 091..., +234..., 234...
    """
    if not phone:
        return ""
    clean = re.sub(r'[^\d]', '', str(phone))
    if clean.startswith("0") and len(clean) == 11:
        return "234" + clean[1:]
    if len(clean) == 10 and clean[0] in ['7', '8', '9']:
        return "234" + clean
    return clean


def get_phone_variants(phone: str) -> list[str]:
    """
    Generates all equivalent representations of a phone number (e.g. 081..., 23481..., +23481..., 81..., +1...).
    Handles raw digits and country prefix variations across international and local formats.
    """
    if not phone:
        return []
    raw_str = str(phone)
    clean_digits = re.sub(r'[^\d]', '', raw_str)
    variants = set([phone, raw_str, clean_digits])
    if clean_digits:
        variants.add(f"+{clean_digits}")

    canonical = normalize_phone_number(phone)
    if len(canonical) == 13 and canonical.startswith("234"):
        local_fmt = "0" + canonical[3:]
        plus_fmt = "+" + canonical
        raw_fmt = canonical[3:]
        variants.update([canonical, local_fmt, plus_fmt, raw_fmt])
    return [v for v in variants if v]


async def get_active_ride(sender_wa_number: str, db: AsyncSession):
    possible_numbers = get_phone_variants(sender_wa_number)
    active_statuses = ["confirmed", "rider_accepted", "awaiting_pickup", "in_transit", "picked_up", "awaiting_dropoff"]
    result = await db.execute(
        select(models.Orders)
        .where(models.Orders.sender_wa_number.in_(possible_numbers))
        .where(models.Orders.status.in_(active_statuses))
        .order_by(models.Orders.created_at.desc())
    )
    order = result.scalars().first()
    if order:
        if order.status == "confirmed" and order.sla_expires_by and order.sla_expires_by <= datetime.now(UTC):
            return None
        return order
    return None

async def update_rider_offer_status(rider_wa_number: str, status_val: str, db: AsyncSession):
    """Updates status in RiderOffer table for rider receipts (delivered, read)."""
    possible_numbers = get_phone_variants(rider_wa_number)

    await db.execute(
        update(models.RiderOffer)
        .where(models.RiderOffer.rider_wa_number.in_(possible_numbers))
        .where(models.RiderOffer.status != "accepted")
        .values(status=status_val, updated_at=datetime.now(UTC))
    )
    await db.commit()


async def get_active_ride_by_number(order_number: str, db: AsyncSession):
    result = await db.execute(
        select(models.Orders)
        .where(models.Orders.order_number == order_number)
    )
    return result.scalars().first()


async def schedule_user_session_timeout(order_number: str, sender_wa_number: str, auth: str, graph_url: str):
    """
    Monitors user input inactivity during order initialization (e.g. pending package image upload).
    Sends a friendly reminder after 5 minutes, and auto-expires the session after 15 minutes.
    """
    try:
        # 1. First reminder after 5 minutes (300 seconds)
        await asyncio.sleep(300)

        from database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            order = await get_active_ride_by_number(order_number, db)
            # If user already uploaded image or order state changed, exit immediately
            if not order or order.status != "confirmed" or order.package_image_id is not None:
                return

            reminder_msg = (
                f"⏰ *Pending Order Reminder*\n\n"
                f"We're still waiting for a photo of your package to complete Order *{order_number}* and alert nearby riders.\n\n"
                f"Please snap and upload the photo whenever you're ready!"
            )
            await send_custom_message(sender_wa_number, reminder_msg, auth, graph_url)

        # 2. Session timeout / expiry after another 10 minutes (600 seconds -> 15 minutes total)
        await asyncio.sleep(600)

        async with AsyncSessionLocal() as db:
            order = await get_active_ride_by_number(order_number, db)
            if not order or order.status != "confirmed" or order.package_image_id is not None:
                return

            # Mark order as expired in DB
            await db.execute(
                update(models.Orders)
                .where(models.Orders.order_number == order_number)
                .values(status="expired")
            )
            await db.commit()

            timeout_msg = (
                f"⌛ *Session Expired*\n\n"
                f"Your order request *{order_number}* has timed out due to inactivity.\n\n"
                f"Whenever you're ready to send a package, just reply 'Hi' or type 'Send an Order'!"
            )
            await send_custom_message(sender_wa_number, timeout_msg, auth, graph_url)
    except Exception as e:
        print(f"schedule_user_session_timeout background task error: {e}")


async def schedule_customer_offer_timeout(order_number: str, customer_wa_number: str, rider_name: str, proposed_amount: str, auth: str, graph_url: str):
    """
    Monitors customer inactivity when a rider sends a counter-offer.
    Sends a friendly reminder after 4 minutes if customer hasn't accepted.
    """
    try:
        await asyncio.sleep(240)

        from database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            order = await get_active_ride_by_number(order_number, db)
            if not order or order.status != "confirmed":
                return  # Stop if customer accepted, cancelled, or rider assigned

            reminder_msg = (
                f"⏰ *Counter Offer Reminder*\n\n"
                f"Rider *{rider_name}* proposed an offer of *{proposed_amount}* for Order *{order_number}*.\n\n"
                f"Please accept the offer or adjust your fare to confirm your rider!"
            )
            await send_custom_message(customer_wa_number, reminder_msg, auth, graph_url)
    except Exception as e:
        print(f"schedule_customer_offer_timeout background task error: {e}")


async def schedule_order_followups(order_number: str, sender_wa_number: str, auth: str, graph_url: str):
    """
    State-aware background task that monitors order search progress.
    Re-queries DB before every alert. Suppresses follow-up if order is no longer searching (confirmed).
    """
    try:
        # Follow-up 1: 60 seconds (1 minute)
        await asyncio.sleep(60)

        from database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            order = await get_active_ride_by_number(order_number, db)
            if not order or order.status != "confirmed":
                return  # Stop immediately if rider accepted, cancelled, or completed!

            offers_res = await db.execute(
                select(models.RiderOffer).where(models.RiderOffer.order_number == order_number)
            )
            offers = offers_res.scalars().all()
            total_notified = len(offers)
            read_count = sum(1 for o in offers if o.status in ["read", "viewed"])
            delivered_count = sum(1 for o in offers if o.status in ["delivered", "read", "viewed"])

            if read_count > 0:
                msg = f"Good news 👀 *{read_count}* rider{'s' if read_count > 1 else ''} have viewed your delivery offer! We're waiting for one to accept."
            elif delivered_count > 0 or total_notified > 0:
                count = delivered_count if delivered_count > 0 else total_notified
                msg = f"Good news 👀 We've dispatched your order to *{count}* nearby rider{'s' if count > 1 else ''}. We're waiting for them to view and accept!"
            else:
                msg = "Stay locked in 👀 We're searching for available riders nearby for your package. We'll update you as soon as one accepts."
            
            await send_custom_message(sender_wa_number, msg, auth, graph_url)

        # Follow-up 2: 2 minutes later (300 seconds total) -> Fare Escalation Recommendation
        await asyncio.sleep(120)

        async with AsyncSessionLocal() as db:
            order = await get_active_ride_by_number(order_number, db)
            if not order or order.status != "confirmed":
                return  # Stop immediately if rider accepted, cancelled, or completed!

            escalation_msg = (
                "We've sent your delivery offer to nearby riders, but none have accepted yet. 🔄\n\n"
                "Increasing your fare slightly can help attract a rider quickly."
            )
            await send_custom_flow(
                wa_number=sender_wa_number,
                flow_token={"order_number": order_number},
                message=escalation_msg,
                header="🔔 Need a rider faster?",
                flow_id="950647507961316",
                flow_cta="I want to increase my fare",
                screen_name="CUST_INCREASE_FARE_SCREEN",
                auth=auth,
                graph_url=graph_url
            )
    except Exception as e:
        print(f"schedule_order_followups background task error: {e}")


async def mark_rider_available_if_rider(sender_wa_number: str, db: AsyncSession):
    """
    Automatically marks a rider as 'available' whenever they send a message to InTime.
    This registers the rider for daily dispatch within Meta's free 24-hour customer service window.
    """
    if not sender_wa_number:
        return
    possible_numbers = get_phone_variants(sender_wa_number)
    rider_result = await db.execute(
        select(models.Riders).where(models.Riders.rider_wa_number.in_(possible_numbers))
    )
    rider = rider_result.scalars().first()
    if rider:
        if rider.availability_status != "available":
            rider.availability_status = "available"
            await db.commit()
            print(f"🟢 [RIDER CHECK-IN] Marked rider '{rider.first_name} {rider.last_name}' ({rider.rider_wa_number}) as AVAILABLE for 24h window.")
        else:
            print(f"ℹ️ [RIDER CHECK-IN] Rider '{rider.first_name} {rider.last_name}' ({rider.rider_wa_number}) is already ACTIVE.")


async def get_rider(sender_wa_number, auth, graph_url, order_details, db:AsyncSession):
    message = f"✅ Your order has been placed!\n\nOrder Number: *{order_details['order_number']}*\n\n🔍 Searching for available riders nearby, please hold on..."
    await send_custom_message(sender_wa_number, message , auth, graph_url)
    
    sender_variants = get_phone_variants(sender_wa_number)
    riders = await db.execute(
        select(models.Riders)
        .where(models.Riders.availability_status == "available")
        .where(models.Riders.rider_wa_number.not_in(sender_variants))
    )
    riders = riders.scalars().all()
    
    print(f"[DISPATCH SEARCH] Order {order_details['order_number']} placed by customer ({sender_wa_number}). Found {len(riders)} available rider(s): {[r.rider_wa_number for r in riders]}")
    if not riders:
        print(f"[DISPATCH SEARCH] No active 'available' riders found in 24h window for order {order_details['order_number']}.")

    is_priority = bool(order_details.get('is_priority') or (order_details.get('is_drug') and order_details.get('is_urgent')))

    for rider in riders:
        try:
            if is_priority:
                header = f"🚨 URGENT MEDICATION DISPATCH! 🚨\n"
                message = (
                    f"💊 *PRIORITY DELIVERY - URGENT MEDICATION* 💊\n\n"
                    f"ORDER DESCRIPTION 📦: {order_details['package_description']}\n\n"
                    f"PICKUP LOCATION📍: {order_details['pick_up_location']}\n\n"
                    f"DROPOFF LOCATION📍: {order_details['drop_off_location']}\n\n"
                    f"OFFERED PRICE💵: {order_details['offered_price']}\n\n"
                    f"ORDER NUMBER: {order_details['order_number']}\n\n"
                    f"⚡ *PRIORITY*: Medical supply needed ASAP! Please accept immediately if available."
                )
            else:
                header = f"DISPATCH REQUEST!\n"
                message = (
                    f"ORDER DESCRIPTION 📦: {order_details['package_description']}\n\n"
                    f"PICKUP LOCATION📍: {order_details['pick_up_location']}\n\n"
                    f"DROPOFF LOCATION📍: {order_details['drop_off_location']}\n\n"
                    f"OFFERED PRICE💵: {order_details['offered_price']}\n\n"
                    f"ORDER NUMBER: {order_details['order_number']}\n\n"
                )

            new_offer = models.RiderOffer(
                order_number=order_details['order_number'],
                rider_wa_number=rider.rider_wa_number,
                status="sent"
            )
            db.add(new_offer)
            
            await send_custom_flow(
                wa_number=rider.rider_wa_number,
                flow_token={"order_number": order_details['order_number']},
                message=message,
                header=header,
                flow_id="1513067607105184",
                flow_cta="Accept or Negotiate",
                screen_name="RECOMMEND",
                auth=auth,
                graph_url=graph_url
            )
            if order_details.get('image_id'):
                await send_image(rider.rider_wa_number, auth, graph_url, order_details['image_id'])
        except Exception as e:
            print(f"Error dispatching offer to rider {rider.rider_wa_number}: {e}")

    await db.commit()

    asyncio.create_task(schedule_order_followups(order_details['order_number'], sender_wa_number, auth, graph_url))
    return




# async def handle_location(sender_wa_number, lat, lng, address, auth, graph_url, db):
#     ride = await get_active_ride(sender_wa_number, db)
    
#     if not ride:
#         # no active ride, something went wrong
#         message = "Something went wrong, please start again."
#         await send_custom_message(sender_wa_number, message , auth, graph_url)
#         return

#     match ride.status:
#         case "awaiting_pickup":
#             ride.pickup_lat = lat
#             ride.pickup_lng = lng
#             ride.pickup_location_name = address
#             ride.status = "awaiting_dropoff"
#             await db.commit()
#             await request_dropoff_location(sender_wa_number, auth, graph_url)

#         case "awaiting_dropoff":
#             ride.dropoff_lat = lat
#             ride.dropoff_lng = lng
#             ride.dropoff_location_name = address
#             ride.status = "confirmed"
#             await db.commit()
            
#             order_details = {
#                 "package_description": ride.package_description,
#                 "pick_up_location": ride.pickup_location_name,
#                 "drop_off_location": ride.dropoff_location_name,
#                 "offered_price": ride.customer_intital_offered_price,
#                 "order_id": ride.order_number

#             }
#             print("order_details is: ")
#             print(order_details)
#             await get_rider(sender_wa_number=sender_wa_number, auth=auth, graph_url=graph_url, order_details=order_details, db=db)

async def send_details_to_recipients(sender_wa_number, message, auth, graph_url):
    req_body = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": sender_wa_number,
        "type": "text",
        "text": {
            "body": message
        }
    }

    headers = {
        "Authorization": f"Bearer {auth}",
        "Content-Type": "application/json"

    }
    async with httpx.AsyncClient() as client:
        response = await client.post(graph_url, json=req_body, headers=headers)
        print(response.status_code, response.text)
    return




async def handle_case_where_rider_has_accepted_the_ride(sender_wa_number, order_number, AUTH, GRAPH_URL, db:AsyncSession):
    order_result = await db.execute(
    select(models.Orders)
    .where(models.Orders.order_number == order_number)
    )
    order = order_result.scalars().first()
    if not order:
        return
    order_status = order.status

    rider_details_res = await db.execute(
    select(models.Riders)
    .where(models.Riders.rider_wa_number == sender_wa_number)
        )
    rider_details = rider_details_res.scalars().first()
    rider_name = f"{rider_details.first_name} {rider_details.last_name}" if rider_details else "Rider"
    rider_phone = rider_details.rider_wa_number if rider_details else sender_wa_number

    if order_status == "confirmed":
        customer_wa_res = await db.execute(
            select(models.Orders.sender_wa_number)
            .where(models.Orders.order_number == order_number)
        )
        customer_wa_number = customer_wa_res.scalars().first() or order.sender_wa_number
        
        sender_user_res = await db.execute(
            select(models.User.name).where(
                models.User.wa_id.in_(get_phone_variants(customer_wa_number))
            )
        )
        sender_name = sender_user_res.scalars().first() or "Someone"

        rider_message = f"🎉 Ride accepted! The customer's number is *{customer_wa_number}*. Please head to the pickup location now. Safe riding! 🏍️"
        customer_message = (
            f"🎉 Great news! Your ride has been accepted.\n\n"
            f"Your rider is on the way to the pickup location and will contact you shortly.\n\n"
            f"🧑‍✈️ Rider's Name: *{rider_name}*\n"
            f"📞 Phone: *{rider_phone}*"
            )
        recipient_message = (
            f"👋 Hello! *{sender_name}* is sending a package to you via InTime!\n\n"
            f"📦 Description: {order.package_description}\n\n"
            f"📍 Pickup: {order.pickup_location_name}\n\n"
            f"🏁 Dropoff: {order.dropoff_location_name}\n\n"
            f"🔖 Order No: {order.order_number}\n\n"
            f"🧑‍✈️ Rider: {rider_name}\n"
            f"📞 Rider's Phone: {rider_phone}"
        )
        recipient_wa_number = order.recipient_phone_number
        
        #sending a message to the rider
        await send_custom_message(sender_wa_number=sender_wa_number, message=rider_message, auth=AUTH, graph_url=GRAPH_URL)         
        
        #sending a message to the customer
        await send_custom_message(sender_wa_number=customer_wa_number, message=customer_message, auth=AUTH, graph_url=GRAPH_URL) 
        
        await send_details_to_recipients(sender_wa_number=recipient_wa_number, message=recipient_message, auth=AUTH, graph_url=GRAPH_URL)
        

        await db.execute(
           update(models.Orders)
           .where(models.Orders.order_number == order_number)
           .values(status="rider_accepted", rider_wa_number=sender_wa_number, final_price_agreed_by_cust_and_rider=order.final_price_agreed_by_cust_and_rider)
        )
        await db.commit()

        asyncio.create_task(schedule_rider_process_reminders(
            order_number=order.order_number,
            rider_wa_number=rider_details.rider_wa_number,
            auth=AUTH,
            graph_url=GRAPH_URL
        ))

    else:
        rider_message = f"⏰ Sorry, you responded a bit late — this order has already been assigned to another rider."
        await send_custom_message(sender_wa_number=sender_wa_number, message=rider_message, auth=AUTH, graph_url=GRAPH_URL)   


async def schedule_rider_process_reminders(order_number: str, rider_wa_number: str, auth: str, graph_url: str):
    """
    Monitors an active order after rider acceptance.
    Sends up to 2 reminders after the initial prompt.
    If the rider fails to respond after 2 reminders during pickup:
      1. Unassigns the rider and closes the order on their side.
      2. Informs the customer/vendor that the order is being re-routed.
      3. Re-populates dispatch requests to available riders via get_rider.
    """
    try:
        # -------------------------------------------------------------
        # PHASE 1: PICKUP PROMPT & REMINDERS (Initial + 2 Reminders max)
        # -------------------------------------------------------------
        # Initial wait before sending first pickup prompt (5 minutes / 300 seconds)
        await asyncio.sleep(300)

        pickup_reminder_count = 0
        max_reminders_after_initial = 2  # Exactly 2 reminders after initial prompt

        while pickup_reminder_count <= max_reminders_after_initial:
            from database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                order = await get_active_ride_by_number(order_number, db)
                
                # Exit if order cancelled, completed, or expired
                if not order or order.status in ["cancelled", "completed", "expired"]:
                    return
                
                # If rider marked package picked up or delivered, advance to Phase 2
                if order.delivery_progression_status in ["package_picked_up", "package_delivered"]:
                    break

                # Send initial prompt (count=0) or follow-up reminder (count 1 or 2)
                if pickup_reminder_count == 0:
                    header = "Have you picked up the package?"
                    message = "📦 Tap the button below once you've picked up the package."
                else:
                    header = "⏰ Pickup Reminder"
                    message = (
                        f"⏰ *Pickup Reminder ({pickup_reminder_count}/{max_reminders_after_initial})*\n\n"
                        f"Hi! You have an ongoing pickup for Order *{order_number}*.\n\n"
                        f"Please tap the button below once you've picked up the package from the sender."
                    )

                await send_custom_flow(
                    wa_number=rider_wa_number,
                    flow_token={"order_number": order_number},
                    message=message,
                    header=header,
                    flow_id="1521319786323152",
                    flow_cta="Picked Up Package?",
                    screen_name="flow_to_ask_if_rider_has_picked_up_package",
                    auth=auth,
                    graph_url=graph_url
                )

            pickup_reminder_count += 1
            await asyncio.sleep(300)  # Wait 5 minutes before next check/reminder

        # -------------------------------------------------------------
        # CHECK IF RIDER FAILED TO RESPOND TO PICKUP REMINDERS
        # -------------------------------------------------------------
        from database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            order = await get_active_ride_by_number(order_number, db)
            if order and order.status == "rider_accepted" and order.delivery_progression_status not in ["package_picked_up", "package_delivered"]:
                print(f"[RIDER TIMEOUT] Rider ({rider_wa_number}) did not respond to pickup reminders for order {order_number}. Re-routing order...")

                # 1. Unassign rider and reset order back to 'confirmed'
                await db.execute(
                    update(models.Orders)
                    .where(models.Orders.order_number == order_number)
                    .values(status="confirmed", rider_wa_number=None)
                )
                await db.commit()

                # 2. Inform unresponsive rider
                unassign_msg = (
                    f"⏰ *Order Re-assigned*\n\n"
                    f"Due to inactivity, Order *{order_number}* has been unassigned from you and returned to dispatch search."
                )
                await send_custom_message(rider_wa_number, unassign_msg, auth, graph_url)

                # 3. Inform vendor / customer
                reroute_msg = (
                    f"🔄 *Re-routing Order*\n\n"
                    f"Your assigned rider was unresponsive for Order *{order_number}*.\n\n"
                    f"We are re-routing your delivery to other nearby riders right now!"
                )
                await send_custom_message(order.sender_wa_number, reroute_msg, auth, graph_url)

                # 4. Re-populate negotiation/offers to riders
                order_details = {
                    "package_description": order.package_description,
                    "pick_up_location": order.pickup_location_name,
                    "drop_off_location": order.dropoff_location_name,
                    "offered_price": order.customer_initial_offered_price or order.final_price_agreed_by_cust_and_rider or "1000",
                    "order_number": order.order_number,
                    "image_id": order.package_image_id,
                    "is_priority": order.is_priority,
                    "is_drug": order.is_drug,
                    "is_urgent": order.is_urgent
                }
                await get_rider(
                    sender_wa_number=order.sender_wa_number,
                    auth=auth,
                    graph_url=graph_url,
                    order_details=order_details,
                    db=db
                )
                return



    except Exception as e:
        print(f"schedule_rider_process_reminders background task error: {e}")


async def _delayed_send_pickup_flow(wa_number, order_number, auth, graph_url, delay=300):
    await asyncio.sleep(delay)
    await send_custom_flow(
        wa_number=wa_number,
        flow_token={"order_number": order_number},
        message="📦 Tap the button below once you've picked up the package.",
        header="Have you picked up the package?",
        flow_id="1521319786323152",
        flow_cta="Picked Up Package?",
        screen_name="flow_to_ask_if_rider_has_picked_up_package",
        auth=auth,
        graph_url=graph_url
    )


async def handle_case_where_rider_is_negotiating_the_ride(sender_wa_number, order_number, AUTH, GRAPH_URL, db:AsyncSession):
    message = (
        "💬 Not happy with the price? Tap below to send your counter offer."
        )

    await send_custom_flow(
            wa_number=sender_wa_number,
            flow_token={"order_number": order_number},
            message=message,
            header="-",
            flow_id="1448553113617488",
            flow_cta="Input Price",
            screen_name="NEGOTIATE_SCREEN",
            auth=AUTH,
            graph_url=GRAPH_URL
        )


async def message_customer_where_rider_is_negotiating_the_ride(sender_wa_number, order_number, rider_proposed_amount, AUTH, GRAPH_URL, db:AsyncSession):
    order_result = await db.execute(
        select(models.Orders)
        .where(models.Orders.order_number == order_number)
    )

    order = order_result.scalars().first()

    rider_result = await db.execute(
        select(models.Riders)
        .where(models.Riders.rider_wa_number == sender_wa_number)
    )

    rider_details = rider_result.scalars().first()

    if order and order.status == "confirmed":
        customer_wa_res = await db.execute(
            select(models.Orders.sender_wa_number)
            .where(models.Orders.order_number == order_number)
        )
        customer_wa_number = customer_wa_res.scalars().first() or order.sender_wa_number
        rider_name = f"{rider_details.first_name} {rider_details.last_name}" if rider_details else "Rider"

        customer_message = (
            f"🧑‍✈️ Rider: *{rider_name}*\n\n"
            f"💰 Offered Price: *{rider_proposed_amount}*\n\n"
            f"🔖 Order No: {order.order_number}\n\n"
            f"⭐ Rating: 4.5 stars"
            )
        
        asking_customer_to_increase_price_msg = (
            f"Not satisfied with any of the offers? "
            f"You can increase your fare using the button below "
            "and we'll search for more riders. 🔄"
        )
        
        
        
        #sending a message to the customer about the riders offering the prices
        await send_custom_flow(
            wa_number=customer_wa_number,
            flow_token={"order_number": order_number, "rider_wa_number": sender_wa_number},
            message=customer_message,
            header="💸 A rider has made a counter offer",
            flow_id="949497837687906",
            flow_cta="Accept this offer",
            screen_name="customer_accept_or_reject_rider_offer",
            auth=AUTH,
            graph_url=GRAPH_URL
        )

         #sending a message to the customer asking if they want to increase fare. This should be outside the loop
        await send_custom_flow(
            wa_number=customer_wa_number,
            flow_token={"order_number": order_number},
            message=asking_customer_to_increase_price_msg,
            header="🔔",
            flow_id="950647507961316",
            flow_cta="I want to increase my fare",
            screen_name="CUST_INCREASE_FARE_SCREEN",
            auth=AUTH,
            graph_url=GRAPH_URL
        )

        asyncio.create_task(schedule_customer_offer_timeout(order_number, customer_wa_number, rider_name, rider_proposed_amount, AUTH, GRAPH_URL))

        

    else:
        rider_message = f"Sorry! you responded late and this order has already been picked up by another rider"
        await send_custom_message(sender_wa_number=sender_wa_number, message=rider_message, auth=AUTH, graph_url=GRAPH_URL)   





async def handle_case_where_customer_has_accepted_the_ride(sender_wa_number, rider_wa_number, order_number, auth, graph_url, db:AsyncSession, agreed_price=None):
    order_result = await db.execute(
    select(models.Orders)
    .where(models.Orders.order_number == order_number)
    )
    order = order_result.scalars().first()
    if not order:
        return
    order_status = order.status

    print(f"riders number is: {rider_wa_number}")
    rider_details_res = await db.execute(
    select(models.Riders)
    .where(models.Riders.rider_wa_number == rider_wa_number)
        )
    rider_details = rider_details_res.scalars().first()
    rider_name = f"{rider_details.first_name} {rider_details.last_name}" if rider_details else "Rider"
    rider_phone = rider_details.rider_wa_number if rider_details else rider_wa_number

    if order_status == "confirmed":
        customer_wa_number = sender_wa_number

        sender_user_res = await db.execute(
            select(models.User.name).where(
                models.User.wa_id.in_(get_phone_variants(customer_wa_number))
            )
        )
        sender_name = sender_user_res.scalars().first() or "Someone"

        rider_message = f"🎉 Ride confirmed! The customer's number is *{customer_wa_number}*. Please head to the pickup location now. Safe riding! 🏍️"
        customer_message = (
            f"🎉 Your ride is confirmed!\n\n"
            f"Your rider is heading to the pickup location and will be in touch shortly.\n\n"
            f"🧑‍✈️ Rider's Name: *{rider_name}*\n"
            f"📞 Phone: *{rider_phone}*"
            )

        recipient_message = (
            f"👋 Hello! *{sender_name}* is sending a package to you via InTime!\n\n"
            f"📦 Description: {order.package_description}\n\n"
            f"📍 Pickup: {order.pickup_location_name}\n\n"
            f"🏁 Dropoff: {order.dropoff_location_name}\n\n"
            f"🔖 Order No: {order.order_number}\n\n"
            f"🧑‍✈️ Rider: {rider_name}\n"
            f"📞 Rider's Phone: {rider_phone}"
        )
        recipient_wa_number = order.recipient_phone_number
        #sending a message to the rider
        await send_custom_message(sender_wa_number=rider_wa_number, message=rider_message, auth=auth, graph_url=graph_url)         
        
        #sending a message to the customer
        await send_custom_message(sender_wa_number=customer_wa_number, message=customer_message, auth=auth, graph_url=graph_url) 

        await send_details_to_recipients(sender_wa_number=recipient_wa_number, message=recipient_message, auth=auth, graph_url=graph_url)
        
        final_price = agreed_price or (order.customer_initial_offered_price if order else None) or "12000"
        await db.execute(
           update(models.Orders)
           .where(models.Orders.order_number == order_number)
           .values(status="rider_accepted", final_price_agreed_by_cust_and_rider=final_price, rider_wa_number=rider_wa_number)
           
        )
        await db.commit()

        asyncio.create_task(schedule_rider_process_reminders(
            order_number=order.order_number,
            rider_wa_number=rider_wa_number,
            auth=auth,
            graph_url=graph_url
        ))



    else:
        rider_message = f"⏰ Sorry, this order has already been assigned to another rider."
        cust_message = f"✅ Your package is already on the way! The rider's details have been sent to you."
        await send_custom_message(sender_wa_number=rider_wa_number, message=rider_message, auth=auth, graph_url=graph_url)   
        await send_custom_message(sender_wa_number=customer_wa_number, message=cust_message, auth=auth, graph_url=graph_url)   

        

async def is_user_registered(sender_wa_number: str, db: AsyncSession) -> bool:
    """Checks if a user is registered by matching display_phone_number, wa_id, phone_number_id, or active orders across formatted variants."""
    possible_numbers = get_phone_variants(sender_wa_number)

    result = await db.execute(
        select(models.User).where(
            (models.User.display_phone_number.in_(possible_numbers)) |
            (models.User.wa_id.in_(possible_numbers)) |
            (models.User.phone_number_id.in_(possible_numbers))
        )
    )
    if result.scalars().first() is not None:
        return True

    order_result = await db.execute(
        select(models.Orders).where(models.Orders.sender_wa_number.in_(possible_numbers))
    )
    return order_result.scalars().first() is not None


async def classify_message_intent(message_text: str) -> str:
    """Classifies user intent semantically using Groq JSON mode."""
    system_prompt = (
        'You are an intent classification engine for InTime delivery platform.\n'
        'Classify the user\'s message into exactly ONE of the following intents:\n'
        '- \'CREATE_ORDER\': ONLY if user explicitly requests to send a package, book a delivery, or place a new order (e.g. "send an order", "book a ride").\n'
        '- \'CANCEL_ORDER\': ONLY if user wants to cancel an active order.\n'
        '- \'TRACK_ORDER\': ONLY if user asks for status, ETA, or tracking of an order.\n'
        '- \'MODIFY_ORDER\': ONLY if user asks to change order details or fare.\n'
        '- \'SUPPORT\': ONLY if user asks for support email, human agent, or help desk.\n'
        '- \'GENERAL_CHAT\': All thank-yous, acknowledgments ("alright thank you", "thanks", "okay", "cool"), small talk, general questions, or small chatter.\n\n'
        'Output strictly a valid JSON object in this format: {"intent": "LABEL"}'
    )
    allowed_intents = {"CREATE_ORDER", "CANCEL_ORDER", "TRACK_ORDER", "MODIFY_ORDER", "SUPPORT", "GENERAL_CHAT"}
    models_to_try = ["groq/compound-mini", "groq/compound", "openai/gpt-oss-20b", "llama-3.1-8b-instant"]
    
    try:
        groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        for model_name in models_to_try:
            try:
                response = await groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": message_text}
                    ],
                    model=model_name,
                    response_format={"type": "json_object"},
                    temperature=0.0,
                    max_tokens=50,
                    timeout=3.0
                )
                raw_content = response.choices[0].message.content.strip()
                parsed = json.loads(raw_content)
                intent = parsed.get("intent", "").upper().strip()
                if intent in allowed_intents:
                    return intent
            except Exception as inner_e:
                continue
    except Exception as e:
        print(f"Intent classification error: {e}")
    return "GENERAL_CHAT"


async def get_active_rider_order(rider_wa_number: str, db: AsyncSession):
    """Finds active transit order assigned to the rider."""
    possible_numbers = get_phone_variants(rider_wa_number)
    result = await db.execute(
        select(models.Orders)
        .where(models.Orders.rider_wa_number.in_(possible_numbers))
        .where(models.Orders.status.in_(["rider_accepted", "awaiting_pickup", "package_picked_up"]))
    )
    return result.scalars().first()


async def handle_text_message(sender_wa_number: str, text_body: str, username: str, db: AsyncSession, auth: str, graph_url: str):
    """Semantic routing for incoming freeform text messages using LLM-as-a-Router."""
    # --- 0. ACTIVE RIDER IN-TRANSIT CHECK ---
    rider_order = await get_active_rider_order(sender_wa_number, db)
    if rider_order:
        lower_text = text_body.strip().lower()
        if lower_text in ["no", "not yet", "no yet", "nope", "n"]:
            rider_msg = f"Got it 👍 Take your time and ride safely! We'll check back with you shortly regarding Order *{rider_order.order_number}*."
            await send_custom_message(sender_wa_number, rider_msg, auth, graph_url)
            return
        elif lower_text in ["yes", "yeah", "yep", "almost", "close", "y", "arrived"]:
            rider_msg = f"Awesome 🛵! Thanks for confirming. When you arrive at the drop-off location for Order *{rider_order.order_number}*, please request the 5-digit verification code from the recipient."
            await send_custom_message(sender_wa_number, rider_msg, auth, graph_url)

            # Notify Customer (Sender) and Recipient upon Rider ETA confirmation
            try:
                sender_res = await db.execute(
                    select(models.User.name).where(
                        models.User.wa_id.in_(get_phone_variants(rider_order.sender_wa_number))
                    )
                )
                sender_name = sender_res.scalars().first() or "Sender"

                customer_eta_msg = f"🛵 *Delivery Update*: Rider has confirmed they are approximately 10 minutes away from the drop-off location for Order *{rider_order.order_number}*!"
                recipient_eta_msg = f"📦 *Package Update*: Your package from *{sender_name}* (Order *{rider_order.order_number}*) is getting close! Your rider has confirmed they are approximately 10 minutes away."

                if rider_order.sender_wa_number:
                    await send_custom_message(sender_wa_number=rider_order.sender_wa_number, message=customer_eta_msg, auth=auth, graph_url=graph_url)
                if rider_order.recipient_phone_number:
                    await send_details_to_recipients(sender_wa_number=rider_order.recipient_phone_number, message=recipient_eta_msg, auth=auth, graph_url=graph_url)
            except Exception as notify_err:
                print(f"Error sending ETA confirmation notifications to customer/recipient: {notify_err}")

            return

    # --- 1. ACTIVE WORKFLOW STATE CHECK ---
    active_order = await get_active_ride(sender_wa_number, db)
    if active_order and active_order.package_image_id is None:
        msg = (
            f"📸 *Package Photo Needed*\n\n"
            f"Your order *{active_order.order_number}* has been initialized.\n"
            f"Please snap and send a photo of the package to complete your dispatch request and alert nearby riders!"
        )
        await send_custom_message(sender_wa_number, msg, auth, graph_url)
        return

    # Fast-path pre-check for generic courtesy acknowledgments
    lower_clean = text_body.strip().lower().strip(".,!?:;")
    generic_courtesies = {
        "ok", "okay", "thanks", "thank you", "alright", "got it", "noted", "cool", 
        "sure", "nice", "alright thank you", "ok thank you", "ok thanks", "great", 
        "fine", "good", "perfect", "kk", "k", "no problem", "np", "thx"
    }
    
    if lower_clean in generic_courtesies:
        intent = "GENERAL_CHAT"
    else:
        # --- 2. SEMANTIC INTENT CLASSIFICATION ---
        intent = await classify_message_intent(text_body)

    # --- 3. APPLICATION ROUTING ---
    if intent == "CREATE_ORDER":
        # Guard: If user has an active order in progress, do not trigger welcome menu unless they explicitly typed 'send an order'
        if active_order and lower_clean != "send an order":
            intent = "GENERAL_CHAT"
        else:
            registered = await is_user_registered(sender_wa_number, db)
            if registered:
                await reply_user_that_has_just_registered(sender_wa_number, auth, graph_url)
            else:
                await send_registration_template(sender_wa_number, auth, graph_url)
            return

    elif intent == "CANCEL_ORDER":
        order = await get_active_ride(sender_wa_number, db)
        if order and order.status in ["confirmed", "awaiting_pickup"]:
            await db.execute(
                update(models.Orders)
                .where(models.Orders.order_number == order.order_number)
                .values(status="cancelled")
            )
            await db.commit()
            msg = f"❌ Your order *{order.order_number}* has been successfully cancelled."
        elif order:
            msg = f"Order *{order.order_number}* cannot be cancelled at this stage (Status: {order.status})."
        else:
            msg = "You currently have no active order to cancel."
        await send_custom_message(sender_wa_number, msg, auth, graph_url)
        return

    elif intent == "TRACK_ORDER":
        order = await get_active_ride(sender_wa_number, db)
        if order:
            rider_info = f"Rider Phone: *{order.rider_wa_number}*" if order.rider_wa_number else "Searching for available riders..."
            msg = (
                f"📦 *Order Status Update*\n\n"
                f"Order Number: *{order.order_number}*\n"
                f"Status: *{order.status.replace('_', ' ').title()}*\n"
                f"Pickup: {order.pickup_location_name or 'Not set'}\n"
                f"Dropoff: {order.dropoff_location_name or 'Not set'}\n"
                f"Package: {order.package_description or 'Not specified'}\n\n"
                f"🧑‍✈️ {rider_info}"
            )
        else:
            msg = "You currently have no active delivery orders."
        await send_custom_message(sender_wa_number, msg, auth, graph_url)
        return

    elif intent == "MODIFY_ORDER":
        msg = (
            "To modify your delivery details or create a new order, "
            "please type 'Send an Order' in this chat to bring up your options."
        )
        await send_custom_message(sender_wa_number, msg, auth, graph_url)
        registered = await is_user_registered(sender_wa_number, db)
        if registered:
            await reply_user_that_has_just_registered(sender_wa_number, auth, graph_url)
        else:
            await send_registration_template(sender_wa_number, auth, graph_url)
        return

    # --- 4. GENERAL CHAT / SUPPORT (Conversational Groq Agent with Memory) ---
    try:
        order = await get_active_ride(sender_wa_number, db)
        if order:
            order_context = f"Active order: {order.order_number} (Status: {order.status})."
        else:
            order_context = "No active delivery order."

        system_prompt = (
            f"You are the warm, energetic, and helpful AI assistant for InTime 🛵💨, Nigeria's premier dispatch and package delivery service.\n"
            f"Customer Name: {username}.\n"
            f"Current Context: {order_context}.\n"
            f"COMPANY KNOWLEDGE:\n"
            f"- Official Website: https://sendintime.com.ng\n"
            f"- Contact Email: contact@sendintime.com.ng (or intimesender@gmail.com)\n"
            f"- Support Phone: +234 815 103 3428\n"
            f"- Coverage: 12+ major cities across Nigeria (Lagos, Abuja, Port Harcourt, Kano, Ibadan, Benin City, Enugu, Kaduna, Onitsha, Warri, Calabar, Owerri).\n"
            f"- Services: InTime connects customers with verified dispatch riders to compare prices, negotiate fares, and send packages fast and safely.\n\n"
            f"STRICT BEHAVIOR RULES:\n"
            f"1. CONTEXTUALLY AWARE: You have multi-turn chat memory. Pay close attention to previous messages in the chat history so your answers connect naturally to what was just discussed.\n"
            f"2. NO REPETITIVE GREETINGS: Do NOT repeat 'Hey {username}!' or formal introductions in every single reply if you are already in an ongoing conversation with the user.\n"
            f"3. EMOJIS & SPICE: Use expressive emojis and icons (like 📦, 🛵, ✨, 🚀, ⚡, 💬, 🎉) in every response to make the conversation lively, engaging, and friendly!\n"
            f"4. STEER BACK TO BUSINESS: For small talk or general questions, respond warmly and enthusiastically (1-2 sentences), but ALWAYS guide the customer back to sending packages with InTime by reminding them to type *Send an Order* whenever they're ready!\n"
            f"5. WHATSAPP BOLD FORMATTING: WhatsApp only bolds text wrapped in SINGLE asterisks like *Send an Order* or *bold text*. NEVER use double asterisks **text** as WhatsApp will display raw ** characters.\n"
            f"6. REFERRAL NAME: Address the customer as {username}.\n"
            f"7. NO BUTTON REFERENCES: Text chat messages do not have buttons. Always tell them to type *Send an Order* in this chat to open the order form.\n"
            f"8. TRANSACTION BOUNDARIES: All bookings happen when the user types *Send an Order*.\n"
            f"STYLE: Keep replies concise (2-3 sentences max), highly engaging, friendly, and spiced with icons!"
        )

        user_history = get_user_chat_memory(sender_wa_number)
        messages_payload = [{"role": "system", "content": system_prompt}]
        for turn in user_history:
            messages_payload.append(turn)
        messages_payload.append({"role": "user", "content": text_body})

        groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        models_to_try = ["groq/compound-mini", "groq/compound", "openai/gpt-oss-20b", "llama-3.1-8b-instant"]

        ai_reply = None
        for model_name in models_to_try:
            try:
                chat_completion = await groq_client.chat.completions.create(
                    messages=messages_payload,
                    model=model_name,
                    max_tokens=200,
                    timeout=5.0
                )
                ai_reply = chat_completion.choices[0].message.content.strip()
                if ai_reply:
                    break
            except Exception as inner_e:
                print(f"Groq conversational model {model_name} warning: {inner_e}")
                continue

        if ai_reply:
            # Convert standard markdown double asterisks (**) to WhatsApp single asterisks (*)
            ai_reply = ai_reply.replace("**", "*")
            add_user_chat_memory(sender_wa_number, "user", text_body)
            add_user_chat_memory(sender_wa_number, "assistant", ai_reply)
            await send_custom_message(sender_wa_number, ai_reply, auth, graph_url)
        else:
            await send_default_template(sender_wa_number, username, auth, graph_url)

    except Exception as e:
        print(f"Groq AI error: {e}")
        await send_default_template(sender_wa_number, username, auth, graph_url)
