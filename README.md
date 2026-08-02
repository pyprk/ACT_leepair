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

The credentials that were blocking event creation are resolved. `.env` needs
`LEAP_SELLER_ID=18862` (Arcade Comedy Theater) and a default `LEAP_VENUE_ID`
(47341 is a reasonable pick — see Venues below).

Finding the seller ID was awkward enough to write down: `GET /sellers` returns
`{"data":[]}` for our token even though the same token reads `/venues` fine, so
the seller is not discoverable the obvious way. It *is* reachable through any
venue's relationship:

```bash
curl -H "X-API-Token: $LEAP_API_TOKEN" -H "Accept: application/vnd.api+json" \
  https://www.showclix.com/api/venues/47341/sellers
```

`get_leap_token.py` still can't fill `LEAP_SELLER_ID` in automatically for the
same reason — set it by hand.

**Known gotchas**

- `GET /series` returns 404. That endpoint doesn't exist on this API host;
  `/api/series` catches it and returns an empty list, so the Series picker
  simply stays empty.
- The form writes `Time of Show for Calendar`, which is not a column on the
  Schedule table — see **Airtable fields**.

### Venues

Nine of the fifteen venues on the account have **no future events** and are
cluttering the picker. Worth confirming with whoever books shows before
retiring them in Leap:

| ID | events | future | last used | name |
|---|---|---|---|---|
| 75945 | 1784 | 153 | 2026-12-31 | Concessions/Merch |
| 86691 | 110 | 94 | 2026-12-26 | Arcade Comedy Theater: Upstairs Stage |
| 47341 | 1269 | 26 | 2027-01-02 | Arcade Comedy Theater: Downstairs |
| 82097 | 572 | 11 | 2027-01-02 | Arcade Comedy Theater: Downstairs |
| 47874 | 1254 | 5 | 2026-11-08 | Arcade Comedy Theater: Downstairs Stage |
| 49109 | 56 | 2 | 2026-09-14 | Arcade Comedy Theater Lounge |
| 49108 | 1812 | 0 | 2026-07-10 | Arcade Comedy Theater: UPSTAIRS |
| 19545 | 1270 | 0 | 2019-11-21 | Highmark Caring Place |
| 47342 | 942 | 0 | 2022-12-10 | DELETE ME |
| 67459 | 293 | 0 | 2021-11-14 | Trust Oasis |
| 21431 | 74 | 0 | 2019-06-06 | The 707 Academy |
| 27619 | 56 | 0 | 2024-02-06 | 820 Liberty Avenue |
| 69473 | 4 | 0 | 2021-08-14 | Allegheny Overlook Stage |
| 74580 | 1 | 0 | 2022-09-10 | Backyard |
| 79133 | 1 | 0 | 2023-11-03 | Liberty Magic |

Two things to settle:

- **49108 "UPSTAIRS" looks superseded.** It carried 1812 events but stopped on
  2026-07-10, right as 86691 "Upstairs Stage" picked up. Almost certainly a
  migration that left the old entry behind.
- **Both "Downstairs" entries are live.** 47341 and 82097 have the same name and
  the same 85 capacity, and both have events into January 2027. That's a real
  split, not a dead twin — someone is picking each. Worth merging on one.

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

Each show has: `name`, `slug`, `description`, `short_description`,
`default_price`, `default_capacity`, `default_duration_minutes`, `tags`, and
optionally `image_url`.

**The Add Show tab only adds.** `POST /shows` appends to `shows.json` and
rejects a slug that already exists with a 409 — there is no edit or delete
route, and no UI for changing a show that is already in the catalogue. To fix a
description, price or image on an existing show you have to edit `shows.json`
by hand and restart. That is the most obvious missing feature in this tool.

## What gets stored in Leap

`POST /create` builds the event from the catalogue entry plus the form:

| Leap attribute | Source |
|---|---|
| `name` | Show name, or the Title Override |
| `description` | Catalogue description, or the Description Override |
| `inventory` | Catalogue capacity, or the Capacity Override |
| `start` / `end` | Date + showtime, plus the catalogue duration |
| `age_minimum` | The Age Restriction dropdown |
| `status` | Always `active` |
| seller / venue / series | `LEAP_SELLER_ID`, the venue picker, the series picker |

A single "General Admission" price level is then attached at the catalogue
price (or the Price Override).

Leap stores `age_minimum` as free text and the existing catalogue is
inconsistent about it — `16+`, `18`, `18+`, `0`, `All Ages` all appear — so
`leap_age_minimum()` normalises the form's wording to the most common `N+`
form. "Other (Please Specify)" maps to nothing and leaves the attribute off the
payload rather than writing a guess.

Leap accepts plenty this form doesn't set — `category`, `doors_open_time`,
`ticket_note`, `url`, `sales_open` / `sales_close`, `image`, `short_name`.
Worth a look if any of those should stop being set by hand in the Leap admin.

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
