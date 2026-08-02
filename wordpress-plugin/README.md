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

3. Create an application password: **Users → Profile → Application Passwords**
   in WordPress admin. Put it in this app's `.env` as `WP_USER` and
   `WP_APP_PW`.

4. Check it responds:

   ```bash
   curl -u "$WP_USER:$WP_APP_PW" \
     https://www.arcadecomedytheater.com/wp-json/ghostlight/v1/descriptions
   ```

Nothing needs restarting — WordPress picks up the route on the next request.

## Not verified yet

There's no PHP runtime on the machine this was written on, so the file has
only been checked structurally (balanced braces, correct opening tag, no
closing `?>`). It has never been executed. Load it on a staging site first if
you have one, and watch for a fatal on plugin load.
