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

## Leap API token

The token is **not** self-service — Leap issues it and hands it over directly.
Ours came from our Leap contact (Mike, via Mindy). If calls start failing with
401, ask for a fresh one rather than trying to generate one in the admin UI.

Once you have it, the setup helper validates it and fills in `.env`:

```bash
python get_leap_token.py
```

It confirms the token works, writes `LEAP_API_TOKEN`, and lists venues so you
can pick `LEAP_VENUE_ID`. It also tries to list sellers for `LEAP_SELLER_ID`,
but that currently comes back empty — see **Current status** below.

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
| `GET /api/airtable/fields` | Writable Schedule columns + their options, read from the live base schema (cached) |
| `POST /shows` | Append a new show to `shows.json` |
| `POST /create` | Create the Leap event + price level, return ticket URL |

## Airtable fields

The form can write every column on the Schedule table that Airtable allows a
client to write:

- The numbered cards fill in the ten derived from the show, date and venue
  (`Show Name`, `Date for Calendar`, `Showtime`, `Stage`, `Ticket Price`, …).
- **⑦ More Airtable Fields** renders an input for every other writable column.
  That list is not hardcoded — `/api/airtable/fields` reads the live base schema,
  so a column added in Airtable appears here after a restart. Everything in the
  panel is optional: blank inputs are not sent, so untouched columns are left
  alone rather than blanked out.
- Linked-record columns (House Manager, Performers/Cast, the producer fields)
  become filterable multi-selects populated from the linked table.

Two groups are deliberately absent. The ~30 computed columns (formula, rollup,
lookup) cannot be written by anyone — that's why the promo blurbs and images
come from linked *Producer Uploads* records instead of this form. And
`Added to Wordpress` belongs to ghostlight, which sets it after publishing and
skips any record where it is already true; writing it here would hide the event
from the sync forever.

Outgoing records are filtered against the schema before being sent, because
Airtable rejects an entire record with a 422 if even one field name is unknown.
Anything dropped is listed in the result panel, which also shows every field
that was saved.

**Known drift:** the form still tries to write `Time of Show for Calendar`,
which no longer exists on the table. The filter drops it and says so, so creates
succeed — but either recreate that column in Airtable or delete the line in
`templates/index.html` to settle it.

## Editing shows

Use the **Add Show to Catalog** tab, or edit `shows.json` by hand. Each show
has: `name`, `slug`, `description`, `short_description`, `default_price`,
`default_capacity`, `default_duration_minutes`, `tags`, and optionally
`image_url`.

## After creation

The Airtable Schedule record is created with the ticket URL written into
`Showclix Ticket Link`, and whatever **Status** is chosen in the form.

**Status defaults to `Draft`, and a Draft record does not sync to WordPress.**
That's deliberate — Draft is a review gate. Ghostlight reads this same table
through the Airtable view `Wordpress Export- All Today Forward`, which excludes
Draft, so the event stays off the website until someone sets `Status` to
`Confirmed`. The next ghostlight run then creates the WordPress event.

The form's ⑥ Airtable Status dropdown can set it to `Confirmed` (or any other
value in the Airtable single-select) at creation time if the event is already
reviewed and should publish straight away.

If an event never shows up on the website, check its Status first.

## WordPress auth (future)

The app is currently standalone with no authentication. The plan is to
eventually put it behind WordPress auth; nothing in the app assumes it yet.
# ACT_leepair
# ACT_leepair
# ACT_leepair
