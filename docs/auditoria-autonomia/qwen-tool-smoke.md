# Qwen Code: contrato de edición RED→GREEN (#2219)
**Runtime: NO DEMOSTRADO.** El laboratorio opt-in no certifica C1, worker, GitHub ni producción. `FIXTURE_ONLY` es solo evidencia sintética; `FAILED` y `UNKNOWN` nunca acreditan ejecución real.
## Invocación en Mac autorizado
```bash
python3 scripts/qwen_tool_smoke.py --run
python3 -m unittest discover -s tests -p 'test_qwen_tool_smoke.py' -v
```
Sin `--run` no invoca Qwen. Solo usa modelo `qwen3:4b` y Ollama **preexistente** en `127.0.0.1:11434/v1`; no instala modelos, arranca servicios ni accede a GitHub, secretos o repositorios. CI ejecuta únicamente pruebas offline.
## Puertas fail-closed
- El laboratorio y HOME viven en un directorio temporal propio (modo 0700); macOS Seatbelt deny-default, salida solo loopback y sondas negativas de filesystem/red/proceso **antes del CLI**. Rechaza paths simbólicos, perfil manipulado, archivos extra, timeout y tests alterados.
- **Qwen Code 0.26.9: ejecución bloqueada hasta auditoría del inventario de herramientas.** Su `--bare` ignora `--core-tools`, por lo que el harness retorna `UNKNOWN` sin invocar el prompt mientras `VERIFIED_TOOL_VERSIONS` no contenga una versión auditada. `--help` o `exit 0` nunca prueban la allowlist. No habilitar versiones sin inventario efectivo verificado de exactamente `read_file` y `edit`.
- Presupuesto máximo: 4 tool calls, 12 turnos, 90 s; unittest RED al inicio y GREEN dentro del sandbox solo para diff exacto `triple(7):14→21`, prueba intacta en bytes LF, perfil íntegro y eventos estructurados `tool_use`/`tool_result` correlacionados. JSON textual no cuenta como llamada efectiva; `exit 55` exige causa saneada.
- Recibo mínimo: versión, modelo, budget, SHA-256 de archivos/eventos, diff permitido y unittest, sin prompts ni logs crudos. Sin ejecución autorizada con herramientas verificadas, conservar **NO DEMOSTRADO** y no inferir C1; evidencia histórica [#2067](https://github.com/pl0n3r/Factory/issues/2067).
