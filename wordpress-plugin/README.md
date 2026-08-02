# WordPress side

The plugin half of this now lives in its own repo:

**<https://github.com/pyprk/ghostlight>**

```
ghostlight/
├── wordpress-plugin/   the WP plugin, including the descriptions REST route
├── sync/               ghostlight.py, the Airtable → WordPress sync
└── DEPLOY.md           deploying both halves
```

The PHP used to be vendored here because the plugin wasn't under version
control anywhere. It is now, so the copy is gone — a second copy is how the
descriptions drifted in the first place.

## What this app depends on

`/api/descriptions` proxies the plugin's REST route:

```
GET  /wp-json/ghostlight/v1/descriptions          every show
GET  /wp-json/ghostlight/v1/descriptions/<slug>   one show
POST /wp-json/ghostlight/v1/descriptions/<slug>   create or update
```

Auth is a WordPress application password over HTTP Basic — `WP_URL`,
`WP_USER` and `WP_APP_PW` in `.env`.

**`GL_DESC_DIR` has to match on whichever site you point at.** The plugin
defaults to `wp-content/uploads/arcade-descriptions`; production keeps the
store beside `ghostlight.py` and must define it in `wp-config.php`. If they
disagree, this app and the website end up editing different files and nothing
errors. See step 0 of the ghostlight repo's `DEPLOY.md`.

## Status

Deployed and verified on the dev site, **wp.deadframe.xyz**. Not yet on
production.
