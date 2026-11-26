# Smoke de Qwen Code: edición real RED→GREEN (#2219)

**Estado de runtime: NO DEMOSTRADO.** El harness versionado no certifica C1, worker autónomo ni operación productiva. `FIXTURE_ONLY` designa exclusivamente los positivos sintéticos; `FAILED` y `UNKNOWN` no son éxito. `TOOL_SMOKE_VERIFIED` requiere recibo del CLI Qwen real y solo acredita este laboratorio.

## Invocación opt-in en Mac autorizado
```bash
python3 scripts/qwen_tool_smoke.py --run
python3 -m unittest discover -s tests -p 'test_qwen_tool_smoke.py' -v
```
Sin `--run` el script no llama Qwen y devuelve `UNKNOWN` (exit 1); **CI solo ejecuta tests offline**. Se necesitan Qwen Code, modelo `qwen3:4b` y servidor Ollama **preexistentes** en `127.0.0.1:11434/v1`. El endpoint/modelo están fijados por código; no se aceptan proveedores remotos ni flags para ampliarlos. No instala ni descarga modelos, arranca daemons, usa GitHub o invoca shell general desde Qwen.

## Guardas y evidencia
- Fixture privado en `TemporaryDirectory` propio, padre y lab del usuario con modo `0700` y sin symlinks; HOME temporal; macOS Seatbelt `deny default` para filesystem/procesos y salida solo hacia loopback. Sondas de rechazo de escritura exterior, red y procesos antes del CLI; perfil no verificable = `UNKNOWN`, sin ejecución.
- Presupuesto 4 tool calls, 12 turnos, 90 s; herramientas `read_file,edit`, `auto-edit` restringido al sandbox. El harness ejecuta unittest RED inicial y, únicamente tras verificar el diff permitido, GREEN dentro del mismo sandbox, sin modificar el test.
- Aceptación exige `tool_use` de edición y `tool_result` correlacionados **de la salida estructurada real**, exit 0, diff exacto `triple(7):14→21`, test SHA inmutable, GREEN y ninguna ruta adicional. Un exit 0 aislado, JSON de herramienta en texto o archivo adicional fracasan. `exit 55` no se atribuye a presupuesto sin evidencia saneada de stderr.
- Recibo limitado a versión/modelo/presupuesto, estado de herramientas, SHA-256 de fixture/test/eventos, diff permitido y unittest; no registra secretos, prompts de terceros ni stdout bruto. La limpieza solo elimina el directorio propio. El sandbox depende de capacidades reales del Mac y no prueba C1 ni operación de servicios.
- **Evidencia real pendiente:** ejecutar exclusivamente por canal autorizado sobre equipo preparado y conservar el recibo primario correlacionado. Si no existe acceso, sigue `NO DEMOSTRADO` aunque CI y `Validar` estén verdes; ver [#2067](https://github.com/pl0n3r/Factory/issues/2067).
