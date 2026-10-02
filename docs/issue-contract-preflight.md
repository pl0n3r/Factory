# Preflight offline del contrato de Issue

Antes de publicar `/tomar`, un agente puede validar localmente que el body del Issue cumple **los dos contratos que Coordinación fijará en la reserva**: acceptance ejecutable y `factory-plan-task`.

## Uso

Guarda o genera el body del Issue localmente y pásalo por stdin:

```bash
python3 scripts/issue_contract_preflight.py < issue-body.md
```

Éxito devuelve JSON determinista con `valid=true`, fingerprints de acceptance/task, `task_key`, claims, dependencias y criterios. Exit code: `0`.

Un contrato inválido devuelve `valid=false`, un `code` estable y una razón auditable. Exit code: `2`.

## Orden fail-closed

1. valida primero las secciones y criterios con `aceptacion_kit.parse_contract`;
2. fija el fingerprint con `contract_fingerprint`;
3. valida el marker con `orquestador_kit.parse_task_marker`;
4. fija su identidad con `task_marker_fingerprint`.

Si acceptance falla, el task marker ni siquiera se procesa. Un marker ausente o inválido bloquea el preflight.

## Límite de confianza

Este comando **no reserva trabajo** y no autoriza ningún cambio. Tampoco consulta GitHub, red, secretos, tokens, credenciales, branches, PRs ni labels. Solo valida texto local reutilizando los parsers canónicos de Factory.

Después de un preflight verde siguen aplicando kill switch, ranking, dependencias, claims, carreras y todas las demás guardas de `PLAN-AGENTES.md`.
