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


async def get_active_ride(sender_wa_number: str, db: AsyncSession):
    result = await db.execute(
        select(models.Orders)
        .where(models.Orders.sender_wa_number == sender_wa_number)
        .where(models.Orders.status.in_(["confirmed"]))
        .order_by(models.Orders.created_at.desc())
    )
    return result.scalars().first()

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
    """Checks if a user is registered by matching display_phone_number, wa_id, or phone_number_id across formatted variants (+ or no +)."""
    clean_num = sender_wa_number.lstrip("+")
    plus_num = f"+{clean_num}"
    possible_numbers = list(set([sender_wa_number, clean_num, plus_num]))

    result = await db.execute(
        select(models.User).where(
            (models.User.display_phone_number.in_(possible_numbers)) |
            (models.User.wa_id.in_(possible_numbers)) |
            (models.User.phone_number_id.in_(possible_numbers))
        )
    )
    return result.scalars().first() is not None


async def handle_text_message(sender_wa_number: str, text_body: str, username: str, db: AsyncSession, auth: str, graph_url: str):
    """Handles freeform text messages using intent detection + Groq + Llama 3."""

    text_lower = text_body.lower().strip()

    # --- Query / Status Intent Check: Keep queries for Groq AI ---
    query_keywords = ["where", "status", "track", "when", "cancel", "how", "what", "why", "price", "cost", "rate", "contact", "support", "problem", "issue", "delay"]
    is_query_or_question = any(re.search(r'\b' + re.escape(kw) + r'\b', text_lower) for kw in query_keywords) or "?" in text_lower

    if not is_query_or_question:
        # --- Intent detection: user explicitly wants to place an order ---
        order_phrases = [
            "send an order", "place an order", "send order", "place order",
            "i want to send", "book a rider", "book rider", "send a package",
            "send package", "need a rider", "need rider", "new order", "create order",
            "send parcel", "dispatch parcel", "deliver package"
        ]
        # Single exact word triggers (only if the message is very short)
        exact_order_words = ["send", "order", "dispatch", "deliver", "package", "parcel"]

        is_order_intent = any(phrase in text_lower for phrase in order_phrases) or (text_lower in exact_order_words)

        if is_order_intent:
            registered = await is_user_registered(sender_wa_number, db)
            if registered:
                await reply_user_that_has_just_registered(sender_wa_number, auth, graph_url)
            else:
                await send_registration_template(sender_wa_number, auth, graph_url)
            return

        # --- Intent detection: greetings → send default template ---
        greeting_pattern = r'\b(hello|hi|hey|good morning|good afternoon|good evening|start|menu|help)\b'
        if re.search(greeting_pattern, text_lower) and len(text_lower.split()) <= 4:
            await send_default_template(sender_wa_number, username, auth, graph_url)
            return

    # --- Everything else: let Groq AI handle it with context ---
    try:
        order = await get_active_ride(sender_wa_number, db)

        if order:
            order_context = (
                f"The user has an active delivery order.\n"
                f"Order Number: {order.order_number}\n"
                f"Status: {order.status}\n"
                f"Pickup: {order.pickup_location_name or 'Not set'}\n"
                f"Dropoff: {order.dropoff_location_name or 'Not set'}\n"
                f"Package: {order.package_description or 'Not specified'}\n"
                f"Rider: {'Assigned' if order.rider_wa_number else 'Still searching for a rider'}"
            )
        else:
            order_context = "The user has no active delivery order at the moment."

        system_prompt = (
            f"You are a friendly, helpful customer support assistant for InTime, a premier dispatch and delivery service in Nigeria. "
            f"You are chatting with {username} via WhatsApp. "
            f"COMPANY KNOWLEDGE:\n"
            f"- Official Website: https://sendintime.com.ng\n"
            f"- Contact Email: contact@sendintime.com.ng (or intimesender@gmail.com)\n"
            f"- Support Phone: +234 815 103 3428\n"
            f"- Coverage: 12+ major cities across Nigeria (Lagos, Abuja, Port Harcourt, Kano, Ibadan, Benin City, Enugu, Kaduna, Onitsha, Warri, Calabar, Owerri).\n"
            f"- Service Details: InTime connects customers with verified dispatch riders to compare prices, negotiate fares, and send packages fast and safely.\n"
            f"- Ordering Flow: While users can visit sendintime.com.ng to learn more, bookings and dispatch requests are created right here in WhatsApp using interactive action buttons.\n"
            f"Current Context: {order_context}.\n"
            f"INSTRUCTIONS: Keep replies short (2-3 sentences max), warm, and plain text only — no markdown, asterisks, or bullet points. "
            f"If asked about our website, contact email, or phone number, provide the correct details above."
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

