"""ALOR Trade API — POST-ордера (мок-режим по умолчанию)."""

import requests
import json
from datetime import datetime
from core.logger import get_logger

import config

log = get_logger(__name__)

# Боевой контур (не dev!)
BASE_URL = "https://api.alor.ru"
OAUTH_URL = "https://oauth.alor.ru"

# Мок-режим: НЕ ставим реальные ордера
_MOCK_MODE = True


def _get_access_token() -> str:
    """Обменивает Refresh на Access (живёт 30 минут)."""
    from local_config import ALOR_TOKEN

    resp = requests.post(f"{OAUTH_URL}/refresh?token={ALOR_TOKEN}", timeout=10)
    resp.raise_for_status()
    return resp.json()["AccessToken"]


def place_order(
    symbol: str,
    side: str,  # "buy" / "sell"
    quantity: int,
    order_type: str = "market",  # "market" / "limit"
    price: float | None = None,
) -> dict:
    """
    Ставит ордер.
    В мок-режиме — возвращает фейковый ответ, НЕ ставит реальный ордер.

    Возвращает:
        {
            "order_id": str,
            "status": "filled" / "rejected" / "mock",
            "symbol": str,
            "side": str,
            "quantity": int,
            "price": float | None,
            "message": str,
        }
    """
    if _MOCK_MODE:
        log.info(
            "MOCK: %s %s %d @ %s (%s)",
            side,
            symbol,
            quantity,
            price or "market",
            order_type,
        )
        return {
            "order_id": f"mock-{datetime.now().timestamp()}",
            "status": "mock",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "message": "Мок-режим: ордер не отправлен",
        }

    # --- Реальный режим (когда будет токен с правами на торговлю) ---
    access = _get_access_token()
    url = f"{BASE_URL}/commandapi/warptrans/TRADE/v2/client/orders/actions/market"
    headers = {
        "Authorization": f"Bearer {access}",
        "Content-Type": "application/json",
    }
    payload = {
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "instrumentGroup": "RFUD",
    }
    if order_type == "limit" and price is not None:
        payload["price"] = price

    resp = requests.post(url, json=payload, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    return {
        "order_id": str(data.get("orderNumber", "")),
        "status": "filled" if data.get("orderNumber") else "rejected",
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "price": price,
        "message": data.get("message", "OK"),
    }


def cancel_order(order_id: str) -> bool:
    """Отменяет ордер. В мок-режиме — всегда True."""
    if _MOCK_MODE:
        log.info("MOCK: cancel order %s", order_id)
        return True

    access = _get_access_token()
    url = f"{BASE_URL}/commandapi/warptrans/TRADE/v2/client/orders/{order_id}"
    headers = {"Authorization": f"Bearer {access}"}
    resp = requests.delete(url, headers=headers, timeout=10)
    return resp.status_code == 200


def get_orders() -> list[dict]:
    """Список активных ордеров. В мок-режиме — пустой список."""
    if _MOCK_MODE:
        return []

    access = _get_access_token()
    url = f"{BASE_URL}/commandapi/warptrans/TRADE/v2/client/orders"
    headers = {"Authorization": f"Bearer {access}"}
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json().get("orders", [])
