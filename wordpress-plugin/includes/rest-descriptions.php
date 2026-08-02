<?php
/**
 * REST API over the show description store.
 *
 * Exposes the same <slug>.json files that the Descriptions tab edits and that
 * ghostlight.py reads as its fallback, so other tools can treat this directory
 * as the single source of truth for a show's evergreen description and poster
 * instead of keeping their own drifting copy.
 *
 * Writes go through gl_desc_save() and gl_desc_log(), exactly as the admin tab
 * does, so the change log records edits from either side.
 *
 * Auth: any user who can edit_posts. Machine clients should authenticate with
 * a WordPress application password over HTTP Basic.
 *
 *   GET  /wp-json/ghostlight/v1/descriptions          → every show
 *   GET  /wp-json/ghostlight/v1/descriptions/<slug>   → one show
 *   POST /wp-json/ghostlight/v1/descriptions/<slug>   → create or update one
 */

defined('ABSPATH') || exit;

define('GL_REST_NS', 'ghostlight/v1');

/** Same capability that gates the admin panel. */
function gl_rest_permission(): bool {
    return current_user_can('edit_posts');
}

/**
 * One show's stored fields. gl_desc_all() truncates descriptions to 140 chars
 * for the admin list, which is no good for a client that intends to display or
 * re-save them, so read the files directly here.
 */
function gl_rest_desc_read(string $slug): ?array {
    $data = gl_desc_get($slug);
    if ($data === null) return null;
    return [
        'slug'        => $slug,
        'description' => (string) ($data['description'] ?? ''),
        'image_url'   => (string) ($data['image_url'] ?? ''),
    ];
}

add_action('rest_api_init', function () {

    register_rest_route(GL_REST_NS, '/descriptions', [
        'methods'             => 'GET',
        'permission_callback' => 'gl_rest_permission',
        'callback'            => function () {
            if (!is_dir(GL_DESC_DIR)) return rest_ensure_response(['descriptions' => []]);
            $out = [];
            foreach (glob(GL_DESC_DIR . '/*.json') ?: [] as $file) {
                $slug = pathinfo($file, PATHINFO_FILENAME);
                if ($slug === 'change_log') continue;
                $row = gl_rest_desc_read($slug);
                if ($row) $out[] = $row;
            }
            usort($out, fn($a, $b) => strcmp($a['slug'], $b['slug']));
            return rest_ensure_response(['descriptions' => $out]);
        },
    ]);

    register_rest_route(GL_REST_NS, '/descriptions/(?P<slug>[A-Za-z0-9\-]+)', [
        [
            'methods'             => 'GET',
            'permission_callback' => 'gl_rest_permission',
            'callback'            => function (WP_REST_Request $req) {
                $slug = sanitize_title($req['slug']);
                $row  = gl_rest_desc_read($slug);
                if ($row === null) {
                    return new WP_Error('gl_not_found', 'No description stored for that slug.', ['status' => 404]);
                }
                return rest_ensure_response($row);
            },
        ],
        [
            'methods'             => 'POST',
            'permission_callback' => 'gl_rest_permission',
            'callback'            => function (WP_REST_Request $req) {
                $slug = sanitize_title($req['slug']);
                if (!$slug) {
                    return new WP_Error('gl_bad_slug', 'Slug is required.', ['status' => 400]);
                }

                $existing = gl_desc_get($slug);
                $is_new   = ($existing === null);
                $existing = $existing ?: [];

                // Merge rather than replace: gl_desc_save() drops any field it
                // is handed as an empty string, so a client sending only a
                // description would otherwise wipe the stored poster.
                $body = $req->get_json_params() ?: $req->get_body_params() ?: [];

                $description = array_key_exists('description', $body)
                    ? sanitize_textarea_field((string) $body['description'])
                    : (string) ($existing['description'] ?? '');

                $image_url = array_key_exists('image_url', $body)
                    ? esc_url_raw((string) $body['image_url'])
                    : (string) ($existing['image_url'] ?? '');

                if ($description === '' && $image_url === '') {
                    return new WP_Error(
                        'gl_empty',
                        'Refusing to write an empty record — send a description or an image_url.',
                        ['status' => 400]
                    );
                }

                gl_desc_save($slug, $description, $image_url);
                gl_desc_log($is_new ? 'created (api)' : 'updated (api)', $slug, gl_current_user());

                $row = gl_rest_desc_read($slug);
                return new WP_REST_Response($row, $is_new ? 201 : 200);
            },
        ],
    ]);
});
