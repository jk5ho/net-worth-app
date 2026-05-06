"""Application-wide constants and configuration."""

import os

CSV_FILE = "net_worth_data.csv"

# Override via environment variable for production deployments, e.g.:
#   export DATABASE_URL=postgresql+psycopg://user:pw@host/db
# Defaults to a local SQLite file so ``streamlit run`` works out of the
# box with no external dependencies.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///net_worth.db")

BASE_COLS = [
    "Provider",
    "Type",
    "Class",
    "Product",
    "Details",
    "Currency",
]

TYPE_OPTIONS = [
    "Personal",
    "401k",
    "HSA",
    "Roth IRA",
    "Trad. IRA",
    "RRSP",
    "GRSP",
]

CLASS_OPTIONS = [
    "ETFs",
    "Stocks",
    "Crypto",
    "Cash",
    "Real Estate",
    "Liability",
    "Funds",
    "Alts",
    "Bonds",
    "MMF",
    "Autos",
]

CURRENCY_OPTIONS = ["USD", "CAD", "JPY", "EUR", "GBP"]

# Liquid investment classes — these rows render in the "Liquid Assets"
# table with Provider/Type/Class/Product columns.
LIQUID_CLASSES = ["Cash", "ETFs", "Stocks", "Crypto", "MMF", "Bonds", "Funds", "Alts"]

# Non-liquid asset / liability classes — these rows render in the
# "Non-Liquid Assets / Liabilities" table with a single Details column
# instead of Class/Product.
NON_LIQUID_CLASSES = ["Real Estate", "Liability", "Autos"]

CLASS_COLORS = {
    "Cash": "#2ca02c",
    "ETFs": "#1f77b4",
    "Stocks": "#17becf",
    "Crypto": "#ff7f0e",
    "Real Estate": "#9467bd",
    "Liability": "#d62728",
    "Funds": "#e377c2",
    "Alts": "#7f7f7f",
    "Bonds": "#bcbd22",
    "MMF": "#8c564b",
    "Autos": "#aec7e8",
}

# Fallback rates if the live FX API fails. Values represent units per 1 USD.
FALLBACK_FX_RATES = {
    "USD": 1.0,
    "CAD": 1.36,
    "JPY": 150.5,
    "EUR": 0.92,
    "GBP": 0.79,
}

FX_API_URL = "https://api.exchangerate-api.com/v4/latest/USD"
FX_CACHE_TTL_SECONDS = 3600
