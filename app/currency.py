"""Currency conversion helpers backed by a live FX API."""

from __future__ import annotations

import json
import urllib.request
from typing import Dict

import pandas as pd
import streamlit as st

from app.config import (
    FALLBACK_FX_RATES,
    FX_API_URL,
    FX_CACHE_TTL_SECONDS,
)


@st.cache_data(ttl=FX_CACHE_TTL_SECONDS)
def _fetch_live_rates() -> Dict[str, float]:
    """Fetch live USD-based FX rates with a graceful fallback.

    Cached at the Streamlit layer so the API is only hit once per TTL window
    across the whole app session.
    """
    try:
        with urllib.request.urlopen(FX_API_URL) as response:
            payload = json.loads(response.read())
        rates = payload.get("rates", {})
        return {
            currency: float(rates.get(currency, fallback))
            for currency, fallback in FALLBACK_FX_RATES.items()
        } | {"USD": 1.0}
    except Exception:
        return dict(FALLBACK_FX_RATES)


class CurrencyConverter:
    """Convert per-row local-currency values into a chosen base currency."""

    def __init__(self, rates: Dict[str, float] | None = None) -> None:
        self.rates: Dict[str, float] = rates if rates is not None else _fetch_live_rates()

    def to_base(self, row: pd.Series, date_col: str, target_currency: str) -> float:
        """Convert ``row[date_col]`` from its local currency into ``target_currency``."""
        raw_value = row[date_col] if pd.notna(row[date_col]) else 0.0
        local_currency = row.get("Currency", "USD") or "USD"

        local_rate = self.rates.get(local_currency, 1.0)
        target_rate = self.rates.get(target_currency, 1.0)

        value_in_usd = float(raw_value) / local_rate
        return value_in_usd * target_rate
