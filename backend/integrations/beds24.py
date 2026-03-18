"""
Integrazione Beds24 API v2.
Autenticazione: refresh token → access token (JWT).

BEDS24_API_KEY = refresh token ottenuto tramite /admin/beds24-setup?invite_code=XXX
"""
import httpx
import os
import logging
import time
from datetime import date

logger = logging.getLogger(__name__)

BEDS24_BASE_URL = "https://api.beds24.com/v2"
BEDS24_REFRESH_TOKEN = os.getenv("BEDS24_API_KEY")

# Cache access token in memoria
_access_token: str | None = None
_token_expires_at: float = 0


def _is_mock() -> bool:
    return not BEDS24_REFRESH_TOKEN


async def _get_access_token() -> str:
    global _access_token, _token_expires_at

    if _access_token and time.time() < _token_expires_at - 300:
        return _access_token

    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BEDS24_BASE_URL}/authentication/setup",
            json={"refreshToken": BEDS24_REFRESH_TOKEN},
        )
        if r.status_code != 200:
            raise ValueError(f"Beds24 auth fallita HTTP {r.status_code}: {r.text}")
        data = r.json()
        _access_token = data["token"]
        _token_expires_at = time.time() + data.get("expiresIn", 86400)
        logger.info("Beds24: access token ottenuto")
        return _access_token


async def _headers() -> dict:
    token = await _get_access_token()
    return {"token": token, "Content-Type": "application/json"}


async def update_price(room_id: str, target_date: date, price: float) -> bool:
    if _is_mock():
        logger.info(f"[MOCK] Beds24: roomId={room_id} → €{price} per {target_date}")
        return True

    date_str = str(target_date)
    payload = [{"roomId": int(room_id), "calendar": [{"from": date_str, "to": date_str, "price1": price}]}]
    logger.info(f"Beds24 update_price: roomId={room_id} date={date_str} price={price}")

    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BEDS24_BASE_URL}/inventory/rooms/calendar",
            headers=await _headers(),
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
        {"roomId": int(u["beds24_id"]), "calendar": [{"from": str(u["date"]), "to": str(u["date"]), "price1": u["price"]}]}
        for u in updates
    ]
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BEDS24_BASE_URL}/inventory/rooms/calendar",
            headers=await _headers(),
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
            headers=await _headers(),
            params={"roomIds": ",".join(room_ids), "startDate": date_str, "endDate": date_str},
        )
        if r.status_code != 200:
            return {}
        result = {}
        for room in r.json().get("data", []):
            cal = room.get("calendar", [])
            if cal:
                result[str(room["roomId"])] = cal[0].get("price1", 0.0)
        return result


async def get_properties() -> list[dict]:
    if _is_mock():
        return []
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{BEDS24_BASE_URL}/properties",
            headers=await _headers(),
            params={"includeAllRooms": "true"},
        )
        if r.status_code == 200:
            return r.json().get("data", [])
        return []
