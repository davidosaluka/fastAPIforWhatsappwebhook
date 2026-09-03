import asyncio
from datetime import UTC, datetime
import random
import string
import time
from typing import Annotated
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, status, Request, HTTPException, Depends, APIRouter
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
import models
import json
from database import Base, engine, get_db
from schemas import apiPostRequestResponse, apiRequestCreate
import os
from dotenv import load_dotenv
import replyhandler
from sqlalchemy.exc import IntegrityError

import logging

logger = logging.getLogger(__name__)

load_dotenv()
router = APIRouter()
VERIFY_TOKEN =  os.getenv("VERIFY_TOKEN")
AUTH = os.getenv("AUTHORIZATION")
GRAPH_URL = os.getenv("GRAPH_URL")

@router.post("", status_code=status.HTTP_200_OK)
async def createAPIrequest(apirequest: apiRequestCreate, db: Annotated[AsyncSession, Depends(get_db)]):
     # Extract messages (if any) first
    _response = apirequest.entry[0]["changes"][0]["value"].get("messages")

    if not _response:
        # Not a message event (e.g. status update) — log it plainly, no dedup needed
        return {"status": "ok"}

    message = _response[0]
    wamid = message["id"]

    newAPIRequest = models.apiRequest(
        method="POST",
        content=apirequest.model_dump_json(),
        response="OK",
        status_code=200,
        wamid=wamid,
    )

    db.add(newAPIRequest)
    try:
        await db.commit()
        await db.refresh(newAPIRequest)
    except IntegrityError:
        # duplicate wamid — already processed this message before
        await db.rollback()
        return {"status": "duplicate, ignored"}
    '''newAPIRequest = models.apiRequest(
        method="POST",
        content= apirequest.model_dump_json(), #json.dumps(apirequest.entry),
        response="OK",
        status_code=200,
    )

    db.add(newAPIRequest)
    await db.commit()
    await db.refresh(newAPIRequest)
    
    _response = apirequest.entry[0]["changes"][0]["value"].get("messages") 
   # _response = apirequest.entry[0]["changes"][0]["value"]["messages"]
    if not _response:
        return {"status": "ok"}
    message = _response[0]'''

    try:
        await replyhandler.show_typing_indicator(
        message_id=wamid,
        auth=AUTH,
        graph_url=GRAPH_URL
    )
    except Exception as e:
        logger.warning(f"Failed to show typing indicator for {wamid}: {e}")

    if message["type"] == "button":
        sender_wa_number = message["from"]
        if message["button"]["payload"] == "Send an Order":
            result = await db.execute(
            select(models.User)
            .where(models.User.display_phone_number == sender_wa_number)
            )
            is_existing_user = result.scalars().first()
            if is_existing_user:
                await replyhandler.reply_user_that_has_just_registered(sender_wa_number, AUTH, GRAPH_URL)
            else:
                await replyhandler.send_registration_template(sender_wa_number, AUTH, GRAPH_URL)
        elif message["button"]["payload"] == "Contact Support":
            custom_message = "Need a hand? 🙋 Reach our support team at intimesender@gmail.com and we'll sort you out.\n\nSend any message here to restart this flow 🔄"
            await replyhandler.send_custom_message(sender_wa_number, custom_message, AUTH, GRAPH_URL)

        elif message["button"]["payload"] == "I'm Available":
            rider_phoneno = message["from"]
            await db.execute(
                update(models.Riders)
                .where(models.Riders.rider_wa_number == rider_phoneno)
                .values(availabilty_status="available")
            )
            await db.commit()
            custom_message = "You're checked in! ✅ New dispatch requests will start routing your way shortly 📦🛵💨"
            await replyhandler.send_custom_message(rider_phoneno, custom_message, AUTH, GRAPH_URL)

        
    if message["type"] == "interactive" and message["interactive"]["type"] == "nfm_reply":
        json_response = json.loads(message["interactive"]["nfm_reply"]["response_json"])
        template_id = json_response.get("template_id")  
        raw_token = json_response.get("flow_token")
        flow_token = json.loads(raw_token) if raw_token and raw_token != "unused" else {}
        order_number = flow_token.get("order_number")
        rider_wa_number = flow_token.get("rider_wa_number")
        name        = json_response.get("name")
        rider_proposed_amount = json_response.get("proposed_amount") 
        customer_fare_increase_amount = json_response.get("customer_fare_increase_amount")
        custRespToRiderOff = json_response.get("custRespToRiderOff")       
        email       = json_response.get("email")         
        status      = json_response.get("status")
        customer_intital_offered_price = json_response.get("customer_intital_offered_price")
        package_description = json_response.get("package_description")       
        sender_wa_number = message["from"] 
        rider_selected_option_for_current_ride = json_response.get("screen_0_Pick_an_Option_0")
        rider_in_pickup_location = json_response.get("screen_for_pickup_location_prompt") 
        rider_in_dropoff_location = json_response.get("screen_for_dropoff_location_prompt") 
        recipient_phone_number = json_response.get("recipient_phone_number")



        if rider_in_pickup_location and rider_in_pickup_location == "At_Pickup": 
            order_details = await db.execute(
                select(models.Orders)
                .where(models.Orders.order_number == order_number)
            )    
            order_details = order_details.scalar_one_or_none()

            sender_details = await db.execute(
                select(models.User)
                .where(models.User.display_phone_number == order_details.sender_wa_number)
            )
            sender_details = sender_details.scalar_one_or_none()

            #notify sender on arrival of rider at pickup location
            await replyhandler.send_custom_message(
                sender_wa_number=order_details.sender_wa_number, 
                message = "Your rider has arrived! 📍 Feel free to give them a call, or expect one from them any moment now 📞",
                auth=AUTH, 
                graph_url=GRAPH_URL
            )

            
            await db.execute(
            update(models.Orders)
            .where(models.Orders.order_number == order_number)
            .values(delivery_progression_status="package_picked_up")
            )
            await db.commit()
            five_digit_code = ''.join(random.choices(string.digits, k=5))
            message_for_sender = (
                f"🔐 Your delivery code: *{five_digit_code}*\n\n"
                "You don't need to do anything with this — it's just a backup copy.\n\n"
                "This same code has already been sent to the recipient and the rider. "
                "We're sharing it with you too, just in case the recipient doesn't receive theirs for any reason.\n\n"
                "Feel free to pass it along to the recipient — the rider will ask for it before handing over the package.\n\n"
                "⚠️ *DO NOT share this code with the rider* — only the recipient should provide it."
            )
            message_for_rider= (
                f"🔐 Delivery code: *{five_digit_code}*\n\n"
                "✅ Confirm this code with the recipient *before* handing over the package."
            )
            message_for_recipient = (
                f"📦 Your package from {sender_details.name} is on its way! The rider just picked it up and is heading to you now.\n\n"
                f"🔐 Delivery code: *{five_digit_code}*\n\n"
                "The rider will ask you for this code before handing over the package — keep it handy!"
            )
            await replyhandler.send_custom_message(
                sender_wa_number=order_details.sender_wa_number, 
                message=message_for_sender,
                auth=AUTH, 
                graph_url=GRAPH_URL
            )

            await replyhandler.send_custom_message(
                sender_wa_number=order_details.rider_wa_number, 
                message=message_for_rider,
                auth=AUTH, 
                graph_url=GRAPH_URL
            )
            await replyhandler.send_custom_message(
                sender_wa_number=order_details.recipient_phone_number, 
                message=message_for_recipient,
                auth=AUTH, 
                graph_url=GRAPH_URL
            )

            await replyhandler.send_custom_flow (
                wa_number=order_details.rider_wa_number,
                flow_token={"order_number": order_details.order_number},
                message="Click the button below when you have dropped off the package successfully",
                header=f"Have you delivered the package? 📬\n\n",
                flow_id="1549615230214062",
                flow_cta="Have you Delivered the Package?",
                screen_name="flow_to_ask_if_rider_has_dropped_off_package",
                auth=AUTH,
                graph_url=GRAPH_URL #modify
            )

        if rider_in_dropoff_location and rider_in_dropoff_location == "At_dropoff":
            order_details = await db.execute(
                select(models.Orders)
                .where(models.Orders.order_number == order_number)
            )    
            order_details = order_details.scalar_one_or_none()
            message_for_sender_and_recipient_and_rider = (
                "📦✅ Package delivered successfully!\n\n"
                "Thank you for choosing inTime 🙌"
            )
            await db.execute(
            update(models.Orders)
            .where(models.Orders.order_number == order_number)
            .values(delivery_progression_status="package_delivered")
            )
            await db.commit()

            await replyhandler.send_custom_message(
                sender_wa_number=order_details.sender_wa_number, 
                message=message_for_sender_and_recipient_and_rider,
                auth=AUTH, 
                graph_url=GRAPH_URL
            )

            await replyhandler.send_custom_message(
                sender_wa_number=order_details.rider_wa_number, 
                message=message_for_sender_and_recipient_and_rider,
                auth=AUTH, 
                graph_url=GRAPH_URL
            )
            await replyhandler.send_custom_message(
                sender_wa_number=order_details.recipient_phone_number, 
                message=message_for_sender_and_recipient_and_rider,
                auth=AUTH, 
                graph_url=GRAPH_URL
            )

            

        if rider_selected_option_for_current_ride:
            order_sla_details = await db.execute(
                select(models.Orders.sla_expires_by)
                .where(models.Orders.order_number == order_number)
            )    
            order_sla_details_result = order_sla_details.scalar_one_or_none()
            order_still_valid =  order_sla_details_result > datetime.now(UTC)
            if order_still_valid:
                if rider_selected_option_for_current_ride == "0_Accept":
                    await replyhandler.handle_case_where_rider_has_accepted_the_ride(sender_wa_number, order_number, AUTH, GRAPH_URL, db)
                else:
                    await replyhandler.handle_case_where_rider_is_negotiating_the_ride(sender_wa_number, order_number, AUTH, GRAPH_URL, db)
            else:
                await replyhandler.send_custom_message(sender_wa_number=sender_wa_number, message = "⏰ This dispatch request has expired — it's already been picked up by another rider. ", auth=AUTH, graph_url=GRAPH_URL)
        if rider_proposed_amount:
            await db.execute(
                update(models.Orders)
                .where(models.Orders.order_number == order_number)
                .values(final_price_agreed_by_cust_and_rider=rider_proposed_amount)
            )
            await db.commit()
            await replyhandler.message_customer_where_rider_is_negotiating_the_ride(sender_wa_number, order_number, rider_proposed_amount, AUTH, GRAPH_URL, db)

        if customer_fare_increase_amount:
            
            await db.execute(
                update(models.Orders)
                .where(models.Orders.order_number == order_number)
                .values(final_price_agreed_by_cust_and_rider=customer_fare_increase_amount)
            )
            await db.commit()

            result = await db.execute(
            select(models.Orders)
            .where(models.Orders.order_number == order_number)
            )

            result = result.scalar_one_or_none()

            order_details = {
                "package_description": result.package_description,
                "pick_up_location": result.pickup_location_name,
                "drop_off_location": result.dropoff_location_name,
                "offered_price": customer_fare_increase_amount,
                "order_number": result.order_number,
                "image_id": result.package_image_id

            }
            await replyhandler.get_rider(sender_wa_number=sender_wa_number, auth=AUTH, graph_url=GRAPH_URL, order_details=order_details, db=db)
        if custRespToRiderOff:
            if custRespToRiderOff == "acceptingRiderOffer":
                await replyhandler.handle_case_where_customer_has_accepted_the_ride(
                    sender_wa_number=sender_wa_number, 
                    rider_wa_number=rider_wa_number,
                    order_number=order_number,
                    auth=AUTH,
                    graph_url=GRAPH_URL,
                    db=db
                    )
            elif custRespToRiderOff == "rejectingRiderOffer":
                message = "❌ The customer declined your offer."
                await replyhandler.send_custom_message(sender_wa_number=rider_wa_number, message=message, auth=AUTH, graph_url=GRAPH_URL)


        match template_id:
            case "user_registration":
                
                wa_id = apirequest.entry[0]["changes"][0]["value"]["contacts"][0]["wa_id"]
                display_phone_number = sender_wa_number
                phone_number_id = apirequest.entry[0]["changes"][0]["value"]["metadata"]["phone_number_id"]
                await createUser(
                            name=name,
                            wa_id=sender_wa_number,
                            display_phone_number=sender_wa_number,
                            phone_number_id=sender_wa_number,
                            db=db
                        )


                
                await replyhandler.reply_user_that_has_just_registered(sender_wa_number, AUTH, GRAPH_URL)
        
            case "order_details":

                await db.execute(
                update(models.Orders)
                .where(models.Orders.sender_wa_number == sender_wa_number)
                .where(models.Orders.status.in_(["confirmed"]))
                .values(status="cancelled")
                )
                await db.commit()

                newOrder = models.Orders(
                status="confirmed",
                sender_wa_number= sender_wa_number,
                customer_intital_offered_price=customer_intital_offered_price,
                final_price_agreed_by_cust_and_rider=customer_intital_offered_price,
                package_description=package_description,
                recipient_phone_number=recipient_phone_number,
                pickup_location_name=(
                    f"{json_response.get('pickup_HouseFlat_Number_0')},"
                    f"{json_response.get('pickup_Street_Name_1')}, "
                    f"{json_response.get('pickup_City_2')}, "
                    f"{json_response.get('pickup_State_3')}, "
                ),
                dropoff_location_name=(
                    f"{json_response.get('dropoff_HouseFlat_Number_0')}, "
                    f"{json_response.get('dropoff_Street_Name_1')}, "
                    f"{json_response.get('dropoff_City_2')}, "
                    f"{json_response.get('dropoff_State_3')}, "
                ),
                )

                db.add(newOrder)
                await db.commit()
                await db.refresh(newOrder)
                await replyhandler.send_custom_message(sender_wa_number, "📸 Please take and upload a photo of the package you're sending.", AUTH, GRAPH_URL)


            case _:
                print(f"Unknown template_id: {template_id}")

    # elif message["type"] == "location":
    #     lat = message["location"]["latitude"]
    #     lng = message["location"]["longitude"]
    #     address = message["location"]["address"]
    #     sender_wa_number = message["from"]
    #     await replyhandler.handle_location(sender_wa_number, lat, lng, address, AUTH, GRAPH_URL, db)

    elif message["type"] == "text":
        sender_wa_number = message["from"]
        username = apirequest.entry[0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]
        await replyhandler.send_default_template (sender_wa_number, username, AUTH, GRAPH_URL)

    elif message ["type"] == "image":
        sender_wa_number = message["from"]

        result = await db.execute(
        select(models.Orders)
        .where(models.Orders.sender_wa_number == sender_wa_number)
        .where(models.Orders.customer_intital_offered_price.is_not(None))
        .where(models.Orders.package_image_id.is_(None))
        .where(models.Orders.sla_expires_by > datetime.now(UTC))
        .order_by(models.Orders.created_at.desc())
        )
        result = result.scalar_one_or_none()

        if result:
            await db.execute(
                    update(models.Orders)
                    .where(models.Orders.sender_wa_number == sender_wa_number)
                    .where(models.Orders.status.in_(["confirmed"]))
                    .values(package_image_id=message["image"]["id"])
                    )
            await db.commit()
            ride = await replyhandler.get_active_ride(sender_wa_number, db)
            order_details = {
                    "package_description": ride.package_description,
                    "pick_up_location": ride.pickup_location_name,
                    "drop_off_location": ride.dropoff_location_name,
                    "offered_price": ride.customer_intital_offered_price,
                    "order_number": ride.order_number,
                    "image_id": ride.package_image_id
                }
            await replyhandler.get_rider(sender_wa_number=sender_wa_number, auth=AUTH, graph_url=GRAPH_URL, order_details=order_details, db=db)
        else:
            await replyhandler.send_something_went_wrong_template(sender_wa_number=sender_wa_number, auth=AUTH, graph_url=GRAPH_URL)
    '''try:
        name = apirequest.entry[0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]
        wa_id = apirequest.entry[0]["changes"][0]["value"]["contacts"][0]["wa_id"]
        display_phone_number = apirequest.entry[0]["changes"][0]["value"]["metadata"]["display_phone_number"]
        phone_number_id = apirequest.entry[0]["changes"][0]["value"]["metadata"]["phone_number_id"]
    except (KeyError, IndexError):
        raise HTTPException(status_code=400, detail="Unexpected payload structure")

    await createUser(
        name=name,
        wa_id=wa_id,
        display_phone_number=display_phone_number,
        phone_number_id=phone_number_id,
        db=db
    )'''

    return {"status": "created"}


async def createUser(name, wa_id, display_phone_number, phone_number_id, db: AsyncSession):

    result = await db.execute(
        select(models.User).where((models.User.phone_number_id == phone_number_id) | (models.User.wa_id == wa_id) | (models.User.display_phone_number == display_phone_number))
    )
    existing_user = result.scalars().first()
    if existing_user:
        return
    new_user = models.User(
        name=name,
        wa_id=wa_id,
        display_phone_number=display_phone_number,
        phone_number_id=phone_number_id
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return ({"status": status.HTTP_201_CREATED, "message": "User Created Successfully"})




@router.get("", status_code=status.HTTP_200_OK)
def validateWhatsAPPGetRequest(
    hub_mode: str = Query(alias="hub.mode"),
    hub_challenge: str = Query(alias="hub.challenge"),
    hub_verify_token: str = Query(alias="hub.verify_token")
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge, status_code=200)
    
    raise HTTPException(status_code=403, detail="Verification failed")



