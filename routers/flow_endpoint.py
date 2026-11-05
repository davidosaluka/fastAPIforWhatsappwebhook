import os
import json
import logging
import base64
import re
from typing import Dict, Any, List
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from sqlalchemy import select, update
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
        "description": "1 Wrap Semo + Egusi Soup + 1x Goat Meat",
        "price": 1400,
        "items": ["1 Wrap Semo (₦700)", "Egusi Soup (₦200)", "1x Goat Meat (₦500)"]
    },
    "pack_fried_feast": {
        "title": "Fried Feast",
        "description": "Fried Rice + 2x Big Beef + Salad + Coke",
        "price": 3300,
        "items": ["Fried Rice (₦1,300)", "2x Big Beef (₦1,000)", "Salad (₦500)", "Coke (₦500)"]
    },
    "pack_rice_beans": {
        "title": "Rice & Beans Combo",
        "description": "White Rice and Beans + 2x Small Beef + Plantain",
        "price": 2200,
        "items": ["White Rice & Beans (₦1,300)", "Stew (₦0)", "2x Small Beef (₦400)", "Plantain (₦500)"]
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


def calculate_delivery_fee(pack_count: int) -> int:
    """
    Tiered delivery fee:
    - Up to 9 packs: ₦800
    - 10 to 15 packs: ₦1,000
    - 16 to 24 packs: ₦1,500
    - 25 packs and above: ₦2,000
    """
    if pack_count <= 9:
        return 800
    elif 10 <= pack_count <= 15:
        return 1000
    elif 16 <= pack_count <= 24:
        return 1500
    else:
        return 2000


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
    # Small Beef (₦200/pc)
    try:
        beef_qty = int(str(pack_data.get("beef_qty") or pack_data.get("small_beef_qty") or "0").strip())
    except (ValueError, TypeError):
        beef_qty = 0
    if beef_qty > 0:
        beef_cost = beef_qty * 200
        unit_price += beef_cost
        items.append(f"{beef_qty}x Small Beef (₦{beef_cost:,})")

    # Big Beef (₦500/pc)
    try:
        big_beef_qty = int(str(pack_data.get("big_beef_qty") or "0").strip())
    except (ValueError, TypeError):
        big_beef_qty = 0
    if big_beef_qty > 0:
        big_beef_cost = big_beef_qty * 500
        unit_price += big_beef_cost
        items.append(f"{big_beef_qty}x Big Beef (₦{big_beef_cost:,})")

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

    # 4. Sides & Extras (Numeric quantities)
    # Plantain (₦500/serv)
    try:
        plantain_qty = int(str(pack_data.get("plantain_qty") or "0").strip())
    except (ValueError, TypeError):
        plantain_qty = 0
    if plantain_qty > 0:
        plantain_cost = plantain_qty * 500
        unit_price += plantain_cost
        items.append(f"{plantain_qty}x Plantain (₦{plantain_cost:,})")

    # Moi Moi (₦1,000/wrap)
    try:
        moimoi_qty = int(str(pack_data.get("moimoi_qty") or "0").strip())
    except (ValueError, TypeError):
        moimoi_qty = 0
    if moimoi_qty > 0:
        moimoi_cost = moimoi_qty * 1000
        unit_price += moimoi_cost
        items.append(f"{moimoi_qty}x Moi Moi (₦{moimoi_cost:,})")

    # Salad (₦500/portion)
    try:
        salad_qty = int(str(pack_data.get("salad_qty") or "0").strip())
    except (ValueError, TypeError):
        salad_qty = 0
    if salad_qty > 0:
        salad_cost = salad_qty * 500
        unit_price += salad_cost
        items.append(f"{salad_qty}x Salad (₦{salad_cost:,})")

    # Goat Meat Pepper Soup (₦2,000/bowl)
    try:
        pepper_soup_qty = int(str(pack_data.get("pepper_soup_qty") or "0").strip())
    except (ValueError, TypeError):
        pepper_soup_qty = 0
    if pepper_soup_qty > 0:
        pepper_soup_cost = pepper_soup_qty * 2000
        unit_price += pepper_soup_cost
        items.append(f"{pepper_soup_qty}x Goat Pepper Soup (₦{pepper_soup_cost:,})")

    # Pepper Sauce (₦200/portion)
    try:
        sauce_qty = int(str(pack_data.get("sauce_qty") or "0").strip())
    except (ValueError, TypeError):
        sauce_qty = 0
    if sauce_qty > 0:
        sauce_cost = sauce_qty * 200
        unit_price += sauce_cost
        items.append(f"{sauce_qty}x Pepper Sauce (₦{sauce_cost:,})")

    # Backward compatibility with legacy extras checkbox list
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


def estimate_items_price(desc: str) -> tuple[int, list[str]]:
    d = desc.lower()
    total = 0
    detected_items = []

    # Check if this line has "N plates of ..." with items before/after
    # Example: "moimoi, 2 plates of white rice, stew and 3 beef each"
    plate_match = re.search(r'(\d+)\s*(?:plates?|packs?)\s*of\s*(.*?)(?:each)?$', d)
    if plate_match:
        qty_plates = int(plate_match.group(1))
        plate_content = plate_match.group(2)
        before_plates = d[:plate_match.start()].strip(' ,-–—:')

        # Price before_plates (e.g. "moimoi")
        side_price, side_items = (0, [])
        if before_plates:
            side_price, side_items = estimate_items_price(before_plates)

        # Price plate_content (e.g. "white rice, stew and 3 beef")
        plate_unit_price, plate_items = _estimate_single_plate_price(plate_content)

        total_line = side_price + (qty_plates * plate_unit_price)
        all_items = side_items + [f"{qty_plates}x Plate: {', '.join(plate_items)} (₦{qty_plates * plate_unit_price:,})"]
        return total_line, all_items

    # Otherwise, single plate / standard order
    return _estimate_single_plate_price(d)


def _estimate_single_plate_price(d: str) -> tuple[int, list[str]]:
    total = 0
    detected_items = []

    # Check if this line is ONLY protein/extras (e.g. "15 beef", "3 chicken")
    has_base = any(k in d for k in ["rice", "semo", "fufu", "swallow", "moimoi", "moi moi", "moi-moi", "spag", "beans", "plate"])

    # 1. Base Meals
    if any(k in d for k in ["mixed rice", "fried & jollof", "fried and jollof"]):
        total += 1300
        detected_items.append("Mixed Rice (₦1,300)")
    elif any(k in d for k in ["rice and beans", "rice & beans", "white rice & beans", "white rice and beans", "white rice, beans", "fried rice, beans"]):
        total += 1300
        detected_items.append("Rice & Beans Combo (₦1,300)")
    elif "jollof" in d:
        total += 1300
        detected_items.append("Jollof Rice (₦1,300)")
    elif "fried rice" in d or "fried" in d:
        total += 1300
        detected_items.append("Fried Rice (₦1,300)")
    elif "white rice" in d:
        total += 1300
        detected_items.append("White Rice (₦1,300)")
    elif any(k in d for k in ["semo", "semovita"]):
        total += 700
        detected_items.append("Semo (₦700)")
    elif "fufu" in d:
        total += 700
        detected_items.append("Fufu (₦700)")
    elif "rice" in d:
        total += 1300
        detected_items.append("Rice Meal (₦1,300)")
    elif any(k in d for k in ["moimoi", "moi moi", "moi-moi"]):
        # Moimoi can serve as base meal
        total += 1000
        detected_items.append("Moi Moi (₦1,000)")
    elif has_base:
        total += 1300
        detected_items.append("Base Meal (₦1,300)")

    # 2. Additional Moimoi if rice was already detected as base
    if any(k in d for k in ["rice", "semo", "fufu"]) and any(k in d for k in ["moimoi", "moi moi", "moi-moi"]):
        total += 1000
        detected_items.append("Moi Moi (₦1,000)")

    # 3. Soups
    has_vegetable = any(k in d for k in ["vegetable", "vegetables", "efo"])
    if has_vegetable:
        total += 500
        detected_items.append("Vegetable Soup (₦500)")
    elif "egusi" in d:
        total += 200
        detected_items.append("Egusi Soup (₦200)")
    elif "ogbono" in d:
        total += 200
        detected_items.append("Ogbono Soup (₦200)")

    # 4. Proteins
    # Chicken (₦3,000)
    m = re.search(r'(\d+)\s*(?:x|-)?\s*chicken', d)
    if m:
        qty = int(m.group(1))
        cost = qty * 3000
        total += cost
        detected_items.append(f"{qty}x Chicken (₦{cost:,})")
    elif "chicken" in d:
        total += 3000
        detected_items.append("Chicken (₦3,000)")

    # Fish (₦1,000)
    m = re.search(r'(\d+)\s*(?:x|-)?\s*(?:fish|titus|croaker)', d)
    if m:
        qty = int(m.group(1))
        cost = qty * 1000
        total += cost
        detected_items.append(f"{qty}x Fish (₦{cost:,})")
    elif any(k in d for k in ["fish", "titus", "croaker"]):
        total += 1000
        detected_items.append("Fish (₦1,000)")

    # Assorted (₦1,000)
    m = re.search(r'(\d+)\s*(?:x|-)?\s*assorted', d)
    if m:
        qty = int(m.group(1))
        cost = qty * 1000
        total += cost
        detected_items.append(f"{qty}x Assorted (₦{cost:,})")
    elif "assorted" in d:
        total += 1000
        detected_items.append("Assorted (₦1,000)")

    # Goat Meat (₦500)
    if "pepper soup" not in d and any(k in d for k in ["goat meat", "goat"]):
        m = re.search(r'(\d+)\s*(?:x|-)?\s*goat', d)
        qty = int(m.group(1)) if m else 1
        cost = qty * 500
        total += cost
        detected_items.append(f"{qty}x Goat Meat (₦{cost:,})")

    # Big Beef (₦500) - ONLY if 'big beef' is explicitly mentioned
    m_bb = re.search(r'(\d+)\s*(?:x|-)?\s*big\s*beef', d)
    if m_bb:
        qty = int(m_bb.group(1))
        cost = qty * 500
        total += cost
        detected_items.append(f"{qty}x Big Beef (₦{cost:,})")
    elif "big beef" in d:
        total += 500
        detected_items.append("Big Beef (₦500)")

    # Small Beef / Default Beef (₦200)
    # Any beef without 'big' defaults to ₦200. Ensure 'goat meat' does not trigger 'meat'!
    m_sb = re.search(r'(\d+)\s*(?:x|-)?\s*(?:small\s*beef|beef|meat)\b', d)
    if m_sb and "big" not in d and not ("goat" in d and "beef" not in d):
        qty = int(m_sb.group(1))
        cost = qty * 200
        total += cost
        detected_items.append(f"{qty}x Beef (₦{cost:,})")
    elif (any(k in d for k in ["small beef", "beef"]) or ("meat" in d and "goat" not in d)) and "big" not in d:
        total += 200
        detected_items.append("Beef (₦200)")

    # Egg (₦300)
    m = re.search(r'(\d+)\s*(?:x|-)?\s*eggs?', d)
    if m:
        qty = int(m.group(1))
        cost = qty * 300
        total += cost
        detected_items.append(f"{qty}x Egg (₦{cost:,})")
    elif "egg" in d:
        total += 300
        detected_items.append("Egg (₦300)")

    # 5. Sides & Extras
    # Plantain (₦500)
    m = re.search(r'(\d+)\s*(?:x|-)?\s*plantain', d)
    if m:
        qty = int(m.group(1))
        cost = qty * 500
        total += cost
        detected_items.append(f"{qty}x Plantain (₦{cost:,})")
    elif "plantain" in d or "dodo" in d:
        total += 500
        detected_items.append("Plantain (₦500)")

    # Salad (₦500)
    if "salad" in d:
        total += 500
        detected_items.append("Salad (₦500)")

    # Pepper Sauce (₦300) - Only if NOT "vegetable sauce"
    # "vegetable sauce" is vegetable soup (₦500), not an extra ₦300 sauce!
    if ("pepper sauce" in d or "sauce" in d) and not has_vegetable:
        total += 300
        detected_items.append("Pepper Sauce (₦300)")

    # Goat Pepper soup (₦2,000)
    if "pepper soup" in d or "peppersoup" in d:
        total += 2000
        detected_items.append("Goat Pepper Soup (₦2,000)")

    # 6. Drinks
    if "water" in d:
        m = re.search(r'(\d+)\s*(?:x|-)?\s*water', d)
        qty = int(m.group(1)) if m else 1
        cost = qty * 300
        total += cost
        detected_items.append(f"{qty}x Water (₦{cost:,})")

    if any(k in d for k in ["malt", "maltina", "amstel"]):
        total += 600
        detected_items.append("Maltina (₦600)")
    elif any(k in d for k in ["coke", "fanta", "sprite", "soft drink", "drink"]):
        total += 500
        detected_items.append("Soft Drink (₦500)")

    # Fallback multiplier if simple "2 plates of ..." with no extra side
    if "of" not in d:
        plate_match_simple = re.search(r'(\d+)\s*(?:plates?|packs?)\b', d)
        multiplier = int(plate_match_simple.group(1)) if plate_match_simple else 1
        total *= multiplier

    return total, detected_items


def parse_bulk_order(raw_text: str) -> tuple[list[dict], int]:
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    packs = []
    current_person = ""
    subtotal = 0

    for line in lines:
        clean_line = line.strip(' *_\t')
        if re.match(r'^(?:food|delivery|grand\s*total|total\s*packs?|subtotal)\b', clean_line, re.IGNORECASE):
            continue

        header_match = re.match(r'^(?:\d+[\.\)]\s*)?([A-Za-z0-9\s]+?)(?:[-–—:]\s*\d+\s*orders?)?:?$', line, re.IGNORECASE)
        is_food_line = any(k in line.lower() for k in ["rice", "semo", "fufu", "beef", "chicken", "fish", "meat", "plantain", "salad", "water", "egg", "soup", "moimoi", "beans", "vegetable"])

        if header_match and not is_food_line:
            current_person = header_match.group(1).strip()
            continue

        free_match = re.search(r'[-–—=:]\s*\*?FREE\*?\s*$', line, re.IGNORECASE)
        if free_match:
            explicit_price = 0
            item_text = line[:free_match.start()].strip(' -–—=:')
        else:
            price_match = re.search(r'[-–—=:]\s*(?:₦|N)?\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{3,6})\s*$', line)
            if price_match:
                price_str = price_match.group(1).replace(',', '')
                try:
                    explicit_price = int(price_str)
                except ValueError:
                    explicit_price = 0
                item_text = line[:price_match.start()].strip(' -–—=:')
            else:
                explicit_price = None
                item_text = line

        person_prefix_match = re.match(r'^(?:\d+[\.\)]\s*)?([A-Za-z]+)\s*[-–—:]\s*(.*)$', item_text)
        if person_prefix_match and not re.match(r'^(?:pack|order)\b', person_prefix_match.group(1), re.IGNORECASE):
            person = person_prefix_match.group(1).strip()
            desc = person_prefix_match.group(2).strip()
        else:
            person = current_person or f"Colleague {len(packs)+1}"
            desc = re.sub(r'^(?:\d+[\.\)]\s*)?', '', item_text).strip(' -–—:')

        if not desc:
            continue

        plate_match = re.search(r'(\d+)\s*(?:plates?|packs?)\b', desc, re.IGNORECASE)
        pack_qty = int(plate_match.group(1)) if plate_match else 1

        if explicit_price is not None:
            price = explicit_price
            items_list = [desc]
        else:
            estimated_price, _ = estimate_items_price(desc)
            price = estimated_price
            items_list = [desc]

        subtotal += price
        pack_name = f"{person}: {desc}"
        packs.append({
            "pack_name": pack_name[:35],
            "quantity": pack_qty,
            "unit_price": price // pack_qty if pack_qty > 0 else price,
            "total_price": price,
            "items": items_list,
            "note": f"For {person}"
        })

    return packs, subtotal


def format_cart_display(cart_packs: list[dict]) -> tuple[str, int]:
    """Formats cart items into clean bulleted text and computes food subtotal."""
    if not cart_packs:
        return "Your cart is empty.", 0

    lines = []
    subtotal = 0
    for idx, pack in enumerate(cart_packs, 1):
        name = pack.get("pack_name", f"Pack {idx}")
        qty = pack.get("quantity", 1)
        total = pack.get("total_price", 0)
        items_summary = ", ".join(pack.get("items", []))
        note = f" (Note: {pack['note']})" if pack.get("note") else ""
        lines.append(f"📦 *{name}* (x{qty}) — ₦{total:,}\n• {items_summary}{note}")
        subtotal += total

    return "\n\n".join(lines), subtotal



def normalize_phone_number(phone: str) -> str:
    if not phone:
        return ""
    clean = re.sub(r'[^\d]', '', str(phone))
    if clean.startswith("0") and len(clean) == 11:
        return "234" + clean[1:]
    if len(clean) == 10 and clean[0] in ['7', '8', '9']:
        return "234" + clean
    return clean


def get_phone_variants(phone: str) -> list[str]:
    if not phone:
        return []
    raw_str = str(phone)
    clean_digits = re.sub(r'[^\d]', '', raw_str)
    variants = set([phone, raw_str, clean_digits])
    if clean_digits:
        variants.add(f"+{clean_digits}")

    canonical = normalize_phone_number(phone)
    if len(canonical) == 13 and canonical.startswith("234"):
        local_fmt = "0" + canonical[3:]
        plus_fmt = "+" + canonical
        raw_fmt = canonical[3:]
        variants.update([canonical, local_fmt, plus_fmt, raw_fmt])
    return [v for v in variants if v]


async def resolve_customer_details(sender_wa: str, db: AsyncSession) -> tuple[bool, str, str, str]:
    """
    Resolves customer registration status and previous saved address.
    Checks models.User first (with phone variants), then past orders in models.Orders.
    Returns: (is_registered, customer_name, saved_address, saved_phone)
    """
    if not sender_wa:
        return False, "", "", ""

    clean_digits = re.sub(r'[^\d]', '', str(sender_wa))
    clean_last_10 = clean_digits[-10:] if len(clean_digits) >= 10 else clean_digits
    possible_numbers = get_phone_variants(sender_wa)

    is_registered = False
    customer_name = ""
    saved_address = ""
    saved_phone = sender_wa

    # 1. Primary check: models.User table
    try:
        user_stmt = select(models.User).where(
            ((models.User.display_phone_number.in_(possible_numbers)) |
             (models.User.wa_id.in_(possible_numbers)) |
             (models.User.phone_number_id.in_(possible_numbers))) &
            (models.User.is_deleted == False)
        )
        user_res = await db.execute(user_stmt)
        user_obj = user_res.scalars().first()
        if user_obj:
            is_registered = True
            raw_name = (user_obj.name or "").strip()
            if raw_name and raw_name.lower() not in ["customer", "none", "null", "user"]:
                customer_name = raw_name
            # Check address column on User table
            user_addr = getattr(user_obj, "address", None)
            if user_addr and isinstance(user_addr, str):
                addr_clean = user_addr.strip()
                if len(addr_clean) >= 5 and addr_clean.lower() not in ["customer address", "none", "null", "dropoff location", "pickup location", "undefined"]:
                    saved_address = addr_clean
                    saved_phone = (user_obj.display_phone_number or user_obj.wa_id or sender_wa).strip()
    except Exception as u_err:
        logger.warning(f"Error querying models.User for {sender_wa}: {u_err}")

    # 2. Secondary check: Query models.Orders if address not stored on User record
    if not saved_address:
        try:
            ord_stmt = (
                select(models.Orders)
                .where(
                    (models.Orders.sender_wa_number.in_(possible_numbers)) |
                    (models.Orders.sender_wa_number.like(f"%{clean_last_10}%"))
                )
                .order_by(models.Orders.created_at.desc())
                .limit(10)
            )
            ord_res = await db.execute(ord_stmt)
            orders = ord_res.scalars().all()

            # Priority 2a: Recent food order dropoff
            for o in orders:
                if o.package_image_id == "FOOD_ORDER":
                    addr = (o.dropoff_location_name or "").strip()
                    if addr and len(addr) >= 5 and addr.lower() not in ["customer address", "none", "null", "dropoff location", "undefined"]:
                        saved_address = addr
                        saved_phone = (o.recipient_phone_number or sender_wa).strip()
                        break

            # Priority 2b: Any recent order dropoff
            if not saved_address:
                for o in orders:
                    addr = (o.dropoff_location_name or "").strip()
                    if addr and len(addr) >= 5 and addr.lower() not in ["customer address", "none", "null", "dropoff location", "undefined"]:
                        saved_address = addr
                        saved_phone = (o.recipient_phone_number or sender_wa).strip()
                        break

            # Priority 2c: Parcel order pickup location (customer dispatched parcel from their home)
            if not saved_address:
                for o in orders:
                    addr = (o.pickup_location_name or "").strip()
                    if addr and len(addr) >= 5 and addr.lower() not in ["pickup location", "customer address", "none", "null", "undefined"] and "madam g" not in addr.lower() and "restaurant" not in addr.lower():
                        saved_address = addr
                        saved_phone = (o.recipient_phone_number or sender_wa).strip()
                        break

            # Backfill to user record if user is registered so future lookups are immediate
            if saved_address and is_registered:
                try:
                    await db.execute(
                        update(models.User)
                        .where(
                            (models.User.display_phone_number.in_(possible_numbers)) |
                            (models.User.wa_id.in_(possible_numbers)) |
                            (models.User.phone_number_id.in_(possible_numbers))
                        )
                        .values(address=saved_address)
                    )
                    await db.commit()
                except Exception as bf_err:
                    logger.warning(f"Failed to backfill user.address: {bf_err}")

        except Exception as o_err:
            logger.warning(f"Error querying orders for {sender_wa}: {o_err}")

    return is_registered, customer_name, saved_address, saved_phone


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

        # Parse flow token data safely (handles dict, JSON string, plain string, int without throwing AttributeError)
        flow_token = {}
        sender_wa = ""
        token_saved_addr = ""
        token_saved_phone = ""
        token_cust_name = ""
        token_is_registered = False

        if isinstance(flow_token_raw, dict):
            flow_token = flow_token_raw
        elif isinstance(flow_token_raw, (str, int)):
            raw_s = str(flow_token_raw).strip()
            if raw_s.startswith("{"):
                try:
                    parsed = json.loads(raw_s)
                    if isinstance(parsed, dict):
                        flow_token = parsed
                    else:
                        sender_wa = str(parsed)
                except Exception:
                    sender_wa = raw_s
            else:
                sender_wa = raw_s

        if isinstance(flow_token, dict):
            sender_wa = str(flow_token.get("sender_wa_number") or flow_token.get("wa_id") or flow_token.get("phone") or sender_wa or "").strip()
            token_saved_addr = str(flow_token.get("saved_address") or flow_token.get("delivery_address") or "").strip()
            token_saved_phone = str(flow_token.get("saved_phone") or flow_token.get("contact_phone") or "").strip()
            token_cust_name = str(flow_token.get("customer_name") or "").strip()
            token_is_registered = bool(flow_token.get("is_registered", False))

        # 2. Opening the Flow (action can be INIT, navigate, or opening data_exchange)
        is_opening_request = (
            action in ["INIT", "navigate"] or
            (action == "data_exchange" and (not screen or screen == "CONFIRM_ADDRESS_SCREEN") and
             not data.get("user_action") and not data.get("selected_pack") and not data.get("base_meal") and
             not data.get("use_previous") and not data.get("bulk_order_text") and not data.get("cart_packs"))
        )
        if is_opening_request:
            # Full lookup for registered user and past saved address
            is_reg, cust_name, saved_address, saved_phone = await resolve_customer_details(sender_wa, db)
            
            # Merge with token data if available
            is_registered = is_reg or token_is_registered
            customer_name = cust_name or token_cust_name
            saved_address = saved_address or token_saved_addr
            saved_phone = saved_phone or token_saved_phone or sender_wa

            has_valid_saved_address = bool(saved_address and len(saved_address) >= 5 and saved_address.lower() not in ["customer address", "none", "null", "dropoff location", "undefined"])

            if has_valid_saved_address:
                # Registered / returning customer with a saved address -> Show CONFIRM_ADDRESS_SCREEN
                greeting = f"Welcome back, *{customer_name}*! 🍲" if customer_name else "Welcome back! 🍲"
                address_display = (
                    f"{greeting}\n\n"
                    f"📍 Saved Address:\n{saved_address}\n\n"
                    f"📞 Receiver's Phone: {saved_phone}"
                )
                resp_payload = {
                    "version": "3.0",
                    "screen": "CONFIRM_ADDRESS_SCREEN",
                    "data": {
                        "saved_address": saved_address,
                        "saved_phone": saved_phone,
                        "delivery_address": saved_address,
                        "contact_phone": saved_phone,
                        "address_display": address_display,
                        "use_previous": "yes"
                    }
                }
            else:
                # User has no saved address -> Route directly to RECOMMEND (Address Input screen)
                resp_payload = {
                    "version": "3.0",
                    "screen": "RECOMMEND",
                    "data": {
                        "screen_0_HouseFlat_Number_0": "",
                        "screen_0_Street_Name_1": "",
                        "screen_0_Receivers_Number_2": saved_phone or sender_wa or "",
                        "HouseFlat_Number_801bd0": "",
                        "Street_Name_17f2ce": "",
                        "Receivers_Number_eb5784": saved_phone or sender_wa or "",
                        "contact_phone": saved_phone or sender_wa or ""
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
                saved_addr = (data.get("saved_address") or data.get("delivery_address") or delivery_address or "").strip()
                
                # If saved_addr is missing from client data, try resolving from database
                if not saved_addr or len(saved_addr) < 5 or saved_addr.lower() in ["customer address", "none", "null", "undefined"]:
                    _, _, db_addr, db_phone = await resolve_customer_details(sender_wa, db)
                    if db_addr and len(db_addr) >= 5:
                        saved_addr = db_addr
                        if db_phone:
                            contact_phone = db_phone

                if use_prev == "yes" and len(saved_addr) >= 5 and saved_addr.lower() not in ["customer address", "none", "null", "undefined"]:
                    # Proceed directly to Restaurant selection (RATE) with verified address
                    resp_payload = {
                        "version": "3.0",
                        "screen": "RATE",
                        "data": {
                            "delivery_address": saved_addr,
                            "contact_phone": contact_phone,
                            "screen_0_HouseFlat_Number_0": "",
                            "screen_0_Street_Name_1": saved_addr,
                            "screen_0_Receivers_Number_2": contact_phone
                        }
                    }
                else:
                    # User chose "No, enter new address" OR had no valid address -> navigate to RECOMMEND
                    resp_payload = {
                        "version": "3.0",
                        "screen": "RECOMMEND",
                        "data": {
                            "screen_0_HouseFlat_Number_0": "",
                            "screen_0_Street_Name_1": "",
                            "screen_0_Receivers_Number_2": contact_phone or sender_wa or "",
                            "HouseFlat_Number_801bd0": "",
                            "Street_Name_17f2ce": "",
                            "Receivers_Number_eb5784": contact_phone or sender_wa or "",
                            "contact_phone": contact_phone or sender_wa or ""
                        }
                    }
                enc_response = encrypt_flow_response(resp_payload, aes_key, iv_bytes)
                return Response(content=enc_response, media_type="text/plain")

            # --- SCREEN: RECOMMEND (Address Entry) ---
            elif screen == "RECOMMEND":
                house_num = (data.get("HouseFlat_Number_801bd0") or data.get("screen_0_HouseFlat_Number_0") or "").strip()
                street_name = (data.get("Street_Name_17f2ce") or data.get("screen_0_Street_Name_1") or "").strip()
                contact_phone = (
                    data.get("Receivers_Number_eb5784") or 
                    data.get("screen_0_Receivers_Number_2") or 
                    data.get("contact_phone") or 
                    sender_wa
                )

                if street_name:
                    if house_num and house_num.lower() not in street_name.lower():
                        delivery_address = f"{house_num}, {street_name}".strip(", ")
                    else:
                        delivery_address = street_name
                elif not delivery_address:
                    delivery_address = house_num or "Customer Address"

                # Persist this address to models.User immediately so it is remembered permanently
                if sender_wa and delivery_address and len(delivery_address) >= 5 and delivery_address != "Customer Address":
                    try:
                        variants = get_phone_variants(sender_wa)
                        await db.execute(
                            update(models.User)
                            .where(
                                (models.User.display_phone_number.in_(variants)) |
                                (models.User.wa_id.in_(variants)) |
                                (models.User.phone_number_id.in_(variants))
                            )
                            .values(address=delivery_address)
                        )
                        await db.commit()
                    except Exception as cache_err:
                        logger.warning(f"Failed to cache address for {sender_wa}: {cache_err}")

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
                if combo_key == "bulk_office_order":
                    # Navigate to Bulk Office Order screen
                    resp_payload = {
                        "version": "3.0",
                        "screen": "BULK_ORDER_SCREEN",
                        "data": {
                            "restaurant": restaurant,
                            "restaurant_logo": LOGO_DATA_URI,
                            "delivery_address": delivery_address,
                            "contact_phone": contact_phone,
                            "cart_packs": current_cart
                        }
                    }
                elif combo_key == "skip_to_custom" or user_action == "switch_to_custom":
                    # Navigate to Custom Pack 1
                    resp_payload = {
                        "version": "3.0",
                        "screen": "BUILD_CUSTOM_PACK_SCREEN",
                        "data": {
                            "restaurant": restaurant,
                            "restaurant_logo": LOGO_DATA_URI,
                            "delivery_address": delivery_address,
                            "contact_phone": contact_phone,
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
                    total_pack_count = sum(p.get("quantity", 1) for p in current_cart) or 1
                    delivery_fee = calculate_delivery_fee(total_pack_count)
                    grand_total = subtotal + delivery_fee
                    totals_display = (
                        f"💳 *Grand Total: ₦{grand_total:,}*\n"
                        f"💵 Food: ₦{subtotal:,}  |  🛵 Delivery ({total_pack_count} pk{'s' if total_pack_count > 1 else ''}): ₦{delivery_fee:,}"
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

            # --- SCREEN: BULK_ORDER_SCREEN (Paste Office List) ---
            elif screen == "BULK_ORDER_SCREEN":
                bulk_parts = [
                    str(data.get("bulk_order_text") or "").strip(),
                    str(data.get("bulk_order_text_2") or "").strip(),
                    str(data.get("bulk_order_text_3") or "").strip()
                ]
                bulk_text = "\n".join([p for p in bulk_parts if p and p.lower() not in ["null", "none"]]).strip()
                bulk_packs, bulk_total = parse_bulk_order(bulk_text)

                if bulk_packs:
                    current_cart.extend(bulk_packs)
                else:
                    current_cart.append({
                        "pack_name": "Bulk Office Order",
                        "quantity": 1,
                        "unit_price": bulk_total or 2500,
                        "total_price": bulk_total or 2500,
                        "items": [bulk_text] if bulk_text else ["Office Bulk Order"],
                        "note": "Office Bulk Order"
                    })

                cart_text, subtotal = format_cart_display(current_cart)
                total_pack_count = sum(p.get("quantity", 1) for p in current_cart) or 1
                delivery_fee = calculate_delivery_fee(total_pack_count)
                grand_total = subtotal + delivery_fee
                totals_display = (
                    f"💳 *Grand Total: ₦{grand_total:,}*\n"
                    f"💵 Food: ₦{subtotal:,}  |  🛵 Delivery ({total_pack_count} pk{'s' if total_pack_count > 1 else ''}): ₦{delivery_fee:,}"
                )

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

            # --- SCREENS: CUSTOM PACK BUILDERS (Pack 1, 2, 3) ---
            elif screen in ["BUILD_CUSTOM_PACK_SCREEN", "BUILD_CUSTOM_PACK_TWO", "BUILD_CUSTOM_PACK_THREE"]:
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
                total_pack_count = sum(p.get("quantity", 1) for p in current_cart) or 1
                delivery_fee = calculate_delivery_fee(total_pack_count)
                grand_total = subtotal + delivery_fee
                totals_display = (
                    f"💳 *Grand Total: ₦{grand_total:,}*\n"
                    f"💵 Food: ₦{subtotal:,}  |  🛵 Delivery ({total_pack_count} pk{'s' if total_pack_count > 1 else ''}): ₦{delivery_fee:,}"
                )

                next_action = data.get("next_action")
                if next_action == "add_another":
                    next_screen_map = {
                        "BUILD_CUSTOM_PACK_SCREEN": "BUILD_CUSTOM_PACK_TWO",
                        "BUILD_CUSTOM_PACK_TWO": "BUILD_CUSTOM_PACK_THREE"
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
                total_pack_count = sum(p.get("quantity", 1) for p in current_cart) or 1
                delivery_fee = calculate_delivery_fee(total_pack_count)
                grand_total = subtotal + delivery_fee
                final_address = delivery_address or street_name or data.get("saved_address") or ""
                if not final_address or final_address.lower() in ["customer address", "none", "null", "undefined", ""]:
                    _, _, db_addr, _ = await resolve_customer_details(sender_wa, db)
                    final_address = db_addr or "Address confirmed at delivery"

                confirm_display = (
                    f"📋 *Order Breakdown ({total_pack_count} pack{'s' if total_pack_count > 1 else ''}):*\n"
                    f"{cart_text}\n\n"
                    f"📍 *Delivery:* {final_address}\n"
                    f"📞 *Receiver:* {contact_phone}\n"
                    f"🍲 *Restaurant:* {restaurant}\n"
                    f"💵 *Food Subtotal:* ₦{subtotal:,}\n"
                    f"🛵 *Delivery Fee:* ₦{delivery_fee:,}\n"
                    f"💳 *Grand Total:* *₦{grand_total:,}*"
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
                        "delivery_fee": delivery_fee,
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

        # Fallback (Safe default routing to address input screen if something was unexpected)
        resp_payload = {
            "version": "3.0",
            "screen": "RECOMMEND",
            "data": {
                "screen_0_HouseFlat_Number_0": "",
                "screen_0_Street_Name_1": "",
                "screen_0_Receivers_Number_2": sender_wa or "",
                "HouseFlat_Number_801bd0": "",
                "Street_Name_17f2ce": "",
                "Receivers_Number_eb5784": sender_wa or "",
                "contact_phone": sender_wa or ""
            }
        }
        enc_response = encrypt_flow_response(resp_payload, aes_key, iv_bytes)
        return Response(content=enc_response, media_type="text/plain")

    except Exception as e:
        logger.error(f"Flow endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=421, detail=str(e))
