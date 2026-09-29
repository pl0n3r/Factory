# Recovery Manifest v1

#327 define la fuente machine-readable de Recovery. No ejecuta backups.

Cada proyecto declara RPO/RTO propios, retention, sources y restore cadence. La política de protección es explícita y fija el objetivo 3-2-1-1-0: 3 copias, 2 tipos de medio, 1 offsite, 1 copia inmutable/versionada y 0 fallos de restore no detectados.

Sources database/media/repository usan REQUIRED o NOT_APPLICABLE; al menos una debe aplicar. Object storage es el offsite técnico requerido y Google Drive puede declararse como cold-copy opcional o NOT_APPLICABLE. iCloud no forma parte del contrato.

Encryption es obligatoria y el manifiesto solo declara key_material=EXTERNAL_ONLY: nunca contiene llaves, tokens ni credenciales. El validador falla cerrado ante campos desconocidos, tipos/coherencia inválidos o formas sensibles.

#328 define adapters; #329 pipeline/evidence; #330 restore drill; #331 health/Readiness; #332 E2E.
