import os
import json
import logging
import base64
import re
import urllib.request
from typing import Tuple, Optional
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


def parse_transfer_receipt(image_bytes: Optional[bytes] = None, text_content: Optional[str] = None) -> Tuple[Optional[int], str]:
    """
    Extracts transfer amount and transaction status from image receipt (via Groq Vision)
    or text message fallback.
    Returns: (amount: int | None, status: 'successful' | 'pending' | 'failed' | 'unknown')
    """
    groq_api_key = os.getenv("GROQ_API_KEY", "").strip()

    # 1. Vision extraction if image provided and Groq key available
    if image_bytes and groq_api_key and len(image_bytes) >= 100:
        try:
            b64_img = base64.b64encode(image_bytes).decode("utf-8")
            client = Groq(api_key=groq_api_key)

            prompt = (
                "You are an expert financial receipt parser for Nigerian bank transfers (Moniepoint, OPay, PalmPay, Kuda, GTBank, Zenith, Access, etc.). "
                "Analyze this bank transfer receipt image. "
                "Extract: "
                "1. The exact total transferred amount in Naira (digits only, e.g., 3500). "
                "2. The transaction status (successful, pending, or failed). "
                "Reply ONLY with a valid JSON object matching this schema: "
                "{\"amount\": <integer or null>, \"status\": \"successful\" | \"pending\" | \"failed\"}."
            )

            resp = client.chat.completions.create(
                model="qwen/qwen3.8-27b",
                max_tokens=150,
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
                stat = str(parsed.get("status") or "successful").lower()
                if amt and isinstance(amt, (int, float)) and amt > 0:
                    return int(amt), stat
        except Exception as e:
            logger.warning(f"Groq vision receipt parsing encountered error: {e}")

    # 2. Text / Caption Fallback
    if text_content:
        amt = extract_amount_from_text(text_content)
        if amt:
            return amt, "successful"

    return None, "unknown"

