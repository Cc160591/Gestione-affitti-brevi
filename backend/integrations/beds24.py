"""
Integrazione Beds24 API v2 per aggiornamento prezzi su Airbnb.
Documentazione: https://api.beds24.com/v2/

Autenticazione: API Key (impostata in Beds24 → Account Access → API Key)
Env var richiesta: BEDS24_API_KEY
"""
import httpx
import os
import logging
from datetime import date

logger = logging.getLogger(__name__)

BEDS24_BASE_URL = "https://api.beds24.com/v2"
BEDS24_API_KEY = os.getenv("BEDS24_API_KEY")


def _headers() -> dict:
    return {"token": BEDS24_API_KEY, "Content-Type": "application/json"}


def _is_mock() -> bool:
    return not BEDS24_API_KEY


async def update_price(room_id: str, target_date: date, price: float) -> bool:
    """
    Aggiorna il prezzo di un appartamento su Beds24 per una data specifica.
    Beds24 sincronizza automaticamente con Airbnb.
    Lancia ValueError con il body della risposta se Beds24 restituisce errore.
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
    logger.info(f"Beds24 request: POST {BEDS24_BASE_URL}/inventory/rooms/calendar payload={payload}")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BEDS24_BASE_URL}/inventory/rooms/calendar",
            headers=_headers(),
            json=payload,
        )
        logger.info(f"Beds24 response: status={response.status_code} body={response.text}")
        if response.status_code == 200:
            return True
        else:
            raise ValueError(
                f"Beds24 HTTP {response.status_code}: {response.text}"
            )


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
            headers=_headers(),
            json=payload,
        )
        if response.status_code == 200:
            return {u["beds24_id"]: True for u in updates}
        else:
            logger.error(f"Beds24: errore bulk update: {response.text}")
            return {u["beds24_id"]: False for u in updates}


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
            headers=_headers(),
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
            headers=_headers(),
            params={"includeAllRooms": "true"},
        )
        if response.status_code == 200:
            return response.json().get("data", [])
        return []
