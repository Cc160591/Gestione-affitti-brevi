"""
Integrazione Beds24 API v2 per aggiornamento prezzi su Airbnb.
Documentazione: https://api.beds24.com/v2/

Autenticazione:
  BEDS24_API_KEY = long-life token (Beds24 → Account Access → Invite Codes → crea invite → usa il token)
  Passato come header: token: <long_life_token>
"""
import httpx
import os
import logging
from datetime import date

logger = logging.getLogger(__name__)

BEDS24_BASE_URL = "https://api.beds24.com/v2"
BEDS24_API_KEY = os.getenv("BEDS24_API_KEY")  # Long life token


def _is_mock() -> bool:
    return not BEDS24_API_KEY


def _headers() -> dict:
    return {"token": BEDS24_API_KEY, "Content-Type": "application/json"}


async def update_price(room_id: str, target_date: date, price: float) -> bool:
    if _is_mock():
        logger.info(f"[MOCK] Beds24: roomId={room_id} → €{price} per {target_date}")
        return True

    date_str = str(target_date)
    payload = [
        {
            "roomId": int(room_id),
            "calendar": [{"from": date_str, "to": date_str, "price1": price}],
        }
    ]
    logger.info(f"Beds24 update_price: roomId={room_id} date={date_str} price={price}")

    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BEDS24_BASE_URL}/inventory/rooms/calendar",
            headers=_headers(),
            json=payload,
        )
        logger.info(f"Beds24 response: {r.status_code} {r.text}")
        if r.status_code == 200:
            return True
        raise ValueError(f"Beds24 HTTP {r.status_code}: {r.text}")


async def update_prices_bulk(updates: list[dict]) -> dict[str, bool]:
    if _is_mock():
        return {u["beds24_id"]: True for u in updates}

    payload = [
        {
            "roomId": int(u["beds24_id"]),
            "calendar": [{"from": str(u["date"]), "to": str(u["date"]), "price1": u["price"]}],
        }
        for u in updates
    ]

    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BEDS24_BASE_URL}/inventory/rooms/calendar",
            headers=_headers(),
            json=payload,
        )
        if r.status_code == 200:
            return {u["beds24_id"]: True for u in updates}
        raise ValueError(f"Beds24 HTTP {r.status_code}: {r.text}")


async def get_current_prices(room_ids: list[str], target_date: date) -> dict[str, float]:
    if _is_mock():
        return {room_id: 0.0 for room_id in room_ids}

    date_str = str(target_date)
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{BEDS24_BASE_URL}/inventory/rooms/calendar",
            headers=_headers(),
            params={"roomIds": ",".join(room_ids), "startDate": date_str, "endDate": date_str},
        )
        if r.status_code == 200:
            result = {}
            for room in r.json().get("data", []):
                calendar = room.get("calendar", [])
                if calendar:
                    result[str(room["roomId"])] = calendar[0].get("price1", 0.0)
            return result
        return {}


async def get_properties() -> list[dict]:
    if _is_mock():
        return []

    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{BEDS24_BASE_URL}/properties",
            headers=_headers(),
            params={"includeAllRooms": "true"},
        )
        if r.status_code == 200:
            return r.json().get("data", [])
        return []
