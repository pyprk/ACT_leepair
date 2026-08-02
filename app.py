#!/usr/bin/env python3
"""
Arcade Event Creator

Flask app: select a show → auto-fill fields → create a Leap (ShowClix V2)
event. The frontend posts the Airtable "Schedule" record directly from the
browser after this backend returns the ticket URL, so this app only talks
to Leap.

Leap V2 API notes (from Core API docs):
- POST /events → creates the event shell (no price here)
- POST /price_levels → creates a ticket tier linked to the event
- Dates: ISO 8601 format
- Price: stored as integer cents (e.g. $15.00 → 1500)
- Ticket URL is built from listing_settings.slug or listing_settings.uri
  in the response
"""
import json
import os
import re

import requests
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory
from dotenv import load_dotenv

# ── Load environment ──────────────────────────────────────────────────────────
CURRENT_DIR = Path(__file__).resolve().parent
for _env_path in [CURRENT_DIR / ".env", CURRENT_DIR.parent / ".env"]:
    if not os.getenv("LEAP_API_TOKEN"):
        load_dotenv(dotenv_path=_env_path)

# Leap / ShowClix V2
LEAP_API_TOKEN = os.getenv("LEAP_API_TOKEN")
LEAP_SELLER_ID = os.getenv("LEAP_SELLER_ID")
LEAP_VENUE_ID = os.getenv("LEAP_VENUE_ID")
LEAP_API_BASE = "https://www.showclix.com/api"  # V2 base — confirmed working

# Airtable — read here and handed to the template so nothing is baked into
# templates/index.html (it would end up in git).
AT_API_KEY = os.getenv("AT_API_KEY", "")
AT_BASE_ID = os.getenv("AT_BASE_ID", "")
AT_TABLE = os.getenv("AT_TABLE", "")

app = Flask(__name__)

# ── Load show catalog ─────────────────────────────────────────────────────────
SHOWS_FILE = CURRENT_DIR / "shows.json"


def load_catalog() -> dict:
    with open(SHOWS_FILE, "r", encoding="utf-8") as f:
        return {s["name"]: s for s in json.load(f)["shows"]}


SHOW_CATALOG = load_catalog()


# ── Helpers ───────────────────────────────────────────────────────────────────
def leap_headers():
    return {
        "X-API-Token": LEAP_API_TOKEN,
        "Content-Type": "application/vnd.api+json",
        "Accept": "application/vnd.api+json",
    }


def dollars_to_cents(amount: float) -> int:
    """Leap stores prices as integer cents."""
    return int(round(amount * 100))


def fmt_time(dt: datetime) -> str:
    # strftime "%-I" is Linux-only; strip the leading zero for portability
    return dt.strftime("%I:%M %p").lstrip("0")


def fmt_long_date(dt: datetime) -> str:
    return f"{dt.strftime('%A, %B')} {dt.day}, {dt.year}"


def leap_age_minimum(choice: str) -> str:
    """
    Map the form's Age Restriction wording onto Leap's `age_minimum`.

    Leap stores this as free text and the existing catalogue is inconsistent
    ('16+', '18', '18+', '0', 'All Ages'), so normalise to the most common
    'N+' form. Returns '' for anything we can't map, which leaves the
    attribute off the payload rather than writing a guess.
    """
    choice = (choice or "").strip()
    if not choice or choice.startswith("Other"):
        return ""
    if choice == "All Ages":
        return "All Ages"
    m = re.match(r"^(\d+)\s+and over$", choice, re.I)
    return f"{m.group(1)}+" if m else ""


def create_leap_event(show: dict, start_dt: datetime, end_dt: datetime,
                      venue_id: str = "", series_id: str = "",
                      age_minimum: str = "") -> dict:
    """
    Step 1: POST /events — creates the event shell.
    Returns the full API response dict.
    Status 'active' makes it live; use 'incomplete' for draft.
    """
    payload = {
        "data": {
            "type": "events",
            "attributes": {
                "name": show["name"],
                "description": show["description"],
                "inventory": show["default_capacity"],
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "status": "active",
                "settings": {
                    "private": False,
                },
            },
            "relationships": {
                "seller": {
                    "data": {"type": "sellers", "id": str(LEAP_SELLER_ID)}
                },
                "venue": {
                    "data": {"type": "venues", "id": str(venue_id or LEAP_VENUE_ID)}
                },
            },
        }
    }
    if age_minimum:
        payload["data"]["attributes"]["age_minimum"] = age_minimum
    if series_id:
        payload["data"]["relationships"]["series"] = {
            "data": {"type": "series", "id": str(series_id)}
        }
    resp = requests.post(
        f"{LEAP_API_BASE}/events",
        headers=leap_headers(),
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def create_leap_price_level(event_id: str, show: dict) -> dict:
    """
    Step 2: POST /price_levels — attaches a ticket tier to the event.
    Price is integer cents. Linked to the event via relationship.
    """
    price_cents = dollars_to_cents(show["default_price"])
    payload = {
        "data": {
            "type": "price_levels",
            "attributes": {
                "name": "General Admission",
                "inventory": show["default_capacity"],
                "price": {
                    "amount": price_cents,
                    "currency": "USD",
                    "symbol": "$",
                },
            },
            "relationships": {
                "event": {
                    "data": {"type": "events", "id": str(event_id)}
                }
            },
        }
    }
    resp = requests.post(
        f"{LEAP_API_BASE}/price_levels",
        headers=leap_headers(),
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def extract_ticket_url(event_response: dict) -> str:
    """
    Pulls the public ticket URL from the event creation response.
    Leap V2 returns listing_settings.uri or listing_settings.slug.
    """
    attrs = event_response.get("data", {}).get("attributes", {})
    listing = attrs.get("listing_settings", {})
    # Prefer the full URI if returned
    uri = listing.get("uri") or listing.get("primary_uri")
    if uri:
        return uri if uri.startswith("http") else f"https://www.showclix.com{uri}"
    # Fall back to slug
    slug = listing.get("slug")
    if slug:
        return f"https://www.showclix.com/event/{slug}"
    # Last resort: numeric event ID
    event_id = event_response.get("data", {}).get("id")
    return f"https://www.showclix.com/event/{event_id}" if event_id else ""


def leap_list(resource: str) -> list:
    """GET a Leap collection and flatten the JSON:API response to id/name."""
    resp = requests.get(
        f"{LEAP_API_BASE}/{resource}",
        headers=leap_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    items = resp.json().get("data", [])
    return [
        {"id": item.get("id"), "name": item.get("attributes", {}).get("name", "")}
        for item in items
    ]


# ── Airtable schema ───────────────────────────────────────────────────────────
AT_API_BASE = "https://api.airtable.com/v0"

# Types Airtable computes. Read-only no matter who is asking.
AT_COMPUTED_TYPES = {
    "formula", "rollup", "count", "autoNumber", "createdTime",
    "lastModifiedTime", "createdBy", "lastModifiedBy", "button",
    "lookup", "multipleLookupValues", "externalSyncSource",
}

# Columns the main form already derives from the show / date / venue inputs.
AT_FIELDS_HANDLED = {
    "Show Name", "Date for Calendar", "Showtime", "Date for Name", "Status",
    "Day of the Week", "Year of Show", "Ticket Price", "Showclix Ticket Link",
    "Stage",
}

# Ghostlight sets this itself after publishing to WordPress, and skips any
# record where it is already true. Writing it here would hide the event from
# the sync permanently.
AT_FIELDS_OFF_LIMITS = {"Added to Wordpress"}

_AT_FIELDS_CACHE = {}


def airtable_get(path, params=None):
    resp = requests.get(
        f"{AT_API_BASE}/{path}",
        headers={"Authorization": f"Bearer {AT_API_KEY}"},
        params=params or {},
        timeout=40,
    )
    resp.raise_for_status()
    return resp.json()


def airtable_all_records(table_id: str, primary: str) -> list:
    """Every record in a table as {id, name}, following pagination."""
    out, offset = [], None
    while True:
        params = {"pageSize": 100, "fields[]": primary}
        if offset:
            params["offset"] = offset
        data = airtable_get(f"{AT_BASE_ID}/{table_id}", params)
        for rec in data.get("records", []):
            label = rec.get("fields", {}).get(primary)
            out.append({
                "id": rec["id"],
                "name": str(label) if label not in (None, "") else "(untitled)",
            })
        offset = data.get("offset")
        if not offset:
            return out


def build_airtable_field_spec():
    """
    Returns (spec, writable):
      spec     — columns the form should render inputs for
      writable — every column name that can be written at all, so the frontend
                 can drop anything the table no longer has. Airtable rejects
                 the whole record with a 422 if one field name is unknown, so a
                 renamed or deleted column would otherwise break every submit.
    """
    meta = airtable_get(f"meta/bases/{AT_BASE_ID}/tables")
    tables = {t["id"]: t for t in meta.get("tables", [])}
    schedule = tables.get(AT_TABLE)
    if not schedule:
        raise RuntimeError(f"table {AT_TABLE} not visible to this API key")

    spec, writable = [], []
    for f in schedule.get("fields", []):
        name, ftype = f.get("name"), f.get("type")
        if ftype in AT_COMPUTED_TYPES:
            continue
        writable.append(name)
        if name in AT_FIELDS_HANDLED or name in AT_FIELDS_OFF_LIMITS:
            continue

        entry = {"name": name, "type": ftype}
        opts = f.get("options") or {}

        if ftype in ("singleSelect", "multipleSelects"):
            entry["choices"] = [c["name"] for c in opts.get("choices", []) if c.get("name")]
        elif ftype == "multipleRecordLinks":
            linked = tables.get(opts.get("linkedTableId"))
            if not linked:
                continue  # linked table not readable with this key
            primary = next(
                (x["name"] for x in linked.get("fields", [])
                 if x.get("id") == linked.get("primaryFieldId")),
                None,
            )
            if not primary:
                continue
            entry["linkedTable"] = linked.get("name")
            entry["records"] = airtable_all_records(opts["linkedTableId"], primary)

        spec.append(entry)
    return spec, writable


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    shows = list(SHOW_CATALOG.values())
    return render_template(
        "index.html",
        shows=shows,
        at_token=AT_API_KEY,
        at_base_id=AT_BASE_ID,
        at_table=AT_TABLE,
    )


@app.route("/shows.json")
def shows_json():
    return send_from_directory(CURRENT_DIR, "shows.json")


@app.route("/show-data/<show_name>")
def show_data(show_name: str):
    show = SHOW_CATALOG.get(show_name)
    if not show:
        return jsonify({"error": "Show not found"}), 404
    return jsonify(show)


@app.route("/api/airtable/fields")
def api_airtable_fields():
    """
    Describe every Airtable column the form can write, so the frontend can
    render inputs for them instead of hardcoding a list that drifts from the
    base. Computed columns (formula/rollup/lookup/…) are skipped because no
    client can write them; so is the field ghostlight owns.

    Cached in memory — building it costs one metadata call plus a scan of each
    linked table.
    """
    if not (AT_API_KEY and AT_BASE_ID and AT_TABLE):
        return jsonify({"fields": [], "error": "Airtable env vars not set"}), 200
    if _AT_FIELDS_CACHE.get("data") is not None:
        return jsonify(_AT_FIELDS_CACHE["data"])
    try:
        spec, writable = build_airtable_field_spec()
        payload = {"fields": spec, "writable": writable}
        _AT_FIELDS_CACHE["data"] = payload
        return jsonify(payload)
    except Exception as e:
        return jsonify({"fields": [], "writable": [], "error": str(e)}), 200


@app.route("/api/venues")
def api_venues():
    if not LEAP_API_TOKEN:
        return jsonify({"venues": [], "error": "LEAP_API_TOKEN not set"}), 200
    try:
        return jsonify({"venues": leap_list("venues")})
    except Exception as e:
        return jsonify({"venues": [], "error": str(e)}), 200


@app.route("/api/series")
def api_series():
    if not LEAP_API_TOKEN:
        return jsonify({"series": [], "error": "LEAP_API_TOKEN not set"}), 200
    try:
        return jsonify({"series": leap_list("series")})
    except Exception as e:
        return jsonify({"series": [], "error": str(e)}), 200


@app.route("/shows", methods=["POST"])
def add_show():
    """Append a new show to shows.json and refresh the in-memory catalog."""
    new_show = request.get_json() or {}
    errors = []
    if not new_show.get("name"):
        errors.append("Show name is required.")
    if not new_show.get("slug"):
        errors.append("Slug is required.")
    if not new_show.get("short_description"):
        errors.append("Short description is required.")
    if errors:
        return jsonify({"error": " ".join(errors)}), 400

    with open(SHOWS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if any(s["slug"] == new_show["slug"] for s in data["shows"]):
        return jsonify({"error": f"Slug '{new_show['slug']}' already exists."}), 409

    data["shows"].append(new_show)
    with open(SHOWS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    SHOW_CATALOG[new_show["name"]] = new_show
    return jsonify({"success": True, "show": new_show}), 201


@app.route("/create", methods=["POST"])
def create_event():
    data = request.get_json()
    show_name = (data.get("show_name") or "").strip()
    event_date = (data.get("event_date") or "").strip()
    event_time = (data.get("event_time") or "").strip()
    errors = []
    if not show_name: errors.append("Show name is required.")
    if not event_date: errors.append("Event date is required.")
    if not event_time: errors.append("Showtime is required.")
    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    # Resolve show + apply overrides
    show = dict(SHOW_CATALOG.get(show_name, {}))
    if not show:
        return jsonify({"success": False, "errors": [f"Unknown show: {show_name}"]}), 400
    if data.get("custom_title"):
        show["name"] = data["custom_title"].strip()
    if data.get("custom_description"):
        show["description"] = data["custom_description"].strip()
    if data.get("override_price"):
        try:
            show["default_price"] = float(data["override_price"])
        except ValueError:
            errors.append("Invalid price.")
    if data.get("override_capacity"):
        try:
            show["default_capacity"] = int(data["override_capacity"])
        except ValueError:
            errors.append("Invalid capacity.")
    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    # Parse datetime
    try:
        start_dt = datetime.strptime(f"{event_date} {event_time}", "%Y-%m-%d %H:%M")
    except ValueError:
        return jsonify({"success": False, "errors": ["Invalid date or time."]}), 400
    end_dt = start_dt + timedelta(minutes=show.get("default_duration_minutes", 90))

    # ── Leap event + price level ──────────────────────────────────────────────
    # (The frontend creates the Airtable Schedule record itself, using the
    #  ticket_url returned here.)
    leap_event_id = None
    ticket_url = ""
    leap_error = None
    if not LEAP_API_TOKEN:
        leap_error = "LEAP_API_TOKEN not set — Leap event skipped."
    else:
        try:
            event_resp = create_leap_event(
                show, start_dt, end_dt,
                venue_id=data.get("event_venue_id") or "",
                series_id=data.get("series_id") or "",
                age_minimum=leap_age_minimum(data.get("age_restriction")),
            )
            leap_event_id = event_resp.get("data", {}).get("id")
            ticket_url = extract_ticket_url(event_resp)
            # attach price level
            create_leap_price_level(leap_event_id, show)
        except requests.HTTPError as e:
            leap_error = f"Leap API {e.response.status_code}: {e.response.text[:300]}"
        except Exception as e:
            leap_error = f"Leap error: {e}"

    return jsonify({
        "success": leap_error is None,
        "show_name": show["name"],
        "event_date": fmt_long_date(start_dt),
        "event_time": fmt_time(start_dt),
        "ticket_url": ticket_url,
        "leap": {
            "success": leap_error is None,
            "event_id": leap_event_id,
            "error": leap_error,
        },
    })


if __name__ == "__main__":
    port = int(os.getenv("CREATOR_PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=False)
