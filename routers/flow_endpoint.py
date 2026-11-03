import os
import json
import logging
from typing import Dict, Any, List
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
import models
from flow_crypto import decrypt_flow_request, encrypt_flow_response

logger = logging.getLogger("flow_endpoint")
router = APIRouter()

# Pricing and catalog constants for Madam G Kitchen
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
    "base_none": {"name": "No Base Meal (Sides/Proteins only)", "price": 0},
    # Soups (Ogbono + Egusi mix is same price ₦200)
    "soup_egusi": {"name": "Egusi Soup", "price": 200},
    "soup_ogbono": {"name": "Ogbono Soup", "price": 200},
    "soup_mixed": {"name": "Mixed (Ogbono & Egusi)", "price": 200},
    "soup_efo": {"name": "Vegetable (Efo Riro)", "price": 500},
    "soup_none": {"name": "No Soup", "price": 0},
    # Proteins
    "protein_chicken_small": {"name": "Small Chicken", "price": 3000},
    "protein_chicken_med": {"name": "Medium Chicken", "price": 3500},
    "protein_chicken_big": {"name": "Big Chicken", "price": 4000},
    "protein_beef_big_1": {"name": "Big Beef (1 piece)", "price": 500},
    "protein_beef_big_2": {"name": "Big Beef (2 pieces)", "price": 1000},
    "protein_beef_small_2": {"name": "Small Beef (2 pieces)", "price": 400},
    "protein_goat": {"name": "Goat Meat", "price": 500},
    "protein_goat_soup": {"name": "Goat Meat Pepper Soup", "price": 2000},
    "protein_egg_fried": {"name": "Fried Egg", "price": 1000},
    "protein_egg_boiled": {"name": "Boiled Egg", "price": 300},
    "protein_none": {"name": "No Protein", "price": 0},
    # Extras & Sides
    "extra_plantain_1": {"name": "Fried Plantain (1 serving)", "price": 500},
    "extra_plantain_2": {"name": "Fried Plantain (2 servings)", "price": 1000},
    "extra_moimoi_1": {"name": "Moi Moi (1 wrap)", "price": 1000},
    "extra_moimoi_2": {"name": "Moi Moi (2 wraps)", "price": 2000},
    "extra_salad": {"name": "Salad", "price": 500},
    # Drinks
    "drink_coke": {"name": "Coke", "price": 500},
    "drink_maltina": {"name": "Maltina", "price": 700},
    "drink_water": {"name": "Water", "price": 300},
    "drink_none": {"name": "No Drink", "price": 0},
}

# Popular pre-designed packs
PREDESIGNED_PACKS = {
    "pack_classic_jollof": {
        "title": "Madam G Classic Jollof",
        "description": "Jollof Rice + Medium Chicken + Fried Plantain",
        "price": 5300,
        "items": ["Jollof Rice (₦1,300)", "Medium Chicken (₦3,500)", "Plantain (₦500)"]
    },
    "pack_swallow_combo": {
        "title": "Madam G Swallow Special",
        "description": "Semo + Egusi Soup + Goat Meat",
        "price": 1400,
        "items": ["Semo (₦700)", "Egusi Soup (₦200)", "Goat Meat (₦500)"]
    },
    "pack_fried_feast": {
        "title": "Madam G Fried Feast",
        "description": "Fried Rice + Big Beef (2 pcs) + Salad + Coke",
        "price": 3300,
        "items": ["Fried Rice (₦1,300)", "Big Beef 2pcs (₦1,000)", "Salad (₦500)", "Coke (₦500)"]
    },
    "pack_rice_beans": {
        "title": "White Rice & Beans Special",
        "description": "White Rice and Beans + Big Beef (1 pc) + Plantain",
        "price": 2300,
        "items": ["White Rice and Beans (₦1,300)", "Big Beef 1pc (₦500)", "Plantain (₦500)"]
    }
}

LOGO_URL = "https://fastapiforwhatsappwebhook-production.up.railway.app/static/madam_g_logo.jpg"


def calculate_pack_price(pack_data: dict) -> tuple[int, list[str]]:
    """Calculates total price and item descriptions for a custom pack."""
    total = 0
    items = []

    # Base
    base_key = pack_data.get("base_meal")
    if base_key and base_key in MEAL_PRICES:
        item = MEAL_PRICES[base_key]
        if item["price"] > 0:
            total += item["price"]
            items.append(f"{item['name']} (₦{item['price']:,})")

    # Soup
    soup_key = pack_data.get("soup")
    if soup_key and soup_key in MEAL_PRICES:
        item = MEAL_PRICES[soup_key]
        if item["price"] > 0:
            total += item["price"]
            items.append(f"{item['name']} (₦{item['price']:,})")

    # Protein
    protein_key = pack_data.get("protein")
    if protein_key and protein_key in MEAL_PRICES:
        item = MEAL_PRICES[protein_key]
        if item["price"] > 0:
            total += item["price"]
            items.append(f"{item['name']} (₦{item['price']:,})")

    # Extras (can be a list of keys)
    extras = pack_data.get("extras", [])
    if isinstance(extras, str):
        extras = [extras]
    for ext_key in extras:
        if ext_key in MEAL_PRICES:
            item = MEAL_PRICES[ext_key]
            if item["price"] > 0:
                total += item["price"]
                items.append(f"{item['name']} (₦{item['price']:,})")

    # Drink
    drink_key = pack_data.get("drink")
    if drink_key and drink_key in MEAL_PRICES:
        item = MEAL_PRICES[drink_key]
        if item["price"] > 0:
            total += item["price"]
            items.append(f"{item['name']} (₦{item['price']:,})")

    qty = int(pack_data.get("quantity") or 1)
    pack_total = total * max(1, qty)
    return pack_total, items


def format_cart_display(cart_packs: list[dict]) -> tuple[str, int]:
    """Formats cart items into user-facing text and computes food subtotal."""
    if not cart_packs:
        return "Your cart is empty.", 0

    lines = []
    grand_total = 0
    for idx, pack in enumerate(cart_packs, 1):
        name = pack.get("pack_name", f"Pack {idx}")
        qty = pack.get("quantity", 1)
        price = pack.get("total_price", 0)
        items_summary = " + ".join(pack.get("items", []))
        instructions = f" (Note: {pack['note']})" if pack.get("note") else ""
        lines.append(f"📦 *{name}* (x{qty}) - ₦{price:,}\n   _{items_summary}_{instructions}")
        grand_total += price

    return "\n\n".join(lines), grand_total


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

        # Parse flow token data
        flow_token = {}
        if flow_token_raw:
            try:
                flow_token = json.loads(flow_token_raw) if isinstance(flow_token_raw, str) else flow_token_raw
            except Exception:
                flow_token = {"sender_wa_number": str(flow_token_raw)}

        sender_wa = flow_token.get("sender_wa_number", "")

        # 2. INIT action (Flow opens on user's phone)
        if action == "INIT":
            # Check database for returning user's saved address and phone
            saved_address = ""
            saved_phone = sender_wa
            has_previous = False

            if sender_wa:
                # Query last food order from this customer
                q = (
                    select(models.Orders)
                    .where(models.Orders.sender_wa_number.like(f"%{sender_wa[-10:]}"))
                    .where(models.Orders.dropoff_location_name.isnot(None))
                    .order_by(models.Orders.created_at.desc())
                    .limit(1)
                )
                res = await db.execute(q)
                last_order = res.scalars().first()
                if last_order and last_order.dropoff_location_name:
                    saved_address = last_order.dropoff_location_name
                    saved_phone = last_order.recipient_phone_number or sender_wa
                    has_previous = True

            if has_previous:
                # Returning customer -> Show address confirmation prompt
                resp_payload = {
                    "version": "3.0",
                    "screen": "CONFIRM_ADDRESS_SCREEN",
                    "data": {
                        "saved_address": saved_address,
                        "saved_phone": saved_phone,
                        "address_display": f"📍 Saved Address: {saved_address}\n📞 Contact Phone: {saved_phone}",
                        "use_previous": "yes"
                    }
                }
            else:
                # New customer -> Directly show address input screen
                resp_payload = {
                    "version": "3.0",
                    "screen": "ENTER_ADDRESS_SCREEN",
                    "data": {
                        "delivery_address": "",
                        "contact_phone": saved_phone
                    }
                }

            enc_response = encrypt_flow_response(resp_payload, aes_key, iv_bytes)
            return Response(content=enc_response, media_type="text/plain")

        # 3. DATA_EXCHANGE action (User interacts with screens)
        if action == "data_exchange":
            user_action = data.get("user_action") or ""
            current_cart = data.get("cart_packs", [])
            delivery_address = data.get("delivery_address") or data.get("saved_address", "")
            contact_phone = data.get("contact_phone") or data.get("saved_phone", sender_wa)
            restaurant = data.get("restaurant", "Madam G Kitchen")

            # --- SCREEN: CONFIRM_ADDRESS_SCREEN ---
            if screen == "CONFIRM_ADDRESS_SCREEN":
                use_prev = data.get("use_previous", "yes")
                if use_prev == "yes":
                    # Proceed to Restaurant Screen with saved info
                    resp_payload = {
                        "version": "3.0",
                        "screen": "SELECT_RESTAURANT_SCREEN",
                        "data": {
                            "delivery_address": delivery_address,
                            "contact_phone": contact_phone,
                            "restaurant": "Madam G Kitchen"
                        }
                    }
                else:
                    # User wants to enter new address & contact
                    resp_payload = {
                        "version": "3.0",
                        "screen": "ENTER_ADDRESS_SCREEN",
                        "data": {
                            "delivery_address": "",
                            "contact_phone": contact_phone
                        }
                    }
                enc_response = encrypt_flow_response(resp_payload, aes_key, iv_bytes)
                return Response(content=enc_response, media_type="text/plain")

            # --- SCREEN: ENTER_ADDRESS_SCREEN ---
            elif screen == "ENTER_ADDRESS_SCREEN":
                entered_addr = data.get("delivery_address", "").strip()
                entered_phone = data.get("contact_phone", "").strip() or sender_wa

                resp_payload = {
                    "version": "3.0",
                    "screen": "SELECT_RESTAURANT_SCREEN",
                    "data": {
                        "delivery_address": entered_addr,
                        "contact_phone": entered_phone,
                        "restaurant": "Madam G Kitchen"
                    }
                }
                enc_response = encrypt_flow_response(resp_payload, aes_key, iv_bytes)
                return Response(content=enc_response, media_type="text/plain")

            # --- SCREEN: SELECT_RESTAURANT_SCREEN ---
            elif screen == "SELECT_RESTAURANT_SCREEN":
                selected_rest = data.get("restaurant", "Madam G Kitchen")
                # Show Menu Choice (Pre-designed Packs vs Custom Pack Builder) with Madam G logo
                resp_payload = {
                    "version": "3.0",
                    "screen": "MENU_CHOICE_SCREEN",
                    "data": {
                        "delivery_address": delivery_address,
                        "contact_phone": contact_phone,
                        "restaurant": selected_rest,
                        "restaurant_logo": LOGO_URL,
                        "cart_packs": current_cart
                    }
                }
                enc_response = encrypt_flow_response(resp_payload, aes_key, iv_bytes)
                return Response(content=enc_response, media_type="text/plain")

            # --- SCREEN: MENU_CHOICE_SCREEN ---
            elif screen == "MENU_CHOICE_SCREEN":
                choice = data.get("menu_choice", "predesigned")
                if choice == "custom":
                    # Navigate to Custom Pack Builder
                    resp_payload = {
                        "version": "3.0",
                        "screen": "BUILD_CUSTOM_PACK_SCREEN",
                        "data": {
                            "delivery_address": delivery_address,
                            "contact_phone": contact_phone,
                            "restaurant": restaurant,
                            "restaurant_logo": LOGO_URL,
                            "cart_packs": current_cart,
                            "pack_quantity": "1"
                        }
                    }
                else:
                    # Navigate to Pre-designed Packs Screen
                    resp_payload = {
                        "version": "3.0",
                        "screen": "PREDESIGNED_PACKS_SCREEN",
                        "data": {
                            "delivery_address": delivery_address,
                            "contact_phone": contact_phone,
                            "restaurant": restaurant,
                            "restaurant_logo": LOGO_URL,
                            "cart_packs": current_cart,
                            "pack_quantity": "1"
                        }
                    }
                enc_response = encrypt_flow_response(resp_payload, aes_key, iv_bytes)
                return Response(content=enc_response, media_type="text/plain")

            # --- SCREEN: PREDESIGNED_PACKS_SCREEN (Add Combo) ---
            elif screen == "PREDESIGNED_PACKS_SCREEN":
                if user_action == "switch_to_custom":
                    resp_payload = {
                        "version": "3.0",
                        "screen": "BUILD_CUSTOM_PACK_SCREEN",
                        "data": {
                            "delivery_address": delivery_address,
                            "contact_phone": contact_phone,
                            "restaurant": restaurant,
                            "restaurant_logo": LOGO_URL,
                            "cart_packs": current_cart,
                            "pack_quantity": "1"
                        }
                    }
                else:
                    # User picked a pre-designed combo
                    combo_key = data.get("selected_pack", "pack_classic_jollof")
                    combo_info = PREDESIGNED_PACKS.get(combo_key, PREDESIGNED_PACKS["pack_classic_jollof"])
                    qty = int(data.get("pack_quantity") or 1)
                    pack_note = data.get("pack_note", "")

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

                    resp_payload = {
                        "version": "3.0",
                        "screen": "CART_REVIEW_SCREEN",
                        "data": {
                            "delivery_address": delivery_address,
                            "contact_phone": contact_phone,
                            "restaurant": restaurant,
                            "restaurant_logo": LOGO_URL,
                            "cart_packs": current_cart,
                            "cart_display": cart_text,
                            "subtotal_text": f"₦{subtotal:,}",
                            "delivery_text": f"₦{est_delivery:,}",
                            "total_text": f"₦{grand_total:,}",
                            "cart_count": len(current_cart)
                        }
                    }
                enc_response = encrypt_flow_response(resp_payload, aes_key, iv_bytes)
                return Response(content=enc_response, media_type="text/plain")

            # --- SCREEN: BUILD_CUSTOM_PACK_SCREEN (Add Custom Pack) ---
            elif screen == "BUILD_CUSTOM_PACK_SCREEN":
                pack_name = f"Custom Pack {len(current_cart) + 1}"
                qty = int(data.get("pack_quantity") or 1)
                pack_price, items_list = calculate_pack_price(data)
                pack_note = data.get("pack_note", "")

                new_pack = {
                    "pack_name": pack_name,
                    "quantity": qty,
                    "unit_price": pack_price // max(1, qty),
                    "total_price": pack_price,
                    "items": items_list,
                    "note": pack_note
                }
                current_cart.append(new_pack)

                cart_text, subtotal = format_cart_display(current_cart)
                est_delivery = 1000
                grand_total = subtotal + est_delivery

                resp_payload = {
                    "version": "3.0",
                    "screen": "CART_REVIEW_SCREEN",
                    "data": {
                        "delivery_address": delivery_address,
                        "contact_phone": contact_phone,
                        "restaurant": restaurant,
                        "restaurant_logo": LOGO_URL,
                        "cart_packs": current_cart,
                        "cart_display": cart_text,
                        "subtotal_text": f"₦{subtotal:,}",
                        "delivery_text": f"₦{est_delivery:,}",
                        "total_text": f"₦{grand_total:,}",
                        "cart_count": len(current_cart)
                    }
                }
                enc_response = encrypt_flow_response(resp_payload, aes_key, iv_bytes)
                return Response(content=enc_response, media_type="text/plain")

            # --- SCREEN: CART_REVIEW_SCREEN ---
            elif screen == "CART_REVIEW_SCREEN":
                if user_action == "add_more":
                    # User clicked "Add Another Pack" -> Return to menu choice
                    resp_payload = {
                        "version": "3.0",
                        "screen": "MENU_CHOICE_SCREEN",
                        "data": {
                            "delivery_address": delivery_address,
                            "contact_phone": contact_phone,
                            "restaurant": restaurant,
                            "restaurant_logo": LOGO_URL,
                            "cart_packs": current_cart
                        }
                    }
                elif user_action.startswith("delete_pack_"):
                    # User clicked Delete on a specific pack
                    try:
                        del_idx = int(user_action.replace("delete_pack_", ""))
                        if 0 <= del_idx < len(current_cart):
                            current_cart.pop(del_idx)
                    except Exception as e:
                        logger.warning(f"Error deleting pack: {e}")

                    cart_text, subtotal = format_cart_display(current_cart)
                    est_delivery = 1000 if current_cart else 0
                    grand_total = subtotal + est_delivery

                    resp_payload = {
                        "version": "3.0",
                        "screen": "CART_REVIEW_SCREEN",
                        "data": {
                            "delivery_address": delivery_address,
                            "contact_phone": contact_phone,
                            "restaurant": restaurant,
                            "restaurant_logo": LOGO_URL,
                            "cart_packs": current_cart,
                            "cart_display": cart_text,
                            "subtotal_text": f"₦{subtotal:,}",
                            "delivery_text": f"₦{est_delivery:,}",
                            "total_text": f"₦{grand_total:,}",
                            "cart_count": len(current_cart)
                        }
                    }
                elif user_action == "checkout" or user_action == "place_order":
                    # Complete order submission payload
                    cart_text, subtotal = format_cart_display(current_cart)
                    est_delivery = 1000
                    grand_total = subtotal + est_delivery

                    resp_payload = {
                        "version": "3.0",
                        "screen": "ORDER_SUCCESS_SCREEN",
                        "data": {
                            "extension_message_response": {
                                "params": {
                                    "flow_name": "food_order_dynamic",
                                    "restaurant": restaurant,
                                    "delivery_address": delivery_address,
                                    "contact_phone": contact_phone,
                                    "cart_packs": json.dumps(current_cart),
                                    "subtotal": subtotal,
                                    "delivery_fee": est_delivery,
                                    "total_amount": grand_total,
                                    "cart_summary": cart_text
                                }
                            }
                        }
                    }
                else:
                    # Default: refresh cart review
                    cart_text, subtotal = format_cart_display(current_cart)
                    est_delivery = 1000
                    grand_total = subtotal + est_delivery

                    resp_payload = {
                        "version": "3.0",
                        "screen": "CART_REVIEW_SCREEN",
                        "data": {
                            "delivery_address": delivery_address,
                            "contact_phone": contact_phone,
                            "restaurant": restaurant,
                            "restaurant_logo": LOGO_URL,
                            "cart_packs": current_cart,
                            "cart_display": cart_text,
                            "subtotal_text": f"₦{subtotal:,}",
                            "delivery_text": f"₦{est_delivery:,}",
                            "total_text": f"₦{grand_total:,}",
                            "cart_count": len(current_cart)
                        }
                    }

                enc_response = encrypt_flow_response(resp_payload, aes_key, iv_bytes)
                return Response(content=enc_response, media_type="text/plain")

        # Unknown action fallback
        resp_payload = {
            "version": "3.0",
            "screen": "CONFIRM_ADDRESS_SCREEN",
            "data": {"status": "ok"}
        }
        enc_response = encrypt_flow_response(resp_payload, aes_key, iv_bytes)
        return Response(content=enc_response, media_type="text/plain")

    except Exception as e:
        logger.error(f"Flow endpoint error: {e}", exc_info=True)
        # WhatsApp expects HTTP 421 if decryption / signature fails
        raise HTTPException(status_code=421, detail=str(e))
