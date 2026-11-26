# Qwen Code: smoke local RED→GREEN (Factory #2219)

**Estado actual: NO DEMOSTRADO.** Este harness implementa un ensayo opt-in, **no** certifica Qwen C1, worker, despacho ni autonomía GitHub. `FIXTURE_ONLY` es solo prueba sintética de las guardas; `TOOL_SMOKE_VERIFIED` exige recibo del CLI real y solo demuestra una edición en laboratorio. `FAILED` y `UNKNOWN` nunca son éxito.

## Uso autorizado

En el **Mac autorizado**, con Qwen Code y el modelo **ya instalados**, servicio Ollama existente en loopback y `/usr/bin/sandbox-exec` funcional:

```bash
python3 scripts/qwen_tool_smoke.py --run --endpoint http://127.0.0.1:11434/v1 --model qwen3:4b
```

Por defecto **no ejecuta** el CLI. Ejecutar sin `--run` devuelve `UNKNOWN` y exit 1. No ejecutarlo en CI ni en el checkout como sandbox. Los únicos tests de CI son offline:

```bash
python3 -m unittest discover -s tests -p 'test_qwen_tool_smoke.py' -v
```

## Límites verificables

- Crea dos archivos Python bajo un directorio temporal **propio**: `module.py` defectuoso (`triple(7)=14`) y `test_module.py` que exige 21; comienza con unittest RED.
- Exige macOS Seatbelt `sandbox-exec` (deny-default, lectura de rutas de runtime, escritura solo en laboratorio, salida de red solo hacia `127.0.0.1`, sin permiso de señales a procesos ajenos); ejecuta sondas negativas de escritura exterior, proceso y red **antes** del CLI. Plataforma/perfil no verificable: `UNKNOWN`, sin invocación Qwen.
- HOME y QWEN_HOME temporales; entorno explícito mínimo, token efímero aleatorio sin credenciales reales, endpoint HTTP `/v1` de IPv4 loopback exacta. No descubre ni transmite tokens del equipo, no descarga modelos, instala binarios, inicia daemons ni detiene procesos ajenos.
- CLI `--bare --core-tools read_file,edit` y aprobación `auto-edit`, sin herramienta shell general; el harness ejecuta `unittest` posterior a la edición **dentro del mismo Seatbelt**, nunca sobre código del modelo sin sandbox. Presupuesto fijo 4 tool calls, 12 turnos y 90 segundos; `exit 55` se registra y solo se atribuye al presupuesto si stderr aporta un indicio explícito; si no, causa `unknown`, **no** fallo general del proveedor.
- Solo acepta eventos **estructurados** `tool_use` + `tool_result` exitoso (ID correlacionado) y resultado terminal del CLI, edición exacta `* 2`→`* 3`, test intacto, unittest GREEN y sin archivos extra ni symlinks (rechazados antes de leer el resultado). JSON escrito como texto, exit 0 aislado o llamadas de API que no editaron fallan.
- Recibo limitado a versiones, modelo, budget, hashes, evidencia estructurada mínima, diff acotado, estados de los tests y causa inmediata. No guarda prompts ni trazas crudas. Limpieza exclusiva del temporal propio; el repositorio y servicios del host no se modifican.

**Advertencia de alcance:** el perfil Seatbelt permite lectura de bibliotecas del sistema y Homebrew; un Qwen instalado fuera de esas rutas puede fallar cerrado. La sonda de red exterior por sí sola no demuestra bloqueo kernel cuando el host está offline; se exige además el perfil deny-default y la ejecución real de Seatbelt. El smoke no prueba acceso a GitHub, integración de productos, despliegue ni `/health`. Si el runtime no está accesible o el CLI no soporta `--core-tools`, permanece `UNKNOWN`.

## Evidencia pendiente

La ejecución real en equipo autorizado debe aportar el JSON terminal del comando con `state=TOOL_SMOKE_VERIFIED`, `runtime_version`, modelo, presupuesto, hash de salida estructurada, diff permitido, hashes de los archivos y estado RED/GREEN. En ausencia de ese recibo el runtime queda **NO DEMOSTRADO**, aunque `Tests de scripts` y `Validar` pasen. Ante `FAILED`/`UNKNOWN`, conservar los hashes y exit code sanitizados; no aumentar el presupuesto indefinidamente ni activar FactoryRunner/ControlBot.
