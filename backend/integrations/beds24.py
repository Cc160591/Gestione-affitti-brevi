"""
Integrazione Beds24 API per aggiornamento prezzi su Airbnb.
Documentazione: https://beds24.com/api/v2
"""
import httpx
import os
from datetime import date


BEDS24_API_KEY = os.getenv("BEDS24_API_KEY")
BEDS24_BASE_URL = "https://beds24.com/api/v2"


async def update_price(beds24_prop_id: str, target_date: date, price: float) -> bool:
    """
    Aggiorna il prezzo di un appartamento su Beds24 per una data specifica.
    Beds24 si occupa della sincronizzazione con Airbnb.

    Returns True se l'aggiornamento è riuscito, False altrimenti.
    """
    if not BEDS24_API_KEY:
        print(f"[MOCK] Beds24: aggiornato {beds24_prop_id} → €{price} per {target_date}")
        return True

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BEDS24_BASE_URL}/prices",
            headers={
                "token": BEDS24_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "propId": beds24_prop_id,
                "roomId": 0,
                "prices": [
                    {
                        "date": str(target_date),
                        "price": price,
                    }
                ],
            },
        )
        if response.status_code == 200:
            return True
        else:
            print(f"[Beds24] Errore aggiornamento {beds24_prop_id}: {response.text}")
            return False


async def update_prices_bulk(
    updates: list[dict],  # [{"beds24_id": str, "date": date, "price": float}]
) -> dict[str, bool]:
    """
    Aggiorna più appartamenti in sequenza.
    Restituisce dict {beds24_id: success}.
    """
    results = {}
    async with httpx.AsyncClient() as client:
        for update in updates:
            success = await update_price(
                update["beds24_id"],
                update["date"],
                update["price"],
            )
            results[update["beds24_id"]] = success
    return results


async def get_current_prices(beds24_prop_ids: list[str], target_date: date) -> dict[str, float]:
    """
    Recupera i prezzi correnti da Beds24 per una lista di appartamenti.
    Utile per mostrare il prezzo attuale nella proposta.
    """
    if not BEDS24_API_KEY:
        # Mock: restituisce prezzi fittizi
        return {prop_id: 100.0 for prop_id in beds24_prop_ids}

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BEDS24_BASE_URL}/prices",
            headers={"token": BEDS24_API_KEY},
            params={
                "propIds": ",".join(beds24_prop_ids),
                "startDate": str(target_date),
                "endDate": str(target_date),
            },
        )
        if response.status_code == 200:
            data = response.json()
            # TODO: adattare al formato reale della risposta Beds24
            return {item["propId"]: item["price"] for item in data.get("data", [])}
        return {}
