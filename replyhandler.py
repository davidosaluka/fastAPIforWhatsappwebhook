import asyncio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import json
import requests
import models
import httpx



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

#rider daily checkin template
async def send_daily_rider_checkin_template(rider_wa_number, auth, graph_url):
    
    req_body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": rider_wa_number,
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
    
    print(req_body)
    async with httpx.AsyncClient() as client:
        response = await client.post(graph_url, json=req_body, headers=headers)
        print(response.status_code, response.text)
    return

#end rider daily checkin


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
    return result.scalar_one_or_none()

async def get_rider(sender_wa_number, auth, graph_url, order_details, db:AsyncSession):
    message = f"Your order number is:\n{order_details['order_number']}.\n\nI am now searching for available Riders for you, please hold"
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
    return




async def handle_case_where_rider_has_accepted_the_ride(sender_wa_number, order_number, AUTH, GRAPH_URL, db:AsyncSession):
    order_result = await db.execute(
    select(models.Orders)
    .where(models.Orders.order_number == order_number)
    )
    order = order_result.scalar_one_or_none()
    order_status = order.status

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
        recipient_message = (
            f"Hello, A dispatch request is on its way to you!"
            f"ORDER DESCRIPTION 📦: {order.package_description}\n\n"
            f"PICKUP LOCATION📍: {order.pickup_location_name}\n\n"
            f"DROPOFF LOCATION📍: {order.dropoff_location_name}\n\n"
            f"ORDER NUMBER: {order.order_number}\n\n"
            f"RIDER'S NAME: {rider_details.first_name} {rider_details.last_name}\n\n"
            f"RIDER'S PHONE NUMBER: {rider_details.rider_wa_number}"
        )
        recipient_wa_number = order.recipient_phone_number
        
        #sending a message to the rider
        await send_custom_message(sender_wa_number=sender_wa_number, message=rider_message, auth=AUTH, graph_url=GRAPH_URL)         
        
        #sending a message to the customer
        await send_custom_message(sender_wa_number=customer_wa_number, message=customer_message, auth=AUTH, graph_url=GRAPH_URL) 

        print("sending message to receiver for line 453")
        await send_custom_message(sender_wa_number=recipient_wa_number, message=recipient_message, auth=AUTH, graph_url=GRAPH_URL)
        print("sending message to receiver for line 453 was successful")
        #await send_details_to_recipients(sender_wa_number=recipient_wa_number, message=recipient_message, auth=AUTH, graph_url=GRAPH_URL)
        

        await db.execute(
           update(models.Orders)
           .where(models.Orders.order_number == order_number)
           .values(status="rider_accepted", rider_wa_number=sender_wa_number, final_price_agreed_by_cust_and_rider=order.final_price_agreed_by_cust_and_rider)
        )
        await db.commit()

        await asyncio.sleep(300)


        await send_custom_flow(
            wa_number=rider_details.rider_wa_number,
            flow_token={"order_number": order.order_number},
            message="Click the button below when you have picked up the package to be delivered",
            header=f"Have you picked up the package?\n\n",
            flow_id="1521319786323152",
            flow_cta="Picked Up Package?",
            screen_name="flow_to_ask_if_rider_has_picked_up_package",
            auth=AUTH,
            graph_url=GRAPH_URL
        )


    else:
        rider_message = f"Sorry! you responded late and this order has already been picked up by another rider"
        await send_custom_message(sender_wa_number=sender_wa_number, message=rider_message, auth=AUTH, graph_url=GRAPH_URL)   


async def handle_case_where_rider_is_negotiating_the_ride(sender_wa_number, order_number, AUTH, GRAPH_URL, db:AsyncSession):
    message = (
        "Kindly click the button below to input your counter offer: "
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

    order = order_result.scalar_one_or_none()

    rider_result = await db.execute(
        select(models.Riders)
        .where(models.Riders.rider_wa_number == sender_wa_number)
    )

    rider_details = rider_result.scalar_one_or_none()

    if order and order.status == "confirmed":
        customer_wa_number = await db.execute(
            select(models.Orders.sender_wa_number)
            .where(models.Orders.order_number == order_number)
        )
        customer_wa_number = customer_wa_number.scalar_one_or_none()

        customer_message = (
            f"Rider's Name: {rider_details.first_name} {rider_details.last_name}\n\n"
            f"Rider's offered price: {rider_proposed_amount}\n\n"
            f"Order Number: {order.order_number}\n\n" 
            f"Rider's rating: 4.5 stars"
            )
        
        asking_customer_to_increase_price_msg = (
            f"If you do not agree to any of the prices above," 
            f"you can increase your fare price by clicking of the button below"
            "and other riders would be searched for"
        )
        
        
        
        #sending a message to the customer about the riders offering the prices
        await send_custom_flow(
            wa_number=customer_wa_number,
            flow_token={"order_number": order_number, "rider_wa_number": sender_wa_number},
            message=customer_message,
            header="This rider is offering these prices instead\n\n",
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





async def handle_case_where_customer_has_accepted_the_ride(sender_wa_number, rider_wa_number, order_number, auth, graph_url, db:AsyncSession):
    order_result = await db.execute(
    select(models.Orders)
    .where(models.Orders.order_number == order_number)
    )
    order = order_result.scalar_one_or_none()
    order_status = order.status

    print(f"riders number is: {rider_wa_number}")
    rider_details = await db.execute(
    select(models.Riders)
    .where(models.Riders.rider_wa_number == rider_wa_number)
        )
    rider_details = rider_details.scalar_one_or_none()

    if order_status == "confirmed":
        customer_wa_number = sender_wa_number

        rider_message = f"You can communicate with the customer on this number: {customer_wa_number}. Please proceed to the pickup location"
        customer_message = (
            f"Ride has been accepted. Rider is proceeding to your pickup location and would be in contact with you shortly\n\n"
            f"Rider's Name: {rider_details.first_name} {rider_details.last_name}\n\n"
            f"Rider's phone number: {rider_details.rider_wa_number}"
            )

        recipient_message = (
            f"Hello, A dispatch request is on its way to you!"
            f"ORDER DESCRIPTION 📦: {order.package_description}\n\n"
            f"PICKUP LOCATION📍: {order.pickup_location_name}\n\n"
            f"DROPOFF LOCATION📍: {order.dropoff_location_name}\n\n"
            f"ORDER NUMBER: {order.order_number}\n\n"
            f"RIDER'S NAME: {rider_details.first_name} {rider_details.last_name}\n\n"
            f"RIDER'S PHONE NUMBER: {rider_details.rider_wa_number}"
        )
        recipient_wa_number = order.recipient_phone_number
        #sending a message to the rider
        await send_custom_message(sender_wa_number=rider_wa_number, message=rider_message, auth=auth, graph_url=graph_url)         
        
        #sending a message to the customer
        await send_custom_message(sender_wa_number=customer_wa_number, message=customer_message, auth=auth, graph_url=graph_url) 

        print("sending message to receiver for line 619")
        await send_custom_message(sender_wa_number=recipient_wa_number, message=recipient_message, auth=auth, graph_url=graph_url)
        print("sending message to receiver for line 619 was successful")
        
        await db.execute(
           update(models.Orders)
           .where(models.Orders.order_number == order_number)
           .values(status="rider_accepted", rider_wa_number=rider_wa_number)
            
        )
        await db.commit()

        await asyncio.sleep(300)


        await send_custom_flow(
            wa_number=rider_wa_number,
            flow_token={"order_number": order.order_number},
            message="Click the button below when you have picked up the package to be delivered",
            header=f"Have you picked up the package?\n\n",
            flow_id="1521319786323152",
            flow_cta="Picked Up Package?",
            screen_name="flow_to_ask_if_rider_has_picked_up_package",
            auth=auth,
            graph_url=graph_url #modify
        )



    else:
        rider_message = f"Sorry! this order has already been picked up by another rider"
        cust_message = f"Sorry! this order has already been picked up by another rider and the details has been sent to you"
        await send_custom_message(sender_wa_number=rider_wa_number, message=rider_message, auth=auth, graph_url=graph_url)   
        await send_custom_message(sender_wa_number=customer_wa_number, message=cust_message, auth=auth, graph_url=graph_url)   

        

