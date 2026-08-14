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

load_dotenv()
router = APIRouter()
VERIFY_TOKEN =  os.getenv("VERIFY_TOKEN")
AUTH = os.getenv("AUTHORIZATION")
GRAPH_URL = os.getenv("GRAPH_URL")

@router.post("", status_code=status.HTTP_200_OK)
async def createAPIrequest(apirequest: apiRequestCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        entry = apirequest.entry[0] if apirequest.entry else {}
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})

        statuses = value.get("statuses")
        if statuses and isinstance(statuses, list):
            status_item = statuses[0]
            recipient_id = status_item.get("recipient_id")
            status_val = status_item.get("status")
            if recipient_id and status_val:
                await replyhandler.update_rider_offer_status(recipient_id, status_val, db)

        _response = value.get("messages")
    except (IndexError, AttributeError, KeyError):
        _response = None

    if not _response:
        return {"status": "ok"}

    message = _response[0]
    wamid = message.get("id")

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

    if message["type"] == "button":
        sender_wa_number = message["from"]
        if message["button"]["payload"] == "Send an Order":
            is_existing_user = await replyhandler.is_user_registered(sender_wa_number, db)
            if is_existing_user:
                await replyhandler.reply_user_that_has_just_registered(sender_wa_number, AUTH, GRAPH_URL)
            else:
                await replyhandler.send_registration_template(sender_wa_number, AUTH, GRAPH_URL)
        elif message["button"]["payload"] == "Contact Support":
            custom_message = "Please contact support throught this email: intimesender@gmail.com \n Send any message to restart this flow"
            await replyhandler.send_custom_message(sender_wa_number, custom_message, AUTH, GRAPH_URL)
        
    if message["type"] == "interactive" and message["interactive"]["type"] == "nfm_reply":
        nfm_reply = message["interactive"]["nfm_reply"]
        raw_response = nfm_reply.get("response_json", "{}")
        json_response = json.loads(raw_response) if isinstance(raw_response, str) else (raw_response if isinstance(raw_response, dict) else {})
        
        template_id = json_response.get("template_id")  
        raw_token = nfm_reply.get("flow_token") or json_response.get("flow_token")
        flow_token = json.loads(raw_token) if raw_token and raw_token != "unused" and isinstance(raw_token, str) else (raw_token if isinstance(raw_token, dict) else {})
        order_number = flow_token.get("order_number")
        rider_wa_number = flow_token.get("rider_wa_number")
        
        name        = json_response.get("name") or json_response.get("user_name")
        rider_proposed_amount = json_response.get("proposed_amount") or json_response.get("rider_proposed_amount")
        customer_fare_increase_amount = json_response.get("customer_fare_increase_amount")
        custRespToRiderOff = json_response.get("custRespToRiderOff")       
        email       = json_response.get("email")         
        status      = json_response.get("status")
        
        raw_price = json_response.get("customer_intital_offered_price") or json_response.get("customer_initial_offered_price") or json_response.get("offered_price") or json_response.get("price")
        raw_desc = json_response.get("package_description") or json_response.get("description")
        raw_recipient = json_response.get("recipient_phone_number") or json_response.get("recipient_phone") or json_response.get("recipient_phone_number_0")
        
        sender_wa_number = message["from"] 
        rider_selected_option_for_current_ride = json_response.get("screen_0_Pick_an_Option_0")
        rider_in_pickup_location = json_response.get("screen_for_pickup_location_prompt") 
        rider_in_dropoff_location = json_response.get("screen_for_dropoff_location_prompt") 

        if not template_id or template_id not in ["order_details", "other_details", "user_registration", "w"]:
            if raw_price or raw_desc or raw_recipient or json_response.get("pickup_HouseFlat_Number_0") or json_response.get("pickup_address"):
                template_id = "order_details"
            elif name or email:
                template_id = "user_registration"

        customer_initial_offered_price = str(raw_price) if raw_price is not None else "0"
        package_description = str(raw_desc) if raw_desc is not None else "Package"
        recipient_phone_number = str(raw_recipient) if raw_recipient is not None else sender_wa_number



        if rider_in_pickup_location and rider_in_pickup_location == "At_Pickup": 
            order_details = await db.execute(
                select(models.Orders)
                .where(models.Orders.order_number == order_number)
            )    
            order_details = order_details.scalar_one_or_none()

            #notify sender on arrival of rider at pickup location
            await replyhandler.send_custom_message(
                sender_wa_number=order_details.sender_wa_number, 
                message="Rider has gotten to your location. You can call the rider or expect a call from then any moment from now" , 
                auth=AUTH, 
                graph_url=GRAPH_URL
            )

            
            await db.execute(
            update(models.Orders)
            .where(models.Orders.order_number == order_number)
            .values(delivery_progression_status="package_picked_up")
            )
            await db.commit()

            asyncio.create_task(_delayed_pickup_arrival_notifications(
                sender_wa=order_details.sender_wa_number,
                rider_wa=order_details.rider_wa_number,
                recipient_phone=order_details.recipient_phone_number,
                order_num=order_details.order_number,
                auth=AUTH,
                graph_url=GRAPH_URL
            ))

        if rider_in_dropoff_location and rider_in_dropoff_location == "At_dropoff":
            order_details = await db.execute(
                select(models.Orders)
                .where(models.Orders.order_number == order_number)
            )    
            order_details = order_details.scalar_one_or_none()
            message_for_sender_and_recipient_and_rider = (
                f"Package has been delivered successfully!\n"
                "Thank you for choosing inTime!\n"
               
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
                await replyhandler.send_custom_message(sender_wa_number=sender_wa_number, message="Dispatch request is expired and has already been completed by another rider", auth=AUTH, graph_url=GRAPH_URL)
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
                message = "Offer was declined by customer"
                await replyhandler.send_custom_message(sender_wa_number=rider_wa_number, message=message, auth=AUTH, graph_url=GRAPH_URL)


        match template_id:
            case "user_registration" | "w":
                try:
                    contacts = value.get("contacts", [{}])
                    wa_id = contacts[0].get("wa_id", sender_wa_number) if contacts else sender_wa_number
                    metadata = value.get("metadata", {})
                    phone_number_id = metadata.get("phone_number_id", sender_wa_number)
                except Exception:
                    wa_id = sender_wa_number
                    phone_number_id = sender_wa_number

                await createUser(
                            name=name,
                            wa_id=sender_wa_number,
                            display_phone_number=sender_wa_number,
                            phone_number_id=phone_number_id,
                            db=db
                        )

                await replyhandler.reply_user_that_has_just_registered(sender_wa_number, AUTH, GRAPH_URL)
        
            case "order_details" | "other_details":

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
                customer_initial_offered_price=customer_initial_offered_price,
                final_price_agreed_by_cust_and_rider=customer_initial_offered_price,
                package_description=package_description,
                recipient_phone_number=recipient_phone_number,
                pickup_location_name=", ".join([str(v).strip() for v in [json_response.get('pickup_HouseFlat_Number_0'), json_response.get('pickup_Street_Name_1'), json_response.get('pickup_City_2'), json_response.get('pickup_State_3')] if v and str(v).lower() != "none"]) or "Pickup Location",
                dropoff_location_name=", ".join([str(v).strip() for v in [json_response.get('dropoff_HouseFlat_Number_0'), json_response.get('dropoff_Street_Name_1'), json_response.get('dropoff_City_2'), json_response.get('dropoff_State_3')] if v and str(v).lower() != "none"]) or "Dropoff Location",
                )

                db.add(newOrder)
                await db.commit()
                await db.refresh(newOrder)
                await replyhandler.send_custom_message(sender_wa_number, "Please take and upload an image of the package you are sending", AUTH, GRAPH_URL)
                asyncio.create_task(replyhandler.schedule_user_session_timeout(newOrder.order_number, sender_wa_number, AUTH, GRAPH_URL))


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
        text_body = message.get("text", {}).get("body", "")
        contacts = value.get("contacts", [{}])
        profile = contacts[0].get("profile", {}) if contacts else {}
        username = profile.get("name", "User")
        await replyhandler.handle_text_message(sender_wa_number, text_body, username, db, AUTH, GRAPH_URL)

    elif message["type"] == "image":
        sender_wa_number = message["from"]

        result = await db.execute(
        select(models.Orders)
        .where(models.Orders.sender_wa_number == sender_wa_number)
        .where(models.Orders.customer_initial_offered_price.is_not(None))
        .where(models.Orders.package_image_id.is_(None))
        .where(models.Orders.sla_expires_by > datetime.now(UTC))
        .order_by(models.Orders.created_at.desc())
        )
        result = result.scalars().first()

        if result:
            await db.execute(
                    update(models.Orders)
                    .where(models.Orders.sender_wa_number == sender_wa_number)
                    .where(models.Orders.status.in_(["confirmed"]))
                    .values(package_image_id=message["image"]["id"])
                    )
            await db.commit()
            ride = await replyhandler.get_active_ride(sender_wa_number, db)
            if ride:
                order_details = {
                    "package_description": ride.package_description,
                    "pick_up_location": ride.pickup_location_name,
                    "drop_off_location": ride.dropoff_location_name,
                    "offered_price": ride.customer_initial_offered_price,
                    "order_number": ride.order_number,
                    "image_id": ride.package_image_id
                }
                await replyhandler.get_rider(sender_wa_number=sender_wa_number, auth=AUTH, graph_url=GRAPH_URL, order_details=order_details, db=db)
            else:
                await replyhandler.send_something_went_wrong_template(sender_wa_number=sender_wa_number, auth=AUTH, graph_url=GRAPH_URL)
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

    possible_numbers = list(set(
        replyhandler.get_phone_variants(wa_id) +
        replyhandler.get_phone_variants(display_phone_number) +
        replyhandler.get_phone_variants(phone_number_id)
    ))

    result = await db.execute(
        select(models.User).where(
            (models.User.phone_number_id.in_(possible_numbers)) |
            (models.User.wa_id.in_(possible_numbers)) |
            (models.User.display_phone_number.in_(possible_numbers))
        )
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


async def _delayed_pickup_arrival_notifications(sender_wa, rider_wa, recipient_phone, order_num, auth, graph_url, delay=300):
    await asyncio.sleep(delay)
    five_digit_code = ''.join(random.choices(string.digits, k=5))
    message_for_sender = (
        f"The Code is: {five_digit_code}.\n"
        "You don't have to do anything with this code.\n"
        "The Same code has been sent to the recipient of the package and the rider as well.\n"
        "We are only sending you this code as a backup in the event that the recipient didnt recieve the code for whatever reason.\n"
        "Feel free to share this code with the recipient as the dispatch rider would demand it before delivering the package.\n"
        "DO NOT SHARE THIS CODE WITH THE RIDER ONLY SHARE WITH THE RECIPIENT"
    )
    message_for_rider = (
        f"The Code is: {five_digit_code}. \n"
        "Confirm this code from the recipient before delivering the package"
    )
    message_for_recipient = (
        "Just Notifying you that Rider has gotten to the pickup location and would be coming to you soon.\n\n" 
        f"The Code is: {five_digit_code}. \n\n"
        "The Rider would request this code of you before delivering you package"
    )
    await replyhandler.send_custom_message(
        sender_wa_number=sender_wa, 
        message=message_for_sender,
        auth=auth, 
        graph_url=graph_url
    )

    await replyhandler.send_custom_message(
        sender_wa_number=rider_wa, 
        message=message_for_rider,
        auth=auth, 
        graph_url=graph_url
    )
    await replyhandler.send_custom_message(
        sender_wa_number=recipient_phone, 
        message=message_for_recipient,
        auth=auth, 
        graph_url=graph_url
    )

    await replyhandler.send_custom_flow(
        wa_number=rider_wa,
        flow_token={"order_number": order_num},
        message="Click the button below when you have dropped off the package successfully",
        header="Have you delivered the package yet?\n\n",
        flow_id="1549615230214062",
        flow_cta="Have you Delivered the Package?",
        screen_name="flow_to_ask_if_rider_has_dropped_off_package",
        auth=auth,
        graph_url=graph_url
    )




