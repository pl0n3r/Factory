<?php
declare(strict_types=1);
$data = json_decode((string) file_get_contents(__DIR__ . '/../config/version.json'), true, flags: JSON_THROW_ON_ERROR);
$version = $data['version'] ?? '';
if (!is_string($version) || preg_match('/^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$/', $version) !== 1) {
    fwrite(STDERR, "Versión inválida\n");
    exit(1);
}
echo "smoke ok\n";
