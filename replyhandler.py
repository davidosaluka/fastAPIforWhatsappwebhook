from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import json
import requests
import models
import httpx



async def send_default_template(sender_wa_number, auth, graph_url):
    
    req_body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": sender_wa_number,
            "type": "template",
            "template": {
                "name": "default_message",
                "language": { "code": "en" }
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
      "text": "Please select your PICK-UP location "
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

async def request_dropoff_location (sender_wa_number, auth, graph_url):
    req_body = {
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "type": "interactive",
  "to": sender_wa_number,
  "interactive": {
    "type": "location_request_message",
    "body": {
      "text": "Please select your DROP-OFF location "
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


async def get_active_ride(sender_wa_number: str, db: AsyncSession):
    result = await db.execute(
        select(models.Orders)
        .where(models.Orders.sender_wa_number == sender_wa_number)
        .where(models.Orders.status.in_(["awaiting_pickup", "awaiting_dropoff"]))
        .order_by(models.Orders.created_at.desc())
    )
    return result.scalar_one_or_none()

async def get_rider(sender_wa_number, auth, graph_url, order_details, db:AsyncSession):
    message = "Getting Riders for you, please hold"
    await send_custom_message(sender_wa_number, message , auth, graph_url)
    riders = await db.execute(
        select(models.Riders)
        .where(models.Riders.availabilty_status == "available")
    )
    riders = riders.scalars().all()
    for rider in riders:
        message = (
            
            f"ORDER DESCRIPTION 📦: {order_details['package_description']}\n\n"
            f"PICKUP LOCATION📍: {order_details['pick_up_location']}\n\n"
            f"DROPOFF LOCATION📍: {order_details['drop_off_location']}\n\n"
            f"OFFERED PRICE💵: {order_details['offered_price']}\n\n"
        )


        req_body={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": rider.rider_wa_number,
            "type": "interactive",
            "interactive": {
                "type": "flow",
                "header": { "type": "text", "text": f"NEW DISPATCH REQUEST!\n" },
                "body": { "text": message },
                "action": {
                "name": "flow",
                "parameters": {
                    "flow_message_version": "3",
                    "flow_token": f"order_id={order_details['order_id']}", 
                    "flow_id": "1513067607105184",
                    "flow_cta": "Accept or Negotiate",
                    "flow_action": "navigate",
                    "flow_action_payload": {
                    "screen": "RECOMMEND"
                    }
                }
                }
            }
        }
        headers = {
        "Authorization": f"Bearer {auth}",
        "Content-Type": "application/json"

         }
      
    async with httpx.AsyncClient() as client:
        response = await client.post(graph_url, json=req_body, headers=headers)
        print("rider message sent")
        print(response.status_code, response.text)
        #print(response.text[0]["messages"][0]["id"])
    
        
        #await send_custom_message(sender_wa_number=rider.rider_wa_number, message=message , auth=auth, graph_url=graph_url)
    return




async def handle_location(sender_wa_number, lat, lng, address, auth, graph_url, db):
    ride = await get_active_ride(sender_wa_number, db)
    
    if not ride:
        # no active ride, something went wrong
        message = "Something went wrong, please start again."
        await send_custom_message(sender_wa_number, message , auth, graph_url)
        return

    match ride.status:
        case "awaiting_pickup":
            ride.pickup_lat = lat
            ride.pickup_lng = lng
            ride.pickup_location_name = address
            ride.status = "awaiting_dropoff"
            await db.commit()
            await request_dropoff_location(sender_wa_number, auth, graph_url)

        case "awaiting_dropoff":
            ride.dropoff_lat = lat
            ride.dropoff_lng = lng
            ride.dropoff_location_name = address
            ride.status = "confirmed"
            await db.commit()
            
            order_details = {
                "package_description": ride.package_description,
                "pick_up_location": ride.pickup_location_name,
                "drop_off_location": ride.dropoff_location_name,
                "offered_price": ride.customer_intital_offered_price,
                "order_id": ride.order_number

            }
            print("order_details is: ")
            print(order_details)
            await get_rider(sender_wa_number=sender_wa_number, auth=auth, graph_url=graph_url, order_details=order_details, db=db)


async def handle_case_where_rider_has_accepted_the_ride(sender_wa_number, order_number, AUTH, GRAPH_URL, db:AsyncSession):
    order_status = await db.execute(
    select(models.Orders.status)
    .where(models.Orders.order_number == order_number)
    )
    order_status = order_status.scalar_one_or_none()

    rider_details = await db.execute(
    select(models.Riders)
    .where(models.Riders.rider_wa_number == sender_wa_number)
        )
    rider_details = rider_details.scalar_one_or_none()

    if order_status == "confirmed":
        customer_wa_number = await db.execute(
            select(models.Orders.sender_wa_number)
            .where(models.Orders.order_number == order_number)
        )
        customer_wa_number = customer_wa_number.scalar_one_or_none()
        rider_message = f"You can communicate with the customer on this number: {customer_wa_number}. Please proceed to the pickup location"
        customer_message = (
            f"Ride has been accepted. Rider is proceeding to your pickup location and would be in contact with you shortly\n\n"
            f"Rider's Name: {rider_details.first_name} {rider_details.last_name}\n\n"
            f"Rider's phone number: {rider_details.rider_wa_number}"
            )
        
        #sending a message to the rider
        await send_custom_message(sender_wa_number=sender_wa_number, message=rider_message, auth=AUTH, graph_url=GRAPH_URL)         
        
        #sending a message to the customer
        await send_custom_message(sender_wa_number=customer_wa_number, message=customer_message, auth=AUTH, graph_url=GRAPH_URL) 
        
        await db.execute(
           update(models.Orders)
           .where(models.Orders.order_number == order_number)
           .values(status="rider_accepted")
        )
        await db.commit()


    else:
        rider_message = f"Sorry! you responded late and this order has already been picked up by another rider"
        await send_custom_message(sender_wa_number=sender_wa_number, message=rider_message, auth=AUTH, graph_url=GRAPH_URL)   


async def handle_case_where_rider_is_negotiating_the_ride(sender_wa_number, order_number, AUTH, GRAPH_URL, db):
    pass
        

