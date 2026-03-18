"""
Integrazione Beds24 API v2 per aggiornamento prezzi su Airbnb.
Documentazione: https://api.beds24.com/v2/

Autenticazione a due step (API v2):
  1. BEDS24_API_KEY = refresh token (da Beds24 → Account Access → API Key)
  2. POST /authentication/setup → ottieni access token (JWT, scade in 24h)
  3. Usa access token nelle chiamate successive con header "token: <access_token>"
"""
import httpx
import os
import logging
import time
from datetime import date

logger = logging.getLogger(__name__)

BEDS24_BASE_URL = "https://api.beds24.com/v2"
BEDS24_REFRESH_TOKEN = os.getenv("BEDS24_API_KEY")

# Cache access token in memoria (valido ~24h)
_access_token: str | None = None
_token_expires_at: float = 0


def _is_mock() -> bool:
    return not BEDS24_REFRESH_TOKEN


async def _get_access_token() -> str:
    """
    Scambia il refresh token con un access token JWT.
    Il token viene cachato in memoria per evitare richieste ripetute.
    """
    global _access_token, _token_expires_at

    # Riusa il token se ancora valido (con 5 minuti di margine)
    if _access_token and time.time() < _token_expires_at - 300:
        return _access_token

    logger.info("Beds24: richiesta nuovo access token")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BEDS24_BASE_URL}/authentication/setup",
            json={"refreshToken": BEDS24_REFRESH_TOKEN},
        )
        if response.status_code != 200:
            raise ValueError(
                f"Beds24 auth fallita HTTP {response.status_code}: {response.text}"
            )
        data = response.json()
        _access_token = data.get("token")
        expires_in = data.get("expiresIn", 86400)  # default 24h
        _token_expires_at = time.time() + expires_in
        logger.info("Beds24: access token ottenuto, scade in %ds", expires_in)
        return _access_token


async def _headers() -> dict:
    token = await _get_access_token()
    return {"token": token, "Content-Type": "application/json"}


async def update_price(room_id: str, target_date: date, price: float) -> bool:
    """
    Aggiorna il prezzo di un appartamento su Beds24 per una data specifica.
    Beds24 sincronizza automaticamente con Airbnb.
    """
    if _is_mock():
        logger.info(f"[MOCK] Beds24: roomId={room_id} → €{price} per {target_date}")
        return True

    date_str = str(target_date)
    payload = [
        {
            "roomId": int(room_id),
            "calendar": [
                {
                    "from": date_str,
                    "to": date_str,
                    "price1": price,
                }
            ],
        }
    ]
    logger.info(f"Beds24 update_price: roomId={room_id} date={date_str} price={price}")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BEDS24_BASE_URL}/inventory/rooms/calendar",
            headers=await _headers(),
            json=payload,
        )
        logger.info(f"Beds24 response: status={response.status_code} body={response.text}")
        if response.status_code == 200:
            return True
        raise ValueError(f"Beds24 HTTP {response.status_code}: {response.text}")


async def update_prices_bulk(
    updates: list[dict],  # [{"beds24_id": str, "date": date, "price": float}]
) -> dict[str, bool]:
    """
    Aggiorna più appartamenti in un'unica chiamata API.
    """
    if _is_mock():
        for u in updates:
            logger.info(f"[MOCK] Beds24: roomId={u['beds24_id']} → €{u['price']} per {u['date']}")
        return {u["beds24_id"]: True for u in updates}

    payload = [
        {
            "roomId": int(u["beds24_id"]),
            "calendar": [
                {
                    "from": str(u["date"]),
                    "to": str(u["date"]),
                    "price1": u["price"],
                }
            ],
        }
        for u in updates
    ]

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BEDS24_BASE_URL}/inventory/rooms/calendar",
            headers=await _headers(),
            json=payload,
        )
        if response.status_code == 200:
            return {u["beds24_id"]: True for u in updates}
        raise ValueError(f"Beds24 HTTP {response.status_code}: {response.text}")


async def get_current_prices(room_ids: list[str], target_date: date) -> dict[str, float]:
    """
    Recupera i prezzi correnti da Beds24 per una lista di roomId.
    """
    if _is_mock():
        return {room_id: 0.0 for room_id in room_ids}

    date_str = str(target_date)
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BEDS24_BASE_URL}/inventory/rooms/calendar",
            headers=await _headers(),
            params={
                "roomIds": ",".join(room_ids),
                "startDate": date_str,
                "endDate": date_str,
            },
        )
        if response.status_code == 200:
            data = response.json()
            result = {}
            for room in data.get("data", []):
                calendar = room.get("calendar", [])
                if calendar:
                    result[str(room["roomId"])] = calendar[0].get("price1", 0.0)
            return result
        return {}


async def get_properties() -> list[dict]:
    """
    Recupera la lista di tutte le proprietà su Beds24.
    """
    if _is_mock():
        return []

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BEDS24_BASE_URL}/properties",
            headers=await _headers(),
            params={"includeAllRooms": "true"},
        )
        if response.status_code == 200:
            return response.json().get("data", [])
        return []
