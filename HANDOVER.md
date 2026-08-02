# Handover

Everything needed to pick this project up on another machine. Written
2026-08-02.

Repo: <https://github.com/pyprk/ACT_leepair> · branch `main`

---

## What this is

A Flask form that creates a Leap (ShowClix V2) ticketing event **and** an
Airtable *Schedule* record in one submit, so shows stop being entered twice by
hand. `README.md` covers how it works; this file covers where things stand and
what is still open.

---

## Getting it running

```bash
git clone git@github.com:pyprk/ACT_leepair.git
cd ACT_leepair
pip install -r requirements.txt
cp .env.example .env      # then fill it in — see below
python app.py             # http://localhost:5050
```

### `.env` — not in the repo, and it is the only real blocker

`.env` is gitignored, so a fresh clone has nothing. You need all of these:

| Variable | Where it comes from |
|---|---|
| `LEAP_API_TOKEN` | Leap issues it directly — **not self-service**. Ask our Leap contact. |
| `LEAP_SELLER_ID` | `18862` (Arcade Comedy Theater) — stable, just set it |
| `LEAP_VENUE_ID` | `47341` is a fine default; it's only a fallback since the form picks a venue |
| `AT_API_KEY` / `AT_BASE_ID` / `AT_TABLE` | Airtable PAT + the Schedule table. Copy from the working `.env` on the tower box |
| `WP_URL` / `WP_USER` / `WP_APP_PW` | WordPress application password — see *Description store* below |

> The Leap token that was used to explore the API during this work is being
> rotated, so it will not work. Get a fresh one.

### Finding the seller ID again, if it's ever lost

`GET /sellers` returns `{"data":[]}` for our token even though the same token
reads `/venues` fine — the seller is not discoverable the obvious way. It is
reachable through any venue's relationship:

```bash
curl -H "X-API-Token: $LEAP_API_TOKEN" -H "Accept: application/vnd.api+json" \
  https://www.showclix.com/api/venues/47341/sellers
```

`get_leap_token.py` still can't fill it in automatically for the same reason.

---

## State of play

### Working

- **Leap event creation** — name, description, capacity, start/end,
  `age_minimum`, seller/venue/series, plus a General Admission price level.
- **Airtable record creation** — all 38 writable *Schedule* columns, each
  optional. The form renders itself from the live base schema via
  `/api/airtable/fields`, so a column added in Airtable appears after a
  restart.
- **Show catalogue editing** — the second tab's *Edit or Create* picker loads
  an existing show for editing (`PUT /shows/<slug>`), including renames.

### Half-done — the description store

This is the main open thread. A show's evergreen `description` and `image_url`
used to be stored **twice**: in `shows.json` here, and in the Ghostlight
plugin's `descriptions/<slug>.json` on the arcade server. They drifted.

The Python side is finished and pushed: the app now reads and writes the
plugin's store, and `shows.json` is meant to keep only what ghostlight has no
use for (short_description, price, capacity, duration, tags).

**Deployed to dev, not to production.** The route is live on
**wp.deadframe.xyz** (the theme dev environment, files at
`/mnt/tower/appdata/wordpress`) and verified end to end there — see below. It
is **not** on the production site yet.

The dev and production plugin copies were reconciled on 2026-08-02. The
deploy package at `projects/work/arcade/ghostlight-wp-plugin/` was two months
stale — dev had moved on to v1.2.1 with an Email Template tab, rewritten admin
CSS/JS, a run-sorting fix in `helpers.php`, and soft-delete for descriptions.
The package now matches dev, with two deliberate exceptions:

- **`includes/dev-bridge.php` is excluded.** It is a dev-only HTTP file-push
  bridge with a hardcoded token; its own header says never deploy it. It is
  loaded only when `wp_get_environment_type() === 'local'`, and
  `template-editor.php` guards on `file_exists`, so its absence is harmless.
- **`GL_DESC_DIR` is now overridable** rather than hardcoded. Dev had moved the
  store to `wp-content/uploads/arcade-descriptions`; production keeps it beside
  `ghostlight.py`. Shipping dev's value to production would have pointed the
  plugin at a directory the sync script never reads, silently killing the
  website's description fallback. Production must define it in `wp-config.php`
  — see step 0 of `ghostlight-deploy/DEPLOY.md`.

Two things still outstanding on that front. The **dev copy of `ghostlight.php`
has not received the `GL_DESC_DIR` guard**: the appdata CIFS share started
refusing writes to that directory partway through (the mount uses `forceuid`,
so `ls` shows it writable while the server denies it — `dev-bridge.php` exists
because of this exact split). Dev works fine as-is since the guard's default is
dev's current value, but the two files differ by that one block until it can be
written. And the **package is still not under version control anywhere**, which
now matters more than it did, because it is the reconciled source of truth.

**`migrate_descriptions.py` still hasn't been run**, so `shows.json` keeps the
old copies (21 of 22).

This is safe to sit in: `keep_locally()` in `app.py` puts the shared fields
back into `shows.json` whenever the store won't accept a write, so nothing is
lost in the meantime. Once the store is reachable, the local duplicates
disappear on their own as shows are saved.

**One show needs a human decision before migrating.** `got-rights` has two
genuinely different write-ups (3% similar) — everything else is identical or
differs only by smart quotes. There is also a stray
`.got-rights.json.swp` vim swap file on the server from May 24, so one of the
two may be an abandoned half-edit. Whoever wrote it will know which to keep.

```bash
python migrate_descriptions.py            # report, changes nothing
python migrate_descriptions.py --apply    # refuses while conflicts remain
```

---

## Things worth knowing before changing anything

**Draft is a deliberate review gate.** The form writes `Status = Draft`, and
ghostlight's export view excludes Draft, so a new event does *not* reach the
website until someone sets it to `Confirmed` in Airtable. Verified against the
live base: of 9 future-dated Draft records, 0 appear in the view. The ⑦ Status
dropdown can set `Confirmed` at creation time if it's already been reviewed.

**Never write `Added to Wordpress`.** Ghostlight owns it — it skips any record
where it's already true, and sets it itself after publishing. Writing it from
here would hide the event from the sync permanently. The field spec endpoint
excludes it deliberately.

**Airtable rejects a whole record over one unknown field name.** The form
filters outgoing records against the live schema for exactly this reason, and
reports anything dropped in the result panel.

**`Time of Show for Calendar` is a phantom.** The form still tries to write it
and no such column exists, so the filter drops it every time. Either recreate
the column in Airtable or delete the line in `templates/index.html`. Before the
filter existed this was failing every single Airtable write.

**Promo blurbs and images can't be written from here.** They're `multipleLookupValues`
on Airtable, computed from linked *Producer Uploads* records — read-only for
every client, which is why the form never touches them.

---

## Open items

- [x] ~~Deploy the route to dev~~ — live and verified on wp.deadframe.xyz
- [ ] Deploy the same two changes to **production** once dev has had some use
- [x] ~~Reconcile the dev and package plugin copies~~ — done 2026-08-02
- [ ] Add the `GL_DESC_DIR` guard block to the **dev** `ghostlight.php` once
      the appdata share allows writes again (cosmetic — the default matches)
- [ ] Put `ghostlight-wp-plugin/` under version control; it is now the
      reconciled source of truth and lives on an unbacked share
- [ ] When deploying to production, add the `GL_DESC_DIR` define to
      `wp-config.php` FIRST — see step 0 of `ghostlight-deploy/DEPLOY.md`
- [ ] `.env` currently points at wp.deadframe.xyz with the credentials from
      `/mnt/tower/projects/.env`; point it at production when that's deployed
- [ ] Settle `got-rights`, then run `migrate_descriptions.py --apply`
- [ ] Get a non-rotating `LEAP_API_TOKEN`
- [ ] **Venue cleanup** — 9 of 15 venues have no future events. `49108
      "UPSTAIRS"` is clearly superseded by `86691 "Upstairs Stage"` (it carried
      1812 events then stopped the day the other started). Both *Downstairs*
      entries (`47341`, `82097`) are live with events into Jan 2027 — that one
      needs a human to pick. Full table in `README.md`.
- [ ] 4 slugs have website copy but no catalogue entry, so they can't be booked
      here: `alter-egos`, `the-mon`,
      `under-the-radar-independent-pittsburgh-improv`,
      `unique-an-improv-show-about-disabilities-and-mental-health`
- [ ] The Airtable PAT is served to every browser that loads the page, since
      the frontend writes to Airtable directly. Fine on a trusted LAN; proxy it
      through `app.py` before this is ever exposed publicly.
- [ ] No delete route for shows — remove entries from `shows.json` by hand

---

## Notes on the dev environment

The tower box this was built on had **no `pip` and no `php`**, which shapes how
things were verified:

- Flask was installed by borrowing the pip in
  `/mnt/tower/projects/venv/lib/python3.11/site-packages` with the system
  Python 3.12, installed to a scratch directory. `python3 -m venv` fails there
  (no `ensurepip`).
- `php-cli` was installed with apt during this work, so the PHP is now linted
  (`php -l`, all 14 plugin files) and executed against a stubbed WordPress —
  the harness lives in the scratch dir, not the repo; it stubs `add_action`,
  `register_rest_route`, `sanitize_title`, `gl_desc_save` and friends. What
  that cannot cover is real WordPress: capability resolution, application
  password auth, and route collisions with other plugins.
- The project lives on a **CIFS share**. Editors that write via
  temp-file-then-rename can fail there, leaving a file unlinked but still
  named — deletes and renames then return `ENOENT` until whatever holds the
  handle closes. If a file starts behaving impossibly, check `lsof` for a
  process holding it and look for `.fuse_hidden*` orphans.
