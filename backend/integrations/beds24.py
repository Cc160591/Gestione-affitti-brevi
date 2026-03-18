"""
Integrazione Beds24 API v1 per aggiornamento prezzi su Airbnb.
Documentazione: https://beds24.com/api/v2/ (API v1, URL storico)

Autenticazione:
  BEDS24_API_KEY  = devKey  (Account → Account Access → API Key 1)
  BEDS24_PROP_KEY = propKey (Marketplace → API Arrivals → Access Key)
"""
import httpx
import os
import logging
from datetime import date

logger = logging.getLogger(__name__)

BEDS24_V1_URL = "https://beds24.com/api/v2"
BEDS24_DEV_KEY  = os.getenv("BEDS24_API_KEY")
BEDS24_PROP_KEY = os.getenv("BEDS24_PROP_KEY")


def _is_mock() -> bool:
    return not BEDS24_DEV_KEY or not BEDS24_PROP_KEY


def _auth() -> dict:
    return {"propKey": BEDS24_PROP_KEY, "devKey": BEDS24_DEV_KEY}


async def update_price(room_id: str, target_date: date, price: float) -> bool:
    if _is_mock():
        logger.info(f"[MOCK] Beds24: roomId={room_id} → €{price} per {target_date}")
        return True

    date_str = str(target_date)
    payload = {
        "authentication": _auth(),
        "data": [
            {
                "roomId": int(room_id),
                "firstNight": date_str,
                "lastNight": date_str,
                "price1": price,
            }
        ],
    }
    logger.info(f"Beds24 update_price: roomId={room_id} date={date_str} price={price}")

    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BEDS24_V1_URL}/setprice", json=payload)
        logger.info(f"Beds24 response: {r.status_code} {r.text}")
        if r.status_code == 200:
            data = r.json()
            if data.get("authentication") == "authenticated":
                return True
            raise ValueError(f"Beds24 autenticazione fallita: {data}")
        raise ValueError(f"Beds24 HTTP {r.status_code}: {r.text}")


async def update_prices_bulk(updates: list[dict]) -> dict[str, bool]:
    if _is_mock():
        return {u["beds24_id"]: True for u in updates}

    data = [
        {
            "roomId": int(u["beds24_id"]),
            "firstNight": str(u["date"]),
            "lastNight": str(u["date"]),
            "price1": u["price"],
        }
        for u in updates
    ]
    payload = {"authentication": _auth(), "data": data}

    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BEDS24_V1_URL}/setprice", json=payload)
        if r.status_code == 200 and r.json().get("authentication") == "authenticated":
            return {u["beds24_id"]: True for u in updates}
        raise ValueError(f"Beds24 HTTP {r.status_code}: {r.text}")


async def get_current_prices(room_ids: list[str], target_date: date) -> dict[str, float]:
    if _is_mock():
        return {room_id: 0.0 for room_id in room_ids}

    date_str = str(target_date)
    payload = {
        "authentication": _auth(),
        "data": {"roomId": [int(r) for r in room_ids], "firstNight": date_str, "lastNight": date_str},
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BEDS24_V1_URL}/getprice", json=payload)
        if r.status_code != 200:
            return {}
        result = {}
        for room in r.json().get("data", []):
            rid = str(room.get("roomId"))
            prices = room.get("prices", [])
            if prices:
                result[rid] = prices[0].get("price1", 0.0)
        return result


async def get_properties() -> list[dict]:
    if _is_mock():
        return []
    payload = {"authentication": _auth()}
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BEDS24_V1_URL}/getproperties", json=payload)
        if r.status_code == 200:
            return r.json().get("data", [])
        return []
