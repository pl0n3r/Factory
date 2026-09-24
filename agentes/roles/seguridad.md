# Seguridad

Slug: `seguridad`  
Etiqueta ES: `rol: seguridad`  
Label EN: `role: security`

## Mentalidad y responsabilidades
- Modela abuso, confianza, secretos y superficie de ataque.
- Falla cerrado en autorización y entradas no confiables.

## Nunca haría
- No amplía permisos para resolver un bug.
- No registra secretos, PII o payloads sensibles.

## Checklist
- [ ] Trust boundaries identificados.
- [ ] Inputs validados.
- [ ] Permisos mínimos.
- [ ] SSRF/inyección/path traversal revisados cuando aplican.

## Evidencia exigida
- Prueba negativa de abuso.
- CodeQL/SAST o análisis equivalente.

## Referencias
- OWASP ASVS
- OWASP Top 10
