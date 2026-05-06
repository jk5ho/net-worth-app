# 💰 Interactive Net Worth Dashboard

A Streamlit application for tracking net worth across providers, account
types, and currencies. Edit your ledger inline, snapshot balances per
date period, and visualise allocation with interactive Plotly charts.

## Features

- **Multi-user accounts** — email + password login, bcrypt-hashed,
  per-user data isolation. Deploy once, share with family.
- **Database persistence** — SQLAlchemy 2.0; SQLite by default, swap to
  Postgres / MySQL via the `DATABASE_URL` env var.
- Two editable AgGrid ledgers with separate column shapes:
  - **Liquid Assets** — `Provider · Type · Class · Product · Currency · <dates>`
  - **Non-Liquid Assets / Liabilities** —
    `Provider · Type · Details · Currency · <dates>`
- Drag-to-reorder rows within each table
- Multi-currency support (USD / CAD / JPY / EUR / GBP) with live FX rates
- Per-period snapshots so you can track net worth growth over time
- Asset allocation, liquid allocation, and per-provider exposure charts
- Hide-balances toggle for screen-sharing
- Collapsible sidebar — starts hidden behind a burger toggle in the
  top-left so the dashboard takes the full width
- Random main-panel background image picked from your `backgrounds/`
  folder on each browser session
- CSV import / export from the sidebar — bring your existing data in,
  or download a backup any time

## Project Structure

```
net-worth-app/
├── net-worth-dashboard.py     # Streamlit entrypoint (thin orchestrator)
├── app/
│   ├── __init__.py
│   ├── config.py              # Constants (columns, options, colors, DB URL)
│   ├── database.py            # SQLAlchemy engine, User + LedgerRow models
│   ├── auth.py                # Password hashing, register, authenticate
│   ├── login_view.py          # Login + signup screen, session helpers
│   ├── currency.py            # CurrencyConverter + cached live-rate fetcher
│   ├── data_manager.py        # DataManager — DB I/O scoped per user
│   ├── sidebar.py             # Sidebar UI (account, periods, add row)
│   ├── dashboard.py           # KPIs and Plotly charts
│   ├── ledger.py              # Two editable AgGrid tables (liquid + non-liquid)
│   └── background.py          # Random main-panel background image
├── backgrounds/               # Drop background images here (jpg/png/webp/gif)
├── net_worth.db               # Local SQLite database (auto-created, gitignored)
├── net_worth_data.csv         # Sample CSV — import from the sidebar
├── requirements.txt
└── README.md
```

Each class owns one responsibility and is wired together in
`net-worth-dashboard.py`.

## Prerequisites

- Python 3.10+ (3.11 or 3.12 recommended)
- `pip` and `venv` (bundled with modern Python installs)

## Run Locally

From the project root:

```bash
# 1. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch the app
streamlit run net-worth-dashboard.py
```

Streamlit prints a local URL (default `http://localhost:8501`). Open it
in your browser.

To stop the server, press `Ctrl+C` in the terminal. To exit the venv,
run `deactivate`.

## Using the App

1. **Create an account** on the **Create account** tab (email + password,
   minimum 8 characters). You'll be signed in immediately. Returning
   visits use the **Sign in** tab.
2. **(Optional) Import a CSV** — open the sidebar, expand
   *Import / Export CSV*, and upload `net_worth_data.csv` (or any other
   CSV that matches the column shape). This replaces your in-database
   ledger atomically.
3. **Add a date period** in the sidebar (e.g. `4/30`). The first period
   you add becomes the baseline column on the ledger.
4. **Add rows** via *Add New Row Entry*. First pick the **Entry kind**
   radio:
   - *Investment (liquid)* — fill in Class (from the liquid list),
     Product, Currency, value.
   - *Asset / Liability (non-liquid)* — fill in Class (Real Estate /
     Liability / Autos), a free-text Details field, Currency, value.
5. **Edit inline** in either ledger table. Changes stay in memory until
   you click **Save all changes**, which writes them to the database.
6. **Click *Refresh Graphs*** to push pending ledger edits into the
   dashboard charts.
7. **Switch base currency** at the top of the sidebar to view all
   metrics in a different currency.
8. **Sign out** at the top of the sidebar when you're done.

### Conventions

- **Liabilities** (Class = `Liability`) are stored as negative numbers
  and live in the non-liquid table.
- **Liquidity is derived from `Class`** — there is no separate Liquid
  flag. Edit the lists in `app/config.py` to recategorise:
  - `LIQUID_CLASSES` — Cash, ETFs, Stocks, Crypto, MMF, Bonds, Funds, Alts
  - `NON_LIQUID_CLASSES` — Real Estate, Liability, Autos
- **Schema split per table:** liquid rows describe themselves with
  `Class` + `Product`; non-liquid rows use a single free-text `Details`
  column. Both columns coexist in the underlying CSV — each row
  populates only the side relevant to its Class.
- **Legacy CSVs** with `Detail` (singular) or `Liquid` columns are
  migrated transparently on load — those columns are dropped and will
  not be re-written on save. The new `Details` (plural) column is
  added with empty values where missing.

## Accounts & Authentication

The app ships with a minimal email/password auth flow.

- **Signup**: email + password (≥ 8 chars) + optional display name.
- **Login**: standard email/password challenge — generic
  *"Invalid email or password"* on failure (no enumeration leak).
- **Hashing**: passwords are hashed with `bcrypt` (per-user salt, cost
  factor controlled by the `bcrypt` library defaults). Plaintext
  passwords are never stored.
- **Session**: the logged-in user lives in `st.session_state` only.
  **You will be signed out on a browser refresh** — there is no
  long-lived cookie. This is intentional for the v1 surface area.
- **Per-user isolation**: every DB read/write is scoped by `user_id`,
  so two accounts on the same deployment cannot see each other's data.

To wipe an account locally: delete `net_worth.db` and re-sign-up.

## Data Storage

All data lives in a relational database accessed via SQLAlchemy. By
default that's a SQLite file at `./net_worth.db`. To use an external
database (Postgres, MySQL, etc.), set the `DATABASE_URL` environment
variable before starting Streamlit:

```bash
# Example: Postgres (Neon, Supabase, RDS, self-hosted, ...)
export DATABASE_URL='postgresql+psycopg://user:pw@host:5432/dbname'
streamlit run net-worth-dashboard.py

# Example: MySQL
export DATABASE_URL='mysql+pymysql://user:pw@host:3306/dbname'
```

Tables are created automatically on first boot
(`Base.metadata.create_all`) — no separate migration step.

### Schema

```
users          (id, email UNIQUE, password_hash, display_name,
                periods JSON, created_at)
ledger_rows    (id, user_id FK, position, provider, type, asset_class,
                product, details, currency, values JSON)
```

Period values are stored as a JSON dict per row (e.g.
`{"3/30": 287868.00, "4/23": 287868.00}`) so adding/removing a date
period is a single column update on the user, not a schema migration.

### Importing your existing CSV

Open the sidebar → *Data Management* → *Import / Export CSV* and upload
your existing `net_worth_data.csv`. The importer:

- drops legacy `Detail` / `Liquid` columns and AgGrid junk columns
- back-fills any missing base columns
- coerces period columns to numeric
- replaces your account's ledger atomically

You can also download the current ledger as a CSV from the same
expander — handy for quick backups.

## Deployment

### Option A — Self-host (single server)

Any host that can run `streamlit run` and offers persistent disk works:

```bash
# On the server
git clone <your-repo> && cd net-worth-app
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# Optional: point at a real DB
export DATABASE_URL='postgresql+psycopg://...'
streamlit run net-worth-dashboard.py --server.port 80 --server.address 0.0.0.0
```

Front it with nginx/Caddy/Cloudflare Tunnel for HTTPS.

### Option B — Streamlit Community Cloud + hosted Postgres

Streamlit Cloud's filesystem is **ephemeral**, so SQLite would lose
data on each redeploy. Use a managed Postgres (Neon, Supabase,
Railway, etc., all of which have free tiers):

1. Create a Postgres database, copy the connection URL.
2. In your Streamlit Cloud app's **Settings → Secrets**, add:
   ```toml
   DATABASE_URL = "postgresql+psycopg://user:pw@host:5432/db"
   ```
   (Streamlit auto-exports secrets as env vars at runtime.)
3. Push the repo. The first boot creates tables.

### Option C — Docker / container hosts

A minimal Dockerfile would copy the repo, install
`requirements.txt`, mount a volume at `/data`, and set
`DATABASE_URL=sqlite:////data/net_worth.db`. Any container host
(Fly.io, Railway, Render, ECS, etc.) will work.

## Background Images

Drop any number of images into the `backgrounds/` folder at the project
root. Supported formats: `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`.

On every fresh browser session the app picks one at random and paints
it behind the main panel only — the sidebar keeps its own background.
The choice is cached in the session, so it stays stable while you
interact with the dashboard. Refresh the browser to roll a new one.

A semi-transparent **black** veil (default 55% opacity) is layered on
top of the image so the photo reads as a *darkened* version of itself
rather than washed-out — and so dashboard text stays readable on busy
photos. Page-bg-overlapping text (page title, dashboard subheader,
metric labels/values, dividers) is recoloured light to keep contrast.

To make the image more (or less) visible, tune the overlay in
`net-worth-dashboard.py`:

```python
# 0.0 = raw image, 1.0 = image fully hidden
BackgroundImage(overlay_opacity=0.4).apply()                     # more image
BackgroundImage(overlay_opacity=0.7).apply()                     # nearly black
BackgroundImage(overlay_rgb="255, 255, 255",                     # back to a
               overlay_opacity=0.78,                             # light/washed
               foreground_color="#262730").apply()               # look
```

If the folder is empty (or missing), the dashboard falls back to
Streamlit's default theme background — no error.

> Tip: keep individual images under ~1 MB. The image is base64-inlined
> into the page CSS, so very large files will slow down initial render.

## Sidebar / Burger Menu

The sidebar starts collapsed. Use Streamlit's toggle in the top-left
of the page (the small chevron / burger icon) to open it when you need
to add rows, switch base currency, or manage date periods.

## Live FX Rates

Rates come from
[`exchangerate-api.com`](https://api.exchangerate-api.com/v4/latest/USD)
and are cached for one hour via Streamlit's `@st.cache_data`. If the
API call fails, the app falls back to the static rates defined in
`app/config.py::FALLBACK_FX_RATES`.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `ModuleNotFoundError: streamlit` | Activate the venv and re-run `pip install -r requirements.txt` |
| Port 8501 already in use | `streamlit run net-worth-dashboard.py --server.port 8502` |
| Charts feel stale after edits | Click **🔄 Refresh Graphs** in the dashboard header |
| FX rates look wrong | Expand *View Live Exchange Rates* in the sidebar; rates refresh hourly |
| No background image showing | Confirm `backgrounds/` contains an image with a supported extension and refresh the browser |
| Background feels stuck on one image | The pick is cached per session — refresh the browser to roll a new one |
| Signed out unexpectedly | Browser refreshes end the session by design — re-sign-in |
| `OperationalError: no such table: users` | The DB couldn't be created at the configured `DATABASE_URL`. Check filesystem permissions or the connection string. |
| Forgot your password | No reset flow yet — delete `net_worth.db` (wipes ALL accounts) or update the `password_hash` directly in the DB |
| Different user but seeing prior data | Sign out then sign in again — the session cache is invalidated on each login. |
