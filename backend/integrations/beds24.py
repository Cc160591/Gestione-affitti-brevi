"""
Integrazione Beds24 API v2 per aggiornamento prezzi su Airbnb.
Documentazione: https://api.beds24.com/v2/

Autenticazione:
  - BEDS24_REFRESH_TOKEN: token di lunga durata (30 giorni inattività)
  - L'access token (24h) viene ottenuto automaticamente e cachato in memoria.

Setup iniziale (una tantum):
  1. Genera un invite code da Beds24 → Account → API
  2. Chiama GET https://api.beds24.com/v2/authentication/setup con header "code: {invite_code}"
  3. Salva il refreshToken ottenuto come BEDS24_REFRESH_TOKEN nelle env vars
"""
import httpx
import os
import logging
from datetime import date, datetime

logger = logging.getLogger(__name__)

BEDS24_BASE_URL = "https://api.beds24.com/v2"
BEDS24_REFRESH_TOKEN = os.getenv("BEDS24_REFRESH_TOKEN")

# Cache access token in memoria
_access_token: str | None = None
_token_expires_at: datetime | None = None


async def _get_access_token() -> str | None:
    """Ottiene un access token valido, rinnovandolo se necessario."""
    global _access_token, _token_expires_at

    if not BEDS24_REFRESH_TOKEN:
        return None

    # Usa il token cachato se ancora valido (con margine di 5 min)
    if _access_token and _token_expires_at:
        remaining = (_token_expires_at - datetime.utcnow()).total_seconds()
        if remaining > 300:
            return _access_token

    # Rinnova il token
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BEDS24_BASE_URL}/authentication/token",
            headers={"refreshToken": BEDS24_REFRESH_TOKEN},
        )
        if response.status_code == 200:
            data = response.json()
            _access_token = data["token"]
            expires_in = data.get("expiresIn", 86400)
            from datetime import timedelta
            _token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            logger.info("Beds24: access token rinnovato")
            return _access_token
        else:
            logger.error(f"Beds24: errore rinnovo token: {response.text}")
            return None


def _is_mock() -> bool:
    return not BEDS24_REFRESH_TOKEN


async def update_price(room_id: str, target_date: date, price: float) -> bool:
    """
    Aggiorna il prezzo di un appartamento su Beds24 per una data specifica.
    Beds24 sincronizza automaticamente con Airbnb.
    """
    if _is_mock():
        logger.info(f"[MOCK] Beds24: roomId={room_id} → €{price} per {target_date}")
        return True

    token = await _get_access_token()
    if not token:
        logger.error("Beds24: impossibile ottenere access token")
        return False

    date_str = str(target_date)
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BEDS24_BASE_URL}/inventory/rooms/calendar",
            headers={
                "token": token,
                "Content-Type": "application/json",
            },
            json=[
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
            ],
        )
        if response.status_code == 200:
            return True
        else:
            logger.error(f"Beds24: errore update roomId={room_id}: {response.text}")
            return False


async def update_prices_bulk(
    updates: list[dict],  # [{"beds24_id": str, "date": date, "price": float}]
) -> dict[str, bool]:
    """
    Aggiorna più appartamenti in un'unica chiamata API.
    Restituisce dict {beds24_id: success}.
    """
    if _is_mock():
        for u in updates:
            logger.info(f"[MOCK] Beds24: roomId={u['beds24_id']} → €{u['price']} per {u['date']}")
        return {u["beds24_id"]: True for u in updates}

    token = await _get_access_token()
    if not token:
        return {u["beds24_id"]: False for u in updates}

    # Raggruppa per roomId per inviare una sola richiesta
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
            headers={"token": token, "Content-Type": "application/json"},
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

    token = await _get_access_token()
    if not token:
        return {}

    date_str = str(target_date)
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BEDS24_BASE_URL}/inventory/rooms/calendar",
            headers={"token": token},
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
    Utile per mappare gli ID Beds24 agli appartamenti nel DB.
    """
    if _is_mock():
        logger.info("[MOCK] Beds24: get_properties non disponibile senza token")
        return []

    token = await _get_access_token()
    if not token:
        return []

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BEDS24_BASE_URL}/properties",
            headers={"token": token},
            params={"includeAllRooms": "true"},
        )
        if response.status_code == 200:
            return response.json().get("data", [])
        return []
