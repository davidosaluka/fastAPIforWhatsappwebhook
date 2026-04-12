from sqlalchemy import select
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
        message = "NEW DISPATCH REQUEST! \n" + order_details
        
        await send_custom_message(sender_wa_number=rider.rider_wa_number, message=message , auth=auth, graph_url=graph_url)
    return




async def handle_location(sender_wa_number, lat, lng, auth, graph_url, db):
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
            ride.status = "awaiting_dropoff"
            await db.commit()
            await request_dropoff_location(sender_wa_number, auth, graph_url)

        case "awaiting_dropoff":
            ride.dropoff_lat = lat
            ride.dropoff_lng = lng
            ride.status = "confirmed"
            await db.commit()
            
            order_details = {
                "package_description": ride.package_description,
                "pick_up_location": ride.pickup_lat + " , " + ride.pickup_lng,
                "drop_off_location": ride.dropoff_lat + " , " + ride.dropoff_lng,
                "offered_price": ride.customer_intital_offered_price

            }
            await get_rider(sender_wa_number=sender_wa_number, auth=auth, graph_url=graph_url, order_number=ride.order_number)
  
