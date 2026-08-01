#!/usr/bin/env python3
"""
Set up Leap (ShowClix) API credentials in .env.

The old self-service endpoint (POST /api/registration) was removed when
ShowClix became Leap. The current mechanism is an "Integration Token"
generated in the Leap Admin UI:

    1. Log in at https://admin.leapevents.com
    2. Go to  https://admin.leapevents.com/user
    3. Generate an Integration Token and copy it

Then run this script and paste the token. It validates the token, writes
LEAP_API_TOKEN to .env, and helps fill in LEAP_SELLER_ID / LEAP_VENUE_ID.

Run it in a terminal:
    python get_leap_token.py
"""
import sys
from pathlib import Path

import requests

# The app talks to the V2 API here (confirmed working in the original app);
# the legacy host is kept as a fallback for the token check.
API_BASES = [
    "https://www.showclix.com/api",
    "https://api.leapevents.com",
]
ENV_FILE = Path(__file__).resolve().parent / ".env"


def set_env_value(key: str, value: str) -> None:
    """Update or append KEY=value in .env, preserving everything else."""
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    for i, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == key:
            lines[i] = f"{key}={value}"
            break
    else:
        lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def flatten(raw) -> list:
    """Normalize a JSON:API or legacy collection response to [(id, name)]."""
    items = raw.get("data", raw) if isinstance(raw, dict) else raw
    out = []
    if isinstance(items, dict):  # legacy: dict keyed by id
        items = [dict(v, id=k) for k, v in items.items() if isinstance(v, dict)]
    for item in items or []:
        if isinstance(item, dict):
            name = (item.get("attributes") or {}).get("name") or item.get("name") or "?"
            out.append((str(item.get("id", "?")), name))
    return out


def get_collection(base: str, resource: str, token: str):
    resp = requests.get(
        f"{base}/{resource}",
        headers={"X-API-Token": token, "Accept": "application/vnd.api+json"},
        timeout=30,
    )
    resp.raise_for_status()
    return flatten(resp.json())


def main() -> None:
    print("Leap / ShowClix API credential setup")
    print("────────────────────────────────────")
    print("1. Log in at https://admin.leapevents.com")
    print("2. Open   https://admin.leapevents.com/user")
    print("3. Generate an Integration Token and copy it\n")
    while True:
        token = input("Paste the Integration Token (or 'q' to quit): ").strip()
        if token.lower() == "q":
            print("Aborted.")
            sys.exit(1)
        if len(token) >= 16:
            break
        print("\nThat doesn't look like a token — a token is a long string of")
        print("letters and numbers, e.g. 3e9fa1980a283fe902c83a8929d0ae91.")
        print("Generate one on https://admin.leapevents.com/user and paste the")
        print("whole string here.\n")

    # ── Validate the token by listing venues ──────────────────────────────
    base = None
    venues = []
    for candidate in API_BASES:
        print(f"Checking token against {candidate} …", end=" ")
        try:
            venues = get_collection(candidate, "venues", token)
            print("OK")
            base = candidate
            break
        except requests.HTTPError as e:
            print(f"{e.response.status_code}")
        except Exception as e:
            print(f"error: {e}")

    if base is None:
        print("\nThe token was rejected by every known API host.")
        print("Double-check the token, or ask Leap support which API host your")
        print("Integration Token is valid for.")
        sys.exit(1)

    set_env_value("LEAP_API_TOKEN", token)
    print(f"\n✓ Token works — wrote LEAP_API_TOKEN to {ENV_FILE}")
    if base != API_BASES[0]:
        print(f"  NOTE: token only worked against {base}.")
        print(f"  app.py currently uses {API_BASES[0]} — update LEAP_API_BASE there if needed.")

    # ── Seller ID ─────────────────────────────────────────────────────────
    try:
        sellers = get_collection(base, "sellers", token)
    except Exception as e:
        sellers = []
        print(f"\nCould not list sellers ({e}) — set LEAP_SELLER_ID manually.")
    if len(sellers) == 1:
        set_env_value("LEAP_SELLER_ID", sellers[0][0])
        print(f"✓ Wrote LEAP_SELLER_ID={sellers[0][0]} ({sellers[0][1]})")
    elif sellers:
        print("\nYour sellers:")
        for i, (sid, name) in enumerate(sellers, 1):
            print(f"  [{i}] {name}  (id {sid})")
        choice = input("Number of the seller for .env (Enter to skip): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(sellers):
            sid, name = sellers[int(choice) - 1]
            set_env_value("LEAP_SELLER_ID", sid)
            print(f"✓ Wrote LEAP_SELLER_ID={sid} ({name})")

    # ── Venue ID ──────────────────────────────────────────────────────────
    if not venues:
        print("\nNo venues returned — set LEAP_VENUE_ID manually.")
    else:
        print("\nYour venues:")
        for i, (vid, name) in enumerate(venues, 1):
            print(f"  [{i}] {name}  (id {vid})")
        choice = input("\nNumber of the default venue for .env (Enter to skip): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(venues):
            vid, name = venues[int(choice) - 1]
            set_env_value("LEAP_VENUE_ID", vid)
            print(f"✓ Wrote LEAP_VENUE_ID={vid} ({name})")

    print("\nDone. Restart app.py to pick up the new values.")


if __name__ == "__main__":
    main()
