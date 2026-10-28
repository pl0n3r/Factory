---
name: factory-test-matrix
description: Detecta el stack real del repo (Laravel, PHP/MariaDB, Node, Python, Playwright) y aplica la matriz de pruebas - unitarias, integración, e2e, regresión, análisis estático y smoke. Úsala antes de abrir o empujar un PR, al añadir pruebas o al preguntar "qué pruebo".
---

# Matriz de pruebas

1. Detecta: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/detect_stack.py" .` → stack y comandos **declarados por el propio repo** (composer/npm scripts, phpunit, phpstan, pint, rector, playwright, unittest). No supongas herramientas que no aparecen.
2. Ejecuta de rápido a lento y para en el primer rojo: formato → estático → unitarias/integración → build → e2e. Solo las relevantes al cambio; el suite completo lo corre CI.
3. Por stack: **Laravel** `php artisan test` + pint + phpstan; migraciones con base temporal, nunca producción. **PHP/MariaDB (Condor, ControlBot)** phpunit + phpstan (+ rector dry-run) y pruebas de aislamiento multiempresa. **Node/web (brvtal, AutoFactory)** `npm test`/lint y Playwright cuando haya config. **Python (Factory, FactoryRunner)** `unittest` o los scripts de `package.json`.
4. **Regresión:** todo fix lleva una prueba que falle si se revierte (plan §2). **Smoke:** contra el `/health` real de lectura; nunca escribas en producción.
5. Reporta qué corrió, qué no pudo correr (y por qué) y el resultado exacto; nunca declares verde lo no ejecutado.
