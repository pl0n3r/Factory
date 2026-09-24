# Resiliencia de capacidades y recuperación de Factory

**Roles:** Seguridad + SRE. **Estado:** contrato técnico alineado con la decisión del dueño en #10. Un manifiesto válido demuestra que la evidencia tiene forma y vigencia aceptables; **no demuestra por sí solo que una credencial, backup o restore real exista o haya funcionado**.

## Modelo operativo vigente

Factory valida capacidades y mecanismos, no una cantidad artificial de identidades:

- **CI:** `github-token:ephemeral`, emitido por GitHub Actions para cada corrida y limitado con `permissions` mínimos por job.
- **Observador:** `github-token:ephemeral` con alcance mínimo para el propio repositorio; los health checks del producto usan endpoints públicos cuando aplica.
- **Deploy:** `hostinger:git`; el despliegue no usa una credencial GitHub persistente de Factory.
- **Escritura cross-repo:** requiere una **GitHub App dedicada**, instalada solo en los repos necesarios y con permisos mínimos. El `GITHUB_TOKEN` de un workflow no se eleva ni se sustituye por PAT personal para sortear esta frontera.

No se admiten PATs personales, tokens de larga duración ni aliases libres dentro del manifiesto. Compartir la clase `github-token:ephemeral` entre CI y observador **no significa reutilizar la misma credencial**: GitHub emite tokens efímeros por ejecución y los permisos efectivos los determina cada job.

Los workflows continúan sujetos al auditor preventivo: acciones fijadas a SHA, `pull_request_target` prohibido, sin `write-all` y sin permisos globales de escritura.

## Manifiesto operativo v2

El gate actual acepta únicamente `version: 2` con campos raíz exactos:

- `version`
- `project`
- `execution_mechanisms`
- `cross_repo_write`
- `checks`

Los mecanismos permitidos son exactamente los descritos arriba y `cross_repo_write.required_mechanism` debe ser `github-app`.

Los checks `repo_backup`, `secrets_escrow`, `token_rotation` y `restore_drill` conservan `verified_at` UTC y `evidence_ref` no sensible. La evidencia debe tener como máximo 90 días y no puede estar fechada en el futuro.

## Manifiesto v1: solo migración

El formato v1 histórico con `identities` queda disponible únicamente mediante el validador legacy explícito para **diagnóstico y migración**. No es una configuración operativa vigente y `validate_manifest()` / `--manifest-stdin` lo rechazan con instrucción de migrar a v2.

Mantener el parser legacy evita perder capacidad de inspeccionar evidencia histórica, pero no permite que una configuración nueva pase el gate con la política anterior.

## Respuesta a compromiso o pérdida de acceso

1. **Contener:** revocar el mecanismo o integración afectada y suspender el job/deploy con ese alcance.
2. **Delimitar:** identificar permisos efectivos, repos alcanzables y ventana de exposición sin copiar secretos a Issues o logs.
3. **Rotar:** renovar credenciales donde existan y revocar las anteriores; los tokens efímeros expiran y no se almacenan como evidencia.
4. **Recuperar:** verificar integridad y antigüedad de la copia externa, restaurar en un entorno aislado y comparar refs, tags y artefactos.
5. **Verificar:** ejecutar CI, smoke y prueba de rollback antes de retomar despliegues.
6. **Aprender:** registrar causa, controles preventivos y resultado en `lecciones/` sin PII ni credenciales.

## Entradas del auditor

`python3 seguridad/resiliencia.py --audit-workflows` audita el conjunto canónico de `.github/workflows`. No sustituye actionlint ni una auditoría completa de permisos efectivos por evento.

El manifiesto operativo se entrega exclusivamente por stdin:

```bash
python3 seguridad/resiliencia.py --audit-workflows
python3 seguridad/resiliencia.py --manifest-stdin < /ruta/externa/manifest-v2.json
```

La ruta externa no entra al proceso como argumento ni se registra. El schema es cerrado y los errores no reproducen valores arbitrarios del manifiesto.

## Límites de la evidencia

La validación estructural no prueba hechos externos. El restore real de #10 se verificó mediante evidencia separada; la decisión del dueño definió el modelo de mecanismos vigente. Si en el futuro aparece una escritura cross-repo, esa capacidad debe introducir una GitHub App dedicada y evidencia verificable antes de habilitarse.
