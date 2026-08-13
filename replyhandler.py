import asyncio
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


async def send_custom_message(sender_wa_number, message , auth, graph_url):

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
        print("custom message sent")
        print(response.status_code, response.text)
        #print(response.text[0]["messages"][0]["id"])
    return

async def send_image(sender_wa_number, auth, graph_url, image_id):
    req_body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": sender_wa_number,
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




async def send_custom_flow(wa_number, flow_token, message,header, flow_id, flow_cta, screen_name, auth, graph_url):
    req_body={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": wa_number,
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
    Generates all equivalent representations of a phone number (e.g. 081..., 23481..., +23481..., 81...).
    """
    if not phone:
        return []
    canonical = normalize_phone_number(phone)
    if len(canonical) == 13 and canonical.startswith("234"):
        local_fmt = "0" + canonical[3:]
        plus_fmt = "+" + canonical
        raw_fmt = canonical[3:]
        return list(set([phone, canonical, local_fmt, plus_fmt, raw_fmt]))
    return [phone]


async def get_active_ride(sender_wa_number: str, db: AsyncSession):
    possible_numbers = get_phone_variants(sender_wa_number)
    result = await db.execute(
        select(models.Orders)
        .where(models.Orders.sender_wa_number.in_(possible_numbers))
        .where(models.Orders.status.in_(["confirmed"]))
        .where(models.Orders.sla_expires_by > datetime.now(UTC))
        .order_by(models.Orders.created_at.desc())
    )
    return result.scalars().first()

async def update_rider_offer_status(rider_wa_number: str, status_val: str, db: AsyncSession):
    """Updates status in RiderOffer table for rider receipts (delivered, read)."""
    clean_num = rider_wa_number.lstrip("+")
    plus_num = f"+{clean_num}"
    possible_numbers = list(set([rider_wa_number, clean_num, plus_num]))

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


async def schedule_order_followups(order_number: str, sender_wa_number: str, auth: str, graph_url: str):
    """
    State-aware background task that monitors order search progress.
    Re-queries DB before every alert. Suppresses follow-up if order is no longer searching (confirmed).
    """
    # Follow-up 1: 3 minutes (180 seconds)
    await asyncio.sleep(180)

    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        order = await get_active_ride_by_number(order_number, db)
        if not order or order.status != "confirmed":
            return  # Stop immediately if rider accepted, cancelled, or completed!

        offers_res = await db.execute(
            select(models.RiderOffer).where(models.RiderOffer.order_number == order_number)
        )
        offers = offers_res.scalars().all()
        read_count = sum(1 for o in offers if o.status in ["read", "viewed"])

        if read_count > 0:
            msg = f"Good news 👀 {read_count} rider{'s' if read_count > 1 else ''} have viewed your delivery offer. We're waiting for one to accept."
        else:
            msg = "Stay locked in 👀 We're still looking for a rider for your package. We'll update you as soon as one accepts."
        
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


async def get_rider(sender_wa_number, auth, graph_url, order_details, db:AsyncSession):
    message = f"✅ Your order has been placed!\n\nOrder Number: *{order_details['order_number']}*\n\n🔍 Searching for available riders nearby, please hold on..."
    await send_custom_message(sender_wa_number, message , auth, graph_url)
    riders = await db.execute(
        select(models.Riders)
        .where(models.Riders.availability_status == "available")
        .where(models.Riders.rider_wa_number != sender_wa_number)  # exclude sender if they're also a rider
    )
    riders = riders.scalars().all()
    
    for rider in riders:
        message = (
            f"ORDER DESCRIPTION 📦: {order_details['package_description']}\n\n"
            f"PICKUP LOCATION📍: {order_details['pick_up_location']}\n\n"
            f"DROPOFF LOCATION📍: {order_details['drop_off_location']}\n\n"
            f"OFFERED PRICE💵: {order_details['offered_price']}\n\n"
            f"ORDER NUMBER: {order_details['order_number']}\n\n"
        )
        print("message is: ")
        print(message)

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
            header=f"DISPATCH REQUEST!\n",
            flow_id="1513067607105184",
            flow_cta="Accept or Negotiate",
            screen_name="RECOMMEND",
            auth=auth,
            graph_url=graph_url
        )
        if order_details.get('image_id'):
            await send_image(rider.rider_wa_number, auth, graph_url, order_details['image_id'])

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
        rider_message = f"🎉 Ride accepted! The customer's number is *{customer_wa_number}*. Please head to the pickup location now. Safe riding! 🏍️"
        customer_message = (
            f"🎉 Great news! Your ride has been accepted.\n\n"
            f"Your rider is on the way to the pickup location and will contact you shortly.\n\n"
            f"🧑‍✈️ Rider's Name: *{rider_name}*\n"
            f"📞 Phone: *{rider_phone}*"
            )
        recipient_message = (
            f"👋 Hello! A package is on its way to you.\n\n"
            f"📦 Description: {order.package_description}\n\n"
            f"📍 Pickup: {order.pickup_location_name}\n\n"
            f"🏁 Dropoff: {order.dropoff_location_name}\n\n"
            f"🔖 Order No: {order.order_number}\n\n"
            f"🧑‍✈️ Rider: {rider_details.first_name} {rider_details.last_name}\n"
            f"📞 Rider's Phone: {rider_details.rider_wa_number}"
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

        asyncio.create_task(_delayed_send_pickup_flow(
            wa_number=rider_details.rider_wa_number,
            order_number=order.order_number,
            auth=AUTH,
            graph_url=GRAPH_URL
        ))

    else:
        rider_message = f"⏰ Sorry, you responded a bit late — this order has already been assigned to another rider."
        await send_custom_message(sender_wa_number=sender_wa_number, message=rider_message, auth=AUTH, graph_url=GRAPH_URL)   


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

        rider_message = f"🎉 Ride confirmed! The customer's number is *{customer_wa_number}*. Please head to the pickup location now. Safe riding! 🏍️"
        customer_message = (
            f"🎉 Your ride is confirmed!\n\n"
            f"Your rider is heading to the pickup location and will be in touch shortly.\n\n"
            f"🧑‍✈️ Rider's Name: *{rider_name}*\n"
            f"📞 Phone: *{rider_phone}*"
            )

        recipient_message = (
            f"👋 Hello! A package is on its way to you.\n\n"
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

        asyncio.create_task(_delayed_send_pickup_flow(
            wa_number=rider_wa_number,
            order_number=order.order_number,
            auth=auth,
            graph_url=graph_url
        ))



    else:
        rider_message = f"⏰ Sorry, this order has already been assigned to another rider."
        cust_message = f"✅ Your package is already on the way! The rider's details have been sent to you."
        await send_custom_message(sender_wa_number=rider_wa_number, message=rider_message, auth=auth, graph_url=graph_url)   
        await send_custom_message(sender_wa_number=customer_wa_number, message=cust_message, auth=auth, graph_url=graph_url)   

        

async def is_user_registered(sender_wa_number: str, db: AsyncSession) -> bool:
    """Checks if a user is registered by matching display_phone_number, wa_id, or phone_number_id across formatted variants."""
    possible_numbers = get_phone_variants(sender_wa_number)

    result = await db.execute(
        select(models.User).where(
            (models.User.display_phone_number.in_(possible_numbers)) |
            (models.User.wa_id.in_(possible_numbers)) |
            (models.User.phone_number_id.in_(possible_numbers))
        )
    )
    return result.scalars().first() is not None


async def handle_text_message(sender_wa_number: str, text_body: str, username: str, db: AsyncSession, auth: str, graph_url: str):
    """Deterministic routing for incoming freeform text messages."""
    text_lower = text_body.lower().strip()

    # --- 0. ACTIVE WORKFLOW STATE CHECK ---
    active_order = await get_active_ride(sender_wa_number, db)
    if active_order and active_order.package_image_id is None:
        msg = (
            f"📸 *Package Photo Needed*\n\n"
            f"Your order *{active_order.order_number}* has been initialized.\n"
            f"Please snap and send a photo of the package to complete your dispatch request and alert nearby riders!"
        )
        await send_custom_message(sender_wa_number, msg, auth, graph_url)
        return

    # --- 1. TRACKING INTENT ---
    tracking_patterns = [
        "track my order", "track order", "order status", "where is my order",
        "where is my package", "where's my order", "status of my order",
        "check my order", "check order status", "track package"
    ]
    if any(p in text_lower for p in tracking_patterns) or text_lower == "track":
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

    # --- 2. CANCEL ORDER INTENT ---
    cancellation_patterns = [
        "cancel my order", "cancel order", "cancel delivery", "cancel ride"
    ]
    if any(p in text_lower for p in cancellation_patterns) or text_lower == "cancel":
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

    # --- 3. CREATE ORDER INTENT (HIGH PRIORITY) ---
    order_phrases = [
        "send an order", "place an order", "send order", "place order",
        "i want to send", "book a rider", "book rider", "send a package",
        "send package", "need a rider", "need rider", "new order", "create order",
        "send parcel", "dispatch parcel", "deliver package", "how do i send",
        "how to send", "how do i book", "how to book", "how can i send",
        "how do i place", "want to send a package", "i need to send",
        "i want to deliver", "i need to deliver", "i want to dispatch",
        "i need a dispatch", "how do i make a delivery", "how can i make a delivery",
        "make a delivery", "make delivery", "create an order", "deliver a package",
        "deliver something", "send something", "dispatch a package", "dispatch something",
        "get a rider", "want a rider"
    ]
    exact_order_words = ["send", "order", "dispatch", "deliver", "package", "parcel"]

    is_order_intent = any(phrase in text_lower for phrase in order_phrases) or (text_lower in exact_order_words)

    if is_order_intent:
        registered = await is_user_registered(sender_wa_number, db)
        if registered:
            await reply_user_that_has_just_registered(sender_wa_number, auth, graph_url)
        else:
            await send_registration_template(sender_wa_number, auth, graph_url)
        return

    # --- 4. PLAIN-TEXT ADDRESS / ORDER DATA IN CHAT ---
    address_patterns = [
        r'\bfrom\s+.+\sto\s+.+',
        r'\bpickup\s*:\s*.+\s*dropoff\s*:\s*.+',
        r'\bdeliver\s+to\s+.+',
        r'\btake\s+.+\sto\s+.+'
    ]
    is_plain_text_address = any(re.search(pat, text_lower) for pat in address_patterns)

    if is_plain_text_address:
        registered = await is_user_registered(sender_wa_number, db)
        await send_custom_message(
            sender_wa_number,
            "To process your delivery securely and accurately, please use the Order Details button below to enter your pickup and dropoff details.",
            auth,
            graph_url
        )
        if registered:
            await reply_user_that_has_just_registered(sender_wa_number, auth, graph_url)
        else:
            await send_registration_template(sender_wa_number, auth, graph_url)
        return

    # --- 5. GREETINGS ---
    greeting_pattern = r'^\s*(hello|hi|hey|good morning|good afternoon|good evening|start|menu|help)\s*$'
    if re.search(greeting_pattern, text_lower):
        await send_default_template(sender_wa_number, username, auth, graph_url)
        return

    # --- 6. GENERAL ASSISTANCE (Groq AI with Strict System Prompt Boundaries) ---
    try:
        order = await get_active_ride(sender_wa_number, db)
        if order:
            order_context = (
                f"Active order: {order.order_number} (Status: {order.status})."
            )
        else:
            order_context = "No active delivery order."

        system_prompt = (
            f"You are the friendly, helpful customer support assistant for InTime, a premier dispatch and delivery service in Nigeria.\n"
            f"Customer Name: {username}.\n"
            f"Current Context: {order_context}.\n"
            f"COMPANY KNOWLEDGE:\n"
            f"- Official Website: https://sendintime.com.ng\n"
            f"- Contact Email: contact@sendintime.com.ng (or intimesender@gmail.com)\n"
            f"- Support Phone: +234 815 103 3428\n"
            f"- Coverage: 12+ major cities across Nigeria (Lagos, Abuja, Port Harcourt, Kano, Ibadan, Benin City, Enugu, Kaduna, Onitsha, Warri, Calabar, Owerri).\n"
            f"- Services: InTime connects customers with verified dispatch riders to compare prices, negotiate fares, and send packages fast and safely.\n\n"
            f"STRICT TRANSACTIONAL BOUNDARIES:\n"
            f"1. You DO NOT create, modify, cancel, or confirm delivery orders.\n"
            f"2. You DO NOT collect pickup addresses, dropoff addresses, prices, or package details in text chat.\n"
            f"3. You DO NOT invent order numbers, order statuses, rider details, or transaction confirmations.\n"
            f"4. All delivery bookings MUST be created using the interactive WhatsApp buttons ('Send an Order' / 'Order Details').\n"
            f"5. If the user asks how to send a package, book a rider, or place an order, tell them to tap the 'Send an Order' or 'Order Details' button in WhatsApp.\n"
            f"INSTRUCTIONS: Keep replies short (2-3 sentences max), warm, and plain text only — no markdown formatting, no asterisks, no bullet points."
        )

        groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

        chat_completion = await groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text_body}
            ],
            model="llama-3.1-8b-instant",
            max_tokens=200,
            timeout=5.0
        )

        ai_reply = chat_completion.choices[0].message.content.strip()
        await send_custom_message(sender_wa_number, ai_reply, auth, graph_url)

    except Exception as e:
        print(f"Groq AI error: {e}")
        await send_default_template(sender_wa_number, username, auth, graph_url)

