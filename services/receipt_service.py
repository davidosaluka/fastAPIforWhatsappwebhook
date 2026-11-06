import os
import json
import logging
import base64
import re
import urllib.request
from typing import Tuple, Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import models
from groq import Groq

logger = logging.getLogger("receipt_service")


async def download_whatsapp_media(media_id: str, auth: str) -> Optional[bytes]:
    """
    Downloads media file from WhatsApp Cloud API using media ID and system Bearer token.
    """
    if not media_id or not auth:
        return None
    try:
        # Step 1: Query WhatsApp Graph API for media URL
        media_info_url = f"https://graph.facebook.com/v21.0/{media_id}"
        req1 = urllib.request.Request(
            media_info_url,
            headers={
                "Authorization": f"Bearer {auth}",
                "User-Agent": "Mozilla/5.0"
            }
        )
        with urllib.request.urlopen(req1, timeout=15) as resp1:
            data = json.loads(resp1.read().decode("utf-8"))
            download_url = data.get("url")

        if not download_url:
            logger.warning(f"No download URL returned for media ID {media_id}")
            return None

        # Step 2: Download raw media bytes from authenticated URL
        req2 = urllib.request.Request(
            download_url,
            headers={
                "Authorization": f"Bearer {auth}",
                "User-Agent": "Mozilla/5.0"
            }
        )
        with urllib.request.urlopen(req2, timeout=25) as resp2:
            return resp2.read()

    except Exception as e:
        logger.error(f"Error downloading WhatsApp media {media_id}: {e}")
        return None


def extract_amount_from_text(text: str) -> Optional[int]:
    """Fallback parser: extracts transferred amount from user text or receipt caption."""
    if not text:
        return None
    clean = text.replace(",", "")
    # Look for patterns like ₦3,500, N3500, 3500 naira, transferred 3500, 3500
    patterns = [
        r'(?:₦|N|NGN)\s*([0-9]{3,7})\b',
        r'(?:transferred|paid|sent|amount)\s*(?:is|of)?\s*(?:₦|N)?\s*([0-9]{3,7})\b',
        r'\b([0-9]{3,7})\s*(?:naira|kobo)\b',
        r'\b([1-9][0-9]{2,5})\b'
    ]
    for p in patterns:
        m = re.search(p, clean, re.IGNORECASE)
        if m:
            try:
                val = int(m.group(1))
                if 200 <= val <= 500000:
                    return val
            except ValueError:
                continue
    return None


def parse_transfer_receipt(
    image_bytes: Optional[bytes] = None,
    text_content: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extracts transfer amount, transaction status, reference, beneficiary details,
    and date from image receipt (via Groq Vision) or text message fallback.
    Returns a structured dictionary:
    {
        "amount": int | None,
        "status": "successful" | "pending" | "failed" | "unknown",
        "transaction_reference": str | None,
        "beneficiary_name": str | None,
        "beneficiary_account": str | None,
        "beneficiary_bank": str | None,
        "transaction_date": str | None
    }
    """
    result: Dict[str, Any] = {
        "amount": None,
        "status": "unknown",
        "transaction_reference": None,
        "beneficiary_name": None,
        "beneficiary_account": None,
        "beneficiary_bank": None,
        "transaction_date": None
    }
    groq_api_key = os.getenv("GROQ_API_KEY", "").strip()

    # 1. Vision extraction if image provided and Groq key available
    if image_bytes and groq_api_key and len(image_bytes) >= 100:
        try:
            b64_img = base64.b64encode(image_bytes).decode("utf-8")
            client = Groq(api_key=groq_api_key)

            prompt = (
                "You are an expert financial receipt parser for Nigerian bank transfers "
                "(Moniepoint, OPay, PalmPay, Kuda, GTBank, Zenith, Access, FirstBank, UBA, etc.).\n"
                "Analyze this transfer receipt image and extract these exact fields:\n"
                "1. amount: total transferred amount in Naira (digits only, e.g. 3500, no currency symbols or commas).\n"
                "2. status: transaction status ('successful', 'pending', or 'failed').\n"
                "3. transaction_reference: unique session ID, transaction reference, or NIP reference number. Null if not clearly visible.\n"
                "4. beneficiary_name: destination / recipient account name (e.g. 'Christiana Adamu'). Null if not found.\n"
                "5. beneficiary_account: destination / recipient account number (digits only, e.g. '5330778741'). Null if not found.\n"
                "6. beneficiary_bank: destination bank name (e.g. 'Moniepoint', 'OPay', 'Kuda'). Null if not found.\n"
                "7. transaction_date: transaction date and time string (e.g. '06 Nov 2026, 17:45'). Null if not found.\n\n"
                "Reply ONLY with a valid JSON object matching this schema:\n"
                "{\n"
                "  \"amount\": <integer or null>,\n"
                "  \"status\": \"successful\" | \"pending\" | \"failed\",\n"
                "  \"transaction_reference\": <string or null>,\n"
                "  \"beneficiary_name\": <string or null>,\n"
                "  \"beneficiary_account\": <string or null>,\n"
                "  \"beneficiary_bank\": <string or null>,\n"
                "  \"transaction_date\": <string or null>\n"
                "}"
            )

            resp = client.chat.completions.create(
                model="qwen/qwen3.8-27b",
                max_tokens=220,
                temperature=0.1,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                        ]
                    }
                ]
            )

            ans = resp.choices[0].message.content.strip()
            # Extract JSON block
            json_match = re.search(r'\{.*\}', ans, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                amt = parsed.get("amount")
                if amt and isinstance(amt, (int, float)) and amt > 0:
                    result["amount"] = int(amt)
                result["status"] = str(parsed.get("status") or "successful").lower()
                result["transaction_reference"] = str(parsed.get("transaction_reference") or "").strip() or None
                result["beneficiary_name"] = str(parsed.get("beneficiary_name") or "").strip() or None
                result["beneficiary_account"] = str(parsed.get("beneficiary_account") or "").strip() or None
                result["beneficiary_bank"] = str(parsed.get("beneficiary_bank") or "").strip() or None
                result["transaction_date"] = str(parsed.get("transaction_date") or "").strip() or None
                return result
        except Exception as e:
            logger.warning(f"Groq vision receipt parsing encountered error: {e}")

    # 2. Text / Caption Fallback
    if text_content:
        amt = extract_amount_from_text(text_content)
        if amt:
            result["amount"] = amt
            result["status"] = "successful"
            return result

    return result


async def validate_receipt_security(
    parsed_receipt: Dict[str, Any],
    active_order: models.Orders,
    restaurant: Optional[models.Restaurants],
    db: AsyncSession
) -> Tuple[bool, str]:
    """
    Validates the parsed receipt against common fraud vectors:
    1. Duplicate Reference: Rejects if the reference/session ID was already used on another order.
    2. Beneficiary Check: Verifies the payment was made to the restaurant's account/name.
    3. Status Check: Verifies the transaction succeeded.
    Returns: (is_valid: bool, rejection_message: str)
    """
    # 1. Status Check
    status = str(parsed_receipt.get("status") or "").lower()
    if status in ["failed", "reversed"]:
        return False, f"❌ The receipt shows the transfer was *{status.upper()}*. Please re-try from your bank app."
    if status == "pending":
        return False, "⏳ The receipt shows the transfer is still *PENDING* with your bank. Please wait a moment for it to complete or check your bank app."

    # 2. Duplicate Transaction Reference Check (Stops re-using old receipts)
    ref = parsed_receipt.get("transaction_reference")
    if ref and len(ref) >= 6:
        dup_stmt = select(models.Orders).where(
            models.Orders.transaction_reference == ref,
            models.Orders.id != active_order.id,
            models.Orders.payment_status.in_(["paid", "partial_payment"])
        )
        dup_res = await db.execute(dup_stmt)
        existing = dup_res.scalars().first()
        if existing:
            logger.warning(f"Fraud attempt: duplicate receipt ref {ref} already used on order {existing.order_number}")
            return False, (
                f"⚠️ *Duplicate Receipt Detected!*\n\n"
                f"This transaction reference (`{ref}`) was already redeemed for Order *#{existing.order_number}*.\n\n"
                f"Each order requires a fresh bank transfer. Please transfer the order amount and send the new receipt."
            )

    # 3. Beneficiary Account & Name Check (Stops paying unrelated accounts)
    if restaurant:
        b_name = (parsed_receipt.get("beneficiary_name") or "").lower().strip()
        b_acct = re.sub(r'[^\d]', '', str(parsed_receipt.get("beneficiary_account") or ""))
        exp_acct = re.sub(r'[^\d]', '', str(restaurant.account_number or "5330778741"))
        exp_name_parts = [p.lower() for p in (restaurant.account_name or "Christiana Adamu").split() if len(p) >= 3]
        exp_rest_parts = [p.lower() for p in (restaurant.name or "Madam G").split() if len(p) >= 3]

        # If recipient account number is visible on receipt, check if it matches
        if b_acct and len(b_acct) >= 7 and len(exp_acct) >= 7:
            if b_acct != exp_acct and not (b_acct.endswith(exp_acct[-6:]) or exp_acct.endswith(b_acct[-6:])):
                return False, (
                    f"❌ *Wrong Beneficiary Account!*\n\n"
                    f"Your receipt shows payment to account `{b_acct}`, but {restaurant.name}'s account number is *`{exp_acct}`* ({restaurant.bank_name or 'Moniepoint'}).\n\n"
                    f"Please make sure you transfer to {restaurant.name} and send the receipt."
                )

        # If recipient name is visible on receipt and has no overlap with expected restaurant/name
        if b_name and len(b_name) >= 4:
            has_match = any(p in b_name for p in exp_name_parts + exp_rest_parts)
            if not has_match and not ("intime" in b_name or "restaurant" in b_name):
                return False, (
                    f"❌ *Wrong Beneficiary Name!*\n\n"
                    f"Your receipt shows payment was sent to *{parsed_receipt.get('beneficiary_name')}*, but {restaurant.name}'s account name is *{restaurant.account_name or 'Christiana Adamu'}*.\n\n"
                    f"Please send the transfer to *{restaurant.account_name}* ({restaurant.bank_name or 'Moniepoint'})."
                )

    return True, ""

