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
require_true(($spec['authentication']['allowlist_required'] ?? false) === true, 'allowlist required');
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
