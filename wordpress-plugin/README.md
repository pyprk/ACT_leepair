# WordPress side

The other half of the shared description store. These files belong to the
**Ghostlight** plugin on the arcade WordPress server, not to this Flask app —
they live here because that plugin directory isn't under version control
anywhere, and this repo is where the matching Python side is.

**This copy is the canonical one.** The working copy on the arcade server is
deployed from here.

## What it does

`includes/rest-descriptions.php` exposes the plugin's existing description
store over the REST API so this app can read and write the same
`<slug>.json` files that the plugin's **Descriptions** tab edits and that
`ghostlight.py` reads as its fallback.

Writes go through the plugin's own `gl_desc_save()` and `gl_desc_log()`, so
edits made from the event creator show up in the same change log as edits made
in the admin tab. The Descriptions tab is untouched and keeps working exactly
as before.

| Route | Purpose |
|---|---|
| `GET /wp-json/ghostlight/v1/descriptions` | Every show — full descriptions, not the 140-char admin truncation |
| `GET /wp-json/ghostlight/v1/descriptions/<slug>` | One show (404 if absent) |
| `POST /wp-json/ghostlight/v1/descriptions/<slug>` | Create or update one |

A `POST` merges rather than replaces: `gl_desc_save()` drops any field handed
to it as an empty string, so sending only a `description` would otherwise wipe
the stored poster.

Auth is any user with `edit_posts` — the same capability that gates the admin
panel. Machine clients use a WordPress **application password** over HTTP
Basic.

## Installing

1. Copy `includes/rest-descriptions.php` into the plugin:

   ```
   /home/arcade2018/apps/arcade_wordpress_2018/wp-content/plugins/ghostlight/includes/
   ```

2. Add one line to `ghostlight.php`, after the other `require_once` calls:

   ```php
   require_once GL_PLUGIN_DIR . 'includes/rest-descriptions.php';
   ```

   Already done in both the dev install and the deploy package at
   `projects/work/arcade/ghostlight-wp-plugin/`, which were reconciled on
   2026-08-02.

   **Before activating on production**, define `GL_DESC_DIR` in
   `wp-config.php` so the plugin and `ghostlight.py` agree on where
   descriptions live — step 0 of `ghostlight-deploy/DEPLOY.md`. Skipping it
   points the plugin at a directory the sync never reads.

3. Create an application password: **Users → Profile → Application Passwords**
   in WordPress admin. Put it in this app's `.env` as `WP_USER` and
   `WP_APP_PW`.

4. Check it responds:

   ```bash
   curl -u "$WP_USER:$WP_APP_PW" \
     https://www.arcadecomedytheater.com/wp-json/ghostlight/v1/descriptions
   ```

Nothing needs restarting — WordPress picks up the route on the next request.

## How far it's been verified

- **Syntax**: `php -l` under PHP 8.3 — this file and all 14 plugin files parse
  cleanly.
- **Load**: executed against a stubbed WordPress (see the harness described in
  `HANDOVER.md`). It loads without a fatal and registers both routes.
- **Behaviour**: the list returns untruncated descriptions; a missing slug 404s;
  create returns 201; a description-only `POST` leaves the stored `image_url`
  intact; an empty body on a new slug is refused with a 400 and writes no file;
  the permission callback closes when the user lacks `edit_posts`.

- **In real WordPress**: deployed to wp.deadframe.xyz and exercised there.
  The namespace registers, an unauthenticated call gets 401, an
  application-password call lists all 26 shows with full text, a single GET
  matches the list copy, a missing slug 404s, a description-only POST leaves
  the stored `image_url` intact, and the write lands in `change_log.json` as
  `updated (api)` beside the admin tab's own entries.

Still unverified: production. The package it would deploy from is now
reconciled with dev and lints clean, but has not been run there.
