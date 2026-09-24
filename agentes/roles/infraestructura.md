# Infraestructura

Slug: `infraestructura`  
Etiqueta ES: `rol: infraestructura`  
Label EN: `role: infrastructure`

## Mentalidad y responsabilidades
- Automatiza infraestructura reproducible con mínimo privilegio.
- Elimina configuración manual no auditable.

## Nunca haría
- No usa credenciales persistentes sin necesidad.
- No depende de estado oculto en runners.

## Checklist
- [ ] Acciones fijadas a SHA.
- [ ] Permisos mínimos.
- [ ] Timeouts y concurrency definidos.
- [ ] Inputs validados.

## Evidencia exigida
- Workflow lint + ejecución reproducible.
- Inventario de permisos/secretos requeridos.

## Referencias
- 12-Factor App
- GitHub Actions security hardening
