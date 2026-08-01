# Arcade Event Creator

Web form: select a show → auto-fill details → create a Leap ticket event + Airtable record in one submit.

## How it works

- **Backend (`app.py`)** — Flask. Serves the form, proxies Leap (ShowClix V2):
  creates the event shell (`POST /events`), attaches a General Admission price
  level (`POST /price_levels`), and returns the public ticket URL. Also manages
  the show catalog (`shows.json`).
- **Frontend (`templates/index.html`)** — after the backend returns the ticket
  URL, the browser posts the record directly to the Airtable **Schedule** table.
  The `const AT = {...}` block is filled in by Flask from `AT_API_KEY`,
  `AT_BASE_ID` and `AT_TABLE` in `.env` — don't hardcode credentials there.

  Because the browser talks to Airtable directly, the token is served to every
  client that loads the page. Fine on a trusted LAN; if this ever goes public,
  proxy the Airtable write through `app.py` instead.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# fill in .env
```

## Getting a Leap API token

Tokens are self-service in the Leap Admin UI (the old ShowClix
`POST /api/registration` endpoint no longer exists):

1. Log in at <https://admin.leapevents.com>
2. Go to <https://admin.leapevents.com/user>
3. Generate an **Integration Token** and copy it
4. Run the setup helper and paste it:

```bash
python get_leap_token.py
```

The script validates the token, writes `LEAP_API_TOKEN` to `.env`, and helps
you pick `LEAP_SELLER_ID` and `LEAP_VENUE_ID` from your account.

If Leap calls ever start failing with 401, generate a fresh token in the
admin and rerun the script.

## Current status

The app is complete but **not yet able to create events** — one credential is
missing. Picking this up:

**Working**

- The Leap Integration Token authenticates (sent as the `X-API-Token` header).
- `GET /venues` returns the full venue list, so `/api/venues` works.

**Blocked — `LEAP_SELLER_ID` is unknown**

`GET /sellers` returns `{"data":[]}` for our token even though the same token
authenticates fine against `/venues` (a bad token gives 401, so this is an
empty result, not an auth failure). `app.py` puts the seller ID in the
`relationships` block of every event create, so nothing can be created until
it's found. Things to try:

```bash
# the sellers relationship hanging off any venue
curl -H "X-API-Token: $LEAP_API_TOKEN" -H "Accept: application/vnd.api+json" \
  https://www.showclix.com/api/venues/47341/sellers
```

Failing that, the seller ID is visible in the admin UI URL at
<https://admin.leapevents.com>, or Leap support can widen the token's scope.

**Gotchas already found**

- `GET /series` returns 404 — that endpoint doesn't exist on this API host.
  `/api/series` catches it and returns an empty list, so it's harmless.
- The venue list contains duplicates: *Arcade Comedy Theater: Downstairs* is
  both `47341` and `82097`, and Upstairs is both `49108` and `86691`. There's
  also a `DELETE ME` venue at `47342`. Confirm which one has live events
  (`/venues/<id>/events`) before setting `LEAP_VENUE_ID`.

## Running

```bash
python app.py
# Runs on http://localhost:5050
```

It binds to `0.0.0.0`, so any machine on the network can reach it at
`http://<your-ip>:5050`.

## Endpoints

| Route | Purpose |
|---|---|
| `GET /` | The form |
| `GET /shows.json` | Show catalog (consumed by the frontend) |
| `GET /show-data/<name>` | Single show details |
| `GET /api/venues` | Venues from your Leap account (frontend falls back to a hardcoded list if unavailable) |
| `GET /api/series` | Series from your Leap account |
| `POST /shows` | Append a new show to `shows.json` |
| `POST /create` | Create the Leap event + price level, return ticket URL |

## Editing shows

Use the **Add Show to Catalog** tab, or edit `shows.json` by hand. Each show
has: `name`, `slug`, `description`, `short_description`, `default_price`,
`default_capacity`, `default_duration_minutes`, `tags`, and optionally
`image_url`.

## After creation

The Airtable Schedule record is created with `Status = Draft` and the ticket
URL written into `Showclix Ticket Link`, so downstream sync (ghostlight →
WordPress) picks it up as usual.

## WordPress auth (future)

The app is currently standalone with no authentication. The plan is to
eventually put it behind WordPress auth; nothing in the app assumes it yet.
# ACT_leepair
# ACT_leepair
# ACT_leepair
