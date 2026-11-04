import os
import json
import logging
import base64
from typing import Dict, Any, List
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
import models
from flow_crypto import decrypt_flow_request, encrypt_flow_response

logger = logging.getLogger("flow_endpoint")
router = APIRouter()

# Pricing and catalog constants for Madam G Restaurant
MEAL_PRICES = {
    # Rice meals (All single price ₦1,300)
    "rice_jollof": {"name": "Jollof Rice", "price": 1300},
    "rice_fried": {"name": "Fried Rice", "price": 1300},
    "rice_white": {"name": "White Rice", "price": 1300},
    "rice_mixed": {"name": "Mixed (Fried & Jollof)", "price": 1300},
    "rice_white_beans": {"name": "White Rice and Beans", "price": 1300},
    # Swallows
    "swallow_semo": {"name": "Semo", "price": 700},
    "swallow_fufu": {"name": "Fufu", "price": 700},
    "base_moimoi": {"name": "Moi Moi Base", "price": 1000},
    "base_none": {"name": "No Base Meal", "price": 0},
    # Soups (Ogbono + Egusi mix is same single price ₦200)
    "soup_stew": {"name": "Stew", "price": 0},
    "soup_egusi": {"name": "Egusi Soup", "price": 200},
    "soup_ogbono": {"name": "Ogbono Soup", "price": 200},
    "soup_mixed": {"name": "Mixed (Ogbono & Egusi)", "price": 200},
    "soup_efo": {"name": "Vegetable (Efo Riro)", "price": 500},
    "soup_none": {"name": "No Soup", "price": 0},
    # Proteins
    "chicken_none": {"name": "No Chicken", "price": 0},
    "protein_chicken_small": {"name": "Small Chicken", "price": 3000},
    "protein_chicken_med": {"name": "Medium Chicken", "price": 3500},
    "protein_chicken_big": {"name": "Big Chicken", "price": 4000},
    "fish_none": {"name": "No Fish", "price": 0},
    "protein_fish": {"name": "Fried Fish", "price": 1000},
    # Extras & Sides
    "extra_plantain_1": {"name": "Plantain 1 serv", "price": 500},
    "extra_plantain_2": {"name": "Plantain 2 serv", "price": 1000},
    "extra_moimoi_1": {"name": "Moi Moi 1 wrap", "price": 1000},
    "extra_moimoi_2": {"name": "Moi Moi 2 wraps", "price": 2000},
    "extra_salad": {"name": "Salad", "price": 500},
    "extra_pepper_sauce": {"name": "Pepper Sauce", "price": 200},
    # Drinks
    "drink_coke": {"name": "Coke/Fanta/Sprite", "price": 500},
    "drink_malt": {"name": "Maltina/Amstel", "price": 600},
    "drink_water": {"name": "Water", "price": 300},
    "drink_chivita": {"name": "Chivita Juice", "price": 1500},
    "drink_none": {"name": "No Drink", "price": 0},
}

# Popular pre-designed packs
PREDESIGNED_PACKS = {
    "pack_classic_jollof": {
        "title": "Classic Jollof Pack",
        "description": "Jollof Rice + Medium Chicken + Plantain",
        "price": 5300,
        "items": ["Jollof Rice (₦1,300)", "Medium Chicken (₦3,500)", "Plantain (₦500)"]
    },
    "pack_swallow_special": {
        "title": "Swallow Special",
        "description": "Semo + Egusi Soup + 1x Goat Meat",
        "price": 1400,
        "items": ["Semo (₦700)", "Egusi Soup (₦200)", "1x Goat Meat (₦500)"]
    },
    "pack_fried_feast": {
        "title": "Fried Feast",
        "description": "Fried Rice + 2x Beef + Salad + Coke",
        "price": 3300,
        "items": ["Fried Rice (₦1,300)", "2x Beef (₦400)", "Salad (₦500)", "Plantain 1 serv (₦500)", "Coke (₦500)"]
    },
    "pack_rice_beans": {
        "title": "Rice & Beans Combo",
        "description": "White Rice and Beans + Stew + 2x Beef + Plantain",
        "price": 2300,
        "items": ["White Rice & Beans (₦1,300)", "Stew (₦0)", "2x Beef (₦400)", "Plantain (₦500)"]
    }
}

# Load Base64 logo data URI for fast and offline image rendering on mobile WhatsApp
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
LOGO_THUMB_PATH = os.path.join(STATIC_DIR, "madam_g_logo_thumb.jpg")
LOGO_RAW_PATH = os.path.join(STATIC_DIR, "madam_g_logo.jpg")

LOGO_DATA_URI = "https://fastapiforwhatsappwebhook-production.up.railway.app/static/madam_g_logo.jpg"
for p in [LOGO_THUMB_PATH, LOGO_RAW_PATH]:
    if os.path.exists(p):
        try:
            with open(p, "rb") as f:
                b64_str = base64.b64encode(f.read()).decode("utf-8")
            LOGO_DATA_URI = f"data:image/jpeg;base64,{b64_str}"
            break
        except Exception as e:
            logger.warning(f"Failed to encode logo from {p}: {e}")


def calculate_pack_price(pack_data: dict) -> tuple[int, int, int, list[str]]:
    """Calculates total pack price, unit price, quantity, and item descriptions."""
    unit_price = 0
    items = []

    # 1. Base meal
    base_key = pack_data.get("base_meal")
    if base_key and base_key in MEAL_PRICES:
        item = MEAL_PRICES[base_key]
        if item["price"] > 0:
            unit_price += item["price"]
            items.append(f"{item['name']} (₦{item['price']:,})")
        elif item["name"] != "No Base Meal":
            items.append(item["name"])

    # 2. Soup choice
    soup_key = pack_data.get("soup")
    if soup_key and soup_key in MEAL_PRICES:
        item = MEAL_PRICES[soup_key]
        if item["price"] > 0:
            unit_price += item["price"]
            items.append(f"{item['name']} (₦{item['price']:,})")
        elif item["name"] not in ["No Soup"]:
            items.append(item["name"])

    # 3. Protein Quantities
    # Beef (₦200/pc)
    try:
        beef_qty = int(str(pack_data.get("beef_qty") or "0").strip())
    except (ValueError, TypeError):
        beef_qty = 0
    if beef_qty > 0:
        beef_cost = beef_qty * 200
        unit_price += beef_cost
        items.append(f"{beef_qty}x Beef (₦{beef_cost:,})")

    # Boiled Egg (₦300/pc)
    try:
        egg_qty = int(str(pack_data.get("egg_qty") or "0").strip())
    except (ValueError, TypeError):
        egg_qty = 0
    if egg_qty > 0:
        egg_cost = egg_qty * 300
        unit_price += egg_cost
        items.append(f"{egg_qty}x Egg (₦{egg_cost:,})")

    # Goat Meat (₦500/pc)
    try:
        goat_qty = int(str(pack_data.get("goat_qty") or "0").strip())
    except (ValueError, TypeError):
        goat_qty = 0
    if goat_qty > 0:
        goat_cost = goat_qty * 500
        unit_price += goat_cost
        items.append(f"{goat_qty}x Goat Meat (₦{goat_cost:,})")

    # Chicken (Small 3000, Med 3500, Big 4000)
    chicken_key = pack_data.get("chicken")
    if chicken_key and chicken_key in MEAL_PRICES:
        item = MEAL_PRICES[chicken_key]
        if item["price"] > 0:
            unit_price += item["price"]
            items.append(f"{item['name']} (₦{item['price']:,})")

    # Fish (₦1,000)
    fish_key = pack_data.get("fish")
    if fish_key and fish_key in MEAL_PRICES:
        item = MEAL_PRICES[fish_key]
        if item["price"] > 0:
            unit_price += item["price"]
            items.append(f"{item['name']} (₦{item['price']:,})")

    # 4. Sides & Extras
    extras = pack_data.get("extras", [])
    if isinstance(extras, str):
        extras = [extras] if extras else []
    for ext_key in extras:
        if ext_key in MEAL_PRICES:
            item = MEAL_PRICES[ext_key]
            if item["price"] > 0:
                unit_price += item["price"]
                items.append(f"{item['name']} (₦{item['price']:,})")

    # 5. Drink
    drink_key = pack_data.get("drink")
    if drink_key and drink_key in MEAL_PRICES:
        item = MEAL_PRICES[drink_key]
        if item["price"] > 0:
            unit_price += item["price"]
            items.append(f"{item['name']} (₦{item['price']:,})")

    # Pack multiplier
    try:
        multiplier = max(1, int(str(pack_data.get("pack_quantity") or "1").strip()))
    except (ValueError, TypeError):
        multiplier = 1

    total_pack_price = unit_price * multiplier
    return total_pack_price, unit_price, multiplier, items


def format_cart_display(cart_packs: list[dict]) -> tuple[str, int]:
    """Formats cart items into user-facing text and computes food subtotal."""
    if not cart_packs:
        return "Your cart is empty.", 0

    lines = []
    subtotal = 0
    for idx, pack in enumerate(cart_packs, 1):
        name = pack.get("pack_name", f"Pack {idx}")
        qty = pack.get("quantity", 1)
        total = pack.get("total_price", 0)
        items_summary = " + ".join(pack.get("items", []))
        note = f" (Note: {pack['note']})" if pack.get("note") else ""
        lines.append(f"📦 *{name}* (x{qty}) - ₦{total:,}\n   _{items_summary}_{note}")
        subtotal += total

    return "\n\n".join(lines), subtotal


@router.post("/flow/endpoint")
async def flow_endpoint(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Encrypted WhatsApp Flows Interactive Endpoint.
    Handles 'ping', 'INIT', and dynamic multi-screen 'data_exchange' for Food Orders.
    """
    try:
        body = await request.json()
        enc_aes_key = body.get("encrypted_aes_key")
        enc_flow_data = body.get("encrypted_flow_data")
        iv = body.get("initial_vector")

        if not enc_aes_key or not enc_flow_data or not iv:
            raise HTTPException(status_code=400, detail="Missing required encrypted payload fields")

        # Decrypt incoming payload
        decrypted_data, aes_key, iv_bytes = decrypt_flow_request(enc_aes_key, enc_flow_data, iv)
        action = decrypted_data.get("action")
        screen = decrypted_data.get("screen")
        data = decrypted_data.get("data", {})
        flow_token_raw = decrypted_data.get("flow_token", "")

        logger.info(f"Flow request: action={action}, screen={screen}, flow_token={flow_token_raw}")

        # 1. Health check from Meta Flow builder
        if action == "ping":
            resp_payload = {
                "version": "3.0",
                "data": {"status": "active"}
            }
            enc_response = encrypt_flow_response(resp_payload, aes_key, iv_bytes)
            return Response(content=enc_response, media_type="text/plain")

        # Handle native Back button action
        if action == "BACK":
            resp_payload = {
                "version": "3.0",
                "data": {"status": "active"}
            }
            enc_response = encrypt_flow_response(resp_payload, aes_key, iv_bytes)
            return Response(content=enc_response, media_type="text/plain")

        # Parse flow token data
        flow_token = {}
        if flow_token_raw:
            try:
                flow_token = json.loads(flow_token_raw) if isinstance(flow_token_raw, str) else flow_token_raw
            except Exception:
                flow_token = {"sender_wa_number": str(flow_token_raw)}

        sender_wa = flow_token.get("sender_wa_number", "")

        # 2. Opening the Flow (action can be INIT, navigate, or initial data_exchange)
        is_opening_request = (
            action in ["INIT", "navigate"] or
            (action == "data_exchange" and not screen and not data.get("user_action") and not data.get("selected_pack") and not data.get("base_meal") and not data.get("use_previous"))
        )
        if is_opening_request:
            saved_address = ""
            saved_phone = sender_wa
            has_previous = False

            if sender_wa:
                try:
                    q = (
                        select(models.Orders)
                        .where(models.Orders.sender_wa_number.like(f"%{sender_wa[-10:]}"))
                        .where(models.Orders.dropoff_location_name.isnot(None))
                        .order_by(models.Orders.created_at.desc())
                        .limit(1)
                    )
                    res = await db.execute(q)
                    last_order = res.scalars().first()
                    if last_order and last_order.dropoff_location_name and last_order.dropoff_location_name.strip():
                        saved_address = last_order.dropoff_location_name.strip()
                        saved_phone = (last_order.recipient_phone_number or sender_wa).strip()
                        has_previous = True
                except Exception as db_err:
                    logger.warning(f"Error querying previous orders for {sender_wa}: {db_err}")

            if has_previous and saved_address:
                # Returning customer -> Show address confirmation prompt
                resp_payload = {
                    "version": "3.0",
                    "screen": "CONFIRM_ADDRESS_SCREEN",
                    "data": {
                        "saved_address": saved_address,
                        "saved_phone": saved_phone,
                        "address_display": f"📍 Saved Address: {saved_address}\n📞 Receiver's Phone: {saved_phone}",
                        "use_previous": "yes"
                    }
                }
            else:
                # New customer -> Directly show RECOMMEND address input screen
                resp_payload = {
                    "version": "3.0",
                    "screen": "RECOMMEND",
                    "data": {
                        "screen_0_HouseFlat_Number_0": "",
                        "screen_0_Street_Name_1": "",
                        "screen_0_Receivers_Number_2": saved_phone
                    }
                }

            enc_response = encrypt_flow_response(resp_payload, aes_key, iv_bytes)
            return Response(content=enc_response, media_type="text/plain")

        # 3. DATA_EXCHANGE action (User interacts with screens)
        if action == "data_exchange":
            user_action = data.get("user_action") or ""
            
            # Safe parsing of cart
            current_cart = data.get("cart_packs", [])
            if isinstance(current_cart, str):
                try:
                    current_cart = json.loads(current_cart) if current_cart else []
                except Exception:
                    current_cart = []
            if not isinstance(current_cart, list):
                current_cart = []

            # Extract address fields from previous or current screens
            house_num = data.get("HouseFlat_Number_801bd0") or data.get("screen_0_HouseFlat_Number_0", "")
            street_name = data.get("Street_Name_17f2ce") or data.get("screen_0_Street_Name_1", "")
            if street_name:
                delivery_address = f"{house_num}, {street_name}".strip(", ")
            else:
                delivery_address = data.get("delivery_address") or data.get("saved_address", "")

            contact_phone = (
                data.get("Receivers_Number_eb5784") or 
                data.get("screen_0_Receivers_Number_2") or 
                data.get("contact_phone") or 
                data.get("saved_phone", sender_wa)
            )

            # Extract restaurant
            rest_input = data.get("Restaurants_e39410") or data.get("restaurant", "Madam G Restaurant")
            if isinstance(rest_input, list):
                restaurant = rest_input[0] if rest_input else "Madam G Restaurant"
            else:
                restaurant = str(rest_input)
            if "madam" in restaurant.lower():
                restaurant = "Madam G Restaurant"

            # --- SCREEN: CONFIRM_ADDRESS_SCREEN ---
            if screen == "CONFIRM_ADDRESS_SCREEN":
                use_prev = data.get("use_previous", "yes")
                if use_prev == "yes":
                    # Proceed directly to Restaurant selection (RATE)
                    resp_payload = {
                        "version": "3.0",
                        "screen": "RATE",
                        "data": {
                            "delivery_address": delivery_address,
                            "contact_phone": contact_phone,
                            "screen_0_HouseFlat_Number_0": house_num,
                            "screen_0_Street_Name_1": street_name or delivery_address,
                            "screen_0_Receivers_Number_2": contact_phone
                        }
                    }
                else:
                    # User chose to enter new address -> navigate to RECOMMEND
                    resp_payload = {
                        "version": "3.0",
                        "screen": "RECOMMEND",
                        "data": {
                            "screen_0_HouseFlat_Number_0": "",
                            "screen_0_Street_Name_1": "",
                            "screen_0_Receivers_Number_2": contact_phone
                        }
                    }
                enc_response = encrypt_flow_response(resp_payload, aes_key, iv_bytes)
                return Response(content=enc_response, media_type="text/plain")

            # --- SCREEN: RECOMMEND (Address Entry) ---
            elif screen == "RECOMMEND":
                resp_payload = {
                    "version": "3.0",
                    "screen": "RATE",
                    "data": {
                        "delivery_address": delivery_address,
                        "contact_phone": contact_phone,
                        "screen_0_HouseFlat_Number_0": house_num,
                        "screen_0_Street_Name_1": street_name,
                        "screen_0_Receivers_Number_2": contact_phone
                    }
                }
                enc_response = encrypt_flow_response(resp_payload, aes_key, iv_bytes)
                return Response(content=enc_response, media_type="text/plain")

            # --- SCREEN: RATE (Pick Restaurant) ---
            elif screen == "RATE":
                resp_payload = {
                    "version": "3.0",
                    "screen": "PREDESIGNED_PACKS_SCREEN",
                    "data": {
                        "delivery_address": delivery_address,
                        "contact_phone": contact_phone,
                        "restaurant": restaurant,
                        "restaurant_logo": LOGO_DATA_URI,
                        "cart_packs": current_cart
                    }
                }
                enc_response = encrypt_flow_response(resp_payload, aes_key, iv_bytes)
                return Response(content=enc_response, media_type="text/plain")

            # --- SCREEN: PREDESIGNED_PACKS_SCREEN ---
            elif screen == "PREDESIGNED_PACKS_SCREEN":
                combo_key = data.get("selected_pack", "skip_to_custom")
                if combo_key == "skip_to_custom" or user_action == "switch_to_custom":
                    resp_payload = {
                        "version": "3.0",
                        "screen": "BUILD_CUSTOM_PACK_SCREEN",
                        "data": {
                            "delivery_address": delivery_address,
                            "contact_phone": contact_phone,
                            "restaurant": restaurant,
                            "restaurant_logo": LOGO_DATA_URI,
                            "cart_packs": current_cart
                        }
                    }
                else:
                    combo_info = PREDESIGNED_PACKS.get(combo_key, PREDESIGNED_PACKS["pack_classic_jollof"])
                    try:
                        qty = max(1, int(str(data.get("pack_quantity") or "1").strip()))
                    except (ValueError, TypeError):
                        qty = 1
                    pack_note = (data.get("pack_note") or "").strip()

                    new_pack = {
                        "pack_name": combo_info["title"],
                        "quantity": qty,
                        "unit_price": combo_info["price"],
                        "total_price": combo_info["price"] * qty,
                        "items": combo_info["items"],
                        "note": pack_note
                    }
                    current_cart.append(new_pack)

                    cart_text, subtotal = format_cart_display(current_cart)
                    est_delivery = 1000
                    grand_total = subtotal + est_delivery
                    totals_display = (
                        f"💵 Food Subtotal: ₦{subtotal:,}\n"
                        f"🛵 Delivery Fee: ₦{est_delivery:,}\n"
                        f"💳 *Grand Total: ₦{grand_total:,}*"
                    )

                    resp_payload = {
                        "version": "3.0",
                        "screen": "CART_REVIEW_SCREEN",
                        "data": {
                            "delivery_address": delivery_address,
                            "contact_phone": contact_phone,
                            "restaurant": restaurant,
                            "cart_packs": current_cart,
                            "cart_display": cart_text,
                            "totals_display": totals_display
                        }
                    }
                enc_response = encrypt_flow_response(resp_payload, aes_key, iv_bytes)
                return Response(content=enc_response, media_type="text/plain")

            # --- SCREENS: CUSTOM PACK BUILDERS (Pack 1, 2, 3, 4) ---
            elif screen in ["BUILD_CUSTOM_PACK_SCREEN", "BUILD_CUSTOM_PACK_TWO", "BUILD_CUSTOM_PACK_THREE", "BUILD_CUSTOM_PACK_FOUR"]:
                pack_idx = len(current_cart) + 1
                pack_note = (data.get("pack_note") or "").strip()
                pack_total, unit_price, qty, items_list = calculate_pack_price(data)

                pack_title = f"Pack {pack_idx}"
                if pack_note:
                    pack_title = f"Pack {pack_idx} ({pack_note[:15]})"

                new_pack = {
                    "pack_name": pack_title,
                    "quantity": qty,
                    "unit_price": unit_price,
                    "total_price": pack_total,
                    "items": items_list,
                    "note": pack_note
                }
                current_cart.append(new_pack)

                cart_text, subtotal = format_cart_display(current_cart)
                est_delivery = 1000
                grand_total = subtotal + est_delivery
                totals_display = (
                    f"💵 Food Subtotal: ₦{subtotal:,}\n"
                    f"🛵 Delivery Fee: ₦{est_delivery:,}\n"
                    f"💳 *Grand Total: ₦{grand_total:,}*"
                )

                next_action = data.get("next_action")
                if next_action == "add_another":
                    next_screen_map = {
                        "BUILD_CUSTOM_PACK_SCREEN": "BUILD_CUSTOM_PACK_TWO",
                        "BUILD_CUSTOM_PACK_TWO": "BUILD_CUSTOM_PACK_THREE",
                        "BUILD_CUSTOM_PACK_THREE": "BUILD_CUSTOM_PACK_FOUR"
                    }
                    target_screen = next_screen_map.get(screen, "CART_REVIEW_SCREEN")
                    resp_payload = {
                        "version": "3.0",
                        "screen": target_screen,
                        "data": {
                            "restaurant": restaurant,
                            "restaurant_logo": LOGO_DATA_URI,
                            "delivery_address": delivery_address,
                            "contact_phone": contact_phone,
                            "cart_packs": current_cart
                        }
                    }
                else:
                    resp_payload = {
                        "version": "3.0",
                        "screen": "CART_REVIEW_SCREEN",
                        "data": {
                            "restaurant": restaurant,
                            "delivery_address": delivery_address,
                            "contact_phone": contact_phone,
                            "cart_packs": current_cart,
                            "cart_display": cart_text,
                            "totals_display": totals_display
                        }
                    }
                enc_response = encrypt_flow_response(resp_payload, aes_key, iv_bytes)
                return Response(content=enc_response, media_type="text/plain")

            # --- SCREEN: CART_REVIEW_SCREEN ---
            elif screen == "CART_REVIEW_SCREEN":
                cart_text, subtotal = format_cart_display(current_cart)
                est_delivery = 1000
                grand_total = subtotal + est_delivery
                confirm_display = (
                    f"📍 *Delivery:* {delivery_address}\n"
                    f"📞 *Receiver:* {contact_phone}\n"
                    f"🍲 *Restaurant:* {restaurant}\n"
                    f"💳 *Total Amount:* ₦{grand_total:,}"
                )

                resp_payload = {
                    "version": "3.0",
                    "screen": "screen_itnvpz",
                    "data": {
                        "delivery_address": delivery_address,
                        "contact_phone": contact_phone,
                        "restaurant": restaurant,
                        "cart_packs": current_cart,
                        "subtotal": subtotal,
                        "delivery_fee": est_delivery,
                        "total_amount": grand_total,
                        "cart_summary": cart_text,
                        "confirm_display": confirm_display,
                        "screen_1_Restaurants_0": [restaurant],
                        "screen_0_HouseFlat_Number_0": house_num,
                        "screen_0_Street_Name_1": street_name or delivery_address,
                        "screen_0_Receivers_Number_2": contact_phone
                    }
                }
                enc_response = encrypt_flow_response(resp_payload, aes_key, iv_bytes)
                return Response(content=enc_response, media_type="text/plain")

        # Fallback (Safe default with all required data keys so client never crashes)
        resp_payload = {
            "version": "3.0",
            "screen": "CONFIRM_ADDRESS_SCREEN",
            "data": {
                "saved_address": "",
                "saved_phone": sender_wa or "",
                "address_display": "Please confirm or enter your delivery address to proceed.",
                "use_previous": "no"
            }
        }
        enc_response = encrypt_flow_response(resp_payload, aes_key, iv_bytes)
        return Response(content=enc_response, media_type="text/plain")

    except Exception as e:
        logger.error(f"Flow endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=421, detail=str(e))
