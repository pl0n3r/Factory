<?php
declare(strict_types=1);
$versionData = json_decode((string) file_get_contents(__DIR__ . '/../config/version.json'), true, flags: JSON_THROW_ON_ERROR);
$version = is_array($versionData) && is_string($versionData['version'] ?? null) ? $versionData['version'] : '';
$phase = getenv('PRODUCTION_STAGE') ?: 'construccion';
$releaseSha = getenv('RELEASE_SHA') ?: '';
$schemaRaw = getenv('SCHEMA_UP_TO_DATE');
$schemaUpToDate = $schemaRaw === false ? null : $schemaRaw === '1';
$liveShaValid = preg_match('/^[0-9a-f]{40}$/', $releaseSha) === 1;
$status = $phase === 'live' && !$liveShaValid ? 'degraded' : 'ok';
if ($status !== 'ok') {
    http_response_code(503);
}
header('Content-Type: application/json');
echo json_encode([
    'status' => $status,
    'version' => $version,
    'release_sha' => $releaseSha !== '' ? $releaseSha : null,
    'schema_up_to_date' => $schemaUpToDate,
    'phase' => $phase,
    'evidence' => $phase === 'live' ? 'runtime' : 'construction-stub',
], JSON_THROW_ON_ERROR);
