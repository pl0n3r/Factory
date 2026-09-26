<?php
declare(strict_types=1);

function fail_contract(string $message): never {
    fwrite(STDERR, $message . PHP_EOL);
    exit(1);
}

function require_true(bool $condition, string $message): void {
    if (!$condition) {
        fail_contract($message);
    }
}

$path = __DIR__ . '/../ops/admin-staff-api.json';
$raw = file_get_contents($path);
require_true($raw !== false, 'admin staff contract missing');
$spec = json_decode($raw, true, 64, JSON_THROW_ON_ERROR);

require_true(($spec['version'] ?? null) === 1, 'unsupported contract version');
require_true(($spec['enabled_by_default'] ?? true) === false, 'contract must default off');
require_true(($spec['authentication']['mode'] ?? '') === 'hmac-sha256', 'HMAC required');
require_true(($spec['authentication']['fail_closed_without_key'] ?? false) === true, 'missing key must fail closed');
require_true(($spec['authentication']['route_registration']['requires_configured_key'] ?? false) === true, 'routes require configured key');
require_true(($spec['authentication']['route_registration']['requires_allowlist'] ?? false) === true, 'routes require configured allowlist');
require_true(($spec['authentication']['route_registration']['disabled_behavior'] ?? '') === 'routes_absent_404', 'disabled ops routes must be absent');
require_true(($spec['authentication']['allowlist_required'] ?? false) === true, 'allowlist required');
require_true(($spec['transport']['scheme'] ?? '') === 'https', 'HTTPS required');
require_true(($spec['transport']['certificate_validation_required'] ?? false) === true, 'certificate validation required');
require_true(($spec['transport']['cleartext_http_forbidden'] ?? false) === true, 'cleartext HTTP forbidden');
require_true(($spec['transport']['hmac_provides_confidentiality'] ?? true) === false, 'HMAC is not encryption');
require_true(($spec['authentication']['canonical_request'] ?? '') === "KEY_ID\nMETHOD\nPATH_WITH_SORTED_QUERY\nTIMESTAMP\nNONCE\nSHA256(BODY)", 'canonical request must contain LF separators');
$query = $spec['authentication']['query_canonicalization'] ?? [];
require_true(($query['representation'] ?? '') === 'ordered_pairs', 'query must preserve ordered pairs');
require_true(($query['preserve_duplicate_keys'] ?? false) === true, 'duplicate query keys must be preserved');
require_true(($query['raw_plus_forbidden'] ?? false) === true, 'raw plus must be rejected');
require_true(($query['space_encoding'] ?? '') === '%20', 'spaces must use RFC3986 encoding');
require_true(($query['literal_plus_encoding'] ?? '') === '%2B', 'literal plus must be encoded');
require_true(($query['percent_hex_case'] ?? '') === 'uppercase', 'percent escapes must be uppercase');
require_true(($query['sort'] ?? []) === ['encoded_name', 'encoded_value'], 'query sort order must be deterministic');
require_true(($spec['mutations']['idempotency_key_required'] ?? false) === true, 'mutation idempotency required');
require_true(($spec['mutations']['idempotency_key_location'] ?? '') === 'header', 'idempotency key must live in a header');
require_true(($spec['mutations']['idempotency_key_header'] ?? '') === 'Idempotency-Key', 'idempotency header name must be portable');
require_true(($spec['mutations']['invalidate_active_authority_on_suspend_or_privilege_reduction'] ?? false) === true, 'suspension and privilege reduction must invalidate active authority');
require_true(($spec['rate_limit']['required'] ?? false) === true, 'rate limit required');
require_true(($spec['search']['empty_query_allowed'] ?? true) === false, 'empty staff search forbidden');
require_true(($spec['audit']['required'] ?? false) === true, 'audit required');
require_true(($spec['scope']['physical_delete'] ?? true) === false, 'physical delete forbidden');
require_true(($spec['scope']['bulk_export'] ?? true) === false, 'bulk export forbidden');

$methods = array_column($spec['operations'] ?? [], 'method');
require_true(!in_array('DELETE', $methods, true), 'DELETE operation forbidden');

$privacy = $spec['privacy']['required_treatments'] ?? [];
require_true(count($privacy) >= 3, 'privacy treatments missing');
foreach ($privacy as $row) {
    require_true(($row['basis'] ?? '') === 'review_required', 'legal basis must remain under review');
    require_true(($row['providers'] ?? null) === [], 'provider must not be invented');
}

echo "admin staff contract ok\n";
