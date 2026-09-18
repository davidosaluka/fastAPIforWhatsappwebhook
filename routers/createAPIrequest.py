import asyncio
import re
from datetime import UTC, datetime, timedelta
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

    if wamid:
        try:
            await replyhandler.show_typing_indicator(
                message_id=wamid,
                auth=AUTH,
                graph_url=GRAPH_URL
            )
        except Exception as e:
            logger.warning(f"Failed to show typing indicator for {wamid}: {e}")

    sender_wa_number = message.get("from")
    if sender_wa_number:
        await replyhandler.mark_rider_available_if_rider(sender_wa_number, db)

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

        elif message["button"]["payload"] in ["Delete my Account", "Delete My Account", "Delete Account", "Delete my data", "Delete Data"]:
            is_existing_user = await replyhandler.is_user_registered(sender_wa_number, db)
            if is_existing_user:
                await replyhandler.send_delete_account_confirmation(sender_wa_number, AUTH, GRAPH_URL, db)
            else:
                custom_message = "You currently do not have a registered account with InTime."
                await replyhandler.send_custom_message(sender_wa_number, custom_message, AUTH, GRAPH_URL)

        elif message["button"]["payload"] == "I'm Available":
            rider_phoneno = message["from"]
            possible_numbers = replyhandler.get_phone_variants(rider_phoneno)
            await db.execute(
                update(models.Riders)
                .where(models.Riders.rider_wa_number.in_(possible_numbers))
                .values(availability_status="available")
            )
            await db.commit()
            custom_message = "Thank you for Checking in! New Dispatch requests would begin routing to you shortly 📦🛵💨"
            await replyhandler.send_custom_message(rider_phoneno, custom_message, AUTH, GRAPH_URL)
        
    if message["type"] == "interactive" and message["interactive"]["type"] == "button_reply":
        button_id = message["interactive"]["button_reply"].get("id", "")
        sender_wa_number = message["from"]

        if button_id.startswith("FIND_ANOTHER_RIDER:"):
            order_number = button_id.split(":", 1)[1]

            # Fetch the order to get rider wa number and current details
            order_res = await db.execute(
                select(models.Orders).where(models.Orders.order_number == order_number)
            )
            order = order_res.scalars().first()

            if order and order.status == "rider_accepted":
                if order.delivery_progression_status == "package_picked_up":
                    in_transit_msg = (
                        f"⚠️ *Package Already in Transit*\n\n"
                        f"Your rider has already picked up your package for Order *{order_number}* and is heading to the destination.\n\n"
                        f"A new rider cannot be assigned while goods are in transit. If you need urgent assistance, please contact our support team at +234 815 103 3428."
                    )
                    await replyhandler.send_custom_message(sender_wa_number, in_transit_msg, AUTH, GRAPH_URL)
                    return

                prev_rider_wa = order.rider_wa_number

                # Unassign current rider, reset order status to confirmed
                await db.execute(
                    update(models.Orders)
                    .where(models.Orders.order_number == order_number)
                    .values(status="confirmed", rider_wa_number=None)
                )
                await db.commit()

                # Notify previous rider they have been unassigned
                if prev_rider_wa:
                    unassign_msg = (
                        f"⏰ *Order Re-assigned*\n\n"
                        f"The customer has chosen to find a different rider for Order *{order_number}*.\n\n"
                        f"This order has been returned to dispatch search."
                    )
                    await replyhandler.send_custom_message(prev_rider_wa, unassign_msg, AUTH, GRAPH_URL)

                # Notify customer re-routing has started
                reroute_msg = (
                    f"🔄 *Finding Another Rider*\n\n"
                    f"We are searching for a new rider for Order *{order_number}* right now!\n\n"
                    f"We'll notify you as soon as a new rider accepts."
                )
                await replyhandler.send_custom_message(sender_wa_number, reroute_msg, AUTH, GRAPH_URL)

                # Re-dispatch to riders, resetting view count
                order_details = {
                    "package_description": order.package_description,
                    "pick_up_location": order.pickup_location_name,
                    "drop_off_location": order.dropoff_location_name,
                    "offered_price": order.final_price_agreed_by_cust_and_rider or order.customer_initial_offered_price or "1000",
                    "order_number": order.order_number,
                    "image_id": order.package_image_id,
                    "is_priority": order.is_priority,
                    "is_drug": order.is_drug,
                    "is_urgent": order.is_urgent
                }
                await replyhandler.get_rider(
                    sender_wa_number=sender_wa_number,
                    auth=AUTH,
                    graph_url=GRAPH_URL,
                    order_details=order_details,
                    db=db,
                    reset_offers=True
                )
            else:
                await replyhandler.send_custom_message(
                    sender_wa_number, "This order is no longer in a state that can be re-routed.", AUTH, GRAPH_URL
                )

        elif button_id.startswith("CANCEL_ORDER:"):
            order_number = button_id.split(":", 1)[1]

            order_res = await db.execute(
                select(models.Orders).where(models.Orders.order_number == order_number)
            )
            order = order_res.scalars().first()

            if order and order.status in ["confirmed", "rider_accepted"]:
                if order.delivery_progression_status == "package_picked_up":
                    in_transit_msg = (
                        f"⚠️ *Package Already in Transit*\n\n"
                        f"Your rider has already picked up your package for Order *{order_number}* and is on the way to the recipient.\n\n"
                        f"Orders cannot be cancelled automatically once picked up. Please contact our support team at +234 815 103 3428 or intimesender@gmail.com for immediate help."
                    )
                    await replyhandler.send_custom_message(sender_wa_number, in_transit_msg, AUTH, GRAPH_URL)
                    return

                prev_rider_wa = order.rider_wa_number

                # Cancel the order
                await db.execute(
                    update(models.Orders)
                    .where(models.Orders.order_number == order_number)
                    .values(status="cancelled")
                )
                await db.commit()

                # Notify the rider (if one was assigned)
                if prev_rider_wa:
                    rider_cancel_msg = (
                        f"❌ *Order Cancelled*\n\n"
                        f"The customer has cancelled Order *{order_number}*.\n\n"
                        f"Thank you for your time — new requests will come your way shortly! 🛵"
                    )
                    await replyhandler.send_custom_message(prev_rider_wa, rider_cancel_msg, AUTH, GRAPH_URL)

                # Confirm cancellation to customer and ask for reason
                cancel_confirm_msg = (
                    f"❌ *Order Cancelled*\n\n"
                    f"Your order *{order_number}* has been successfully cancelled.\n\n"
                    f"We're sorry to see you go! 🙏 If you'd like to share why you cancelled, just type your reason below — your feedback helps us improve."
                )
                await replyhandler.send_custom_message(sender_wa_number, cancel_confirm_msg, AUTH, GRAPH_URL)
            else:
                await replyhandler.send_custom_message(
                    sender_wa_number, "This order cannot be cancelled at its current stage.", AUTH, GRAPH_URL
                )

        elif button_id == "CONFIRM_DELETE_ACCOUNT":
            active_order = await replyhandler.check_active_user_order(sender_wa_number, db)
            if active_order:
                if active_order.delivery_progression_status == "package_picked_up":
                    in_transit_msg = (
                        f"⚠️ *Account Deletion Blocked*\n\n"
                        f"Your package for Order *{active_order.order_number}* is currently in transit with your dispatch rider.\n\n"
                        f"For safety and security of goods in transit, your active delivery must be completed before your account can be deleted. "
                        f"Once your package has been delivered to the recipient, you can proceed with deleting your account!"
                    )
                    await replyhandler.send_custom_message(sender_wa_number, in_transit_msg, AUTH, GRAPH_URL)
                else:
                    active_msg = (
                        f"⚠️ *Account Deletion Blocked*\n\n"
                        f"You currently have an active order (**Order *{active_order.order_number}***) in progress.\n\n"
                        f"Account deletion cannot be processed while an order is active. "
                        f"Please cancel your active order first (or wait for it to complete) before deleting your account.\n\n"
                        f"ℹ️ *To cancel your active order, simply type 'Cancel Order' or tap the cancel button on your order details.*"
                    )
                    await replyhandler.send_custom_message(sender_wa_number, active_msg, AUTH, GRAPH_URL)
            else:
                await replyhandler.delete_user_data(sender_wa_number, db)
                confirm_msg = (
                    "🗑️ *Account Deleted*\n\n"
                    "Your account and profile data have been permanently deleted from InTime.\n\n"
                    "If you ever wish to use our services again, simply type *Send an Order* to re-register!"
                )
                await replyhandler.send_custom_message(sender_wa_number, confirm_msg, AUTH, GRAPH_URL)

        elif button_id == "CANCEL_DELETE_ACCOUNT":
            cancel_msg = (
                "✅ *Action Cancelled*\n\n"
                "Your account deletion request has been cancelled. Your account remains active and secure!"
            )
            await replyhandler.send_custom_message(sender_wa_number, cancel_msg, AUTH, GRAPH_URL)

        elif button_id.startswith("rate_rider:"):
            parts = button_id.split(":")
            if len(parts) >= 3:
                order_number = parts[1]
                try:
                    rating_val = int(parts[2])
                    await replyhandler.save_rider_rating(
                        order_number=order_number,
                        rating_val=rating_val,
                        customer_wa=sender_wa_number,
                        db=db,
                        auth=AUTH,
                        graph_url=GRAPH_URL
                    )
                except ValueError:
                    pass

        elif button_id.startswith("ETA_YES_10MINS:"):
            order_number = button_id.split(":", 1)[1]
            order_res = await db.execute(
                select(models.Orders).where(models.Orders.order_number == order_number)
            )
            order = order_res.scalars().first()
            if order:
                rider_msg = (
                    f"Awesome 🛵!\n\n"
                    f"Thanks for confirming. When you arrive at the drop-off location for Order *{order.order_number}*, please request the 5-digit verification code from the recipient."
                )
                await replyhandler.send_custom_message(sender_wa_number, rider_msg, AUTH, GRAPH_URL)

                # Fetch sender name
                sender_res = await db.execute(
                    select(models.User.name).where(
                        models.User.wa_id.in_(replyhandler.get_phone_variants(order.sender_wa_number))
                    )
                )
                sender_name = sender_res.scalars().first() or "Sender"

                customer_eta_msg = (
                    f"🛵 *Delivery Update*\n\n"
                    f"Rider has confirmed they are approximately 10 minutes away from the drop-off location for Order *{order.order_number}*!"
                )
                recipient_eta_msg = (
                    f"📦 *Package Update*\n\n"
                    f"Your package from *{sender_name}* (Order *{order.order_number}*) is getting close!\n\n"
                    f"Your rider has confirmed they are approximately 10 minutes away."
                )

                if order.sender_wa_number:
                    await replyhandler.send_custom_message(sender_wa_number=order.sender_wa_number, message=customer_eta_msg, auth=AUTH, graph_url=GRAPH_URL)
                if order.recipient_phone_number:
                    await replyhandler.send_details_to_recipients(sender_wa_number=order.recipient_phone_number, message=recipient_eta_msg, auth=AUTH, graph_url=GRAPH_URL)

        elif button_id.startswith("ETA_NO_STILL_FAR:"):
            order_number = button_id.split(":", 1)[1]
            rider_msg = (
                f"Got it 👍\n\n"
                f"Take your time and ride safely! We'll check back with you shortly regarding Order *{order_number}*."
            )
            await replyhandler.send_custom_message(sender_wa_number, rider_msg, AUTH, GRAPH_URL)

    if message["type"] == "interactive" and message["interactive"]["type"] == "list_reply":
        list_reply = message["interactive"]["list_reply"]
        list_id = list_reply.get("id", "")
        sender_wa_number = message["from"]

        if list_id.startswith("rate_rider:"):
            parts = list_id.split(":")
            if len(parts) >= 3:
                order_number = parts[1]
                try:
                    rating_val = int(parts[2])
                    await replyhandler.save_rider_rating(
                        order_number=order_number,
                        rating_val=rating_val,
                        customer_wa=sender_wa_number,
                        db=db,
                        auth=AUTH,
                        graph_url=GRAPH_URL
                    )
                except ValueError:
                    pass

    if message["type"] == "interactive" and message["interactive"]["type"] == "nfm_reply":
        nfm_reply = message["interactive"]["nfm_reply"]
        raw_response = nfm_reply.get("response_json", "{}")
        json_response = json.loads(raw_response) if isinstance(raw_response, str) else (raw_response if isinstance(raw_response, dict) else {})
        
        template_id = json_response.get("template_id")  
        raw_token = nfm_reply.get("flow_token") or json_response.get("flow_token")
        flow_token = json.loads(raw_token) if raw_token and raw_token != "unused" and isinstance(raw_token, str) else (raw_token if isinstance(raw_token, dict) else {})
        order_number = flow_token.get("order_number")
        rider_wa_number = flow_token.get("rider_wa_number")
        
        name        = (
            json_response.get("name") or 
            json_response.get("user_name") or 
            json_response.get("screen_0_Name_0") or 
            json_response.get("full_name") or
            json_response.get("Name") or
            json_response.get("first_name") or
            json_response.get("customer_name")
        )
        rider_proposed_amount = json_response.get("proposed_amount") or json_response.get("rider_proposed_amount")
        customer_fare_increase_amount = json_response.get("customer_fare_increase_amount")
        custRespToRiderOff = json_response.get("custRespToRiderOff")       
        email       = json_response.get("email")         
        status      = json_response.get("status")
        
        raw_price = json_response.get("customer_intital_offered_price") or json_response.get("customer_initial_offered_price") or json_response.get("offered_price") or json_response.get("price")
        raw_desc = json_response.get("package_description") or json_response.get("description")
        raw_recipient = json_response.get("recipient_phone_number") or json_response.get("recipient_phone") or json_response.get("recipient_phone_number_0")
        
        raw_is_drug = json_response.get("is_drug") or json_response.get("Is_Drug_med") or json_response.get("is_medication") or json_response.get("isDrug")
        raw_is_urgent = json_response.get("is_urgent") or json_response.get("Is_Urgent_asap") or json_response.get("is_asap") or json_response.get("isUrgent")

        is_drug = str(raw_is_drug).lower() in ["true", "1", "yes"] if raw_is_drug is not None else False
        is_urgent = str(raw_is_urgent).lower() in ["true", "1", "yes"] if raw_is_urgent is not None else False
        is_priority = bool(is_urgent or (is_drug and is_urgent))
        if is_priority:
            is_drug = True
            is_urgent = True

        sender_wa_number = message["from"] 
        rider_selected_option_for_current_ride = json_response.get("screen_0_Pick_an_Option_0")
        rider_in_pickup_location = json_response.get("screen_for_pickup_location_prompt") 
        rider_in_dropoff_location = json_response.get("screen_for_dropoff_location_prompt") 

        is_specific_action = bool(
            rider_in_pickup_location or
            rider_in_dropoff_location or
            rider_selected_option_for_current_ride or
            rider_proposed_amount or
            custRespToRiderOff or
            customer_fare_increase_amount
        )

        if is_specific_action:
            template_id = None
        elif not template_id or template_id not in ["order_details", "other_details", "user_registration", "w"]:
            # Order fields always take priority — prevents combined registration+order forms being re-classified as user_registration
            if raw_price or raw_desc or raw_recipient or json_response.get("pickup_HouseFlat_Number_0") or json_response.get("pickup_address"):
                template_id = "order_details"
            elif name or json_response.get("screen_0_Name_0"):
                template_id = "user_registration"
            else:
                template_id = None

        customer_initial_offered_price = str(raw_price) if raw_price is not None else "0"
        package_description = str(raw_desc) if raw_desc is not None else "Package"
        recipient_phone_number = str(raw_recipient) if raw_recipient is not None else sender_wa_number

        rider_in_pickup = bool(
            rider_in_pickup_location == "At_Pickup" or
            (isinstance(rider_in_pickup_location, str) and "pickup" in rider_in_pickup_location.lower()) or
            any("pickup" in str(k).lower() or "pickup" in str(v).lower() for k, v in json_response.items())
        )

        if rider_in_pickup:
            order_details = None
            if order_number:
                res = await db.execute(
                    select(models.Orders).where(models.Orders.order_number == order_number)
                )    
                order_details = res.scalar_one_or_none()
            if not order_details and sender_wa_number:
                order_details = await replyhandler.get_active_rider_order(sender_wa_number, db)

            if order_details:
                code_to_set = order_details.verification_code or ''.join(random.choices(string.digits, k=5))
                await db.execute(
                    update(models.Orders)
                    .where(models.Orders.order_number == order_details.order_number)
                    .values(
                        delivery_progression_status="package_picked_up",
                        verification_code=code_to_set
                    )
                )
                await db.commit()

                # Fetch sender name for recipient notification
                sender_res = await db.execute(
                    select(models.User.name).where(
                        models.User.wa_id.in_(replyhandler.get_phone_variants(order_details.sender_wa_number))
                    )
                )
                sender_name = sender_res.scalars().first() or "Sender"

                # 1. Notify Rider IMMEDIATELY
                rider_phone = order_details.rider_wa_number or sender_wa_number
                rider_pickup_msg = (
                    f"📦 *Pickup Confirmed!* 🏍️💨\n\n"
                    f"You have confirmed package pickup for Order *{order_details.order_number}*.\n\n"
                    f"🏁 *Head to Drop-off:* {order_details.dropoff_location_name or 'Drop-off location'}\n\n"
                    f"📋 *Next Step upon Arrival:*\n"
                    f"• Ask the recipient for their *5-digit verification code*\n"
                    f"• Simply reply with the code here in this chat (e.g. *12345*) to complete delivery! (3 trials available) 🤝✨"
                )
                await replyhandler.send_custom_message(
                    sender_wa_number=rider_phone,
                    message=rider_pickup_msg,
                    auth=AUTH,
                    graph_url=GRAPH_URL
                )

                # 2. Notify Customer (Sender)
                sender_pickup_msg = (
                    f"📦 *Package Picked Up!* 🛵💨\n\n"
                    f"Your rider has collected your package for Order *{order_details.order_number}* and is on the way to the recipient!"
                )
                await replyhandler.send_custom_message(
                    sender_wa_number=order_details.sender_wa_number,
                    message=sender_pickup_msg,
                    auth=AUTH,
                    graph_url=GRAPH_URL
                )

                # 3. Send 5-Digit Verification Code to Recipient
                recipient_code_msg = (
                    f"🛵💨 *Your Package Is On The Way!* 📦✨\n\n"
                    f"Your dispatch rider has picked up your package from *{sender_name}* (Order *{order_details.order_number}*) and is en route!\n\n"
                    f"🔐 *Your Delivery Verification Code:*\n"
                    f"👉  *{code_to_set}*  👈\n\n"
                    f"📋 *Instructions:*\n"
                    f"• Share this *5-digit code* with the rider when they arrive to securely receive your package. 🤝\n\n"
                    f"Thank you for choosing *InTime*! 🌟🚀"
                )
                if order_details.recipient_phone_number:
                    await replyhandler.send_details_to_recipients(
                        sender_wa_number=order_details.recipient_phone_number,
                        message=recipient_code_msg,
                        auth=AUTH,
                        graph_url=GRAPH_URL
                    )

                # 4. Send Backup Verification Code to Sender
                sender_backup_code_msg = (
                    f"🔐 *Delivery Verification Code (Backup)* 📦✨\n\n"
                    f"Your package for Order *{order_details.order_number}* is on the way!\n\n"
                    f"🔑 Verification Code: 👉 *{code_to_set}* 👈\n\n"
                    f"ℹ️ We sent this code directly to your recipient. We're sharing it with you as a helpful backup! 🛡️"
                )
                await replyhandler.send_custom_message(
                    sender_wa_number=order_details.sender_wa_number,
                    message=sender_backup_code_msg,
                    auth=AUTH,
                    graph_url=GRAPH_URL
                )

                # 5. Launch delayed ETA check background monitor
                asyncio.create_task(_delayed_pickup_arrival_notifications(
                    sender_wa=order_details.sender_wa_number,
                    rider_wa=order_details.rider_wa_number,
                    recipient_phone=order_details.recipient_phone_number,
                    order_num=order_details.order_number,
                    auth=AUTH,
                    graph_url=GRAPH_URL
                ))

        rider_in_dropoff = bool(
            rider_in_dropoff_location == "At_dropoff" or
            (isinstance(rider_in_dropoff_location, str) and "dropoff" in rider_in_dropoff_location.lower()) or
            any("dropoff" in str(k).lower() or "dropoff" in str(v).lower() for k, v in json_response.items())
        )

        if rider_in_dropoff:
            order_details = None
            if order_number:
                res = await db.execute(
                    select(models.Orders).where(models.Orders.order_number == order_number)
                )    
                order_details = res.scalar_one_or_none()
            if not order_details and sender_wa_number:
                order_details = await replyhandler.get_active_rider_order(sender_wa_number, db)

            if order_details:
                flow_code = (
                    json_response.get("verification_code") or
                    json_response.get("code") or
                    json_response.get("otp") or
                    json_response.get("digit") or
                    json_response.get("pin")
                )
                if flow_code:
                    await replyhandler.verify_delivery_code(
                        order=order_details,
                        submitted_code=str(flow_code),
                        rider_wa_number=order_details.rider_wa_number or sender_wa_number,
                        db=db,
                        auth=AUTH,
                        graph_url=GRAPH_URL
                    )
                elif order_details.verification_code and order_details.delivery_progression_status != "package_delivered":
                    code_prompt = (
                        f"🔐 *Recipient Verification Code Required* 🛵💨\n\n"
                        f"To complete Order *{order_number}*, please ask the recipient for their *5-digit verification code* and reply with it in this chat (e.g. *12345*).\n\n"
                        f"⚠️ *Note:* You have 3 trials to enter the correct code."
                    )
                    await replyhandler.send_custom_message(
                        sender_wa_number=order_details.rider_wa_number or sender_wa_number,
                        message=code_prompt,
                        auth=AUTH,
                        graph_url=GRAPH_URL
                    )
                else:
                    # Fetch rider name for the rating prompt
                    rider_name_res = await db.execute(
                        select(models.Riders.first_name, models.Riders.last_name)
                        .where(models.Riders.rider_wa_number == order_details.rider_wa_number)
                    )
                    rider_name_row = rider_name_res.first()
                    rider_display_name = f"{rider_name_row[0]} {rider_name_row[1]}" if rider_name_row else "your rider"

                    message_for_rider = (
                        f"📦 *Package has been delivered successfully!*\n\n"
                        f"Thank you for your service! More orders coming soon. 🛵💨🎉\n\n"
                        f"Order *{order_number}* is completed. Keep up the fantastic hustle! 💪✨"
                    )
                    message_for_recipient = (
                        f"✅🎉 *Your Package Has Arrived!*\n\n"
                        f"Your delivery for Order *{order_number}* has been completed successfully! 📦✨\n\n"
                        f"Thank you for choosing *InTime*! Have a wonderful day ahead! 🌟😊"
                    )
                    message_for_sender = (
                        f"🎉🥳 *Delivery Complete!* 📦✨\n\n"
                        f"Woohoo! Your package for Order *{order_number}* has been delivered safely and successfully! 🎊🛵💨\n\n"
                        f"Thank you so much for choosing *InTime* — we absolutely loved delivering for you today! 🚀💫\n"
                        f"Whenever you need to send another package, we're always right here for you! 🌟🙌"
                    )

                    await db.execute(
                        update(models.Orders)
                        .where(models.Orders.order_number == order_number)
                        .values(
                            delivery_progression_status="package_delivered",
                            status="completed"
                        )
                    )
                    await db.commit()

                    # Notify rider
                    await replyhandler.send_custom_message(
                        sender_wa_number=order_details.rider_wa_number,
                        message=message_for_rider,
                        auth=AUTH,
                        graph_url=GRAPH_URL
                    )
                    # Notify sender
                    await replyhandler.send_custom_message(
                        sender_wa_number=order_details.sender_wa_number,
                        message=message_for_sender,
                        auth=AUTH,
                        graph_url=GRAPH_URL
                    )
                    # Notify recipient
                    await replyhandler.send_custom_message(
                        sender_wa_number=order_details.recipient_phone_number,
                        message=message_for_recipient,
                        auth=AUTH,
                        graph_url=GRAPH_URL
                    )

                    # Send rating prompt to customer (list message with 5 → 1 stars)
                    await replyhandler.send_rider_rating_prompt(
                        customer_wa_number=order_details.sender_wa_number,
                        rider_name=rider_display_name,
                        order_number=order_number,
                        auth=AUTH,
                        graph_url=GRAPH_URL
                    )

        if rider_selected_option_for_current_ride:
            order_sla_details = await db.execute(
                select(models.Orders.sla_expires_by)
                .where(models.Orders.order_number == order_number)
            )    
            order_sla_details_result = order_sla_details.scalar_one_or_none()
            order_still_valid = bool(order_sla_details_result and order_sla_details_result > datetime.now(UTC))
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
                .values(
                    customer_initial_offered_price=str(customer_fare_increase_amount),
                    final_price_agreed_by_cust_and_rider=str(customer_fare_increase_amount)
                )
            )
            await db.commit()

            result = await db.execute(
                select(models.Orders)
                .where(models.Orders.order_number == order_number)
            )
            result = result.scalar_one_or_none()

            if result:
                order_details = {
                    "package_description": result.package_description,
                    "pick_up_location": result.pickup_location_name,
                    "drop_off_location": result.dropoff_location_name,
                    "offered_price": customer_fare_increase_amount,
                    "order_number": result.order_number,
                    "image_id": result.package_image_id,
                    "is_priority": result.is_priority,
                    "is_drug": result.is_drug,
                    "is_urgent": result.is_urgent
                }
                await replyhandler.send_custom_message(
                    sender_wa_number=sender_wa_number,
                    message=f"✅ *Fare Updated*\n\nYour fare for Order *{result.order_number}* has been updated to *₦{customer_fare_increase_amount}*. Re-broadcasting your order to nearby riders now! 🛵💨",
                    auth=AUTH,
                    graph_url=GRAPH_URL
                )
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

                user_result = await createUser(
                            name=name or "Customer",
                            wa_id=sender_wa_number,
                            display_phone_number=sender_wa_number,
                            phone_number_id=phone_number_id,
                            db=db
                        )

                # Cancel any old unfulfilled "confirmed" orders for this customer so they start with a clean slate
                await db.execute(
                    update(models.Orders)
                    .where(models.Orders.sender_wa_number.in_(replyhandler.get_phone_variants(sender_wa_number)))
                    .where(models.Orders.status.in_(["confirmed"]))
                    .values(status="cancelled")
                )
                await db.commit()

                # Guard: only notify if the customer has an in-progress delivery with a rider actively en route
                active_delivery_check = await db.execute(
                    select(models.Orders)
                    .where(models.Orders.sender_wa_number.in_(replyhandler.get_phone_variants(sender_wa_number)))
                    .where(models.Orders.status.in_(["rider_accepted", "awaiting_pickup", "package_picked_up", "in_transit", "awaiting_dropoff"]))
                    .where(models.Orders.created_at >= datetime.now(UTC) - timedelta(hours=24))
                )
                active_delivery = active_delivery_check.scalars().first()

                if active_delivery:
                    info_msg = (
                        f"📦 *Delivery In Progress*\n\n"
                        f"Welcome back! You already have an active order being handled by a rider (Order *{active_delivery.order_number}*).\n\n"
                        f"Type *Track Order* to see live progress, or contact support if you need assistance!"
                    )
                    await replyhandler.send_custom_message(sender_wa_number, info_msg, AUTH, GRAPH_URL)
                else:
                    # Always dispatch the order details form to the customer upon registration
                    await replyhandler.reply_user_that_has_just_registered(sender_wa_number, AUTH, GRAPH_URL)
        
            case "order_details" | "other_details":
                is_existing_user = await replyhandler.is_user_registered(sender_wa_number, db)
                if not is_existing_user:
                    # Fallback auto-reactivation: if account was deleted in DB, reactivate it now
                    possible_numbers = replyhandler.get_phone_variants(sender_wa_number)
                    del_user_res = await db.execute(
                        select(models.User).where(
                            (models.User.display_phone_number.in_(possible_numbers)) |
                            (models.User.wa_id.in_(possible_numbers)) |
                            (models.User.phone_number_id.in_(possible_numbers)) |
                            (models.User.wa_id.like(f"DELETED_%_{sender_wa_number}"))
                        )
                    )
                    del_user = del_user_res.scalars().first()
                    if del_user:
                        del_user.is_deleted = False
                        del_user.wa_id = sender_wa_number
                        del_user.display_phone_number = sender_wa_number
                        await db.commit()
                        await db.refresh(del_user)
                        print(f"🟢 [AUTO-REACTIVATED] User {sender_wa_number} reactivated on order details submission.")
                        is_existing_user = True
                    else:
                        # Auto-create user from contact profile so order is never dropped
                        contacts = value.get("contacts", [{}])
                        profile = contacts[0].get("profile", {}) if contacts else {}
                        cust_name = profile.get("name") or name or "Customer"
                        await createUser(
                            name=cust_name,
                            wa_id=sender_wa_number,
                            display_phone_number=sender_wa_number,
                            phone_number_id=sender_wa_number,
                            db=db
                        )
                        is_existing_user = True

                await db.execute(
                update(models.Orders)
                .where(models.Orders.sender_wa_number.in_(replyhandler.get_phone_variants(sender_wa_number)))
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
                is_drug=is_drug,
                is_urgent=is_urgent,
                is_priority=is_priority
                )

                db.add(newOrder)
                await db.commit()
                await db.refresh(newOrder)
                await replyhandler.send_custom_message(sender_wa_number, "Please take and upload an image of the package you are sending", AUTH, GRAPH_URL)
                asyncio.create_task(replyhandler.schedule_user_session_timeout(newOrder.order_number, sender_wa_number, AUTH, GRAPH_URL))

            case _:
                print(f"Unknown template_id: {template_id}")

    elif message["type"] == "text":
        sender_wa_number = message["from"]
        text_body = message.get("text", {}).get("body", "")
        contacts = value.get("contacts", [{}])
        profile = contacts[0].get("profile", {}) if contacts else {}
        username = profile.get("name", "User")
        await replyhandler.handle_text_message(sender_wa_number, text_body, username, db, AUTH, GRAPH_URL)

    elif message["type"] == "image":
        sender_wa_number = message["from"]
        possible_numbers = replyhandler.get_phone_variants(sender_wa_number)

        result = await db.execute(
        select(models.Orders)
        .where(models.Orders.sender_wa_number.in_(possible_numbers))
        .where(models.Orders.customer_initial_offered_price.is_not(None))
        .where(models.Orders.package_image_id.is_(None))
        .where(models.Orders.sla_expires_by > datetime.now(UTC))
        .order_by(models.Orders.created_at.desc())
        )
        result = result.scalars().first()

        if result:
            await db.execute(
                    update(models.Orders)
                    .where(models.Orders.order_number == result.order_number)
                    .values(package_image_id=message["image"]["id"])
                    )
            await db.commit()
            ride = await replyhandler.get_active_ride(sender_wa_number, db)
            if not ride:
                ride = result
            if ride:
                order_details = {
                    "package_description": ride.package_description,
                    "pick_up_location": ride.pickup_location_name,
                    "drop_off_location": ride.dropoff_location_name,
                    "offered_price": ride.customer_initial_offered_price,
                    "order_number": ride.order_number,
                    "image_id": ride.package_image_id,
                    "is_priority": ride.is_priority,
                    "is_drug": ride.is_drug,
                    "is_urgent": ride.is_urgent
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
    clean_name = name or "Customer"
    clean_wa_id = re.sub(r'[^\d]', '', str(wa_id)) if wa_id else str(wa_id)
    clean_display = re.sub(r'[^\d]', '', str(display_phone_number)) if display_phone_number else clean_wa_id
    clean_phone_id = str(phone_number_id) if phone_number_id else clean_wa_id

    possible_numbers = list(set(
        replyhandler.get_phone_variants(clean_wa_id) +
        replyhandler.get_phone_variants(clean_display) +
        replyhandler.get_phone_variants(clean_phone_id)
    ))

    # Search for ANY existing record matching these numbers, including soft-deleted and DELETED_ prefixed users
    stmt = select(models.User).where(
        (models.User.phone_number_id.in_(possible_numbers)) |
        (models.User.wa_id.in_(possible_numbers)) |
        (models.User.display_phone_number.in_(possible_numbers)) |
        (models.User.wa_id.like(f"DELETED_%_{clean_wa_id}")) |
        (models.User.display_phone_number.like(f"DELETED_%_{clean_display}")) |
        (models.User.phone_number_id.like(f"DELETED_%_{clean_phone_id}"))
    )
    result = await db.execute(stmt)
    existing_user = result.scalars().first()

    if existing_user:
        was_previously_deleted = existing_user.is_deleted or "DELETED_" in str(existing_user.wa_id)
        # Reactivate user record if it was soft-deleted, and restore clean phone fields
        existing_user.is_deleted = False
        existing_user.wa_id = clean_wa_id
        existing_user.display_phone_number = clean_display
        existing_user.phone_number_id = clean_phone_id
        if clean_name and clean_name != "Customer":
            existing_user.name = clean_name
        try:
            await db.commit()
            await db.refresh(existing_user)
            print(f"🟢 [USER REACTIVATED/UPDATED] User '{existing_user.name}' ({clean_wa_id}) is active in DB.")
        except Exception as e:
            await db.rollback()
            print(f"⚠️ [USER UPDATE ERROR] ({clean_wa_id}): {e}")

        if was_previously_deleted:
            # Clean up old orders from the deleted session so they never leak into the reactivated session
            old_orders_res = await db.execute(
                select(models.Orders).where(
                    models.Orders.sender_wa_number.in_(possible_numbers)
                )
            )
            old_orders = old_orders_res.scalars().all()
            for ord_obj in old_orders:
                if ord_obj.status in ["confirmed", "rider_accepted", "awaiting_pickup", "in_transit", "awaiting_dropoff"]:
                    if ord_obj.delivery_progression_status != "package_delivered":
                        ord_obj.status = "cancelled"
                ord_obj.sender_wa_number = f"DELETED_{clean_wa_id}"
            await db.commit()

        return existing_user

    # Brand-new user creation
    new_user = models.User(
        name=clean_name,
        wa_id=clean_wa_id,
        display_phone_number=clean_display,
        phone_number_id=clean_phone_id,
        is_deleted=False
    )

    db.add(new_user)
    try:
        await db.commit()
        await db.refresh(new_user)
        print(f"🟢 [USER SAVED] Registered new user '{clean_name}' ({clean_wa_id}) in DB.")
        return new_user
    except IntegrityError:
        await db.rollback()
        # Fallback: recover by fetching the existing record that triggered the unique constraint
        retry_res = await db.execute(
            select(models.User).where(
                (models.User.wa_id == clean_wa_id) |
                (models.User.wa_id.like(f"%{clean_wa_id}%"))
            )
        )
        recovered = retry_res.scalars().first()
        if recovered:
            recovered.is_deleted = False
            recovered.wa_id = clean_wa_id
            recovered.display_phone_number = clean_display
            recovered.phone_number_id = clean_phone_id
            if clean_name and clean_name != "Customer":
                recovered.name = clean_name
            await db.commit()
            await db.refresh(recovered)
            print(f"🟢 [USER RECOVERED] Recovered and reactivated user '{recovered.name}' ({clean_wa_id}).")
            return recovered
    except Exception as e:
        await db.rollback()
        print(f"❌ [USER CREATE ERROR] ({clean_wa_id}): {e}")

    return new_user




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
    # --- STEP 1: 10-MINUTE PROXIMITY NOTIFICATION ---
    await asyncio.sleep(delay)  # Initial delay after package pickup

    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        order = await replyhandler.get_active_ride_by_number(order_num, db)
        if not order or order.status in ["cancelled", "completed", "expired"]:
            return
        if order.delivery_progression_status == "package_delivered":
            return
        
        sender_res = await db.execute(
            select(models.User.name).where(
                models.User.wa_id.in_(replyhandler.get_phone_variants(sender_wa))
            )
        )
        sender_name = sender_res.scalars().first() or "Sender"

    # Step 1: Send ETA Check prompt strictly to the Rider first via interactive buttons
    await replyhandler.send_rider_eta_prompt(
        rider_wa_number=rider_wa,
        order_number=order_num,
        auth=auth,
        graph_url=graph_url
    )

    # --- STEP 2: VERIFICATION CODE & DROPOFF FLOW (5 mins after 10-min proximity alert) ---
    await asyncio.sleep(300)

    async with AsyncSessionLocal() as db:
        order = await replyhandler.get_active_ride_by_number(order_num, db)
        if not order or order.status in ["cancelled", "completed", "expired"]:
            return
        if order.delivery_progression_status == "package_delivered":
            return

        five_digit_code = order.verification_code or ''.join(random.choices(string.digits, k=5))
        if not order.verification_code:
            await db.execute(
                update(models.Orders)
                .where(models.Orders.order_number == order_num)
                .values(verification_code=five_digit_code)
            )
            await db.commit()
    message_for_sender = (
        f"🔐 *Delivery Verification Code (Backup)* 📦✨\n\n"
        f"Your rider is approaching the drop-off location for Order *{order_num}*!\n\n"
        f"🔑 Verification Code: 👉 *{five_digit_code}* 👈\n\n"
        f"ℹ️ *Good to Know:*\n\n"
        f"• You don't need to take any action right now. 👍\n\n"
        f"• We have sent this same code directly to your recipient so they can confirm delivery with the rider. 📱\n\n"
        f"• We're sharing it with you as a helpful backup just in case they need it! 🔄\n\n"
        f"⚠️ *Important Security Note:*\n"
        f"Please share this code *ONLY* with your recipient, *NEVER* directly with the rider! 🛡️"
    )
    message_for_rider = (
        f"🔐 *Drop-off Verification Code* 🛵💨\n\n"
        f"Order: *{order_num}*\n\n"
        f"📋 *Delivery Steps:*\n\n"
        f"1️⃣ Ask the recipient for their 5-digit verification code upon arrival. 🤝\n\n"
        f"2️⃣ Reply with the code directly in this chat (e.g. *{five_digit_code}*) or tap the button below to verify! 💬📱\n\n"
        f"⚠️ *Note:* You have 3 trials to enter the correct code."
    )
    message_for_recipient = (
        f"🛵💨 *Your Package Is Arriving Soon!* 📦✨\n\n"
        f"Great news! Your dispatch rider is now close to your location with your package from *{sender_name}*!\n\n"
        f"🔐 *Your Delivery Verification Code:*\n\n"
        f"👉  *{five_digit_code}*  👈\n\n"
        f"📋 *Instructions:*\n\n"
        f"• Please share this *5-digit code* with the rider when they arrive. 🤝\n\n"
        f"• The rider needs this code to safely complete your delivery. ✅\n\n"
        f"Thank you for choosing *InTime*! 🌟🚀"
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




