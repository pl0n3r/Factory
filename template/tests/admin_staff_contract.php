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
require_true(($spec['authentication']['method_normalization'] ?? '') === 'ASCII_UPPERCASE', 'method normalization required');
require_true(($spec['authentication']['body_hash_source'] ?? '') === 'raw_request_body_bytes_before_decode', 'raw body bytes must be hashed');
require_true(($spec['authentication']['body_hash_encoding'] ?? '') === 'sha256_hex_lowercase_64', 'body hash encoding required');
require_true(($spec['authentication']['canonical_request_encoding'] ?? '') === 'UTF-8', 'canonical request must be UTF-8');
require_true(($spec['authentication']['line_separator'] ?? '') === 'LF', 'canonical request must use LF');
require_true(($spec['authentication']['signature_encoding'] ?? '') === 'hex_lowercase_64', 'signature encoding required');
require_true(($spec['authentication']['json_reserialization_forbidden'] ?? false) === true, 'JSON reserialization must be forbidden');
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
require_true(($spec['mutations']['idempotency_scope'] ?? []) === ['product', 'actor_key_id', 'action', 'target'], 'idempotency scope must be portable');
require_true(($spec['mutations']['fingerprint_encoding'] ?? '') === 'sha256_hex_lowercase_64', 'idempotency fingerprint encoding required');
require_true((int)($spec['mutations']['retention_min_seconds'] ?? 0) >= 86400, 'idempotency retention must be at least 24h');
require_true((int)($spec['mutations']['retention_min_seconds'] ?? 0) !== (int)($spec['authentication']['nonce_ttl_seconds'] ?? 0), 'idempotency retention must be distinct from nonce TTL');
require_true(($spec['mutations']['store_result_with_fingerprint'] ?? false) === true, 'idempotency must store result with fingerprint');
require_true(($spec['mutations']['equivalent_retry'] ?? '') === 'return_same_logical_result_without_side_effect', 'equivalent retries must not repeat effects');
require_true(($spec['mutations']['mismatched_fingerprint_status'] ?? null) === 409, 'mismatched idempotency fingerprint must be 409');
require_true(($spec['mutations']['nonce_ttl_is_separate'] ?? false) === true, 'nonce TTL and idempotency retention must stay separate');
require_true(($spec['mutations']['invalidate_active_authority_on_suspend_or_privilege_reduction'] ?? false) === true, 'suspension and privilege reduction must invalidate active authority');
require_true(($spec['rate_limit']['required'] ?? false) === true, 'rate limit required');
require_true(($spec['search']['empty_query_allowed'] ?? true) === false, 'empty staff search forbidden');
require_true(($spec['audit']['required'] ?? false) === true, 'audit required');
require_true(($spec['scope']['physical_delete'] ?? true) === false, 'physical delete forbidden');
require_true(($spec['scope']['bulk_export'] ?? true) === false, 'bulk export forbidden');
require_true(($spec['scope']['protected_subject_mutation_forbidden'] ?? false) === true, 'protected authority mutation forbidden');
require_true(in_array('owner', $spec['scope']['protected_subjects'] ?? [], true), 'owner must be protected');
require_true(in_array('platform_owner', $spec['scope']['protected_roles'] ?? [], true), 'platform owner must be protected');
require_true(($spec['scope']['product_role_mapping_required'] ?? false) === true, 'product role mapping required');
require_true(($spec['invitation_delivery']['server_side_handoff_required'] ?? false) === true, 'server-side invitation handoff required');
require_true(($spec['invitation_delivery']['success_requires_handoff'] ?? false) === true, 'invite success requires handoff');
require_true(($spec['invitation_delivery']['token_in_response'] ?? true) === false, 'invitation token must not be returned');
require_true(($spec['invitation_delivery']['failure_policy'] ?? '') === 'fail_and_leave_no_usable_invitation', 'failed delivery must leave no usable invitation');

$methods = array_column($spec['operations'] ?? [], 'method');
require_true(!in_array('DELETE', $methods, true), 'DELETE operation forbidden');

$privacy = $spec['privacy']['required_treatments'] ?? [];
require_true(count($privacy) >= 3, 'privacy treatments missing');
foreach ($privacy as $row) {
    require_true(($row['basis'] ?? '') === 'review_required', 'legal basis must remain under review');
    require_true(($row['providers'] ?? null) === [], 'provider must not be invented');
}

$fixture = $spec['authentication']['known_answer'] ?? [];
require_true(hash('sha256', (string)($fixture['body'] ?? '')) === ($fixture['body_sha256'] ?? ''), 'known-answer body hash mismatch');
$canonical = implode("\n", [
    (string)($fixture['key_id'] ?? ''),
    (string)($fixture['method'] ?? ''),
    (string)($fixture['path_with_sorted_query'] ?? ''),
    (string)($fixture['timestamp'] ?? ''),
    (string)($fixture['nonce'] ?? ''),
    (string)($fixture['body_sha256'] ?? ''),
]);
require_true($canonical === ($fixture['canonical_request'] ?? ''), 'known-answer canonical request mismatch');
require_true(
    hash_hmac('sha256', $canonical, (string)($fixture['key'] ?? '')) === ($fixture['signature'] ?? ''),
    'known-answer HMAC mismatch'
);

echo "admin staff contract ok\n";
