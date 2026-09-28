STATE
objetivo: corregir fallo de Playwright en el flujo de login de Condor
repo: pl0n3r/Condor
issue: #210
pr: #215
head: trabajo/issue-210@6e862e9a1b2c3d4e5f60718293a4b5c6d7e8f901
decisiones:
- el login no maneja credenciales reales en pruebas
confirmado:
- el fallo viene del wiring de test, no del transporte productivo
- Backend y Validar están verdes
no repetir:
- reintentar Playwright sin cambiar APP_ENV=test (falló 3 veces por lo mismo)
pendiente:
- Playwright
siguiente: validar el contenedor en APP_ENV=test y relanzar solo Playwright
