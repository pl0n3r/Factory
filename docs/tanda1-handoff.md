# Handoff de TANDA 1

Estado: **bloqueado por evidencia humana/externa; no se debe cerrar ningún gate por inferencia**.

Este documento no reemplaza los Issues fuente. Resume el mínimo que falta para que el dueño o un revisor humano pueda desbloquear TANDA 1 sin reconstruir el historial.

## #9 — puertas de decisión humana

**Ya verificado en GitHub:** clasificación de puertas, etiqueta `decisión: dueño`, asignación, mención única, limpieza e idempotencia; también se ejercitó una decisión real en #35.

**Única evidencia faltante:** confirmar externamente que la notificación correspondiente fue recibida como push en el teléfono del dueño mediante GitHub Mobile.

**No vale como sustituto:** estado success del workflow, comentario de GitHub, asignación o inferencia del agente.

**Default seguro:** mantener #9 abierto/bloqueado si no existe confirmación real de recepción móvil.

## #10 — resiliencia del dueño y de la fábrica

**Ya verificado:** auditoría preventiva de workflows y restore real desde una copia externa a GitHub con hashes verificados.

**Única evidencia faltante:** observar identidades/GitHub Apps realmente separadas para **CI, deploy y observer**, con mínimo privilegio y trazabilidad. No se deben versionar App IDs sensibles, private keys, tokens ni secretos.

**No vale como sustituto:** asumir que tres jobs distintos equivalen a tres identidades, o inferir configuración externa desde `github.token`.

**Default seguro:** mantener #10 abierto/bloqueado hasta disponer de evidencia real de las tres identidades.

## #12 — cumplimiento legal y de datos

**Ya verificado:** gate técnico de evidencia/licencias, inventario técnico de datos por producto, mecanismo real de dependencias de BRVTAL y snapshot npm reproducible ligado al SHA auditado y al run 36001724208.

**Evidencia material faltante por Condor, GrindFlow y BRVTAL:**

1. referencia vigente a política de privacidad;
2. referencia a términos;
3. registro de tratamientos;
4. canal para derechos del titular;
5. política/tabla de retención;
6. revisión de proveedores/encargados;
7. referencia y fecha de revisión jurídica humana.

Las referencias no deben incluir PII, secretos ni texto libre sensible.

**Dependencias/licencias de BRVTAL:** Factory versiona el `package.json` exacto de BRVTAL `138b1bab…` y el `package-lock.json` exacto generado por el run `36001724208` con npm `10.9.8` y `--package-lock-only --ignore-scripts --no-audit --no-fund`. El gate valida hashes canónicos, metadata cerrada y reutiliza `inspect_npm()` sobre el lock, que contiene `@playwright/test → playwright → playwright-core` en `1.63.0` con licencia Apache-2.0. Esto cubre el inventario de licencias de #12 con evidencia técnica reproducible, sin afirmar que el lock reproduzca una instalación histórica de producción. La dependencia vendorizada `qrcode.min.js` conserva su licencia MIT separada.

**No vale como sustituto:** fixtures, búsquedas sin resultado, inferencias del código o el propio inventario técnico de Factory.

**Default seguro:** mantener #12 abierto/bloqueado y no declarar cumplimiento jurídico por inferencia.

## #13 — épico de madurez

#13 depende de #9, #10 y #12. Se cierra únicamente después de que esos tres gates estén materialmente cerrados. No requiere inventar una cuarta evidencia independiente.

## #35 — exposición pública de la cabina

#35 es una decisión separada de dirección de producto. El default B ya está aplicado: **no publicar GitHub Pages todavía**. Mientras se conserve ese default privado, #35 no debe bloquear el cierre técnico de TANDA 1.

## Primer release de Factory

Los tags `v1` y `v1.0.0` no deben crearse mientras TANDA 1 permanezca abierta.

Después de cerrar #1–#14:

1. resolver explícitamente la puerta humana `release-1.0.0`;
2. revalidar el HEAD exacto de `main`;
3. seguir **[release-bootstrap.md](release-bootstrap.md)** para el primer `v1`;
4. validar un consumidor real de `@v1`;
5. recién entonces iniciar TANDA 2.

**Default seguro:** `v1.0.0` permanece **no publicado y no autorizado** hasta que todas esas condiciones sean observables.
