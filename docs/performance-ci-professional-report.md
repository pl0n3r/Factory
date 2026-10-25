# Reporte profesional read-only de CI FactoryRunner (#1506; épico #304)

`performance.ci_professional_report.diagnose_factoryrunner_ci_professionals`
compone el adaptador GET-only `evaluate_factoryrunner_ci_run` (#1497) y
`compile_performance_team` (#1504) sin recalcular presupuestos ni duplicar
algoritmos Readiness. El caller debe autenticar por su cuenta el GET de GitHub
para una corrida exacta de `pl0n3r/FactoryRunner` con `event=push`,
`head_branch=main`, `name=CI` y `completed/success`. El módulo es puro,
no hace llamadas HTTP ni recibe tokens.

**Señal auténtica, no arreglo:** run #40119747013, SHA
`33277d549a82e9cba5371982d1d80e43e06bd0d5`, elapsed **130 segundos**
contra budget `lte 120s`, un exceso de 10 segundos (8,3 %).
El contrato `performance/contracts/factoryrunner.json` permite únicamente
`observe, diagnose, benchmark`; no autoriza `create_work_item` ni
`auto_repair`.

En CURRENT + PERF_DEGRADATION, el resultado contiene Readiness canónico y
una **recomendación** de profesionales real de Team Compiler para investigar
el cuello, no asignación ni diagnóstico causal verificado. Un run sano
sintético devuelve NO_ASSIGNMENT; STALE/UNKNOWN devuelve Readiness UNKNOWN
sin equipo. Datos de corrida no canónicos fallan cerrado. La proyección copia
solamente campos canónicos saneados, nunca payload arbitrario, credenciales
ni logs.

`authority=unchanged`, `execute_actions=false`,
`create_work_item=false`, `dispatch=false`, `adopt=false` y
`candidate_terminal=false` siguen siendo invariantes. Esta hoja solo avanza
el handoff diagnóstico: **no cumple** AC-05, AC-07, AC-08 ni AC-11 operativo
del padre #304. Un E2E auténtico requerirá permiso y un fix medido
sobre FactoryRunner con WorkItem/PR, AFTER comparable y decisión humana
cuando corresponda. No modifica Factory@v1 ni publica releases.

Pruebas:
`python3 -m unittest discover -s tests -p test_performance_ci_professional_report.py -v`.
