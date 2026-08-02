#!/usr/bin/env python3
"""
Move show descriptions out of shows.json and into the shared store.

`description` and `image_url` used to live in both shows.json (for the Leap
ticket page) and the Ghostlight plugin's description store (for the website).
They drifted. The app now reads and writes only the shared store, so these two
fields need to come out of shows.json — but not before anything missing
upstream has been pushed there, and not before a human has settled any show
where the two copies disagree.

    python migrate_descriptions.py            # report only, changes nothing
    python migrate_descriptions.py --apply    # push + strip, refuses on conflicts
    python migrate_descriptions.py --apply --prefer-local
                                              # ...treating shows.json as correct

Needs WP_URL, WP_USER and WP_APP_PW in .env — the same application password
the app uses.
"""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
import os

CURRENT_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=CURRENT_DIR / ".env")

SHOWS_FILE = CURRENT_DIR / "shows.json"
WP_URL = os.getenv("WP_URL", "https://www.arcadecomedytheater.com").rstrip("/")
WP_USER = os.getenv("WP_USER", "")
WP_APP_PW = os.getenv("WP_APP_PW", "")
ENDPOINT = "/wp-json/ghostlight/v1/descriptions"

SIMILAR_ENOUGH = 0.95  # below this, a human picks


def norm(text: str) -> str:
    """Compare on meaning, not typography — smart quotes and dashes differ freely."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'),
                 ("”", '"'), ("–", "-"), ("—", "-"), ("\xa0", " ")):
        text = text.replace(a, b)
    return re.sub(r"\s+", " ", text).strip()


def auth():
    if not (WP_USER and WP_APP_PW):
        sys.exit("WP_USER / WP_APP_PW are not set in .env — cannot reach the description store.")
    return (WP_USER, WP_APP_PW)


def fetch_remote() -> dict:
    resp = requests.get(f"{WP_URL}{ENDPOINT}", auth=auth(), timeout=30)
    resp.raise_for_status()
    return {d["slug"]: d for d in resp.json().get("descriptions", [])}


def push(slug: str, description: str, image_url: str) -> None:
    resp = requests.post(
        f"{WP_URL}{ENDPOINT}/{slug}",
        auth=auth(),
        json={"description": description, "image_url": image_url},
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"{slug}: WordPress {resp.status_code} {resp.text[:200]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="actually push missing entries and strip the fields from shows.json")
    ap.add_argument("--prefer-local", action="store_true",
                    help="on a conflict, overwrite the shared store with the shows.json copy")
    args = ap.parse_args()

    data = json.loads(SHOWS_FILE.read_text(encoding="utf-8"))
    remote = fetch_remote()

    missing, conflicts, agreed = [], [], []
    for show in data["shows"]:
        slug = show.get("slug", "")
        local_desc = show.get("description", "") or ""
        local_img = show.get("image_url", "") or ""
        if not local_desc and not local_img:
            continue
        if slug not in remote:
            missing.append((slug, local_desc, local_img))
            continue
        r = remote[slug]
        same_desc = norm(local_desc) == norm(r.get("description", ""))
        same_img = norm(local_img) == norm(r.get("image_url", ""))
        if same_desc and same_img:
            agreed.append(slug)
        else:
            ratio = difflib.SequenceMatcher(
                None, norm(local_desc), norm(r.get("description", ""))).ratio()
            conflicts.append((slug, ratio, local_desc, r.get("description", ""),
                              local_img, r.get("image_url", "")))

    print(f"shows in catalogue      : {len(data['shows'])}")
    print(f"already identical       : {len(agreed)}")
    print(f"missing from the store  : {len(missing)}")
    print(f"conflicting             : {len(conflicts)}")

    for slug, _, _ in missing:
        print(f"    + would push  {slug}")

    real_conflicts = [c for c in conflicts if c[1] < SIMILAR_ENOUGH]
    for slug, ratio, ld, rd, li, ri in conflicts:
        kind = "CONFLICT" if ratio < SIMILAR_ENOUGH else "cosmetic"
        print(f"    ! {kind} {ratio*100:5.1f}%  {slug}")
        if kind == "CONFLICT":
            print(f"        shows.json  : {norm(ld)[:110]}")
            print(f"        store       : {norm(rd)[:110]}")

    if not args.apply:
        print("\nDry run. Re-run with --apply once the conflicts above are settled.")
        return

    if real_conflicts and not args.prefer_local:
        print(f"\nRefusing to apply: {len(real_conflicts)} show(s) genuinely disagree.")
        print("Fix them in the plugin's Descriptions tab so both sides match, then")
        print("re-run — or pass --prefer-local to overwrite the store from shows.json.")
        sys.exit(1)

    for slug, desc, img in missing:
        push(slug, desc, img)
        print(f"    pushed {slug}")
    if args.prefer_local:
        for slug, _, ld, _, li, _ in conflicts:
            push(slug, ld, li)
            print(f"    overwrote {slug}")

    stripped = 0
    for show in data["shows"]:
        for key in ("description", "image_url"):
            if key in show:
                del show[key]
                stripped += 1
    SHOWS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nRemoved {stripped} field(s) from shows.json. The shared store is now the only copy.")


if __name__ == "__main__":
    main()
