---
name: factory-security-audit
description: Auditoría de seguridad de cambios en la fábrica pl0n3r - autenticación y autorización, roles, secretos, inyección SQL, XSS/CSRF, aislamiento multiempresa, dependencias vulnerables y configuración insegura. Úsala al revisar PRs de riesgo, tocar auth, SQL, formularios, uploads o permisos.
---

# Auditoría de seguridad

Rol «Seguridad» del plan §4 con perfil en `agentes/roles/seguridad.md`; riesgo alto exige segunda pasada de otro rol. Revisa el diff y los archivos tocados:

1. **AuthN/AuthZ:** toda ruta nueva exige sesión y rol/permiso en el servidor; sin IDOR (el recurso pertenece al usuario/empresa); recuperación de cuenta sin enumeración y con tokens de un solo uso.
2. **Multiempresa (Condor):** toda consulta filtra por empresa/tenant; busca consultas sin `WHERE company/tenant`, cachés o archivos compartidos entre empresas.
3. **Inyección:** SQL solo con parámetros (PDO/Eloquent bindings); `grep` de concatenaciones en SQL, `exec/system/eval`, rutas armadas con entrada de usuario.
4. **XSS/CSRF:** salida escapada por defecto; tokens CSRF en POST/PUT/DELETE; cabeceras y cookies `HttpOnly/Secure/SameSite`.
5. **Secretos:** nada en repo ni logs (D-062: repos públicos); `.env` fuera de git; revisa el diff con `git diff | grep -iE 'key|secret|token|passw'`.
6. **Dependencias:** `composer audit`, `npm audit --omit=dev` si las herramientas existen; sin dependencias nuevas sin motivo.
7. **Config:** debug apagado, permisos mínimos en workflows (`permissions:`), acciones fijadas a SHA, uploads validados.
8. Hallazgo high/critical = veto de merge (D-069). Reporta archivo:línea, explotación realista y arreglo; datos personales → `datos.yml` en el mismo PR.
