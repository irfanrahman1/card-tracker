# Card Tracker

Track credit cards and their reward rules, log purchases, see monthly spending
by category, and get a "best card for this purchase" recommendation.

- **Backend:** FastAPI + SQLite (via SQLAlchemy)
- **Frontend:** React + Vite (mobile-responsive; tabs become a bottom bar on phones)
- **Hosting:** free on Vercel (website on the CDN, API as a Python function) + Neon Postgres; a Dockerfile is included for container hosts. See [DEPLOY.md](DEPLOY.md)
- Accounts with email + password; each person's data is private. No Plaid (yet): the code is structured so it can be added as another transaction source.

## Build status

| Stage | What | Status |
|---|---|---|
| 1 | Backend core: cards + reward rules, manual purchases, categories, swappable sources | ✅ |
| 2 | Monthly summary, recommendation, CSV upload, demo data | ✅ |
| 3 | React frontend | ✅ |
| 4 | Real bank CSVs, 8 categories, refunds, fix-a-category | ✅ |
| 5 | Card catalog, point values, fees/perks, wallet optimizer, tests | ✅ |
| 6 | Accounts (sign up / log in), privacy, demo account, Postgres-ready | ✅ |
| 7 | Deploy: Vercel + Neon Postgres (free), Dockerfile for other hosts | ✅ |
| 8 | Bank linking with Plaid (sandbox) | ⏳ |
| 9 | CI, architecture docs, demo | ⏳ |

## Quick start (macOS)

Requires Python 3.10+ and Node.js 18+ (`brew install node` if `node --version` fails).

```bash
cd card-tracker
./start.sh
```

Then open **http://localhost:5173** and click **⚡ Load demo data**.
The first run installs everything (about a minute); later runs start in seconds.
Press **Ctrl+C** to stop.

**On your phone:** with the app running and your phone on the same Wi-Fi, open the
`Network:` address `start.sh` prints (like `http://192.168.1.20:5173`).

## Project layout

```
card-tracker/
├── .gitignore
├── README.md
├── start.sh              # one command: installs + starts backend and frontend
├── vercel.json           # Vercel: build, routing, security headers
├── api/index.py          # Vercel entry point for the API
├── Dockerfile            # container hosts: builds the website, runs the API (serves both)
├── DEPLOY.md             # how to put it online for free
├── sample-data/
│   └── purchases.csv     # example CSV to try the upload
└── backend/
    ├── requirements.txt
    ├── requirements-dev.txt  # test tools (pytest)
    ├── tests/                # unit tests for rewards, optimizer, CSV parsing
    ├── .env.example          # sample settings; copy to .env (never committed)
    └── app/
        ├── main.py           # FastAPI app, CORS, routers
        ├── database.py       # SQLite engine + session
        ├── models.py         # tables: cards, reward_rules, transactions
        ├── schemas.py        # request/response validation
        ├── categories.py     # category list + keyword guessing (Amazon → shopping)
        ├── recommendation.py # "best card for this purchase" logic (no web/DB code)
        ├── optimizer.py      # wallet optimizer: best cards for your yearly spending
        ├── catalog/
        │   └── cards.json    # popular cards + reward rules (data, not code)
        ├── ingest.py         # saves transactions from ANY source (shared clean-up)
        ├── sources/          # where transactions come from
        │   ├── base.py       # TransactionSource interface
        │   ├── manual.py     # manual entry
        │   ├── csv_source.py # CSV upload
        │   └── demo.py       # demo cards + sample purchases
        └── routers/
            ├── cards.py
            ├── transactions.py   # incl. CSV upload
            ├── insights.py       # monthly summary + recommendation
            └── demo.py           # load demo data / clear all
└── frontend/
    ├── package.json
    ├── vite.config.js        # dev server; forwards /api to the backend
    └── src/
        ├── App.jsx           # header, tabs, toasts, backend status
        ├── api.js            # every backend call in one place
        ├── categories.js     # category labels/colors + formatting helpers
        ├── styles.css        # all styling (light + dark mode, mobile layout)
        └── components/
            ├── Overview.jsx      # month totals, category bars, trend chart
            ├── CategoryBars.jsx
            ├── TrendChart.jsx
            ├── BestCard.jsx      # "best card for this purchase"
            ├── Optimizer.jsx     # yearly wallet value + cards to add
            ├── Purchases.jsx     # add purchase, CSV upload, purchase list
            └── Cards.jsx         # add/edit/delete cards and reward rules
```

## Manual setup (if you'd rather not use start.sh)

### Backend

Requires Python 3.10+. Check with `python3 --version`.

**macOS:** the `python3` from Apple's Command Line Tools is often 3.9, which is
too old. Install a newer one with [Homebrew](https://brew.sh):

```bash
brew install python@3.12
```

Then use `python3.12` in place of `python3` when creating the venv below. Once
the venv is activated, plain `python`/`pip` point at the right version.
(Stage 3 will also need Node.js: `brew install node`.)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API runs at http://localhost:8000. **http://localhost:8000/docs** is an auto-generated page for testing the API by hand
(it's for developers; the real app is at http://localhost:5173).

The SQLite database is created automatically as `backend/card_tracker.db`
(ignored by git). Delete that file to start fresh.

### Optional settings

Defaults work out of the box. To override them, copy `.env.example` to `.env`
and start the server with:

```bash
uvicorn app.main:app --reload --env-file .env
```

`.env` is in `.gitignore`. Don't commit keys or secrets.

### Frontend (in a second terminal)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The backend must be running too. If it isn't,
the app shows a red "Can't reach the backend" banner.

## Running tests

```bash
cd backend
source venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest
```

To run the same tests against Postgres (like production), set
`TEST_DATABASE_URL=postgresql://...` to an empty test database first.

## Accounts, security and privacy

Everyone signs up with an email and a password (or clicks **Try the demo** for a
throwaway account with sample data, deleted after 24 hours). Code: `backend/app/auth.py`
and `backend/app/routers/auth.py`.

| Protection | How |
|---|---|
| Passwords never stored | Argon2id hashes (salted, deliberately slow). Login errors don't reveal whether an email has an account, and take the same time either way. |
| Sessions can't be stolen by page scripts | A random 256-bit token in an `HttpOnly`, `SameSite=Lax` cookie (`Secure` over HTTPS). Only its SHA-256 hash is stored, so a leaked database can't be used to log in. |
| Private data | Every card, purchase and category rule has an owner (`user_id`); every query filters by the logged-in user, and other people's ids return 404. Covered by `tests/test_auth_and_privacy.py`. |
| Brute force | 5 failed logins per IP or email in 15 minutes blocks further tries for a while, tracked in the database (only hashed keys) so it holds across servers. Forwarded-for headers are only trusted from the host's own proxy, so faking them doesn't help. |
| Cross-site attacks | No CORS; state-changing requests from other websites are rejected (Origin check) on top of SameSite cookies. Security headers: `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Cache-Control: no-store` on the API. |
| Minimal data | Only an email. Never card numbers. |
| Leave anytime | Account menu: delete all my data, or delete the account and everything in it. Changing the password logs out other devices. |

**Upgrading an older copy:** data created before accounts existed is given to the
first account you create, so your cards and purchases carry over.

**Production settings** (environment variables, never in code): `DATABASE_URL`
(Postgres), `COOKIE_SECURE=true`, `TRUSTED_PROXY_HOPS=1` (behind the host's proxy).

## Concepts

**Categories:** `food`, `transportation`, `groceries`, `shopping`, `travel`,
`subscriptions`, `fees` (card fees), `other`. Each purchase's category is chosen in this order:

1. Anything from **Amazon always counts as shopping**.
2. A category you picked for that merchant in the app (remembered, see below).
3. The bank's own category label, if the CSV has one (e.g. Chase "Food & Drink").
4. Keywords in the merchant name: "halal", "OMNY", "Booking.com", `TST*` (restaurant terminals)…
5. Otherwise `other`.

All of this lives in `backend/app/categories.py`. Add keywords there for stores it misses.

**Fixing a category:** on the Purchases tab, click a purchase's category and pick
another. Every purchase from that merchant moves too, and future uploads use your choice.

**Refunds and credits** (Amazon returns, Amex statement credits) are stored as negative
amounts, so they subtract from their category. **Card payments** ("AUTOPAY PAYMENT - THANK YOU")
are skipped. They're you paying the bill, not spending.

**Reward rules:** each card has a `base_rate` (percent back on everything)
plus optional per-category rules, e.g. `groceries: 4` means 4% (or 4x points).

**Transaction sources:** every input (manual form, CSV, demo data, later Plaid)
is a `TransactionSource` with one method, `fetch()`, that returns purchases.
`ingest.save_from_source()` does the shared work: normalizing categories,
dropping unknown card ids, and skipping duplicates via `external_id`.

### Adding Plaid later

1. Add `plaid-python` to `requirements.txt`; put `PLAID_CLIENT_ID` / `PLAID_SECRET` in `.env` (never in code).
2. Create `app/sources/plaid.py` with a `PlaidSource(TransactionSource)` whose
   `fetch()` calls Plaid's `/transactions/sync` and maps each result to
   `TransactionIn` (use Plaid's `transaction_id` as `external_id` so re-syncs don't duplicate).
3. Add a route that calls `save_from_source(db, PlaidSource(...))`.

## CSV format

Upload your card's export as-is. Tested with American Express; also handles the
column layouts of Chase, Capital One, Discover, Citi, Apple Card and Bank of America.
Uploading overlapping exports (e.g. last month and this month) doesn't create duplicates.

**Getting the file:** log in to your card's website → Activity/Transactions → Download → CSV.
Then on the Purchases tab, pick that card in "Card for rows that don't name one" and upload.

Column names are matched loosely (any case):

| Field | Accepted headers | Required |
|---|---|---|
| date | `date`, `transaction date`, `posted date`… | yes (`2026-10-03`, `10/03/2026`, …) |
| merchant | `merchant`, `name`, `payee`, `description` | yes |
| amount | `amount`, or separate `debit` / `credit` columns | yes. Whichever sign most rows use counts as a purchase; the other sign is a refund |
| category | `category` | no, guessed if blank |
| type | `type` | no (`Payment` rows are skipped, `Return` rows count as refunds) |
| card | `card`, `card name` | no, matched to your card names |

See `sample-data/purchases.csv` for a small example.

## Card catalog and point values

`backend/app/catalog/cards.json` lists 18 popular US cards (Amex, Chase, Capital One,
Citi, Wells Fargo, Discover, Bank of America, Apple, Robinhood) with their bonus
categories, caps and annual fees, each with the date its terms were checked and a
source link. Pick one on the Cards tab and everything fills in. Terms change, so
update the JSON when they do.

Some cards need more than "X% on a category":

- **Rotating quarterly categories** (Discover it, Chase Freedom Flex): the rule has a
  `valid_until` date (it stops counting after the quarter) and `portion: 0.25` (the
  optimizer applies it to a quarter of your yearly spending). Update these each quarter.
- **Shared caps** (BofA Customized Cash, Freedom Flex): rules with the same `cap_group`
  on a card use up one cap together.
- **Choose your category** (BofA Customized Cash): you pick the 3% category when adding
  the card; the optimizer tries the pick that suits your spending best.

Cards are compared by **value per dollar in cents**: rate × point value. 3% cash back is
3¢/$; 4 points/$ at 1.25¢ per point is 5¢/$. Point value defaults to 1¢ (a safe,
cash-like value) and you can change it per card.

## Wallet optimizer (Optimize tab)

`backend/app/optimizer.py` takes a year of spending per category (your last 12 months
of purchases, scaled to a year, or numbers you type in) and:

1. Assigns each dollar to the best card in your wallet, filling yearly caps first
   (e.g. 6% on the first $6,000 of groceries, then the next best card).
2. Subtracts annual fees and adds the yearly value of perks you said you use.
3. Tries adding each catalog card and ranks them by how much they'd add per year after fees.
4. Finds the best single card and the best two-card combination for your spending.

## Recommendation logic

`backend/app/recommendation.py`: for a purchase's category, each card earns its
rule for that category if it has one, otherwise its base rate. Cards are ranked by
value per dollar (rate × point value); the top one is "best". If you give a merchant instead of a category,
the category is guessed first (so Amazon → shopping).

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/signup` · `/login` · `/logout` | Create an account / log in / log out (sets or clears the session cookie) |
| GET | `/api/auth/me` | Who's logged in (401 if nobody) |
| POST | `/api/auth/demo` | Throwaway demo account with sample data |
| POST | `/api/auth/change-password` · `/delete-account` | Change password / delete account and all data |
| GET | `/api/categories` | List categories |
| GET / POST | `/api/cards` | List / add cards (with `rules`) |
| PUT / DELETE | `/api/cards/{id}` | Edit / remove a card |
| GET | `/api/transactions?month=YYYY-MM&category=food` | List purchases (both filters optional) |
| PATCH | `/api/transactions/{id}` | Change category (also that merchant's other purchases + remembered) or card |
| POST | `/api/transactions` | Add a purchase manually |
| DELETE | `/api/transactions/{id}` | Remove a purchase |
| POST | `/api/transactions/upload` | Import a CSV (form fields: `file`, optional `card_id`) |
| GET | `/api/summary?month=YYYY-MM&card=ID` | Spending by category for a month (defaults to latest), for all cards or one (`card=none` = no card), rewards earned vs. best possible, and spending per card |
| GET | `/api/summary/trend?card=ID` | Spending by category for every month (optional card filter) |
| GET | `/api/recommend?amount=50&category=food` | Best card (or use `merchant=Amazon` instead of `category`) |
| POST | `/api/demo/load` | Add sample cards + ~90 sample purchases to your account (safe to repeat) |
| POST | `/api/demo/clear` | Delete all your cards, purchases and category fixes |
| GET | `/api/cards/catalog` | Popular cards you can add in one click |
| POST | `/api/cards/from-catalog/{catalog_id}` | Add a catalog card to your wallet |
| POST | `/api/optimizer` | Yearly wallet value and best cards to add (optional what-if `spending`) |
