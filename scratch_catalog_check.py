import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

auth = os.getenv("AUTHORIZATION", "").strip()
graph_url = os.getenv("GRAPH_URL", "").strip()
catalog_id = os.getenv("META_CATALOG_ID", "1515700860395437").strip()
waba_id = os.getenv("WABA_ID", "793614220010952").strip()
prod_phone = os.getenv("PRODUCTION_PHONE_NUMBER", "NOT SET").strip()

phone_number_id = ""
if "/v21.0/" in graph_url:
    phone_number_id = graph_url.split("/v21.0/")[1].split("/")[0]

print("=== Config Check ===")
print(f"AUTH present: {bool(auth)} (length={len(auth)})")
print(f"GRAPH_URL: {graph_url}")
print(f"Phone number ID: {phone_number_id}")
print(f"WABA_ID: {waba_id}")
print(f"CATALOG_ID: {catalog_id}")
print(f"PRODUCTION_PHONE_NUMBER: {prod_phone}")

if not auth:
    print("\nAUTHORIZATION token is MISSING in .env")
    print("Railway env vars are not in your local .env file.")
    print("Add AUTHORIZATION=<your_token> to .env to test locally.")
else:
    async def check_catalog():
        headers = {"Authorization": f"Bearer {auth}", "Content-Type": "application/json"}
        async with httpx.AsyncClient() as client:
            # 1. Check catalog items via Graph API
            print("\n--- Checking catalog items ---")
            items_url = f"https://graph.facebook.com/v21.0/{catalog_id}/products?fields=retailer_id,name,price,availability&limit=5"
            r = await client.get(items_url, headers=headers)
            print(f"Catalog items ({r.status_code}): {r.text[:600]}")

            # 2. Check whatsapp_commerce_settings
            if phone_number_id:
                print("\n--- Checking commerce settings ---")
                comm_url = f"https://graph.facebook.com/v21.0/{phone_number_id}/whatsapp_commerce_settings"
                r2 = await client.get(comm_url, headers=headers)
                print(f"Commerce settings ({r2.status_code}): {r2.text[:400]}")

            # 3. Check WABA product_catalogs
            print("\n--- Checking WABA linked catalogs ---")
            waba_cat_url = f"https://graph.facebook.com/v21.0/{waba_id}/product_catalogs"
            r3 = await client.get(waba_cat_url, headers=headers)
            print(f"WABA catalogs ({r3.status_code}): {r3.text[:400]}")

    asyncio.run(check_catalog())
